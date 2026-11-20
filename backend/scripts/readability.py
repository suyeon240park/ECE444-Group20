"""Q3 readability check (#70): Flesch-Kincaid grade of the app's explanation text.

Runs the same services as the results page, so the scored text is what a user sees:

- nutrient explanations (#37, F3): the %DV definition, then each nutrient's
  "what it is" and "how to read" text;
- ingredient explanations (#33, F4): each matched ingredient's "what it is",
  "why it is used" and explanation, its flag reason and authority statements.

Preprocessing follows Q3 in docs/requirements.md:

- product names and brands, and ingredient names, aliases and E/INS numbers, are removed;
- source citations and URLs are removed (sources are separate fields and are never
  scored; URLs or "(Source: ...)" left inside a text are stripped as well);
- technical terms defined in the UI may be removed: by default "%DV", which the
  results page defines in its own glossary box (``--keep-defined-terms`` keeps it).

Each product's explanation text is joined into one passage and graded; the result is
the mean grade over the products, passing at 8 or below. Q3 asks for a long combined
sample rather than one-sentence passages, so single texts are listed only to show
which ones to rewrite first.

Run from ``backend/``::

    python -m scripts.readability                       # default test products
    python -m scripts.readability --product my.json ... # OFF responses to score
    python -m scripts.readability --json                # machine-readable output

Exit status: 0 pass, 1 fail, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.product import Product
from app.services.analysis import confirmed_paths
from app.services.ingredient_analysis import IngredientAnalysisService
from app.services.ingredient_knowledge import IngredientKnowledgeBase, load_ingredient_knowledge
from app.services.normalize import normalize_off_product
from app.services.nutrient_content import NutrientContent, load_nutrient_content
from app.services.nutrient_explanations import explain_nutrients

TARGET_GRADE = 8.0

_OFF_FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "off"
# Real OFF records, one per category, so the default run covers Q3's "at least 3
# packaged-food categories". Use --product for the usability-test products (#69).
DEFAULT_PRODUCTS = (
    (_OFF_FIXTURES / "ketchup_found.json", "condiment"),
    (_OFF_FIXTURES / "nutella_found.json", "spread"),
    (_OFF_FIXTURES / "oatmeal_squares_found.json", "breakfast cereal"),
)

# Defined in the results page's own glossary box (daily_value_definition).
DEFINED_TERMS = ("% DV", "%DV")

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_CITATION = re.compile(
    r"\((?:source|sources|see|from)\s*:[^)]*\)|\[\s*\d+(?:\s*[,-]\s*\d+)*\s*\]", re.IGNORECASE
)
# Abbreviations whose full stop does not end a sentence.
_ABBREVIATIONS = re.compile(r"\b(?:e\.g|i\.e|etc|vs|approx|U\.S|Dr|Mr|Mrs|Ms|No)\.", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
_WORD = re.compile(r"[A-Za-z0-9]+(?:['’.-][A-Za-z0-9]+)*")


# --- Flesch-Kincaid --------------------------------------------------------------------


def count_syllables(word: str) -> int:
    """Syllables in an English word, by the usual vowel-group rules. At least 1.

    A heuristic, like every syllable counter used for readability scores; it is
    deterministic so the grade only changes when the text does.
    """
    word = word.lower().replace("’", "'")
    if any(ch.isdigit() for ch in word):
        # A number is read as one word; its spelling out is not scored.
        return 1
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    if re.search(r"[^aeiouy]le$", word):
        stem, extra = word[:-2], 1  # "table", "vegetable": the final -le is a syllable
    else:
        stem = re.sub(r"(?:[^laeiouy]es|[^tdaeiouy]ed|[^laeiouy]e)$", lambda m: m.group()[0], word)
        extra = 0
    groups = len(re.findall(r"[aeiouy]+", stem))
    return max(1, groups + extra)


def sentences(text: str) -> list[str]:
    protected = _ABBREVIATIONS.sub(lambda m: m.group().replace(".", "\0"), text)
    parts = (p.replace("\0", ".").strip() for p in _SENTENCE_END.split(protected))
    return [p for p in parts if _WORD.search(p)]


def words(text: str) -> list[str]:
    return _WORD.findall(text)


@dataclass(frozen=True)
class Score:
    sentences: int
    words: int
    syllables: int

    @property
    def grade(self) -> float | None:
        if not self.sentences or not self.words:
            return None
        return 0.39 * self.words / self.sentences + 11.8 * self.syllables / self.words - 15.59


def score(text: str) -> Score:
    found = sentences(text)
    tokens = [w for s in found for w in words(s)]
    return Score(len(found), len(tokens), sum(count_syllables(w) for w in tokens))


# --- Preprocessing ---------------------------------------------------------------------


def _name_pattern(names: Iterable[str]) -> re.Pattern[str] | None:
    cleaned = sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True)
    if not cleaned:
        return None
    alternatives = "|".join(re.escape(n) for n in cleaned)
    # A digit may come first: "5% DV".
    return re.compile(rf"(?<![A-Za-z%])(?:{alternatives})(?!\w)", re.IGNORECASE)


def preprocess(text: str, names: Iterable[str] = (), terms: Iterable[str] = ()) -> str:
    """Q3's preprocessing: drop URLs, citations, proper names and defined terms."""
    text = _URL.sub(" ", text)
    text = _CITATION.sub(" ", text)
    for pattern in (_name_pattern(names), _name_pattern(terms)):
        if pattern is not None:
            text = pattern.sub(" ", text)
    text = re.sub(r"\(\s*\)|\[\s*\]", " ", text)  # brackets emptied by the removals
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


