"""Decide whether database data is enough or a Nutrition Facts photo is needed (#15, F1).

Three paths, taken from the outcome of a barcode lookup (#14):

1. complete database result: use it, and do not ask for a photo;
2. product identified but required nutrition missing: ask for a Nutrition Facts photo;
3. lookup did not return a product: offer a nutrition-only reading of a photo, which
   never claims the product was identified.

Everything here is a pure function over the contract's types (``docs/api/README.md``),
so it does not depend on how the lookup or the label reading is implemented.
Completeness is never set here: it always comes from ``compute_missing_fields()``
through ``ProductResult``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from app.models.product import (
    ApiError,
    DataSource,
    ErrorCode,
    Nutrition,
    NutritionBasis,
    Product,
    ProductResult,
    ResultType,
    Serving,
    Source,
)


class NextAction(str, Enum):
    """What the application does after a barcode lookup."""

    USE_DATABASE = "use_database"
    REQUEST_NUTRITION_PHOTO = "request_nutrition_photo"
    NUTRITION_ONLY_PHOTO = "nutrition_only_photo"
    RETAKE_BARCODE_PHOTO = "retake_barcode_photo"


class Reason(str, Enum):
    """Why that action was chosen. "Not found" and "lookup failed" stay separate."""

    COMPLETE = "complete"
    NUTRITION_MISSING = "nutrition_missing"
    ONLY_NON_NUTRITION_MISSING = "only_non_nutrition_missing"
    PRODUCT_NOT_FOUND = "product_not_found"
    LOOKUP_FAILED = "lookup_failed"
    INVALID_BARCODE = "invalid_barcode"


# missing_fields paths a Nutrition Facts photo can supply. A photo of the table cannot
# supply a product name or an ingredient list (F1: ingredient OCR is not attempted).
_PHOTO_PREFIXES = ("serving.", "nutrition.")

_LOOKUP_FAILURES = {ErrorCode.UPSTREAM_UNAVAILABLE, ErrorCode.UPSTREAM_TIMEOUT}


@dataclass(frozen=True)
class RoutingDecision:
    action: NextAction
    reason: Reason
    # True only when the barcode lookup returned a product.
    product_identified: bool
    # The missing_fields paths the requested photo is expected to fill.
    photo_fields: tuple[str, ...] = ()
    # True when the database gave no answer, so asking again may succeed (502/504).
    can_retry_lookup: bool = False

    @property
    def photo_requested(self) -> bool:
        return self.action in (
            NextAction.REQUEST_NUTRITION_PHOTO,
            NextAction.NUTRITION_ONLY_PHOTO,
        )


def route_lookup(outcome: ProductResult | ApiError) -> RoutingDecision:
    """Choose the next step from a barcode lookup's result or error."""
    if isinstance(outcome, ApiError):
        return _route_error(outcome)
    if outcome.result is not ResultType.PRODUCT:
        raise ValueError("a barcode lookup returns a 'product' result, not 'nutrition_only'")

    missing = outcome.missing_fields
    if not missing:
        return RoutingDecision(NextAction.USE_DATABASE, Reason.COMPLETE, product_identified=True)

    photo_fields = tuple(path for path in missing if path.startswith(_PHOTO_PREFIXES))
    if photo_fields:
        return RoutingDecision(
            NextAction.REQUEST_NUTRITION_PHOTO,
            Reason.NUTRITION_MISSING,
            product_identified=True,
            photo_fields=photo_fields,
        )
    # Only the name or ingredients are missing. The result stays incomplete, but a
    # Nutrition Facts photo would not change that, so none is requested.
    return RoutingDecision(
        NextAction.USE_DATABASE, Reason.ONLY_NON_NUTRITION_MISSING, product_identified=True
    )


