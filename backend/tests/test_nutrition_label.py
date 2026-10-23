"""Tests for the Nutrition Facts photo endpoint and its service (#42).

The vision model is replaced by a fake extractor: no API calls run in CI.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import responses
import yaml
from PIL import Image

from app import create_app
from app.models.product import Certainty, Source
from app.routes.nutrition_label import ERROR_CODES
from app.services.label_extraction import (
    Extraction,
    LabelExtractionError,
    LabelExtractionTimeout,
    VisionConfig,
    normalize_reply,
)
from app.services.label_reading import (
    DEFAULT_FALLBACK_MODELS,
    MAX_EDGE_PIXELS,
    LabelReader,
    LabelReadingError,
    extract_without_waiting,
    give_up_on_rate_limit,
    parse_models,
    prepare_photo,
    to_contract,
)

CONFIG = VisionConfig(api_key="test-key", model="test-model")

# A Ritz-style label as the model would return it.
REPLY = {
    "table_found": True,
    "serving": {
        "size_text": "6 crackers (30 g)",
        "household": "6 crackers",
        "quantity": 30,
        "unit": "g",
    },
    "servings_per_package": 7,
    "nutrients": {
        "calories": {"amount": 150, "unit": "kcal", "daily_value_percent": None},
        "total_fat": {"amount": 8, "unit": "g", "daily_value_percent": 11},
        "saturated_fat": {"amount": 1, "unit": "g", "daily_value_percent": 5},
        "sodium": {"amount": 230, "unit": "mg", "daily_value_percent": 10},
        "fibre": {"amount": None, "unit": None, "daily_value_percent": 2},
    },
    "unreadable_fields": ["nutrients.fibre.amount"],
}


def encode(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


PHOTO = encode(Image.new("RGB", (60, 40), "white"))


class FakeExtractor:
    """Records each call and returns a fixed reply, or raises a fixed error.

    ``errors`` maps a model name to the error that model raises.
    """

    def __init__(self, reply=REPLY, error=None, errors=None):
        self.reply = reply
        self.error = error
        self.errors = errors or {}
        self.calls = []

    def __call__(self, image, mime_type, config):
        self.calls.append((image, mime_type, config))
        error = self.errors.get(config.model, self.error)
        if error is not None:
            raise error
        return Extraction(normalize_reply(self.reply), config.model, 1.0, 10, 10)

    @property
    def models(self):
        return [config.model for _, _, config in self.calls]


def client_with(reader):
    app = create_app({"TESTING": True})
    app.extensions["label_reader"] = reader
    return app.test_client()


def post_photo(client, data=PHOTO, filename="label.png", content_type="image/png"):
    return client.post(
        "/api/nutrition-label",
        data={"image": (io.BytesIO(data), filename, content_type)},
        content_type="multipart/form-data",
    )


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.get_json()
    assert body["error"]["code"] == code
    assert body["error"]["message"]


# --- Endpoint: success -----------------------------------------------------------------


def test_label_photo_returns_a_nutrition_only_result():
    extractor = FakeExtractor()
    response = post_photo(client_with(LabelReader(CONFIG, extract=extractor)))

    assert response.status_code == 200
    body = response.get_json()
    assert body["result"] == "nutrition_only"
    product = body["product"]
    assert product["barcode"] is None and product["name"] is None
    assert product["source"]["provider"] == "nutrition_label_photo"
    assert product["serving"] == {
        "size_text": "6 crackers (30 g)",
        "quantity": 30,
        "unit": "g",
        "source": "nutrition_label_photo",
        "certainty": "uncertain",
    }
    assert product["package"]["servings_per_package"] == 7
    assert product["package"]["certainty"] == "uncertain"
    nutrients = product["nutrition"]["nutrients"]
    assert product["nutrition"]["basis"] == "serving"
    assert nutrients["sodium"] == {
        "amount": 230,
        "unit": "mg",
        "daily_value_percent": 10,
        "source": "nutrition_label_photo",
        "certainty": "uncertain",
    }
    assert nutrients["calories"]["amount"] == 150
    assert nutrients["fibre"] is None  # only the %DV was read
    assert nutrients["protein"] is None
    assert len(extractor.calls) == 1
    _, mime_type, config = extractor.calls[0]
    assert mime_type == "image/jpeg"
    assert config == CONFIG


def test_unconfirmed_serving_is_reported_missing_until_the_user_confirms_it():
    """Q1: an uncertain serving size must not be used to scale nutrients."""
    body = post_photo(client_with(LabelReader(CONFIG, extract=FakeExtractor()))).get_json()

    assert "serving.size_text" in body["missing_fields"]
    assert "nutrition.nutrients.sodium" in body["missing_fields"]
    assert body["completeness"] == "incomplete"  # nothing is usable before confirmation


def test_label_without_nutrients_still_returns_the_serving():
    reply = {
        "table_found": True,
        "serving": {"size_text": "1 cup (250 mL)", "quantity": 250, "unit": "mL"},
    }
    body = post_photo(client_with(LabelReader(CONFIG, extract=FakeExtractor(reply)))).get_json()

    assert body["product"]["serving"]["unit"] == "ml"
    assert body["product"]["nutrition"]["basis"] is None
    assert body["product"]["package"]["source"] is None


# --- Endpoint: errors ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (LabelExtractionTimeout("slow"), 504, "upstream_timeout"),
        (LabelExtractionError("HTTP 500"), 502, "upstream_unavailable"),
    ],
)
def test_vision_model_failures(error, status, code):
    response = post_photo(client_with(LabelReader(CONFIG, extract=FakeExtractor(error=error))))

    assert_error(response, status, code)


def test_no_table_in_photo_is_422():
    reader = LabelReader(CONFIG, extract=FakeExtractor({"table_found": False}))

    assert_error(post_photo(client_with(reader)), 422, "nutrition_table_not_found")


def test_without_an_api_key_the_endpoint_is_503():
    extractor = FakeExtractor()

    response = post_photo(client_with(LabelReader(None, extract=extractor)))

    assert_error(response, 503, "photo_reading_unavailable")
    assert extractor.calls == []


def test_app_without_gemini_key_answers_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = create_app({"TESTING": True}).test_client()

    assert_error(post_photo(client), 503, "photo_reading_unavailable")


def test_app_with_gemini_key_configures_the_reader(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    app = create_app({"TESTING": True})

    assert app.extensions["label_reader"]._config is not None


def test_missing_image_field():
    client = client_with(LabelReader(CONFIG, extract=FakeExtractor()))
    response = client.post("/api/nutrition-label", data={}, content_type="multipart/form-data")

    assert_error(response, 400, "missing_image")


def test_request_that_is_not_multipart():
    client = client_with(LabelReader(CONFIG, extract=FakeExtractor()))

    assert_error(client.post("/api/nutrition-label", json={}), 400, "missing_image")


def test_file_that_is_not_an_image_is_rejected_before_the_model():
    extractor = FakeExtractor()

    response = post_photo(client_with(LabelReader(CONFIG, extract=extractor)), data=b"not an image")

    assert_error(response, 400, "invalid_image")
    assert extractor.calls == []


def test_unsupported_image_type():
    gif = encode(Image.new("RGB", (10, 10), "white"), "GIF")

    response = post_photo(
        client_with(LabelReader(CONFIG, extract=FakeExtractor())),
        data=gif,
        content_type="image/gif",
    )

    assert_error(response, 415, "unsupported_media_type")


@pytest.mark.parametrize("brand", [b"heic", b"mif1"])
def test_heic_photo_is_refused_by_name(brand):
    heic = b"\x00\x00\x00\x18ftyp" + brand + b"\x00" * 20
    extractor = FakeExtractor()

    response = post_photo(
        client_with(LabelReader(CONFIG, extract=extractor)),
        data=heic,
        filename="IMG_0001.HEIC",
        content_type="image/heic",
    )

    assert_error(response, 415, "unsupported_media_type")
    assert "HEIC" in response.get_json()["error"]["message"]
    assert extractor.calls == []


def test_upload_over_size_limit():
    app = create_app({"TESTING": True, "MAX_CONTENT_LENGTH": 64})
    app.extensions["label_reader"] = LabelReader(CONFIG, extract=FakeExtractor())

    assert_error(post_photo(app.test_client()), 413, "file_too_large")


def test_wrong_method_is_405():
    assert (
        create_app({"TESTING": True}).test_client().get("/api/nutrition-label").status_code == 405
    )


# --- Service ---------------------------------------------------------------------------


def test_prepare_photo_shrinks_large_photos_and_converts_to_jpeg():
    large = encode(Image.new("RGBA", (MAX_EDGE_PIXELS * 2, MAX_EDGE_PIXELS), (255, 255, 255, 0)))

    prepared = Image.open(io.BytesIO(prepare_photo(large)))

    assert prepared.format == "JPEG"
    assert prepared.size == (MAX_EDGE_PIXELS, MAX_EDGE_PIXELS // 2)


def test_prepare_photo_keeps_small_photos_at_their_size():
    prepared = Image.open(io.BytesIO(prepare_photo(PHOTO)))

    assert prepared.size == (60, 40)


def test_prepare_photo_passes_validation_errors_through():
    with pytest.raises(LabelReadingError) as raised:
        prepare_photo(b"")

    assert raised.value.code == "invalid_image"
    assert raised.value.status == 400


def test_to_contract_marks_every_value_uncertain():
    reading = to_contract(normalize_reply(REPLY))

    assert reading.serving.source is Source.NUTRITION_LABEL_PHOTO
    assert reading.serving.certainty is Certainty.UNCERTAIN
    assert not reading.serving.is_usable
    assert reading.package.certainty is Certainty.UNCERTAIN
    values = [v for v in reading.nutrition.nutrients.values() if v is not None]
    assert values and all(v.certainty is Certainty.UNCERTAIN for v in values)


def test_to_contract_of_an_empty_table():
    reading = to_contract(normalize_reply({"table_found": True}))

    assert reading.serving.source is None
    assert reading.package.source is None
    assert reading.nutrition.basis is None


# --- Contract --------------------------------------------------------------------------

SPEC = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.yaml").read_text(
        encoding="utf-8"
    )
)


def test_spec_lists_every_error_code_the_endpoint_returns():
    schema = SPEC["components"]["schemas"]["PhotoError"]
    assert schema["properties"]["error"]["properties"]["code"]["enum"] == list(ERROR_CODES)


def test_spec_documents_every_status_the_endpoint_returns():
    responses = SPEC["paths"]["/api/nutrition-label"]["post"]["responses"]
    assert set(responses) == {"200", "400", "413", "415", "422", "502", "503", "504"}


# --- Real extractor, mocked HTTP -------------------------------------------------------


@responses.activate
def test_rate_limit_fails_fast_instead_of_waiting():
    url = f"{CONFIG.base_url}/models/{CONFIG.model}:generateContent"
    responses.post(url, status=429, body="quota exceeded")

    response = post_photo(client_with(LabelReader(CONFIG)))

    assert_error(response, 502, "upstream_unavailable")
    assert len(responses.calls) == 1


def test_give_up_on_rate_limit_raises_instead_of_sleeping():
    with pytest.raises(LabelExtractionError):
        give_up_on_rate_limit(30)


@responses.activate
def test_reads_a_model_reply_end_to_end():
    url = f"{CONFIG.base_url}/models/{CONFIG.model}:generateContent"
    reply = {"candidates": [{"content": {"parts": [{"text": json.dumps(REPLY)}]}}]}
    responses.post(url, json=reply)

    extraction = extract_without_waiting(PHOTO, "image/png", CONFIG)

    assert extraction.result["nutrition"]["nutrients"]["sodium"]["amount"] == 230


@responses.activate
def test_overloaded_model_falls_back_to_the_next_one():
    overloaded = f"{CONFIG.base_url}/models/{CONFIG.model}:generateContent"
    fallback = f"{CONFIG.base_url}/models/backup-model:generateContent"
    responses.post(overloaded, status=503, body="high demand")
    reply = {"candidates": [{"content": {"parts": [{"text": json.dumps(REPLY)}]}}]}
    responses.post(fallback, json=reply)

    response = post_photo(client_with(LabelReader(CONFIG, fallback_models=["backup-model"])))

    assert response.status_code == 200
    assert response.get_json()["product"]["nutrition"]["nutrients"]["sodium"]["amount"] == 230
    assert [call.request.url for call in responses.calls] == [overloaded, fallback]


# --- Fallback models -------------------------------------------------------------------


def test_fallback_model_is_used_when_the_primary_fails():
    extractor = FakeExtractor(errors={"test-model": LabelExtractionError("HTTP 404")})
    reader = LabelReader(CONFIG, extract=extractor, fallback_models=["backup-a", "backup-b"])

    response = post_photo(client_with(reader))

    assert response.status_code == 200
    assert extractor.models == ["test-model", "backup-a"]
    assert all(config.api_key == CONFIG.api_key for _, _, config in extractor.calls)


def test_every_model_failing_is_502():
    extractor = FakeExtractor(error=LabelExtractionError("HTTP 503"))
    reader = LabelReader(CONFIG, extract=extractor, fallback_models=["backup-a", "backup-b"])

    assert_error(post_photo(client_with(reader)), 502, "upstream_unavailable")
    assert extractor.models == ["test-model", "backup-a", "backup-b"]


def test_timeout_is_not_retried_on_another_model():
    """The user has already waited the full timeout; a second one would double it."""
    extractor = FakeExtractor(errors={"test-model": LabelExtractionTimeout("slow")})
    reader = LabelReader(CONFIG, extract=extractor, fallback_models=["backup-a"])

    assert_error(post_photo(client_with(reader)), 504, "upstream_timeout")
    assert extractor.models == ["test-model"]


def test_table_not_found_is_not_retried_on_another_model():
    extractor = FakeExtractor({"table_found": False})
    reader = LabelReader(CONFIG, extract=extractor, fallback_models=["backup-a"])

    assert_error(post_photo(client_with(reader)), 422, "nutrition_table_not_found")
    assert extractor.models == ["test-model"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("b, a ,b,,c", ("b", "c")),
        ("", ()),
        (" , ", ()),
    ],
)
def test_parse_models(value, expected):
    assert parse_models(value, primary="a") == expected


def test_app_reads_fallback_models_from_the_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("VISION_MODEL", "main")
    monkeypatch.setenv("VISION_FALLBACK_MODELS", "backup, main")

    reader = create_app({"TESTING": True}).extensions["label_reader"]

    assert reader._fallback_models == ("backup",)


def test_app_has_default_fallback_models(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("VISION_FALLBACK_MODELS", raising=False)

    reader = create_app({"TESTING": True}).extensions["label_reader"]

    assert reader._fallback_models == parse_models(DEFAULT_FALLBACK_MODELS, reader._config.model)
    assert reader._fallback_models  # not empty


def test_empty_setting_disables_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("VISION_FALLBACK_MODELS", "")

    assert create_app({"TESTING": True}).extensions["label_reader"]._fallback_models == ()
