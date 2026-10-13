"""Ingredient content and the reusable F4 result contract (#33).

Content is constructed by the validating knowledge-base loader. These immutable
objects contain reviewed text, never explanations generated at request time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class IngredientStatus(str, Enum):
    UNAVAILABLE = "unavailable"
    NO_MATCHES = "no_matches"
    ANALYZED = "analyzed"


class Authority(str, Enum):
    HEALTH_CANADA = "health_canada"
    EFSA = "efsa"
    FDA = "fda"
    WHO_JECFA = "who_jecfa"


class FlagCategory(str, Enum):
    AUTHORITY_ACTION = "authority_action"
    CONFLICTING_ASSESSMENTS = "conflicting_assessments"


@dataclass(frozen=True)
class SourcedText:
    text: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class IngredientSource:
    id: str
    publisher: str
    title: str
    url: str
    published_on: str | None
    accessed_on: str


@dataclass(frozen=True)
class AuthorityPosition:
    id: str
    authority: str
    statement: str
    scope: str
    source_ids: tuple[str, ...]
    assessed_on: str | None
    effective_on: str | None


@dataclass(frozen=True)
class IngredientFlag:
    flag_reason: str
    category: str
    source_ids: tuple[str, ...]
    position_ids: tuple[str, ...]


def _json_value(value: Any) -> Any:
    """Convert dataclass tuples to actual JSON arrays before comparing contracts."""
    if isinstance(value, dict):
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


@dataclass(frozen=True)
class IngredientEntry:
    id: str
    name: str
    aliases: tuple[str, ...]
    e_numbers: tuple[str, ...]
    ins_numbers: tuple[str, ...]
    what_it_is: SourcedText
    why_used: SourcedText
    explanation: SourcedText
    sources: tuple[IngredientSource, ...]
    last_reviewed: str
    authority_positions: tuple[AuthorityPosition, ...]
    flag: IngredientFlag | None

    @property
    def flagged(self) -> bool:
        return self.flag is not None

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class IngredientOccurrence:
    text: str
    path: tuple[int, ...]


@dataclass(frozen=True)
class MatchedIngredient:
    ingredient: IngredientEntry
    occurrences: tuple[IngredientOccurrence, ...]


@dataclass(frozen=True)
class UnmatchedIngredient:
    text: str
    occurrences: tuple[IngredientOccurrence, ...]


@dataclass(frozen=True)
class IngredientWarning:
    code: str
    text: str


@dataclass(frozen=True)
class IngredientAnalysisResult:
    status: IngredientStatus
    matched: tuple[MatchedIngredient, ...] = ()
    unmatched: tuple[UnmatchedIngredient, ...] = ()
    warnings: tuple[IngredientWarning, ...] = ()

    @property
    def checked_count(self) -> int:
        return len(self.matched)

    @property
    def total_count(self) -> int:
        return len(self.matched) + len(self.unmatched)

    @property
    def flagged_ids(self) -> list[str]:
        return [m.ingredient.id for m in self.matched if m.ingredient.flagged]

    def to_dict(self) -> dict[str, Any]:
        message = None
        if self.status is IngredientStatus.UNAVAILABLE:
            message = "Ingredient information not available"
        elif self.status is IngredientStatus.NO_MATCHES:
            message = "No verified ingredient analysis available."
        elif not self.flagged_ids:
            message = "No flagged ingredients found among the ingredients checked."
        return {
            "status": self.status.value,
            "checked_count": self.checked_count,
            "total_count": self.total_count,
            "flagged_count": len(self.flagged_ids),
            "matched": [_json_value(asdict(m)) for m in self.matched],
            "unmatched": [_json_value(asdict(u)) for u in self.unmatched],
            "flagged_ids": self.flagged_ids,
            "warnings": [_json_value(asdict(w)) for w in self.warnings],
            "message": message,
            "coverage_text": (
                f"Checked {self.checked_count} of {self.total_count} ingredients "
                "against our reviewed ingredient database."
            ),
        }
