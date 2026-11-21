from pathlib import Path

import pytest

from scripts import usability_report as ur

DEVICES = {"P1": "phone", "P2": "phone", "P3": "phone", "P4": "desktop", "P5": "desktop"}
CATEGORY = {"T1": "condiments", "T2": "condiments", "T3": "beverages", "T4": "snacks"}
BEST_SUS = "5,1,5,1,5,1,5,1,5,1"  # 100
WORST_SUS = "1,5,1,5,1,5,1,5,1,5"  # 0


def write_session(
    folder: Path,
    *,
    devices: dict[str, str] | None = None,
    fails: set[tuple[str, str]] = frozenset(),
    sus: dict[str, str] | None = None,
    extra_attempts: list[str] = (),
    categories: dict[str, str] | None = None,
    training: str = "no",
) -> Path:
    devices = devices or DEVICES
    categories = categories or CATEGORY
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "participants.csv").write_text(
        "participant,device,nutrition_training\n"
        + "".join(f"{p},{d},{training}\n" for p, d in devices.items()),
        encoding="utf-8",
    )
    rows = ["participant,task,category,outcome,scorer_a,scorer_b,final,notes"]
    for who in devices:
        for task in ur.TASKS:
            result = "fail" if (who, task) in fails else "pass"
            outcome = "asked_help" if result == "fail" else "completed"
            scorers = f"{result},{result}" if task in ur.OPEN_ENDED else ","
            rows.append(f"{who},{task},{categories[task]},{outcome},{scorers},{result},")
    rows += extra_attempts
    (folder / "attempts.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    answers = sus or {}
    (folder / "sus.csv").write_text(
        "participant,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10\n"
        + "".join(f"{p},{answers.get(p, BEST_SUS)}\n" for p in devices),
        encoding="utf-8",
    )
    return folder


def test_sus_score_follows_the_standard_formula():
    assert ur.sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100
    assert ur.sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0
    assert ur.sus_score([3] * 10) == 50
    assert ur.sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == 75
    with pytest.raises(ValueError):
        ur.sus_score([3] * 9)


def test_a_clean_session_passes(tmp_path, capsys):
    folder = write_session(tmp_path / "s1")

    assert ur.main([str(folder)]) == 0
    report = capsys.readouterr().out
    assert "**Q3 result: PASS**" in report
    assert "| Overall unassisted task success | at least 80% | 100.0% (20/20) | met |" in report
    assert "| Mean SUS | at least 68 | 100.0 | met |" in report
    assert "| P4 | desktop | pass | pass | pass | pass |" in report
    assert "Scorers disagreed on 0 of 10 open-ended answers" in report


def test_overall_target_is_80_percent_of_attempts(tmp_path, capsys):
    # 4 failures of 20 attempts is exactly 80%: still a pass. A fifth failure is not.
    four = {("P1", "T1"), ("P2", "T2"), ("P3", "T3"), ("P4", "T4")}
    assert ur.main([str(write_session(tmp_path / "a", fails=four))]) == 0
    capsys.readouterr()

    five = four | {("P5", "T1")}
    assert ur.main([str(write_session(tmp_path / "b", fails=five))]) == ur.EXIT_BELOW_TARGET
    assert "| Overall unassisted task success | at least 80% | 75.0% (15/20) | MISSED |" in (
        capsys.readouterr().out
    )


def test_every_task_needs_three_of_five(tmp_path, capsys):
    two_fail = {("P1", "T3"), ("P2", "T3")}  # T3 passed by 3 of 5: floor met
    assert ur.main([str(write_session(tmp_path / "a", fails=two_fail))]) == 0
    capsys.readouterr()

    three_fail = {("P1", "T4"), ("P2", "T4"), ("P3", "T4")}  # overall 85% but T4 is 2 of 5
    code = ur.main([str(write_session(tmp_path / "b", fails=three_fail))])
    report = capsys.readouterr().out
    assert code == ur.EXIT_BELOW_TARGET
    assert "T1 5/5, T2 5/5, T3 5/5, T4 2/5 | MISSED |" in report
    assert "**Q3 result: FAIL**" in report
    assert "- T4: P1 (asked_help), P2 (asked_help), P3 (asked_help)" in report


def test_sus_below_68_fails(tmp_path, capsys):
    sus = {"P1": WORST_SUS, "P2": WORST_SUS, "P3": WORST_SUS}  # mean (0*3 + 100*2) / 5 = 40
    assert ur.main([str(write_session(tmp_path / "s", sus=sus))]) == ur.EXIT_BELOW_TARGET
    assert "| Mean SUS | at least 68 | 40.0 | MISSED |" in capsys.readouterr().out


def test_conditions_make_a_run_not_valid(tmp_path, capsys):
    four_phones = {"P1": "phone", "P2": "phone", "P3": "phone", "P4": "phone", "P5": "desktop"}
    code = ur.main([str(write_session(tmp_path / "a", devices=four_phones))])
    assert code == ur.EXIT_INVALID
    assert "1 on a desktop browser; Q3 needs at least 2" in capsys.readouterr().out

    four = {k: v for k, v in DEVICES.items() if k != "P5"}
    assert ur.main([str(write_session(tmp_path / "b", devices=four))]) == ur.EXIT_INVALID
    assert "4 participants; Q3 needs at least 5" in capsys.readouterr().out

    two_categories = {**CATEGORY, "T4": "condiments"}
    assert ur.main([str(write_session(tmp_path / "c", categories=two_categories))]) == (
        ur.EXIT_INVALID
    )
    out = capsys.readouterr().out
    assert "2 product categories; Q3 needs at least 3" in out
    assert "**Q3 result: NOT VALID**" in out


def test_per_task_floor_scales_beyond_five_participants(tmp_path):
    seven = {f"P{i}": "phone" if i <= 4 else "desktop" for i in range(1, 8)}
    session = ur.load_session(write_session(tmp_path / "s", devices=seven))
    assert ur.compute(session).floor == 5  # 3 of 5 is 60%; ceil(0.6 * 7)


def test_open_ended_scorer_disagreement_is_counted_and_needs_a_reason(tmp_path, capsys):
    folder = write_session(tmp_path / "s")
    original = (folder / "attempts.csv").read_text()
    row = "P1,T3,beverages,completed,pass,pass,pass,"
    differing = "P1,T3,beverages,completed,pass,fail,pass,"

    (folder / "attempts.csv").write_text(original.replace(row, differing + "gave the % meaning"))
    assert ur.main([str(folder)]) == 0
    out = capsys.readouterr().out
    assert "Scorers disagreed on 1 of 10 open-ended answers" in out
    assert "| P1 | T3 | pass | fail | pass | gave the % meaning |" in out

    (folder / "attempts.csv").write_text(original.replace(row, differing))
    assert ur.main([str(folder)]) == ur.EXIT_INVALID
    assert "the scorers differ; write how it was resolved" in capsys.readouterr().err


def test_rerun_q2_rows_are_not_counted(tmp_path, capsys):
    extra = ["P1,T1,condiments,rerun_q2,,,,backend timed out (Q2), re-ran"]
    # An extra uncounted row must not create a duplicate or change the results.
    assert ur.main([str(write_session(tmp_path / "s", extra_attempts=extra))]) == 0
    assert "100.0% (20/20)" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (("P1,T1,condiments,completed,,,pass,", "P1,T9,condiments,completed,,,pass,"), "task must"),
        (("completed,,,pass,\nP1,T2", "bogus,,,pass,\nP1,T2"), "outcome must"),
        (
            ("P1,T1,condiments,completed,,,pass,", "P1,T1,condiments,completed,,,maybe,"),
            "pass or fail",
        ),
        (
            ("P1,T1,condiments,completed,,,pass,", "P1,T1,condiments,asked_help,,,pass,"),
            "is a failure",
        ),
        (
            ("P1,T1,condiments,completed,,,pass,", "P1,T1,condiments,completed,,,,"),
            "final is empty",
        ),
        (
            ("P1,T3,beverages,completed,pass,pass,pass,", "P1,T3,beverages,completed,,pass,pass,"),
            "needs scorer_a",
        ),
        (
            (
                "P1,T3,beverages,completed,pass,pass,pass,",
                "P1,T3,beverages,completed,pass,pass,fail,",
            ),
            "so final is pass",
        ),
        (
            ("P1,T1,condiments,completed,,,pass,", "P9,T1,condiments,completed,,,pass,"),
            "not in participants.csv",
        ),
    ],
)
def test_attempt_rows_are_checked(tmp_path, capsys, edit, message):
    folder = write_session(tmp_path / "s")
    text = (folder / "attempts.csv").read_text()
    assert edit[0] in text
    (folder / "attempts.csv").write_text(text.replace(*edit, 1))

    assert ur.main([str(folder)]) == ur.EXIT_INVALID
    assert message in capsys.readouterr().err


