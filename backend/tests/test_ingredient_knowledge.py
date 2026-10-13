"""Strict content validation and collection lifecycle for #33."""

import copy
import json
from pathlib import Path

import pytest

from app.services.ingredient_knowledge import (
    CONTENT_DIR,
    IngredientKnowledgeBase,
    IngredientKnowledgeError,
    load_ingredient_knowledge,
    load_source_policy,
    parse_entry,
)
from scripts.validate_ingredients import main

DOCUMENTS = json.loads(
    (Path(__file__).parent / "fixtures/ingredients/entries.json").read_text(encoding="utf-8")
)


def document():
    return copy.deepcopy(next(e for e in DOCUMENTS if e["id"] == "titanium_dioxide"))


def parse(raw):
    return parse_entry(raw, load_source_policy(), "test-entry.json")


def test_production_collection_validates_without_synthetic_entries():
    kb = load_ingredient_knowledge()
    assert all("synthetic" not in e.explanation.text.casefold() for e in kb.entries.values())


def test_all_fixture_aliases_match_their_own_entry():
    kb = IngredientKnowledgeBase(((e["id"], e) for e in DOCUMENTS), load_source_policy())
    for raw in DOCUMENTS:
        assert kb.entries[raw["id"]].to_dict() == raw
        for name in (raw["name"], *raw["aliases"], *raw["e_numbers"], *raw["ins_numbers"]):
            assert kb.match(name).id == raw["id"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("id",), "Bad ID"),
        (("name",), ""),
        (("aliases",), "sugar"),
        (("aliases",), [" "]),
        (("aliases",), ["same", "same"]),
        (("aliases",), ["..."]),
        (("sources",), []),
        (("sources",), {}),
        (("sources", 0, "id"), "Bad ID"),
        (("sources", 0, "title"), 1),
        (("sources", 0, "url"), "https://www.canada.ca.evil.example/"),
        (("sources", 0, "url"), "https://evil.example/www.canada.ca"),
        (("sources", 0, "url"), "http://www.canada.ca/"),
        (("sources", 0, "url"), "https://user@www.canada.ca/"),
        (("sources", 0, "url"), "https://www.canada.ca:8000/"),
        (("sources", 0, "url"), "https://[broken"),
        (("sources", 0, "url"), "https://www.canada.ca/a b"),
        (("sources", 0, "published_on"), "2025-02-30"),
        (("sources", 0, "accessed_on"), "20250101"),
        (("last_reviewed",), ""),
        (("last_reviewed",), None),
        (("explanation", "text"), ""),
        (("why_used", "source_ids"), []),
        (("what_it_is", "source_ids"), ["missing"]),
        (("flag", "flag_reason"), " "),
        (("flag", "category"), "technical_name"),
        (("flag", "source_ids"), []),
        (("flag", "source_ids"), ["missing"]),
        (("flag", "position_ids"), []),
        (("flag", "position_ids"), ["missing"]),
        (("flag", "position_ids"), ["hc_position"]),
        (("authority_positions", 0, "authority"), "uk_fsa"),
        (("authority_positions", 0, "scope"), ""),
        (("authority_positions", 0, "source_ids"), ["efsa"]),
        (("e_numbers",), ["INS 171"]),
        (("e_numbers",), ["E171x5"]),
        (("ins_numbers",), ["171"]),
        (("ins_numbers",), ["INS 171(i)bad"]),
    ],
)
def test_rejects_invalid_fields(path, value):
    raw = document()
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(IngredientKnowledgeError, match="test-entry.json"):
        IngredientKnowledgeBase([("test-entry.json", raw)], load_source_policy())


@pytest.mark.parametrize("field", list(document()))
def test_every_entry_field_required(field):
    raw = document()
    del raw[field]
    with pytest.raises(IngredientKnowledgeError, match="missing fields"):
        parse(raw)


