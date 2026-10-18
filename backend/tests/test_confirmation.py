"""Confirming photo values and re-analyzing (#39): POST /api/analysis/confirm.

Each round trip starts from a real ``POST /api/analysis/label-photo`` response (fake
model and database), marks values the way the client does, and sends it back.
"""

from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from app.models.product import (
    Certainty,
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
from app.services.confirmation import (
    ConfirmationError,
    PhotoValues,
    parse_photo_values,
    rebuild_product,
)
from app.services.errors import ProductLookupError
from tests.test_analysis import (
    BARCODE,
    SPEC,
    FakeLookup,
    assert_error,
    database_product,
    explanation_row,
    make_client,
    ok_body,
    post_photo,
)

PHOTO = Source.NUTRITION_LABEL_PHOTO


def confirm(client, body):
    return client.post("/api/analysis/confirm", json=body)


def photo_values(body):
    """Every label-photo value in a response's product, as (dotted path, object)."""
    product = body["product"]
    found = []
    for key in ("serving", "package"):
        if product[key]["source"] == PHOTO.value:
            found.append((key, product[key]))
    for name, value in product["nutrition"]["nutrients"].items():
        if value is not None and value["source"] == PHOTO.value:
            found.append((f"nutrition.nutrients.{name}", value))
    return found


def confirmed(body, skip=()):
    """The response with every photo value marked user_confirmed, except ``skip`` paths."""
    body = copy.deepcopy(body)
    for path, value in photo_values(body):
        if path not in skip:
            value["certainty"] = Certainty.USER_CONFIRMED.value
    return body


# --- Round trips ---------------------------------------------------------------------


def test_confirmed_nutrition_only_photo_is_scaled_and_explained():
    client = make_client()
    read = ok_body(post_photo(client))
    assert read["package_nutrition"]["status"] == "not_calculated"

    body = ok_body(confirm(client, confirmed(read)))

    assert body["result"] == "nutrition_only"
    assert body["product"]["barcode"] is None
    assert body["package_nutrition"]["status"] == "calculated"
    assert body["package_nutrition"]["servings"] == 7  # the label's servings per package
    assert body["package_nutrition"]["pending_confirmation"] == []
    sodium = explanation_row(body, "sodium")
    assert sodium["status"] == "verified"
    assert sodium["explanation_message"] is None
    assert body["product"]["nutrition"]["nutrients"]["sodium"]["certainty"] == "user_confirmed"


def test_unconfirmed_values_stay_unused():
    client = make_client()
    read = ok_body(post_photo(client))

    body = ok_body(confirm(client, confirmed(read, skip={"nutrition.nutrients.sodium"})))

    assert explanation_row(body, "sodium")["status"] == "needs_confirmation"
    assert "nutrition.nutrients.sodium" in body["package_nutrition"]["pending_confirmation"]
    assert explanation_row(body, "calories")["status"] == "verified"


def test_unconfirmed_servings_per_package_blocks_the_whole_package():
    client = make_client()
    read = ok_body(post_photo(client))

    body = ok_body(confirm(client, confirmed(read, skip={"package"})))

    assert body["package_nutrition"]["status"] == "not_calculated"
    assert body["package_nutrition"]["reason"] == "unconfirmed_photo_values"


def test_user_correction_is_used():
    client = make_client()
    read = confirmed(ok_body(post_photo(client)))
    read["product"]["nutrition"]["nutrients"]["sodium"]["amount"] = 999
    read["product"]["package"]["servings_per_package"] = 2

    body = ok_body(confirm(client, read))

    assert body["product"]["nutrition"]["nutrients"]["sodium"]["amount"] == 999
    assert body["package_nutrition"]["servings"] == 2
    sodium = next(r for r in body["package_nutrition"]["rows"] if r["name"] == "sodium")
    assert sodium["whole_package"]["amount"] == 999 * 2


def test_confirmed_photo_values_are_merged_into_the_database_product():
    lookup = FakeLookup({BARCODE: database_product(nutrition=False)})
    client = make_client(lookup)
    read = ok_body(post_photo(client, barcode=BARCODE))

    body = ok_body(confirm(client, confirmed(read)))

    assert lookup.calls == [BARCODE, BARCODE]
    assert body["result"] == "product"
    assert body["product"]["name"] == "Example Crackers"
    assert body["ingredients"]["status"] == "analyzed"
    assert body["package_nutrition"]["status"] == "calculated"


def test_extra_analysis_sections_in_the_request_are_ignored():
    client = make_client()
    read = confirmed(ok_body(post_photo(client)))
    read["package_nutrition"] = {"status": "calculated", "servings": 1000}

    body = ok_body(confirm(client, read))

    assert body["package_nutrition"]["servings"] == 7


# --- Database values come from the server ---------------------------------------------


def test_database_values_in_the_request_are_ignored():
    database = database_product()
    client = make_client(FakeLookup({BARCODE: database}))
    read = ok_body(client.get(f"/api/analysis/{BARCODE}"))
    tampered = copy.deepcopy(read)
    tampered["product"]["name"] = "Something else"
    tampered["product"]["nutrition"]["nutrients"]["sodium"]["amount"] = 1
    tampered["product"]["serving"]["certainty"] = "user_confirmed"

    body = ok_body(confirm(client, tampered))

    assert body["product"]["name"] == "Example Crackers"
    assert body["product"]["nutrition"]["nutrients"]["sodium"]["amount"] == 2.0
    assert body["product"]["serving"]["certainty"] == "reported"


def test_a_photo_value_cannot_replace_a_database_value():
    client = make_client(FakeLookup({BARCODE: database_product()}))
    read = ok_body(client.get(f"/api/analysis/{BARCODE}"))
    read["product"]["nutrition"]["nutrients"]["sodium"].update(
        source="nutrition_label_photo", certainty="user_confirmed", amount=1
    )

    assert_error(confirm(client, read), 400, "invalid_confirmation")


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (None, 404, "product_not_found"),
        (ProductLookupError(ErrorCode.UPSTREAM_TIMEOUT, "Timed out."), 504, "upstream_timeout"),
        (ProductLookupError(ErrorCode.UPSTREAM_UNAVAILABLE, "Down."), 502, "upstream_unavailable"),
    ],
)
def test_lookup_errors_are_returned(error, status, code):
    lookup = FakeLookup({BARCODE: database_product(nutrition=False)})
    client = make_client(lookup)
    read = confirmed(ok_body(post_photo(client, barcode=BARCODE)))
    lookup.answers = {} if error is None else {BARCODE: error}

    assert_error(confirm(client, read), status, code)


