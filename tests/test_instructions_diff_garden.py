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
             "garden_action": "resolve_dead_link", "path": "Notes/Src.md",
             "stem": "Src", "target": "Missing", "replace": ""},
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


class TestGardenEditFrontmatter:
    """spec 032 T4.3 — a frontmatter-declared broken-`up` fix routes to
    garden_action "edit_frontmatter" (_route_broken_up, garden-audit-parser.py).

    Before this task, _GARDEN_EXPECTED_KINDS had no "edit_frontmatter" key, so
    _garden_item_covered's `for kind in _GARDEN_EXPECTED_KINDS.get(ga, ())`
    iterated zero times and returned True having checked nothing — per-item
    coverage printed [OK] for an item it never verified. These tests must fail
    on that vacuous True, not merely confirm a correct item prints [OK].
    """

    def _item(self, **overrides) -> dict:
        item = {
            "id": "F06", "garden_check": "broken_up",
            "garden_action": "edit_frontmatter", "path": "Notes/FM.md",
            "stem": "FM", "up_value": "[[Dead MOC]]", "up_target": "Dead MOC",
            "choice": "remove", "new_target": None,
        }
        item.update(overrides)
        return item

    def test_missing_action_not_covered(self):
        # No edit_frontmatter action at all — the exact vacuous-True scenario.
        item = self._item()
        assert diff._garden_item_covered(item, []) is False

    def test_mismatched_path_not_covered(self):
        item = self._item()
        actions = build_garden_audit_actions([item])
        for a in actions:
            a["path"] = "Notes/Wrong.md"
        assert diff._garden_item_covered(item, actions) is False

    def test_correct_item_is_covered(self):
        item = self._item()
        actions = build_garden_audit_actions([item])
        assert diff._garden_item_covered(item, actions) is True

    def test_end_to_end_missing_action_hard_fails(self):
        # Also proves GARDEN_ACTION_ORDER must carry "edit_frontmatter": with
        # zero actual actions of this kind, all_kinds only extends with kinds
        # PRESENT in actual_counts — a kind absent from both GARDEN_ACTION_ORDER
        # and actual_counts never enters the printed table or the TOTAL sums,
        # so a wholly-missing action would silently reconcile as equal (0/0)
        # rather than hard-failing on the expected N vs actual 0 mismatch.
        parsed = {
            "run_id": "run-diff-garden-fm", "generated": "g", "profile": "miyo",
            "confirmed_items": [self._item()],
            "acked_advisories": [],
        }
        code, out = _run(parsed, _instrs([]))
        assert code == 1
        assert "edit_frontmatter" in out
        assert "[DIFF]" in out or "[MISSING]" in out
