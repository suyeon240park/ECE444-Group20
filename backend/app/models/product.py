"""Product data model returned by ``GET /api/products/{barcode}`` (#20).

This module is the code form of the contract in ``docs/api/openapi.yaml`` and
``docs/api/README.md``. Every producer of a product result (Open Food Facts lookup
#14, Nutrition Facts OCR #15) builds these objects, and ``to_dict()`` is the only
way they are turned into JSON, so the response shape cannot drift between them.

Missing data is always ``None`` (JSON ``null``), never ``0`` or ``""``, and every
key is always present in the JSON output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Source(str, Enum):
    """Where a value came from. Shown to the user next to the value (F1)."""

    OPEN_FOOD_FACTS = "open_food_facts"
    NUTRITION_LABEL_PHOTO = "nutrition_label_photo"


class Certainty(str, Enum):
    """How far a value can be trusted.

    ``reported`` is used for product-database values. ``confident`` and
    ``uncertain`` are for OCR values under Q1's confidence rule; uncertain values
    must not be used for explanations or whole-package calculations.
    """

    REPORTED = "reported"
    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"


class NutritionBasis(str, Enum):
    """The amount every nutrient value in one result refers to. Never mixed."""

    SERVING = "serving"
    PER_100G = "100g"
    PER_100ML = "100ml"


class Completeness(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class ResultType(str, Enum):
    """``product``: identified by barcode. ``nutrition_only``: label photo only (F1)."""

    PRODUCT = "product"
    NUTRITION_ONLY = "nutrition_only"


class ErrorCode(str, Enum):
    INVALID_BARCODE = "invalid_barcode"
    PRODUCT_NOT_FOUND = "product_not_found"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"


ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_BARCODE: 400,
    ErrorCode.PRODUCT_NOT_FOUND: 404,
    ErrorCode.UPSTREAM_UNAVAILABLE: 502,
    ErrorCode.UPSTREAM_TIMEOUT: 504,
}

# Nutrition fields F1 requires for a full analysis, in Nutrition Facts table order.
REQUIRED_NUTRIENTS: tuple[str, ...] = (
    "calories",
    "total_fat",
    "saturated_fat",
    "sodium",
    "carbohydrate",
    "sugars",
    "fibre",
    "protein",
)
# Shown when available; their absence never makes a result incomplete.
OPTIONAL_NUTRIENTS: tuple[str, ...] = ("trans_fat", "cholesterol")
ALL_NUTRIENTS: tuple[str, ...] = REQUIRED_NUTRIENTS + OPTIONAL_NUTRIENTS

# The one unit each nutrient is expressed in, matching the Canadian Nutrition Facts table.
CANONICAL_UNITS: dict[str, str] = {
    "calories": "kcal",
    "total_fat": "g",
    "saturated_fat": "g",
    "trans_fat": "g",
    "cholesterol": "mg",
    "sodium": "mg",
    "carbohydrate": "g",
    "sugars": "g",
    "fibre": "g",
    "protein": "g",
}

QUANTITY_UNITS: tuple[str, ...] = ("g", "ml")

# EAN-8, UPC-A (12), EAN-13 and GTIN-14, digits only.
BARCODE_PATTERN = re.compile(r"^\d{8,14}$")

_DATABASE_SOURCES = {Source.OPEN_FOOD_FACTS}
_OCR_CERTAINTIES = {Certainty.CONFIDENT, Certainty.UNCERTAIN}


def is_valid_barcode(value: str) -> bool:
    return bool(BARCODE_PATTERN.match(value))


def _check_source_certainty(source: Source, certainty: Certainty) -> None:
    if source in _DATABASE_SOURCES and certainty is not Certainty.REPORTED:
        raise ValueError(f"database values must have certainty 'reported', got {certainty.value!r}")
    if source not in _DATABASE_SOURCES and certainty not in _OCR_CERTAINTIES:
        raise ValueError(
            f"label-photo values must be 'confident' or 'uncertain', got {certainty.value!r}"
        )


def _check_quantity(name: str, value: float | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def _check_unit(name: str, value: str | None) -> None:
    if value is not None and value not in QUANTITY_UNITS:
        raise ValueError(f"{name} must be one of {QUANTITY_UNITS}, got {value!r}")


def _check_source_presence(name: str, values: tuple[Any, ...], source: Source | None) -> None:
    """A source is required when any value is present and forbidden when none is."""
    has_value = any(v is not None for v in values)
    if has_value and source is None:
        raise ValueError(f"{name} has values but no source")
    if not has_value and source is not None:
        raise ValueError(f"{name} has a source but no values")


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetimes must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class NutrientValue:
    """One nutrient amount on the result's nutrition basis."""

    amount: float
    unit: str
    source: Source
    certainty: Certainty
    # The %DV printed on the label. Open Food Facts does not provide one, so it is
    # always None for database values; a calculated %DV is not stored here (F3).
    daily_value_percent: float | None = None

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError(f"amount must not be negative, got {self.amount}")
        if self.daily_value_percent is not None and self.daily_value_percent < 0:
            raise ValueError(
                f"daily_value_percent must not be negative, got {self.daily_value_percent}"
            )
        _check_source_certainty(self.source, self.certainty)

    @property
    def is_usable(self) -> bool:
        """Whether F2/F3 may treat this value as verified information."""
        return self.certainty is not Certainty.UNCERTAIN

    def to_dict(self) -> dict[str, Any]:
        return {
            "amount": self.amount,
            "unit": self.unit,
            "daily_value_percent": self.daily_value_percent,
            "source": self.source.value,
            "certainty": self.certainty.value,
        }


