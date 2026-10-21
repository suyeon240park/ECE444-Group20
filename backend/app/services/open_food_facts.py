"""Thin client for the Open Food Facts product API (v3).

Only HTTP and response-shape concerns live here. Turning the record into the
application's model is ``normalize.py``'s job.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests

from app.models.product import ErrorCode
from app.services.errors import ProductLookupError

logger = logging.getLogger(__name__)

# Ask OFF for only what the normalizer reads: smaller responses, and fewer
# surprises when OFF adds fields.
FIELDS = ",".join(
    [
        "code",
        "product_name",
        "product_name_en",
        "product_name_fr",
        "brands",
        "ingredients_text",
        "ingredients_text_en",
        "ingredients_text_fr",
        "serving_size",
        "serving_quantity",
        "serving_quantity_unit",
        "quantity",
        "product_quantity",
        "product_quantity_unit",
        "nutrition_data_per",
        "nutriments",
        "last_modified_t",
    ]
)

# OFF answers "success_with_warnings" for a found product whose code it had to
# normalize, e.g. a 12-digit UPC-A padded to 13 digits.
_SUCCESS_STATUSES = {"success", "success_with_warnings"}

_TIMEOUT_MESSAGE = "The product database did not respond in time."
_UNAVAILABLE_MESSAGE = "The product database is unavailable. Try again shortly."


def _unavailable() -> ProductLookupError:
    return ProductLookupError(ErrorCode.UPSTREAM_UNAVAILABLE, _UNAVAILABLE_MESSAGE)


def _json_object(response: requests.Response) -> dict[str, Any] | None:
    """The body as a JSON object, or None. OFF answers with an HTML page when overloaded."""
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


class OpenFoodFactsClient:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        timeout: float,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        # Applies to connecting and to each wait for data, not to the whole request.
        self._timeout = timeout
        self._session = session or requests.Session()

    def fetch_product(self, barcode: str) -> dict[str, Any] | None:
        """Return OFF's ``product`` object, or None when OFF has no such product.

        The barcode must already be validated. Raises ``ProductLookupError`` with
        ``upstream_timeout`` or ``upstream_unavailable`` when the answer is unknown.
        """
        url = f"{self._base_url}/api/v3/product/{quote(barcode, safe='')}"
        try:
            response = self._session.get(
                url,
                params={"fields": FIELDS},
                headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                timeout=self._timeout,
            )
        except requests.Timeout as exc:
            logger.warning("Open Food Facts timed out for %s", barcode)
            raise ProductLookupError(ErrorCode.UPSTREAM_TIMEOUT, _TIMEOUT_MESSAGE) from exc
        except requests.RequestException as exc:
            logger.warning("Open Food Facts request failed for %s: %s", barcode, exc)
            raise _unavailable() from exc

        body = _json_object(response)

        if response.status_code == 404 and body is not None:
            result = body.get("result")
            if isinstance(result, dict) and result.get("id") == "product_not_found":
                return None

        product = body.get("product") if body is not None else None
        usable = (
            response.status_code == 200
            and body is not None
            and body.get("status") in _SUCCESS_STATUSES
            and isinstance(product, dict)
        )
        if not usable:
            logger.warning(
                "Open Food Facts returned an unusable response for %s: HTTP %s",
                barcode,
                response.status_code,
            )
            raise _unavailable()
        return product