# --- Collecting the explanation text ---------------------------------------------------


@dataclass(frozen=True)
class Text:
    where: str  # e.g. "nutrient sodium / how_to_read"
    raw: str
    scored: str


@dataclass
class ProductReport:
    label: str
    category: str
    texts: list[Text] = field(default_factory=list)

    @property
    def passage(self) -> str:
        return " ".join(t.scored for t in self.texts if t.scored)

    @property
    def score(self) -> Score:
        return score(self.passage)


def load_product(path: Path) -> Product:
    """An OFF v3 response (``{"product": {...}}``) or the bare product object."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: not a JSON object")
    product = raw.get("product", raw)
    if not isinstance(product, dict):
        raise ValueError(f"{path}: no product object")
    barcode = str(product.get("code") or raw.get("code") or "")
    return normalize_off_product(product, barcode, datetime.now(timezone.utc))


def collect(
    product: Product,
    content: NutrientContent,
    knowledge: IngredientKnowledgeBase,
    keep_defined_terms: bool = False,
    category: str = "",
) -> ProductReport:
    """The explanation text the results page shows for ``product``, preprocessed."""
    nutrients = explain_nutrients(product, content, confirmed_paths(product)).to_dict()
    ingredients = IngredientAnalysisService(knowledge).analyze(product).to_dict()

    entries = [m["ingredient"] for m in ingredients["matched"]]
    # A brand field can list several brands: "Alpen, Post".
    names = [product.name or "", product.brand or "", *(product.brand or "").split(",")]
    for entry in entries:
        names += [entry["name"], *entry["aliases"], *entry["e_numbers"], *entry["ins_numbers"]]
    terms = () if keep_defined_terms else DEFINED_TERMS

    found: list[tuple[str, str]] = []
    definition = nutrients["daily_value_definition"]
    if definition:
        found.append(("glossary %DV", definition["text"]))
    for row in nutrients["rows"]:
        for key in ("what_it_is", "how_to_read"):
            if row[key]:
                found.append((f"nutrient {row['name']} / {key}", row[key]["text"]))
    for entry in entries:
        for key in ("what_it_is", "why_used", "explanation"):
            found.append((f"ingredient {entry['id']} / {key}", entry[key]["text"]))
        if entry["flag"]:
            found.append((f"ingredient {entry['id']} / flag", entry["flag"]["flag_reason"]))
        for position in entry["authority_positions"]:
            found.append((f"ingredient {entry['id']} / {position['id']}", position["statement"]))

    label = product.name or product.barcode
    report = ProductReport(f"{label} ({product.barcode})", category)
    for where, raw in found:
        report.texts.append(Text(where, raw, preprocess(raw, names, terms)))
    return report


# --- Report ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    products: list[ProductReport]
    mean_grade: float | None
    pooled: Score

    @property
    def passed(self) -> bool:
        return self.mean_grade is not None and self.mean_grade <= TARGET_GRADE


def evaluate(reports: Sequence[ProductReport]) -> Result:
    grades = [r.score.grade for r in reports if r.score.grade is not None]
    # Each distinct text once, so text shared by every product is not counted 3 times.
    unique = dict.fromkeys(t.scored for r in reports for t in r.texts if t.scored)
    return Result(
        list(reports),
        statistics.fmean(grades) if grades else None,
        score(" ".join(unique)),
    )


def _fmt(grade: float | None) -> str:
    return "n/a" if grade is None else f"{grade:.1f}"


def hardest_texts(result: Result, limit: int = 5) -> list[tuple[float, Text]]:
    seen: dict[str, tuple[float, Text]] = {}
    for report in result.products:
        for text in report.texts:
            grade = score(text.scored).grade
            if grade is not None and text.scored not in seen:
                seen[text.scored] = (grade, text)
    return sorted(seen.values(), key=lambda pair: pair[0], reverse=True)[:limit]


def to_markdown(result: Result, keep_defined_terms: bool) -> str:
    verdict = "PASS" if result.passed else "FAIL"
    lines = [
        "## Q3 readability (Flesch-Kincaid)",
        "",
        f"**Mean grade: {_fmt(result.mean_grade)}** (target {TARGET_GRADE:g} or below): "
        f"**{verdict}**",
        "",
        "| Product | Category | Texts | Sentences | Words | Grade |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for report in result.products:
        s = report.score
        lines.append(
            f"| {report.label} | {report.category or '-'} | {len(report.texts)} | "
            f"{s.sentences} | {s.words} | {_fmt(s.grade)} |"
        )
    pooled = result.pooled
    lines += [
        "",
        f"All distinct texts pooled into one passage: grade {_fmt(pooled.grade)} "
        f"({pooled.sentences} sentences, {pooled.words} words).",
        "",
        "Preprocessing: product names and brands, ingredient names, aliases and E/INS "
        "numbers, source citations and URLs removed; "
        + (
            "defined terms kept."
            if keep_defined_terms
            else '"%DV" removed (defined in the results page\'s glossary box).'
        ),
        "",
        "### Hardest texts (rewrite these first)",
        "",
        "| Grade | Where | Text |",
        "|---:|---|---|",
    ]
    for grade, text in hardest_texts(result):
        lines.append(f"| {grade:.1f} | {text.where} | {text.raw.replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def to_json(result: Result) -> dict[str, Any]:
    return {
        "target_grade": TARGET_GRADE,
        "mean_grade": result.mean_grade,
        "passed": result.passed,
        "pooled": {**result.pooled.__dict__, "grade": result.pooled.grade},
        "products": [
            {
                "product": r.label,
                "category": r.category,
                "sentences": r.score.sentences,
                "words": r.score.words,
                "syllables": r.score.syllables,
                "grade": r.score.grade,
                "texts": [{"where": t.where, "scored": t.scored} for t in r.texts],
            }
            for r in result.products
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--product",
        action="append",
        type=Path,
        metavar="PATH[=CATEGORY]",
        help="Open Food Facts response JSON to score; repeat for each product. "
        "Append =category to label it. Default: three fixtures in tests/fixtures/off.",
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    parser.add_argument(
        "--keep-defined-terms", action="store_true", help='score "%%DV" instead of removing it'
    )
    args = parser.parse_args(argv)

    if args.product:
        targets = []
        for item in args.product:
            path, _, category = str(item).partition("=")
            targets.append((Path(path), category))
    else:
        targets = list(DEFAULT_PRODUCTS)

    content = load_nutrient_content()
    knowledge = load_ingredient_knowledge()
    reports = []
    for path, category in targets:
        try:
            product = load_product(path)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        reports.append(collect(product, content, knowledge, args.keep_defined_terms, category))

    result = evaluate(reports)
    if args.json:
        print(json.dumps(to_json(result), indent=2))
    else:
        sys.stdout.write(to_markdown(result, args.keep_defined_terms))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
