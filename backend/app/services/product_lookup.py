"""Barcode -> ``ProductResult``: validate, check the cache, ask Open Food Facts, normalize."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from app.models.product import ErrorCode, ProductResult, ResultType, is_valid_barcode
from app.services.cache import TTLCache
from app.services.errors import ProductLookupError
from app.services.normalize import has_no_data, normalize_off_product


class ProductSource(Protocol):
    def fetch_product(self, barcode: str) -> dict[str, Any] | None: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductLookupService:
    def __init__(
        self,
        client: ProductSource,
        cache: TTLCache[ProductResult],
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._client = client
        self._cache = cache
        self._clock = clock

    def lookup(self, barcode: str) -> ProductResult:
        """Return the product, or raise ``ProductLookupError`` with the contract's error code.

        Only found products are cached. A failure or a "not found" is asked again next
        time, since the database may recover or gain the product.
        """
        if not is_valid_barcode(barcode):
            raise ProductLookupError(ErrorCode.INVALID_BARCODE, "Barcode must be 8 to 14 digits.")

        cached = self._cache.get(barcode)
        if cached is not None:
            return cached

        raw = self._client.fetch_product(barcode)
        if raw is None:
            raise self._not_found(barcode)
        product = normalize_off_product(raw, barcode, self._clock())
        if has_no_data(product):
            raise self._not_found(barcode)

        result = ProductResult(ResultType.PRODUCT, product)
        self._cache.set(barcode, result)
        return result

    @staticmethod
    def _not_found(barcode: str) -> ProductLookupError:
        return ProductLookupError(
            ErrorCode.PRODUCT_NOT_FOUND, f"No product found for barcode {barcode}."
        )
