"""Record the vision model's raw reply to a label photo, for the end-to-end tests (#44).

The end-to-end tests replay these replies instead of calling Gemini, so CI needs no
API key. Usage, from ``backend/`` with ``GEMINI_API_KEY`` set (``.env`` is read)::

    python -m scripts.record_gemini_reply \\
        ../tests/fixtures/nutrition_labels/images/008_ketchup.jpg \\
        tests/fixtures/e2e/gemini_008_ketchup.json

The photo is prepared exactly as the server prepares it (``prepare_photo``), and
VISION_MODEL then each fallback model is tried, as ``LabelReader`` does. Only the
reply body is saved, with the model that gave it; the request (and so the API key)
is never written.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from app.services.label_extraction import LabelExtractionError, VisionConfig, extract_label
from app.services.label_reading import (
    DEFAULT_FALLBACK_MODELS,
    _give_up,
    parse_models,
    prepare_photo,
)


def record(photo: Path, config: VisionConfig, fallbacks: tuple[str, ...]) -> dict[str, Any]:
    image = prepare_photo(photo.read_bytes())
    replies: list[requests.Response] = []

    def post(*args: Any, **kwargs: Any) -> requests.Response:
        response = requests.post(*args, **kwargs)
        replies.append(response)
        return response

    for model in (config.model, *fallbacks):
        try:
            extract_label(
                image, "image/jpeg", replace(config, model=model), post=post, sleep=_give_up
            )
        except LabelExtractionError as error:
            print(f"{model}: {error}", file=sys.stderr)
            continue
        return {"model": model, "reply": replies[-1].json()}
    raise SystemExit("no model returned a usable reply")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    load_dotenv()
    config = VisionConfig.from_env()
    fallbacks = parse_models(
        os.getenv("VISION_FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS), config.model
    )
    recorded = record(args.photo, config, fallbacks)
    args.output.write_text(json.dumps(recorded, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"{args.photo.name}: recorded {recorded['model']} reply to {args.output}")


if __name__ == "__main__":
    main()
