"""Whole-package nutrition result (#36, F2).

Produced by ``app.services.package_nutrition`` from a ``Product``; ``to_dict()`` is
its JSON form, documented as ``PackageNutritionResult`` in docs/api/openapi.yaml.
Every key is always present, and missing data is ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.models.product import NutrientValue

NOT_CALCULATED_MESSAGE = (
    "Whole-package nutrition could not be calculated from the available serving and "
    "package information."
)
APPROXIMATE_LABEL = "Approximate"
WHOLE_PACKAGE_DAILY_VALUE_LABEL = "Calculated for whole package"


class PackageNutritionStatus(str, Enum):
    CALCULATED = "calculated"
    NOT_CALCULATED = "not_calculated"


class MultiplierMethod(str, Enum):
    """How the number of servings in the package was obtained (F2 "Serving multiplier")."""

    # Stated by a source: exact.
    SERVINGS_PER_PACKAGE = "servings_per_package"
    # Net package quantity / serving size: "Approximate".
    PACKAGE_QUANTITY = "package_quantity"


class NotCalculatedReason(str, Enum):
    """Why no whole-package values were produced. The user always sees the same message."""

    NO_PER_SERVING_NUTRITION = "no_per_serving_nutrition"
    NO_PACKAGE_INFORMATION = "no_package_information"
    NO_SERVING_QUANTITY = "no_serving_quantity"
    INCOMPATIBLE_UNITS = "incompatible_units"
    PACKAGE_SMALLER_THAN_SERVING = "package_smaller_than_serving"
    UNCONFIRMED_PHOTO_VALUES = "unconfirmed_photo_values"


class WholePackageStatus(str, Enum):
    """Per nutrient: whether its whole-package amount could be shown."""

    CALCULATED = "calculated"
    # No usable per-serving amount, or no whole-package calculation at all.
    NOT_AVAILABLE = "not_available"
    # A label-photo amount the user has not confirmed yet (#39).
    NEEDS_CONFIRMATION = "needs_confirmation"


@dataclass(frozen=True)
class WholePackageAmount:
    """One nutrient for the whole package. ``amount`` is unrounded; show ``display_amount``."""

    amount: float
    unit: str
    display_amount: float
    # Calculated from the whole-package amount, never scaled from a per-serving %DV.
    daily_value_percent: float | None = None
    display_daily_value_percent: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "amount": self.amount,
            "unit": self.unit,
            "display_amount": self.display_amount,
            "daily_value_percent": self.daily_value_percent,
            "display_daily_value_percent": self.display_daily_value_percent,
        }


@dataclass(frozen=True)
class PackageNutrientRow:
    name: str
    # The labelled per-serving value, shown whether or not it could be scaled.
    per_serving: NutrientValue | None
    whole_package: WholePackageAmount | None
    whole_package_status: WholePackageStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "per_serving": self.per_serving.to_dict() if self.per_serving else None,
            "whole_package": self.whole_package.to_dict() if self.whole_package else None,
            "whole_package_status": self.whole_package_status.value,
        }


@dataclass(frozen=True)
class PackageNutritionResult:
    status: PackageNutritionStatus
    rows: tuple[PackageNutrientRow, ...]
    per_serving_label: str | None = None
    whole_package_label: str | None = None
    # Unrounded number of servings in the package; ``display_servings`` is for the UI.
    servings: float | None = None
    display_servings: float | None = None
    method: MultiplierMethod | None = None
    reason: NotCalculatedReason | None = None
    # Label-photo values (dotted paths) that would be used once the user confirms them.
    pending_confirmation: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        calculated = self.status is PackageNutritionStatus.CALCULATED
        if calculated != (self.servings is not None and self.method is not None):
            raise ValueError("a calculated result needs servings and a method, and only it")
        if calculated == (self.reason is not None):
            raise ValueError("a reason is required exactly when nothing was calculated")

    @property
    def daily_value_label(self) -> str | None:
        """F2's "Calculated for whole package", once for the column rather than on every row."""
        has_dv = any(
            row.whole_package is not None and row.whole_package.daily_value_percent is not None
            for row in self.rows
        )
        return WHOLE_PACKAGE_DAILY_VALUE_LABEL if has_dv else None

    @property
    def approximate(self) -> bool:
        return self.method is MultiplierMethod.PACKAGE_QUANTITY

    def to_dict(self) -> dict[str, Any]:
        calculated = self.status is PackageNutritionStatus.CALCULATED
        return {
            "status": self.status.value,
            "per_serving_label": self.per_serving_label,
            "whole_package_label": self.whole_package_label,
            "servings": self.servings,
            "display_servings": self.display_servings,
            "method": self.method.value if self.method else None,
            "approximate": self.approximate,
            "approximate_label": APPROXIMATE_LABEL if self.approximate else None,
            "daily_value_label": self.daily_value_label,
            "reason": self.reason.value if self.reason else None,
            "message": None if calculated else NOT_CALCULATED_MESSAGE,
            "pending_confirmation": list(self.pending_confirmation),
            "rows": [row.to_dict() for row in self.rows],
        }
