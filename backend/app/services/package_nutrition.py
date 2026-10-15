"""Whole-package nutrition from per-serving values (#36, F2). Pure; no network or Flask I/O.

The multiplier follows F2's order:

1. a reliable servings-per-package value, used as stated;
2. otherwise net package quantity / serving size, when both are reliable and in the
   same unit. This result is labelled "Approximate".

Without either, nothing is calculated and the result carries F2's message. #28
found Open Food Facts package sizes missing or wrong for most Canadian products, so
this is a common case, not an error.

Label-photo values (serving, servings per package, nutrients) are used only once
the user has confirmed them (#39, Q1). The caller passes the confirmed values as
dotted paths, as in ``missing_fields``: ``"serving"``,
``"package.servings_per_package"``, ``"package.quantity"`` and
``"nutrition.nutrients.<name>"``. Database values need no confirmation.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from app.models.package_nutrition import (
    MultiplierMethod,
    NotCalculatedReason,
    PackageNutrientRow,
    PackageNutritionResult,
    PackageNutritionStatus,
    WholePackageAmount,
    WholePackageStatus,
)
from app.models.product import (
    ALL_NUTRIENTS,
    NutrientValue,
    NutritionBasis,
    Product,
    Source,
)
from app.services.daily_values import daily_value_percent

SERVING_PATH = "serving"
SERVINGS_PER_PACKAGE_PATH = "package.servings_per_package"
PACKAGE_QUANTITY_PATH = "package.quantity"

# A package that works out to less than one serving means the package or serving size
# is wrong (#28 saw both). Slightly under one is kept: labels round the serving size.
_MIN_DERIVED_SERVINGS = 0.95


def _round_half_up(value: float, places: int) -> float:
    exponent = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(exponent, rounding=ROUND_HALF_UP))


def display_amount(amount: float, unit: str) -> float:
    """Round a calculated amount for display only; calculations keep the unrounded value.

    kcal and mg to whole numbers; grams to 0.1 g below 10 g and to whole grams above.
    """
    if unit == "g" and amount < 10:
        return _round_half_up(amount, 1)
    return _round_half_up(amount, 0)


def _nutrient_path(name: str) -> str:
    return f"nutrition.nutrients.{name}"


class _Trust:
    """Decides which values may be used and records the photo values awaiting confirmation."""

    def __init__(self, confirmed: Iterable[str]) -> None:
        self._confirmed = frozenset(confirmed)
        self.pending: list[str] = []

    def allows(self, source: Source | None, path: str) -> bool:
        if source is not Source.NUTRITION_LABEL_PHOTO:
            return True
        if path in self._confirmed:
            return True
        if path not in self.pending:
            self.pending.append(path)
        return False


def _multiplier(
    product: Product, trust: _Trust
) -> tuple[float, MultiplierMethod] | NotCalculatedReason:
    serving, package = product.serving, product.package

    stated = package.servings_per_package
    if stated is not None and trust.allows(package.source, SERVINGS_PER_PACKAGE_PATH):
        return float(stated), MultiplierMethod.SERVINGS_PER_PACKAGE

    if package.quantity is None:
        if stated is not None:
            return NotCalculatedReason.UNCONFIRMED_PHOTO_VALUES
        return NotCalculatedReason.NO_PACKAGE_INFORMATION
    if serving.quantity is None:
        return NotCalculatedReason.NO_SERVING_QUANTITY
    # Ask about both values, so the user can confirm them together.
    package_ok = trust.allows(package.source, PACKAGE_QUANTITY_PATH)
    serving_ok = trust.allows(serving.source, SERVING_PATH)
    if not (package_ok and serving_ok):
        return NotCalculatedReason.UNCONFIRMED_PHOTO_VALUES
    if package.unit != serving.unit:
        # g and mL are never converted: the food's density is unknown.
        return NotCalculatedReason.INCOMPATIBLE_UNITS

    servings = package.quantity / serving.quantity
    if servings < _MIN_DERIVED_SERVINGS:
        return NotCalculatedReason.PACKAGE_SMALLER_THAN_SERVING
    return servings, MultiplierMethod.PACKAGE_QUANTITY


def _per_serving_label(product: Product) -> str:
    size = product.serving.size_text
    return f"Per serving ({size})" if size else "Per serving"


def _whole_package_label(product: Product, servings: float, method: MultiplierMethod) -> str:
    package = product.package
    # The quantity was trusted when it was divided; otherwise an unconfirmed photo
    # quantity is not shown as the package size.
    trusted = (
        method is MultiplierMethod.PACKAGE_QUANTITY
        or package.source is not Source.NUTRITION_LABEL_PHOTO
    )
    if package.quantity_text and trusted:
        return f"Whole package ({package.quantity_text})"
    return f"Whole package ({_round_half_up(servings, 1):g} servings)"


def _not_calculated(
    reason: NotCalculatedReason,
    rows: tuple[PackageNutrientRow, ...],
    trust: _Trust,
    per_serving_label: str | None,
) -> PackageNutritionResult:
    return PackageNutritionResult(
        PackageNutritionStatus.NOT_CALCULATED,
        rows,
        per_serving_label=per_serving_label,
        reason=reason,
        pending_confirmation=tuple(trust.pending),
    )


def calculate_package_nutrition(
    product: Product, confirmed: Iterable[str] = ()
) -> PackageNutritionResult:
    """Per-serving and whole-package values for every nutrient in ``ALL_NUTRIENTS``.

    Per-serving values are always returned for display, even when they cannot be
    scaled. Calories never get a %DV, and no %DV is invented: a whole-package %DV
    comes only from Health Canada's Daily Values (``daily_values``).
    """
    trust = _Trust(confirmed)
    nutrients = product.nutrition.nutrients

    if product.nutrition.basis is not NutritionBasis.SERVING:
        # Per-100 g data is never scaled: F2 multiplies the labelled serving.
        rows = tuple(
            PackageNutrientRow(name, None, None, WholePackageStatus.NOT_AVAILABLE)
            for name in ALL_NUTRIENTS
        )
        return _not_calculated(NotCalculatedReason.NO_PER_SERVING_NUTRITION, rows, trust, None)

    usable: dict[str, NutrientValue] = {}
    statuses: dict[str, WholePackageStatus] = {}
    for name in ALL_NUTRIENTS:
        value = nutrients[name]
        if value is None:
            statuses[name] = WholePackageStatus.NOT_AVAILABLE
        elif not trust.allows(value.source, _nutrient_path(name)):
            statuses[name] = WholePackageStatus.NEEDS_CONFIRMATION
        elif value.source is not Source.NUTRITION_LABEL_PHOTO and not value.is_usable:
            statuses[name] = WholePackageStatus.NOT_AVAILABLE
        else:
            usable[name] = value

    multiplier = _multiplier(product, trust)
    per_serving_label = _per_serving_label(product)
    if isinstance(multiplier, NotCalculatedReason):
        # Confirming a nutrient would not help: there is no package to scale it to.
        rows = tuple(
            PackageNutrientRow(name, nutrients[name], None, WholePackageStatus.NOT_AVAILABLE)
            for name in ALL_NUTRIENTS
        )
        return _not_calculated(multiplier, rows, trust, per_serving_label)
    if not usable:
        rows = tuple(
            PackageNutrientRow(name, nutrients[name], None, statuses[name])
            for name in ALL_NUTRIENTS
        )
        return _not_calculated(
            NotCalculatedReason.UNCONFIRMED_PHOTO_VALUES, rows, trust, per_serving_label
        )

    servings, method = multiplier
    totals = {name: value.amount * servings for name, value in usable.items()}
    rows = []
    for name in ALL_NUTRIENTS:
        if name not in totals:
            rows.append(PackageNutrientRow(name, nutrients[name], None, statuses[name]))
            continue
        unit = usable[name].unit
        percent = daily_value_percent(name, totals)
        whole = WholePackageAmount(
            amount=totals[name],
            unit=unit,
            display_amount=display_amount(totals[name], unit),
            daily_value_percent=percent,
            display_daily_value_percent=(
                int(_round_half_up(percent, 0)) if percent is not None else None
            ),
        )
        rows.append(PackageNutrientRow(name, nutrients[name], whole, WholePackageStatus.CALCULATED))

    return PackageNutritionResult(
        PackageNutritionStatus.CALCULATED,
        tuple(rows),
        per_serving_label=per_serving_label,
        whole_package_label=_whole_package_label(product, servings, method),
        servings=servings,
        display_servings=_round_half_up(servings, 1),
        method=method,
        pending_confirmation=tuple(trust.pending),
    )
