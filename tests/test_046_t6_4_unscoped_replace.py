#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_4_unscoped_replace.py — an unscoped `replace_between_markers` from the real producer path (spec 046 T6.4).

T6.1 proved the action's `$def` with a hand-written set whose action carries a `scope`. A `before` row re-run
produces the unscoped form (no `scope` key: its block sits above the heading, so no heading scopes it). This
builds that action through `plan_section` -> `SectionPlan.action` -> `rss.compose` ->
`build_review_instruction_set` on an existing note carrying its first block, and validates the set against BOTH
committed schemas (the producer's and Hashi's vendored copy). Mechanisms each test falsifies:

- the producer adding a `scope` to a `before` replace: ``test_the_built_action_is_unscoped``
- the producer emitting a shape either schema refuses (key, marker or version drift): ``test_the_set_validates_against_both_committed_schemas``
- the validation passing vacuously: ``test_a_broken_action_fails_both_schemas`` (each required field removed, an
  extra key, a bad marker: the same validation reports an error)
- the action not applying with Hashi's documented semantics: ``test_the_reference_applier_replaces_only_the_block``

Spec: docs/XDD/specs/046-review-template-sections/plan/phase-6.md (T6.1 "Open for T6.4")
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
sys.path.insert(0, str(REPO / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from e2e_046_sections_walk import APPLY  # noqa: E402
from lib import review_actions as ra  # noqa: E402
from lib import review_section_plan as rsp  # noqa: E402
from lib import review_section_set as rss  # noqa: E402

SCHEMAS = {"producer": REPO / "tomo" / "schemas" / "instructions.schema.json",
           "vendored": REPO / "tomo" / "schemas" / "hashi-instructions.schema.json"}
TARGET = "Calendar/Weekly/2026-W13.md"
PERIOD = "2026-W13"
ROW = {"id": "s1", "heading": "Reflection", "level": 2, "parent": None, "occurrence": 1, "placement": "before"}
NOTE = "# 2026-W13\n\nown text\n\n## Reflection\nreflect\n"


def _apply(text: str, action: dict) -> str:
    result, out = APPLY[action["action"]](text, action)
    assert result == "applied", (result, action)
    return out


def _built_set() -> dict:
    """First delivery, applied; the re-run's replace action wrapped in the wire envelope."""
    first = rsp.plan_section(ROW, NOTE, PERIOD, [{"text": "one item"}])
    assert first.mode == rsp.INSERT
    delivered = _apply(NOTE, first.action("I01", TARGET))
    again = rsp.plan_section(ROW, delivered, PERIOD, [{"text": "second item"}])
    assert again.mode == rsp.REPLACE
    plan = ra.ReviewPlan(ra.INSERT, TARGET, False, [], {})
    plan.actions = rss.compose([again], TARGET)
    return ra.build_review_instruction_set(plan, stem="2026-W13_review", generated="2026-11-19T08:00:00Z",
                                           profile="miyo")


def _errors(doc: dict, name: str) -> list:
    schema = json.loads(SCHEMAS[name].read_text(encoding="utf-8"))
    return [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)]


def test_the_built_action_is_unscoped():
    (action,) = _built_set()["actions"]
    assert action["action"] == "replace_between_markers"
    assert "scope" not in action
    assert action["content"] == "- second item"


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_the_set_validates_against_both_committed_schemas(name):
    assert _errors(_built_set(), name) == []


@pytest.mark.parametrize("name", sorted(SCHEMAS))
@pytest.mark.parametrize("mutate", [
    lambda a: a.pop("start_marker"),
    lambda a: a.pop("end_marker"),
    lambda a: a.pop("content"),
    lambda a: a.pop("target_path"),
    lambda a: a.update(extra=1),
    lambda a: a.update(start_marker=" %% tomo:s1 2026-W13 %%"),
    lambda a: a.update(scope={"heading": "Reflection"}),
], ids=["no-start", "no-end", "no-content", "no-target", "extra-key", "padded-marker", "scope-no-level"])
def test_a_broken_action_fails_both_schemas(mutate, name):
    """The same validation the happy path runs, on the built action with one thing broken: it reports an error."""
    doc = copy.deepcopy(_built_set())
    mutate(doc["actions"][0])
    assert _errors(doc, name) != []


def test_the_reference_applier_replaces_only_the_block():
    first = rsp.plan_section(ROW, NOTE, PERIOD, [{"text": "one item"}])
    delivered = _apply(NOTE, first.action("I01", TARGET))
    (action,) = _built_set()["actions"]
    after = _apply(delivered, action)
    assert after == delivered.replace("- one item", "- second item")
