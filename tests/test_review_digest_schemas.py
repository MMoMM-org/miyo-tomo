#!/usr/bin/env python3
# version: 0.1.1
"""test_review_digest_schemas.py — spec 047 T4.1: the digest and carryover file contracts.

The two closed schemas under ``tomo/schemas/`` are what ``review-digest.py check``
validates the agents' files against first (SDD ADR-4, Application Data Models).
The positive fixtures are the W14 digest and carryover of the SDD's walkthrough (b);
every refusal case mutates one field of them, so a test fails exactly when the
schema stops enforcing that one rule (an unknown field, an empty text, a cap,
an id or key pattern, a type enum, the growth candidates' notes bounds).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

import jsonschema  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = REPO_ROOT / "tomo" / "schemas"
DIGEST_SCHEMA = SCHEMAS / "review-digest.schema.json"
CARRYOVER_SCHEMA = SCHEMAS / "review-carryover.schema.json"

# SDD walkthrough (b): 2026-W14 with previous week and previous month.
W14_DIGEST = {
    "read_id": "R",
    "unit": "2026-W14",
    "days": ["2026-03-30", "2026-03-31"],
    "done": [{"text": "5 km run", "sources": ["2026-03-31"]}],
    "open": [],
    "themes": [],
    "sections": [],
    "child_notes": [],
    "notable": [],
    "growth": [],
}
W14_CARRYOVER = {
    "read_id": "R",
    "notes": [
        {"path": "Calendar/302 Weekly/2026-W13.md", "kind": "week", "name": "2026-W13", "items": 2},
        {"path": "Calendar/303 Monthly/2026-02.md", "kind": "month", "name": "2026-02", "items": 1},
    ],
    "items": [
        {"id": "c1", "type": "intention", "text": "Start running again", "sources": ["2026-W13", "2026-02"]},
        {"id": "c2", "type": "open", "text": "Call Jana about the trip", "sources": ["2026-W13"]},
    ],
}


def _validator(path: Path) -> jsonschema.Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


@pytest.fixture(scope="module")
def digest() -> jsonschema.Draft202012Validator:
    return _validator(DIGEST_SCHEMA)


@pytest.fixture(scope="module")
def carryover() -> jsonschema.Draft202012Validator:
    return _validator(CARRYOVER_SCHEMA)


def _entry(i: int = 0) -> dict:
    return {"text": f"item {i}", "sources": ["2026-03-31"]}


def _growth(n_notes: int = 1) -> dict:
    return {
        "text": "Two new notes on running",
        "sources": ["2026-03-31"],
        "notes": [f"Atlas/Notes/Run {i}.md" for i in range(n_notes)],
    }


def _carry_item(i: int = 1) -> dict:
    return {"id": f"c{i}", "type": "open", "text": "t", "sources": ["2026-W13"]}


def _with(base: dict, **fields) -> dict:
    doc = copy.deepcopy(base)
    doc.update(fields)
    return doc


# --- positive fixtures -------------------------------------------------------


def test_w14_digest_validates(digest):
    digest.validate(W14_DIGEST)


def test_w14_carryover_validates(carryover):
    carryover.validate(W14_CARRYOVER)


def test_single_day_theme_is_allowed_in_a_digest(digest):
    theme = {"text": "Running", "days": ["2026-03-31"], "sources": ["2026-03-31"]}
    digest.validate(_with(W14_DIGEST, themes=[theme]))


def test_section_with_known_key_pattern_validates(digest):
    digest.validate(_with(W14_DIGEST, sections=[{"key": "s12", "items": [_entry()]}]))


@pytest.mark.parametrize("n_notes", [1, 10])
def test_growth_candidate_validates_with_one_to_ten_notes(digest, n_notes):
    digest.validate(_with(W14_DIGEST, growth=[_growth(n_notes)]))


_THEME = {"text": "Running", "days": ["2026-03-31"], "sources": ["2026-03-31"]}


@pytest.mark.parametrize(
    "field, doc",
    [
        ("done", _with(W14_DIGEST, done=[_entry(i) for i in range(25)])),
        ("open", _with(W14_DIGEST, open=[_entry(i) for i in range(25)])),
        ("notable", _with(W14_DIGEST, notable=[_entry(i) for i in range(15)])),
        ("themes", _with(W14_DIGEST, themes=[_THEME] * 15)),
        ("child_notes", _with(W14_DIGEST, child_notes=[_entry(i) for i in range(15)])),
        ("growth", _with(W14_DIGEST, growth=[_growth() for _ in range(15)])),
        ("section items", _with(W14_DIGEST, sections=[{"key": "s1", "items": [_entry(i) for i in range(30)]}])),
    ],
)
def test_digest_caps_are_inclusive(digest, field, doc):
    digest.validate(doc)


def test_carryover_cap_is_inclusive(carryover):
    carryover.validate(_with(W14_CARRYOVER, items=[_carry_item(i) for i in range(1, 31)]))


# --- digest refusals ---------------------------------------------------------


def _refused(validator, doc) -> None:
    assert not validator.is_valid(doc), "schema accepted a document it must refuse"


def test_digest_refuses_an_unknown_top_level_field(digest):
    _refused(digest, _with(W14_DIGEST, summary="free text"))


def test_digest_refuses_an_unknown_entry_field(digest):
    _refused(digest, _with(W14_DIGEST, done=[{**_entry(), "score": 1}]))


def test_digest_refuses_an_empty_text(digest):
    _refused(digest, _with(W14_DIGEST, done=[{"text": "", "sources": ["2026-03-31"]}]))


@pytest.mark.parametrize("entry", [{"text": "call"}, {"text": "call", "sources": []}], ids=["absent", "empty"])
def test_digest_refuses_an_entry_without_sources(digest, entry):
    _refused(digest, _with(W14_DIGEST, open=[entry]))


def test_digest_refuses_more_than_25_done(digest):
    _refused(digest, _with(W14_DIGEST, done=[_entry(i) for i in range(26)]))


@pytest.mark.parametrize("key", ["S1", "s", "s1234", "section 1", "x1"])
def test_digest_refuses_a_section_key_outside_the_pattern(digest, key):
    _refused(digest, _with(W14_DIGEST, sections=[{"key": key, "items": [_entry()]}]))


def test_digest_refuses_a_growth_candidate_without_notes(digest):
    candidate = _growth()
    del candidate["notes"]
    _refused(digest, _with(W14_DIGEST, growth=[candidate]))
    _refused(digest, _with(W14_DIGEST, growth=[_growth(0)]))


def test_digest_refuses_a_growth_candidate_with_more_than_ten_notes(digest):
    _refused(digest, _with(W14_DIGEST, growth=[_growth(11)]))


def test_digest_refuses_a_growth_candidate_without_sources(digest):
    _refused(digest, _with(W14_DIGEST, growth=[{**_growth(), "sources": []}]))


def test_digest_refuses_more_than_15_growth_candidates(digest):
    _refused(digest, _with(W14_DIGEST, growth=[_growth() for _ in range(16)]))


def test_digest_refuses_a_theme_without_days(digest):
    _refused(digest, _with(W14_DIGEST, themes=[{"text": "Running", "days": [], "sources": ["2026-03-31"]}]))


# --- carryover refusals ------------------------------------------------------


def test_carryover_refuses_an_unknown_field(carryover):
    _refused(carryover, _with(W14_CARRYOVER, extra=True))
    item = {**W14_CARRYOVER["items"][0], "age": 2}
    _refused(carryover, _with(W14_CARRYOVER, items=[item]))


def test_carryover_refuses_an_empty_text(carryover):
    item = {**W14_CARRYOVER["items"][0], "text": ""}
    _refused(carryover, _with(W14_CARRYOVER, items=[item]))


def test_carryover_refuses_an_item_without_sources(carryover):
    item = {**W14_CARRYOVER["items"][0], "sources": []}
    _refused(carryover, _with(W14_CARRYOVER, items=[item]))


@pytest.mark.parametrize("item_id", ["C1", "c", "c1234", "s1", "1"])
def test_carryover_refuses_an_id_outside_the_pattern(carryover, item_id):
    item = {**W14_CARRYOVER["items"][0], "id": item_id}
    _refused(carryover, _with(W14_CARRYOVER, items=[item]))


@pytest.mark.parametrize("item_type", ["done", "task", ""])
def test_carryover_refuses_a_type_outside_open_intention_theme(carryover, item_type):
    item = {**W14_CARRYOVER["items"][0], "type": item_type}
    _refused(carryover, _with(W14_CARRYOVER, items=[item]))


def test_carryover_refuses_more_than_30_items(carryover):
    _refused(carryover, _with(W14_CARRYOVER, items=[_carry_item(i) for i in range(1, 32)]))


def test_carryover_refuses_a_note_kind_outside_week_month_quarter(carryover):
    note = {**W14_CARRYOVER["notes"][0], "kind": "year"}
    _refused(carryover, _with(W14_CARRYOVER, notes=[note]))


def test_carryover_refuses_a_negative_note_item_count(carryover):
    note = {**W14_CARRYOVER["notes"][0], "items": -1}
    _refused(carryover, _with(W14_CARRYOVER, notes=[note]))


@pytest.mark.parametrize("key", list(W14_CARRYOVER))
def test_carryover_refuses_a_missing_required_key(carryover, key):
    doc = copy.deepcopy(W14_CARRYOVER)
    del doc[key]
    _refused(carryover, doc)


@pytest.mark.parametrize("key", list(W14_DIGEST))
def test_digest_refuses_a_missing_required_key(digest, key):
    doc = copy.deepcopy(W14_DIGEST)
    del doc[key]
    _refused(digest, doc)


@pytest.mark.parametrize(
    "mutation",
    [
        {"open": [_entry(i) for i in range(26)]},
        {"notable": [_entry(i) for i in range(16)]},
        {"themes": [_THEME] * 16},
        {"child_notes": [_entry(i) for i in range(16)]},
        {"sections": [{"key": "s1", "items": [_entry(i) for i in range(31)]}]},
        {"days": []},
        {"days": ["2026-3-30"]},
        {"read_id": ""},
        {"unit": ""},
        {"themes": [{**_THEME, "days": ["30.03.2026"]}]},
    ],
    ids=[
        "open-26", "notable-16", "themes-16", "child_notes-16", "section-items-31",
        "days-empty", "days-bad-date", "read_id-empty", "unit-empty", "theme-days-bad-date",
    ],
)
def test_digest_refuses_one_mutation_of_the_w14_digest(digest, mutation):
    _refused(digest, _with(W14_DIGEST, **mutation))
