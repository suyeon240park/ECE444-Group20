"""Offline real-data validation: behavioral properties and a limited reference parser.

This measures specified behaviors, not overall ingredient or health accuracy.
OFF's computed ingredient tree is retained for review, never treated as truth.
"""

import argparse
import json
import re
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import (
    IngredientKnowledgeBase,
    load_ingredient_knowledge,
    load_source_policy,
)
from app.services.ingredient_names import normalize_name
from app.services.ingredient_parser import MAX_TEXT_LENGTH, parse_ingredients
from app.services.normalize import normalize_off_product
from scripts.ingredient_production_report import production_row, production_summary

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/ingredients"


def signature(result):
    return {
        "status": result["status"],
        "matched_ids": sorted(m["ingredient"]["id"] for m in result["matched"]),
        "unmatched": sorted(normalize_name(u["text"]) for u in result["unmatched"]),
        "total_count": result["total_count"],
        "flagged_ids": sorted(result["flagged_ids"]),
    }


def balanced(text):
    stack = []
    for char in text:
        if char in "([":
            stack.append(char)
        elif char in ")]":
            if not stack or stack.pop() != {"\u0029": "(", "]": "["}[char]:
                return False
    return not stack


def flat_reference(text, knowledge):
    """Independent comma-only segmentation for an explicitly limited grammar.

    No production splitting helper is used. Identity lookup still uses the fixed
    synthetic KB; this check isolates segmentation, not content correctness.
    """
    value = re.sub(r"^\s*ingr[eé]dients\s*:\s*", "", text, flags=re.I).strip().rstrip(".")
    if not value or any(c in value for c in "()[];:\n\r/•.%"):
        return None
    if re.search(
        r"\d,\d|\b(?:and|or|et|ou|contains|contient|may|peut|made|fait|sans|free)\b", value, re.I
    ):
        return None
    terms = [term.strip() for term in value.split(",")]
    if not all(terms) or any(not normalize_name(term) for term in terms):
        return None
    matched, unknown = set(), set()
    for term in terms:
        entry = knowledge.match(term)
        if entry:
            matched.add(entry.id)
        else:
            unknown.add(normalize_name(term))
    return {
        "candidate_names": [normalize_name(term) for term in terms],
        "matched_ids": sorted(matched),
        "unmatched": sorted(unknown),
        "total_count": len(matched) + len(unknown),
    }


def tree_texts(nodes):
    for node in nodes:
        if isinstance(node, dict):
            if node.get("text"):
                yield node["text"]
            yield from tree_texts(node.get("ingredients", []))


def audit_checks(row, audit):
    """Selected source-text assertions, not full ground truth for a product."""
    candidates = {normalize_name(c) for c in row["candidates"]}
    required = {normalize_name(c) for c in audit.get("required_candidates", [])}
    forbidden = {normalize_name(c) for c in audit.get("forbidden_candidates", [])}
    missing_ids = set(audit.get("required_matched_ids", [])) - set(row["result"]["matched_ids"])
    failures = {
        "missing_candidates": sorted(required - candidates),
        "forbidden_candidates": sorted(forbidden & candidates),
        "missing_matched_ids": sorted(missing_ids),
    }
    if "expected_total" in audit and row["result"]["total_count"] != audit["expected_total"]:
        failures["total_count"] = {
            "expected": audit["expected_total"],
            "actual": row["result"]["total_count"],
        }
    return {
        "category": audit["category"],
        "passed": not any(failures.values()),
        "failures": failures,
    }