@dataclass(frozen=True)
class Serving:
    """Labelled serving size, e.g. ``"2 tbsp (30 g)"`` → quantity 30, unit ``"g"``."""

    size_text: str | None = None
    quantity: float | None = None
    unit: str | None = None
    source: Source | None = None

    def __post_init__(self) -> None:
        _check_quantity("serving.quantity", self.quantity)
        _check_unit("serving.unit", self.unit)
        _check_source_presence("serving", (self.size_text, self.quantity, self.unit), self.source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "size_text": self.size_text,
            "quantity": self.quantity,
            "unit": self.unit,
            "source": self.source.value if self.source else None,
        }


@dataclass(frozen=True)
class Package:
    """Net package quantity and servings per package, for F2.

    ``servings_per_package`` stays None unless a source states it; it is never
    estimated here (requirements, "How will net package quantity be obtained").
    """

    quantity_text: str | None = None
    quantity: float | None = None
    unit: str | None = None
    servings_per_package: float | None = None
    source: Source | None = None

    def __post_init__(self) -> None:
        _check_quantity("package.quantity", self.quantity)
        _check_quantity("package.servings_per_package", self.servings_per_package)
        _check_unit("package.unit", self.unit)
        _check_source_presence(
            "package",
            (self.quantity_text, self.quantity, self.unit, self.servings_per_package),
            self.source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity_text": self.quantity_text,
            "quantity": self.quantity,
            "unit": self.unit,
            "servings_per_package": self.servings_per_package,
            "source": self.source.value if self.source else None,
        }


@dataclass(frozen=True)
class Nutrition:
    """All nutrient values of one result, on a single basis.

    ``nutrients`` always ends up with every key in ``ALL_NUTRIENTS``; keys not
    passed in are filled with None.
    """

    basis: NutritionBasis | None = None
    nutrients: dict[str, NutrientValue | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.nutrients) - set(ALL_NUTRIENTS)
        if unknown:
            raise ValueError(f"unknown nutrients: {sorted(unknown)}")
        filled = {name: self.nutrients.get(name) for name in ALL_NUTRIENTS}
        object.__setattr__(self, "nutrients", filled)

        present = {name: value for name, value in filled.items() if value is not None}
        if present and self.basis is None:
            raise ValueError("nutrition has values but no basis")
        for name, value in present.items():
            if value.unit != CANONICAL_UNITS[name]:
                raise ValueError(f"{name} must be in {CANONICAL_UNITS[name]!r}, got {value.unit!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "basis": self.basis.value if self.basis else None,
            "nutrients": {
                name: (value.to_dict() if value else None) for name, value in self.nutrients.items()
            },
        }


