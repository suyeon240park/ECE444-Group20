"""Keep docs/api/openapi.yaml and app/models/product.py in agreement.

Each documented example is rebuilt from the model and compared with ``to_dict()``,
so changing either side without the other fails CI.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from app.models.product import (
    ALL_NUTRIENTS,
    CANONICAL_UNITS,
    ApiError,
    Certainty,
    DataSource,
    ErrorCode,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    Package,
    Product,
    ProductResult,
    ResultType,
    Serving,
    Source,
)

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.yaml"
SPEC = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
SCHEMAS = SPEC["components"]["schemas"]
EXAMPLES = SPEC["components"]["examples"]

RETRIEVED_AT = datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc)
OFF = Source.OPEN_FOOD_FACTS
PHOTO = Source.NUTRITION_LABEL_PHOTO


def off(name, amount):
    return NutrientValue(amount, CANONICAL_UNITS[name], OFF, Certainty.REPORTED)


def photo(name, amount, dv=None, certainty=Certainty.CONFIDENT):
    return NutrientValue(amount, CANONICAL_UNITS[name], PHOTO, certainty, daily_value_percent=dv)


def product_complete():
    amounts = {
        "calories": 140,
        "total_fat": 5,
        "saturated_fat": 0.5,
        "sodium": 210,
        "carbohydrate": 21,
        "sugars": 1,
        "fibre": 3,
        "protein": 3,
        "trans_fat": 0,
    }
    return ProductResult(
        ResultType.PRODUCT,
        Product(
            barcode="0012345678905",
            name="Whole Wheat Crackers",
            brand="Example Foods",
            ingredients_text="Whole wheat flour, canola oil, sugar, salt, baking soda.",
            serving=Serving("6 crackers (30 g)", 30, "g", OFF),
            package=Package("300 g", 300, "g", None, OFF),
            nutrition=Nutrition(
                NutritionBasis.SERVING, {name: off(name, a) for name, a in amounts.items()}
            ),
            source=DataSource(
                OFF,
                RETRIEVED_AT,
                url="https://world.openfoodfacts.org/product/0012345678905",
                last_modified_at=datetime(2026, 3, 20, 9, 30, tzinfo=timezone.utc),
            ),
        ),
    )


def product_incomplete():
    amounts = {
        "calories": 539,
        "total_fat": 30.9,
        "saturated_fat": 10.6,
        "sodium": 43,
        "carbohydrate": 57.5,
        "sugars": 56.3,
        "protein": 6.3,
    }
    return ProductResult(
        ResultType.PRODUCT,
        Product(
            barcode="3017624010701",
            name="Nutella",
            brand="Ferrero",
            ingredients_text=(
                "sugar, palm oil, hazelnuts, skimmed milk powder, fat reduced cocoa, "
                "emulsifier, vanillin"
            ),
            package=Package("400.0 g", 400, "g", None, OFF),
            nutrition=Nutrition(
                NutritionBasis.PER_100G, {name: off(name, a) for name, a in amounts.items()}
            ),
            source=DataSource(
                OFF, RETRIEVED_AT, url="https://world.openfoodfacts.org/product/3017624010701"
            ),
        ),
    )


def nutrition_only():
    nutrients = {
        "calories": photo("calories", 110),
        "total_fat": photo("total_fat", 0, dv=0),
        "saturated_fat": photo("saturated_fat", 0, dv=0),
        "sodium": photo("sodium", 10, dv=0),
        "carbohydrate": photo("carbohydrate", 26),
        "sugars": photo("sugars", 22, dv=22, certainty=Certainty.UNCERTAIN),
        "fibre": photo("fibre", 0, dv=0),
        "protein": photo("protein", 2),
        "trans_fat": photo("trans_fat", 0),
        "cholesterol": photo("cholesterol", 0),
    }
    return ProductResult(
        ResultType.NUTRITION_ONLY,
        Product(
            serving=Serving("1 cup (250 mL)", 250, "ml", PHOTO),
            nutrition=Nutrition(NutritionBasis.SERVING, nutrients),
            source=DataSource(PHOTO, RETRIEVED_AT),
        ),
    )


MODEL_EXAMPLES = {
    "productComplete": product_complete,
    "productIncomplete": product_incomplete,
    "nutritionOnly": nutrition_only,
    "errorInvalidBarcode": lambda: ApiError(
        ErrorCode.INVALID_BARCODE, "Barcode must be 8 to 14 digits."
    ),
    "errorProductNotFound": lambda: ApiError(
        ErrorCode.PRODUCT_NOT_FOUND, "No product found for barcode 0000000000001."
    ),
    "errorUpstreamUnavailable": lambda: ApiError(
        ErrorCode.UPSTREAM_UNAVAILABLE, "The product database is unavailable. Try again shortly."
    ),
    "errorUpstreamTimeout": lambda: ApiError(
        ErrorCode.UPSTREAM_TIMEOUT, "The product database did not respond in time."
    ),
}


def test_every_documented_example_has_a_model_counterpart():
    assert set(EXAMPLES) == set(MODEL_EXAMPLES)


@pytest.mark.parametrize("name", sorted(MODEL_EXAMPLES))
def test_documented_example_matches_model_output(name):
    assert MODEL_EXAMPLES[name]().to_dict() == EXAMPLES[name]["value"]


def object_schemas(schema, path):
    """Yield (path, schema) for every object schema, including nested ones."""
    if schema.get("type") == "object":
        yield path, schema
        for prop, sub in schema.get("properties", {}).items():
            yield from object_schemas(sub, f"{path}.{prop}")


ALL_OBJECT_SCHEMAS = [
    item for name, schema in SCHEMAS.items() for item in object_schemas(schema, name)
]


@pytest.mark.parametrize(
    ("path", "schema"), ALL_OBJECT_SCHEMAS, ids=[p for p, _ in ALL_OBJECT_SCHEMAS]
)
def test_every_property_is_required_and_closed(path, schema):
    # "Every key is always present" is the contract's core rule.
    assert set(schema["required"]) == set(schema["properties"]), path
    assert schema["additionalProperties"] is False, path


def test_schema_enums_match_model_enums():
    nutrient = SCHEMAS["NutrientValue"]["properties"]
    assert SCHEMAS["Source"]["enum"] == [s.value for s in Source]
    assert nutrient["certainty"]["enum"] == [c.value for c in Certainty]
    assert sorted(nutrient["unit"]["enum"]) == sorted(set(CANONICAL_UNITS.values()))
    assert SCHEMAS["Nutrition"]["properties"]["basis"]["enum"] == [
        *(b.value for b in NutritionBasis),
        None,
    ]
    assert SCHEMAS["ProductResult"]["properties"]["result"]["enum"] == [r.value for r in ResultType]
    assert SCHEMAS["Error"]["properties"]["error"]["properties"]["code"]["enum"] == [
        c.value for c in ErrorCode
    ]


def test_schema_lists_every_model_nutrient():
    nutrients = SCHEMAS["Nutrition"]["properties"]["nutrients"]
    assert list(nutrients["properties"]) == list(ALL_NUTRIENTS)
