"""Read one Nutrition Facts photo with the vision model and print the result (#16).

python -m scripts.extract_label path/to/photo.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.services.label_extraction import LabelExtractionError, VisionConfig, extract_label_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo", type=Path)
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        extraction = extract_label_file(args.photo, VisionConfig.from_env())
    except LabelExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    output = {
        **extraction.result,
        "meta": {
            "model": extraction.model,
            "latency_seconds": round(extraction.latency_seconds, 2),
            "input_tokens": extraction.input_tokens,
            "output_tokens": extraction.output_tokens,
        },
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