# --- Bad requests ---------------------------------------------------------------------


@pytest.fixture
def read_body():
    return confirmed(ok_body(post_photo(make_client())))


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b.update(result="something"),
        lambda b: b.update(product="not an object"),
        lambda b: b["product"]["nutrition"]["nutrients"]["sodium"].update(certainty="confident"),
        lambda b: b["product"]["nutrition"]["nutrients"]["sodium"].update(certainty="reported"),
        lambda b: b["product"]["serving"].update(certainty=None),
        lambda b: b["product"]["nutrition"]["nutrients"]["sodium"].update(amount=-1),
        lambda b: b["product"]["nutrition"]["nutrients"]["sodium"].update(amount="ten"),
        lambda b: b["product"]["nutrition"]["nutrients"]["sodium"].update(unit="g"),
        lambda b: b["product"]["package"].update(servings_per_package=0),
        lambda b: b["product"]["nutrition"]["nutrients"].update(
            potassium={
                "amount": 1,
                "unit": "mg",
                "source": "nutrition_label_photo",
                "certainty": "user_confirmed",
                "daily_value_percent": None,
            }
        ),
    ],
)
def test_invalid_values_are_rejected(read_body, change):
    change(read_body)
    assert_error(confirm(make_client(), read_body), 400, "invalid_confirmation")


def test_body_must_be_json():
    response = make_client().post("/api/analysis/confirm", data="hello")
    assert_error(response, 400, "invalid_confirmation")


@pytest.mark.parametrize("barcode", [None, "12", 123])
def test_product_result_needs_a_valid_barcode(barcode):
    lookup = FakeLookup({BARCODE: database_product(nutrition=False)})
    client = make_client(lookup)
    read = confirmed(ok_body(post_photo(client, barcode=BARCODE)))
    read["product"]["barcode"] = barcode

    assert_error(confirm(client, read), 400, "invalid_barcode")


def test_a_nutrition_only_result_never_claims_a_product(read_body):
    read_body["product"]["barcode"] = BARCODE
    read_body["product"]["name"] = "Claimed name"

    body = ok_body(confirm(make_client(), read_body))

    assert body["product"]["barcode"] is None
    assert body["product"]["name"] is None


# --- Service ---------------------------------------------------------------------------


def test_photo_nutrients_need_a_photo_serving_when_the_database_is_per_100g():
    database = database_product()
    per_100 = Product(
        source=database.product.source,
        barcode=BARCODE,
        name="Example",
        nutrition=Nutrition(
            NutritionBasis.PER_100G,
            {"sodium": NutrientValue(100, "mg", Source.OPEN_FOOD_FACTS, Certainty.REPORTED)},
        ),
    )
    photo = PhotoValues(
        None,
        None,
        {"fibre": NutrientValue(2, "g", PHOTO, Certainty.USER_CONFIRMED)},
    )
    with pytest.raises(ConfirmationError, match="photo serving"):
        rebuild_product(ProductResult(ResultType.PRODUCT, per_100), photo)


def test_photo_package_does_not_replace_a_database_servings_per_package():
    database = database_product()
    database = ProductResult(
        ResultType.PRODUCT,
        Product(
            source=database.product.source,
            barcode=BARCODE,
            serving=database.product.serving,
            package=Package(None, None, None, 10, Source.OPEN_FOOD_FACTS),
            nutrition=database.product.nutrition,
        ),
    )
    photo = PhotoValues(
        None, Package(servings_per_package=3, source=PHOTO, certainty=Certainty.USER_CONFIRMED), {}
    )
    assert rebuild_product(database, photo).product.package.servings_per_package == 10


def test_parse_reads_only_photo_values():
    body = database_product().to_dict()["product"]
    assert parse_photo_values(body) == PhotoValues(None, None, {})


def test_parsed_photo_serving_keeps_its_text():
    product = {
        "serving": {
            "size_text": "6 crackers (30 g)",
            "quantity": 30,
            "unit": "g",
            "source": "nutrition_label_photo",
            "certainty": "user_confirmed",
        }
    }
    serving = parse_photo_values(product).serving
    assert serving == Serving("6 crackers (30 g)", 30, "g", PHOTO, Certainty.USER_CONFIRMED)


def test_the_client_request_matches_the_documented_schema():
    read = confirmed(ok_body(post_photo(make_client())))
    request = {"result": read["result"], "product": read["product"]}
    schema = {"$ref": "#/components/schemas/ConfirmationRequest", "components": SPEC["components"]}
    Draft202012Validator(schema).validate(request)
