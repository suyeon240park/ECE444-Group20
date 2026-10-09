from datetime import datetime, timezone

import pytest

from app.models.product import Completeness, ErrorCode, ResultType
from app.services.cache import TTLCache
from app.services.errors import ProductLookupError
from app.services.product_lookup import ProductLookupService, to_ean13

NOW = datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc)
KETCHUP = "0013000006408"


class FakeClient:
    """Answers from a dict of barcode -> product / None / exception, and counts calls."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def fetch_product(self, barcode):
        self.calls.append(barcode)
        answer = self.answers[barcode]
        if isinstance(answer, Exception):
            raise answer
        return answer


def service(client, ttl=60):
    return ProductLookupService(client, TTLCache(ttl), clock=lambda: NOW)


def error_of(svc, barcode) -> ProductLookupError:
    with pytest.raises(ProductLookupError) as excinfo:
        svc.lookup(barcode)
    return excinfo.value


def test_found_product_is_normalized(off_product):
    result = service(FakeClient({KETCHUP: off_product("ketchup_found")})).lookup(KETCHUP)

    assert result.result is ResultType.PRODUCT
    assert result.completeness is Completeness.COMPLETE
    assert result.product.name == "Tomato Ketchup"
    assert result.product.source.retrieved_at == NOW


def test_incomplete_product_is_still_a_result(off_product):
    result = service(FakeClient({"3017624010701": off_product("nutella_found")})).lookup(
        "3017624010701"
    )

    assert result.completeness is Completeness.INCOMPLETE
    assert "nutrition.nutrients.fibre" in result.missing_fields


@pytest.mark.parametrize(
    "barcode", ["", "abc", "1234567", "123456789012345", "3017624010701\n", "٣٠١٧٦٢٤٠١٠٧٠١"]
)
def test_invalid_barcode_never_reaches_the_client(barcode):
    client = FakeClient({})

    assert error_of(service(client), barcode).code is ErrorCode.INVALID_BARCODE
    assert client.calls == []


def test_unknown_product_is_not_found():
    error = error_of(service(FakeClient({KETCHUP: None})), KETCHUP)

    assert error.code is ErrorCode.PRODUCT_NOT_FOUND
    assert error.message == f"No product found for barcode {KETCHUP}."


def test_record_with_no_data_is_not_found(off_product):
    client = FakeClient({"4006381333931": off_product("empty_record")})

    assert error_of(service(client), "4006381333931").code is ErrorCode.PRODUCT_NOT_FOUND


def test_upstream_errors_propagate():
    failure = ProductLookupError(ErrorCode.UPSTREAM_TIMEOUT, "slow")

    assert error_of(service(FakeClient({KETCHUP: failure})), KETCHUP) is failure


def test_found_products_are_cached(off_product):
    client = FakeClient({KETCHUP: off_product("ketchup_found")})
    svc = service(client)

    first = svc.lookup(KETCHUP)
    second = svc.lookup(KETCHUP)

    assert client.calls == [KETCHUP]
    assert second is first


def test_disabled_cache_asks_every_time(off_product):
    client = FakeClient({KETCHUP: off_product("ketchup_found")})
    svc = service(client, ttl=0)

    svc.lookup(KETCHUP)
    svc.lookup(KETCHUP)

    assert client.calls == [KETCHUP, KETCHUP]


def test_not_found_is_not_cached():
    client = FakeClient({KETCHUP: None})
    svc = service(client)

    error_of(svc, KETCHUP)
    error_of(svc, KETCHUP)

    assert client.calls == [KETCHUP, KETCHUP]


def test_failures_are_not_cached_and_recovery_works(off_product):
    client = FakeClient({KETCHUP: ProductLookupError(ErrorCode.UPSTREAM_UNAVAILABLE, "down")})
    svc = service(client)

    assert error_of(svc, KETCHUP).code is ErrorCode.UPSTREAM_UNAVAILABLE
    client.answers[KETCHUP] = off_product("ketchup_found")

    assert svc.lookup(KETCHUP).product.name == "Tomato Ketchup"


def test_default_clock_is_timezone_aware(off_product):
    svc = ProductLookupService(FakeClient({KETCHUP: off_product("ketchup_found")}), TTLCache(0))

    assert svc.lookup(KETCHUP).product.source.retrieved_at.tzinfo is not None


KETCHUP_ZERO_UPC_A = "057000002916"
KETCHUP_ZERO_EAN_13 = "0057000002916"


@pytest.mark.parametrize(
    ("barcode", "expected"),
    [
        ("057000002916", "0057000002916"),  # UPC-A gets its leading zero
        ("0057000002916", "0057000002916"),  # EAN-13 unchanged
        ("12345670", "12345670"),  # EAN-8 unchanged
        ("10057000002913", "10057000002913"),  # GTIN-14 unchanged
    ],
)
def test_to_ean13(barcode, expected):
    assert to_ean13(barcode) == expected


def test_upc_a_is_looked_up_as_ean_13(off_product):
    client = FakeClient({KETCHUP_ZERO_EAN_13: off_product("ketchup_zero_upc_a")})

    result = service(client).lookup(KETCHUP_ZERO_UPC_A)

    assert client.calls == [KETCHUP_ZERO_EAN_13]
    assert result.product.barcode == KETCHUP_ZERO_EAN_13


def test_upc_a_and_ean_13_share_one_cache_entry(off_product):
    client = FakeClient({KETCHUP_ZERO_EAN_13: off_product("ketchup_zero_upc_a")})
    svc = service(client)

    first = svc.lookup(KETCHUP_ZERO_UPC_A)
    second = svc.lookup(KETCHUP_ZERO_EAN_13)

    assert second is first
    assert client.calls == [KETCHUP_ZERO_EAN_13]
