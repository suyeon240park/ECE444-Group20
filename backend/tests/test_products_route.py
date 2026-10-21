import pytest
import responses

from app import create_app
from app.models.product import ErrorCode
from app.services.errors import ProductLookupError

TOP_LEVEL_KEYS = ["result", "completeness", "missing_fields", "product"]
PRODUCT_KEYS = [
    "barcode",
    "name",
    "brand",
    "ingredients_text",
    "serving",
    "package",
    "nutrition",
    "source",
]


class FakeService:
    def __init__(self, error=None):
        self.error = error

    def lookup(self, barcode):
        raise self.error


@pytest.fixture
def app():
    return create_app({"TESTING": True, "OFF_BASE_URL": "https://off.test"})


def off_url(barcode):
    return f"https://off.test/api/v3/product/{barcode}"


@responses.activate
def test_found_product_matches_the_contract(app, off_response):
    responses.get(off_url("0013000006408"), json=off_response("ketchup_found"))

    response = app.test_client().get("/api/products/0013000006408")

    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == set(TOP_LEVEL_KEYS)  # Flask sorts keys; order is not contract
    assert set(body["product"]) == set(PRODUCT_KEYS)
    assert body["result"] == "product"
    assert body["completeness"] == "complete"
    assert body["missing_fields"] == []
    assert body["product"]["nutrition"]["basis"] == "serving"
    assert body["product"]["nutrition"]["nutrients"]["sodium"]["amount"] == 122
    assert body["product"]["source"]["provider"] == "open_food_facts"


@responses.activate
def test_incomplete_product_lists_what_is_missing(app, off_response):
    responses.get(off_url("3017624010701"), json=off_response("nutella_found"))

    body = app.test_client().get("/api/products/3017624010701").get_json()

    assert body["completeness"] == "incomplete"
    assert body["missing_fields"] == [
        "serving.size_text",
        "nutrition.basis",
        "nutrition.nutrients.fibre",
    ]
    assert body["product"]["serving"]["size_text"] is None
    assert body["product"]["nutrition"]["nutrients"]["fibre"] is None


@responses.activate
def test_unknown_product_is_404(app, off_response):
    responses.get(off_url("0000000000001"), json=off_response("not_found"), status=404)

    response = app.test_client().get("/api/products/0000000000001")

    assert response.status_code == 404
    assert response.get_json() == {
        "error": {
            "code": "product_not_found",
            "message": "No product found for barcode 0000000000001.",
        }
    }


@responses.activate
def test_record_with_no_data_is_404(app, off_response):
    responses.get(off_url("4006381333931"), json=off_response("empty_record"))

    response = app.test_client().get("/api/products/4006381333931")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "product_not_found"


@pytest.mark.parametrize("barcode", ["abc", "1234567", "123456789012345", "3017624010701x"])
def test_malformed_barcode_is_400_without_calling_off(app, barcode):
    # No responses mock is active: any outbound request would fail the test.
    response = app.test_client().get(f"/api/products/{barcode}")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": {"code": "invalid_barcode", "message": "Barcode must be 8 to 14 digits."}
    }


@responses.activate
def test_off_outage_is_502(app):
    responses.get(off_url("3017624010701"), body="<html>busy</html>", status=503)

    response = app.test_client().get("/api/products/3017624010701")

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "upstream_unavailable"


@responses.activate
def test_off_timeout_is_504(app):
    import requests

    responses.get(off_url("3017624010701"), body=requests.ReadTimeout())

    response = app.test_client().get("/api/products/3017624010701")

    assert response.status_code == 504
    assert response.get_json()["error"]["code"] == "upstream_timeout"


@responses.activate
def test_repeat_lookups_are_served_from_the_cache(app, off_response):
    responses.get(off_url("0013000006408"), json=off_response("ketchup_found"))
    client = app.test_client()

    first = client.get("/api/products/0013000006408")
    second = client.get("/api/products/0013000006408")

    assert len(responses.calls) == 1
    assert second.get_json() == first.get_json()


@responses.activate
def test_cache_can_be_disabled_by_config(off_response):
    app = create_app(
        {"TESTING": True, "OFF_BASE_URL": "https://off.test", "PRODUCT_CACHE_TTL_SECONDS": 0}
    )
    responses.get(off_url("0013000006408"), json=off_response("ketchup_found"))
    client = app.test_client()

    client.get("/api/products/0013000006408")
    client.get("/api/products/0013000006408")

    assert len(responses.calls) == 2


@responses.activate
def test_configured_user_agent_is_sent(off_response):
    app = create_app(
        {
            "TESTING": True,
            "OFF_BASE_URL": "https://off.test",
            "OFF_USER_AGENT": "Custom/9 (team@example.com)",
        }
    )
    responses.get(off_url("0013000006408"), json=off_response("ketchup_found"))

    app.test_client().get("/api/products/0013000006408")

    assert responses.calls[0].request.headers["User-Agent"] == "Custom/9 (team@example.com)"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ErrorCode.INVALID_BARCODE, 400),
        (ErrorCode.PRODUCT_NOT_FOUND, 404),
        (ErrorCode.UPSTREAM_UNAVAILABLE, 502),
        (ErrorCode.UPSTREAM_TIMEOUT, 504),
    ],
)
def test_every_error_code_maps_to_its_documented_status(app, code, status):
    app.extensions["product_lookup"] = FakeService(ProductLookupError(code, "boom"))

    response = app.test_client().get("/api/products/3017624010701")

    assert response.status_code == status
    assert response.get_json() == {"error": {"code": code.value, "message": "boom"}}


def test_cors_headers_are_present_on_product_responses(app):
    response = app.test_client().get(
        "/api/products/abc", headers={"Origin": "http://localhost:8081"}
    )

    assert response.headers.get("Access-Control-Allow-Origin") in ("*", "http://localhost:8081")


@responses.activate
def test_12_digit_upc_a_returns_the_product(app, off_response):
    # Phone scanners report North American barcodes as 12 digits. This used to answer 502.
    responses.get(off_url("0057000002916"), json=off_response("ketchup_zero_upc_a"))

    response = app.test_client().get("/api/products/057000002916")

    assert response.status_code == 200
    assert response.get_json()["product"]["barcode"] == "0057000002916"
    assert responses.calls[0].request.url.startswith(off_url("0057000002916") + "?")
