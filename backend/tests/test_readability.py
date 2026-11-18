"""Q3 readability check (#70): scoring, preprocessing and the default report."""

import json

import pytest

from scripts import readability as r


@pytest.mark.parametrize(
    ("word", "syllables"),
    [
        ("salt", 1),
        ("the", 1),
        ("sugar", 2),
        ("energy", 3),
        ("table", 2),
        ("vegetable", 4),
        ("makes", 1),
        ("added", 2),
        ("used", 1),
        ("carbohydrate", 4),
        ("chloride", 2),
        ("5", 1),
        ("%", 0),
    ],
)
def test_count_syllables(word, syllables):
    assert r.count_syllables(word) == syllables


def test_sentences_ignore_abbreviations_and_decimals():
    text = "Some foods, e.g. bread, have 0.5 g. Others do not! Is that so?"
    assert r.sentences(text) == [
        "Some foods, e.g. bread, have 0.5 g",
        "Others do not",
        "Is that so",
    ]


def test_grade_matches_the_formula():
    s = r.score("The cat sat on the mat. It was a good cat.")
    assert (s.sentences, s.words, s.syllables) == (2, 11, 11)
    assert s.grade == pytest.approx(0.39 * 11 / 2 + 11.8 * 11 / 11 - 15.59)


def test_empty_text_has_no_grade():
    assert r.score("").grade is None
    assert r.score(r.preprocess("See https://example.com.")).words == 1


def test_preprocess_removes_urls_citations_names_and_terms():
    text = (
        "Sodium chloride (salt) adds taste (Source: Health Canada) [1]. "
        "See https://www.canada.ca/x. Aim for 5% DV or less of %DV."
    )
    out = r.preprocess(text, names=["salt", "Sodium chloride"], terms=r.DEFINED_TERMS)
    assert "salt" not in out.lower()
    assert "chloride" not in out
    assert "canada.ca" not in out
    assert "Health Canada" not in out
    assert "[1]" not in out
    assert "DV" not in out
    assert "()" not in out and "( )" not in out
    assert out.startswith("adds taste")


def test_name_removal_matches_whole_words_only():
    assert r.preprocess("Salted foods have salt.", names=["salt"]) == "Salted foods have."


def test_default_products_cover_three_categories_and_pass():
    reports = [
        r.collect(
            r.load_product(path),
            r.load_nutrient_content(),
            r.load_ingredient_knowledge(),
            category=category,
        )
        for path, category in r.DEFAULT_PRODUCTS
    ]
    assert len({report.category for report in reports}) >= 3
    result = r.evaluate(reports)
    assert all(report.score.words >= 300 for report in reports)
    assert result.passed, r.to_markdown(result, keep_defined_terms=False)


def test_scored_text_has_no_names_or_urls():
    product = r.load_product(r.DEFAULT_PRODUCTS[0][0])
    report = r.collect(product, r.load_nutrient_content(), r.load_ingredient_knowledge())
    wheres = [t.where for t in report.texts]
    assert "glossary %DV" in wheres
    assert "nutrient sodium / what_it_is" in wheres
    assert any(w.startswith("ingredient ") for w in wheres)
    passage = report.passage
    assert "http" not in passage
    assert "Ketchup" not in passage
    assert "%DV" not in passage


def test_main_exit_status_and_outputs(tmp_path, capsys):
    assert r.main([]) == 0
    assert "**PASS**" in capsys.readouterr().out

    assert r.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["passed"] is True
    assert len(data["products"]) == 3

    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert r.main(["--product", str(bad)]) == 2


def test_main_fails_above_target(monkeypatch, capsys):
    monkeypatch.setattr(r, "TARGET_GRADE", 1.0)
    assert r.main([]) == 1
    assert "**FAIL**" in capsys.readouterr().out
