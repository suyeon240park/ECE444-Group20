from datetime import datetime, timezone

import pytest

from app.models.product import (
    ALL_NUTRIENTS,
    NutritionBasis,
    ProductResult,
    ResultType,
    Source,
    compute_missing_fields,
)
from app.services.normalize import _NUTRIENT_KEYS, has_no_data, normalize_off_product

NOW = datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc)
BARCODE = "0013000006408"


def normalize(raw, barcode=BARCODE):
    return normalize_off_product(raw, barcode, NOW)


def nutriments(suffix, **values):
    """Build OFF-style nutriments, e.g. nutriments("_serving", fat=1) -> {"fat_serving": 1}."""
    return {f"{key.replace('_', '-')}{suffix}": value for key, value in values.items()}


def amounts(product):
    return {k: (v.amount if v else None) for k, v in product.nutrition.nutrients.items()}


def test_every_model_nutrient_has_an_off_mapping():
    assert set(_NUTRIENT_KEYS) == set(ALL_NUTRIENTS)


# --- real records --------------------------------------------------------------------------------


def test_complete_per_serving_product(off_product):
    product = normalize(off_product("ketchup_found"))

    assert product.barcode == "0013000006408"
    assert product.name == "Tomato Ketchup"
    assert product.brand
    assert product.ingredients_text.startswith("Tomatoes")
    assert product.serving.size_text == "1 Tbsp (17 g)"
    assert (product.serving.quantity, product.serving.unit) == (17, "g")
    assert product.serving.source is Source.OPEN_FOOD_FACTS
    assert product.package.quantity_text == "20 oz - 570g"
    assert product.package.unit == "g"
    assert product.package.quantity == pytest.approx(566.99, abs=0.01)
    assert product.package.servings_per_package is None
    assert product.nutrition.basis is NutritionBasis.SERVING
    assert product.source.url == "https://world.openfoodfacts.org/product/0013000006408"
    assert product.source.last_modified_at == datetime.fromtimestamp(1784308872, tz=timezone.utc)

    result = ProductResult(ResultType.PRODUCT, product)
    assert result.missing_fields == []


def test_sodium_is_converted_from_grams_to_milligrams(off_product):
    nutrients = normalize(off_product("ketchup_found")).nutrition.nutrients

    assert nutrients["sodium"].amount == 122  # OFF: sodium_serving = 0.122 g
    assert nutrients["sodium"].unit == "mg"
    assert nutrients["calories"].amount == 16.5
    assert nutrients["calories"].unit == "kcal"
    assert nutrients["fibre"].amount == 0.119


def test_a_stated_zero_is_kept_as_zero(off_product):
    nutrients = normalize(off_product("ketchup_found")).nutrition.nutrients

    assert nutrients["total_fat"].amount == 0
    assert nutrients["trans_fat"].amount == 0
    assert nutrients["cholesterol"].amount == 0


def test_nutrients_are_database_values_with_no_printed_daily_value(off_product):
    for value in normalize(off_product("ketchup_found")).nutrition.nutrients.values():
        if value is not None:
            assert value.source is Source.OPEN_FOOD_FACTS
            assert value.certainty.value == "reported"
            assert value.daily_value_percent is None


def test_product_with_only_per_100g_data_is_incomplete(off_product):
    product = normalize(off_product("nutella_found"), "3017624010701")

    assert product.name == "Nutella"
    assert product.brand == "Ferrero"
    assert product.serving.size_text is None
    assert product.serving.source is None
    assert product.nutrition.basis is NutritionBasis.PER_100G
    assert product.nutrition.nutrients["sodium"].amount == 43
    assert product.nutrition.nutrients["fibre"] is None
    assert compute_missing_fields(product) == [
        "serving.size_text",
        "nutrition.basis",
        "nutrition.nutrients.fibre",
    ]


def test_empty_ingredient_string_and_missing_nutrition_become_null(off_product):
    product = normalize(off_product("kraft_no_ingredients"), "0068100058925")

    assert product.ingredients_text is None
    assert product.nutrition.basis is None
    assert set(amounts(product).values()) == {None}
    assert product.package.quantity_text == "200 g"
    assert not has_no_data(product)


def test_record_with_only_a_code_has_no_data(off_product):
    product = normalize(off_product("empty_record"), "4006381333931")

    assert has_no_data(product)
    assert product.barcode == "4006381333931"
    assert product.serving.source is None
    assert product.package.source is None


# --- text fields ---------------------------------------------------------------------------------


def test_name_falls_back_through_languages():
    assert normalize({"product_name": "Plain", "product_name_en": "En"}).name == "Plain"
    assert normalize({"product_name": " ", "product_name_en": "En"}).name == "En"
    assert normalize({"product_name_en": "", "product_name_fr": "Fr"}).name == "Fr"
    assert normalize({"product_name": "  "}).name is None


def test_ingredients_prefer_english_then_generic_then_french():
    both = {"ingredients_text_en": "sugar", "ingredients_text": "sucre"}
    assert normalize(both).ingredients_text == "sugar"
    assert normalize({"ingredients_text": "sucre"}).ingredients_text == "sucre"
    assert (
        normalize({"ingredients_text": "", "ingredients_text_fr": "sel"}).ingredients_text == "sel"
    )


def test_text_is_trimmed_and_non_strings_are_missing():
    product = normalize({"product_name": "  Crackers \n", "brands": 5, "quantity": ["400 g"]})

    assert product.name == "Crackers"
    assert product.brand is None
    assert product.package.quantity_text is None


# --- serving and package -------------------------------------------------------------------------


def test_serving_with_text_only_has_no_quantity():
    serving = normalize({"serving_size": "1 cup"}).serving

    assert (serving.size_text, serving.quantity, serving.unit) == ("1 cup", None, None)
    assert serving.source is Source.OPEN_FOOD_FACTS


