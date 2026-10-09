import json
from pathlib import Path

import pytest
import requests

from app.services import label_extraction as le
from app.services.label_extraction import (
    LabelExtractionError,
    VisionConfig,
    extract_label,
    extract_label_file,
    mime_type_for,
    normalize_reply,
)

CONFIG = VisionConfig(api_key="test-key", model="test-model", base_url="https://api.test")

GOOD_REPLY = {
    "table_found": True,
    "serving": {
        "size_text": "Per 6 crackers  (30 g)",
        "household": "6 crackers",
        "quantity": 30,
        "unit": "g",
    },
    "servings_per_package": None,
    "nutrients": {
        "calories": {"amount": 140, "unit": "Cal", "daily_value_percent": 7},
        "total_fat": {"amount": 5, "unit": "g", "daily_value_percent": 7},
        "saturated_fat": {"amount": 0.5, "unit": "g", "daily_value_percent": 4},
        "trans_fat": {"amount": 0, "unit": "g", "daily_value_percent": None},
        "sodium": {"amount": 310, "unit": "mg", "daily_value_percent": 13},
        "potassium": {"amount": 90, "unit": "mg", "daily_value_percent": 2},
    },
    "unreadable_fields": ["nutrients.fibre.amount", "servings_per_package", 7],
}


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text or json.dumps(body)

    def json(self):
        return self._body


def gemini_body(text, usage=None, finish="STOP"):
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
        "usageMetadata": (
            {"promptTokenCount": 1800, "candidatesTokenCount": 300, "thoughtsTokenCount": 200}
            if usage is None
            else usage
        ),
    }


class FakePost:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_normalize_reply_maps_fields_and_drops_extras():
    result = normalize_reply(GOOD_REPLY)

    assert result["status"] == "found"
    assert result["serving"] == {
        "size_text": "Per 6 crackers (30 g)",
        "household": "6 crackers",
        "quantity": 30.0,
        "unit": "g",
    }
    assert result["package"] == {"servings_per_package": None}
    nutrients = result["nutrition"]["nutrients"]
    assert set(nutrients) == set(le.NUTRIENT_UNITS)
    # Calories keep their own unit and never carry a %DV.
    assert nutrients["calories"] == {"amount": 140.0, "unit": "kcal", "daily_value_percent": None}
    assert nutrients["sodium"] == {"amount": 310.0, "unit": "mg", "daily_value_percent": 13.0}
    assert nutrients["trans_fat"] == {"amount": 0.0, "unit": "g", "daily_value_percent": None}
    assert nutrients["fibre"] is None
    assert result["nutrition"]["basis"] == "serving"
    assert result["unreadable_fields"] == [
        "nutrition.nutrients.fibre.amount",
        "package.servings_per_package",
    ]
    assert result["rejected_fields"] == []


def test_normalize_reply_not_found():
    assert normalize_reply({"table_found": False}) == {"status": "not_found"}


@pytest.mark.parametrize("reply", [[], {"table_found": "yes"}, {}])
def test_normalize_reply_rejects_malformed_replies(reply):
    with pytest.raises(LabelExtractionError):
        normalize_reply(reply)


def test_normalize_reply_rejects_invalid_values_instead_of_guessing():
    result = normalize_reply(
        {
            "table_found": True,
            "serving": {"quantity": 0, "unit": "oz"},
            "servings_per_package": "about 4",
            "nutrients": {
                "sodium": {"amount": 0.31, "unit": "g", "daily_value_percent": 13},
                "sugars": {"amount": -1, "unit": "g"},
                "protein": {"amount": True, "unit": "g"},
                "fibre": "2 g",
            },
        }
    )

    assert result["serving"]["quantity"] is None
    assert result["serving"]["unit"] is None
    assert result["package"]["servings_per_package"] is None
    # A wrong unit is not converted: the amount is dropped, the printed %DV kept.
    assert result["nutrition"]["nutrients"]["sodium"] == {
        "amount": None,
        "unit": None,
        "daily_value_percent": 13.0,
    }
    assert result["nutrition"]["nutrients"]["sugars"] is None
    assert result["nutrition"]["nutrients"]["protein"] is None
    assert result["nutrition"]["nutrients"]["fibre"] is None
    assert len(result["rejected_fields"]) == 6
    assert result["unreadable_fields"] == []