def test_duplicate_and_missing_attempts_are_errors(tmp_path, capsys):
    dup = write_session(tmp_path / "a", extra_attempts=["P1,T1,condiments,completed,,,pass,"])
    assert ur.main([str(dup)]) == ur.EXIT_INVALID
    assert "two counted attempts at T1" in capsys.readouterr().err

    missing = write_session(tmp_path / "b")
    lines = (missing / "attempts.csv").read_text().splitlines()
    (missing / "attempts.csv").write_text("\n".join(x for x in lines if not x.startswith("P2,T4")))
    assert ur.main([str(missing)]) == ur.EXIT_INVALID
    assert "P2 has no attempt for T4" in capsys.readouterr().err


def test_participant_rules(tmp_path, capsys):
    assert ur.main([str(write_session(tmp_path / "a", training="yes"))]) == ur.EXIT_INVALID
    assert "has nutrition training" in capsys.readouterr().err

    assert ur.main([str(write_session(tmp_path / "b", training="maybe"))]) == ur.EXIT_INVALID
    assert "nutrition_training must be no" in capsys.readouterr().err

    folder = write_session(tmp_path / "c")
    text = (folder / "participants.csv").read_text().replace("P1,phone", "P1,tablet")
    (folder / "participants.csv").write_text(text)
    assert ur.main([str(folder)]) == ur.EXIT_INVALID
    assert "device must be one of" in capsys.readouterr().err

    (folder / "participants.csv").write_text(text.replace("P1,tablet", "P2,phone"))
    assert ur.main([str(folder)]) == ur.EXIT_INVALID
    assert "P2 appears twice" in capsys.readouterr().err