def test_quantity_without_a_usable_unit_is_dropped():
    raw = {"serving_size": "1 oz", "serving_quantity": 28, "serving_quantity_unit": "oz"}
    serving = normalize(raw).serving

    assert (serving.quantity, serving.unit) == (None, None)
    assert serving.size_text == "1 oz"


@pytest.mark.parametrize("quantity", [0, -5, "abc", None, True, float("nan"), float("inf")])
def test_unusable_quantities_are_dropped(quantity):
    raw = {"product_quantity": quantity, "product_quantity_unit": "g", "quantity": "400 g"}
    package = normalize(raw).package

    assert (package.quantity, package.unit) == (None, None)
    assert package.quantity_text == "400 g"


def test_numeric_strings_and_uppercase_units_are_accepted():
    raw = {"product_quantity": "400", "product_quantity_unit": "G"}

    assert (normalize(raw).package.quantity, normalize(raw).package.unit) == (400.0, "g")


def test_package_without_any_value_has_no_source():
    assert normalize({"quantity": " "}).package.source is None


# --- nutrition basis -----------------------------------------------------------------------------


def test_per_serving_values_are_never_topped_up_from_per_100g():
    raw = {
        "serving_size": "30 g",
        "nutriments": {
            **nutriments("_serving", energy_kcal=140, sodium=0.21),
            **nutriments("_100g", energy_kcal=467, sodium=0.7, fat=16.7, proteins=10),
        },
    }
    product = normalize(raw)

    assert product.nutrition.basis is NutritionBasis.SERVING
    assert amounts(product)["calories"] == 140
    assert amounts(product)["sodium"] == 210
    assert amounts(product)["total_fat"] is None
    assert amounts(product)["protein"] is None


def test_serving_values_without_a_serving_size_are_not_used():
    raw = {"nutriments": {**nutriments("_serving", energy_kcal=140), **nutriments("_100g", fat=3)}}
    product = normalize(raw)

    assert product.nutrition.basis is NutritionBasis.PER_100G
    assert amounts(product)["calories"] is None
    assert amounts(product)["total_fat"] == 3


def test_serving_size_without_serving_values_uses_per_100g():
    raw = {"serving_size": "30 g", "nutriments": nutriments("_100g", energy_kcal=467)}
    product = normalize(raw)

    assert product.nutrition.basis is NutritionBasis.PER_100G
    assert amounts(product)["calories"] == 467


@pytest.mark.parametrize(
    "raw_units",
    [{"product_quantity_unit": "ml"}, {"serving_quantity_unit": " ML "}],
)
def test_products_sold_by_volume_are_per_100ml(raw_units):
    raw = {"nutriments": nutriments("_100g", energy_kcal=42), **raw_units}

    assert normalize(raw).nutrition.basis is NutritionBasis.PER_100ML


def test_solid_products_are_per_100g():
    raw = {"nutriments": nutriments("_100g", energy_kcal=42), "product_quantity_unit": "g"}

    assert normalize(raw).nutrition.basis is NutritionBasis.PER_100G


@pytest.mark.parametrize("nutriments_value", [None, [], "x", {}])
def test_missing_or_malformed_nutriments_give_empty_nutrition(nutriments_value):
    product = normalize({"serving_size": "30 g", "nutriments": nutriments_value})

    assert product.nutrition.basis is None
    assert set(amounts(product).values()) == {None}


@pytest.mark.parametrize("bad", [-1, "n/a", None, True, float("nan"), float("inf"), [], {}])
def test_bad_nutrient_values_become_missing(bad):
    raw = {"serving_size": "30 g", "nutriments": {"fat_serving": bad, "proteins_serving": 4}}
    product = normalize(raw)

    assert amounts(product)["total_fat"] is None
    assert amounts(product)["protein"] == 4


def test_numeric_string_nutrient_values_are_accepted():
    raw = {"serving_size": "30 g", "nutriments": {"proteins_serving": "4.5"}}

    assert amounts(normalize(raw))["protein"] == 4.5


def test_unit_conversion_leaves_no_float_noise():
    raw = {"serving_size": "30 g", "nutriments": nutriments("_serving", sodium=0.043)}

    assert amounts(normalize(raw))["sodium"] == 43


# --- identity and provenance ---------------------------------------------------------------------


def test_off_code_is_used_when_valid():
    assert normalize({"code": "3017624010701"}, "03017624010701").barcode == "3017624010701"


@pytest.mark.parametrize("code", [None, "", "123", "abc", 3017624010701])
def test_requested_barcode_is_used_when_off_code_is_unusable(code):
    assert normalize({"code": code}, "3017624010701").barcode == "3017624010701"


@pytest.mark.parametrize("modified", [None, "x", -1e30, 1e30, float("nan"), True])
def test_bad_last_modified_becomes_null(modified):
    assert normalize({"last_modified_t": modified}).source.last_modified_at is None


def test_retrieved_at_is_the_supplied_time():
    assert normalize({}).source.retrieved_at == NOW


# --- no-data check -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        {"product_name": "Crackers"},
        {"brands": "Example"},
        {"ingredients_text": "salt"},
        {"serving_size": "30 g"},
        {"quantity": "400 g"},
        {"nutriments": {"proteins_100g": 4}},
    ],
)
def test_any_single_piece_of_data_is_enough_to_count_as_a_product(raw):
    assert not has_no_data(normalize(raw))


@pytest.mark.parametrize(
    "raw", [{}, {"code": "3017624010701"}, {"product_name": "", "brands": " "}]
)
def test_nothing_usable_counts_as_no_data(raw):
    assert has_no_data(normalize(raw))
