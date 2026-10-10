"""Completeness check and photo fallback routing (#15, F1).

The lookup results used here are the sample responses of the API contract
(``docs/api/openapi.yaml``), built by ``test_contract_examples`` and checked there
against the YAML, so these tests do not depend on the Open Food Facts lookup (#14).
"""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.models.product import (
    ALL_NUTRIENTS,
    CANONICAL_UNITS,
    REQUIRED_NUTRIENTS,
    ApiError,
    Certainty,
    Completeness,
    ErrorCode,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    ProductResult,
    ResultType,
    Serving,
    Source,
)
from app.services.fallback_routing import (
    NextAction,
    Reason,
    build_nutrition_only,
    merge_label_nutrition,
    route_lookup,
    same_serving_basis,
)
from tests.test_contract_examples import (
    MODEL_EXAMPLES,
    nutrition_only,
    product_complete,
    product_incomplete,
)

READ_AT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
OFF = Source.OPEN_FOOD_FACTS
PHOTO = Source.NUTRITION_LABEL_PHOTO


def photo(name, amount, certainty=Certainty.CONFIDENT):
    return NutrientValue(amount, CANONICAL_UNITS[name], PHOTO, certainty)


def label_nutrition(basis=NutritionBasis.SERVING, **overrides):
    """A full label reading whose amounts (9) are distinct from every database sample."""
    nutrients = {name: photo(name, 9) for name in ALL_NUTRIENTS}
    nutrients.update(overrides)
    return Nutrition(basis, nutrients)


def label_serving(quantity=30, unit="g"):
    return Serving(f"1 portion ({quantity} {unit})", quantity, unit, PHOTO)


def crackers_without(*names):
    """The contract's complete product with some nutrients missing (still per 30 g serving)."""
    result = product_complete()
    nutrients = {
        name: None if name in names else value
        for name, value in result.product.nutrition.nutrients.items()
    }
    nutrition = Nutrition(NutritionBasis.SERVING, nutrients)
    return ProductResult(ResultType.PRODUCT, replace(result.product, nutrition=nutrition))


def error(name):
    return MODEL_EXAMPLES[name]()


# --- path 1: complete database result ------------------------------------------------------------


def test_complete_result_uses_database_and_requests_no_photo():
    decision = route_lookup(product_complete())

    assert decision.action is NextAction.USE_DATABASE
    assert decision.reason is Reason.COMPLETE
    assert decision.photo_requested is False
    assert decision.photo_fields == ()
    assert decision.product_identified is True


def test_missing_optional_nutrients_do_not_request_a_photo():
    # The contract's complete example has no cholesterol; trans fat is optional too.
    result = crackers_without("trans_fat", "cholesterol")

    assert route_lookup(result).photo_requested is False


def test_missing_name_or_ingredients_alone_does_not_request_a_photo():
    result = product_complete()
    result = ProductResult(ResultType.PRODUCT, replace(result.product, ingredients_text=None))
    decision = route_lookup(result)

    assert result.completeness is Completeness.INCOMPLETE
    assert decision.action is NextAction.USE_DATABASE
    assert decision.reason is Reason.ONLY_NON_NUTRITION_MISSING
    assert decision.photo_requested is False


# --- path 2: identified, required nutrition missing ----------------------------------------------


def test_incomplete_contract_example_requests_a_photo_for_its_missing_fields():
    decision = route_lookup(product_incomplete())

    assert decision.action is NextAction.REQUEST_NUTRITION_PHOTO
    assert decision.reason is Reason.NUTRITION_MISSING
    assert decision.product_identified is True
    assert decision.photo_fields == (
        "serving.size_text",
        "nutrition.basis",
        "nutrition.nutrients.fibre",
    )


@pytest.mark.parametrize("name", REQUIRED_NUTRIENTS)
def test_each_missing_required_nutrient_requests_a_photo(name):
    decision = route_lookup(crackers_without(name))

    assert decision.action is NextAction.REQUEST_NUTRITION_PHOTO
    assert decision.photo_fields == (f"nutrition.nutrients.{name}",)


def test_missing_serving_size_requests_a_photo():
    result = product_complete()
    result = ProductResult(ResultType.PRODUCT, replace(result.product, serving=Serving()))

    assert route_lookup(result).photo_fields == ("serving.size_text",)


