"""Rebuild a photo result from the values the user checked (#39, Q1 safe-use rule).

The client shows the values read from a Nutrition Facts photo (#42), the user
confirms or corrects them, and the client sends the result back with the checked
values marked ``user_confirmed``. This module turns that request back into a
``ProductResult`` that the analysis pipeline (#43) can scale (#36) and explain (#37).

Only label-photo values are taken from the client. For a product identified by
barcode, every database value comes from a fresh lookup, so a client can neither
change database data nor mark it confirmed. The merge follows
``merge_label_nutrition``: a photo serving replaces the database's serving and
nutrition as a whole; without one, photo values only fill the database's gaps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from app.models.product import (
    ALL_NUTRIENTS,
    Certainty,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    Package,
    ProductResult,
    ResultType,
    Serving,
    Source,
)
from app.services.fallback_routing import build_nutrition_only

PHOTO = Source.NUTRITION_LABEL_PHOTO
# What a client may say about a photo value: still unchecked, or checked by the user.
CLIENT_CERTAINTIES = {Certainty.UNCERTAIN.value, Certainty.USER_CONFIRMED.value}


class ConfirmationError(Exception):
    """A request the endpoint refuses, with a stable ``code`` and HTTP status."""

    def __init__(self, message: str, code: str = "invalid_confirmation", status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class PhotoValues:
    """The label-photo values in a confirmation request; database values are ignored."""

    serving: Serving | None
    package: Package | None
    nutrients: dict[str, NutrientValue]


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfirmationError(f"{path} must be an object")
    return value


def _optional_object(parent: dict[str, Any], key: str, path: str) -> dict[str, Any]:
    """``parent[key]`` as an object. Absent means empty; null or any other type is refused."""
    if key not in parent:
        return {}
    return _object(parent[key], path)


def _number(raw: dict[str, Any], key: str, path: str, required: bool = False) -> float | None:
    """A finite number from the request.

    Flask's parser accepts ``NaN`` and ``Infinity``, which would make the response
    invalid JSON, and Python counts ``true`` as 1, so both are refused here.
    """
    value = raw.get(key)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfirmationError(f"{path}.{key} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise ConfirmationError(f"{path}.{key} must be a finite number, got {value!r}")
    return value


def _certainty(raw: dict[str, Any], path: str) -> Certainty:
    certainty = raw.get("certainty")
    if certainty not in CLIENT_CERTAINTIES:
        raise ConfirmationError(
            f"{path}.certainty must be 'uncertain' or 'user_confirmed', got {certainty!r}"
        )
    return Certainty(certainty)


def _is_photo(raw: dict[str, Any] | None) -> bool:
    return isinstance(raw, dict) and raw.get("source") == PHOTO.value


def _build(path: str, make):
    """Run a model constructor, reporting its validation errors as a bad request."""
    try:
        return make()
    except (TypeError, ValueError) as exc:
        raise ConfirmationError(f"{path}: {exc}") from None


def parse_photo_values(product: Any) -> PhotoValues:
    """The ``nutrition_label_photo`` values of a ``product`` object (#20 contract)."""
    product = _object(product, "product")

    serving = None
    raw_serving = _optional_object(product, "serving", "product.serving")
    if _is_photo(raw_serving):
        certainty = _certainty(raw_serving, "product.serving")
        quantity = _number(raw_serving, "quantity", "product.serving")
        serving = _build(
            "product.serving",
            lambda: Serving(
                raw_serving.get("size_text"),
                quantity,
                raw_serving.get("unit"),
                PHOTO,
                certainty,
            ),
        )

    package = None
    raw_package = _optional_object(product, "package", "product.package")
    if _is_photo(raw_package):
        certainty = _certainty(raw_package, "product.package")
        servings = _number(raw_package, "servings_per_package", "product.package")
        # The label prints servings per package only (#42); net quantity is never read.
        package = _build(
            "product.package",
            lambda: Package(servings_per_package=servings, source=PHOTO, certainty=certainty),
        )

    nutrition = _optional_object(product, "nutrition", "product.nutrition")
    raw_nutrients = _optional_object(nutrition, "nutrients", "product.nutrition.nutrients")
    nutrients: dict[str, NutrientValue] = {}
    for name, raw in raw_nutrients.items():
        if not _is_photo(raw):
            continue
        path = f"product.nutrition.nutrients.{name}"
        if name not in ALL_NUTRIENTS:
            raise ConfirmationError(f"{path}: unknown nutrient")
        certainty = _certainty(raw, path)
        amount = _number(raw, "amount", path, required=True)
        daily_value = _number(raw, "daily_value_percent", path)
        nutrients[name] = _build(
            path,
            lambda raw=raw, certainty=certainty, amount=amount, daily_value=daily_value: (
                NutrientValue(amount, raw.get("unit"), PHOTO, certainty, daily_value)
            ),
        )
    return PhotoValues(serving, package, nutrients)


def _photo_nutrition(photo: PhotoValues) -> Nutrition:
    # Every photo nutrient is per serving (#42).
    if not photo.nutrients:
        return Nutrition()
    return _build("product.nutrition", lambda: Nutrition(NutritionBasis.SERVING, photo.nutrients))


def rebuild_nutrition_only(photo: PhotoValues, read_at: datetime) -> ProductResult:
    """A ``nutrition_only`` result from the checked photo values alone (F1 path 3)."""
    return build_nutrition_only(
        photo.serving or Serving(), _photo_nutrition(photo), read_at, photo.package
    )


def rebuild_product(database: ProductResult, photo: PhotoValues) -> ProductResult:
    """The database product with the checked photo values merged back in (F1 path 2)."""
    product = database.product
    if photo.package is not None and product.package.servings_per_package is None:
        product = replace(product, package=photo.package)

    if photo.serving is not None:
        # The label's serving replaced the database's, so its nutrition did too.
        merged = replace(product, serving=photo.serving, nutrition=_photo_nutrition(photo))
    elif photo.nutrients:
        if product.nutrition.basis is not NutritionBasis.SERVING:
            raise ConfirmationError(
                "photo nutrients need a photo serving: the database nutrition is not per serving"
            )
        nutrients = dict(product.nutrition.nutrients)
        for name, value in photo.nutrients.items():
            if nutrients[name] is not None:
                raise ConfirmationError(
                    f"product.nutrition.nutrients.{name}: the database already has this value"
                )
            nutrients[name] = value
        merged = replace(product, nutrition=Nutrition(NutritionBasis.SERVING, nutrients))
    else:
        merged = product
    return ProductResult(ResultType.PRODUCT, merged)
