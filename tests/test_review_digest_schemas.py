#!/usr/bin/env python3
# version: 0.1.4
"""test_review_digest_schemas.py — spec 047 T4.1: the digest and carryover file contracts.

The two closed schemas under ``tomo/schemas/`` are what ``review-digest.py check``
validates the agents' files against first (SDD ADR-4, Application Data Models).
The positive fixtures are the W14 digest and carryover of the SDD's walkthrough (b);
every refusal case mutates one field of them, so a test fails exactly when the
schema stops enforcing that one rule (an unknown field, a nested required key, an empty text, a cap,
an id or key pattern, a type enum, the growth candidates' notes bounds). A walk over a
full document (one of every nested object) pins the rest: every value's type, every
string's non-emptiness, every object's closedness, and every enum member. Each pattern
is pinned end to end at every place it applies: both anchors, both bounds of every
quantifier, every literal and every character class.
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


@pytest.mark.parametrize("key", ["s1", "s12", "s123"])
def test_section_with_known_key_pattern_validates(digest, key):
    digest.validate(_with(W14_DIGEST, sections=[{"key": key, "items": [_entry()]}]))


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


@pytest.mark.parametrize(
    "key",
    [
        "S1", "s", "s1234", "section 1", "x1",
        "xs1", "s1x",  # text before or after the key
        "s/", "s:",  # a non-digit just below "0", just above "9"
        "s\uff11",  # a full-width digit
    ],
)
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


@pytest.mark.parametrize(
    "item_id",
    [
        "C1", "c", "c1234", "s1", "1",
        "xc1", "c1x",  # text before or after the id
        "c/", "c:",  # a non-digit just below "0", just above "9"
        "c\uff11",  # a full-width digit
    ],
)
def test_carryover_refuses_an_id_outside_the_pattern(carryover, item_id):
    item = {**W14_CARRYOVER["items"][0], "id": item_id}
    _refused(carryover, _with(W14_CARRYOVER, items=[item]))


@pytest.mark.parametrize("item_id", ["c1", "c123"])
def test_carryover_accepts_an_id_of_one_to_three_digits(carryover, item_id):
    carryover.validate(_with(W14_CARRYOVER, items=[{**_carry_item(), "id": item_id}]))


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


_SECTION = {"key": "s1", "items": [_entry()]}


def _nested_doc(owner: str, obj: dict) -> tuple[str, dict]:
    """The W14 fixture with ``obj`` as the one nested object of ``owner``."""
    if owner == "note":
        return "carryover", _with(W14_CARRYOVER, notes=[obj])
    if owner == "item":
        return "carryover", _with(W14_CARRYOVER, items=[obj])
    field = {"entry": "done", "theme": "themes", "section": "sections", "growth": "growth"}[owner]
    return "digest", _with(W14_DIGEST, **{field: [obj]})


_NESTED_OBJECTS = {
    "note": W14_CARRYOVER["notes"][0],
    "item": _carry_item(),
    "entry": _entry(),
    "theme": _THEME,
    "section": _SECTION,
    "growth": _growth(),
}


@pytest.mark.parametrize(
    "owner, key",
    [(owner, key) for owner, obj in _NESTED_OBJECTS.items() for key in obj],
    ids=lambda v: v,
)
def test_refuses_a_nested_object_missing_a_required_key(request, owner, key):
    obj = copy.deepcopy(_NESTED_OBJECTS[owner])
    schema, intact = _nested_doc(owner, obj)
    validator = request.getfixturevalue(schema)
    validator.validate(intact)
    del obj[key]
    _refused(validator, _nested_doc(owner, obj)[1])


@pytest.mark.parametrize(
    "mutation",
    [
        {"read_id": ""},
        {"notes": [{**W14_CARRYOVER["notes"][0], "path": ""}]},
        {"notes": [{**W14_CARRYOVER["notes"][0], "name": ""}]},
    ],
    ids=["read_id-empty", "note-path-empty", "note-name-empty"],
)
def test_carryover_refuses_an_empty_string(carryover, mutation):
    _refused(carryover, _with(W14_CARRYOVER, **mutation))


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


# --- every field of a full document ------------------------------------------
# One of every nested object, so a walk over the fixture reaches every keyword of both
# schemas: each value of the wrong type, each string emptied, each object given an
# unknown key must be refused, and each enum member must be accepted.

FULL_DIGEST = _with(
    W14_DIGEST,
    open=[_entry(1)],
    notable=[_entry(2)],
    themes=[copy.deepcopy(_THEME)],
    sections=[copy.deepcopy(_SECTION)],
    child_notes=[{"text": "weekly note says", "sources": ["2026-W14"]}],
    growth=[_growth()],
)
_FULL = {"digest": FULL_DIGEST, "carryover": W14_CARRYOVER}


def _walk(node, path=()):
    yield path, node
    children = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
    for key, child in children:
        yield from _walk(child, (*path, key))


def _replaced(doc, path, value):
    doc = copy.deepcopy(doc)
    if not path:
        return value
    parent = doc
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    return doc


def _wrong_types(value) -> list:
    if isinstance(value, dict):
        return [[], "x"]
    if isinstance(value, list):
        return ["x", {}]
    if isinstance(value, str):
        return [1, None]
    if isinstance(value, int):
        return [1.5, "2"]
    raise TypeError(value)


def _cases(predicate, make):
    return [
        pytest.param(schema, path, bad, id=f"{schema}:{'/'.join(map(str, path)) or '<root>'}:{bad!r}")
        for schema, doc in _FULL.items()
        for path, value in _walk(doc)
        if predicate(value)
        for bad in make(value)
    ]


@pytest.mark.parametrize("schema", list(_FULL))
def test_full_document_validates(request, schema):
    request.getfixturevalue(schema).validate(_FULL[schema])


@pytest.mark.parametrize("schema, path, bad", _cases(lambda v: True, _wrong_types))
def test_refuses_a_value_of_the_wrong_type(request, schema, path, bad):
    _refused(request.getfixturevalue(schema), _replaced(_FULL[schema], path, bad))


@pytest.mark.parametrize("schema, path, bad", _cases(lambda v: isinstance(v, str), lambda v: [""]))
def test_refuses_an_empty_string_anywhere(request, schema, path, bad):
    _refused(request.getfixturevalue(schema), _replaced(_FULL[schema], path, bad))


@pytest.mark.parametrize(
    "schema, path, bad", _cases(lambda v: isinstance(v, dict), lambda v: [{**v, "unknown_key": 1}])
)
def test_refuses_an_unknown_key_on_any_object(request, schema, path, bad):
    _refused(request.getfixturevalue(schema), _replaced(_FULL[schema], path, bad))


@pytest.mark.parametrize("kind", ["week", "month", "quarter"])
def test_carryover_accepts_every_note_kind(carryover, kind):
    carryover.validate(_with(W14_CARRYOVER, notes=[{**W14_CARRYOVER["notes"][0], "kind": kind}]))


@pytest.mark.parametrize("item_type", ["open", "intention", "theme"])
def test_carryover_accepts_every_item_type(carryover, item_type):
    carryover.validate(_with(W14_CARRYOVER, items=[{**_carry_item(), "type": item_type}]))


# --- the patterns, at every place they apply ---------------------------------
# A character class is pinned by a non-digit just below "0" ("/") and just above "9"
# (":"), and by a full-width digit: jsonschema matches with Python's re, whose \d is any
# Unicode digit, so "[0-9]" -> "\d" would admit it.

_BAD_DATES = [
    "x2026-01-01",  # text before the date
    "2026-01-01x",  # text after the date
    "26-01-01", "202-01-01", "12026-01-01",  # a year of 2, 3 or 5 digits
    "2026-1-01", "2026-001-01",  # a month of 1 or 3 digits
    "2026-01-1", "2026-01-001",  # a day of 1 or 3 digits
    "2026/01-01", "2026-01/01",  # another separator after the year, after the month
    "202/-01-01", "2026-0/-01", "2026-01-0/",  # "/" in the year, the month, the day
    "202:-01-01", "2026-0:-01", "2026-01-0:",  # ":" in the year, the month, the day
    "\uff12026-01-01", "2026-\uff101-01", "2026-01-\uff101",  # a full-width digit in each
]

# Every place the digest applies $defs/date: its pointer, and the W14 digest with that one date there.
_DATE_PLACES = {
    "days": ("properties/days/items", lambda date: _with(W14_DIGEST, days=[date])),
    "theme days": (
        "properties/themes/items/properties/days/items",
        lambda date: _with(W14_DIGEST, themes=[{**_THEME, "days": [date]}]),
    ),
}


@pytest.mark.parametrize("place", list(_DATE_PLACES))
@pytest.mark.parametrize("date", _BAD_DATES)
def test_digest_refuses_a_date_outside_the_pattern(digest, place, date):
    with_date = _DATE_PLACES[place][1]
    digest.validate(with_date("2026-01-01"))
    _refused(digest, with_date(date))


def _pattern_places(schema: dict) -> set:
    """Pointers of the subschemas a pattern applies at, its own or a patterned $def's by $ref."""
    patterned = {f"#/$defs/{name}" for name, sub in schema.get("$defs", {}).items() if "pattern" in sub}
    return {
        "/".join(map(str, path))
        for path, node in _walk(schema)
        if isinstance(node, dict)
        and path[:1] != ("$defs",)
        and ("pattern" in node or node.get("$ref") in patterned)
    }


def test_every_place_a_pattern_applies_is_pinned_above():
    digest_schema = json.loads(DIGEST_SCHEMA.read_text(encoding="utf-8"))
    carryover_schema = json.loads(CARRYOVER_SCHEMA.read_text(encoding="utf-8"))
    date_places = {pointer for pointer, _ in _DATE_PLACES.values()}
    assert _pattern_places(digest_schema) == date_places | {"properties/sections/items/properties/key"}
    assert _pattern_places(carryover_schema) == {"properties/items/items/properties/id"}