def test_photo_fields_exclude_what_a_nutrition_photo_cannot_supply():
    result = crackers_without("sodium")
    result = ProductResult(ResultType.PRODUCT, replace(result.product, ingredients_text=None))
    decision = route_lookup(result)

    assert "ingredients_text" in result.missing_fields
    assert decision.action is NextAction.REQUEST_NUTRITION_PHOTO
    assert decision.photo_fields == ("nutrition.nutrients.sodium",)


def test_per_100g_data_counts_as_incomplete_and_requests_a_photo():
    result = product_complete()
    per_100g = Nutrition(NutritionBasis.PER_100G, result.product.nutrition.nutrients)
    result = ProductResult(ResultType.PRODUCT, replace(result.product, nutrition=per_100g))

    assert route_lookup(result).photo_fields == ("nutrition.basis",)


# --- path 3: lookup did not return a product -----------------------------------------------------


def test_not_found_offers_nutrition_only_photo():
    decision = route_lookup(error("errorProductNotFound"))

    assert decision.action is NextAction.NUTRITION_ONLY_PHOTO
    assert decision.reason is Reason.PRODUCT_NOT_FOUND
    assert decision.product_identified is False
    assert decision.can_retry_lookup is False


@pytest.mark.parametrize("name", ["errorUpstreamUnavailable", "errorUpstreamTimeout"])
def test_lookup_failure_is_not_reported_as_not_found(name):
    decision = route_lookup(error(name))

    assert decision.action is NextAction.NUTRITION_ONLY_PHOTO
    assert decision.reason is Reason.LOOKUP_FAILED
    assert decision.reason is not Reason.PRODUCT_NOT_FOUND
    assert decision.can_retry_lookup is True
    assert decision.product_identified is False


def test_invalid_barcode_asks_for_a_clearer_barcode_photo():
    decision = route_lookup(error("errorInvalidBarcode"))

    assert decision.action is NextAction.RETAKE_BARCODE_PHOTO
    assert decision.reason is Reason.INVALID_BARCODE
    assert decision.photo_requested is False
    assert decision.product_identified is False


def test_every_contract_error_code_is_routed():
    for code in ErrorCode:
        assert route_lookup(ApiError(code, "x")).product_identified is False


def test_route_lookup_rejects_a_nutrition_only_result():
    with pytest.raises(ValueError, match="nutrition_only"):
        route_lookup(nutrition_only())


def test_nutrition_only_fallback_does_not_claim_a_product():
    result = build_nutrition_only(label_serving(250, "ml"), label_nutrition(), READ_AT)
    body = result.to_dict()

    assert body["result"] == "nutrition_only"
    for key in ("barcode", "name", "brand", "ingredients_text"):
        assert body["product"][key] is None
    assert body["product"]["source"]["provider"] == "nutrition_label_photo"
    assert body["product"]["source"]["url"] is None
    assert body["completeness"] == "complete"
    assert body["missing_fields"] == []


def test_nutrition_only_matches_the_contract_example():
    example = nutrition_only()
    built = build_nutrition_only(
        example.product.serving, example.product.nutrition, example.product.source.retrieved_at
    )

    assert built.to_dict() == example.to_dict()
    # Completeness is derived, not set: the uncertain sugars value counts as missing.
    assert built.missing_fields == ["nutrition.nutrients.sugars"]


def test_nutrition_only_keeps_unread_values_null_and_stated_zero_as_zero():
    nutrition = label_nutrition(fibre=None, total_fat=photo("total_fat", 0))
    body = build_nutrition_only(label_serving(), nutrition, READ_AT).to_dict()
    nutrients = body["product"]["nutrition"]["nutrients"]

    assert nutrients["fibre"] is None
    assert nutrients["total_fat"]["amount"] == 0
    assert body["missing_fields"] == ["nutrition.nutrients.fibre"]


def test_nutrition_only_rejects_database_values():
    database_value = product_complete().product.nutrition.nutrients["calories"]

    with pytest.raises(ValueError, match="nutrition_label_photo"):
        build_nutrition_only(label_serving(), label_nutrition(calories=database_value), READ_AT)
    with pytest.raises(ValueError, match="nutrition_label_photo"):
        build_nutrition_only(Serving("30 g", 30, "g", OFF), label_nutrition(), READ_AT)


# --- serving bases are never mixed ---------------------------------------------------------------


