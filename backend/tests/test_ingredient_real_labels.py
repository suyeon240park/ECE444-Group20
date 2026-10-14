"""Frozen real label inputs, with expectations authored without running the parser.

These regression cases use synthetic knowledge entries, not reviewed health advice.
Source transcription and counting decisions still need teammate sign-off.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.product import DataSource, Product, Source
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import IngredientKnowledgeBase, load_source_policy
from app.services.ingredient_parser import parse_ingredients

FIXTURES = Path(__file__).parent / "fixtures/ingredients"
CASES = json.loads((FIXTURES / "real_labels.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def knowledge():
    entries = json.loads((FIXTURES / "entries.json").read_text(encoding="utf-8"))
    return IngredientKnowledgeBase(((e["id"], e) for e in entries), load_source_policy())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_real_label_candidates_and_analysis(knowledge, case):
    text = case["ingredients_text"]
    if text is not None:
        parsed = parse_ingredients(text, knowledge)
        # Names as well as counts: dropping one and inventing another must fail.
        assert [c.lookup_text for c in parsed.candidates] == case["expected_candidates"]
        assert not any(c.force_unmatched for c in parsed.candidates)
        assert parsed.warnings == ()
    product = Product(
        source=DataSource(Source.OPEN_FOOD_FACTS, datetime(2000, 1, 1, tzinfo=timezone.utc)),
        ingredients_text=text,
    )
    result = IngredientAnalysisService(knowledge).analyze(product).to_dict()
    assert result["status"] == case["expected_status"]
    assert [m["ingredient"]["id"] for m in result["matched"]] == case["expected_matched_ids"]
    assert [u["text"] for u in result["unmatched"]] == case["expected_unmatched"]
    assert result["checked_count"] == len(case["expected_matched_ids"])
    assert result["total_count"] == case["expected_total"]
    assert result["warnings"] == []
    assert result["coverage_text"] == (
        f"Checked {len(case['expected_matched_ids'])} of {case['expected_total']} ingredients "
        "against our reviewed ingredient database."
        if text is not None
        else None
    )


def test_frozen_missing_input_matches_original_off_record():
    source = json.loads(
        (FIXTURES.parent / "off/kraft_no_ingredients.json").read_text(encoding="utf-8")
    )
    assert not source["product"].get("ingredients_text")
    case = next(case for case in CASES if case["id"] == "off_missing_ingredients")
    assert case["ingredients_text"] is None