def test_sus_rows_are_checked(tmp_path, capsys):
    bad = write_session(tmp_path / "a", sus={"P1": "5,1,5,1,5,1,5,1,5,6"})
    assert ur.main([str(bad)]) == ur.EXIT_INVALID
    assert "q10 must be a whole number 1 to 5" in capsys.readouterr().err

    missing = write_session(tmp_path / "b")
    lines = (missing / "sus.csv").read_text().splitlines()
    (missing / "sus.csv").write_text("\n".join(x for x in lines if not x.startswith("P5")) + "\n")
    assert ur.main([str(missing)]) == ur.EXIT_INVALID
    assert "no answers for P5" in capsys.readouterr().err


def test_missing_file_and_blank_template(tmp_path, capsys):
    assert ur.main([str(tmp_path)]) == ur.EXIT_INVALID
    assert "participants.csv is missing" in capsys.readouterr().err

    templates = Path(__file__).resolve().parents[2] / "docs" / "usability"
    session = ur.load_session(templates)  # the blank templates: header rows only
    assert session.devices == {} and session.attempts == []
    assert len(ur.condition_problems(session)) == 4
    assert ur.main([str(templates)]) == ur.EXIT_INVALID
    assert "no attempts recorded yet" in capsys.readouterr().err


def test_pilot_scores_one_participant_without_a_q3_verdict(tmp_path, capsys):
    one = {"X1": "desktop"}
    fails = {("X1", "T4")}
    folder = write_session(tmp_path / "pilot", devices=one, fails=fails)

    assert ur.main(["--pilot", str(folder)]) == 0
    out = capsys.readouterr().out
    assert "**PILOT RUN (1 participant), not a Q3 result.**" in out
    assert "Q3 needs 5 or more participants from outside the team" in out
    assert "### Targets (for reference only in a pilot)" in out
    assert "| X1 | desktop | pass | pass | pass | fail |" in out
    assert "**Q3 result:" not in out


def test_without_pilot_one_participant_is_not_valid(tmp_path, capsys):
    folder = write_session(tmp_path / "s", devices={"X1": "desktop"})
    assert ur.main([str(folder)]) == ur.EXIT_INVALID
    assert "**Q3 result: NOT VALID**" in capsys.readouterr().out


def test_pilot_still_rejects_bad_files(tmp_path, capsys):
    folder = write_session(tmp_path / "s", devices={"X1": "desktop"})
    (folder / "sus.csv").write_text("participant,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10\n")
    assert ur.main(["--pilot", str(folder)]) == ur.EXIT_INVALID
    assert "no answers for X1" in capsys.readouterr().err
