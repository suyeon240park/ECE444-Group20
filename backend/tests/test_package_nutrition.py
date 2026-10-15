"""Whole-package nutrition (#36, F2): both multiplier paths, units, missing data, %DV."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from app.models.package_nutrition import (
    APPROXIMATE_LABEL,
    NOT_CALCULATED_MESSAGE,
    WHOLE_PACKAGE_DAILY_VALUE_LABEL,
    MultiplierMethod,
    NotCalculatedReason,
    PackageNutritionResult,
    PackageNutritionStatus,
    WholePackageStatus,
)
from app.models.product import (
    ALL_NUTRIENTS,
    CANONICAL_UNITS,
    Certainty,
    DataSource,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    Package,
    Product,
    Serving,
    Source,
)
from app.services.daily_values import DAILY_VALUES, DAILY_VALUES_VERSION, daily_value_percent
from app.services.package_nutrition import calculate_package_nutrition, display_amount

RETRIEVED_AT = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
OFF = Source.OPEN_FOOD_FACTS
PHOTO = Source.NUTRITION_LABEL_PHOTO

# Per serving (30 g), loosely a peanut butter.
PER_SERVING = {
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


def off_value(name):
    return NutrientValue(PER_SERVING[name], CANONICAL_UNITS[name], OFF, Certainty.REPORTED)


def photo_value(name, certainty=Certainty.CONFIDENT):
    return NutrientValue(PER_SERVING[name], CANONICAL_UNITS[name], PHOTO, certainty)


def make_product(
    *,
    serving=None,
    package=None,
    nutrients=None,
    basis=NutritionBasis.SERVING,
):
    if serving is None:
        serving = Serving("2 tbsp (30 g)", 30, "g", OFF)
    if package is None:
        package = Package("375 g", 375, "g", None, OFF)
    if nutrients is None:
        nutrients = {name: off_value(name) for name in ALL_NUTRIENTS}
    return Product(
        source=DataSource(OFF, RETRIEVED_AT),
        barcode="0064144043101",
        serving=serving,
        package=package,
        nutrition=Nutrition(basis, nutrients),
    )


def rows_by_name(result):
    return {row.name: row for row in result.rows}


# --- multiplier path 1: stated servings per package ---------------------------------


def test_stated_servings_per_package_is_exact():
    product = make_product(package=Package("375 g", 375, "g", 12, OFF))
    result = calculate_package_nutrition(product)

    assert result.status is PackageNutritionStatus.CALCULATED
    assert result.method is MultiplierMethod.SERVINGS_PER_PACKAGE
    assert result.servings == 12
    assert not result.approximate
    assert result.to_dict()["approximate_label"] is None
    assert rows_by_name(result)["calories"].whole_package.amount == 190 * 12


def test_stated_servings_win_over_package_quantity():
    # 375 / 30 = 12.5, but the label states 12: the stated value is used.
    product = make_product(package=Package("375 g", 375, "g", 12, OFF))
    assert calculate_package_nutrition(product).servings == 12


def test_stated_servings_work_without_any_package_quantity():
    product = make_product(package=Package(None, None, None, 4, OFF))
    result = calculate_package_nutrition(product)
    assert result.servings == 4
    assert result.whole_package_label == "Whole package (4 servings)"


# --- multiplier path 2: package quantity / serving size -------------------------------


def test_derived_multiplier_is_approximate_and_unrounded():
    result = calculate_package_nutrition(make_product())

    assert result.status is PackageNutritionStatus.CALCULATED
    assert result.method is MultiplierMethod.PACKAGE_QUANTITY
    assert result.servings == 12.5
    assert result.approximate
    body = result.to_dict()
    assert body["approximate"] is True
    assert body["approximate_label"] == APPROXIMATE_LABEL
    assert body["whole_package_label"] == "Whole package (375 g)"
    assert body["per_serving_label"] == "Per serving (2 tbsp (30 g))"


def test_rounding_happens_only_for_display():
    # 500 / 30 = 16.666…; 7 g protein per serving -> 116.666… g.
    product = make_product(package=Package("500 g", 500, "g", None, OFF))
    result = calculate_package_nutrition(product)
    protein = rows_by_name(result)["protein"].whole_package

    assert result.servings == pytest.approx(500 / 30)
    assert result.display_servings == 16.7
    assert protein.amount == pytest.approx(7 * 500 / 30)
    assert protein.display_amount == 117


def test_millilitres_are_compatible_with_millilitres():
    product = make_product(
        serving=Serving("250 mL", 250, "ml", OFF),
        package=Package("2 L", 2000, "ml", None, OFF),
    )
    result = calculate_package_nutrition(product)
    assert result.servings == 8
    assert result.approximate


def test_single_serve_package_slightly_under_the_serving_is_kept():
    product = make_product(package=Package("29 g", 29, "g", None, OFF))
    result = calculate_package_nutrition(product)
    assert result.status is PackageNutritionStatus.CALCULATED
    assert result.servings == pytest.approx(29 / 30)


# --- no whole-package values ----------------------------------------------------------


@pytest.mark.parametrize(
    ("serving", "package", "reason"),
    [
        (
            Serving("250 mL", 250, "ml", OFF),
            Package("500 g", 500, "g", None, OFF),
            NotCalculatedReason.INCOMPATIBLE_UNITS,
        ),
        (
            Serving("30 g", 30, "g", OFF),
            Package("1 L", 1000, "ml", None, OFF),
            NotCalculatedReason.INCOMPATIBLE_UNITS,
        ),
        (
            Serving("30 g", 30, "g", OFF),
            Package(),
            NotCalculatedReason.NO_PACKAGE_INFORMATION,
        ),
        (
            # Package text alone, e.g. "1 jar", gives no quantity to divide.
            Serving("30 g", 30, "g", OFF),
            Package("1 jar", None, None, None, OFF),
            NotCalculatedReason.NO_PACKAGE_INFORMATION,
        ),
        (
            Serving("2 tbsp", None, None, OFF),
            Package("375 g", 375, "g", None, OFF),
            NotCalculatedReason.NO_SERVING_QUANTITY,
        ),
        (
            # #28: a wrong package size, smaller than one serving.
            Serving("30 g", 30, "g", OFF),
            Package("5 g", 5, "g", None, OFF),
            NotCalculatedReason.PACKAGE_SMALLER_THAN_SERVING,
        ),
    ],
)
def test_unrelatable_serving_and_package_give_the_f2_message(serving, package, reason):
    result = calculate_package_nutrition(make_product(serving=serving, package=package))
    body = result.to_dict()

    assert result.status is PackageNutritionStatus.NOT_CALCULATED
    assert result.reason is reason
    assert body["message"] == NOT_CALCULATED_MESSAGE
    assert body["servings"] is None
    assert body["whole_package_label"] is None
    assert body["approximate"] is False
    for row in result.rows:
        assert row.whole_package is None
        assert row.whole_package_status is WholePackageStatus.NOT_AVAILABLE
    # The labelled serving view is never replaced.
    assert rows_by_name(result)["calories"].per_serving == off_value("calories")


@pytest.mark.parametrize("basis", [NutritionBasis.PER_100G, None])
def test_per_100g_or_no_nutrition_is_never_scaled(basis):
    nutrients = {} if basis is None else None
    result = calculate_package_nutrition(make_product(basis=basis, nutrients=nutrients))
    assert result.reason is NotCalculatedReason.NO_PER_SERVING_NUTRITION
    assert result.per_serving_label is None
    assert all(row.per_serving is None and row.whole_package is None for row in result.rows)


def test_missing_nutrient_is_not_available_while_others_are_calculated():
    nutrients = {name: off_value(name) for name in ALL_NUTRIENTS if name != "fibre"}
    rows = rows_by_name(calculate_package_nutrition(make_product(nutrients=nutrients)))

    assert rows["fibre"].per_serving is None
    assert rows["fibre"].whole_package is None
    assert rows["fibre"].whole_package_status is WholePackageStatus.NOT_AVAILABLE
    assert rows["protein"].whole_package_status is WholePackageStatus.CALCULATED


def test_every_nutrient_has_a_row_in_table_order():
    result = calculate_package_nutrition(make_product())
    assert [row.name for row in result.rows] == list(ALL_NUTRIENTS)


# --- label-photo values need the user's confirmation (#39) ----------------------------


def photo_product(**overrides):
    defaults = {
        "serving": Serving("2 tbsp (30 g)", 30, "g", PHOTO),
        "package": Package(None, None, None, 12, PHOTO),
        "nutrients": {name: photo_value(name) for name in ALL_NUTRIENTS},
    }
    defaults.update(overrides)
    return make_product(**defaults)


def test_unconfirmed_photo_servings_per_package_is_not_used():
    result = calculate_package_nutrition(photo_product())
    assert result.status is PackageNutritionStatus.NOT_CALCULATED
    assert result.reason is NotCalculatedReason.UNCONFIRMED_PHOTO_VALUES
    assert "package.servings_per_package" in result.pending_confirmation


def test_confirmed_photo_values_are_used():
    confirmed = ["package.servings_per_package"] + [
        f"nutrition.nutrients.{name}" for name in ALL_NUTRIENTS
    ]
    result = calculate_package_nutrition(photo_product(), confirmed)
    assert result.status is PackageNutritionStatus.CALCULATED
    assert result.servings == 12
    assert result.pending_confirmation == ()


def test_unconfirmed_photo_nutrient_is_not_scaled():
    confirmed = ["package.servings_per_package", "nutrition.nutrients.calories"]
    result = calculate_package_nutrition(photo_product(), confirmed)
    rows = rows_by_name(result)

    assert rows["calories"].whole_package_status is WholePackageStatus.CALCULATED
    assert rows["sodium"].whole_package is None
    assert rows["sodium"].whole_package_status is WholePackageStatus.NEEDS_CONFIRMATION
    assert "nutrition.nutrients.sodium" in result.pending_confirmation


def test_no_confirmed_nutrients_means_nothing_calculated():
    result = calculate_package_nutrition(photo_product(), ["package.servings_per_package"])
    assert result.reason is NotCalculatedReason.UNCONFIRMED_PHOTO_VALUES
    assert all(
        row.whole_package_status is WholePackageStatus.NEEDS_CONFIRMATION for row in result.rows
    )


def test_user_confirmation_lets_an_uncertain_photo_value_be_used():
    nutrients = {name: photo_value(name, Certainty.UNCERTAIN) for name in ALL_NUTRIENTS}
    confirmed = ["package.servings_per_package", "nutrition.nutrients.protein"]
    rows = rows_by_name(calculate_package_nutrition(photo_product(nutrients=nutrients), confirmed))
    assert rows["protein"].whole_package.amount == 7 * 12


def test_unconfirmed_photo_serving_blocks_the_derived_multiplier():
    product = photo_product(
        package=Package("375 g", 375, "g", None, OFF),
        nutrients={name: off_value(name) for name in ALL_NUTRIENTS},
    )
    result = calculate_package_nutrition(product)
    assert result.reason is NotCalculatedReason.UNCONFIRMED_PHOTO_VALUES
    assert result.pending_confirmation == ("serving",)

    confirmed = calculate_package_nutrition(product, ["serving"])
    assert confirmed.method is MultiplierMethod.PACKAGE_QUANTITY


def test_unconfirmed_stated_servings_falls_back_to_package_quantity():
    product = make_product(package=Package("375 g", 375, "g", 12, PHOTO))
    result = calculate_package_nutrition(product, ["package.quantity"])

    assert result.method is MultiplierMethod.PACKAGE_QUANTITY
    assert result.servings == 12.5
    assert result.pending_confirmation == ("package.servings_per_package",)
    assert result.whole_package_label == "Whole package (375 g)"


def test_unconfirmed_photo_package_text_is_not_shown():
    product = make_product(package=Package("375 g", 375, "g", 12, PHOTO))
    result = calculate_package_nutrition(product, ["package.servings_per_package"])
    assert result.method is MultiplierMethod.SERVINGS_PER_PACKAGE
    assert result.whole_package_label == "Whole package (12 servings)"


# --- whole-package %DV ----------------------------------------------------------------


def test_whole_package_dv_is_calculated_from_the_whole_package_amount():
    nutrients = {name: off_value(name) for name in ALL_NUTRIENTS}
    # A printed per-serving %DV must never be scaled into the whole-package one.
    nutrients["sodium"] = NutrientValue(140, "mg", PHOTO, Certainty.CONFIDENT, 99)
    product = make_product(nutrients=nutrients)
    result = calculate_package_nutrition(product, ["nutrition.nutrients.sodium"])
    sodium = rows_by_name(result)["sodium"].whole_package

    assert sodium.daily_value_percent == pytest.approx(140 * 12.5 / 2300 * 100)
    assert sodium.display_daily_value_percent == 76


def test_dv_label_is_given_once_for_the_column_not_per_row():
    body = calculate_package_nutrition(make_product()).to_dict()
    assert body["daily_value_label"] == WHOLE_PACKAGE_DAILY_VALUE_LABEL
    assert all("daily_value_label" not in (row["whole_package"] or {}) for row in body["rows"])


def test_no_dv_label_without_any_whole_package_dv():
    # Only nutrients without a Daily Value: nothing to label.
    nutrients = {name: off_value(name) for name in ("calories", "carbohydrate", "protein")}
    body = calculate_package_nutrition(make_product(nutrients=nutrients)).to_dict()
    assert body["status"] == "calculated"
    assert body["daily_value_label"] is None

    not_calculated = calculate_package_nutrition(make_product(package=Package())).to_dict()
    assert not_calculated["daily_value_label"] is None


@pytest.mark.parametrize("name", ["calories", "carbohydrate", "protein", "trans_fat"])
def test_no_dv_is_invented(name):
    whole = rows_by_name(calculate_package_nutrition(make_product()))[name].whole_package
    assert whole.daily_value_percent is None
    assert whole.display_daily_value_percent is None


def test_saturated_dv_covers_saturated_plus_trans():
    nutrients = {name: off_value(name) for name in ALL_NUTRIENTS}
    nutrients["trans_fat"] = NutrientValue(0.2, "g", OFF, Certainty.REPORTED)
    product = make_product(nutrients=nutrients)
    saturated = rows_by_name(calculate_package_nutrition(product))["saturated_fat"]

    assert saturated.whole_package.daily_value_percent == pytest.approx((3 + 0.2) * 12.5 / 20 * 100)


def test_saturated_dv_needs_trans_fat_too():
    nutrients = {name: off_value(name) for name in ALL_NUTRIENTS if name != "trans_fat"}
    saturated = rows_by_name(calculate_package_nutrition(make_product(nutrients=nutrients)))[
        "saturated_fat"
    ]
    assert saturated.whole_package.amount == 3 * 12.5
    assert saturated.whole_package.daily_value_percent is None


def test_daily_values_table():
    assert DAILY_VALUES_VERSION == "2022-10-20"
    assert set(DAILY_VALUES) <= set(ALL_NUTRIENTS)
    assert not {"calories", "carbohydrate", "protein", "trans_fat"} & set(DAILY_VALUES)
    assert daily_value_percent("sodium", {"sodium": 2300}) == 100
    assert daily_value_percent("sodium", {"sodium": None}) is None
    assert daily_value_percent("calories", {"calories": 2000}) is None


# --- display rounding -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "unit", "expected"),
    [
        (2.25, "g", 2.3),
        (0.04, "g", 0.0),
        (9.96, "g", 10.0),
        (12.5, "g", 13),
        (237.5, "kcal", 238),
        (1749.4, "mg", 1749),
    ],
)
def test_display_amount(amount, unit, expected):
    assert display_amount(amount, unit) == expected


def test_to_dict_has_every_key():
    body = calculate_package_nutrition(make_product()).to_dict()
    assert set(body) == {
        "status",
        "per_serving_label",
        "whole_package_label",
        "servings",
        "display_servings",
        "method",
        "approximate",
        "approximate_label",
        "daily_value_label",
        "reason",
        "message",
        "pending_confirmation",
        "rows",
    }
    assert set(body["rows"][0]) == {"name", "per_serving", "whole_package", "whole_package_status"}
    assert set(body["rows"][0]["whole_package"]) == {
        "amount",
        "unit",
        "display_amount",
        "daily_value_percent",
        "display_daily_value_percent",
    }


# --- contract -------------------------------------------------------------------------

SPEC = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "docs/api/openapi.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "product",
    [
        make_product(),
        make_product(package=Package("375 g", 375, "g", 12, OFF)),
        make_product(package=Package()),
        make_product(basis=NutritionBasis.PER_100G),
        photo_product(),
    ],
)
def test_output_satisfies_openapi_schema(product):
    schema = {
        "$ref": "#/components/schemas/PackageNutritionResult",
        "components": SPEC["components"],
    }
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(calculate_package_nutrition(product).to_dict())


def test_result_rejects_inconsistent_status():
    with pytest.raises(ValueError, match="servings and a method"):
        PackageNutritionResult(PackageNutritionStatus.CALCULATED, ())
    with pytest.raises(ValueError, match="reason is required"):
        PackageNutritionResult(
            PackageNutritionStatus.CALCULATED,
            (),
            servings=2,
            method=MultiplierMethod.SERVINGS_PER_PACKAGE,
            reason=NotCalculatedReason.INCOMPATIBLE_UNITS,
        )
