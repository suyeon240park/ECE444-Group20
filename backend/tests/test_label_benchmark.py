import json
from pathlib import Path

import pytest

from app.models.product import Certainty
from app.services.label_extraction import Extraction, LabelExtractionError
from app.services.label_reading import to_contract
from scripts import label_benchmark as lb
from scripts.label_benchmark import Record, TruthRow, load_truth, render_report, score_image

RESULT = {
    "status": "found",
    "serving": {
        "size_text": "6 crackers (30 g)",
        "household": "6 Crackers.",
        "quantity": 30.0,
        "unit": "g",
    },
    "package": {"servings_per_package": None},
    "nutrition": {
        "basis": "serving",
        "nutrients": {
            "sodium": {"amount": 310.0, "unit": "mg", "daily_value_percent": 18.0},
            "sugars": None,
            "trans_fat": {"amount": 0.0, "unit": "g", "daily_value_percent": None},
        },
    },
}

TRUTH = [
    TruthRow("serving.household", "6 crackers", ""),
    TruthRow("serving.quantity", "30", "g"),
    TruthRow("nutrition.nutrients.sodium.amount", "310", "mg"),
    TruthRow("nutrition.nutrients.sodium.daily_value_percent", "13", ""),
    TruthRow("nutrition.nutrients.sugars.amount", "2", "g"),
    TruthRow("package.servings_per_package", "", ""),
    TruthRow("nutrition.nutrients.trans_fat.amount", "", ""),
]

CSV = """image,field,expected,unit
001_crackers.jpg,serving.quantity,30,g
001_crackers.jpg,nutrition.nutrients.sodium.amount,310,mg
001_crackers.jpg,package.servings_per_package,-,
002_box_back.jpg,status,not_found,
"""


def outcomes(scores):
    return {s.field: s.outcome for s in scores}


def test_score_image_follows_q1_rules():
    scores = score_image("001.jpg", TRUTH, Record("001.jpg", RESULT))

    assert outcomes(scores) == {
        "serving.household": "correct",  # case, spacing and dots ignored
        "serving.quantity": "correct",
        "nutrition.nutrients.sodium.amount": "correct",
        "nutrition.nutrients.sodium.daily_value_percent": "wrong",  # the 13 -> 18 example
        "nutrition.nutrients.sugars.amount": "missing",
        "package.servings_per_package": "absent",  # not printed, not counted
        "nutrition.nutrients.trans_fat.amount": "extra",  # returned but not printed
    }
    assert lb.accuracy(scores) == (3, 5)


def test_score_image_checks_units():
    rows = [TruthRow("serving.quantity", "30", "mL")]
    assert outcomes(score_image("a", rows, Record("a", RESULT))) == {"serving.quantity": "wrong"}


def test_score_image_table_not_found():
    rows = [TruthRow("status", "not_found", "")]
    assert score_image("a", rows, Record("a", {"status": "not_found"}))[0].outcome == "correct"
    assert score_image("a", rows, Record("a", RESULT))[0].outcome == "wrong"
    assert score_image("a", rows, Record("a", None, "HTTP 500"))[0].outcome == "missing"


def test_score_image_unreadable_photo_is_not_scored():
    rows = [TruthRow("status", "unreadable", "")]
    for record in (Record("a", RESULT), Record("a", {"status": "not_found"}), None):
        scores = score_image("a", rows, record)
        assert [s.outcome for s in scores] == ["unsupported"]
        assert lb.accuracy(scores) == (0, 0)


def test_score_image_failed_or_not_found_counts_fields_as_missing():
    for record in (Record("a", None, "HTTP 500"), Record("a", {"status": "not_found"}), None):
        scores = score_image("a", TRUTH, record)
        assert lb.accuracy(scores) == (0, 5)


def test_load_truth(tmp_path: Path):
    path = tmp_path / "ground_truth.csv"
    path.write_text(CSV, encoding="utf-8")

    truth = load_truth(path)

    assert truth["001_crackers.jpg"][0] == TruthRow("serving.quantity", "30", "g")
    assert truth["001_crackers.jpg"][2] == TruthRow("package.servings_per_package", "", "")
    assert truth["002_box_back.jpg"] == [TruthRow("status", "not_found", "")]


