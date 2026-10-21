"""Load the reviewed nutrient explanations (#38) that F3's display (#37) shows.

The content is ``content/nutrients/nutrients.json``; its rules are in that folder's
README. Like the ingredient content (#33), a broken file raises
``NutrientContentError`` rather than silently showing fewer explanations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from app.models.ingredients import IngredientSource, SourcedText
from app.models.product import ALL_NUTRIENTS
from app.services.ingredient_knowledge import (
    CONTENT_DIR as INGREDIENT_CONTENT_DIR,
)
from app.services.ingredient_knowledge import (
    IngredientKnowledgeError,
    _date,
    _id,
    _list,
    _object,
    _read,
    _refs,
    _text,
    load_source_policy,
)

CONTENT_PATH = Path(__file__).resolve().parents[2] / "content" / "nutrients" / "nutrients.json"
# One list of approved source hosts for all reviewed content.
SOURCE_POLICY_PATH = INGREDIENT_CONTENT_DIR / "source-policy.json"


class NutrientContentError(ValueError):
    """Broken nutrient content, not a nutrient without an explanation."""


class Guidance(str, Enum):
    """Whether Health Canada suggests getting less or more of a nutrient. Never a verdict."""

    LIMIT = "limit"
    GET_MORE = "get_more"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class NutrientExplanation:
    id: str
    name: str
    guidance: Guidance
    # None when no reviewed source supports a text yet.
    what_it_is: SourcedText | None
    how_to_read: SourcedText | None


@dataclass(frozen=True)
class GlossaryTerm:
    term: str
    text: SourcedText


@dataclass(frozen=True)
class NutrientContent:
    reviewed_on: str | None
    reviewed_by: str | None
    glossary: MappingProxyType[str, GlossaryTerm]
    sources: MappingProxyType[str, IngredientSource]
    nutrients: MappingProxyType[str, NutrientExplanation]

    @property
    def is_reviewed(self) -> bool:
        """Only reviewed content may be shown as a verified explanation (F3)."""
        return self.reviewed_on is not None


def _sourced(value: Any, known: set[str], path: str) -> SourcedText:
    raw = _object(value, {"text", "source_ids"}, path)
    return SourcedText(_text(raw["text"], f"{path}.text"), _refs(raw["source_ids"], known, path))


def _source(value: Any, allowed_hosts: frozenset[str], path: str) -> IngredientSource:
    raw = _object(value, {"id", "publisher", "title", "url", "published_on", "accessed_on"}, path)
    url = _text(raw["url"], f"{path}.url")
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in allowed_hosts
        or parts.username is not None
        or parts.port not in (None, 443)
    ):
        raise NutrientContentError(f"{path}.url: expected HTTPS on an approved hostname")
    return IngredientSource(
        _id(raw["id"], f"{path}.id"),
        _text(raw["publisher"], f"{path}.publisher"),
        _text(raw["title"], f"{path}.title"),
        url,
        _date(raw["published_on"], f"{path}.published_on", nullable=True),
        _date(raw["accessed_on"], f"{path}.accessed_on"),
    )


def parse_nutrient_content(raw: Any, allowed_hosts: frozenset[str], path: str) -> NutrientContent:
    try:
        return _parse(raw, allowed_hosts, path)
    except IngredientKnowledgeError as exc:
        # The shared validators raise the ingredient error type; report it as ours.
        raise NutrientContentError(str(exc)) from exc


def _parse(raw: Any, allowed_hosts: frozenset[str], path: str) -> NutrientContent:
    raw = _object(
        raw,
        {"schema_version", "reviewed_on", "reviewed_by", "glossary", "sources", "nutrients"},
        path,
    )
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise NutrientContentError(f"{path}: unsupported nutrient schema version")
    reviewed_on = _date(raw["reviewed_on"], f"{path}.reviewed_on", nullable=True)
    reviewed_by = raw["reviewed_by"]
    if reviewed_by is not None:
        _text(reviewed_by, f"{path}.reviewed_by")
    if (reviewed_on is None) != (reviewed_by is None):
        raise NutrientContentError(f"{path}: reviewed_on and reviewed_by go together")

    sources: dict[str, IngredientSource] = {}
    for i, value in enumerate(_list(raw["sources"], f"{path}.sources", nonempty=True)):
        source = _source(value, allowed_hosts, f"{path}.sources[{i}]")
        if source.id in sources:
            raise NutrientContentError(f"{path}.sources[{i}]: duplicate id {source.id!r}")
        sources[source.id] = source
    known = set(sources)

    glossary_raw = raw["glossary"]
    if not isinstance(glossary_raw, dict):
        raise NutrientContentError(f"{path}.glossary: expected an object")
    glossary: dict[str, GlossaryTerm] = {}
    for key, value in glossary_raw.items():
        p = f"{path}.glossary.{key}"
        term = _object(value, {"term", "text", "source_ids"}, p)
        glossary[_id(key, p)] = GlossaryTerm(
            _text(term["term"], f"{p}.term"),
            _sourced({"text": term["text"], "source_ids": term["source_ids"]}, known, p),
        )
    if "daily_value_percent" not in glossary:
        raise NutrientContentError(f"{path}.glossary: %DV needs its definition (#38)")

    nutrients: dict[str, NutrientExplanation] = {}
    for i, value in enumerate(_list(raw["nutrients"], f"{path}.nutrients", nonempty=True)):
        p = f"{path}.nutrients[{i}]"
        entry = _object(value, {"id", "name", "guidance", "what_it_is", "how_to_read"}, p)
        nutrient_id = _id(entry["id"], f"{p}.id")
        if nutrient_id not in ALL_NUTRIENTS:
            raise NutrientContentError(f"{p}.id: unknown nutrient {nutrient_id!r}")
        if nutrient_id in nutrients:
            raise NutrientContentError(f"{p}.id: duplicate nutrient {nutrient_id!r}")
        try:
            guidance = Guidance(entry["guidance"])
        except ValueError:
            raise NutrientContentError(f"{p}.guidance: unknown {entry['guidance']!r}") from None
        texts = {
            key: None if entry[key] is None else _sourced(entry[key], known, f"{p}.{key}")
            for key in ("what_it_is", "how_to_read")
        }
        nutrients[nutrient_id] = NutrientExplanation(
            nutrient_id, _text(entry["name"], f"{p}.name"), guidance, **texts
        )
    missing = [name for name in ALL_NUTRIENTS if name not in nutrients]
    if missing:
        raise NutrientContentError(f"{path}.nutrients: missing {missing}")

    return NutrientContent(
        reviewed_on,
        reviewed_by,
        MappingProxyType(glossary),
        MappingProxyType(sources),
        MappingProxyType(nutrients),
    )


def load_nutrient_content(
    path: Path = CONTENT_PATH, policy_path: Path = SOURCE_POLICY_PATH
) -> NutrientContent:
    try:
        allowed_hosts = load_source_policy(policy_path)
        raw = _read(Path(path))
    except IngredientKnowledgeError as exc:
        raise NutrientContentError(str(exc)) from exc
    return parse_nutrient_content(raw, allowed_hosts, str(path))