def test_unknown_fields_wrong_shapes_and_duplicate_ids():
    raw = document()
    raw["extra"] = True
    with pytest.raises(IngredientKnowledgeError, match="unknown fields"):
        parse(raw)
    with pytest.raises(IngredientKnowledgeError, match="expected an object"):
        parse([])
    for field, message in (
        ("sources", "duplicate source"),
        ("authority_positions", "duplicate position"),
    ):
        raw = document()
        raw[field].append(copy.deepcopy(raw[field][0]))
        with pytest.raises(IngredientKnowledgeError, match=message):
            parse(raw)


def test_single_authority_action_and_future_effective_date():
    raw = document()
    raw["flag"].update(category="authority_action", position_ids=["hc_position"], source_ids=["hc"])
    raw["authority_positions"][0]["effective_on"] = "2099-01-01"
    assert parse(raw).flagged
    raw["flag"]["source_ids"] = ["efsa"]
    with pytest.raises(IngredientKnowledgeError, match="unknown references"):
        parse(raw)


@pytest.mark.parametrize("collision", ["id", "name", "alias", "e_number", "ins_number"])
def test_cross_entry_collisions(collision):
    raw = document()
    other = document()
    other.update(id="other", name="Other", aliases=[], e_numbers=[], ins_numbers=[])
    if collision == "id":
        other["id"] = raw["id"]
    elif collision == "name":
        other["name"] = raw["name"].upper()
    else:
        other["aliases"] = {"alias": [" TiO2. "], "e_number": ["e 171"], "ins_number": ["ins-171"]}[
            collision
        ]
    with pytest.raises(IngredientKnowledgeError, match="duplicate canonical|collides"):
        IngredientKnowledgeBase([("a.json", raw), ("b.json", other)], load_source_policy())


def content_dir(tmp_path):
    (tmp_path / "entries").mkdir()
    (tmp_path / "source-policy.json").write_text(
        (CONTENT_DIR / "source-policy.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def test_loader_and_cli(tmp_path, monkeypatch, capsys):
    directory = content_dir(tmp_path)
    path = directory / "entries" / "titanium_dioxide.json"
    path.write_text(json.dumps({"schema_version": 1, "ingredient": document()}), encoding="utf-8")
    kb = load_ingredient_knowledge(directory)
    assert kb.match("E171").id == "titanium_dioxide"
    assert main(["--directory", str(directory)]) == 0
    assert "Validated 1" in capsys.readouterr().out
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    assert main(["--directory", str(directory)]) == 1
    assert "duplicate JSON key" in capsys.readouterr().out
    path.write_text("not JSON", encoding="utf-8")
    with pytest.raises(IngredientKnowledgeError, match="titanium_dioxide.json"):
        load_ingredient_knowledge(directory)
    monkeypatch.chdir(tmp_path)
    load_ingredient_knowledge()  # Default location does not depend on cwd.


@pytest.mark.parametrize("version", [2, True, "1"])
def test_unsupported_versions(tmp_path, version):
    directory = content_dir(tmp_path)
    path = directory / "entries" / "entry.json"
    path.write_text(
        json.dumps({"schema_version": version, "ingredient": document()}), encoding="utf-8"
    )
    with pytest.raises(IngredientKnowledgeError, match="unsupported ingredient"):
        load_ingredient_knowledge(directory)
    path = directory / "source-policy.json"
    path.write_text(
        json.dumps({"version": version, "allowed_hosts": ["canada.ca"]}), encoding="utf-8"
    )
    with pytest.raises(IngredientKnowledgeError, match="unsupported source-policy"):
        load_source_policy(path)


def test_missing_paths_and_invalid_policy(tmp_path):
    with pytest.raises(IngredientKnowledgeError, match="source-policy.json"):
        load_ingredient_knowledge(tmp_path)
    policy = tmp_path / "source-policy.json"
    policy.write_text(
        json.dumps({"version": 1, "allowed_hosts": ["*.canada.ca"]}), encoding="utf-8"
    )
    with pytest.raises(IngredientKnowledgeError, match="invalid exact hostname"):
        load_source_policy(policy)
    policy.write_text(json.dumps({"version": 1, "allowed_hosts": ["canada.ca"]}), encoding="utf-8")
    with pytest.raises(IngredientKnowledgeError, match="missing entries directory"):
        load_ingredient_knowledge(tmp_path)
