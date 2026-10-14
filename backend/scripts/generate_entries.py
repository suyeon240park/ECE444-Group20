"""Generate ingredient entry JSON files from a compact seed data file.

Instead of hand-writing ~60 lines of JSON per ingredient, authors fill in a
seed file that defines shared sources once and keeps each ingredient to its
essential fields.  This script expands seed records into full schema-version-1
entry files and validates every one through the production loader.

Run from backend/:
    python -m scripts.generate_entries --seed content/ingredients/seed.json
    python -m scripts.generate_entries --seed content/ingredients/seed.json --dry-run
"""

import argparse
import json
from datetime import date
from pathlib import Path

from app.services.ingredient_knowledge import (
    CONTENT_DIR,
    IngredientKnowledgeError,
    load_source_policy,
    parse_entry,
)


def load_seed(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expand_entry(item: dict, shared_sources: dict, today: str) -> dict:
    sources = []
    for sid in item["source_ids"]:
        if sid not in shared_sources:
            raise ValueError(f"{item['id']}: unknown source '{sid}'")
        src = shared_sources[sid]
        sources.append(
            {
                "id": sid,
                "publisher": src["publisher"],
                "title": src["title"],
                "url": src["url"],
                "published_on": src.get("published_on"),
                "accessed_on": src.get("accessed_on", today),
            }
        )

    what_refs = item.get("what_it_is_sources", item["source_ids"][:1])
    why_refs = item.get("why_used_sources", item["source_ids"][:1])
    expl_refs = item.get("explanation_sources", item["source_ids"][:1])

    return {
        "schema_version": 1,
        "ingredient": {
            "id": item["id"],
            "name": item["name"],
            "aliases": item.get("aliases", []),
            "e_numbers": item.get("e_numbers", []),
            "ins_numbers": item.get("ins_numbers", []),
            "what_it_is": {
                "text": item["what_it_is"],
                "source_ids": what_refs,
            },
            "why_used": {
                "text": item["why_used"],
                "source_ids": why_refs,
            },
            "explanation": {
                "text": item["explanation"],
                "source_ids": expl_refs,
            },
            "sources": sources,
            "last_reviewed": item.get("last_reviewed", today),
            "authority_positions": item.get("authority_positions", []),
            "flag": item.get("flag", None),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=CONTENT_DIR / "entries")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    seed = load_seed(args.seed)
    shared_sources = {s["id"]: s for s in seed["sources"]}
    today = date.today().isoformat()
    allowed_hosts = load_source_policy()

    generated = 0
    skipped = 0
    errors = 0

    for item in seed["ingredients"]:
        entry_id = item["id"]
        out_path = args.output / f"{entry_id}.json"
        if out_path.exists():
            skipped += 1
            continue
        try:
            full = expand_entry(item, shared_sources, today)
            parse_entry(full["ingredient"], allowed_hosts, entry_id)
        except (IngredientKnowledgeError, ValueError, KeyError) as exc:
            print(f"  ERROR {entry_id}: {exc}")
            errors += 1
            continue

        if args.dry_run:
            print(f"  [dry-run] would write {out_path.name}")
        else:
            out_path.write_text(
                json.dumps(full, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  wrote {out_path.name}")
        generated += 1

    print(f"\nGenerated: {generated}  Skipped (exist): {skipped}  Errors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
