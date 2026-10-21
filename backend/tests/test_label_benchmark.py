import json
from pathlib import Path

import pytest

from app.services.label_extraction import Extraction, LabelExtractionError
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
    truth = {"001.jpg": TRUTH, "002.jpg": [TruthRow("status", "not_found", "")], "003.jpg": TRUTH}
    records = {
        "001.jpg": Record("001.jpg", RESULT, None, "m", 4.0, 1000, 200),
        "002.jpg": Record("002.jpg", {"status": "not_found"}, None, "m", 2.0, 1000, 200),
        "004.jpg": Record("004.jpg", None, "HTTP 500", "m"),
    }

    report = render_report(truth, records)

    assert "**Aggregate field accuracy: 36.4% (4/11)**" in report
    assert "Photos: 3 (1 failed)" in report
    assert "Response time: mean 3.0 s, max 4.0 s" in report
    assert "Cost per photo: mean $0.0008" in report
    assert "| 003.jpg | 0 | 0 | 5 | 0 |  | no photo |" in report
    assert "| 004.jpg | 0 | 0 | 0 | 0 |  | no ground truth; error: HTTP 500 |" in report
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

    assert lb.main(["--fixtures", str(fixtures), "--out", str(out)]) == 0
    first = capsys.readouterr().out
    assert "**Aggregate field accuracy: 66.7% (2/3)**" in first
    assert sorted(p.name for p in out.iterdir()) == [
        "001_crackers.jpg.json",
        "002_box_back.jpg.json",
    ]
    assert json.loads((out / "002_box_back.jpg.json").read_text())["error"] == "HTTP 500"

    monkeypatch.setattr(lb, "extract_label_file", None)  # --from must not call the API
    assert lb.main(["--fixtures", str(fixtures), "--from", str(out)]) == 0
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