def test_same_serving_basis_fills_only_the_missing_nutrients():
    database = crackers_without("fibre", "sodium")
    merged = merge_label_nutrition(database, label_serving(30, "g"), label_nutrition())
    nutrients = merged.product.nutrition.nutrients

    assert nutrients["fibre"] == photo("fibre", 9)
    assert nutrients["sodium"] == photo("sodium", 9)
    for name in REQUIRED_NUTRIENTS:
        if name not in ("fibre", "sodium"):
            assert nutrients[name] == database.product.nutrition.nutrients[name]
    assert merged.product.serving == database.product.serving
    assert merged.completeness is Completeness.COMPLETE
    assert route_lookup(merged).photo_requested is False


def test_different_serving_size_replaces_database_nutrition_instead_of_mixing():
    database = crackers_without("fibre")
    serving = label_serving(40, "g")
    merged = merge_label_nutrition(database, serving, label_nutrition())

    assert merged.product.serving == serving
    assert {v.source for v in merged.product.nutrition.nutrients.values()} == {PHOTO}
    assert merged.product.nutrition.basis is NutritionBasis.SERVING


def test_per_100g_database_values_are_never_combined_with_a_per_serving_label():
    database = product_incomplete()  # contract example: per 100 g, no serving, no fibre
    label = label_nutrition(protein=None)
    merged = merge_label_nutrition(database, label_serving(15, "g"), label)
    nutrients = merged.product.nutrition.nutrients

    assert merged.product.nutrition.basis is NutritionBasis.SERVING
    assert all(v is None or v.source is PHOTO for v in nutrients.values())
    # The label did not give protein. The database's per-100 g protein is not carried
    # over or scaled to the serving: the value stays missing.
    assert nutrients["protein"] is None
    assert merged.missing_fields == ["nutrition.nutrients.protein"]
    # Identity, ingredients and package still come from the database.
    assert merged.product.name == "Nutella"
    assert merged.product.ingredients_text == database.product.ingredients_text
    assert merged.product.package == database.product.package
    assert merged.product.source.provider is OFF


@pytest.mark.parametrize(
    ("serving", "basis"),
    [
        (Serving("30 ml", 30, "ml", PHOTO), NutritionBasis.SERVING),  # different unit
        (Serving("6 crackers", None, None, PHOTO), NutritionBasis.SERVING),  # quantity unread
        (Serving("30 g", 30, "g", PHOTO), NutritionBasis.PER_100G),  # label not per serving
    ],
)
def test_bases_that_cannot_be_shown_equal_are_not_mixed(serving, basis):
    database = crackers_without("fibre")
    merged = merge_label_nutrition(database, serving, label_nutrition(basis))

    assert same_serving_basis(database.product, serving, label_nutrition(basis)) is False
    assert {v.source for v in merged.product.nutrition.nutrients.values()} == {PHOTO}
    assert merged.product.nutrition.basis is basis


def test_database_serving_without_a_quantity_is_not_treated_as_matching():
    database = crackers_without("fibre")
    product = replace(database.product, serving=Serving("6 crackers", None, None, OFF))

    assert same_serving_basis(product, label_serving(30, "g"), label_nutrition()) is False


def test_uncertain_label_value_stays_missing_after_a_merge():
    database = crackers_without("fibre")
    label = label_nutrition(fibre=photo("fibre", 3, Certainty.UNCERTAIN))
    merged = merge_label_nutrition(database, label_serving(30, "g"), label)

    assert merged.product.nutrition.nutrients["fibre"].certainty is Certainty.UNCERTAIN
    assert merged.missing_fields == ["nutrition.nutrients.fibre"]
    assert route_lookup(merged).action is NextAction.REQUEST_NUTRITION_PHOTO


def test_label_that_read_nothing_leaves_the_database_result_unchanged():
    database = crackers_without("fibre")

    assert merge_label_nutrition(database, Serving(), Nutrition()) is database


def test_merge_rejects_a_nutrition_only_result_and_mislabelled_values():
    with pytest.raises(ValueError, match="'product' result"):
        merge_label_nutrition(nutrition_only(), label_serving(), label_nutrition())

    database_value = product_complete().product.nutrition.nutrients["fibre"]
    with pytest.raises(ValueError, match="nutrition_label_photo"):
        merge_label_nutrition(
            crackers_without("fibre"), label_serving(), label_nutrition(fibre=database_value)
        )
