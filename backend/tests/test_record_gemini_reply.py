"""Tests for scripts/record_gemini_reply.py (#44). Gemini is replaced by ``responses``."""

from __future__ import annotations

import json

import pytest
import responses

from app.services.label_extraction import DEFAULT_BASE_URL, VisionConfig
from scripts import record_gemini_reply
from tests.test_end_to_end import OVERLOADED, PHOTOS, RECORDED

CONFIG = VisionConfig(api_key="test-key", model="primary-model")
PHOTO = PHOTOS / "005_crackers.jpg"
REPLY = json.loads((RECORDED / "gemini_005_crackers.json").read_text("utf-8"))["reply"]


def url(model: str) -> str:
    return f"{DEFAULT_BASE_URL}/models/{model}:generateContent"


@responses.activate
def test_records_the_reply_of_the_first_model_that_answers():
    responses.post(url("primary-model"), status=503, json=OVERLOADED)
    responses.post(url("fallback-model"), json=REPLY)

    recorded = record_gemini_reply.record(PHOTO, CONFIG, ("fallback-model",))

    assert recorded == {"model": "fallback-model", "reply": REPLY}


@responses.activate
def test_stops_when_no_model_answers():
    responses.post(url("primary-model"), status=503, json=OVERLOADED)

    with pytest.raises(SystemExit, match="no model returned a usable reply"):
        record_gemini_reply.record(PHOTO, CONFIG, ())


@responses.activate
def test_main_writes_the_model_and_reply_but_not_the_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    monkeypatch.setenv("VISION_MODEL", "primary-model")
    monkeypatch.setenv("VISION_FALLBACK_MODELS", "")
    monkeypatch.setattr(record_gemini_reply, "load_dotenv", lambda: None)
    responses.post(url("primary-model"), json=REPLY)
    output = tmp_path / "reply.json"

    record_gemini_reply.main([str(PHOTO), str(output)])

    text = output.read_text("utf-8")
    assert json.loads(text) == {"model": "primary-model", "reply": REPLY}
    assert "secret-test-key" not in text
