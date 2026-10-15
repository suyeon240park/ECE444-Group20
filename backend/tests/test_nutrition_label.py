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
    MAX_EDGE_PIXELS,
    LabelReader,
    LabelReadingError,
    extract_without_waiting,
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
    """Records each call and returns a fixed reply, or raises a fixed error."""

    def __init__(self, reply=REPLY, error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def __call__(self, image, mime_type, config):
        self.calls.append((image, mime_type, config))
        if self.error is not None:
            raise self.error
        return Extraction(normalize_reply(self.reply), config.model, 1.0, 10, 10)


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
    assert config is CONFIG


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


@responses.activate
def test_reads_a_model_reply_end_to_end():
    url = f"{CONFIG.base_url}/models/{CONFIG.model}:generateContent"
    reply = {"candidates": [{"content": {"parts": [{"text": json.dumps(REPLY)}]}}]}
    responses.post(url, json=reply)

    extraction = extract_without_waiting(PHOTO, "image/png", CONFIG)

    assert extraction.result["nutrition"]["nutrients"]["sodium"]["amount"] == 230
