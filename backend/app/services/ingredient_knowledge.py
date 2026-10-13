"""Load a reviewed, versioned JSON collection and build an exact-name index."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import fields
from datetime import date
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

from app.models.ingredients import (
    Authority,
    AuthorityPosition,
    FlagCategory,
    IngredientEntry,
    IngredientFlag,
    IngredientSource,
    SourcedText,
)
from app.services.ingredient_names import normalize_name

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content" / "ingredients"
_ID = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
_NUMBER = re.compile(r"[0-9]{3,4}[a-z]?(?:\([ivx]+\))?\Z")
AUTHORITY_HOSTS = {
    "health_canada": {"canada.ca", "www.canada.ca"},
    "efsa": {"efsa.europa.eu", "www.efsa.europa.eu"},
    "fda": {"fda.gov", "www.fda.gov"},
    "who_jecfa": {"who.int", "www.who.int", "apps.who.int", "cdn.who.int"},
}


class IngredientKnowledgeError(ValueError):
    """Broken configuration/content, not a product with no recognized ingredients."""


def _fail(path: str, message: str):
    raise IngredientKnowledgeError(f"{path}: {message}")


def _object(value, expected: set[str], path: str) -> dict:
    if not isinstance(value, dict):
        _fail(path, "expected an object")
    if set(value) != expected:
        _fail(
            path,
            f"missing fields {sorted(expected - value.keys())}; "
            f"unknown fields {sorted(value.keys() - expected)}",
        )
    return value


def _text(value, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "expected non-blank text")
    return value


def _id(value, path: str) -> str:
    if not _ID.fullmatch(_text(value, path)):
        _fail(path, "expected a lowercase snake_case identifier")
    return value


def _date(value, path: str, nullable: bool = False):
    if nullable and value is None:
        return None
    _text(value, path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _fail(path, "expected a valid YYYY-MM-DD date")
    if parsed.isoformat() != value:
        _fail(path, "expected a YYYY-MM-DD date")
    return value


def _list(value, path: str, nonempty: bool = False) -> list:
    if not isinstance(value, list) or (nonempty and not value):
        _fail(path, "expected a non-empty array" if nonempty else "expected an array")
    return value


def _strings(value, path: str, nonempty: bool = False) -> tuple[str, ...]:
    result = tuple(_text(v, f"{path}[{i}]") for i, v in enumerate(_list(value, path, nonempty)))
    if len(set(result)) != len(result):
        _fail(path, "duplicate values")
    return result


def _refs(value, known: set[str], path: str) -> tuple[str, ...]:
    result = _strings(value, path, nonempty=True)
    if not set(result) <= known:
        _fail(path, f"unknown references {sorted(set(result) - known)}")
    return result


def _shape(value, cls, path):
    return _object(value, {f.name for f in fields(cls)}, path)


def _read(path: Path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail(str(path), f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    except (OSError, UnicodeError, ValueError) as exc:
        raise IngredientKnowledgeError(f"{path}: {exc}") from exc


def load_source_policy(path: Path = CONTENT_DIR / "source-policy.json") -> frozenset[str]:
    raw = _object(_read(path), {"version", "allowed_hosts"}, str(path))
    if type(raw["version"]) is not int or raw["version"] != 1:
        _fail(str(path), "unsupported source-policy version")
    hosts = _strings(raw["allowed_hosts"], f"{path}.allowed_hosts", nonempty=True)
    for host in hosts:
        if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}", host):
            _fail(str(path), f"invalid exact hostname {host!r}")
    return frozenset(hosts)


def parse_entry(raw: dict, allowed_hosts: frozenset[str], path: str) -> IngredientEntry:
    raw = _shape(raw, IngredientEntry, path)
    sources = []
    for i, source in enumerate(_list(raw["sources"], f"{path}.sources", True)):
        p = f"{path}.sources[{i}]"
        source = _shape(source, IngredientSource, p)
        url = _text(source["url"], f"{p}.url")
        try:
            parsed_url = urlsplit(url)
            valid_url = (
                parsed_url.scheme == "https"
                and parsed_url.hostname in allowed_hosts
                and parsed_url.username is None
                and parsed_url.password is None
                and parsed_url.port in (None, 443)
                and not any(c.isspace() for c in url)
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            _fail(f"{p}.url", "expected HTTPS on an explicitly approved hostname")
        sources.append(
            IngredientSource(
                _id(source["id"], f"{p}.id"),
                _text(source["publisher"], f"{p}.publisher"),
                _text(source["title"], f"{p}.title"),
                url,
                _date(source["published_on"], f"{p}.published_on", True),
                _date(source["accessed_on"], f"{p}.accessed_on"),
            )
        )
    source_ids = {s.id for s in sources}
    if len(source_ids) != len(sources):
        _fail(f"{path}.sources", "duplicate source IDs")

    def claim(name):
        p = f"{path}.{name}"
        value = _shape(raw[name], SourcedText, p)
        return SourcedText(
            _text(value["text"], f"{p}.text"),
            _refs(value["source_ids"], source_ids, f"{p}.source_ids"),
        )

    positions = []
    for i, value in enumerate(_list(raw["authority_positions"], f"{path}.authority_positions")):
        p = f"{path}.authority_positions[{i}]"
        value = _shape(value, AuthorityPosition, p)
        authority = _text(value["authority"], f"{p}.authority")
        if authority not in {a.value for a in Authority}:
            _fail(f"{p}.authority", "unrecognized flagging authority")
        refs = _refs(value["source_ids"], source_ids, f"{p}.source_ids")
        for source in sources:
            if (
                source.id in refs
                and urlsplit(source.url).hostname not in AUTHORITY_HOSTS[authority]
            ):
                _fail(f"{p}.source_ids", "position must cite its own authority")
        positions.append(
            AuthorityPosition(
                _id(value["id"], f"{p}.id"),
                authority,
                _text(value["statement"], f"{p}.statement"),
                _text(value["scope"], f"{p}.scope"),
                refs,
                _date(value["assessed_on"], f"{p}.assessed_on", True),
                _date(value["effective_on"], f"{p}.effective_on", True),
            )
        )
    position_ids = {p.id for p in positions}
    if len(position_ids) != len(positions):
        _fail(f"{path}.authority_positions", "duplicate position IDs")
    flag = None
    if raw["flag"] is not None:
        p = f"{path}.flag"
        value = _shape(raw["flag"], IngredientFlag, p)
        category = _text(value["category"], f"{p}.category")
        if category not in {c.value for c in FlagCategory}:
            _fail(f"{p}.category", "unrecognized flag category")
        refs = _refs(value["position_ids"], position_ids, f"{p}.position_ids")
        supporting = [position for position in positions if position.id in refs]
        if category == "conflicting_assessments" and len({p.authority for p in supporting}) < 2:
            _fail(p, "conflict requires at least two distinct authorities")
        supported_sources = {s for position in supporting for s in position.source_ids}
        flag = IngredientFlag(
            _text(value["flag_reason"], f"{p}.flag_reason"),
            category,
            _refs(value["source_ids"], supported_sources, f"{p}.source_ids"),
            refs,
        )

    identifiers = {}
    for field, prefix in (("e_numbers", "E"), ("ins_numbers", "INS ")):
        identifiers[field] = _strings(raw[field], f"{path}.{field}")
        for identifier in identifiers[field]:
            if not identifier.startswith(prefix) or not _NUMBER.fullmatch(
                identifier[len(prefix) :]
            ):
                _fail(f"{path}.{field}", f"expected {prefix} followed by an explicit number/suffix")
    return IngredientEntry(
        _id(raw["id"], f"{path}.id"),
        _text(raw["name"], f"{path}.name"),
        _strings(raw["aliases"], f"{path}.aliases"),
        **identifiers,
        what_it_is=claim("what_it_is"),
        why_used=claim("why_used"),
        explanation=claim("explanation"),
        sources=tuple(sources),
        last_reviewed=_date(raw["last_reviewed"], f"{path}.last_reviewed"),
        authority_positions=tuple(positions),
        flag=flag,
    )


class IngredientKnowledgeBase:
    """Validated immutable collection; an empty collection is valid for #33."""

    def __init__(self, documents: Iterable[tuple[str, dict]], allowed_hosts: frozenset[str]):
        entries: dict[str, IngredientEntry] = {}
        index: dict[str, IngredientEntry] = {}
        for path, document in documents:
            entry = parse_entry(document, allowed_hosts, path)
            if entry.id in entries:
                _fail(path, f"duplicate canonical ID {entry.id!r}")
            entries[entry.id] = entry
            for name in (entry.name, *entry.aliases, *entry.e_numbers, *entry.ins_numbers):
                key = normalize_name(name)
                if not key:
                    _fail(path, "name/alias normalizes to empty text")
                if key in index and index[key].id != entry.id:
                    _fail(path, f"name {name!r} collides with {index[key].id!r}")
                index[key] = entry
        self.entries: Mapping[str, IngredientEntry] = MappingProxyType(entries)
        self.index: Mapping[str, IngredientEntry] = MappingProxyType(index)

    def match(self, text: str) -> IngredientEntry | None:
        return self.index.get(normalize_name(text))


def load_ingredient_knowledge(directory: Path = CONTENT_DIR) -> IngredientKnowledgeBase:
    directory = Path(directory)
    allowed_hosts = load_source_policy(directory / "source-policy.json")
    entries_dir = directory / "entries"
    if not entries_dir.is_dir():
        _fail(str(entries_dir), "missing entries directory")
    documents = []
    for path in sorted(entries_dir.glob("*.json")):
        raw = _object(_read(path), {"schema_version", "ingredient"}, str(path))
        if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
            _fail(str(path), "unsupported ingredient schema version")
        documents.append((str(path), raw["ingredient"]))
    return IngredientKnowledgeBase(documents, allowed_hosts)
