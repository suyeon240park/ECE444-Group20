"""Replay a frozen OFF sample; report exploratory checks without health claims.

Run from backend: python -m scripts.check_ingredient_dataset --output PATH
No live calls or parser-generated expected answers. Production observations are
reported separately from the unchanged synthetic-fixture assertions.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import (
    IngredientKnowledgeBase,
    load_ingredient_knowledge,
    load_source_policy,
)
from app.services.ingredient_parser import parse_ingredients
from app.services.normalize import normalize_off_product
from scripts.ingredient_production_report import production_row, production_summary

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/ingredients"


def evaluate(snapshot, expectations):
    entries = json.loads((FIXTURES / "entries.json").read_text(encoding="utf-8"))
    knowledge = IngredientKnowledgeBase(((e["id"], e) for e in entries), load_source_policy())
    service = IngredientAnalysisService(knowledge)
    production = IngredientAnalysisService(load_ingredient_knowledge())
    results = []
    for record in snapshot["records"]:
        row = {k: record[k] for k in ("barcode", "sample_name", "category", "http_status")}
        body = record["response"]
        if body.get("status") not in {"success", "success_with_warnings"}:
            row["lookup_status"] = "not_found" if record["http_status"] == 404 else "error"
            results.append(row)
            continue
        product = normalize_off_product(
            body["product"], record["barcode"], datetime.fromisoformat(record["retrieved_at"])
        )
        row["lookup_status"] = "found"
        row["ingredients_text"] = product.ingredients_text
        row["candidates"] = (
            [
                c.lookup_text
                for c in parse_ingredients(product.ingredients_text, knowledge).candidates
            ]
            if product.ingredients_text
            else []
        )
        result = service.analyze(product).to_dict()
        row.update(
            status=result["status"],
            checked_count=result["checked_count"],
            total_count=result["total_count"],
            matched_ids=[m["ingredient"]["id"] for m in result["matched"]],
            unmatched=[u["text"] for u in result["unmatched"]],
            warnings=result["warnings"],
            coverage_text=result["coverage_text"],
        )
        row["invariants"] = {
            "coverage_counts_agree": result["total_count"]
            == len(result["matched"]) + len(result["unmatched"]),
            "no_coverage_claim_without_candidates": result["coverage_text"] is None
            if result["total_count"] == 0
            else result["coverage_text"] is not None,
        }
        live_content = production.analyze(product)
        row["production_status"] = live_content.status.value
        row["production_checked_count"] = live_content.checked_count
        row["production"] = production_row(live_content)
        expected = expectations["cases"].get(record["barcode"])
        if expected:
            # Expected names are authored separately from engine output. A failure
            # is retained in this exploratory report, not rewritten into a pass.
            row["expectation"] = expected
            row["checks"] = {
                key: row[key] == value
                for key, value in expected.items()
                if key in {"candidates", "matched_ids", "total_count"}
            }
            if "warning_expected" in expected:
                row["checks"]["warning_present"] = (
                    bool(row["warnings"]) == expected["warning_expected"]
                )
        results.append(row)
    analyzed = [r for r in results if r.get("ingredients_text")]
    audited = [r for r in results if r.get("checks")]
    return {
        "sample_source": snapshot["sample_source"],
        "limitations": [
            "Exploratory OFF-text validation, not package-verified ingredient truth.",
            "Expected results are agent-authored and await teammate review.",
            "Synthetic matches and flags do not measure production coverage or health accuracy.",
            "Rows without expectations are exercised but not scored for parsing correctness.",
        ],
        "summary": {
            "sample_size": len(results),
            "found": sum(r["lookup_status"] == "found" for r in results),
            "with_ingredient_text": len(analyzed),
            "unavailable": sum(r.get("status") == "unavailable" for r in results),
            "with_warnings": sum(bool(r["warnings"]) for r in analyzed),
            "audited_rows": len(audited),
            "all_selected_checks_pass": sum(all(r["checks"].values()) for r in audited),
            "rows_with_check_failures": sum(not all(r["checks"].values()) for r in audited),
            "invariant_failures": sum(
                not all(r["invariants"].values()) for r in results if "invariants" in r
            ),
            "canonical_match_checks": sum("matched_ids" in r["checks"] for r in audited),
            "canonical_match_check_failures": sum(
                r["checks"].get("matched_ids") is False for r in audited
            ),
            "production_entry_count": len(production.knowledge.entries),
            "production": production_summary(results),
        },
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads((FIXTURES / "off_sample_issue28.json").read_text(encoding="utf-8"))
    expectations = json.loads(
        (FIXTURES / "off_sample_expectations.json").read_text(encoding="utf-8")
    )
    report = evaluate(snapshot, expectations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], indent=2))
    print(f"Exploratory report: {args.output}; selected checks are not an overall accuracy score.")
    return int(
        report["summary"]["rows_with_check_failures"] > 0
        or report["summary"]["invariant_failures"] > 0
        or report["summary"]["production"]["invariant_failures"] > 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
