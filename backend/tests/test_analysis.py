"""Tests for the product-analysis pipeline (#43): both endpoints and the service.

The product database and the vision model are fakes; no network calls run.
"""

from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from app import build_ingredient_analysis, create_app
from app.models.product import (
    ALL_NUTRIENTS,
    CANONICAL_UNITS,
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
from app.services import analysis as analysis_service
from app.services.analysis import AnalysisService, confirmed_paths
from app.services.errors import ProductLookupError
from app.services.fallback_routing import NextAction, Reason, merge_label_nutrition
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import IngredientKnowledgeBase, load_source_policy
from app.services.label_reading import LabelReader
from tests.test_nutrition_label import CONFIG, PHOTO, FakeExtractor

OFF = Source.OPEN_FOOD_FACTS
LABEL = Source.NUTRITION_LABEL_PHOTO
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
BARCODE = "0012345678905"
SPEC = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.yaml").read_text(
        encoding="utf-8"
    )
)
ENTRIES = json.loads(
    (Path(__file__).parent / "fixtures" / "ingredients" / "entries.json").read_text(
        encoding="utf-8"
    )
)


# --- Builders ------------------------------------------------------------------------


def nutrients(source=OFF, certainty=Certainty.REPORTED, amount=2.0):
    return {
        name: NutrientValue(
            amount=amount, unit=CANONICAL_UNITS[name], source=source, certainty=certainty
        )
        for name in ALL_NUTRIENTS
    }


def database_product(*, nutrition=True, ingredients="Sugar, salt, colour (titanium dioxide)"):
    return ProductResult(
        ResultType.PRODUCT,
        Product(
            source=DataSource(OFF, NOW, url=f"https://world.openfoodfacts.org/product/{BARCODE}"),
            barcode=BARCODE,
            name="Example Crackers",
            brand="Example Foods",
            ingredients_text=ingredients,
            serving=Serving("6 crackers (30 g)", 30, "g", OFF) if nutrition else Serving(),
            package=Package("300 g", 300, "g", None, OFF) if nutrition else Package(),
            nutrition=Nutrition(NutritionBasis.SERVING, nutrients()) if nutrition else Nutrition(),
        ),
    )


class FakeLookup:
    """Answers lookups from a dict of barcode -> ProductResult or ProductLookupError."""

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.calls = []

    def lookup(self, barcode):
        self.calls.append(barcode)
        answer = self.answers.get(barcode)
        if answer is None:
            raise ProductLookupError(
                ErrorCode.PRODUCT_NOT_FOUND, f"No product found for {barcode}."
            )
        if isinstance(answer, ProductLookupError):
            raise answer
        return answer


def knowledge():
    return IngredientKnowledgeBase(((e["id"], e) for e in ENTRIES), load_source_policy())


def make_client(lookup=None, extractor=None, ingredients="default"):
    app = create_app({"TESTING": True})
    app.extensions["product_lookup"] = lookup or FakeLookup()
    app.extensions["label_reader"] = LabelReader(CONFIG, extract=extractor or FakeExtractor())
    service = IngredientAnalysisService(knowledge()) if ingredients == "default" else ingredients
    app.extensions["analysis"] = AnalysisService(service)
    return app.test_client()


def post_photo(client, barcode=None, data=PHOTO):
    form = {"image": (io.BytesIO(data), "label.png", "image/png")}
    if barcode is not None:
        form["barcode"] = barcode
    return client.post("/api/analysis/label-photo", data=form, content_type="multipart/form-data")


VALIDATOR = Draft202012Validator(
    {"$ref": "#/components/schemas/AnalysisResult", "components": SPEC["components"]}
)


def ok_body(response):
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    VALIDATOR.validate(body)
    return body


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code


# --- Barcode path ----------------------------------------------------------------------


def test_complete_product_has_every_section():
    client = make_client(FakeLookup({BARCODE: database_product()}))

    body = ok_body(client.get(f"/api/analysis/{BARCODE}"))

    assert body["result"] == "product"
    assert body["completeness"] == "complete"
    assert body["product"]["name"] == "Example Crackers"
    assert body["next_step"] == {
        "action": "use_database",
        "reason": "complete",
        "product_identified": True,
        "photo_fields": [],
        "can_retry_lookup": False,
    }
    assert body["package_nutrition"]["status"] == "calculated"
    assert body["package_nutrition"]["servings"] == 10
    assert body["explanations"] is None
    assert body["ingredients"]["status"] == "analyzed"
    assert body["ingredients"]["flagged_ids"] == ["titanium_dioxide"]


