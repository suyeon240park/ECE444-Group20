"""Independent identity expectations for #34 and #35 sourced production content.

These tests establish matching behavior, not scientific or teammate approval.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.product import DataSource, Product, Source
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import load_ingredient_knowledge
from app.services.normalize import normalize_off_product
from scripts.ingredient_production_report import production_row, production_summary

FIXTURES = Path(__file__).parent / "fixtures/ingredients"
IDENTITIES = [
    ("water", "Water", "eau"),
    ("salt", "Salt", "sel"),
    ("sugar", "Sugar", "sucre"),
    ("brown_sugar", "Brown sugar", "cassonade"),
    ("corn_syrup", "Corn syrup", "sirop de maïs"),
    ("glucose_fructose", "Glucose-fructose", "glucose-fructose"),
    ("vegetable_oil", "Vegetable oil", "huile végétale"),
    ("canola_oil", "Canola oil", "huile de canola"),
    ("sunflower_oil", "Sunflower oil", "huile de tournesol"),
    ("corn_oil", "Corn oil", "huile de maïs"),
    ("soybean_oil", "Soybean oil", "huile de soya"),
    ("coconut_oil", "Coconut oil", "huile de noix de coco"),
    ("wheat_flour", "Wheat flour", "farine de blé"),
    ("durum_wheat_semolina", "Durum wheat semolina", "semoule de blé dur"),
    ("whole_grain_oats", "Whole grain oats", "avoine à grains entiers"),
    ("corn_starch", "Corn starch", "amidon de maïs"),
    ("modified_corn_starch", "Modified corn starch", "amidon de maïs modifié"),
    ("soy_lecithin", "Soy lecithin", "lécithine de soja"),
    ("skim_milk", "Skim milk", "lait écrémé"),
    ("cream", "Cream", "crème"),
    ("potatoes", "Potatoes", "pommes de terre"),
    ("tomato_paste", "Tomato paste", "pâte de tomates"),
    ("onion_powder", "Onion powder", "poudre d'oignon"),
    ("garlic", "Garlic", "ail"),
    ("natural_flavour", "Natural flavour", "arôme naturel"),
]


@pytest.fixture(scope="module")
def service():
    return IngredientAnalysisService(load_ingredient_knowledge())


def analyze(service, text):
    return service.analyze(
        Product(
            source=DataSource(Source.OPEN_FOOD_FACTS, datetime(2000, 1, 1, tzinfo=timezone.utc)),
            ingredients_text=text,
        )
    )


@pytest.mark.parametrize(("expected_id", "english", "french"), IDENTITIES)
def test_production_english_french_identity_and_deduplication(
    service, expected_id, english, french
):
    assert service.knowledge.match(english).id == expected_id
    assert service.knowledge.match(french).id == expected_id
    result = analyze(service, f"Ingredients: {english}. Ingrédients : {french}.")
    assert [m.ingredient.id for m in result.matched] == [expected_id]
    assert result.checked_count == result.total_count == 1
    assert not result.unmatched


@pytest.mark.parametrize(
    ("text", "forbidden_id"),
    [
        ("starch", "corn_starch"),
        ("amidon", "corn_starch"),
        ("modified starch", "modified_corn_starch"),
        ("modified food starch", "modified_corn_starch"),
        ("corn starch", "modified_corn_starch"),
        ("modified corn starch", "corn_starch"),
        ("milk", "skim_milk"),
        ("skim milk powder", "skim_milk"),
        ("cream", "skim_milk"),
        ("skim milk", "cream"),
        ("lecithin", "soy_lecithin"),
        ("E322", "soy_lecithin"),
        ("INS 322", "soy_lecithin"),
        ("sunflower lecithin", "soy_lecithin"),
        ("brown sugar", "sugar"),
        ("golden syrup", "brown_sugar"),
        ("corn syrup", "glucose_fructose"),
        ("glucose-fructose", "corn_syrup"),
        ("high fructose corn syrup", "glucose_fructose"),
        ("sugars", "sugar"),
        ("sucres", "sugar"),
        ("flavour", "natural_flavour"),
        ("artificial flavour", "natural_flavour"),
        ("natural and artificial flavour", "natural_flavour"),
        ("hydrogenated canola oil", "canola_oil"),
        ("high oleic sunflower oil", "sunflower_oil"),
        ("whole wheat flour", "wheat_flour"),
        ("enriched wheat flour", "wheat_flour"),
        ("semolina", "durum_wheat_semolina"),
        ("oat bran", "whole_grain_oats"),
        ("potato starch", "potatoes"),
        ("tomato puree", "tomato_paste"),
        ("garlic powder", "garlic"),
        ("onion salt", "onion_powder"),
    ],
)
def test_source_processing_and_grade_are_not_conflated(service, text, forbidden_id):
    match = service.knowledge.match(text)
    assert match is None or match.id != forbidden_id
    # Also guard parser shortcuts, not just the direct alias index.
    assert forbidden_id not in {m.ingredient.id for m in analyze(service, text).matched}


def test_mixed_list_preserves_unknown_and_four_sweetener_identities(service):
    result = analyze(
        service,
        "Sugars (sugar, brown sugar, corn syrup, glucose-fructose), "
        "unreviewed example ingredient, sucre, sirop de maïs",
    )
    assert {m.ingredient.id for m in result.matched} == {
        "sugar",
        "brown_sugar",
        "corn_syrup",
        "glucose_fructose",
    }
    assert result.checked_count == 4
    assert result.total_count == 5
    assert [u.text for u in result.unmatched] == ["unreviewed example ingredient"]


def test_canadian_golden_sugar_name_does_not_mean_golden_syrup(service):
    assert service.knowledge.match("golden sugar").id == "brown_sugar"


def test_real_bilingual_lays_with_production_content(service):
    snapshot = json.loads((FIXTURES / "off_sample_issue28.json").read_text(encoding="utf-8"))
    record = next(r for r in snapshot["records"] if r["barcode"] == "060410047019")
    product = normalize_off_product(
        record["response"]["product"],
        record["barcode"],
        datetime.fromisoformat(record["retrieved_at"]),
    )
    assert "SPECIALLY SELECTED POTATOES" in product.ingredients_text
    assert "POMMES DE TERRE SPÉCIALEMENT SÉLECTIONNÉES" in product.ingredients_text
    result = service.analyze(product)
    assert [m.ingredient.id for m in result.matched] == ["potatoes", "vegetable_oil", "salt"]
    assert result.checked_count == result.total_count == 3
    assert not result.unmatched
    assert not result.warnings


def test_production_report_retains_coverage_unknowns_and_counts_products_once(service):
    observed = production_row(analyze(service, "Sugar, sucre, unreviewed example ingredient"))
    missing = production_row(analyze(service, None))
    assert observed["matched_ids"] == ["sugar"]
    assert observed["unmatched"] == ["unreviewed example ingredient"]
    assert observed["checked_count"] == 1
    assert observed["total_count"] == 2
    assert observed["coverage_text"].startswith("Checked 1 of 2")
    assert missing["coverage_text"] is None
    summary = production_summary([{"production": observed}, {"production": missing}, {}])
    assert summary["distinct_product_frequency"] == {"sugar": 1}
    assert summary["analyzed_products"] == 2
    assert summary["unavailable_products"] == 1
    assert summary["products_with_matches"] == 1
    assert summary["checked_count_sum"] == 1
    assert summary["total_count_sum"] == 2
    assert summary["invariant_failures"] == 0
    assert production_summary([])["distinct_product_frequency"] == {}


def test_report_separates_malformed_text_from_missing_data(service):
    row = production_row(analyze(service, "Salt, mystery blend ("))
    summary = production_summary([{"production": row}])
    assert summary["unavailable_products"] == 0
    assert summary["products_with_warnings"] == 1
    assert summary["products_by_warning_code"]["unbalanced_brackets"] == 1


# ---------------------------------------------------------------------------
# Issue #35 — flagged additive entries
# ---------------------------------------------------------------------------

ADDITIVE_IDENTITIES = [
    ("titanium_dioxide", "Titanium dioxide", "E171"),
    ("aspartame", "Aspartame", "E951"),
    ("erythrosine", "Erythrosine", "E127"),
    ("allura_red", "Allura Red AC", "E129"),
    ("tartrazine", "Tartrazine", "E102"),
    ("sunset_yellow", "Sunset Yellow FCF", "E110"),
    ("brilliant_blue", "Brilliant Blue FCF", "E133"),
    ("caramel_colour", "Caramel colour", "E150a"),
    ("annatto", "Annatto", "E160b"),
    ("anthocyanins", "Anthocyanins", "E163"),
    ("tocopherols", "Tocopherols", "E306"),
    ("monoglycerides", "Monoglycerides", "E471"),
    ("carrageenan", "Carrageenan", "E407"),
    ("calcium_carbonate", "Calcium carbonate", "E170"),
    ("trisodium_phosphate", "Trisodium phosphate", "E339"),
    ("gelatin", "Gelatin", None),
    ("malic_acid", "Malic acid", "E296"),
    ("sodium_citrate", "Sodium citrate", "E331"),
    ("locust_bean_gum", "Locust bean gum", "E410"),
    ("sodium_benzoate", "Sodium benzoate", "E211"),
    ("potassium_sorbate", "Potassium sorbate", "E202"),
    ("xanthan_gum", "Xanthan gum", "E415"),
    ("sucralose", "Sucralose", "E955"),
    ("acesulfame_potassium", "Acesulfame potassium", "E950"),
    ("sodium_nitrite", "Sodium nitrite", "E250"),
]


@pytest.mark.parametrize(("expected_id", "name", "e_number"), ADDITIVE_IDENTITIES)
def test_additive_name_and_e_number_resolution(service, expected_id, name, e_number):
    assert service.knowledge.match(name).id == expected_id
    if e_number:
        assert service.knowledge.match(e_number).id == expected_id


FLAGGED_ADDITIVES = [
    ("titanium_dioxide", "conflicting_assessments"),
    ("aspartame", "conflicting_assessments"),
    ("erythrosine", "authority_action"),
    ("allura_red", "authority_action"),
    ("tartrazine", "authority_action"),
    ("sunset_yellow", "authority_action"),
    ("brilliant_blue", "authority_action"),
]


@pytest.mark.parametrize(("entry_id", "expected_category"), FLAGGED_ADDITIVES)
def test_flagged_additive_has_correct_category(service, entry_id, expected_category):
    entry = service.knowledge.entries[entry_id]
    assert entry.flagged
    assert entry.flag.category == expected_category
    assert entry.flag.flag_reason


UNFLAGGED_ADDITIVES = [
    "caramel_colour",
    "annatto",
    "anthocyanins",
    "tocopherols",
    "monoglycerides",
    "carrageenan",
    "calcium_carbonate",
    "trisodium_phosphate",
    "gelatin",
    "malic_acid",
    "sodium_citrate",
    "locust_bean_gum",
    "sodium_benzoate",
    "potassium_sorbate",
    "xanthan_gum",
    "sucralose",
    "acesulfame_potassium",
    "sodium_nitrite",
]


@pytest.mark.parametrize("entry_id", UNFLAGGED_ADDITIVES)
def test_unflagged_additive_is_not_flagged(service, entry_id):
    entry = service.knowledge.entries[entry_id]
    assert not entry.flagged


def test_total_entry_count(service):
    assert len(service.knowledge.entries) == 50


def test_flagged_ids_in_analysis_result(service):
    result = analyze(service, "Ingredients: Aspartame, sugar, titanium dioxide, salt")
    assert set(result.flagged_ids) == {"aspartame", "titanium_dioxide"}
    assert result.to_dict()["flagged_count"] == 2


def test_e_number_does_not_conflate_additives(service):
    assert service.knowledge.match("E171").id == "titanium_dioxide"
    assert service.knowledge.match("E951").id == "aspartame"
    assert service.knowledge.match("E129").id == "allura_red"
    assert service.knowledge.match("E407").id == "carrageenan"
