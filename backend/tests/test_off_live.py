"""Calls the real Open Food Facts API. Skipped by default and in CI.

Run with ``pytest -m live --no-cov`` from backend/. Open Food Facts limits product reads to
15 per minute per IP and is edited by the public, so these tests make few requests and
assert only what does not depend on one product's current data.
"""

import pytest

from app import create_app
from app.models.product import Completeness

pytestmark = pytest.mark.live

# Set a real contact in OFF_USER_AGENT when running this against production regularly.
USER_AGENT = "WhatsInMyFood-tests/0.1 (ECE444 student project)"


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True, "OFF_USER_AGENT": USER_AGENT}).test_client()


def test_known_product_is_returned_in_the_contract_shape(client):
    response = client.get("/api/products/3017624010701")

    assert response.status_code == 200
    body = response.get_json()
    assert body["product"]["barcode"] == "3017624010701"
    assert body["product"]["name"]
    assert body["completeness"] in {c.value for c in Completeness}
    assert body["product"]["source"]["provider"] == "open_food_facts"
    assert set(body["product"]["nutrition"]["nutrients"]) >= {"calories", "sodium", "fibre"}


def test_unknown_barcode_is_404(client):
    response = client.get("/api/products/0000000000001")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "product_not_found"
