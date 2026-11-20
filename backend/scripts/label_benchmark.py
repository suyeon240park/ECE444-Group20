"""Score vision-model label extraction against hand-transcribed labels (#16, Q1).

    python -m scripts.label_benchmark                  # every photo in the fixtures folder
    python -m scripts.label_benchmark --out results/   # also save each reply as JSON
    python -m scripts.label_benchmark --from results/  # re-score saved replies, no API calls

Prints a Markdown report: the verdict against Q1, per-photo counts, every mismatch,
per-field accuracy, the critical serving fields on their own, response time and cost.
Scoring follows Q1: a field not printed on the label is left out of the accuracy
denominator, and whitespace and unit spacing are ignored ("1 g" equals "1g").

Exit status: 0 when Q1 is met, 1 when the run is not usable (a setup error, or photos
that could not be read because of an API error such as a quota limit, so the run is
INCOMPLETE and must be repeated), 2 when the run misses the target (#18), so CI can
fail an extraction change that makes the reading worse.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.models.package_nutrition import PackageNutritionStatus
from app.models.product import Certainty, DataSource, Product, Source
from app.services.label_extraction import (
    MIME_TYPES,
    NUTRIENT_UNITS,
    LabelExtractionError,
    VisionConfig,
    extract_label_file,
)
from app.services.label_reading import to_contract
from app.services.package_nutrition import calculate_package_nutrition

DEFAULT_FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "nutrition_labels"

# Every field the ground truth may list (Q1's atomic fields), plus "status" for
# photos without a Nutrition Facts table.
FIELDS: tuple[str, ...] = (
    "status",
    "serving.household",
    "serving.quantity",
    "package.servings_per_package",
    *(f"nutrition.nutrients.{n}.amount" for n in NUTRIENT_UNITS),
    *(f"nutrition.nutrients.{n}.daily_value_percent" for n in NUTRIENT_UNITS if n != "calories"),
)

COUNTED = ("correct", "wrong", "missing")

EXIT_INCOMPLETE = 1
EXIT_BELOW_TARGET = 2

# Q1's target: at least 95% aggregate field-level accuracy. Change it only through a
# reviewed requirements revision (docs/requirements.md, Q1 verification step 8).
TARGET_ACCURACY = 95.0

# Q1's critical multiplier fields: the values that set F2's serving multiplier. A photo
# value for either must never be used before the user confirms it (safe use).
CRITICAL_FIELDS: tuple[str, ...] = ("serving.quantity", "package.servings_per_package")

# Written in ground_truth.csv for a field the label does not print.
NOT_PRINTED = "-"

# The "status" values a photo may have: no Nutrition Facts table, or one a human
# reviewer cannot read. Q1 leaves unreadable photos out of the accuracy and tracks
# them separately as unsupported input.
NOT_FOUND = "not_found"
UNREADABLE = "unreadable"


@dataclass(frozen=True)
class TruthRow:
    field: str
    expected: str  # "" when the field is not printed on the label
    unit: str


@dataclass(frozen=True)
class Record:
    """One photo's extraction, as saved with --out."""

    image: str
    result: dict[str, Any] | None
    error: str | None = None
    model: str | None = None
    latency_seconds: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Score:
    image: str
    field: str
    expected: str
    actual: str
    outcome: str  # correct | wrong | missing | extra | absent | unsupported


