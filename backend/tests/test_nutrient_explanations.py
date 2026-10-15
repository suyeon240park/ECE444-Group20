"""Per-serving %DV, the 5% / 15% rule and nutrient explanations (#37, F3)."""

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml
from jsonschema import Draft202012Validator

from app.models.product import (
    ALL_NUTRIENTS,
    CANONICAL_UNITS,
    Certainty,
    DataSource,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    Product,
    Serving,
    Source,
)
from app.services.daily_values import DAILY_VALUES_URL, DAILY_VALUES_VERSION
from app.services.nutrient_content import load_nutrient_content
from app.services.nutrient_explanations import (
    CALCULATED_LABEL,
    NO_EXPLANATION_MESSAGE,
    NOT_AVAILABLE,
    DailyValueOrigin,
    Interpretation,
    ValueStatus,
    explain_nutrients,
    interpret,
)

OFF = Source.OPEN_FOOD_FACTS
PHOTO = Source.NUTRITION_LABEL_PHOTO
REVIEWED = load_nutrient_content()
UNREVIEWED = dataclasses.replace(REVIEWED, reviewed_on=None, reviewed_by=None)

AMOUNTS = {
    "calories": 190,
    "total_fat": 16,
    "saturated_fat": 3,
    "trans_fat": 0,
    "cholesterol": 0,
    "sodium": 140,
    "carbohydrate": 7,
    "sugars": 3,
    "fibre": 2,
    "protein": 7,
}


def value(name, amount=None, source=OFF, certainty=None, dv=None):
    amount = AMOUNTS[name] if amount is None else amount
    certainty = certainty or (Certainty.REPORTED if source is OFF else Certainty.CONFIDENT)
    return NutrientValue(amount, CANONICAL_UNITS[name], source, certainty, dv)


def product(nutrients=None, basis=NutritionBasis.SERVING):
    if nutrients is None:
        nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    source = DataSource(OFF, datetime(2026, 10, 14, tzinfo=timezone.utc))
    return Product(
        source=source,
        barcode="0064144043101",
        serving=Serving("2 tbsp (30 g)", 30, "g", OFF),
        nutrition=Nutrition(basis, nutrients),
    )


def rows(result):
    return {row.name: row for row in result.rows}


def body_rows(result):
    return {row["name"]: row for row in result.to_dict()["rows"]}


# --- %DV --------------------------------------------------------------------------------


def test_calculated_dv_uses_health_canada_daily_values():
    sodium = rows(explain_nutrients(product(), REVIEWED))["sodium"].daily_value
    assert sodium.percent == pytest.approx(140 / 2300 * 100)
    assert sodium.display_percent == 6
    assert sodium.origin is DailyValueOrigin.CALCULATED
    assert body_rows(explain_nutrients(product(), REVIEWED))["sodium"]["daily_value"]["label"] == (
        CALCULATED_LABEL
    )


def test_label_dv_is_used_as_printed_and_not_labelled_calculated():
    nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    nutrients["sodium"] = value("sodium", source=PHOTO, dv=7)
    result = explain_nutrients(product(nutrients), REVIEWED, ["nutrition.nutrients.sodium"])
    sodium = body_rows(result)["sodium"]["daily_value"]
    assert sodium["percent"] == 7
    assert sodium["origin"] == "label"
    assert sodium["label"] is None


@pytest.mark.parametrize("name", ["calories", "carbohydrate", "protein", "trans_fat"])
def test_no_dv_is_invented(name):
    assert rows(explain_nutrients(product(), REVIEWED))[name].daily_value is None


def test_calories_ignore_a_printed_dv():
    nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    nutrients["calories"] = value("calories", source=PHOTO, dv=10)
    result = explain_nutrients(product(nutrients), REVIEWED, ["nutrition.nutrients.calories"])
    assert rows(result)["calories"].daily_value is None


def test_saturated_dv_is_saturated_plus_trans():
    nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    nutrients["trans_fat"] = value("trans_fat", amount=0.5)
    saturated = rows(explain_nutrients(product(nutrients), REVIEWED))["saturated_fat"]
    assert saturated.daily_value.percent == pytest.approx((3 + 0.5) / 20 * 100)


def test_dv_table_reference_is_returned():
    reference = explain_nutrients(product(), REVIEWED).to_dict()["daily_values_reference"]
    assert reference["url"] == DAILY_VALUES_URL
    assert reference["version"] == DAILY_VALUES_VERSION


# --- 5% / 15% ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        (0, Interpretation.A_LITTLE),
        (5, Interpretation.A_LITTLE),
        (6, None),
        (14, None),
        (15, Interpretation.A_LOT),
        (120, Interpretation.A_LOT),
    ],
)
def test_thresholds(percent, expected):
    assert interpret(percent) is expected


def test_threshold_uses_the_displayed_percent():
    # 5.4% displays as 5%, which is "a little" on the label too.
    nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    nutrients["sodium"] = value("sodium", amount=2300 * 0.054)
    sodium = body_rows(explain_nutrients(product(nutrients), REVIEWED))["sodium"]["daily_value"]
    assert sodium["display_percent"] == 5
    assert sodium["interpretation_text"] == "a little"


