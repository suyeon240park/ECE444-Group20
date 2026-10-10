"""Malformed API replies always end in LabelExtractionError (review of PR #27)."""

import json
import math

import pytest

from app.services.label_extraction import (
    LabelExtractionError,
    VisionConfig,
    extract_label,
    normalize_reply,
)

CONFIG = VisionConfig(api_key="k", model="m", base_url="https://api.test")
NOT_FOUND = json.dumps({"table_found": False})


class Reply:
    def __init__(self, body=None, text="", status_code=200, not_json=False):
        self.status_code = status_code
        self._body = body
        self._not_json = not_json
        self.text = text or json.dumps(body)

    def json(self):
        if self._not_json:
            raise ValueError("Expecting value")
        return self._body


def run(reply):
    return extract_label(b"x", "image/png", CONFIG, post=lambda url, **kw: reply)


def candidate(**overrides):
    base = {"content": {"parts": [{"text": NOT_FOUND}]}, "finishReason": "STOP"}
    return {"candidates": [{**base, **overrides}]}


@pytest.mark.parametrize(
    "reply",
    [
        Reply(text="<html>busy</html>", not_json=True),
        Reply(body=["not", "an", "object"]),
        Reply(body=None, text="null"),
        Reply(body={"candidates": None, "promptFeedback": None}),
        Reply(body={"candidates": "nope"}),
        Reply(body={"candidates": [None]}),
        Reply(body=candidate(content=None)),
        Reply(body=candidate(content={"parts": None})),
        Reply(body=candidate(content={"parts": [{"text": None}, "junk", 7]})),
    ],
)
def test_malformed_replies_raise_label_extraction_error(reply):
    with pytest.raises(LabelExtractionError):
        run(reply)


def test_null_usage_metadata_and_counts_do_not_lose_the_result():
    body = candidate()
    for usage in (
        None,
        {"promptTokenCount": None, "candidatesTokenCount": "3", "thoughtsTokenCount": True},
    ):
        extraction = run(Reply(body={**body, "usageMetadata": usage}))
        assert extraction.result == {"status": "not_found"}
        assert (extraction.input_tokens, extraction.output_tokens) == (0, 0)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_rejected(value):
    result = normalize_reply(
        {
            "table_found": True,
            "serving": {"quantity": value, "unit": "g"},
            "nutrients": {"sodium": {"amount": value, "unit": "mg", "daily_value_percent": value}},
        }
    )
    assert result["serving"]["quantity"] is None
    assert result["nutrition"]["nutrients"]["sodium"] is None
    assert len(result["rejected_fields"]) == 3
