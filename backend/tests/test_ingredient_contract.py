"""Executable handoff examples and OpenAPI validation for #40/#43."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from app.models.ingredients import Authority, FlagCategory, IngredientStatus
from app.models.product import DataSource, Product, Source
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import IngredientKnowledgeBase, load_source_policy

ROOT = Path(__file__).resolve().parents[2]
SPEC = yaml.safe_load((ROOT / "docs/api/openapi.yaml").read_text(encoding="utf-8"))
EXAMPLES = json.loads((ROOT / "docs/api/ingredient-examples.json").read_text(encoding="utf-8"))
ENTRIES = json.loads(
    (Path(__file__).parent / "fixtures/ingredients/entries.json").read_text(encoding="utf-8")
)
SERVICE = IngredientAnalysisService(
    IngredientKnowledgeBase(((e["id"], e) for e in ENTRIES), load_source_policy())
)


def validator(name):
    schema = {"$ref": f"#/components/schemas/{name}", "components": SPEC["components"]}
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize("name", EXAMPLES)
def test_documented_example_is_exact_service_output(name):
    example = EXAMPLES[name]
    product = Product(
        source=DataSource(Source.OPEN_FOOD_FACTS, datetime(2000, 1, 1, tzinfo=timezone.utc)),
        ingredients_text=example["ingredients_text"],
    )
    assert SERVICE.analyze(product).to_dict() == example["result"]
    validator("IngredientAnalysisResult").validate(example["result"])


def test_entry_documents_satisfy_openapi_schema():
    check = validator("IngredientContentDocument")
    for entry in ENTRIES:
        check.validate({"schema_version": 1, "ingredient": entry})


def test_schema_enums_and_multiple_flag_handoff():
    for name, enum in (
        ("IngredientStatus", IngredientStatus),
        ("IngredientAuthority", Authority),
        ("IngredientFlagCategory", FlagCategory),
    ):
        assert SPEC["components"]["schemas"][name]["enum"] == [e.value for e in enum]
    result = EXAMPLES["multiple_flags"]["result"]
    assert result["flagged_count"] == 4
    assert len(result["flagged_ids"]) == 4  # #40, not the service, collapses the list.


def test_returned_json_cannot_mutate_shared_reviewed_content():
    product = Product(
        source=DataSource(Source.OPEN_FOOD_FACTS, datetime(2000, 1, 1, tzinfo=timezone.utc)),
        ingredients_text="Sugar",
    )
    first = SERVICE.analyze(product).to_dict()
    first["matched"][0]["ingredient"]["aliases"].append("another food")
    assert (
        "another food"
        not in SERVICE.analyze(product).to_dict()["matched"][0]["ingredient"]["aliases"]
    )
