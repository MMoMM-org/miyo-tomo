#!/usr/bin/env python3
# version: 0.1.0
"""test_032_t6_1_end_to_end_routing.py — end-to-end routing test (T6.1).

Drives the PUBLIC entry points of the garden-audit Pass-1/Pass-2 pipeline
(not the internal helpers): render the report + wire from a doc
(garden-audit-render.render_frontmatter/render_report/build_wire_payload),
simulate the user's markdown decisions, join them via
garden-audit-parser.build_from_report, and assemble the Hashi action list via
lib.render_actions.build_garden_audit_actions — exactly the path
gen-garden-audit-hashi-example.py and test_garden_audit_hashi_example.py
already exercise for the Hashi wire (`[ref: memory: mock at orchestrator,
not helper]`).

One fixture, mixed by construction: a note with an INLINE-declared broken
parent (`up_source: "inline"`) and a note with a PROPERTY-declared broken
parent (`up_source: "frontmatter"`), both repointed by the user in one
approval pass. Phases 1-5 already make the routing itself work
(_route_broken_up); this test proves the whole chain produces the right
SHAPE, COUNT and ANCHORING end to end, and that the result is consumable
downstream (schema, instructions-diff, instructions-dryrun).

Spec: docs/XDD/specs/032-up-source-routing/plan/phase-6.md T6.1
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gar = _load("garden_audit_render", "garden-audit-render.py")
gap = _load("garden_audit_parser", "garden-audit-parser.py")
diff = _load("instructions_diff", "instructions-diff.py")
dryrun = _load("instructions_dryrun", "instructions-dryrun.py")

from lib.render_actions import build_garden_audit_actions  # noqa: E402

INLINE_PATH = "Notes/Inline Child.md"
INLINE_STEM = "Inline Child"
PROPERTY_PATH = "Notes/Property Child.md"
PROPERTY_STEM = "Property Child"

# The fixture's observed property value BEFORE the fix — asserted verbatim,
# order intact, as the edit_frontmatter action's `expected`.
PROPERTY_UP_VALUE = ["[[Old MOC]]", "[[Reisen (MOC)]]"]


def _finding(fid: str, path: str, stem: str, detail: dict) -> dict:
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": path, "stem": stem}, "detail": detail,
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _mixed_doc() -> dict:
    """One inline-declared + one property-declared broken-`up` finding.

    spec 033: up_broken_reason is always present once up_source/up_value are
    populated (a post-033-classified cache entry) — its absence is a
    DIFFERENT, deliberate shape (garden-audit-render.py's cause-unknown
    withhold reason), not this fixture's concern.
    """
    return {
        "run_id": "run-t6-1-001",
        "generated": "2026-09-02T10:00:00Z",
        "profile": "miyo",
        "skipped_checks": [], "skipped_checks_reason": "",
        "reappeared_exclusions": [],
        "findings": [
            _finding(
                "F01", INLINE_PATH, INLINE_STEM,
                {"up_target": "['Old Parent MOC']", "up_source": "inline", "up_value": None,
                 "up_broken_reason": "unresolved"},
            ),
            _finding(
                "F02", PROPERTY_PATH, PROPERTY_STEM,
                {"up_target": "Old MOC", "up_source": "frontmatter", "up_value": PROPERTY_UP_VALUE,
                 "up_broken_reason": "unresolved"},
            ),
        ],
    }


def _approve_both(report: str) -> str:
    """Simulate the user filling BOTH Repoint fields and approving the report."""
    # F01 (inline) — the body-oriented placeholder wording.
    report = report.replace(
        "- **Repoint to:** [[]]    ← enter the correct MOC to repoint "
        "up::, or leave empty to remove",
        "- **Repoint to:** [[New Parent MOC]]",
        1,
    )
    # F02 (property) — the property-oriented placeholder wording (names the
    # `up` property explicitly, never "up::" — spec 032 T5.1).
    report = report.replace(
        "- **Repoint to:** [[]]    ← enter the correct MOC to "
        "repoint the `up` property, or leave empty to remove",
        "- **Repoint to:** [[New MOC]]",
        1,
    )
    return report.replace("- [ ] Approved", "- [x] Approved", 1)


def _build_pipeline():
    """Run the real Pass-1 render -> user approval -> Pass-2 join -> assemble."""
    doc = _mixed_doc()
    report = "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)
    wire = gar.build_wire_payload(doc)
    report = _approve_both(report)

    parsed = gap.build_from_report(report, wire)
    actions = build_garden_audit_actions(parsed["confirmed_items"])
    return parsed, actions


# ---------------------------------------------------------------------------
# The core end-to-end assertions.
# ---------------------------------------------------------------------------

def test_both_notes_confirmed_through_the_report_placeholders():
    # Sanity: both Repoint placeholders were actually present and replaced —
    # if the placeholder text drifted, the replace() would silently no-op and
    # the confirmed_items assertions below would be the only signal.
    parsed, _ = _build_pipeline()
    assert len(parsed["confirmed_items"]) == 2
    assert parsed["unroutable"] == []


def test_total_action_count_is_exactly_two():
    # Guards against the seventh hollow-test mechanism this spec has already
    # produced eight times: an assertion satisfied by a MISSING action. If
    # the inline note silently emitted nothing, a test that only checked "is
    # there an edit_frontmatter" would still pass.
    _, actions = _build_pipeline()
    assert len(actions) == 2


def _anchor_path(action: dict) -> str:
    """The path of the note an action actually modifies.

    edit_frontmatter (and remove_up_link/resolve_dead_link) carry the note
    path as `path`; add_relationship carries it as `target_moc_path` (the
    note whose up:: line gets the new relationship line) — same field name
    as link_to_moc's target-MOC path, but a different meaning here.
    """
    return action["path"] if "path" in action else action["target_moc_path"]


def test_inline_note_gets_body_action_property_note_gets_edit_frontmatter():
    _, actions = _build_pipeline()
    by_path = {_anchor_path(a): a for a in actions}
    assert set(by_path) == {INLINE_PATH, PROPERTY_PATH}  # anchored, not swapped

    inline_action = by_path[INLINE_PATH]
    property_action = by_path[PROPERTY_PATH]

    # Inline-declared → body-oriented action (add_relationship: the up::
    # line is repointed in the note body), never edit_frontmatter.
    assert inline_action["action"] == "add_relationship"
    assert inline_action["action"] != "edit_frontmatter"

    # Property-declared → edit_frontmatter, never a body action.
    assert property_action["action"] == "edit_frontmatter"
    assert property_action["action"] != "add_relationship"


def test_edit_frontmatter_expected_matches_observed_value_order_intact():
    _, actions = _build_pipeline()
    property_action = next(a for a in actions if _anchor_path(a) == PROPERTY_PATH)
    assert property_action["expected"] == PROPERTY_UP_VALUE
    # The repoint replaces only the matched entry — the second entry's
    # position is untouched, proving order survives the transform (not just
    # the trivial remove-path identity).
    assert property_action["value"] == ["[[New MOC]]", "[[Reisen (MOC)]]"]


# ---------------------------------------------------------------------------
# Downstream consumers: schema, instructions-diff, instructions-dryrun.
# ---------------------------------------------------------------------------

def _instructions_envelope(parsed: dict, actions: list[dict]) -> dict:
    """Wrap actions exactly as instruction-render.py does for garden-audit."""
    return {
        "schema_version": "2",
        "type": "tomo-instructions",
        "source_suggestions": "garden-audit-report",
        "generated": "2026-09-02T10:05:00Z",
        "profile": parsed["profile"],
        "tomo_version": None,
        "action_count": len(actions),
        "md_peer": "2026-09-02_1000_garden-audit",
        "actions": actions,
        "tomo": {"doc_type": "garden-audit", "state": "pending-apply", "run_id": parsed["run_id"]},
    }


def test_instruction_set_validates_against_instructions_schema():
    parsed, actions = _build_pipeline()
    instructions = _instructions_envelope(parsed, actions)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=instructions, schema=schema)  # raises on failure


def test_instructions_diff_reconciles_with_no_mismatch():
    parsed, actions = _build_pipeline()
    instrs = {"action_count": len(actions), "actions": actions}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code, _obs = diff.run_diff(parsed, instrs)
    out = buf.getvalue()
    assert code == 0, out
    assert "RESULT: OK" in out


def test_instructions_dryrun_exits_0(tmp_path):
    parsed, actions = _build_pipeline()
    instructions = _instructions_envelope(parsed, actions)
    fixture = tmp_path / "instructions.json"
    fixture.write_text(json.dumps(instructions, ensure_ascii=False, indent=2), encoding="utf-8")

    argv = sys.argv
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        sys.argv = ["instructions-dryrun.py", str(fixture)]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = dryrun.main()
    finally:
        sys.argv = argv
    assert code == 0, stderr.getvalue()
    assert "unknown kind" not in stdout.getvalue()
