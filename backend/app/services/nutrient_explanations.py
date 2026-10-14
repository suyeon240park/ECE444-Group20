"""Per-serving %DV, Health Canada's 5% / 15% reading, and nutrient explanations (#37, F3).

Pure; no network or Flask I/O. The JSON shape is ``NutrientExplanationResult`` in
docs/api/openapi.yaml.

- A %DV printed on the label is used as it is. Otherwise one is calculated from
  Health Canada's Daily Values (``daily_values``) and labelled "Calculated". No %DV
  is invented: calories, carbohydrate, protein and trans fat never get one.
- "A little" (5% DV or less) and "a lot" (15% DV or more) are applied to per-serving
  %DVs only, never to whole-package amounts (#36) or per-100 g values.
- A label-photo value is used only after the user confirms it (#39), with the same
  dotted paths as ``package_nutrition``. Until then it is shown but not interpreted or
  explained as verified.
- Explanations come from the reviewed content (#38). Without reviewed content or
  text, the row says "No verified explanation available yet."

There is no overall score or good/bad verdict.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

from app.models.ingredients import IngredientSource, SourcedText
from app.models.product import ALL_NUTRIENTS, NutrientValue, NutritionBasis, Product, Source
from app.services.daily_values import (
    DAILY_VALUES_TITLE,
    DAILY_VALUES_URL,
    DAILY_VALUES_VERSION,
    daily_value_percent,
)
from app.services.nutrient_content import Guidance, NutrientContent

NOT_AVAILABLE = "Not available"
NO_EXPLANATION_MESSAGE = "No verified explanation available yet."
CALCULATED_LABEL = "Calculated"
NEEDS_CONFIRMATION_MESSAGE = "Confirm this value from the photo before it is explained."

A_LITTLE_MAX = 5
A_LOT_MIN = 15


class ValueStatus(str, Enum):
    VERIFIED = "verified"
    NOT_AVAILABLE = "not_available"
    # A label-photo value the user has not confirmed (#39).
    NEEDS_CONFIRMATION = "needs_confirmation"


class DailyValueOrigin(str, Enum):
    LABEL = "label"
    CALCULATED = "calculated"


class Interpretation(str, Enum):
    A_LITTLE = "a_little"
    A_LOT = "a_lot"


_INTERPRETATION_TEXT = {Interpretation.A_LITTLE: "a little", Interpretation.A_LOT: "a lot"}


def _round_percent(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def interpret(display_percent: int) -> Interpretation | None:
    """Health Canada's rule; between 5% and 15% only the number is shown."""
    if display_percent <= A_LITTLE_MAX:
        return Interpretation.A_LITTLE
    if display_percent >= A_LOT_MIN:
        return Interpretation.A_LOT
    return None


@dataclass(frozen=True)
class DailyValue:
    percent: float
    display_percent: int
    origin: DailyValueOrigin
    interpretation: Interpretation | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "percent": self.percent,
            "display_percent": self.display_percent,
            "origin": self.origin.value,
            "label": CALCULATED_LABEL if self.origin is DailyValueOrigin.CALCULATED else None,
            "interpretation": self.interpretation.value if self.interpretation else None,
            "interpretation_text": (
                _INTERPRETATION_TEXT[self.interpretation] if self.interpretation else None
            ),
        }


def _source_dict(source: IngredientSource) -> dict[str, Any]:
    return {
        "id": source.id,
        "publisher": source.publisher,
        "title": source.title,
        "url": source.url,
    }


def _text_dict(text: SourcedText, content: NutrientContent) -> dict[str, Any]:
    return {
        "text": text.text,
        "sources": [_source_dict(content.sources[i]) for i in text.source_ids],
    }


@dataclass(frozen=True)
class Explanation:
    what_it_is: SourcedText | None
    how_to_read: SourcedText | None


