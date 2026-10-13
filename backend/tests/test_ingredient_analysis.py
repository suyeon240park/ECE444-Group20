"""F4 behavior using synthetic content; no authority or OFF requests."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.product import DataSource, Product, Source
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import IngredientKnowledgeBase, load_source_policy
from app.services.ingredient_names import normalize_name
from app.services.ingredient_parser import MAX_DEPTH, MAX_TEXT_LENGTH, parse_ingredients

FIXTURES = Path(__file__).parent / "fixtures" / "ingredients"


@pytest.fixture
def knowledge():
    entries = json.loads((FIXTURES / "entries.json").read_text(encoding="utf-8"))
    return IngredientKnowledgeBase(((e["id"], e) for e in entries), load_source_policy())


def product(text, source=Source.OPEN_FOOD_FACTS):
    return Product(
        source=DataSource(source, datetime(2000, 1, 1, tzinfo=timezone.utc)), ingredients_text=text
    )


def analyze(knowledge, text):
    return IngredientAnalysisService(knowledge).analyze(product(text)).to_dict()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  ,SUGAR; ", "sugar"),
        ("E 171", "e171"),
        ("e-171", "e171"),
        ("INS 171", "ins171"),
        ("E150(i)", "e150(i)"),
        ("Émulsifiant", "émulsifiant"),
        ("lécithine   de soja", "lécithine de soja"),
        ("", ""),
    ],
)
def test_normalization(text, expected):
    assert normalize_name(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sugar, SUCRE, sugar, salt, SEL", ["sugar", "salt"]),
        ("Titanium dioxide, E 171, INS 171, TiO2", ["titanium_dioxide"]),
        ("ascorbic acid (vitamin C), E300", ["ascorbic_acid"]),
        ("Sugars [sugar, corn syrup]; salt", ["sugar", "corn_syrup", "salt"]),
        ("colour (titanium dioxide)", ["titanium_dioxide"]),
        ("chocolate (sugar, milk), salt", ["chocolate", "sugar", "milk", "salt"]),
        ("Mono- and diglycerides, salt", ["mono_diglycerides", "salt"]),
        ("lecithin (soy)", ["soy_lecithin"]),
        ("Sugar 10%, salt (2%)", ["sugar", "salt"]),
        ("Sugar and/or salt", ["sugar", "salt"]),
        ("Sugar/sucre", ["sugar"]),
        ("Salt (for freshness)", ["salt"]),
        ("1,3-Butylene glycol, salt", ["chemical_locant", "salt"]),
        ("FD&C Red No. 3, salt", ["erythrosine", "salt"]),
        ("E150(i), salt", ["caramel_i", "salt"]),
        ("Ingredients: Sugar, salt. Ingrédients: Sucre, sel.", ["sugar", "salt"]),
        ("Sugar, salt. GLUTEN-FREE. Ingrédients : sucre, sel. SANS GLUTEN.", ["sugar", "salt"]),
        ("Ingredients Semoule, sel", ["salt"]),
        ("Grape juice (contains sulphites), sugar", ["grape_juice", "sulphites", "sugar"]),
        ("Sugar. Contains: Milk. Salt. May contain soy.", ["sugar", "salt"]),
        ("Ingredients: sugar. Contains: milk. Ingredients: salt.", ["sugar", "salt"]),
        ("Chocolate (sugar) and salt", ["chocolate", "sugar", "salt"]),
    ],
)
def test_supported_structures(knowledge, text, expected):
    result = analyze(knowledge, text)
    assert [m["ingredient"]["id"] for m in result["matched"]] == expected


def test_story_example(knowledge):
    result = analyze(
        knowledge,
        "Sugar, corn syrup, modified corn starch, colour (titanium dioxide), carnauba wax",
    )
    assert (result["checked_count"], result["total_count"], result["flagged_count"]) == (4, 5, 1)
    assert result["flagged_ids"] == ["titanium_dioxide"]
    assert result["unmatched"][0]["text"] == "carnauba wax"
    assert result["coverage_text"] == (
        "Checked 4 of 5 ingredients against our reviewed ingredient database."
    )
    assert len(result["matched"][3]["ingredient"]["authority_positions"]) == 2


def test_oil_context_does_not_match_corn_kernels(knowledge):
    result = analyze(knowledge, "Vegetable oil (corn, canola and/or soybean), corn")
    assert [m["ingredient"]["id"] for m in result["matched"]] == [
        "vegetable_oil",
        "corn_oil",
        "canola_oil",
        "soybean_oil",
        "corn",
    ]
    assert result["matched"][1]["occurrences"][0]["text"] == "corn"
    assert analyze(knowledge, "Vegetable oil (milk)")["unmatched"][0]["text"] == "milk"


@pytest.mark.parametrize(
    "text",
    [
        "sodium",
        "sodium benzoate derivative",
        "modified starch",
        "sodium metabisulphite",
        "caramel colour",
        "lecithin",
        "E150(ii)",
        "171",
        "2% milk",
        "lecithine de soja",
    ],
)
def test_no_inferred_identity(knowledge, text):
    result = analyze(knowledge, text)
    assert result["checked_count"] == 0
    assert result["status"] == "no_matches"
    assert result["message"] == "No verified ingredient analysis available."


def test_unknown_dedup_is_only_normalized_text(knowledge):
    result = analyze(knowledge, "Water, WATER, eau, sugar, sucre")
    assert result["checked_count"] == 1
    assert result["total_count"] == 3
    assert len(result["unmatched"][0]["occurrences"]) == 2
    assert len(result["matched"][0]["occurrences"]) == 2
    assert result["message"] == "No flagged ingredients found among the ingredients checked."


@pytest.mark.parametrize(
    "text", ["Salt (sugar", "Salt [sugar)", "Salt ) sugar", "Salt (sugar) stuff"]
)
def test_malformed_span_not_repaired(knowledge, text):
    result = analyze(knowledge, text)
    assert result["checked_count"] == 0
    assert result["total_count"] == 1
    assert result["warnings"]
    assert result["unmatched"][0]["text"] == text


def test_malformed_language_does_not_hide_next_heading(knowledge):
    result = analyze(knowledge, "Ingredients: salt (sugar Ingrédients: sel, sucre.")
    assert result["checked_count"] == 2
    assert result["warnings"][0]["code"] == "unbalanced_brackets"


def test_provenance_and_absence(knowledge):
    service = IngredientAnalysisService(knowledge)
    for p in (product(None), product("Sugar", Source.NUTRITION_LABEL_PHOTO)):
        result = service.analyze(p).to_dict()
        assert result["status"] == "unavailable"
        assert result["message"] == "Ingredient information not available"
        assert result["checked_count"] == result["total_count"] == 0
        assert result["matched"] == result["unmatched"] == result["warnings"] == []


def test_empty_collection_is_not_missing_list():
    result = analyze(IngredientKnowledgeBase([], load_source_policy()), "sugar, salt")
    assert result["status"] == "no_matches"
    assert result["total_count"] == 2


def test_limits_and_non_ingredient_text(knowledge):
    for text, code in (
        ("x" * (MAX_TEXT_LENGTH + 1), "text_limit"),
        ("(" * (MAX_DEPTH + 2) + "salt" + ")" * (MAX_DEPTH + 2), "nesting_limit"),
        ("Contains: Milk.", "no_ingredient_candidates"),
    ):
        parsed = parse_ingredients(text, knowledge)
        assert code in [w.code for w in parsed.warnings]
    result = analyze(knowledge, "Our delicious product Ingredients: salt")
    assert result["checked_count"] == 1
    assert result["warnings"][0]["code"] == "ignored_preamble"


def test_original_annotation_and_immutable_index(knowledge):
    result = analyze(knowledge, "Ascorbic acid (vitamin C)")
    assert result["matched"][0]["occurrences"][0]["text"] == "Ascorbic acid (vitamin C)"
    with pytest.raises(TypeError):
        knowledge.index["bogus"] = knowledge.entries["sugar"]


def test_bilingual_heading_without_full_stop_preserves_first_list(knowledge):
    result = analyze(knowledge, "Titanium dioxide, salt Ingrédients: sel, sucre")
    assert result["flagged_ids"] == ["titanium_dioxide"]
    assert result["checked_count"] == 3


@pytest.mark.parametrize("text", ["(salt", "salt)", "E150(i))", "[sugar)"])
def test_boundary_punctuation_cannot_hide_broken_brackets(knowledge, text):
    result = analyze(knowledge, text)
    assert result["checked_count"] == 0
    assert result["warnings"][0]["code"] == "unbalanced_brackets"


def test_conjunction_between_compounds_keeps_both_sets_of_children(knowledge):
    result = analyze(knowledge, "Chocolate (sugar) and grape juice (sulphites)")
    assert [m["ingredient"]["id"] for m in result["matched"]] == [
        "chocolate",
        "sugar",
        "grape_juice",
        "sulphites",
    ]


def test_annotations_cannot_erase_oil_context(knowledge):
    result = analyze(knowledge, "Vegetable oil (milk (for colour), corn (for freshness))")
    assert [m["ingredient"]["id"] for m in result["matched"]] == ["vegetable_oil", "corn_oil"]
    assert result["unmatched"][0]["text"] == "milk (for colour)"


@pytest.mark.parametrize("advisory", ["Contains", "Contains:", "May contain", "Contient :"])
def test_entire_allergen_advisory_is_excluded(knowledge, advisory):
    result = analyze(knowledge, f"Sugar. {advisory} milk, salt. Ingredients: corn syrup.")
    assert [m["ingredient"]["id"] for m in result["matched"]] == ["sugar", "corn_syrup"]


def test_embedded_declaration_is_not_an_allergen_advisory(knowledge):
    result = analyze(knowledge, "Grape juice (contains: sulphites, sugar)")
    assert [m["ingredient"]["id"] for m in result["matched"]] == [
        "grape_juice",
        "sulphites",
        "sugar",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Sugar\nContains: milk, salt",
        "Sugar, contains milk, salt",
        "Contains: milk, salt. Ingredients: Sugar",
    ],
)
def test_advisory_boundaries(knowledge, text):
    result = analyze(knowledge, text)
    assert [m["ingredient"]["id"] for m in result["matched"]] == ["sugar"]


def test_surrounding_punctuation_preserves_identifier_suffix(knowledge):
    result = analyze(knowledge, "[(E150(i))], E150(ii)")
    assert [m["ingredient"]["id"] for m in result["matched"]] == ["caramel_i"]
    assert result["total_count"] == 2
