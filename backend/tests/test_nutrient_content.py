"""Reviewed nutrient explanation content (#38) and its loader."""

import copy
import json
import re

import pytest

from app.models.product import ALL_NUTRIENTS, CANONICAL_UNITS
from app.services.ingredient_knowledge import load_source_policy
from app.services.nutrient_content import (
    CONTENT_PATH,
    SOURCE_POLICY_PATH,
    Guidance,
    NutrientContentError,
    load_nutrient_content,
    parse_nutrient_content,
)

RAW = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
HOSTS = load_source_policy(SOURCE_POLICY_PATH)
CONTENT = load_nutrient_content()


def parse(raw):
    return parse_nutrient_content(raw, HOSTS, "test")


def mutated(change):
    raw = copy.deepcopy(RAW)
    change(raw)
    return raw


def entry(raw, nutrient_id):
    return next(e for e in raw["nutrients"] if e["id"] == nutrient_id)


def test_every_supported_nutrient_has_an_entry():
    assert set(CONTENT.nutrients) == set(ALL_NUTRIENTS)


def test_every_text_has_an_approved_source():
    for nutrient in CONTENT.nutrients.values():
        for text in (nutrient.what_it_is, nutrient.how_to_read):
            if text is not None:
                assert text.source_ids
                assert set(text.source_ids) <= set(CONTENT.sources)


def test_dv_definition_is_present():
    term = CONTENT.glossary["daily_value_percent"]
    assert "%DV" in term.term
    assert "5% DV or less is a little" in term.text.text
    assert "15% DV or more is a lot" in term.text.text


def test_guidance_distinguishes_limit_from_get_more():
    guidance = {name: n.guidance for name, n in CONTENT.nutrients.items()}
    assert guidance["sodium"] is Guidance.LIMIT
    assert guidance["sugars"] is Guidance.LIMIT
    assert guidance["saturated_fat"] is Guidance.LIMIT
    assert guidance["fibre"] is Guidance.GET_MORE


def test_no_verdict_words():
    banned = re.compile(r"\b(good|bad|healthy|unhealthy|avoid|dangerous|safe)\b", re.IGNORECASE)
    for nutrient in CONTENT.nutrients.values():
        for text in (nutrient.what_it_is, nutrient.how_to_read):
            if text is not None:
                assert not banned.search(text.text), (nutrient.id, text.text)


def test_daily_values_in_texts_match_the_table():
    # Every "Daily Value of N unit" must agree with Health Canada's table (2022-10-20).
    expected = {
        "total_fat": "75 g",
        "saturated_fat": "20 g",
        "sodium": "2300 mg",
        "fibre": "28 g",
        "sugars": "100 g",
    }
    for name, nutrient in CONTENT.nutrients.items():
        text = nutrient.how_to_read.text if nutrient.how_to_read else ""
        quoted = re.findall(r"Daily Value of (\d+ (?:g|mg))", text)
        assert quoted == ([expected[name]] if name in expected else []), name
        if name in expected:
            assert expected[name].endswith(CANONICAL_UNITS[name])


def test_nutrients_without_a_dv_say_so():
    for name in ("calories", "carbohydrate", "protein", "trans_fat", "cholesterol"):
        assert "no %DV" in CONTENT.nutrients[name].how_to_read.text


def test_cholesterol_has_no_unsourced_text():
    cholesterol = CONTENT.nutrients["cholesterol"]
    # No approved page explains dietary cholesterol; only the label reading is sourced.
    assert cholesterol.what_it_is is None
    assert cholesterol.how_to_read.source_ids == ("fats_food_labels",)


def test_carbohydrate_no_dv_does_not_cite_the_outdated_page():
    # The Carbohydrates page still quotes a 300 g Daily Value the current table dropped.
    how_to_read = CONTENT.nutrients["carbohydrate"].how_to_read
    assert "carbohydrates" not in how_to_read.source_ids


def test_content_is_reviewed():
    assert CONTENT.reviewed_on == "2026-10-15"
    assert CONTENT.reviewed_by == "Frank-The-Coder"
    assert CONTENT.is_reviewed


def test_unreviewed_content_loads():
    raw = mutated(lambda r: r.update(reviewed_on=None, reviewed_by=None))
    assert not parse(raw).is_reviewed


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["nutrients"].pop(), "missing"),
        (lambda r: r["nutrients"].append(copy.deepcopy(r["nutrients"][0])), "duplicate nutrient"),
        (lambda r: entry(r, "sodium").update(id="potassium"), "unknown nutrient"),
        (lambda r: entry(r, "sodium").update(guidance="bad"), "guidance"),
        (lambda r: entry(r, "sodium")["what_it_is"].update(source_ids=["nope"]), "unknown"),
        (lambda r: entry(r, "sodium")["what_it_is"].update(source_ids=[]), "non-empty"),
        (lambda r: entry(r, "sodium")["what_it_is"].update(text="  "), "non-blank"),
        (lambda r: r["sources"][0].update(url="http://www.canada.ca/x"), "HTTPS"),
        (lambda r: r["sources"][0].update(url="https://example.com/x"), "approved"),
        (lambda r: r["sources"].append(copy.deepcopy(r["sources"][0])), "duplicate id"),
        (lambda r: r.update(reviewed_by=None), "go together"),
        (lambda r: r.update(reviewed_on="16/10/2026", reviewed_by="x"), "date"),
        (lambda r: r.update(schema_version=2), "schema version"),
        (lambda r: r["glossary"].clear(), "%DV"),
        (lambda r: r.update(extra=1), "unknown fields"),
    ],
)
def test_broken_content_is_rejected(change, message):
    with pytest.raises(NutrientContentError, match=message):
        parse(mutated(change))


def test_unreadable_file_is_a_content_error(tmp_path):
    path = tmp_path / "nutrients.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(NutrientContentError):
        load_nutrient_content(path)
