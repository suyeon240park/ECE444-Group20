"""Production-content observations, separate from synthetic parser assertions."""

from collections import Counter


def production_row(result):
    value = result.to_dict()
    return {
        "status": value["status"],
        "matched_ids": [m["ingredient"]["id"] for m in value["matched"]],
        "unmatched": [u["text"] for u in value["unmatched"]],
        "checked_count": value["checked_count"],
        "total_count": value["total_count"],
        "coverage_text": value["coverage_text"],
        "warnings": value["warnings"],
    }


def production_summary(rows):
    observations = [row["production"] for row in rows if "production" in row]
    # Each ID counts once per product, including repeated/bilingual declarations.
    frequency = Counter(
        ingredient_id for row in observations for ingredient_id in set(row["matched_ids"])
    )
    return {
        "analyzed_products": len(observations),
        "products_with_matches": sum(row["checked_count"] > 0 for row in observations),
        "unavailable_products": sum(row["status"] == "unavailable" for row in observations),
        "products_with_warnings": sum(bool(row["warnings"]) for row in observations),
        "products_by_warning_code": dict(
            sorted(
                Counter(
                    code
                    for row in observations
                    for code in {warning["code"] for warning in row["warnings"]}
                ).items()
            )
        ),
        "checked_count_sum": sum(row["checked_count"] for row in observations),
        "total_count_sum": sum(row["total_count"] for row in observations),
        "distinct_product_frequency": dict(sorted(frequency.items())),
        "invariant_failures": sum(
            row["checked_count"] != len(set(row["matched_ids"]))
            or row["total_count"] != row["checked_count"] + len(row["unmatched"])
            or (row["coverage_text"] is not None) != (row["total_count"] > 0)
            for row in observations
        ),
    }
