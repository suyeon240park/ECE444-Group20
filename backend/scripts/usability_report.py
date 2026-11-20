"""Score the Q3 usability test (#69) from the session files.

    python -m scripts.usability_report ../docs/usability/session-1
    python -m scripts.usability_report --pilot ../docs/usability/pilot

The folder holds three anonymized CSV files (see docs/usability/test-plan.md):
``participants.csv``, ``attempts.csv`` and ``sus.csv``. The script checks Q3's
conditions, then prints a Markdown report: overall and per-task success, mean SUS, the
T3/T4 scorer disagreements, and a verdict against Q3's targets.

``--pilot`` scores a run that does not meet Q3's conditions (for example one team member
trying the tasks once). The report is stamped as a pilot and gives no Q3 verdict.

Exit status: 0 when the conditions hold and every target is met, 1 when the files or
the conditions are not valid (the result does not count), 2 when a target is missed.
With ``--pilot``: 0 whenever the files are valid.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

TASKS = ("T1", "T2", "T3", "T4")
OPEN_ENDED = ("T3", "T4")  # scored by two teammates against the rubric

# Q3 targets (docs/requirements.md). Change them only through a reviewed requirements
# revision, which is why they are constants and not command-line options.
TARGET_OVERALL_SUCCESS = 80.0  # percent of all participant-task attempts
FLOOR_PER_TASK = (3, 5)  # each task passed by at least 3 of 5 participants, 60% beyond 5
TARGET_SUS = 68.0

# Q3 conditions.
MIN_PARTICIPANTS = 5
MIN_PHONE = 3
MIN_DESKTOP = 2
MIN_CATEGORIES = 3

DEVICES = ("phone", "desktop")
OUTCOMES = ("completed", "gave_up", "asked_help", "rerun_q2")
RESULTS = ("pass", "fail")
SUS_ITEMS = tuple(f"q{i}" for i in range(1, 11))

EXIT_INVALID = 1
EXIT_BELOW_TARGET = 2


class InvalidSession(ValueError):
    """The files break a rule of the test plan; the result must not be reported."""


@dataclass(frozen=True)
class Attempt:
    participant: str
    task: str
    category: str
    outcome: str
    scorer_a: str
    scorer_b: str
    final: str
    notes: str

    @property
    def passed(self) -> bool:
        return self.final == "pass"

    @property
    def disagreed(self) -> bool:
        return self.task in OPEN_ENDED and self.scorer_a != self.scorer_b


@dataclass(frozen=True)
class Session:
    devices: dict[str, str]  # participant -> phone | desktop
    attempts: list[Attempt]  # without the rerun_q2 rows
    sus: dict[str, list[int]]  # participant -> ten answers


def _rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    if not path.exists():
        raise InvalidSession(f"{path.name} is missing")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [
            (line, {k: (v or "").strip() for k, v in row.items() if k})
            for line, row in enumerate(reader, start=2)
            if any((v or "").strip() for v in row.values())
        ]


def _need(row: dict[str, str], key: str, name: str, line: int) -> str:
    value = row.get(key, "")
    if not value:
        raise InvalidSession(f"{name} line {line}: {key} is empty")
    return value


def load_session(folder: Path) -> Session:
    devices: dict[str, str] = {}
    for line, row in _rows(folder / "participants.csv"):
        who = _need(row, "participant", "participants.csv", line)
        if who in devices:
            raise InvalidSession(f"participants.csv line {line}: {who} appears twice")
        device = _need(row, "device", "participants.csv", line)
        if device not in DEVICES:
            raise InvalidSession(f"participants.csv line {line}: device must be one of {DEVICES}")
        training = _need(row, "nutrition_training", "participants.csv", line)
        if training == "yes":
            raise InvalidSession(
                f"participants.csv line {line}: {who} has nutrition training; Q3 excludes "
                "them, so remove them and their rows"
            )
        if training != "no":
            raise InvalidSession(f"participants.csv line {line}: nutrition_training must be no")
        devices[who] = device

    attempts: list[Attempt] = []
    seen: set[tuple[str, str]] = set()
    for line, row in _rows(folder / "attempts.csv"):
        name = "attempts.csv"
        who = _need(row, "participant", name, line)
        task = _need(row, "task", name, line)
        if who not in devices:
            raise InvalidSession(f"{name} line {line}: {who} is not in participants.csv")
        if task not in TASKS:
            raise InvalidSession(f"{name} line {line}: task must be one of {TASKS}")
        outcome = _need(row, "outcome", name, line)
        if outcome not in OUTCOMES:
            raise InvalidSession(f"{name} line {line}: outcome must be one of {OUTCOMES}")
        if outcome == "rerun_q2":
            continue  # recorded against Q2; the task is run again in a later row
        category = _need(row, "category", name, line)
        a, b = row.get("scorer_a", ""), row.get("scorer_b", "")
        final = _need(row, "final", name, line)
        for label, value in (("scorer_a", a), ("scorer_b", b), ("final", final)):
            if value and value not in RESULTS:
                raise InvalidSession(f"{name} line {line}: {label} must be pass or fail")
        if outcome in ("gave_up", "asked_help") and final == "pass":
            raise InvalidSession(f"{name} line {line}: {outcome} is a failure, not a pass")
        if task in OPEN_ENDED:
            if not (a and b):
                raise InvalidSession(f"{name} line {line}: {task} needs scorer_a and scorer_b")
            if a == b and final != a:
                raise InvalidSession(f"{name} line {line}: both scorers said {a}, so final is {a}")
            if a != b and not row.get("notes"):
                raise InvalidSession(
                    f"{name} line {line}: the scorers differ; write how it was resolved in notes"
                )
        if (who, task) in seen:
            raise InvalidSession(
                f"{name} line {line}: {who} has two counted attempts at {task} "
                "(mark the abandoned one rerun_q2)"
            )
        seen.add((who, task))
        attempts.append(Attempt(who, task, category, outcome, a, b, final, row.get("notes", "")))

    for who in devices:
        missing = [t for t in TASKS if (who, t) not in seen]
        if missing:
            raise InvalidSession(f"attempts.csv: {who} has no attempt for {', '.join(missing)}")

    sus: dict[str, list[int]] = {}
    for line, row in _rows(folder / "sus.csv"):
        who = _need(row, "participant", "sus.csv", line)
        if who not in devices:
            raise InvalidSession(f"sus.csv line {line}: {who} is not in participants.csv")
        if who in sus:
            raise InvalidSession(f"sus.csv line {line}: {who} appears twice")
        answers = []
        for item in SUS_ITEMS:
            raw = row.get(item, "")
            if raw not in ("1", "2", "3", "4", "5"):
                raise InvalidSession(f"sus.csv line {line}: {item} must be a whole number 1 to 5")
            answers.append(int(raw))
        sus[who] = answers
    missing_sus = [who for who in devices if who not in sus]
    if missing_sus:
        raise InvalidSession(f"sus.csv: no answers for {', '.join(missing_sus)}")
    return Session(devices, attempts, sus)


def sus_score(answers: list[int]) -> float:
    """The standard SUS score: odd items count (answer - 1), even items (5 - answer)."""
    if len(answers) != 10:
        raise ValueError("SUS has ten items")
    total = sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))
    return total * 2.5


def condition_problems(session: Session) -> list[str]:
    """The Q3 conditions the session does not meet."""
    problems = []
    n = len(session.devices)
    if n < MIN_PARTICIPANTS:
        problems.append(f"{n} participants; Q3 needs at least {MIN_PARTICIPANTS}")
    phones = sum(d == "phone" for d in session.devices.values())
    desktops = sum(d == "desktop" for d in session.devices.values())
    if phones < MIN_PHONE:
        problems.append(f"{phones} on a phone-size browser; Q3 needs at least {MIN_PHONE}")
    if desktops < MIN_DESKTOP:
        problems.append(f"{desktops} on a desktop browser; Q3 needs at least {MIN_DESKTOP}")
    categories = {a.category for a in session.attempts}
    if len(categories) < MIN_CATEGORIES:
        problems.append(f"{len(categories)} product categories; Q3 needs at least {MIN_CATEGORIES}")
    return problems


@dataclass(frozen=True)
class Results:
    passed: int
    total: int
    per_task: dict[str, int]  # task -> participants who passed
    floor: int
    sus_by_participant: dict[str, float]
    mean_sus: float

    @property
    def overall_percent(self) -> float:
        return 100 * self.passed / self.total

    @property
    def overall_met(self) -> bool:
        return self.passed * 100 >= TARGET_OVERALL_SUCCESS * self.total

    @property
    def tasks_below_floor(self) -> list[str]:
        return [t for t in TASKS if self.per_task[t] < self.floor]

    @property
    def sus_met(self) -> bool:
        return self.mean_sus >= TARGET_SUS

    @property
    def met(self) -> bool:
        return self.overall_met and not self.tasks_below_floor and self.sus_met


def compute(session: Session) -> Results:
    n = len(session.devices)
    per_task = {t: sum(a.passed for a in session.attempts if a.task == t) for t in TASKS}
    sus = {who: sus_score(answers) for who, answers in session.sus.items()}
    return Results(
        passed=sum(a.passed for a in session.attempts),
        total=len(session.attempts),
        per_task=per_task,
        floor=math.ceil(FLOOR_PER_TASK[0] * n / FLOOR_PER_TASK[1]),
        sus_by_participant=sus,
        mean_sus=statistics.mean(sus.values()),
    )


def _mark(met: bool) -> str:
    return "met" if met else "MISSED"


def render_report(session: Session, pilot: bool = False) -> str:
    problems = condition_problems(session)
    results = compute(session)
    n = len(session.devices)
    participants = sorted(session.devices, key=lambda p: (len(p), p))
    by_key = {(a.participant, a.task): a for a in session.attempts}

    if pilot:
        verdict = (
            f"**PILOT RUN ({n} participant{'s' if n != 1 else ''}), not a Q3 result.** "
            f"Q3 needs {MIN_PARTICIPANTS} or more participants from outside the team "
            f"({MIN_PHONE} on a phone, {MIN_DESKTOP} on a desktop) and {MIN_CATEGORIES} product "
            "categories. The numbers show how the tasks went, not whether Q3 is met or missed."
        )
    elif problems:
        verdict = "**Q3 result: NOT VALID**: " + "; ".join(problems) + ". Do not report this run."
    elif results.met:
        verdict = "**Q3 result: PASS**: all three targets are met."
    else:
        verdict = "**Q3 result: FAIL**: at least one target is missed (see below)."

    lines = [
        "## Usability test results (Q3)",
        "",
        verdict,
        "",
        f"Participants: {n} ({sum(d == 'phone' for d in session.devices.values())} phone, "
        f"{sum(d == 'desktop' for d in session.devices.values())} desktop); "
        f"product categories: {', '.join(sorted({a.category for a in session.attempts}))}",
        "",
        "### Targets (for reference only in a pilot)" if pilot else "### Targets",
        "",
        "| Measure | Target | Result | |",
        "|---|---|---|---|",
        f"| Overall unassisted task success | at least {TARGET_OVERALL_SUCCESS:g}% | "
        f"{results.overall_percent:.1f}% ({results.passed}/{results.total}) | "
        f"{_mark(results.overall_met)} |",
        f"| Per task | each task passed by at least {results.floor} of {n} participants | "
        + ", ".join(f"{t} {results.per_task[t]}/{n}" for t in TASKS)
        + f" | {_mark(not results.tasks_below_floor)} |",
        f"| Mean SUS | at least {TARGET_SUS:g} | {results.mean_sus:.1f} "
        f"| {_mark(results.sus_met)} |",
        "",
        "### Task success by participant",
        "",
        "| Participant | Device | " + " | ".join(TASKS) + " |",
        "|---|---|" + "---|" * len(TASKS),
    ]
    for who in participants:
        cells = " | ".join(by_key[(who, t)].final for t in TASKS)
        lines.append(f"| {who} | {session.devices[who]} | {cells} |")
    lines += ["", "### Task success by task", "", "| Task | Passed | Rate |", "|---|---|---|"]
    for t in TASKS:
        lines.append(f"| {t} | {results.per_task[t]}/{n} | {100 * results.per_task[t] / n:.0f}% |")

    lines += ["", "### SUS", "", "| Participant | Score |", "|---|---|"]
    lines += [f"| {who} | {results.sus_by_participant[who]:g} |" for who in participants]
    lines.append(f"| **Mean** | **{results.mean_sus:.1f}** |")

    disagreements = [a for a in session.attempts if a.disagreed]
    lines += [
        "",
        "### T3 and T4 scoring",
        "",
        f"Scorers disagreed on {len(disagreements)} of "
        f"{sum(a.task in OPEN_ENDED for a in session.attempts)} open-ended answers "
        "before they were resolved.",
    ]
    if disagreements:
        lines += ["", "| Participant | Task | Scorer A | Scorer B | Final | Resolution |"]
        lines += ["|---|---|---|---|---|---|"]
        lines += [
            f"| {a.participant} | {a.task} | {a.scorer_a} | {a.scorer_b} | {a.final} | {a.notes} |"
            for a in disagreements
        ]

    failed_by_task: dict[str, list[str]] = defaultdict(list)
    for a in session.attempts:
        if not a.passed:
            failed_by_task[a.task].append(f"{a.participant} ({a.outcome})")
    lines += ["", "### Failed attempts", ""]
    if failed_by_task:
        lines += [f"- {t}: {', '.join(who)}" for t, who in sorted(failed_by_task.items())]
        lines.append("")
        lines.append(
            "Open one issue per usability problem behind these (test plan, Problems found)."
        )
    else:
        lines.append("None.")
    lines += [
        "",
        "Readability (Q3 measure 3) is measured separately and is not part of this report.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="folder with participants, attempts and sus CSVs")
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="score a run that does not meet Q3's conditions; no Q3 verdict is given",
    )
    args = parser.parse_args(argv)
    try:
        session = load_session(args.folder)
    except InvalidSession as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID
    if not session.attempts:
        print("error: no attempts recorded yet", file=sys.stderr)
        return EXIT_INVALID
    print(render_report(session, pilot=args.pilot))
    if args.pilot:
        return 0
    if condition_problems(session):
        return EXIT_INVALID
    return 0 if compute(session).met else EXIT_BELOW_TARGET


if __name__ == "__main__":
    sys.exit(main())
