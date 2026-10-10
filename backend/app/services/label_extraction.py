"""Prototype: read a Nutrition Facts table from a photo with a vision-model API (#16).

Time-boxed spike for deciding whether the photo fallback stays in scope (Q1, #4).
The photo goes to Google's Gemini API with a prompt asking for the table as JSON,
and the reply is checked and normalized into the field names of the product
contract (#20), so results can be scored against hand-transcribed labels
(``scripts/label_benchmark.py``).

Vision models do not report per-field confidence, so nothing here is marked
"confident": values the model could not read clearly come back as None and are
listed in ``unreadable_fields``. Q1's confidence rule is still to be designed.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Nutrients read from the table, in Canadian Nutrition Facts table order. Same names
# and units as CANONICAL_UNITS in app/models/product.py (#20); a test keeps them in sync.
NUTRIENT_UNITS: dict[str, str] = {
    "calories": "kcal",
    "total_fat": "g",
    "saturated_fat": "g",
    "trans_fat": "g",
    "carbohydrate": "g",
    "fibre": "g",
    "sugars": "g",
    "protein": "g",
    "cholesterol": "mg",
    "sodium": "mg",
}
SERVING_UNITS = ("g", "ml")

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}

# Free-tier keys are rate limited; wait and retry instead of failing the photo.
RETRY_STATUSES = (429, 503)
MAX_RETRIES = 2
RETRY_WAIT_SECONDS = 30

PROMPT = """\
The photo shows a Canadian food package. Read its Nutrition Facts table \
("Nutrition Facts / Valeur nutritive") and return one JSON object and nothing else.

If no Nutrition Facts table is visible, or it is too blurred to read, return \
{"table_found": false}.

Otherwise return:
{
  "table_found": true,
  "serving": {"size_text": string|null, "household": string|null,
              "quantity": number|null, "unit": "g"|"mL"|null},
  "servings_per_package": number|null,
  "nutrients": {"<name>": {"amount": number|null, "unit": string|null,
                           "daily_value_percent": number|null}},
  "unreadable_fields": [string]
}

Nutrient names: calories, total_fat, saturated_fat, trans_fat, carbohydrate, fibre, \
sugars, protein, cholesterol, sodium.

