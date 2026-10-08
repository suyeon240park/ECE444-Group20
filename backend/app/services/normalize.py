"""Turn an Open Food Facts product record into the application's ``Product`` model.

The rules are the ones in docs/api/README.md ("Open Food Facts -> model mapping"):
anything OFF leaves out, blanks or gets wrong becomes ``None``, never ``0`` or ``""``,
and nutrient values from different bases are never mixed.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.models.product import (
    CANONICAL_UNITS,
    QUANTITY_UNITS,
    Certainty,
    DataSource,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    Package,
    Product,
    Serving,
    Source,
    is_valid_barcode,
)

OFF_PRODUCT_URL = "https://world.openfoodfacts.org/product/{code}"

# Model nutrient -> (OFF key without its _serving / _100g suffix, factor to the model's unit).
# OFF stores everything in grams except energy; sodium and cholesterol are mg on the label.
_NUTRIENT_KEYS: dict[str, tuple[str, int]] = {
    "calories": ("energy-kcal", 1),
    "total_fat": ("fat", 1),
    "saturated_fat": ("saturated-fat", 1),
    "trans_fat": ("trans-fat", 1),
    "cholesterol": ("cholesterol", 1000),
    "sodium": ("sodium", 1000),
    "carbohydrate": ("carbohydrates", 1),
    "sugars": ("sugars", 1),
    "fibre": ("fiber", 1),
    "protein": ("proteins", 1),
}


def _text(value: Any) -> str | None:
    """A non-blank string, trimmed; anything else is missing."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_text(raw: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        text = _text(raw.get(key))
        if text is not None:
            return text
    return None


def _number(value: Any) -> float | int | None:
    """A finite number. OFF sends numbers, and sometimes numeric strings, for the same field."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return None


def _quantity(
    raw: dict[str, Any], quantity_key: str, unit_key: str
) -> tuple[float | int | None, str | None]:
    """A positive quantity with its unit; both or neither."""
    quantity = _number(raw.get(quantity_key))
    unit = _text(raw.get(unit_key))
    unit = unit.lower() if unit else None
    if quantity is None or quantity <= 0 or unit not in QUANTITY_UNITS:
        return None, None
    return quantity, unit


def _serving(raw: dict[str, Any]) -> Serving:
    size_text = _text(raw.get("serving_size"))
    quantity, unit = _quantity(raw, "serving_quantity", "serving_quantity_unit")
    if size_text is None and quantity is None:
        return Serving()
    return Serving(size_text, quantity, unit, Source.OPEN_FOOD_FACTS)


def _package(raw: dict[str, Any]) -> Package:
    quantity_text = _text(raw.get("quantity"))
    quantity, unit = _quantity(raw, "product_quantity", "product_quantity_unit")
    if quantity_text is None and quantity is None:
        return Package()
    # OFF has no servings-per-package field; it is never estimated here.
    return Package(quantity_text, quantity, unit, None, Source.OPEN_FOOD_FACTS)


def _read_nutrients(nutriments: dict[str, Any], suffix: str) -> dict[str, NutrientValue | None]:
    nutrients: dict[str, NutrientValue | None] = {}
    for name, (stem, factor) in _NUTRIENT_KEYS.items():
        amount = _number(nutriments.get(f"{stem}{suffix}"))
        if amount is None or amount < 0:
            nutrients[name] = None
            continue
        if factor != 1:
            amount = round(amount * factor, 6)
        nutrients[name] = NutrientValue(
            amount, CANONICAL_UNITS[name], Source.OPEN_FOOD_FACTS, Certainty.REPORTED
        )
    return nutrients


def _per_100_basis(raw: dict[str, Any]) -> NutritionBasis:
    # OFF's ``_100g`` keys mean per 100 mL for liquids, but its ``nutrition_data_per`` field
    # still says "100g" for them, so a product sold by volume is treated as per 100 mL.
    units = (raw.get("product_quantity_unit"), raw.get("serving_quantity_unit"))
    if any(isinstance(u, str) and u.strip().lower() == "ml" for u in units):
        return NutritionBasis.PER_100ML
    return NutritionBasis.PER_100G


def _nutrition(raw: dict[str, Any]) -> Nutrition:
    nutriments = raw.get("nutriments")
    if not isinstance(nutriments, dict):
        return Nutrition()

    # Prefer the labelled serving, which is what F1 requires. A basis is chosen as a whole:
    # a per-serving result never has per-100 g values filled in for its gaps.
    if _text(raw.get("serving_size")) is not None:
        per_serving = _read_nutrients(nutriments, "_serving")
        if any(v is not None for v in per_serving.values()):
            return Nutrition(NutritionBasis.SERVING, per_serving)

    per_100 = _read_nutrients(nutriments, "_100g")
    if any(v is not None for v in per_100.values()):
        return Nutrition(_per_100_basis(raw), per_100)
    return Nutrition()


def _timestamp(value: Any) -> datetime | None:
    seconds = _number(value)
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def normalize_off_product(raw: dict[str, Any], barcode: str, retrieved_at: datetime) -> Product:
    """Build a ``Product`` from OFF's ``product`` object.

    ``barcode`` is the one that was requested; it is used when OFF's own ``code`` is
    missing or not a valid barcode. ``retrieved_at`` must be timezone-aware.
    """
    code = raw.get("code")
    canonical = code if isinstance(code, str) and is_valid_barcode(code) else barcode
    return Product(
        barcode=canonical,
        name=_first_text(raw, "product_name", "product_name_en", "product_name_fr"),
        brand=_text(raw.get("brands")),
        ingredients_text=_first_text(
            raw, "ingredients_text_en", "ingredients_text", "ingredients_text_fr"
        ),
        serving=_serving(raw),
        package=_package(raw),
        nutrition=_nutrition(raw),
        source=DataSource(
            Source.OPEN_FOOD_FACTS,
            retrieved_at,
            url=OFF_PRODUCT_URL.format(code=canonical),
            last_modified_at=_timestamp(raw.get("last_modified_t")),
        ),
    )


def has_no_data(product: Product) -> bool:
    """Whether OFF knows the barcode but holds nothing we can show.

    Such records are reported as "not found" rather than as an incomplete product.
    """
    return (
        product.name is None
        and product.brand is None
        and product.ingredients_text is None
        and product.serving.source is None
        and product.package.source is None
        and product.nutrition.basis is None
    )
