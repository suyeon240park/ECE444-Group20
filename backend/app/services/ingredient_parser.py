"""Bounded structural parsing of OFF text; ambiguous spans remain unmatched.

This is deliberately not an OCR repair or language model. A candidate carries
both its original label text and its lookup form, including narrow oil context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.ingredients import IngredientWarning
from app.services.ingredient_knowledge import IngredientKnowledgeBase
from app.services.ingredient_names import IDENTIFIER, normalize_name

MAX_TEXT_LENGTH = 50_000
MAX_DEPTH = 32
_HEADING = re.compile(r"\bingr[eé]dients\s*:\s*", re.IGNORECASE)
_LEADING_HEADING = re.compile(r"^\s*ingr[eé]dients\b\s*:?\s*", re.IGNORECASE)
_GROUPS = {
    "sugars",
    "sucres",
    "colour",
    "colours",
    "color",
    "colors",
    "colorant",
    "colorants",
    "emulsifier",
    "emulsifiers",
    "émulsifiant",
    "émulsifiants",
    "preservative",
    "preservatives",
    "agent de conservation",
    "agents de conservation",
}
_ANNOTATIONS = {
    "for colour",
    "for color",
    "for freshness",
    "pour la couleur",
    "pour préserver la fraîcheur",
    "preservative",
    "emulsifier",
    "antioxidant",
    "colour",
    "color",
    "colorant",
    "émulsifiant",
    "agent de conservation",
}
_IGNORE = re.compile(
    r"^(?:contains\b|may contain\b|contient\b|peut contenir\b|"
    r"gluten[- ]free\b|sans gluten\b|sans gélatine\b|sans agent de conservation\b|"
    r"made with\b|fait (?:de|à partir)\b|keep refrigerated\b|garder au réfrigérateur\b)",
    re.I,
)
_CONJUNCTION = re.compile(r"\s+(?:and\s*/\s*or|et\s*/\s*ou|and|or|et|ou)\s+|\s*/\s*", re.I)
_COMPOUND_NAMES = {
    "mono- and diglycerides",
    "mono- et diglycérides",
    "monoglycerides and diglycerides",
    "mono- and di-glycerides",
}
_OIL_WRAPPERS = {"vegetable oil", "vegetable oils", "huile végétale", "huiles végétales"}
_OIL_COMPONENTS = {
    "corn": "corn oil",
    "canola": "canola oil",
    "soybean": "soybean oil",
    "sunflower": "sunflower oil",
    "cottonseed": "cottonseed oil",
    "maïs": "huile de maïs",
    "soja": "huile de soja",
    "tournesol": "huile de tournesol",
}


@dataclass(frozen=True)
class IngredientCandidate:
    text: str
    lookup_text: str
    path: tuple[int, ...]
    force_unmatched: bool = False


@dataclass(frozen=True)
class ParsedIngredients:
    candidates: tuple[IngredientCandidate, ...]
    warnings: tuple[IngredientWarning, ...]


def _split(text: str) -> tuple[list[str], bool, bool]:
    """Split delimiters outside nesting. Return false for any unbalanced group."""
    parts, stack, sentences = [], [], []
    start = 0
    sentence_start = 0
    for i, char in enumerate(text):
        if char in "([":
            stack.append(char)
        elif char in ")]":
            if not stack or stack.pop() != {"\u0029": "(", "]": "["}[char]:
                return [text], False, False
        elif not stack:
            delimiter = char in ",;•\n\r"
            if char in "\n\r":
                sentences.append(text[sentence_start:i])
                sentence_start = i + 1
            # Numeric chemical locants and French decimal percentages are not lists.
            if char == "," and i and i + 1 < len(text):
                delimiter = not (text[i - 1].isdigit() and text[i + 1].isdigit())
            if char == ".":
                before = text[start:i].rstrip().casefold()
                after = text[i + 1 :]
                delimiter = (not after or after[0].isspace()) and not (
                    before.endswith(("no", "vit")) or (after.lstrip()[:1].isdigit())
                )
                if delimiter:
                    sentences.append(text[sentence_start:i])
                    sentence_start = i + 1
            if delimiter:
                parts.append(text[start:i])
                start = i + 1
    if stack:
        return [text], False, False
    parts.append(text[start:])
    sentences.append(text[sentence_start:])
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > 1:
        return sentences, True, True
    return [p.strip() for p in parts if p.strip()], True, False


def _groups(text: str) -> tuple[str, list[str], str]:
    """Read immediate child groups from an already balanced token."""
    start = next((i for i, c in enumerate(text) if c in "(["), len(text))
    if start == len(text):
        return text, [], ""
    children, depth, opening, last = [], 0, start, start
    tails = []
    for i in range(start, len(text)):
        if text[i] in "([":
            if depth == 0:
                tails.append(text[last:i])
                opening = i
            depth += 1
        elif text[i] in ")]":
            depth -= 1
            if depth == 0:
                children.append(text[opening + 1 : i])
                last = i + 1
    tails.append(text[last:])
    return text[:start].strip(), children, " ".join(tails).strip()


def _alternatives(text: str) -> list[str]:
    """Split conjunctions only outside groups, without dropping later groups."""
    top_level = set()
    depth = 0
    for i, char in enumerate(text):
        if depth == 0:
            top_level.add(i)
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
    parts, start = [], 0
    for match in _CONJUNCTION.finditer(text):
        if match.start() in top_level:
            parts.append(text[start : match.start()])
            start = match.end()
    parts.append(text[start:])
    return parts if all(p.strip() for p in parts) else [text]


def parse_ingredients(text: str, knowledge: IngredientKnowledgeBase) -> ParsedIngredients:
    candidates: list[IngredientCandidate] = []
    warnings: list[IngredientWarning] = []

    def warn(code, raw):
        warnings.append(IngredientWarning(code, raw))

    def add(raw, lookup, path, uncertain=False):
        if normalize_name(lookup):
            candidates.append(IngredientCandidate(raw.strip(), lookup.strip(), path, uncertain))

    def leaf(raw, lookup, path, oil):
        key = normalize_name(lookup)
        if oil:
            if key in _OIL_COMPONENTS:
                lookup = _OIL_COMPONENTS[key]
            elif not (key.endswith(" oil") or key.startswith("huile ")):
                warn("ambiguous_oil_component", raw)
                add(raw, lookup, path, True)
                return
        add(raw, lookup, path)

    def visit(raw: str, path: tuple[int, ...], depth=0, oil=False, component=False):
        value = raw.strip()
        if not value:
            return
        if depth > MAX_DEPTH:
            warn("nesting_limit", value)
            add(raw, value, path, True)
            return
        value = _LEADING_HEADING.sub("", value)
        if not normalize_name(value):
            return
        parts, balanced, sentence_split = _split(value)
        if sentence_split:
            for i, part in enumerate(parts):
                visit(part, (*path, i), depth + 1, oil, component)
            return
        declaration = re.match(r"^(?:contains|contient)\b\s*:?\s*", value, re.I)
        if component and declaration:
            value = value[declaration.end() :]
            parts, balanced, _ = _split(value)
        elif _IGNORE.match(value):
            # Discard the whole advisory, including any comma-separated list.
            return
        if not balanced:
            warn("unbalanced_brackets", value)
            add(raw, value, path, True)
            return
        oil_name = normalize_name(value)
        if oil and oil_name in _OIL_COMPONENTS:
            add(raw, _OIL_COMPONENTS[oil_name], path)
            return
        explicit_oil = oil_name.endswith(" oil") or oil_name.startswith("huile ")
        if knowledge.match(value) and (not oil or explicit_oil):
            add(raw, value, path)
            return
        if len(parts) > 1:
            for i, part in enumerate(parts):
                if not component and _IGNORE.match(part):
                    break  # Remaining comma-separated words belong to this advisory.
                visit(part, (*path, i), depth + 1, oil, component)
            return
        key = normalize_name(value)
        if key in _COMPOUND_NAMES or IDENTIFIER.fullmatch(key):
            leaf(raw, value, path, oil)
            return
        # A bounded suffix percentage annotates ingredient proportion. Leading
        # percentages and qualifiers (e.g. 2% milk) are preserved.
        value = re.sub(r"\s+\d+(?:[.,]\d+)?\s*%\s*$", "", value)
        key = normalize_name(value)
        if knowledge.match(value) and (not oil or explicit_oil):
            add(raw, value, path)
            return
        alternatives = _alternatives(value)
        if len(alternatives) > 1:
            for i, part in enumerate(alternatives):
                visit(part, (*path, i), depth + 1, oil, component)
            return
        head, children, tail = _groups(value)
        if children:
            # Functional annotations and synonymous parentheticals are not new
            # ingredients. A whole-token alias may describe source (lecithin (soy)).
            head_match = knowledge.match(head)
            substantive = []
            for child in children:
                child_match = knowledge.match(child)
                if normalize_name(child) in _ANNOTATIONS:
                    continue
                if re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*%\s*", child):
                    continue
                if head_match and child_match and head_match.id == child_match.id:
                    continue
                substantive.append(child)
            if tail:
                warn("ambiguous_group", value)
                add(raw, value, path, True)
                return
            wrapper = normalize_name(head) in _GROUPS and bool(substantive)
            if head and not substantive:
                leaf(raw, head, path, oil)
                return
            if head and not wrapper:
                visit(head, (*path, 0), depth + 1, oil, component)
            for i, child in enumerate(substantive, 1):
                visit(child, (*path, i), depth + 1, normalize_name(head) in _OIL_WRAPPERS, True)
            return
        leaf(raw, value, path, oil)

    if len(text) > MAX_TEXT_LENGTH:
        return ParsedIngredients(
            (IngredientCandidate(text, text, (0,), True),),
            (IngredientWarning("text_limit", "Ingredient list exceeds the supported length."),),
        )
    nesting = 0
    for char in text:
        if char in "([":
            nesting += 1
            if nesting > MAX_DEPTH:
                return ParsedIngredients(
                    (IngredientCandidate(text, text, (0,), True),),
                    (IngredientWarning("nesting_limit", "Ingredient list is nested too deeply."),),
                )
        elif char in ")]":
            nesting = max(0, nesting - 1)
    # Explicit headings start independent lists even if the preceding language
    # is malformed. Do not turn non-ingredient preamble into food candidates.
    sections = _HEADING.split(text)
    if len(sections) > 1 and sections[0].strip():
        prefix = sections[0].strip()
        prefix_parts, balanced, _ = _split(prefix)
        if balanced and len(prefix_parts) == 1 and not knowledge.match(prefix):
            warn("ignored_preamble", prefix)
            sections[0] = ""
    for i, section in enumerate(sections):
        visit(section, (i,))
    if text.strip() and not candidates:
        warn(
            "no_ingredient_candidates",
            "No ingredient names could be parsed from the supplied text.",
        )
    return ParsedIngredients(tuple(candidates), tuple(warnings))