def _route_error(error: ApiError) -> RoutingDecision:
    if error.code is ErrorCode.INVALID_BARCODE:
        return RoutingDecision(
            NextAction.RETAKE_BARCODE_PHOTO, Reason.INVALID_BARCODE, product_identified=False
        )
    if error.code is ErrorCode.PRODUCT_NOT_FOUND:
        return RoutingDecision(
            NextAction.NUTRITION_ONLY_PHOTO, Reason.PRODUCT_NOT_FOUND, product_identified=False
        )
    if error.code in _LOOKUP_FAILURES:
        # We do not know whether the product exists, so this must not be reported as
        # "not found"; the user may retry the lookup or carry on with a photo.
        return RoutingDecision(
            NextAction.NUTRITION_ONLY_PHOTO,
            Reason.LOOKUP_FAILED,
            product_identified=False,
            can_retry_lookup=True,
        )
    raise ValueError(f"unhandled lookup error code: {error.code.value!r}")


def _check_label_reading(serving: Serving, nutrition: Nutrition) -> None:
    """A label reading must be labelled as one, so its values are never shown as database data."""
    if serving.source not in (None, Source.NUTRITION_LABEL_PHOTO):
        raise ValueError("label serving must have source 'nutrition_label_photo'")
    for name, value in nutrition.nutrients.items():
        if value is not None and value.source is not Source.NUTRITION_LABEL_PHOTO:
            raise ValueError(f"label value {name} must have source 'nutrition_label_photo'")


def same_serving_basis(database: Product, label_serving: Serving, label: Nutrition) -> bool:
    """Whether database and label nutrition describe the same amount of food.

    True only when both are per serving and both state the same metric serving
    quantity and unit. An unknown quantity on either side is not a match: we cannot
    show the bases agree, so the values must not be combined.
    """
    if database.nutrition.basis is not NutritionBasis.SERVING:
        return False
    if label.basis is not NutritionBasis.SERVING:
        return False
    ours, theirs = database.serving, label_serving
    if ours.quantity is None or theirs.quantity is None:
        return False
    if ours.unit is None or ours.unit != theirs.unit:
        return False
    return math.isclose(ours.quantity, theirs.quantity)


def merge_label_nutrition(
    database: ProductResult, label_serving: Serving, label_nutrition: Nutrition
) -> ProductResult:
    """Apply a Nutrition Facts photo reading to a product identified by barcode (path 2).

    - Same serving basis: the label fills only the nutrients the database lacks, and
      the database values and serving stay in use.
    - Any other case: the label's serving and nutrition replace the database's as a
      whole. Values on different bases are never combined, and nothing is converted
      or derived from per-100 g data.

    The product's identity, ingredients and package always stay from the database.
    A reading with no nutrient values changes nothing.
    """
    if database.result is not ResultType.PRODUCT:
        raise ValueError("label nutrition can only be merged into a 'product' result")
    _check_label_reading(label_serving, label_nutrition)
    if label_nutrition.basis is None:
        return database

    product = database.product
    if same_serving_basis(product, label_serving, label_nutrition):
        nutrients = {
            name: value if value is not None else label_nutrition.nutrients[name]
            for name, value in product.nutrition.nutrients.items()
        }
        merged = replace(product, nutrition=Nutrition(NutritionBasis.SERVING, nutrients))
    else:
        merged = replace(product, serving=label_serving, nutrition=label_nutrition)
    return ProductResult(ResultType.PRODUCT, merged)


def build_nutrition_only(
    label_serving: Serving, label_nutrition: Nutrition, read_at: datetime
) -> ProductResult:
    """Build the result for a label photo read without an identified product (path 3).

    Barcode, name, brand and ingredients are left ``None``: the lookup did not
    identify a product, so the result must not claim one (F1).
    """
    _check_label_reading(label_serving, label_nutrition)
    product = Product(
        source=DataSource(Source.NUTRITION_LABEL_PHOTO, read_at),
        serving=label_serving,
        nutrition=label_nutrition,
    )
    return ProductResult(ResultType.NUTRITION_ONLY, product)
