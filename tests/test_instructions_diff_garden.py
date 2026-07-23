#!/usr/bin/env python3
# version: 0.1.0
"""test_instructions_diff_garden.py — garden-audit mode of the coverage audit.

Pre-existing gap (fixed 2026-07-23): garden-audit confirmed_items carry
garden_action, not the suggestions manifest shape — derive_expected miscounted
every garden item as an expected move_note, so the conductor's MANDATORY 3e
coverage audit hard-failed on ANY garden-audit doc with confirmed items.

Covers:
  - route:    garden-shaped parsed envelopes reach run_diff_garden
  - reconcile: a correct parser→builder render (all four garden_action kinds,
               incl. the new remove_up_link) → exit 0
  - falsify:  a missing / mismatched instruction still fails (exit 1)
  - advisory: acked_advisories produce no expected actions
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "instructions_diff", SCRIPTS_DIR / "instructions-diff.py"
)
diff = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(diff)

from lib.render_actions import build_garden_audit_actions  # noqa: E402


def _parsed_garden() -> dict:
    """One confirmed item per garden_action kind + one acked advisory."""
    return {
        "run_id": "run-diff-garden", "generated": "g", "profile": "miyo",
        "confirmed_items": [
            {"id": "F01", "garden_check": "dead_link",
             "garden_action": "edit_note_text", "path": "Notes/Src.md",
             "stem": "Src", "match": "[[Missing]]", "replace": "Missing",
             "occurrence": "all"},
            {"id": "F02", "garden_check": "broken_up",
             "garden_action": "remove_up_link", "path": "Notes/Broken.md",
             "stem": "Broken", "link": "Deleted MOC"},
            {"id": "F03", "garden_check": "broken_up",
             "garden_action": "add_relationship", "path": "Notes/Child.md",
             "stem": "Child", "up_line": "up:: [[Correct MOC]]"},
            {"id": "F04", "garden_check": "orphan",
             "garden_action": "file_note", "path": "Notes/Orphan.md",
             "stem": "Orphan", "target_moc": "Writing MOC",
             "target_moc_path": "MOCs/Writing MOC.md"},
        ],
        "acked_advisories": [
            {"id": "F05", "path": "Maps/Old MOC.md", "check": "stale_moc"},
        ],
    }


def _instrs(actions) -> dict:
    return {"action_count": len(actions), "actions": actions}


def _run(parsed, instrs):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code, obs = diff.run_diff(parsed, instrs)
    return code, buf.getvalue()


class TestGardenRoute:
    def test_garden_shape_detected(self):
        assert diff._is_garden_parsed(_parsed_garden()) is True

    def test_suggestions_shape_not_garden(self):
        assert diff._is_garden_parsed(
            {"confirmed_items": [{"id": "a1", "action": "create_moc"}]}
        ) is False

    def test_empty_items_not_garden(self):
        assert diff._is_garden_parsed({"confirmed_items": []}) is False


class TestGardenReconcile:
    def test_real_builder_output_reconciles_exit_0(self):
        parsed = _parsed_garden()
        actions = build_garden_audit_actions(parsed["confirmed_items"])
        code, out = _run(parsed, _instrs(actions))
        assert code == 0, out
        assert "RESULT: OK" in out
        assert "acked_advisories=1" in out  # advisories visible, not counted

    def test_acked_advisories_expect_no_actions(self):
        parsed = _parsed_garden()
        parsed["confirmed_items"] = []
        parsed["acked_advisories"] = [
            {"id": "F05", "path": "Maps/Old MOC.md", "check": "stale_moc"},
        ]
        # No confirmed items → not garden-shaped (falls to suggestions math with
        # all-zero expectations) → still exit 0 against an empty action list.
        code, out = _run(parsed, _instrs([]))
        assert code == 0, out


class TestGardenFalsify:
    def test_missing_action_fails(self):
        parsed = _parsed_garden()
        actions = build_garden_audit_actions(parsed["confirmed_items"])
        dropped = [a for a in actions if a["action"] != "remove_up_link"]
        code, out = _run(parsed, _instrs(dropped))
        assert code == 1
        assert "remove_up_link" in out and "[DIFF]" in out

    def test_wrong_link_value_fails_per_item_coverage(self):
        parsed = _parsed_garden()
        actions = build_garden_audit_actions(parsed["confirmed_items"])
        for a in actions:
            if a["action"] == "remove_up_link":
                a["link"] = "Wrong MOC"
        code, out = _run(parsed, _instrs(actions))
        assert code == 1
        assert "[MISSING]" in out

    def test_extra_unexpected_action_fails(self):
        parsed = _parsed_garden()
        actions = build_garden_audit_actions(parsed["confirmed_items"])
        actions.append({"id": "I99", "action": "skip", "reason": "stray",
                        "applied": False})
        code, out = _run(parsed, _instrs(actions))
        assert code == 1
