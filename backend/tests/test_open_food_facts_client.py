import pytest
import requests
import responses

from app.models.product import ErrorCode
from app.services.errors import ProductLookupError
from app.services.open_food_facts import FIELDS, OpenFoodFactsClient

BASE = "https://off.test"
UA = "TestApp/1.0 (test@example.com)"
BARCODE = "3017624010701"
URL = f"{BASE}/api/v3/product/{BARCODE}"

HTML_503 = "<!DOCTYPE html><html><body><h1>Page temporarily unavailable</h1></body></html>"


@pytest.fixture
def client():
    return OpenFoodFactsClient(BASE, UA, timeout=5)


def error_code(excinfo) -> ErrorCode:
    return excinfo.value.code


@responses.activate
def test_returns_the_product_object(client, off_response):
    body = off_response("nutella_found")
    responses.get(URL, json=body)

    assert client.fetch_product(BARCODE) == body["product"]


@responses.activate
def test_sends_user_agent_fields_and_uses_v3(client, off_response):
    responses.get(URL, json=off_response("nutella_found"))

    client.fetch_product(BARCODE)

    request = responses.calls[0].request
    assert request.headers["User-Agent"] == UA
    assert request.headers["Accept"] == "application/json"
    assert request.params == {"fields": FIELDS}
    assert request.url.startswith(f"{BASE}/api/v3/product/{BARCODE}?")


@responses.activate
def test_trailing_slash_in_base_url_is_ignored(off_response):
    responses.get(URL, json=off_response("nutella_found"))

    assert OpenFoodFactsClient(BASE + "/", UA, 5).fetch_product(BARCODE) is not None


@responses.activate
def test_unknown_barcode_returns_none(client, off_response):
    responses.get(URL, json=off_response("not_found"), status=404)

    assert client.fetch_product(BARCODE) is None


@responses.activate
def test_barcode_is_url_encoded(client):
    # Callers validate first, but the client must not let a path escape if they do not.
    responses.get(f"{BASE}/api/v3/product/1%2F..%2Fx", json={"status": "failure"}, status=500)

    with pytest.raises(ProductLookupError):
        client.fetch_product("1/../x")


@pytest.mark.parametrize(
    ("status", "kwargs"),
    [
        (404, {"body": HTML_503, "content_type": "text/html"}),
        (404, {"json": {"result": {"id": "something_else"}}}),
        (404, {"json": {"result": "product_not_found"}}),
        (404, {"json": ["product_not_found"]}),
        (200, {"body": HTML_503, "content_type": "text/html"}),
        (200, {"json": ["not", "an", "object"]}),
        (200, {"json": {"status": "failure", "product": {"code": BARCODE}}}),
        (200, {"json": {"status": "success"}}),
        (200, {"json": {"status": "success", "product": "nope"}}),
        (400, {"json": {"status": "failure"}}),
        (429, {"body": "slow down"}),
        (500, {"json": {"status": "failure"}}),
        (503, {"body": HTML_503, "content_type": "text/html"}),
    ],
)
@responses.activate
def test_unusable_responses_are_reported_as_unavailable(client, status, kwargs):
    responses.get(URL, status=status, **kwargs)

    with pytest.raises(ProductLookupError) as excinfo:
        client.fetch_product(BARCODE)

    assert error_code(excinfo) is ErrorCode.UPSTREAM_UNAVAILABLE


@pytest.mark.parametrize("timeout_error", [requests.ReadTimeout, requests.ConnectTimeout])
@responses.activate
def test_timeouts_are_reported_as_timeouts(client, timeout_error):
    responses.get(URL, body=timeout_error("too slow"))

    with pytest.raises(ProductLookupError) as excinfo:
        client.fetch_product(BARCODE)

    assert error_code(excinfo) is ErrorCode.UPSTREAM_TIMEOUT


@pytest.mark.parametrize("failure", [requests.ConnectionError, requests.exceptions.SSLError])
@responses.activate
def test_network_failures_are_reported_as_unavailable(client, failure):
    responses.get(URL, body=failure("network down"))

    with pytest.raises(ProductLookupError) as excinfo:
        client.fetch_product(BARCODE)

    assert error_code(excinfo) is ErrorCode.UPSTREAM_UNAVAILABLE


def test_timeout_is_passed_to_requests():
    seen = {}

    class FakeSession:
        def get(self, url, **kwargs):
            seen.update(kwargs)
            raise requests.Timeout

    with pytest.raises(ProductLookupError):
        OpenFoodFactsClient(BASE, UA, timeout=2.5, session=FakeSession()).fetch_product(BARCODE)

    assert seen["timeout"] == 2.5


@responses.activate
def test_found_with_warnings_is_a_found_product(client, off_response):
    # Real OFF answer for the 12-digit UPC-A 057000002916: it pads the code and replies
    # "success_with_warnings". This used to be reported as an outage (502).
    body = off_response("ketchup_zero_upc_a")
    responses.get(f"{BASE}/api/v3/product/057000002916", json=body)

    product = client.fetch_product("057000002916")

    assert body["status"] == "success_with_warnings"
    assert product == body["product"]
    assert product["code"] == "0057000002916"


@responses.activate
def test_unrecognized_status_is_still_unavailable(client, off_response):
    body = off_response("nutella_found") | {"status": "something_new"}
    responses.get(URL, json=body)

    with pytest.raises(ProductLookupError) as excinfo:
        client.fetch_product(BARCODE)
    assert error_code(excinfo) is ErrorCode.UPSTREAM_UNAVAILABLE