def evaluate(snapshot, audits):
    entries = json.loads((FIXTURES / "entries.json").read_text(encoding="utf-8"))
    knowledge = IngredientKnowledgeBase(((e["id"], e) for e in entries), load_source_policy())
    service = IngredientAnalysisService(knowledge)
    production = IngredientAnalysisService(load_ingredient_knowledge())
    results, latencies = [], []
    for record in snapshot["records"]:
        raw = record["product"]
        row = {"barcode": raw["code"], "name": raw.get("product_name"), "language": raw.get("lang")}
        try:
            product = normalize_off_product(
                raw, raw["code"], datetime.fromisoformat(record["retrieved_at"])
            )
            text = product.ingredients_text
            row["ingredients_text"] = text
            start = time.perf_counter()
            result = service.analyze(product).to_dict()
            latencies.append((time.perf_counter() - start) * 1000)
            original = signature(result)
            row["result"] = original
            row["warnings"] = result["warnings"]
            candidates = parse_ingredients(text, knowledge).candidates
            row["candidates"] = [c.lookup_text for c in candidates]
            if raw["code"] in audits:
                row["targeted_audit"] = audit_checks(row, audits[raw["code"]])
            row["off_computed_ingredient_texts"] = list(tree_texts(raw.get("ingredients", [])))
            live_content = production.analyze(product)
            row["production_checked_count"] = live_content.checked_count
            row["production"] = production_row(live_content)
            row["invariants"] = {
                "count_consistency": result["total_count"]
                == len(result["matched"]) + len(result["unmatched"]),
                "flag_references": set(result["flagged_ids"]) <= set(original["matched_ids"]),
                "unique_matches": len(original["matched_ids"]) == len(set(original["matched_ids"])),
                "coverage_presence": (result["coverage_text"] is not None)
                == (result["total_count"] > 0),
            }
            variants = {"uppercase": text.upper(), "outer_whitespace": f" \t{text}\t "}
            if len(text) * 2 + 16 <= MAX_TEXT_LENGTH:
                variants["repeat_list"] = text + "\nIngredients: " + text
            if balanced(text) and len(text) + 55 <= MAX_TEXT_LENGTH:
                variants["append_allergen_advisory"] = (
                    text.rstrip().rstrip(".") + ". Contains: milk, soy, peanuts."
                )
            row["properties"] = {}
            row["property_failures"] = {}
            for name, variant in variants.items():
                modified = normalize_off_product(
                    {"ingredients_text_en": variant}, raw["code"], product.source.retrieved_at
                )
                observed = signature(service.analyze(modified).to_dict())
                row["properties"][name] = observed == original
                if observed != original:
                    row["property_failures"][name] = {"input": variant, "observed": observed}
            expected = flat_reference(text, knowledge)
            if expected is not None:
                observed = {
                    "candidate_names": [normalize_name(c) for c in row["candidates"]],
                    **{k: original[k] for k in ("matched_ids", "unmatched", "total_count")},
                }
                row["flat_reference"] = {"passed": observed == expected, "expected": expected}
            # Triage signals only. Review the original input before calling a
            # signal a defect; these are not automatic accuracy judgments.
            row["review_signals"] = []
            if any(
                normalize_name(c.lookup_text) in {"and", "or", "et", "ou", "from", "de"}
                for c in candidates
            ):
                row["review_signals"].append("standalone_connector")
            if re.search(r"\((?:vitamin[e]?\s+[abdke]\d*|fer)\)", text, re.I):
                row["review_signals"].append("nutrient_parenthesis")
            if re.search(
                r"\b(?:refrigerate|refrigerated|distributed by|prepared for|"
                r"best before|favourite|www\.)",
                text,
                re.I,
            ):
                row["review_signals"].append("possible_packaging_prose")
            if len(row["off_computed_ingredient_texts"]) > max(3, len(candidates) * 2):
                row["review_signals"].append("off_tree_much_larger")
        except Exception as exc:
            row["exception"] = f"{type(exc).__name__}: {exc}"
        results.append(row)
    properties = {}
    for name in ("uppercase", "outer_whitespace", "repeat_list", "append_allergen_advisory"):
        checked = [r["properties"][name] for r in results if name in r.get("properties", {})]
        properties[name] = {"checked": len(checked), "failed": checked.count(False)}
    references = [r["flat_reference"] for r in results if "flat_reference" in r]
    reviewed = [r["targeted_audit"] for r in results if "targeted_audit" in r]
    return {
        "method": (
            "Frozen Canada-tagged real OFF inputs; fixed synthetic KB. Property checks "
            "and restricted independent comma-only reference. No human-verified "
            "accuracy estimate or health assessment."
        ),
        "summary": {
            "products": len(results),
            "distinct_barcodes": len({r["barcode"] for r in results}),
            "nonblank_ingredient_lists": sum(bool(r.get("ingredients_text")) for r in results),
            "exceptions": sum("exception" in r for r in results),
            "invariant_failures": sum(
                not all(r["invariants"].values()) for r in results if "invariants" in r
            ),
            "properties": properties,
            "products_with_property_failure": sum(
                bool(r.get("property_failures")) for r in results
            ),
            "flat_reference": {
                "checked": len(references),
                "failed": sum(not r["passed"] for r in references),
            },
            "targeted_audits": {
                "expected": len(audits),
                "checked": len(reviewed),
                "failed": sum(not r["passed"] for r in reviewed),
                "failed_by_category": dict(
                    Counter(r["category"] for r in reviewed if not r["passed"])
                ),
            },
            "products_with_warnings": sum(bool(r.get("warnings")) for r in results),
            "review_signals": dict(
                Counter(s for r in results for s in r.get("review_signals", []))
            ),
            "source_languages": dict(Counter(r["language"] for r in results)),
            "production_entries": len(production.knowledge.entries),
            "production": production_summary(results),
            "analysis_ms_median": round(statistics.median(latencies), 3) if latencies else None,
            "analysis_ms_max": round(max(latencies), 3) if latencies else None,
        },
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=FIXTURES / "off_canada_500.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audits", type=Path, default=FIXTURES / "off_canada_500_audit.json")
    args = parser.parse_args()
    snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    audit_data = json.loads(args.audits.read_text(encoding="utf-8"))
    audits = {case["barcode"]: case for case in audit_data["cases"]}
    if len(audits) != len(audit_data["cases"]):
        raise ValueError("Duplicate audit barcodes")
    report = evaluate(snapshot, audits)
    report["audit_method"] = audit_data["method"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], indent=2))
    summary = report["summary"]
    return int(
        bool(
            summary["exceptions"]
            or summary["invariant_failures"]
            or summary["production"]["invariant_failures"]
            or summary["products_with_property_failure"]
            or summary["flat_reference"]["failed"]
            or summary["targeted_audits"]["failed"]
            or summary["targeted_audits"]["checked"] != summary["targeted_audits"]["expected"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