def test_load_truth_accepts_excel_csv(tmp_path: Path):
    path = tmp_path / "ground_truth.csv"
    path.write_text(CSV.replace("\n", "\r\n"), encoding="utf-8-sig")
    assert load_truth(path)["001_crackers.jpg"][0] == TruthRow("serving.quantity", "30", "g")


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("001.jpg,nutrition.nutrients.sodium,310,mg", "unknown field"),
        (",status,found,", "image"),
        ("001.jpg,serving.quantity,,g", "no expected value"),
        ("001.jpg,status,blurry,", "status must be not_found or unreadable"),
    ],
)
def test_load_truth_rejects_typos(tmp_path: Path, row, message):
    path = tmp_path / "ground_truth.csv"
    path.write_text("image,field,expected,unit\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_truth(path)


def test_render_report(monkeypatch):
    monkeypatch.setenv("VISION_PRICE_INPUT_PER_MTOK", "0.30")
    monkeypatch.setenv("VISION_PRICE_OUTPUT_PER_MTOK", "2.50")
    truth = {
        "001.jpg": TRUTH,
        "002.jpg": [TruthRow("status", "not_found", "")],
        "003.jpg": TRUTH,
        "005.jpg": [TruthRow("status", "unreadable", "")],
    }
    records = {
        "001.jpg": Record("001.jpg", RESULT, None, "m", 4.0, 1000, 200),
        "002.jpg": Record("002.jpg", {"status": "not_found"}, None, "m", 2.0, 1000, 200),
        "004.jpg": Record("004.jpg", None, "HTTP 500", "m"),
        "005.jpg": Record("005.jpg", RESULT, None, "m", 2.0, 1000, 200),
    }

    report = render_report(truth, records)

    assert "**Aggregate field accuracy: 36.4% (4/11)**" in report
    assert (
        "Unsupported input (photos a reviewer cannot read, left out of the accuracy): 1" in report
    )
    assert "| 005.jpg | 0 | 0 | 0 | 0 | 2.0 | unreadable to a reviewer: not scored |" in report
    assert "Photos: 4 (1 failed)" in report
    assert "Response time: mean 2.7 s, max 4.0 s" in report
    assert "Cost per photo: mean $0.0008" in report
    assert "| 003.jpg | 0 | 0 | 5 | 0 |  | no photo |" in report
    assert "| 004.jpg | 0 | 0 | 0 | 0 |  | no ground truth; error, not scored: HTTP 500 |" in report
    assert "| 002.jpg | 1 | 0 | 0 | 0 | 2.0 | model: table not found |" in report
    assert (
        "| 001.jpg | nutrition.nutrients.sodium.daily_value_percent | wrong | 13 | 18 |" in report
    )
    assert (
        "| 001.jpg | nutrition.nutrients.trans_fat.amount | extra | (not printed) | 0 g |" in report
    )
    assert "| nutrition.nutrients.sodium.amount | 1 | 2 | 50.0% |" in report


def test_render_report_without_prices_or_mismatches(monkeypatch):
    monkeypatch.delenv("VISION_PRICE_INPUT_PER_MTOK", raising=False)
    records = {"a": Record("a", {"status": "not_found"}, None, "m", 1.0)}

    report = render_report({"a": [TruthRow("status", "not_found", "")]}, records)

    assert "set VISION_PRICE_INPUT_PER_MTOK" in report
    assert "### Mismatches\n\nNone." in report


def make_fixtures(tmp_path: Path) -> Path:
    (tmp_path / "images").mkdir(parents=True)
    (tmp_path / "images" / "001_crackers.jpg").write_bytes(b"jpg")
    (tmp_path / "images" / "002_box_back.jpg").write_bytes(b"jpg")
    (tmp_path / "images" / "notes.txt").write_text("not a photo")
    (tmp_path / "ground_truth.csv").write_text(CSV, encoding="utf-8")
    return tmp_path


def test_main_runs_photos_saves_and_rescores(tmp_path, monkeypatch, capsys):
    fixtures = make_fixtures(tmp_path / "fx")
    out = tmp_path / "out"
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    def fake_extract(photo, config):
        if photo.name.startswith("002"):
            raise LabelExtractionError("HTTP 500")
        return Extraction(RESULT, config.model, 3.0, 1000, 100)

    monkeypatch.setattr(lb, "extract_label_file", fake_extract)

    # 002 failed with an API error: the run is incomplete, not a score (#18).
    assert lb.main(["--fixtures", str(fixtures), "--out", str(out)]) == lb.EXIT_INCOMPLETE
    first = capsys.readouterr().out
    assert "**Aggregate field accuracy: 100.0% (2/2)**" in first
    assert sorted(p.name for p in out.iterdir()) == [
        "001_crackers.jpg.json",
        "002_box_back.jpg.json",
    ]
    assert json.loads((out / "002_box_back.jpg.json").read_text())["error"] == "HTTP 500"

    monkeypatch.setattr(lb, "extract_label_file", None)  # --from must not call the API
    assert lb.main(["--fixtures", str(fixtures), "--from", str(out)]) == lb.EXIT_INCOMPLETE
    assert capsys.readouterr().out == first


def test_main_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(lb, "load_dotenv", lambda: None)

    assert lb.main(["--fixtures", str(tmp_path)]) == 1
    assert "no photos" in capsys.readouterr().err

    fixtures = make_fixtures(tmp_path / "fx")
    assert lb.main(["--fixtures", str(fixtures)]) == 1
    assert "GEMINI_API_KEY" in capsys.readouterr().err

    with (fixtures / "ground_truth.csv").open("a", encoding="utf-8") as f:
        f.write("001_crackers.jpg,serving.household,,\n")
    assert lb.main(["--fixtures", str(fixtures)]) == 1
    assert "serving.household has no expected value" in capsys.readouterr().err


# --- Q1 pass/fail and critical fields (#18) ---------------------------------------

PASSING_RESULT = {
    "status": "found",
    "serving": {"size_text": "6 crackers (30 g)", "household": "6", "quantity": 30.0, "unit": "g"},
    "package": {"servings_per_package": 4.0},
    "nutrition": {
        "basis": "serving",
        "nutrients": {"sodium": {"amount": 310.0, "unit": "mg", "daily_value_percent": 13.0}},
    },
}
PASSING_TRUTH = [
    TruthRow("serving.quantity", "30", "g"),
    TruthRow("package.servings_per_package", "4", ""),
    TruthRow("nutrition.nutrients.sodium.amount", "310", "mg"),
]


def test_evaluate_meets_the_target_exactly():
    # 19 of 20 fields correct is 95%: a pass. 18 of 20 is 90%: a fail.
    passing = lb.Evaluation([], 19, 20, 95.0, [])
    failing = lb.Evaluation([], 18, 20, 95.0, [])
    assert passing.accuracy_met and passing.passed and passing.needed == 19
    assert not failing.accuracy_met and not failing.passed
    assert not lb.Evaluation([], 20, 20, 95.0, ["001.jpg"]).passed  # unsafe photo: fail


def test_evaluate_just_below_target_fails_even_though_it_prints_as_95():
    ev = lb.Evaluation([], 9499, 10000, 95.0, [])  # 94.99%
    assert lb._pct(ev.correct, ev.total) == "95.0%"
    assert not ev.accuracy_met


def test_evaluate_nothing_scored_is_a_fail():
    ev = lb.evaluate({}, {})
    assert ev.total == 0 and not ev.passed
    assert "nothing was scored" in "\n".join(lb.verdict_lines(ev))


def test_critical_safe_use_checks_every_photo_with_a_table():
    records = {
        "001.jpg": Record("001.jpg", PASSING_RESULT),
        "002.jpg": Record("002.jpg", {"status": "not_found"}),  # no table: nothing to use
        "003.jpg": Record("003.jpg", None, error="HTTP 500"),
    }
    assert lb.critical_safe_use(records) == (1, [])


def test_critical_safe_use_fails_when_a_photo_value_is_not_unconfirmed(monkeypatch):
    def confirmed(result):
        reading = to_contract(result)
        object.__setattr__(reading.package, "certainty", Certainty.USER_CONFIRMED)
        return reading

    monkeypatch.setattr(lb, "to_contract", confirmed)
    checked, unsafe = lb.critical_safe_use({"001.jpg": Record("001.jpg", PASSING_RESULT)})
    assert (checked, unsafe) == (1, ["001.jpg"])


def test_critical_safe_use_fails_closed_on_a_reply_it_cannot_read():
    record = Record("001.jpg", {"status": "found", "serving": {"quantity": "lots", "unit": "g"}})
    assert lb.critical_safe_use({"001.jpg": record}) == (1, ["001.jpg"])


def test_report_has_a_verdict_and_a_critical_fields_section():
    report = render_report(
        {"001.jpg": PASSING_TRUTH}, {"001.jpg": Record("001.jpg", PASSING_RESULT)}
    )

    assert "**Q1 verdict: PASS**: aggregate accuracy 100.0% (3/3) against the 95% target" in report
    assert "at least 3 correct fields were needed" in report
    assert "### Critical fields (they set the serving multiplier in F2)" in report
    assert "| serving.quantity | 1 | 1 | 100.0% |" in report
    assert "| package.servings_per_package | 1 | 1 | 100.0% |" in report
    assert "Safe use (Q1: 100%): 1 of 1 photos" in report
    assert "wrong or missing (the user must catch these when confirming):\n\nNone." in report


def test_report_lists_wrong_critical_values_and_fails():
    wrong = {**PASSING_RESULT, "package": {"servings_per_package": 14.0}}
    report = render_report({"001.jpg": PASSING_TRUTH}, {"001.jpg": Record("001.jpg", wrong)})

    assert "**Q1 verdict: FAIL**: aggregate accuracy 66.7% (2/3)" in report
    assert "| 001.jpg | package.servings_per_package | wrong | 4 | 14 |" in report
    assert "| package.servings_per_package | 0 | 1 | 0.0% |" in report


def test_report_names_unsafe_photos(monkeypatch):
    monkeypatch.setattr(lb, "critical_safe_use", lambda records: (2, ["002.jpg"]))
    report = render_report(
        {"001.jpg": PASSING_TRUTH}, {"001.jpg": Record("001.jpg", PASSING_RESULT)}
    )

    assert "**Q1 verdict: FAIL**" in report
    assert "critical-field safe use FAILED on 1 photo(s)" in report
    assert "Safe use (Q1: 100%): 1 of 2 photos" in report
    assert "Unsafe: 002.jpg" in report


def test_main_exits_zero_when_q1_is_met(tmp_path, monkeypatch, capsys):
    fixtures = tmp_path / "fx"
    (fixtures / "images").mkdir(parents=True)
    (fixtures / "images" / "001_crackers.jpg").write_bytes(b"jpg")
    (fixtures / "ground_truth.csv").write_text(
        "image,field,expected,unit\n"
        "001_crackers.jpg,serving.quantity,30,g\n"
        "001_crackers.jpg,package.servings_per_package,4,\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setattr(
        lb, "extract_label_file", lambda photo, config: Extraction(PASSING_RESULT, "m", 1.0, 1, 1)
    )

    assert lb.main(["--fixtures", str(fixtures)]) == 0
    assert "**Q1 verdict: PASS**" in capsys.readouterr().out


# --- API errors are not misreads (review of #18) ----------------------------------


def _two_photos(second_record):
    truth = {"001.jpg": PASSING_TRUTH, "002.jpg": PASSING_TRUTH}
    records = {"001.jpg": Record("001.jpg", PASSING_RESULT), "002.jpg": second_record}
    return truth, records


def test_a_photo_that_failed_with_an_api_error_is_left_out_of_the_score():
    truth, records = _two_photos(Record("002.jpg", None, error="HTTP 429: quota"))
    ev = lb.evaluate(truth, records)

    assert (ev.correct, ev.total) == (3, 3)  # the failed photo's 3 fields are not "missing"
    assert ev.failed == ["002.jpg"]
    assert ev.verdict == "INCOMPLETE" and not ev.passed
    assert ev.exit_code == lb.EXIT_INCOMPLETE == 1


def test_a_missing_photo_still_counts_as_missing():
    truth, records = _two_photos(None)
    del records["002.jpg"]
    ev = lb.evaluate(truth, records)

    assert (ev.correct, ev.total) == (3, 6)
    assert ev.failed == [] and ev.verdict == "FAIL" and ev.exit_code == lb.EXIT_BELOW_TARGET


def test_a_misread_is_still_a_fail_not_incomplete():
    wrong = {**PASSING_RESULT, "package": {"servings_per_package": 14.0}}
    truth, records = _two_photos(Record("002.jpg", wrong))
    assert lb.evaluate(truth, records).verdict == "FAIL"


def test_an_unsafe_photo_fails_even_when_the_run_is_incomplete(monkeypatch):
    monkeypatch.setattr(lb, "critical_safe_use", lambda records: (1, ["001.jpg"]))
    truth, records = _two_photos(Record("002.jpg", None, error="HTTP 429"))
    assert lb.evaluate(truth, records).verdict == "FAIL"


def test_report_says_the_run_is_incomplete_and_how_many_photos_failed():
    truth, records = _two_photos(Record("002.jpg", None, error="HTTP 429: quota"))
    report = render_report(truth, records)

    assert "**Q1 verdict: INCOMPLETE**" in report
    assert "1 photo(s) failed with an API error" in report
    assert "run it again" in report
    assert "| 002.jpg | 0 | 0 | 0 | 0 |  | error, not scored: HTTP 429: quota |" in report
    assert "**Aggregate field accuracy: 100.0% (3/3)**" in report
    assert "Photos: 2 (1 failed)" in report


def test_scripts_do_not_import_datetime_utc():
    """datetime.UTC exists only since Python 3.11; the README promises 3.10 or newer."""
    import ast

    for path in Path(lb.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "datetime":
                assert "UTC" not in [alias.name for alias in node.names], path.name
