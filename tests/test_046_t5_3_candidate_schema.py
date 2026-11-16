#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_3_candidate_schema.py — the test-only v4 candidate schema and the helper switch (spec 046 T5.3, ADR-5).

Until Hashi releases ``replace_between_markers`` (T6.1) no committed schema changes; a set carrying the new action
is validated against a candidate built by ``review_deliver_helpers.candidate_schema`` from the vendored Hashi copy
plus the handoff ``$def``, and every other set keeps validating against the committed schemas.

Mechanisms each test falsifies:
- the added ``$def`` and ``oneOf`` entry: ``test_candidate_validates_a_set_with_the_new_action``
- the ``$def``'s constraints (required, patterns, scope, no extra keys): ``test_candidate_rejects_a_malformed_action``
- the build from the vendored file (nothing else changed): ``test_candidate_is_the_vendored_copy_plus_the_def``
- the fixture writer: ``test_the_fixture_file_is_the_builder_output``
- the switch in ``schema_errors`` (both directions): ``test_schema_errors_switches_only_for_the_new_action``,
  ``test_schema_errors_still_reports_a_malformed_new_action``
- the committed schemas still lack the action (T6.1 flips this): ``test_committed_schemas_refuse_the_new_action``
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import (  # noqa: E402
    CANDIDATE_NAME,
    NEW_ACTION,
    SCHEMA_PARAMS,
    SCHEMAS,
    VENDORED,
    candidate_schema,
    schema_errors,
    write_candidate_schema,
)

from lib import review_section_plan as rsp  # noqa: E402

TARGET = "Efforts/200 Journal/2026/2026-W13.md"


def _replace(scope=True) -> dict:
    plan = rsp.SectionPlan(key="s1", mode="replace", start_marker=rsp.start_marker("s1", "2026-W13"),
                           end_marker=rsp.end_marker("s1", "2026-W13"), lines=["- one", "- two"],
                           scope={"heading": "What Went Well This Week?", "level": 4} if scope else None)
    return plan.action("I01", TARGET)


def _set(*actions) -> dict:
    return {"schema_version": "3", "type": "tomo-instructions", "generated": "2026-03-30T09:00:00Z",
            "profile": "miyo", "md_peer": "2026-W13_review_instructions", "actions": list(actions)}


def _insert() -> dict:
    return {"id": "I02", "action": "insert_under_marker", "target_path": TARGET,
            "anchor": {"type": "heading", "value": "In my own words"}, "placement": "before",
            "content": "## Tomo Review\n%% tomo-review 2026-W13 %%\n- alt\n"}


def _errors(doc: dict, schema: dict) -> list[str]:
    return [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)]


# ---------------------------------------------------------------- the candidate

@pytest.mark.parametrize("scope", [True, False], ids=["scoped", "unscoped"])
def test_candidate_validates_a_set_with_the_new_action(scope):
    assert _errors(_set(_replace(scope), _insert()), candidate_schema()) == []


@pytest.mark.parametrize("mutate", [
    lambda a: a.pop("end_marker"),
    lambda a: a.pop("content"),
    lambda a: a.update(start_marker=" %% tomo:s1 2026-W13 %%"),
    lambda a: a.update(end_marker="%% /tomo:s1\n2026-W13 %%"),
    lambda a: a.update(start_marker=""),
    lambda a: a.update(scope={"heading": "X", "level": 7}),
    lambda a: a.update(scope={"heading": "X"}),
    lambda a: a.update(scope={"heading": "X", "level": 2, "parent": "Y"}),
    lambda a: a.update(target_path=""),
    lambda a: a.update(extra=1),
], ids=["no-end", "no-content", "leading-space", "newline", "empty-start", "level-7", "scope-no-level",
        "scope-extra", "empty-target", "extra-key"])
def test_candidate_rejects_a_malformed_action(mutate):
    action = _replace()
    mutate(action)
    assert _errors(_set(action), candidate_schema()) != []


def test_candidate_is_the_vendored_copy_plus_the_def():
    vendored = json.loads(VENDORED.read_text(encoding="utf-8"))
    built = candidate_schema()
    assert NEW_ACTION not in vendored["$defs"]
    added = built["$defs"].pop(NEW_ACTION)
    assert added["properties"]["action"] == {"const": NEW_ACTION}
    one_of = built["properties"]["actions"]["items"]["oneOf"]
    assert one_of.pop() == {"$ref": f"#/$defs/{NEW_ACTION}"}
    assert built == vendored, "the candidate must change nothing but the new action"
    assert built["properties"]["schema_version"] == {"const": "3"}


def test_the_fixture_file_is_the_builder_output(tmp_path):
    path = write_candidate_schema(tmp_path)
    assert path == tmp_path / CANDIDATE_NAME == tmp_path / "instructions-v4-candidate.schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == candidate_schema()


def test_candidate_does_not_alias_the_def():
    first = candidate_schema()
    first["$defs"][NEW_ACTION]["required"].append("nope")
    assert "nope" not in candidate_schema()["$defs"][NEW_ACTION]["required"]


# ---------------------------------------------------------------- the switch

@pytest.mark.parametrize("schema", SCHEMA_PARAMS)
def test_schema_errors_switches_only_for_the_new_action(schema):
    assert schema_errors(_set(_replace(), _insert()), schema) == []
    bad = _insert()
    bad["placement"] = "sideways"
    committed = json.loads(schema.read_text(encoding="utf-8"))
    assert schema_errors(_set(bad), schema) == _errors(_set(bad), committed) != []


@pytest.mark.parametrize("schema", SCHEMA_PARAMS)
def test_schema_errors_still_reports_a_malformed_new_action(schema):
    action = _replace()
    action["scope"]["level"] = 0
    assert schema_errors(_set(action), schema) != []


@pytest.mark.parametrize("path", SCHEMAS, ids=[p.name for p in SCHEMAS])
def test_committed_schemas_refuse_the_new_action(path):
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert NEW_ACTION not in committed["$defs"]
    assert _errors(_set(copy.deepcopy(_replace())), committed) != []
