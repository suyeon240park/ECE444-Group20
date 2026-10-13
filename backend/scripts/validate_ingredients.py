"""Offline validation: python -m scripts.validate_ingredients [--directory PATH]."""

import argparse
from pathlib import Path

from app.services.ingredient_knowledge import (
    CONTENT_DIR,
    IngredientKnowledgeError,
    load_ingredient_knowledge,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=CONTENT_DIR)
    args = parser.parse_args(argv)
    try:
        knowledge = load_ingredient_knowledge(args.directory)
    except IngredientKnowledgeError as exc:
        print(f"Invalid ingredient knowledge base: {exc}")
        return 1
    print(f"Validated {len(knowledge.entries)} reviewed ingredient entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