@dataclass(frozen=True)
class DataSource:
    """Provenance of the product record as a whole."""

    provider: Source
    retrieved_at: datetime
    url: str | None = None
    last_modified_at: datetime | None = None

    def __post_init__(self) -> None:
        # Fail at construction rather than at serialization.
        _iso_utc(self.retrieved_at)
        if self.last_modified_at is not None:
            _iso_utc(self.last_modified_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "url": self.url,
            "retrieved_at": _iso_utc(self.retrieved_at),
            "last_modified_at": _iso_utc(self.last_modified_at) if self.last_modified_at else None,
        }


@dataclass(frozen=True)
class Product:
    source: DataSource
    barcode: str | None = None
    name: str | None = None
    brand: str | None = None
    ingredients_text: str | None = None
    serving: Serving = field(default_factory=Serving)
    package: Package = field(default_factory=Package)
    nutrition: Nutrition = field(default_factory=Nutrition)

    def __post_init__(self) -> None:
        if self.barcode is not None and not is_valid_barcode(self.barcode):
            raise ValueError(f"barcode must be 8-14 digits, got {self.barcode!r}")
        for name in ("name", "brand", "ingredients_text"):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise ValueError(f"{name} must be None rather than blank")

    def to_dict(self) -> dict[str, Any]:
        return {
            "barcode": self.barcode,
            "name": self.name,
            "brand": self.brand,
            "ingredients_text": self.ingredients_text,
            "serving": self.serving.to_dict(),
            "package": self.package.to_dict(),
            "nutrition": self.nutrition.to_dict(),
            "source": self.source.to_dict(),
        }


def compute_missing_fields(product: Product, result: ResultType = ResultType.PRODUCT) -> list[str]:
    """Dotted JSON paths of the data F1 requires for a full analysis that is missing.

    An uncertain OCR value counts as missing because it cannot be used. A
    nutrition-only result is judged on its nutrition alone: it never has a name or
    ingredients, by definition.
    """
    missing: list[str] = []
    if result is ResultType.PRODUCT:
        if product.name is None:
            missing.append("name")
        if product.ingredients_text is None:
            missing.append("ingredients_text")
    if product.serving.size_text is None:
        missing.append("serving.size_text")
    if product.nutrition.basis is not NutritionBasis.SERVING:
        missing.append("nutrition.basis")
    for name in REQUIRED_NUTRIENTS:
        value = product.nutrition.nutrients[name]
        if value is None or not value.is_usable:
            missing.append(f"nutrition.nutrients.{name}")
    return missing


@dataclass(frozen=True)
class ProductResult:
    """Body of a successful (HTTP 200) product response.

    ``completeness`` and ``missing_fields`` are derived from the product rather
    than stored, so they can never disagree with it.
    """

    result: ResultType
    product: Product

    def __post_init__(self) -> None:
        if self.result is ResultType.NUTRITION_ONLY:
            p = self.product
            if any(v is not None for v in (p.barcode, p.name, p.brand, p.ingredients_text)):
                raise ValueError(
                    "a nutrition-only result must not identify a product "
                    "(barcode, name, brand and ingredients_text must be None)"
                )
            if p.source.provider is not Source.NUTRITION_LABEL_PHOTO:
                raise ValueError("a nutrition-only result must come from a nutrition label photo")
        elif self.product.barcode is None:
            raise ValueError("a product result must have a barcode")

    @property
    def missing_fields(self) -> list[str]:
        return compute_missing_fields(self.product, self.result)

    @property
    def completeness(self) -> Completeness:
        return Completeness.INCOMPLETE if self.missing_fields else Completeness.COMPLETE

    def to_dict(self) -> dict[str, Any]:
        missing = self.missing_fields
        return {
            "result": self.result.value,
            "completeness": (Completeness.INCOMPLETE if missing else Completeness.COMPLETE).value,
            "missing_fields": missing,
            "product": self.product.to_dict(),
        }


@dataclass(frozen=True)
class ApiError:
    """Body of every non-200 product response: ``{"error": {"code", "message"}}``."""

    code: ErrorCode
    message: str

    @property
    def http_status(self) -> int:
        return ERROR_HTTP_STATUS[self.code]

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code.value, "message": self.message}}
