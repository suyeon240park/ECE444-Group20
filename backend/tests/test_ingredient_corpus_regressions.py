"""Confirmed structural failures from frozen OFF labels, enforced by normal CI.

These assertions check parsing and synthetic identity, not food guidance.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.product import DataSource, Product, Source
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import IngredientKnowledgeBase, load_source_policy
from app.services.ingredient_names import normalize_name
from app.services.ingredient_parser import parse_ingredients
from app.services.normalize import normalize_off_product

FIXTURES = Path(__file__).parent / "fixtures/ingredients"
AUDITS = json.loads((FIXTURES / "off_canada_500_audit.json").read_text(encoding="utf-8"))["cases"]
RECORDS = {
    r["product"]["code"]: r["product"]
    for r in json.loads((FIXTURES / "off_canada_500.json").read_text(encoding="utf-8"))["records"]
}


@pytest.fixture(scope="module")
def knowledge():
    entries = json.loads((FIXTURES / "entries.json").read_text(encoding="utf-8"))
    return IngredientKnowledgeBase(((e["id"], e) for e in entries), load_source_policy())


@pytest.mark.parametrize("audit", AUDITS, ids=lambda a: a["barcode"])
def test_confirmed_real_label_assertions(knowledge, audit):
    raw = RECORDS[audit["barcode"]]
    product = normalize_off_product(
        raw, audit["barcode"], datetime(2000, 1, 1, tzinfo=timezone.utc)
    )
    candidates = {
        normalize_name(c.lookup_text)
        for c in parse_ingredients(product.ingredients_text, knowledge).candidates
    }
    assert {normalize_name(c) for c in audit.get("required_candidates", [])} <= candidates
    assert not {normalize_name(c) for c in audit.get("forbidden_candidates", [])} & candidates
    result = IngredientAnalysisService(knowledge).analyze(product)
    assert set(audit.get("required_matched_ids", [])) <= {m.ingredient.id for m in result.matched}
    if "expected_total" in audit:
        assert result.total_count == audit["expected_total"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sugar, gluten-free oats, salt", ["Sugar", "gluten-free oats", "salt"]),
        (
            "Oat base (water, gluten free oat flour), salt",
            ["Oat base", "water", "gluten free oat flour", "salt"],
        ),
        ("Sugar, GLUTEN-FREE, salt. SANS GLUTEN.", ["Sugar", "salt"]),
        ("Sugar, contains less than 2% of salt, soy lecithin", ["Sugar", "salt", "soy lecithin"]),
        (
            "Sugar. Contains 2% or less of: salt, soy lecithin. Contains: milk, soy.",
            ["Sugar", "salt", "soy lecithin"],
        ),
        ("Chocolate (contains 2% or less of salt, milk)", ["Chocolate", "salt", "milk"]),
        ("Sugar, contains less than 0.5% of salt", ["Sugar", "salt"]),
        (
            "Vegetable oil (canola, and/or soybean oil)",
            ["Vegetable oil", "canola oil", "soybean oil"],
        ),
        ("Sugar, and/or salt", ["Sugar", "salt"]),
        ("Sucre, et/ou sel", ["Sucre", "sel"]),
        ("Salt, Oregano. Contains: milk, soy, peanuts.", ["Salt", "Oregano"]),
        ("Sugar. Made with milk., Salt, soy lecithin", ["Sugar", "Salt", "soy lecithin"]),
        ("FD&C Red No. 3, salt", ["FD&C Red No. 3", "salt"]),
        ("Vit. C, salt", ["Vit. C", "salt"]),
    ],
)
def test_ingredient_and_advisory_boundaries(knowledge, text, expected):
    parsed = parse_ingredients(text, knowledge)
    assert [c.lookup_text for c in parsed.candidates] == expected
    assert not parsed.warnings


def test_original_variety_pack_keeps_later_flavours(knowledge):
    snapshot = json.loads((FIXTURES / "off_sample_issue28.json").read_text(encoding="utf-8"))
    raw = next(r for r in snapshot["records"] if r["barcode"] == "629025410009")
    product = normalize_off_product(
        raw["response"]["product"], raw["barcode"], datetime.fromisoformat(raw["retrieved_at"])
    )
    result = IngredientAnalysisService(knowledge).analyze(product)
    names = {
        normalize_name(c.lookup_text)
        for c in parse_ingredients(product.ingredients_text, knowledge).candidates
    }
    assert {"raspberries", "strawberries", "anthocyanins", "paprika", "locust bean gum"} <= names
    assert result.total_count == 18


def test_appended_advisory_does_not_change_real_marinara(knowledge):
    raw = RECORDS["0747479005470"]
    text = raw.get("ingredients_text_en") or raw["ingredients_text"]
    service = IngredientAnalysisService(knowledge)

    def analyze(value):
        return service.analyze(
            Product(
                source=DataSource(
                    Source.OPEN_FOOD_FACTS, datetime(2000, 1, 1, tzinfo=timezone.utc)
                ),
                ingredients_text=value,
            )
        ).to_dict()

    original = analyze(text)
    appended = analyze(text + ". Contains: milk, soy, peanuts.")
    # Sentence grouping changes occurrence paths, but not names or coverage.
    assert appended["total_count"] == original["total_count"] == 8
    assert [m["ingredient"]["id"] for m in appended["matched"]] == [
        m["ingredient"]["id"] for m in original["matched"]
    ]
    assert [u["text"] for u in appended["unmatched"]] == [u["text"] for u in original["unmatched"]]
    assert appended["warnings"] == original["warnings"] == []