def test_product_without_nutrition_asks_for_a_photo_and_still_analyzes_ingredients():
    client = make_client(FakeLookup({BARCODE: database_product(nutrition=False)}))

    body = ok_body(client.get(f"/api/analysis/{BARCODE}"))

    assert body["completeness"] == "incomplete"
    assert body["next_step"]["action"] == "request_nutrition_photo"
    assert "nutrition.basis" in body["next_step"]["photo_fields"]
    assert body["package_nutrition"]["status"] == "not_calculated"
    assert body["ingredients"]["status"] == "analyzed"


def test_product_without_ingredients_still_has_nutrition():
    client = make_client(FakeLookup({BARCODE: database_product(ingredients=None)}))

    body = ok_body(client.get(f"/api/analysis/{BARCODE}"))

    assert body["ingredients"]["status"] == "unavailable"
    assert body["ingredients"]["message"] == "Ingredient information not available"
    assert body["package_nutrition"]["status"] == "calculated"
    assert body["next_step"]["reason"] == "only_non_nutrition_missing"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProductLookupError(ErrorCode.PRODUCT_NOT_FOUND, "No product found."), 404),
        (ProductLookupError(ErrorCode.UPSTREAM_UNAVAILABLE, "Unavailable."), 502),
        (ProductLookupError(ErrorCode.UPSTREAM_TIMEOUT, "Timed out."), 504),
        (ProductLookupError(ErrorCode.INVALID_BARCODE, "Bad barcode."), 400),
    ],
)
def test_lookup_errors_are_the_products_endpoint_errors(error, status):
    client = make_client(FakeLookup({BARCODE: error}))

    assert_error(client.get(f"/api/analysis/{BARCODE}"), status, error.code.value)


def test_unknown_barcode_is_404():
    assert_error(make_client().get(f"/api/analysis/{BARCODE}"), 404, "product_not_found")


# --- Each section degrades on its own --------------------------------------------------


class BrokenIngredients:
    def analyze(self, product):
        raise RuntimeError("broken knowledge base")


def test_failing_ingredient_analysis_does_not_hide_nutrition():
    client = make_client(FakeLookup({BARCODE: database_product()}), ingredients=BrokenIngredients())

    body = ok_body(client.get(f"/api/analysis/{BARCODE}"))

    assert body["ingredients"] is None
    assert body["package_nutrition"]["status"] == "calculated"


def test_failing_nutrition_calculation_does_not_hide_ingredients(monkeypatch):
    def broken(*args, **kwargs):
        raise ZeroDivisionError

    monkeypatch.setattr(analysis_service, "calculate_package_nutrition", broken)
    client = make_client(FakeLookup({BARCODE: database_product()}))

    body = ok_body(client.get(f"/api/analysis/{BARCODE}"))

    assert body["package_nutrition"] is None
    assert body["ingredients"]["status"] == "analyzed"


def test_knowledge_base_that_does_not_load_leaves_only_ingredients_out(monkeypatch):
    def broken():
        raise ValueError("invalid entry")

    monkeypatch.setattr("app.load_ingredient_knowledge", broken)
    assert build_ingredient_analysis() is None

    client = make_client(FakeLookup({BARCODE: database_product()}), ingredients=None)
    body = ok_body(client.get(f"/api/analysis/{BARCODE}"))

    assert body["ingredients"] is None
    assert body["package_nutrition"]["status"] == "calculated"


def test_app_loads_the_real_knowledge_base():
    app = create_app({"TESTING": True})

    assert app.extensions["analysis"]._ingredients is not None


# --- Photo path ------------------------------------------------------------------------


def test_photo_without_barcode_is_nutrition_only():
    body = ok_body(post_photo(make_client()))

    assert body["result"] == "nutrition_only"
    product = body["product"]
    assert product["barcode"] is None and product["name"] is None and product["brand"] is None
    assert product["source"]["provider"] == "nutrition_label_photo"
    assert body["next_step"] is None
    assert body["ingredients"]["status"] == "unavailable"
    # Every photo value waits for the user, so nothing is scaled yet (Q1).
    assert body["package_nutrition"]["status"] == "not_calculated"
    assert "package.servings_per_package" in body["package_nutrition"]["pending_confirmation"]


def test_photo_with_a_found_barcode_fills_that_products_nutrition():
    lookup = FakeLookup({BARCODE: database_product(nutrition=False)})

    body = ok_body(post_photo(make_client(lookup), barcode=BARCODE))

    assert lookup.calls == [BARCODE]
    assert body["result"] == "product"
    product = body["product"]
    assert product["name"] == "Example Crackers"
    assert product["source"]["provider"] == "open_food_facts"
    assert product["serving"]["source"] == "nutrition_label_photo"
    assert product["nutrition"]["nutrients"]["sodium"]["source"] == "nutrition_label_photo"
    assert product["package"]["servings_per_package"] == 7
    assert body["ingredients"]["status"] == "analyzed"
    assert body["next_step"] is None