def test_normalize_reply_without_nutrients_has_no_basis():
    result = normalize_reply({"table_found": True, "serving": "30 g", "nutrients": None})
    assert result["nutrition"]["basis"] is None
    assert result["serving"]["quantity"] is None


def test_extract_label_sends_photo_and_counts_tokens():
    post = FakePost(FakeResponse(body=gemini_body(json.dumps(GOOD_REPLY))))

    extraction = extract_label(b"jpeg-bytes", "image/jpeg", CONFIG, post=post)

    url, kwargs = post.calls[0]
    assert url == "https://api.test/models/test-model:generateContent"
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    parts = kwargs["json"]["contents"][0]["parts"]
    assert parts[0]["inline_data"] == {"mime_type": "image/jpeg", "data": "anBlZy1ieXRlcw=="}
    assert parts[1]["text"] == le.PROMPT
    assert kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert extraction.result["serving"]["quantity"] == 30.0
    assert extraction.model == "test-model"
    assert extraction.input_tokens == 1800
    assert extraction.output_tokens == 500
    assert extraction.latency_seconds >= 0


def test_extract_label_ignores_thoughts_and_code_fences():
    body = gemini_body("```json\n" + json.dumps({"table_found": False}) + "\n```", usage={})
    body["candidates"][0]["content"]["parts"].insert(0, {"text": "thinking...", "thought": True})

    extraction = extract_label(b"x", "image/png", CONFIG, post=FakePost(FakeResponse(body=body)))

    assert extraction.result == {"status": "not_found"}
    assert extraction.input_tokens == 0


def test_extract_label_retries_when_rate_limited():
    waits = []
    post = FakePost(
        FakeResponse(429, text="quota"),
        FakeResponse(503, text="busy"),
        FakeResponse(body=gemini_body('{"table_found": false}')),
    )

    extraction = extract_label(b"x", "image/png", CONFIG, post=post, sleep=waits.append)

    assert extraction.result == {"status": "not_found"}
    assert waits == [le.RETRY_WAIT_SECONDS, le.RETRY_WAIT_SECONDS]


def test_extract_label_gives_up_after_retries():
    post = FakePost(*[FakeResponse(429, text="quota")] * (le.MAX_RETRIES + 1))
    with pytest.raises(LabelExtractionError, match="HTTP 429"):
        extract_label(b"x", "image/png", CONFIG, post=post, sleep=lambda s: None)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse(400, text="bad key"), "HTTP 400"),
        (FakeResponse(body={"promptFeedback": {"blockReason": "SAFETY"}}), "SAFETY"),
        (FakeResponse(body=gemini_body('{"table_found": tr', finish="MAX_TOKENS")), "MAX_TOKENS"),
        (requests.Timeout(), "no reply within 60 s"),
        (requests.ConnectionError("offline"), "request failed"),
    ],
)
def test_extract_label_errors(response, message):
    with pytest.raises(LabelExtractionError, match=message):
        extract_label(b"x", "image/png", CONFIG, post=FakePost(response))


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", " key ")
    monkeypatch.setenv("VISION_MODEL", "")
    monkeypatch.setenv("VISION_TIMEOUT_SECONDS", "30")
    config = VisionConfig.from_env()
    assert (config.api_key, config.model, config.timeout_seconds) == ("key", le.DEFAULT_MODEL, 30)

    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(LabelExtractionError, match="GEMINI_API_KEY"):
        VisionConfig.from_env()


def test_mime_types(tmp_path: Path):
    assert mime_type_for(Path("a.JPG")) == "image/jpeg"
    assert mime_type_for(Path("a.heic")) == "image/heic"
    with pytest.raises(LabelExtractionError, match="unsupported"):
        mime_type_for(Path("a.gif"))

    photo = tmp_path / "label.png"
    photo.write_bytes(b"png")
    post = FakePost(FakeResponse(body=gemini_body('{"table_found": false}')))
    extract_label_file(photo, CONFIG, post=post)
    assert post.calls[0][1]["json"]["contents"][0]["parts"][0]["inline_data"]["mime_type"] == (
        "image/png"
    )