def test_a_lot_text():
    nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    nutrients["sodium"] = value("sodium", amount=460)  # 20%
    sodium = body_rows(explain_nutrients(product(nutrients), REVIEWED))["sodium"]["daily_value"]
    assert sodium["interpretation"] == "a_lot"
    assert sodium["interpretation_text"] == "a lot"


def test_per_100g_amounts_get_no_dv_or_interpretation():
    result = explain_nutrients(product(basis=NutritionBasis.PER_100G), REVIEWED)
    assert all(row.daily_value is None for row in result.rows)
    assert rows(result)["sodium"].status is ValueStatus.VERIFIED


# --- missing and unconfirmed values ---------------------------------------------------


def test_missing_nutrient_is_not_available():
    nutrients = {name: value(name) for name in ALL_NUTRIENTS if name != "fibre"}
    fibre = body_rows(explain_nutrients(product(nutrients), REVIEWED))["fibre"]
    assert fibre["value"] is None
    assert fibre["status_text"] == NOT_AVAILABLE
    assert fibre["daily_value"] is None


def test_unconfirmed_photo_value_is_not_explained_as_verified():
    nutrients = {name: value(name, source=PHOTO) for name in ALL_NUTRIENTS}
    sodium = body_rows(explain_nutrients(product(nutrients), REVIEWED))["sodium"]
    assert sodium["status"] == "needs_confirmation"
    assert sodium["value"]["amount"] == 140
    assert sodium["daily_value"] is None
    assert sodium["what_it_is"] is None
    assert sodium["explanation_message"] == NO_EXPLANATION_MESSAGE


def test_unconfirmed_trans_fat_blocks_the_combined_dv():
    nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    nutrients["trans_fat"] = value("trans_fat", source=PHOTO)
    saturated = rows(explain_nutrients(product(nutrients), REVIEWED))["saturated_fat"]
    assert saturated.status is ValueStatus.VERIFIED
    assert saturated.daily_value is None


def test_confirmed_uncertain_photo_value_is_used():
    nutrients = {name: value(name) for name in ALL_NUTRIENTS}
    nutrients["sodium"] = value("sodium", source=PHOTO, certainty=Certainty.UNCERTAIN)
    result = explain_nutrients(product(nutrients), REVIEWED, ["nutrition.nutrients.sodium"])
    assert rows(result)["sodium"].status is ValueStatus.VERIFIED


# --- explanations -----------------------------------------------------------------------


def test_explanation_shows_text_and_source_links():
    sodium = body_rows(explain_nutrients(product(), REVIEWED))["sodium"]
    assert sodium["what_it_is"]["text"].startswith("Sodium is a mineral")
    assert all(
        s["url"].startswith("https://www.canada.ca/") for s in sodium["what_it_is"]["sources"]
    )
    assert sodium["how_to_read"]["sources"]
    assert sodium["explanation_message"] is None
    assert sodium["guidance"] == "limit"


def test_unreviewed_content_shows_no_explanation():
    result = explain_nutrients(product(), UNREVIEWED)
    body = result.to_dict()
    assert body["daily_value_definition"] is None
    for row in body["rows"]:
        assert row["what_it_is"] is None
        assert row["how_to_read"] is None
        assert row["explanation_message"] == NO_EXPLANATION_MESSAGE


def test_content_is_reviewed():
    assert REVIEWED.is_reviewed


def test_partial_explanation_shows_what_is_sourced():
    # Cholesterol has a sourced how_to_read but no what_it_is (#38 review).
    cholesterol = body_rows(explain_nutrients(product(), REVIEWED))["cholesterol"]
    assert cholesterol["what_it_is"] is None
    assert cholesterol["how_to_read"]["text"].startswith("Cholesterol is shown in milligrams")
    assert cholesterol["explanation_message"] is None


def test_nutrient_without_any_reviewed_text_says_so():
    nutrients = dict(REVIEWED.nutrients)
    nutrients["cholesterol"] = dataclasses.replace(
        nutrients["cholesterol"], what_it_is=None, how_to_read=None
    )
    content = dataclasses.replace(REVIEWED, nutrients=MappingProxyType(nutrients))
    cholesterol = body_rows(explain_nutrients(product(), content))["cholesterol"]
    assert cholesterol["explanation_message"] == NO_EXPLANATION_MESSAGE


def test_dv_definition_is_included_once_reviewed():
    definition = explain_nutrients(product(), REVIEWED).to_dict()["daily_value_definition"]
    assert "%DV" in definition["term"]
    assert definition["sources"]


def test_no_overall_score_or_verdict():
    body = explain_nutrients(product(), REVIEWED).to_dict()
    assert set(body) == {"basis", "daily_values_reference", "daily_value_definition", "rows"}


# --- contract ---------------------------------------------------------------------------

SPEC = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "docs/api/openapi.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    ("content", "item"),
    [
        (REVIEWED, product()),
        (UNREVIEWED, product()),
        (REVIEWED, product(basis=NutritionBasis.PER_100G)),
        (REVIEWED, product({name: value(name, source=PHOTO, dv=3) for name in ALL_NUTRIENTS})),
        (REVIEWED, product({}, basis=None)),
    ],
)
def test_output_satisfies_openapi_schema(content, item):
    schema = {
        "$ref": "#/components/schemas/NutrientExplanationResult",
        "components": SPEC["components"],
    }
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(explain_nutrients(item, content).to_dict())