@pytest.mark.parametrize(
    "error",
    [
        None,  # not in the database
        ProductLookupError(ErrorCode.UPSTREAM_TIMEOUT, "Timed out."),
    ],
)
def test_photo_with_an_unidentified_barcode_never_claims_a_product(error):
    lookup = FakeLookup({BARCODE: error} if error else {})

    body = ok_body(post_photo(make_client(lookup), barcode=BARCODE))

    assert body["result"] == "nutrition_only"
    assert body["product"]["barcode"] is None
    assert body["product"]["name"] is None


def test_invalid_barcode_is_rejected_before_the_photo_is_read():
    extractor = FakeExtractor()

    response = post_photo(make_client(extractor=extractor), barcode="12ab")

    assert_error(response, 400, "invalid_barcode")
    assert extractor.calls == []


def test_blank_barcode_is_treated_as_none():
    body = ok_body(post_photo(make_client(), barcode="  "))

    assert body["result"] == "nutrition_only"


def test_photo_errors_are_the_nutrition_label_errors():
    client = make_client(extractor=FakeExtractor({"table_found": False}))

    assert_error(post_photo(client), 422, "nutrition_table_not_found")
    assert_error(
        client.post("/api/analysis/label-photo", data={}, content_type="multipart/form-data"),
        400,
        "missing_image",
    )


# --- Confirmation (Q1) -----------------------------------------------------------------


def confirmed_photo_result(certainty):
    return ProductResult(
        ResultType.NUTRITION_ONLY,
        Product(
            source=DataSource(LABEL, NOW),
            serving=Serving("6 crackers (30 g)", 30, "g", LABEL, certainty),
            package=Package(servings_per_package=7, source=LABEL, certainty=certainty),
            nutrition=Nutrition(NutritionBasis.SERVING, nutrients(LABEL, certainty)),
        ),
    )


def test_confirmed_paths_lists_user_confirmed_values():
    product = confirmed_photo_result(Certainty.USER_CONFIRMED).product

    paths = confirmed_paths(product)

    assert paths[:3] == ["serving", "package.servings_per_package", "package.quantity"]
    assert "nutrition.nutrients.sodium" in paths


def test_confirmed_paths_ignores_unconfirmed_and_database_values():
    assert confirmed_paths(confirmed_photo_result(Certainty.UNCERTAIN).product) == []
    assert confirmed_paths(database_product().product) == []


def test_user_confirmed_photo_values_are_scaled_to_the_package():
    service = AnalysisService(None)

    confirmed = service.analyze(confirmed_photo_result(Certainty.USER_CONFIRMED))
    unconfirmed = service.analyze(confirmed_photo_result(Certainty.UNCERTAIN))

    assert confirmed.package_nutrition.to_dict()["status"] == "calculated"
    assert confirmed.package_nutrition.servings == 7
    assert unconfirmed.package_nutrition.to_dict()["status"] == "not_calculated"


# --- Label package merge (#15 path 2) --------------------------------------------------


def label_reading():
    serving = Serving("1 portion (30 g)", 30, "g", LABEL)
    nutrition = Nutrition(NutritionBasis.SERVING, nutrients(LABEL, Certainty.UNCERTAIN))
    package = Package(servings_per_package=7, source=LABEL)
    return serving, nutrition, package


def test_label_servings_per_package_fills_a_database_package_without_one():
    merged = merge_label_nutrition(database_product(), *label_reading())

    assert merged.product.package.servings_per_package == 7
    assert merged.product.package.source is LABEL


def test_database_servings_per_package_is_kept():
    database = database_product()
    database = replace(
        database,
        product=replace(database.product, package=Package("300 g", 300, "g", 10, OFF)),
    )

    merged = merge_label_nutrition(database, *label_reading())

    assert merged.product.package.servings_per_package == 10
    assert merged.product.package.source is OFF


def test_label_package_must_come_from_the_photo():
    serving, nutrition, _ = label_reading()

    with pytest.raises(ValueError, match="label package"):
        merge_label_nutrition(
            database_product(), serving, nutrition, Package(servings_per_package=7, source=OFF)
        )


# --- Contract --------------------------------------------------------------------------


def test_next_step_schema_lists_the_actions_a_found_product_can_get():
    schema = SPEC["components"]["schemas"]["NextStep"]["properties"]
    found = {NextAction.USE_DATABASE.value, NextAction.REQUEST_NUTRITION_PHOTO.value}
    reasons = {Reason.COMPLETE.value, Reason.NUTRITION_MISSING.value}
    reasons.add(Reason.ONLY_NON_NUTRITION_MISSING.value)
    assert set(schema["action"]["enum"]) == found
    assert set(schema["reason"]["enum"]) == reasons


def test_analysis_result_extends_the_product_result_contract():
    schemas = SPEC["components"]["schemas"]
    product_keys = schemas["ProductResult"]["required"]

    assert schemas["AnalysisResult"]["required"][: len(product_keys)] == product_keys