@dataclass(frozen=True)
class NutrientRow:
    name: str
    display_name: str
    guidance: Guidance
    value: NutrientValue | None
    status: ValueStatus
    daily_value: DailyValue | None
    explanation: Explanation | None

    def to_dict(self, content: NutrientContent) -> dict[str, Any]:
        explained = self.explanation is not None
        return {
            "name": self.name,
            "display_name": self.display_name,
            "guidance": self.guidance.value,
            "value": self.value.to_dict() if self.value else None,
            "status": self.status.value,
            "status_text": {
                ValueStatus.VERIFIED: None,
                ValueStatus.NOT_AVAILABLE: NOT_AVAILABLE,
                ValueStatus.NEEDS_CONFIRMATION: NEEDS_CONFIRMATION_MESSAGE,
            }[self.status],
            "daily_value": self.daily_value.to_dict() if self.daily_value else None,
            "what_it_is": (
                _text_dict(self.explanation.what_it_is, content)
                if explained and self.explanation.what_it_is
                else None
            ),
            "how_to_read": (
                _text_dict(self.explanation.how_to_read, content)
                if explained and self.explanation.how_to_read
                else None
            ),
            "explanation_message": None if explained else NO_EXPLANATION_MESSAGE,
        }


@dataclass(frozen=True)
class NutrientExplanationResult:
    basis: NutritionBasis | None
    rows: tuple[NutrientRow, ...]
    content: NutrientContent

    def to_dict(self) -> dict[str, Any]:
        glossary = self.content.glossary["daily_value_percent"]
        return {
            "basis": self.basis.value if self.basis else None,
            "daily_values_reference": {
                "title": DAILY_VALUES_TITLE,
                "url": DAILY_VALUES_URL,
                "version": DAILY_VALUES_VERSION,
            },
            "daily_value_definition": (
                {"term": glossary.term, **_text_dict(glossary.text, self.content)}
                if self.content.is_reviewed
                else None
            ),
            "rows": [row.to_dict(self.content) for row in self.rows],
        }


def _usable(value: NutrientValue | None, name: str, confirmed: frozenset[str]) -> ValueStatus:
    if value is None:
        return ValueStatus.NOT_AVAILABLE
    if value.source is Source.NUTRITION_LABEL_PHOTO:
        confirmed_here = f"nutrition.nutrients.{name}" in confirmed
        return ValueStatus.VERIFIED if confirmed_here else ValueStatus.NEEDS_CONFIRMATION
    return ValueStatus.VERIFIED if value.is_usable else ValueStatus.NOT_AVAILABLE


def _daily_value(
    name: str, value: NutrientValue, amounts: dict[str, float | None]
) -> DailyValue | None:
    if name == "calories":
        return None
    if value.daily_value_percent is not None:
        percent, origin = float(value.daily_value_percent), DailyValueOrigin.LABEL
    else:
        calculated = daily_value_percent(name, amounts)
        if calculated is None:
            return None
        percent, origin = calculated, DailyValueOrigin.CALCULATED
    display = _round_percent(percent)
    return DailyValue(percent, display, origin, interpret(display))


def explain_nutrients(
    product: Product, content: NutrientContent, confirmed: Iterable[str] = ()
) -> NutrientExplanationResult:
    confirmed = frozenset(confirmed)
    nutrition = product.nutrition
    per_serving = nutrition.basis is NutritionBasis.SERVING

    statuses = {name: _usable(nutrition.nutrients[name], name, confirmed) for name in ALL_NUTRIENTS}
    # Only verified amounts feed a calculated %DV, including the combined saturated + trans.
    amounts = {
        name: nutrition.nutrients[name].amount if status is ValueStatus.VERIFIED else None
        for name, status in statuses.items()
    }

    rows = []
    for name in ALL_NUTRIENTS:
        value = nutrition.nutrients[name]
        entry = content.nutrients[name]
        verified = statuses[name] is ValueStatus.VERIFIED
        # %DV is defined per serving; a per-100 g amount is shown without one.
        daily = _daily_value(name, value, amounts) if verified and per_serving else None
        explanation = (
            Explanation(entry.what_it_is, entry.how_to_read)
            if verified
            and content.is_reviewed
            and (entry.what_it_is is not None or entry.how_to_read is not None)
            else None
        )
        rows.append(
            NutrientRow(name, entry.name, entry.guidance, value, statuses[name], daily, explanation)
        )
    return NutrientExplanationResult(nutrition.basis, tuple(rows), content)