def load_truth(path: Path) -> dict[str, list[TruthRow]]:
    truth: dict[str, list[TruthRow]] = defaultdict(list)
    # utf-8-sig: Excel's "CSV UTF-8" starts the file with a byte-order mark.
    with path.open(newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            field = (row.get("field") or "").strip()
            if field not in FIELDS:
                raise ValueError(f"{path.name} line {line}: unknown field {field!r}")
            image = (row.get("image") or "").strip()
            if not image:
                raise ValueError(f"{path.name} line {line}: missing image")
            # A blank cell is an unfinished transcription, not "not printed", so
            # forgetting a value can never silently shrink the denominator.
            expected = (row.get("expected") or "").strip()
            if not expected:
                raise ValueError(
                    f"{path.name} line {line}: {field} has no expected value "
                    f"(use {NOT_PRINTED} if the label does not print it)"
                )
            if field == "status" and expected not in (NOT_FOUND, UNREADABLE):
                raise ValueError(
                    f"{path.name} line {line}: status must be {NOT_FOUND} or {UNREADABLE}"
                )
            if expected == NOT_PRINTED:
                expected = ""
            truth[image].append(TruthRow(field, expected, (row.get("unit") or "").strip()))
    return dict(truth)


def lookup(result: dict[str, Any], field: str) -> tuple[Any, str | None]:
    """The value at a dotted path and its unit, if the value has one."""
    *parents, key = field.split(".")
    node: Any = result
    for part in parents:
        node = node.get(part) if isinstance(node, dict) else None
    if not isinstance(node, dict):
        return None, None
    unit = node.get("unit") if key in ("amount", "quantity") else None
    return node.get(key), unit


def _norm(text: str) -> str:
    """Ignore case, whitespace and abbreviation dots: "1 tsp." equals "1tsp"."""
    return re.sub(r"[\s.]+", "", text).lower()


def _matches(expected: str, unit: str, actual: Any, actual_unit: str | None) -> bool:
    if unit and _norm(unit) != _norm(actual_unit or ""):
        return False
    try:
        return abs(float(expected) - float(actual)) < 1e-9
    except (TypeError, ValueError):
        return _norm(expected) == _norm(str(actual))


def score_image(image: str, rows: list[TruthRow], record: Record | None) -> list[Score]:
    result = record.result if record else None
    status_row = next((r for r in rows if r.field == "status"), None)
    actual_status = result.get("status", "") if result else ""

    if status_row and status_row.expected == UNREADABLE:
        return [Score(image, "status", UNREADABLE, actual_status, "unsupported")]
    if status_row and status_row.expected == NOT_FOUND:
        outcome = (
            "correct" if actual_status == NOT_FOUND else ("wrong" if actual_status else "missing")
        )
        return [Score(image, "status", NOT_FOUND, actual_status, outcome)]

    scores = []
    for row in rows:
        if row.field == "status":
            continue
        actual, actual_unit = lookup(result, row.field) if result else (None, None)
        shown = (
            "" if actual is None else f"{actual:g}" if isinstance(actual, float) else str(actual)
        )
        if actual_unit and shown:
            shown += f" {actual_unit}"
        if not row.expected:
            outcome = "absent" if actual is None else "extra"
        elif actual is None:
            outcome = "missing"
        else:
            outcome = (
                "correct" if _matches(row.expected, row.unit, actual, actual_unit) else "wrong"
            )
        expected = f"{row.expected} {row.unit}".strip()
        scores.append(Score(image, row.field, expected, shown, outcome))
    return scores


def accuracy(scores: list[Score]) -> tuple[int, int]:
    counted = [s for s in scores if s.outcome in COUNTED]
    return sum(s.outcome == "correct" for s in counted), len(counted)


@dataclass(frozen=True)
class Evaluation:
    """The scores of one run and whether they meet Q1."""

    scores: list[Score]
    correct: int
    total: int
    target: float
    unsafe: list[str]  # photos whose critical values could be used without confirmation
    failed: list[str] = dataclasses.field(default_factory=list)  # photos the API call failed for

    @property
    def accuracy_met(self) -> bool:
        # Integer arithmetic: 94.96% must fail even though it prints as "95.0%".
        return self.total > 0 and self.correct * 100 >= self.target * self.total

    @property
    def needed(self) -> int:
        """The fewest correct fields that would meet the target at this denominator."""
        return math.ceil(self.target * self.total / 100)

    @property
    def verdict(self) -> str:
        """PASS, FAIL, or INCOMPLETE when photos failed with an API error.

        An API error (a quota limit, a network failure) says nothing about extraction
        accuracy, so those photos are left out of the score and the run cannot pass.
        A critical value that could be used unconfirmed fails the run regardless.
        """
        if self.unsafe:
            return "FAIL"
        if self.failed:
            return "INCOMPLETE"
        return "PASS" if self.accuracy_met else "FAIL"

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"

    @property
    def exit_code(self) -> int:
        return {"PASS": 0, "INCOMPLETE": EXIT_INCOMPLETE, "FAIL": EXIT_BELOW_TARGET}[self.verdict]


def critical_safe_use(records: dict[str, Record]) -> tuple[int, list[str]]:
    """Check that no critical value read from a photo can be used before confirmation.

    Q1 needs 100% safe use: an OCR serving-size or servings-per-package value must not
    reach F2 unless the user has confirmed it. Each reply is turned into the product
    contract as the API does (``to_contract``), then F2 is asked for the whole-package
    values with nothing confirmed. A photo is unsafe if a critical value is not marked
    ``uncertain``, if F2 calculates anything, or if the reply cannot be checked.

    Returns (photos checked, unsafe photos). Only replies with a table are checked.
    """
    checked, unsafe = 0, []
    for image, record in sorted(records.items()):
        result = record.result
        if not result or result.get("status") == NOT_FOUND:
            continue
        checked += 1
        try:
            reading = to_contract(result)
            product = Product(
                source=DataSource(Source.NUTRITION_LABEL_PHOTO, datetime.now(timezone.utc)),
                serving=reading.serving,
                package=reading.package,
                nutrition=reading.nutrition,
            )
            package = calculate_package_nutrition(product)
        except (ValueError, TypeError, KeyError, AttributeError):
            unsafe.append(image)  # fail closed
            continue
        critical = []
        if reading.serving.quantity is not None:
            critical.append(reading.serving.certainty)
        if reading.package.servings_per_package is not None:
            critical.append(reading.package.certainty)
        if (
            any(certainty is not Certainty.UNCERTAIN for certainty in critical)
            or package.status is PackageNutritionStatus.CALCULATED
        ):
            unsafe.append(image)
    return checked, unsafe


def failed_photos(records: dict[str, Record]) -> list[str]:
    return sorted(image for image, record in records.items() if record.error)


def evaluate(
    truth: dict[str, list[TruthRow]],
    records: dict[str, Record],
    target: float = TARGET_ACCURACY,
) -> Evaluation:
    scores: list[Score] = []
    for image in sorted(set(truth) | set(records)):
        record = records.get(image)
        if record is not None and record.error:
            continue  # an API error is not a misread: see Evaluation.verdict
        scores += score_image(image, truth.get(image, []), record)
    correct, total = accuracy(scores)
    return Evaluation(
        scores, correct, total, target, critical_safe_use(records)[1], failed_photos(records)
    )


def _cost(record: Record) -> float | None:
    try:
        price_in = float(os.environ["VISION_PRICE_INPUT_PER_MTOK"])
        price_out = float(os.environ["VISION_PRICE_OUTPUT_PER_MTOK"])
    except (KeyError, ValueError):
        return None
    return (record.input_tokens * price_in + record.output_tokens * price_out) / 1_000_000


def _pct(correct: int, total: int) -> str:
    return f"{100 * correct / total:.1f}%" if total else "n/a"


def verdict_lines(ev: Evaluation) -> list[str]:
    """The pass/fail line for the top of the report (Q1 verification step 7)."""
    if ev.total == 0:
        accuracy_text = "nothing was scored"
    else:
        accuracy_text = (
            f"aggregate accuracy {_pct(ev.correct, ev.total)} ({ev.correct}/{ev.total}) against "
            f"the {ev.target:g}% target; at least {ev.needed} correct fields were needed"
        )
    safe_text = (
        "critical-field safe use: all photo values stay unconfirmed until the user confirms them"
        if not ev.unsafe
        else f"critical-field safe use FAILED on {len(ev.unsafe)} photo(s)"
    )
    incomplete = ""
    if ev.failed and ev.verdict == "INCOMPLETE":
        incomplete = (
            f" {len(ev.failed)} photo(s) failed with an API error (for example a quota limit) "
            "and are left out of the score, so this run cannot decide Q1: run it again "
            "(`--from` re-scores saved replies; a second run only needs the failed photos' "
            "quota). The figures below cover only the photos that were read."
        )
    return [
        f"**Q1 verdict: {ev.verdict}**: {accuracy_text}; {safe_text}.{incomplete}",
        "",
        "A PASS counts toward Q1 only once two teammates have checked the ground truth "
        "(see tests/fixtures/nutrition_labels/README.md, status of the values).",
    ]


def critical_lines(
    by_field: dict[str, list[Score]], records: dict[str, Record], ev: Evaluation
) -> list[str]:
    """Serving size and servings per package, reported apart from the aggregate."""
    checked, _ = critical_safe_use(records)
    lines = [
        "### Critical fields (they set the serving multiplier in F2)",
        "",
        "| Field | Correct | Counted | Accuracy |",
        "|---|---|---|---|",
    ]
    wrong = []
    for field in CRITICAL_FIELDS:
        c, t = accuracy(by_field.get(field, []))
        lines.append(f"| {field} | {c} | {t} | {_pct(c, t)} |")
        wrong += [s for s in by_field.get(field, []) if s.outcome in ("wrong", "missing", "extra")]
    lines += [
        "",
        f"Safe use (Q1: 100%): {checked - len(ev.unsafe)} of {checked} photos with a table "
        "keep their serving size and servings per package unconfirmed, and F2 calculates "
        "no whole-package value from them before the user confirms.",
    ]
    if ev.unsafe:
        lines += ["", "Unsafe: " + ", ".join(ev.unsafe)]
    lines += [
        "",
        "Critical values that were wrong or missing (the user must catch these when confirming):",
        "",
    ]
    if wrong:
        lines += ["| Photo | Field | Outcome | Expected | Got |", "|---|---|---|---|---|"]
        lines += [
            f"| {s.image} | {s.field} | {s.outcome} | {s.expected or '(not printed)'} "
            f"| {s.actual or '(none)'} |"
            for s in wrong
        ]
    else:
        lines.append("None.")
    return lines


def render_report(
    truth: dict[str, list[TruthRow]],
    records: dict[str, Record],
    target: float = TARGET_ACCURACY,
) -> str:
    images = sorted(set(truth) | set(records))
    all_scores: list[Score] = []
    per_image: list[str] = []
    for image in images:
        record = records.get(image)
        scores = [] if record and record.error else score_image(image, truth.get(image, []), record)
        all_scores += scores
        counts = {o: sum(s.outcome == o for s in scores) for o in (*COUNTED, "extra")}
        notes = []
        if any(s.outcome == "unsupported" for s in scores):
            notes.append("unreadable to a reviewer: not scored")
        if image not in truth:
            notes.append("no ground truth")
        if record is None:
            notes.append("no photo")
        elif record.error:
            notes.append(f"error, not scored: {record.error}")
        elif record.result and record.result.get("status") == "not_found":
            notes.append("model: table not found")
        seconds = f"{record.latency_seconds:.1f}" if record and record.latency_seconds else ""
        per_image.append(
            f"| {image} | {counts['correct']} | {counts['wrong']} | {counts['missing']} "
            f"| {counts['extra']} | {seconds} | {'; '.join(notes)} |"
        )

    evaluation = evaluate(truth, records, target)
    correct, total = evaluation.correct, evaluation.total
    counts = {o: sum(s.outcome == o for s in all_scores) for o in (*COUNTED, "extra")}
    ok = [r for r in records.values() if not r.error and r.latency_seconds is not None]
    models = sorted({r.model for r in records.values() if r.model})

    lines = [
        "## Nutrition Facts extraction benchmark (Q1)",
        "",
        *verdict_lines(evaluation),
        "",
        f"Model: {', '.join(models) or 'n/a'}; Photos: {len(records)} "
        f"({sum(1 for r in records.values() if r.error)} failed)",
        "",
        f"**Aggregate field accuracy: {_pct(correct, total)} ({correct}/{total})**: "
        f"correct {counts['correct']}, wrong {counts['wrong']}, missing {counts['missing']}. "
        f"Extra (a value returned for a field not printed on the label): {counts['extra']}.",
        "",
        "Unsupported input (photos a reviewer cannot read, left out of the accuracy): "
        f"{sum(s.outcome == 'unsupported' for s in all_scores)}",
        "",
    ]
    if ok:
        times = [r.latency_seconds for r in ok]
        lines.append(
            f"Response time: mean {statistics.mean(times):.1f} s, max {max(times):.1f} s; "
            f"Tokens per photo: mean {statistics.mean(r.input_tokens for r in ok):,.0f} in / "
            f"{statistics.mean(r.output_tokens for r in ok):,.0f} out"
        )
        costs = [_cost(r) for r in ok]
        if all(c is not None for c in costs):
            lines.append(f"Cost per photo: mean ${statistics.mean(costs):.4f}")
        else:
            lines.append(
                "Cost per photo: set VISION_PRICE_INPUT_PER_MTOK and "
                "VISION_PRICE_OUTPUT_PER_MTOK to compute"
            )
        lines.append("")

    lines += [
        "### Per photo",
        "",
        "| Photo | Correct | Wrong | Missing | Extra | Time (s) | Notes |",
        "|---|---|---|---|---|---|---|",
        *per_image,
        "",
        "### Mismatches",
        "",
    ]
    mismatches = [s for s in all_scores if s.outcome in ("wrong", "missing", "extra")]
    if mismatches:
        lines += ["| Photo | Field | Outcome | Expected | Got |", "|---|---|---|---|---|"]
        lines += [
            f"| {s.image} | {s.field} | {s.outcome} | {s.expected or '(not printed)'} "
            f"| {s.actual or '(none)'} |"
            for s in mismatches
        ]
    else:
        lines.append("None.")

    by_field: dict[str, list[Score]] = defaultdict(list)
    for s in all_scores:
        by_field[s.field].append(s)
    lines += [
        "",
        "### Per field",
        "",
        "| Field | Correct | Counted | Accuracy |",
        "|---|---|---|---|",
    ]
    for field in FIELDS:
        if field in by_field:
            c, t = accuracy(by_field[field])
            lines.append(f"| {field} | {c} | {t} | {_pct(c, t)} |")
    lines += ["", *critical_lines(by_field, records, evaluation)]
    return "\n".join(lines) + "\n"


def run_photos(photos: list[Path], config: VisionConfig, out: Path | None) -> dict[str, Record]:
    records: dict[str, Record] = {}
    for i, photo in enumerate(photos, start=1):
        print(f"[{i}/{len(photos)}] {photo.name}", file=sys.stderr)
        try:
            e = extract_label_file(photo, config)
            record = Record(
                photo.name,
                e.result,
                None,
                e.model,
                e.latency_seconds,
                e.input_tokens,
                e.output_tokens,
            )
        except LabelExtractionError as exc:
            record = Record(photo.name, None, str(exc), config.model)
        records[photo.name] = record
        if out:
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{photo.name}.json").write_text(
                json.dumps(record.__dict__, indent=2), encoding="utf-8"
            )
    return records


def load_records(directory: Path) -> dict[str, Record]:
    records = {}
    for path in sorted(directory.glob("*.json")):
        record = Record(**json.loads(path.read_text(encoding="utf-8")))
        records[record.image] = record
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--out", type=Path, help="save each reply as JSON in this folder")
    source.add_argument("--from", dest="saved", type=Path, help="score replies saved with --out")
    args = parser.parse_args(argv)

    load_dotenv()
    truth_path = args.fixtures / "ground_truth.csv"
    try:
        truth = load_truth(truth_path) if truth_path.exists() else {}
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not truth:
        print(f"warning: no ground truth in {truth_path}; nothing will be scored", file=sys.stderr)

    if args.saved:
        records = load_records(args.saved)
    else:
        photos = sorted(
            p for p in (args.fixtures / "images").glob("*") if p.suffix.lower() in MIME_TYPES
        )
        if not photos:
            print(f"error: no photos in {args.fixtures / 'images'}", file=sys.stderr)
            return 1
        try:
            config = VisionConfig.from_env()
        except LabelExtractionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        records = run_photos(photos, config, args.out)

    print(render_report(truth, records))
    return evaluate(truth, records).exit_code


if __name__ == "__main__":
    sys.exit(main())
