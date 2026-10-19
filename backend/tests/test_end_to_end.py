"""End-to-end tests (#44): barcode → lookup → analysis → response, through the real app.

The app is built by ``create_app`` exactly as in production. Only the two outside
services are replaced, at the HTTP level, by recorded replies:

- Open Food Facts: real v3 responses in ``tests/fixtures/off/``;
- Gemini: real replies to the team's label photos in ``tests/fixtures/e2e/``,
  recorded with ``scripts/record_gemini_reply.py``.

Everything in between is the production code: barcode check, OFF client,
normalizer, cache, completeness, routing (#15), photo reading (#42), merging,
whole-package nutrition (#36), %DV and explanations from the reviewed nutrient
content (#37, #38), the ingredient knowledge base as shipped in
``content/`` (#33-#35) and the pipeline (#43). Unit tests replace those parts
with fakes; these tests show they fit together.

A request with no recorded reply fails the test, so CI never calls an external API.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import responses

from app import create_app
from app.services.label_extraction import DEFAULT_BASE_URL, DEFAULT_MODEL
from app.services.label_reading import DEFAULT_FALLBACK_MODELS, parse_models
from tests.conftest import load_off
from tests.test_analysis import VALIDATOR

RECORDED = Path(__file__).parent / "fixtures" / "e2e"
PHOTOS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "nutrition_labels" / "images"

OFF_PRODUCT = "https://world.openfoodfacts.org/api/v3/product/"
# Production model order: VISION_MODEL, then the fallbacks (#42).
MODELS = (DEFAULT_MODEL, *parse_models(DEFAULT_FALLBACK_MODELS, DEFAULT_MODEL))
OVERLOADED = {
    "error": {
        "code": 503,
        "message": "This model is currently experiencing high demand.",
        "status": "UNAVAILABLE",
    }
}

# Barcodes of the recorded products.
KETCHUP = "0013000006408"  # complete in OFF
OYSTER_SAUCE = "4891130005418"  # per-100 g data only: photo 010 is its label
KETCHUP_ZERO = "0057000002916"  # no saturated fat or fibre: photo 008 is its label
UNKNOWN = "0620009999909"  # valid check digit, not in OFF

# What the user reads (F2, F3, F4). The results page also shows "Not available"
# for a whole_package_status of not_available.
NOT_CALCULATED = (
    "Whole-package nutrition could not be calculated from the available serving and "
    "package information."
)
NOT_AVAILABLE = "Not available"
NO_EXPLANATION = "No verified explanation available yet."
CONFIRM_FIRST = "Confirm this value from the photo before it is explained."
PER_100_G_NOTE = (
    "These amounts are per 100 g, not per serving. %DV is only given per serving, so none is shown."
)
NO_INGREDIENTS = "Ingredient information not available"
NONE_FLAGGED = "No flagged ingredients found among the ingredients checked."
COVERAGE = re.compile(
    r"^Checked (\d+) of (\d+) ingredients against our reviewed ingredient database\.$"
)
NUTRIENTS = {
    "calories",
    "total_fat",
    "saturated_fat",
    "trans_fat",
    "carbohydrate",
    "fibre",
    "sugars",
    "protein",
    "cholesterol",
    "sodium",
}


class Services:
    """Recorded replies of Open Food Facts and Gemini, registered per test."""

    def __init__(self, mock: responses.RequestsMock) -> None:
        self._mock = mock

    def product(self, barcode: str, fixture: str) -> None:
        body = load_off(fixture)
        status = 404 if body["result"]["id"] == "product_not_found" else 200
        self._mock.get(OFF_PRODUCT + barcode, json=body, status=status)

    def database_down(self, barcode: str) -> None:
        # OFF answers an HTML page when overloaded.
        self._mock.get(
            OFF_PRODUCT + barcode,
            status=503,
            body="<html><body>Service Unavailable</body></html>",
            content_type="text/html",
        )

    def label(self, recording: str) -> None:
        """Gemini's recorded reply to a photo, from the model that gave it.

        The models tried before it answer 503, as they did while recording.
        """
        recorded = json.loads((RECORDED / f"gemini_{recording}.json").read_text("utf-8"))
        for model in MODELS[: MODELS.index(recorded["model"])]:
            self.vision_down(model)
        self._mock.post(_generate_url(recorded["model"]), json=recorded["reply"])

    def vision_down(self, model: str) -> None:
        self._mock.post(_generate_url(model), status=503, json=OVERLOADED)

    def calls(self, prefix: str) -> list[str]:
        return [c.request.url for c in self._mock.calls if c.request.url.startswith(prefix)]


def _generate_url(model: str) -> str:
    return f"{DEFAULT_BASE_URL}/models/{model}:generateContent"


@pytest.fixture
def services(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "recorded-replies-only")
    for name in ("VISION_MODEL", "VISION_FALLBACK_MODELS", "OFF_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    with responses.RequestsMock() as mock:
        yield Services(mock)
        unrecorded = [c.request.url for c in mock.calls if isinstance(c.response, Exception)]
        assert not unrecorded, f"requests with no recorded reply: {unrecorded}"


@pytest.fixture
def client(services):
    return create_app({"TESTING": True}).test_client()


def analysis(response) -> dict:
    """A 200 analysis body, checked against the OpenAPI schema."""
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    VALIDATOR.validate(body)
    return body


def send_photo(client, photo: Path, barcode: str | None = None):
    data = {"image": (photo.open("rb"), photo.name)}
    if barcode is not None:
        data["barcode"] = barcode
    return client.post("/api/analysis/label-photo", data=data)


def rows(body: dict) -> dict[str, dict]:
    return {row["name"]: row for row in body["package_nutrition"]["rows"]}


def nutrient(body: dict, name: str) -> dict:
    return body["product"]["nutrition"]["nutrients"][name]


def explained(body: dict) -> dict[str, dict]:
    return {row["name"]: row for row in body["explanations"]["rows"]}


def assert_waits_for_confirmation(body: dict) -> None:
    """Q1: no photo value is read as "a little"/"a lot" or explained before it is confirmed."""
    for row in explained(body).values():
        assert (row["status"], row["status_text"]) == ("needs_confirmation", CONFIRM_FIRST)
        assert row["daily_value"] is None
        assert row["explanation_message"] == NO_EXPLANATION


def assert_no_ingredients(body: dict) -> None:
    ingredients = body["ingredients"]
    assert ingredients["status"] == "unavailable"
    assert ingredients["message"] == NO_INGREDIENTS
    assert ingredients["coverage_text"] is None


# --- Complete product (F1 path 1) ----------------------------------------------------


def test_complete_product_returns_nutrition_and_ingredients_without_a_photo(services, client):
    services.product(KETCHUP, "ketchup_found")

    body = analysis(client.get(f"/api/analysis/{KETCHUP}"))

    assert (body["result"], body["completeness"], body["missing_fields"]) == (
        "product",
        "complete",
        [],
    )
    assert (body["product"]["name"], body["product"]["brand"]) == ("Tomato Ketchup", "Heinz")
    assert body["next_step"]["action"] == "use_database"

    # F2: per serving and for the whole 570 g bottle, labelled as approximate
    # because servings per package is derived from the package quantity.
    package = body["package_nutrition"]
    assert package["status"] == "calculated"
    assert package["per_serving_label"] == "Per serving (1 Tbsp (17 g))"
    assert package["whole_package_label"] == "Whole package (20 oz - 570g)"
    assert package["approximate_label"] == "Approximate"
    assert package["daily_value_label"] == "Calculated for whole package"
    assert package["display_servings"] == 33.4
    by_name = rows(body)
    assert set(by_name) == NUTRIENTS
    assert {row["whole_package_status"] for row in by_name.values()} == {"calculated"}
    assert by_name["calories"]["whole_package"]["display_amount"] == 550
    assert by_name["sodium"]["per_serving"]["amount"] == 122
    assert by_name["sodium"]["whole_package"]["display_amount"] == 4069
    assert by_name["sodium"]["whole_package"]["display_daily_value_percent"] == 177

    # F3: per-serving %DV calculated from Health Canada's Daily Values, read as
    # "a little" (5% or less), with the reviewed explanation and its sources.
    explanations = body["explanations"]
    assert explanations["basis_label"] == "per serving"
    by_name = explained(body)
    assert {row["status"] for row in by_name.values()} == {"verified"}
    sodium = by_name["sodium"]
    assert sodium["daily_value"]["display_percent"] == 5
    assert sodium["daily_value"]["label"] == "Calculated"
    assert sodium["daily_value"]["interpretation_text"] == "a little"
    assert sodium["what_it_is"]["sources"] and sodium["how_to_read"]["sources"]
    assert sodium["explanation_message"] is None
    assert by_name["calories"]["daily_value"] is None  # no %DV is invented

    # F4: reviewed entries matched, coverage stated, nothing flagged.
    ingredients = body["ingredients"]
    assert ingredients["status"] == "analyzed"
    assert ingredients["message"] == NONE_FLAGGED
    assert ingredients["flagged_ids"] == []
    assert {"sugar", "salt"} <= {m["ingredient"]["id"] for m in ingredients["matched"]}
    checked, total = COVERAGE.match(ingredients["coverage_text"]).groups()
    assert (int(checked), int(total)) == (ingredients["checked_count"], 9)

    assert services.calls(DEFAULT_BASE_URL) == []


# --- Incomplete product, then a label photo (F1 path 2) ------------------------------


def test_incomplete_product_asks_for_a_photo_and_uses_its_label(services, client):
    services.product(OYSTER_SAUCE, "oyster_sauce_no_serving")
    # The recorded reply has a carbohydrate %DV of 0 that the label does not print.
    # Keep it: these tests check the flow; the Q1 benchmark (#17) checks accuracy.
    services.label("010_dark-sauce")

    scanned = analysis(client.get(f"/api/analysis/{OYSTER_SAUCE}"))

    # OFF has per-100 g values only, so nothing per serving can be shown.
    assert scanned["completeness"] == "incomplete"
    assert scanned["next_step"]["action"] == "request_nutrition_photo"
    assert scanned["next_step"]["photo_fields"] == ["serving.size_text", "nutrition.basis"]
    package = scanned["package_nutrition"]
    assert (package["status"], package["message"]) == ("not_calculated", NOT_CALCULATED)
    assert {row["whole_package_status"] for row in package["rows"]} == {"not_available"}
    # F3: per-100 g amounts are explained but never given a %DV.
    assert scanned["explanations"]["basis_note"] == PER_100_G_NOTE
    by_name = explained(scanned)
    assert {row["daily_value"] is None for row in by_name.values()} == {True}
    assert by_name["sodium"]["status"] == "verified"
    assert by_name["sodium"]["how_to_read"] is not None
    for missing in ("trans_fat", "cholesterol"):
        assert by_name[missing]["status_text"] == NOT_AVAILABLE
        assert by_name[missing]["explanation_message"] == NO_EXPLANATION
    assert_no_ingredients(scanned)

    photographed = analysis(send_photo(client, PHOTOS / "010_dark-sauce.jpg", OYSTER_SAUCE))

    # Same product, now with the label's per-serving values. Database identity
    # stays; the per-100 g values are replaced, never mixed with the label's.
    assert photographed["result"] == "product"
    assert (photographed["product"]["barcode"], photographed["product"]["name"]) == (
        OYSTER_SAUCE,
        "Premium Oyster Sauce",
    )
    assert photographed["next_step"] is None
    assert photographed["product"]["serving"]["size_text"] == "1 tbsp (15 ml)"
    sodium = nutrient(photographed, "sodium")
    assert (sodium["amount"], sodium["unit"], sodium["daily_value_percent"]) == (780, "mg", 34)
    nutrients = photographed["product"]["nutrition"]["nutrients"].values()
    assert {(v["source"], v["certainty"]) for v in nutrients} == {
        ("nutrition_label_photo", "uncertain")
    }

    # Q1: photo values are shown per serving but not scaled until the user confirms them.
    package = photographed["package_nutrition"]
    assert package["per_serving_label"] == "Per serving (1 tbsp (15 ml))"
    assert set(package["pending_confirmation"]) == {f"nutrition.nutrients.{n}" for n in NUTRIENTS}
    assert rows(photographed)["sodium"]["per_serving"]["amount"] == 780
    assert (package["status"], package["message"]) == ("not_calculated", NOT_CALCULATED)
    assert_waits_for_confirmation(photographed)
    assert_no_ingredients(photographed)

    # The product was looked up once (cached for the photo step), and the label
    # read once, on the fallback model after the default one answered 503.
    assert len(services.calls(OFF_PRODUCT)) == 1
    assert [url.split("/models/")[1] for url in services.calls(DEFAULT_BASE_URL)] == [
        f"{MODELS[0]}:generateContent",
        f"{MODELS[1]}:generateContent",
    ]


def test_photo_on_the_same_serving_basis_only_fills_gaps(services, client):
    # Ketchup Zero's label uses the simplified format and does not print saturated
    # fat or fibre, so the photo cannot fill the two values OFF is missing.
    services.product(KETCHUP_ZERO, "ketchup_zero_upc_a")
    services.label("008_ketchup")

    scanned = analysis(client.get(f"/api/analysis/{KETCHUP_ZERO}"))
    assert scanned["next_step"]["photo_fields"] == [
        "nutrition.nutrients.saturated_fat",
        "nutrition.nutrients.fibre",
    ]

    photographed = analysis(send_photo(client, PHOTOS / "008_ketchup.jpg", KETCHUP_ZERO))

    assert photographed["product"]["name"] == "Ketchup Zero"
    assert photographed["missing_fields"] == scanned["missing_fields"]
    assert photographed["product"]["nutrition"] == scanned["product"]["nutrition"]
    assert photographed["product"]["serving"]["source"] == "open_food_facts"
    assert photographed["package_nutrition"]["pending_confirmation"] == []
    by_name = explained(photographed)
    for missing in ("saturated_fat", "fibre"):
        assert (by_name[missing]["status"], by_name[missing]["status_text"]) == (
            "not_available",
            NOT_AVAILABLE,
        )
    assert by_name["sodium"]["status"] == "verified"


# --- Barcode not found, then a label photo (F1 path 3) -------------------------------


def test_unknown_barcode_gives_a_nutrition_only_result_from_the_photo(services, client):
    services.product(UNKNOWN, "not_found_valid_code")
    services.label("005_crackers")

    not_found = client.get(f"/api/analysis/{UNKNOWN}")

    assert not_found.status_code == 404
    assert not_found.get_json()["error"]["code"] == "product_not_found"

    body = analysis(send_photo(client, PHOTOS / "005_crackers.jpg"))

    # Never claims the product was identified (F1).
    assert body["result"] == "nutrition_only"
    product = body["product"]
    assert [product[key] for key in ("barcode", "name", "brand", "ingredients_text")] == [None] * 4
    assert product["source"]["provider"] == "nutrition_label_photo"
    assert product["serving"]["size_text"] == "6 crackers (20 g)"
    assert nutrient(body, "sodium")["amount"] == 160
    assert nutrient(body, "saturated_fat")["daily_value_percent"] == 8
    assert body["next_step"] is None
    assert body["package_nutrition"]["per_serving_label"] == "Per serving (6 crackers (20 g))"
    assert len(body["package_nutrition"]["pending_confirmation"]) == len(NUTRIENTS)
    assert_waits_for_confirmation(body)
    assert_no_ingredients(body)


def test_photo_with_an_unknown_barcode_is_still_nutrition_only(services, client):
    services.product(UNKNOWN, "not_found_valid_code")
    services.label("005_crackers")

    body = analysis(send_photo(client, PHOTOS / "005_crackers.jpg", UNKNOWN))

    assert body["result"] == "nutrition_only"
    assert body["product"]["barcode"] is None


# --- When an outside service fails ---------------------------------------------------


def test_database_outage_is_not_reported_as_not_found_and_the_photo_still_works(services, client):
    services.database_down(OYSTER_SAUCE)
    services.label("010_dark-sauce")

    lookup = client.get(f"/api/analysis/{OYSTER_SAUCE}")

    assert lookup.status_code == 502
    assert lookup.get_json()["error"]["code"] == "upstream_unavailable"

    body = analysis(send_photo(client, PHOTOS / "010_dark-sauce.jpg", OYSTER_SAUCE))

    assert body["result"] == "nutrition_only"
    assert nutrient(body, "sodium")["amount"] == 780


def test_vision_outage_on_every_model_fails_the_photo_but_not_the_product(services, client):
    services.product(OYSTER_SAUCE, "oyster_sauce_no_serving")
    for model in MODELS:
        services.vision_down(model)

    photo = send_photo(client, PHOTOS / "010_dark-sauce.jpg", OYSTER_SAUCE)

    assert photo.status_code == 502
    assert photo.get_json()["error"] == {
        "code": "upstream_unavailable",
        "message": "The label-reading service is unavailable. Try again shortly.",
    }
    # The barcode result is unaffected and still offers the photo.
    body = analysis(client.get(f"/api/analysis/{OYSTER_SAUCE}"))
    assert body["next_step"]["action"] == "request_nutrition_photo"


def test_photo_without_a_nutrition_facts_table_asks_for_a_retake(services, client):
    services.label("no_table")

    response = send_photo(client, RECORDED / "no_table.png")

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "nutrition_table_not_found"
    assert services.calls(OFF_PRODUCT) == []
