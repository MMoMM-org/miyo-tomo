#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_1_wire_v4.py — the instruction wire moves to v4 with `replace_between_markers` (spec 046 T6.1, ADR-5).

Hashi built the action on `feat/179-replace-between-markers`, commit abd92d6 (PR #181, not yet merged). The owner
decided the vendored copy is taken from that commit, pre-release, because Hashi releases only after the joint
test-vault run, and that run needs Tomo's v4 sets. Re-check byte-identity against the released tag before merge.

Pinned hash derivation, recompute with:
  git -C ../Hashi show abd92d6:src/schema/instructions.schema.json | shasum -a 256

Mechanisms each test falsifies:
- the vendored copy re-vendored byte for byte (any edit, or the old c217f66 copy): ``test_vendored_copy_is_hashi_abd92d6``,
  ``test_vendored_copy_matches_the_hashi_commit``
- Hashi's `$def` drifting from the handoff fragment: ``test_hashi_def_is_the_handoff_fragment``
- the producer schema lacking the action, or its `$def` differing from the contract's:
  ``test_producer_defines_the_action_as_the_contract_does``
- the `$def`'s constraints (required, patterns, scope, no extra keys) on both committed schemas:
  ``test_committed_schemas_reject_a_malformed_action``
- the producer still declaring "3": ``test_producer_declares_version_4``, ``test_wire_schema_version_reads_4``
- a producer emitting a literal instead of reading the schema: ``test_every_instruction_producer_reads_the_schema``,
  ``test_note_and_review_sets_carry_4``
- the shape manifest left at "3": ``test_shape_manifest_is_at_version_4``
- the vendored copy refusing waiting v3 sets, or the producer accepting one: ``test_vendored_accepts_v3_and_v4``,
  ``test_producer_refuses_a_v3_set``
- the T5.3 test-only candidate left behind: ``test_the_test_only_candidate_is_gone``
- Tomo's reference splice diverging from Hashi's own vectors: ``test_hashi_replace_vectors_through_the_reference``,
  ``test_hashi_insert_vectors_through_the_reference``

Spec: docs/XDD/specs/046-review-template-sections/plan/phase-6.md (T6.1)
Ref: SDD/ADR-5; SDD/Cross-Component Boundaries
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
SCRIPTS_DIR = REPO / "tomo" / "scripts"
SCHEMAS = REPO / "tomo" / "schemas"
PRODUCER = SCHEMAS / "instructions.schema.json"
VENDORED = SCHEMAS / "hashi-instructions.schema.json"
MANIFEST = SCHEMAS / "shapes" / "instructions.shape.json"
HASHI_REPO = REPO.parent / "Hashi"
HASHI_COMMIT = "abd92d6"
VENDORED_SHA256 = "51b80e494493c08ac2f03c90b4002e5ad1dd44d4dac1348b5bd22983bec23c91"
ACTION = "replace_between_markers"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from e2e_046_sections_walk import _insert_under_marker, _replace_between_markers  # noqa: E402

from lib import note_actions, note_meta  # noqa: E402
from lib import review_actions as ra  # noqa: E402
from lib.wire_version import wire_schema_version  # noqa: E402

# The `$def` of the handoff _outbox/for-hashi/2026-11-14_tomo-to-hashi_replace-between-markers.md §1, held as data.
HANDOFF_DEF = {
    "type": "object",
    "required": ["id", "action", "target_path", "start_marker", "end_marker", "content"],
    "additionalProperties": False,
    "description": "Replace only the lines strictly between a start-marker line and its end-marker line in an "
                   "existing note; the marker lines and every other line stay byte-identical. Modify-only.",
    "properties": {
        "id": {"$ref": "#/$defs/action_id"},
        "action": {"const": ACTION},
        "target_path": {"type": "string", "minLength": 1},
        "start_marker": {"type": "string", "minLength": 1, "pattern": "^\\S([^\\n]*\\S)?$"},
        "end_marker": {"type": "string", "minLength": 1, "pattern": "^\\S([^\\n]*\\S)?$"},
        "scope": {
            "type": "object", "required": ["heading", "level"], "additionalProperties": False,
            "properties": {"heading": {"type": "string", "minLength": 1},
                           "level": {"type": "integer", "minimum": 1, "maximum": 6}},
        },
        "content": {"type": "string",
                    "description": "Lines between the markers joined by \\n, no trailing newline; \"\" = zero lines."},
        "applied": {"$ref": "#/$defs/applied_field"},
    },
}
TARGET = "Calendar/Weekly/2026-W13.md"
START = "%% tomo:s1 2026-W13 %%"
END = "%% /tomo:s1 2026-W13 %%"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _set(version: str) -> dict:
    return {"schema_version": version, "type": "tomo-instructions", "generated": "2026-03-30T09:00:00Z",
            "profile": "miyo", "md_peer": "2026-W13_review_instructions",
            "actions": [{"id": "I01", "action": ACTION, "target_path": TARGET, "start_marker": START,
                         "end_marker": END, "content": "- one",
                         "scope": {"heading": "What Went Well This Week?", "level": 4}}]}


def _errors(doc: dict, path: Path) -> list[str]:
    return [e.message for e in jsonschema.Draft202012Validator(_load(path)).iter_errors(doc)]


# ---------------------------------------------------------------- the vendored contract

def test_vendored_copy_is_hashi_abd92d6():
    assert hashlib.sha256(VENDORED.read_bytes()).hexdigest() == VENDORED_SHA256


def test_vendored_copy_matches_the_hashi_commit():
    if not (HASHI_REPO / ".git").exists():
        pytest.skip(f"the Hashi checkout is absent: {HASHI_REPO} not found")
    shown = subprocess.run(["git", "-C", str(HASHI_REPO), "show", f"{HASHI_COMMIT}:src/schema/instructions.schema.json"],
                           capture_output=True, check=True).stdout
    assert shown == VENDORED.read_bytes()


def test_hashi_def_is_the_handoff_fragment():
    vendored = _load(VENDORED)
    assert vendored["$defs"][ACTION] == HANDOFF_DEF
    assert {"$ref": f"#/$defs/{ACTION}"} in vendored["properties"]["actions"]["items"]["oneOf"]


def test_vendored_accepts_v3_and_v4():
    assert _load(VENDORED)["properties"]["schema_version"]["enum"] == ["3", "4"]
    assert _errors(_set("4"), VENDORED) == []
    v3 = _set("3")
    v3["actions"] = [{"id": "I01", "action": "skip", "source_path": None, "reason": "nothing to do"}]
    assert _errors(v3, VENDORED) == []


# ---------------------------------------------------------------- the producer

def test_producer_defines_the_action_as_the_contract_does():
    producer = _load(PRODUCER)
    assert producer["$defs"][ACTION] == _load(VENDORED)["$defs"][ACTION]
    assert {"$ref": f"#/$defs/{ACTION}"} in producer["properties"]["actions"]["items"]["oneOf"]
    assert _errors(_set("4"), PRODUCER) == []


def test_producer_declares_version_4():
    assert _load(PRODUCER)["properties"]["schema_version"] == {"const": "4"}


def test_producer_refuses_a_v3_set():
    assert _errors(_set("3"), PRODUCER) != []


@pytest.mark.parametrize("path", [PRODUCER, VENDORED], ids=lambda p: p.name)
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
def test_committed_schemas_reject_a_malformed_action(mutate, path):
    """Moved from the removed T5.3 candidate test: the same constraints, now on the committed schemas."""
    doc = _set("4")
    mutate(doc["actions"][0])
    assert _errors(doc, path) != []


def test_wire_schema_version_reads_4():
    assert wire_schema_version("instructions.schema.json") == "4"


@pytest.mark.parametrize("path", ["instruction-render.py", "lib/note_actions.py", "lib/review_actions.py",
                                  "lib/review_delivery.py"])
def test_every_instruction_producer_reads_the_schema(path):
    text = (SCRIPTS_DIR / path).read_text(encoding="utf-8")
    assert '"schema_version": wire_schema_version(' in text
    assert '"schema_version": "' not in text


def test_note_and_review_sets_carry_4():
    meta = note_meta.new_meta(stem="s", run_id="r", created="2026-11-04T17:30:05Z", generated="2026-11-04T17:30:05Z",
                              template="Templates/t.md", template_stem="t", source_path=None, inbox="100 Inbox/",
                              title="T", destination="Atlas", default_destination="Atlas/", profile="miyo")
    assert note_actions.build_note_instruction_set(meta)["schema_version"] == "4"
    plan = ra.ReviewPlan(mode="new", target=TARGET, target_moved=False, duplicates=[], place={})
    doc = ra.build_review_instruction_set(plan, stem="2026-W13_review", generated="2026-03-30T09:00:00Z",
                                          profile="miyo")
    assert doc["schema_version"] == "4"


def test_shape_manifest_is_at_version_4():
    manifest = _load(MANIFEST)
    assert manifest["schema_version"] == "4"
    assert f"/$defs/{ACTION}" in manifest["nodes"]


def test_the_test_only_candidate_is_gone():
    helpers = (TESTS_DIR / "review_deliver_helpers.py").read_text(encoding="utf-8")
    for name in ("candidate_schema", "CANDIDATE_NAME", "REPLACE_BETWEEN_MARKERS", "instructions-v4-candidate"):
        assert name not in helpers, name
    assert not (TESTS_DIR / "test_046_t5_3_candidate_schema.py").exists()


# ---------------------------------------------------------------- Hashi's own vectors through Tomo's reference

# test/unit/actions/replaceBetweenMarkers.test.ts at abd92d6 (LF vectors; the CRLF addition is not modelled).
WEEK = "\n".join(["# 2026-W13", "#### What Went Well This Week?", "The user's own text stays here.", START,
                  "- old 1", "- old 2", END, "More user text after the block.", "#### What Was Hard?", "Untouched.",
                  ""])
SCOPE = {"heading": "What Went Well This Week?", "level": 4}
REPLACED = WEEK.replace("- old 1\n- old 2", "- new A\n- new B")
REPLACE_VECTORS = [
    ("replace", WEEK, {}, "applied", REPLACED),
    ("grow", WEEK, {"content": "a\nb\nc\nd"}, "applied", WEEK.replace("- old 1\n- old 2", "a\nb\nc\nd")),
    ("empty", WEEK, {"content": ""}, "applied", WEEK.replace("- old 1\n- old 2\n", "")),
    ("no-eol", "\n".join([START, "old", END]), {"content": "new"}, "applied", "\n".join([START, "new", END])),
    ("already", WEEK, {"content": "- old 1\n- old 2"}, "skipped-already", WEEK),
    ("padded", WEEK.replace(START, START + "  "), {}, "applied",
     WEEK.replace(START, START + "  ").replace("- old 1\n- old 2", "- new A\n- new B")),
    ("fenced", "\n".join(["```", START, "```", START, "old", END, ""]), {"content": "new"}, "applied",
     "\n".join(["```", START, "```", START, "new", END, ""])),
    ("indented", "\n".join(["  " + START, "old", END, ""]), {}, "failed", None),
    ("quoted", "\n".join(["> " + START, "old", END, ""]), {}, "failed", None),
    ("duplicated", "\n".join([START, "a", END, "", START, "b", END, ""]), {}, "failed", None),
    ("end-missing", "\n".join([END, START, "old", ""]), {}, "failed", None),
    ("second-end", "\n".join([START, "old", END, "text", END, ""]), {}, "failed", None),
    ("markers-equal", WEEK, {"end_marker": START}, "failed", None),
    ("scoped", WEEK, {"scope": SCOPE}, "applied", REPLACED),
    ("scope-level", WEEK, {"scope": {**SCOPE, "level": 3}}, "failed", None),
    ("scope-outside", WEEK, {"scope": {"heading": "What Was Hard?", "level": 4}}, "failed", None),
]


@pytest.mark.parametrize("text,over,outcome,after", [v[1:] for v in REPLACE_VECTORS],
                         ids=[v[0] for v in REPLACE_VECTORS])
def test_hashi_replace_vectors_through_the_reference(text, over, outcome, after):
    action = {"id": "I01", "action": ACTION, "target_path": TARGET, "start_marker": START, "end_marker": END,
              "content": "- new A\n- new B", **over}
    result, out = _replace_between_markers(text, action)
    assert result == outcome
    assert out == (text if after is None else after)


# test/unit/actions/insertUnderMarker.test.ts at abd92d6 (heading anchors, the only ones /review emits).
HEADING_DOC = "\n".join(["# Dev Log", "## Captures", "- old entry", "", "## Other", "- other"])
BLOCK = "### 2026-06-23\n\n- Shipped X"
INSERT_VECTORS = [
    ("inside", HEADING_DOC, {}, "applied",
     "\n".join(["# Dev Log", "## Captures", "- old entry", "", BLOCK, "## Other", "- other"])),
    ("inside-eof", "\n".join(["# Dev Log", "## Captures", "- old entry"]), {}, "applied",
     "\n".join(["# Dev Log", "## Captures", "- old entry", BLOCK])),
    ("before", HEADING_DOC, {"placement": "before", "content": "PRE"}, "applied",
     HEADING_DOC.replace("## Captures", "PRE\n## Captures")),
    ("after", HEADING_DOC, {"placement": "after", "content": "POST"}, "applied",
     HEADING_DOC.replace("## Captures", "## Captures\nPOST")),
    ("not-found", HEADING_DOC, {"anchor": {"type": "heading", "value": "Nonexistent"}}, "failed", HEADING_DOC),
    ("already", HEADING_DOC, {"content": "- old entry"}, "skipped-already", HEADING_DOC),
]


@pytest.mark.parametrize("text,over,outcome,after", [v[1:] for v in INSERT_VECTORS],
                         ids=[v[0] for v in INSERT_VECTORS])
def test_hashi_insert_vectors_through_the_reference(text, over, outcome, after):
    action = {"id": "I01", "action": "insert_under_marker", "target_path": TARGET,
              "anchor": {"type": "heading", "value": "Captures"}, "placement": "inside", "content": BLOCK, **over}
    assert _insert_under_marker(text, action) == (outcome, after)
