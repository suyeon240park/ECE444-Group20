#!/usr/bin/env python3
"""Generate reviewed additive entries for issue #35.

Reads additive definitions from additive_seed.json and expands each into
a full schema-v1 JSON file under backend/content/ingredients/entries/.
"""

import json
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SEED = BACKEND / "content" / "ingredients" / "additive_seed.json"
ENTRIES = BACKEND / "content" / "ingredients" / "entries"

sys.path.insert(0, str(BACKEND))

TODAY = date.today().isoformat()


def expand_entry(item: dict, shared_sources: dict, today: str) -> dict:
    sources = []
    for sid in item["source_ids"]:
        if sid in shared_sources:
            sources.append(deepcopy(shared_sources[sid]))
        else:
            raise ValueError(f"{item['id']}: unknown shared source {sid!r}")

    for extra in item.get("extra_sources", []):
        sources.append(extra)

    entry = {
        "id": item["id"],
        "name": item["name"],
        "aliases": item.get("aliases", []),
        "e_numbers": item.get("e_numbers", []),
        "ins_numbers": item.get("ins_numbers", []),
        "what_it_is": {
            "text": item["what_it_is"]["text"],
            "source_ids": item["what_it_is"]["source_ids"],
        },
        "why_used": {
            "text": item["why_used"]["text"],
            "source_ids": item["why_used"]["source_ids"],
        },
        "explanation": {
            "text": item["explanation"]["text"],
            "source_ids": item["explanation"]["source_ids"],
        },
        "sources": sources,
        "last_reviewed": today,
        "authority_positions": item.get("authority_positions", []),
        "flag": item.get("flag", None),
    }
    return {"schema_version": 1, "ingredient": entry}


def main():
    dry_run = "--dry-run" in sys.argv

    with open(SEED, encoding="utf-8") as f:
        seed = json.load(f)

    shared_sources = seed["shared_sources"]
    ingredients = seed["ingredients"]

    written = 0
    skipped = 0
    errors = 0

    for item in ingredients:
        out = ENTRIES / f"{item['id']}.json"
        if out.exists():
            print(f"  SKIP  {item['id']} (already exists)")
            skipped += 1
            continue
        try:
            doc = expand_entry(item, shared_sources, TODAY)
        except Exception as exc:
            print(f"  ERROR {item['id']}: {exc}")
            errors += 1
            continue

        if dry_run:
            print(f"  DRY   {item['id']}")
        else:
            out.write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  WRITE {item['id']}")
        written += 1

    print(f"\n{written} written, {skipped} skipped, {errors} errors")

    if not dry_run and written > 0:
        from app.services.ingredient_knowledge import load_ingredient_knowledge

        print("\nValidating through production loader...")
        try:
            kb = load_ingredient_knowledge()
            print(f"OK — {len(kb.entries)} total entries loaded")
        except Exception as exc:
            print(f"VALIDATION FAILED: {exc}")
            sys.exit(1)


if __name__ == "__main__":
    main()