Rules:
- Copy values exactly as printed. Never calculate, estimate or fill in a value from \
general knowledge.
- Use null for anything not printed on the table. If something is printed but you \
cannot read it with certainty, use null and add its path (for example \
"nutrients.sodium.amount" or "serving.quantity") to unreadable_fields.
- Serving: size_text is the English serving statement without "Per", for example \
"6 crackers (30 g)"; household is the household measure ("6 crackers"); quantity and \
unit are the metric amount (30, "g").
- servings_per_package only when the label prints it.
- calories: amount is the number, unit "kcal", daily_value_percent null.
- The table prints one %DV for "Saturated + Trans": put it on saturated_fat and leave \
trans_fat's daily_value_percent null.
- If the table has several columns (for example "as sold" and "prepared", or two \
serving sizes), use only the first column.
- Ignore the French text, and potassium, calcium, iron and other vitamins and minerals.
"""


class LabelExtractionError(Exception):
    """The API call failed or its reply could not be used."""


@dataclass(frozen=True)
class VisionConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 60
    base_url: str = DEFAULT_BASE_URL

    @classmethod
    def from_env(cls) -> VisionConfig:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise LabelExtractionError("GEMINI_API_KEY is not set (see backend/.env.example)")
        return cls(
            api_key=api_key,
            model=os.getenv("VISION_MODEL", "").strip() or DEFAULT_MODEL,
            timeout_seconds=float(os.getenv("VISION_TIMEOUT_SECONDS", "60")),
        )


@dataclass(frozen=True)
class Extraction:
    """Normalized result of one photo plus what it cost to get."""

    result: dict[str, Any]
    model: str
    latency_seconds: float
    input_tokens: int
    output_tokens: int


def mime_type_for(path: Path) -> str:
    try:
        return MIME_TYPES[path.suffix.lower()]
    except KeyError:
        raise LabelExtractionError(f"unsupported image type: {path.name}") from None


def extract_label_file(path: Path, config: VisionConfig, **kwargs: Any) -> Extraction:
    return extract_label(path.read_bytes(), mime_type_for(path), config, **kwargs)


def extract_label(
    image: bytes,
    mime_type: str,
    config: VisionConfig,
    *,
    post: Callable[..., Any] = requests.post,
    sleep: Callable[[float], None] = time.sleep,
) -> Extraction:
    """Send one photo to the model and return the normalized table."""
    url = f"{config.base_url}/models/{config.model}:generateContent"
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image).decode("ascii"),
                        }
                    },
                    {"text": PROMPT},
                ]
            }
        ],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    headers = {"x-goog-api-key": config.api_key, "Content-Type": "application/json"}

    for attempt in range(MAX_RETRIES + 1):
        started = time.perf_counter()
        try:
            response = post(url, headers=headers, json=body, timeout=config.timeout_seconds)
        except requests.Timeout:
            raise LabelExtractionError(f"no reply within {config.timeout_seconds:g} s") from None
        except requests.RequestException as exc:
            raise LabelExtractionError(f"request failed: {exc}") from None
        latency = time.perf_counter() - started
        if response.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
            sleep(RETRY_WAIT_SECONDS)
            continue
        break

    if response.status_code != 200:
        raise LabelExtractionError(f"HTTP {response.status_code}: {response.text[:300]}")

    try:
        data = response.json()
    except ValueError:
        raise LabelExtractionError(f"reply is not JSON: {response.text[:200]!r}") from None
    if not isinstance(data, dict):
        raise LabelExtractionError(f"reply is not a JSON object: {str(data)[:200]!r}")
    reply = _parse_reply(data)
    usage = _dict(data.get("usageMetadata"))
    return Extraction(
        result=normalize_reply(reply),
        model=config.model,
        latency_seconds=latency,
        input_tokens=_count(usage, "promptTokenCount"),
        # Thinking tokens are billed as output.
        output_tokens=_count(usage, "candidatesTokenCount") + _count(usage, "thoughtsTokenCount"),
    )


def _dict(value: Any) -> dict[str, Any]:
    """The value if it is a JSON object, else an empty one: the API sometimes sends null."""
    return value if isinstance(value, dict) else {}


def _count(usage: dict[str, Any], key: str) -> int:
    """A token count, or 0 when missing or malformed; it only feeds the cost report."""
    value = usage.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _parse_reply(data: dict[str, Any]) -> Any:
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        reason = _dict(data.get("promptFeedback")).get("blockReason") or "no candidates"
        raise LabelExtractionError(f"model returned no answer ({reason})")
    candidate = _dict(candidates[0])
    parts = _dict(candidate.get("content")).get("parts")
    if not isinstance(parts, list):
        parts = []
    text = "".join(
        p["text"]
        for p in parts
        if isinstance(p, dict) and isinstance(p.get("text"), str) and not p.get("thought")
    )
    # JSON mode should prevent code fences, but strip them if the model adds them.
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        finish = candidate.get("finishReason", "unknown")
        raise LabelExtractionError(
            f"reply is not JSON (finishReason {finish}): {text[:200]!r}"
        ) from None


def normalize_reply(reply: Any) -> dict[str, Any]:
    """Turn the model's JSON into the prototype's result shape.

    Invalid values (negative, non-numeric, wrong unit) become None and are listed
    in ``rejected_fields``; they are never repaired or guessed.
    """
    if not isinstance(reply, dict):
        raise LabelExtractionError("reply is not a JSON object")
    found = reply.get("table_found")
    if found is False:
        return {"status": "not_found"}
    if found is not True:
        raise LabelExtractionError(f"reply has no valid table_found: {found!r}")

    rejected: list[str] = []

    def number(path: str, value: Any, *, positive: bool = False) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            rejected.append(f"{path}: not a number ({value!r})")
            return None
        if not math.isfinite(value):
            rejected.append(f"{path}: not a finite number ({value!r})")
            return None
        if value < 0 or (positive and value == 0):
            rejected.append(f"{path}: out of range ({value!r})")
            return None
        return float(value)

    serving_in = reply.get("serving") if isinstance(reply.get("serving"), dict) else {}
    serving_unit = _unit(serving_in.get("unit"))
    if serving_unit is not None and serving_unit not in SERVING_UNITS:
        rejected.append(f"serving.unit: unexpected unit ({serving_in.get('unit')!r})")
        serving_unit = None
    serving = {
        "size_text": _text(serving_in.get("size_text")),
        "household": _text(serving_in.get("household")),
        "quantity": number("serving.quantity", serving_in.get("quantity"), positive=True),
        "unit": serving_unit,
    }

    nutrients_in = reply.get("nutrients") if isinstance(reply.get("nutrients"), dict) else {}
    nutrients: dict[str, dict[str, Any] | None] = {}
    for name, canonical in NUTRIENT_UNITS.items():
        nutrients[name] = _nutrient(name, canonical, nutrients_in.get(name), number, rejected)

    unreadable_in = reply.get("unreadable_fields")
    unreadable = [
        _result_path(p)
        for p in (unreadable_in if isinstance(unreadable_in, list) else [])
        if isinstance(p, str) and p.strip()
    ]

    return {
        "status": "found",
        "serving": serving,
        "package": {
            "servings_per_package": number(
                "package.servings_per_package", reply.get("servings_per_package"), positive=True
            )
        },
        "nutrition": {
            "basis": "serving" if any(v is not None for v in nutrients.values()) else None,
            "nutrients": nutrients,
        },
        "unreadable_fields": unreadable,
        "rejected_fields": rejected,
    }


def _nutrient(
    name: str,
    canonical: str,
    value: Any,
    number: Callable[..., float | None],
    rejected: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    path = f"nutrition.nutrients.{name}"
    amount = number(f"{path}.amount", value.get("amount"))
    if amount is not None and name != "calories":
        unit = _unit(value.get("unit"))
        if unit != canonical:
            rejected.append(f"{path}.unit: expected {canonical!r}, got {value.get('unit')!r}")
            amount = None
    daily_value = (
        None
        if name == "calories"
        else number(f"{path}.daily_value_percent", value.get("daily_value_percent"))
    )
    if amount is None and daily_value is None:
        return None
    return {
        "amount": amount,
        "unit": canonical if amount is not None else None,
        "daily_value_percent": daily_value,
    }


def _text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return " ".join(value.split())


def _unit(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower()


def _result_path(path: str) -> str:
    """Map the prompt's field paths onto the result's paths."""
    path = path.strip()
    if path.startswith("nutrients."):
        return "nutrition." + path
    if path == "servings_per_package":
        return "package.servings_per_package"
    return path
