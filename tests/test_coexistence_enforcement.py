#!/usr/bin/env python3
# version: 0.2.0
"""test_coexistence_enforcement.py — Tests for _enforce_coexistence in suggestions-reducer.

Verifies the deterministic coexistence rules from inbox-analyst Step 9:
- create_atomic_note + log_entry with worthiness >= 0.5 → convert log_entry to log_link
- worthiness < 0.5 (and not force_atomic) → flag create_atomic_note `suppressed`
  (kept in the list for a light render, NOT promoted) — #88, regardless of daily
- force_atomic → never suppressed (the opt-in escape hatch)
- No violation (worthy atomic) → pass through unchanged
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

enforce = _mod._enforce_coexistence


def _atomic(worthiness: float = 0.7, stem: str = "test-note", force_atomic: bool = False) -> dict:
    a = {
        "kind": "create_atomic_note",
        "atomic_note_worthiness": worthiness,
        "suggested_title": stem,
        "stem": stem,
    }
    if force_atomic:
        a["force_atomic"] = True
    return a


def _daily_with_log_entry() -> dict:
    return {
        "kind": "update_daily",
        "date": "2026-05-26",
        "updates": [
            {
                "kind": "log_entry",
                "content": "Some log content",
                "position": "after_last_line",
                "time": None,
                "time_source": None,
                "reason": "Short note",
            }
        ],
    }


def _daily_with_log_link() -> dict:
    return {
        "kind": "update_daily",
        "date": "2026-05-26",
        "updates": [
            {
                "kind": "log_link",
                "target_stem": "test-note",
                "position": "after_last_line",
                "reason": "Substantive note",
            }
        ],
    }


def _daily_with_tracker() -> dict:
    return {
        "kind": "update_daily",
        "date": "2026-05-26",
        "updates": [
            {
                "kind": "tracker",
                "field": "Sport",
                "value": True,
                "reason": "Mentioned running",
            }
        ],
    }


class TestCoexistenceHighWorthiness:
    def test_log_entry_converted_to_log_link(self):
        """Worthiness >= 0.5: keep atomic, convert log_entry → log_link."""
        actions = [_atomic(0.7, "furano"), _daily_with_log_entry()]
        result = enforce(actions)

        kinds = [a["kind"] for a in result]
        assert "create_atomic_note" in kinds

        daily = next(a for a in result if a["kind"] == "update_daily")
        update_kinds = [u["kind"] for u in daily["updates"]]
        assert "log_link" in update_kinds
        assert "log_entry" not in update_kinds

    def test_converted_log_link_has_target_stem(self):
        """Converted log_link gets target_stem from atomic action."""
        actions = [_atomic(0.8, "my-note"), _daily_with_log_entry()]
        result = enforce(actions)

        daily = next(a for a in result if a["kind"] == "update_daily")
        link = next(u for u in daily["updates"] if u["kind"] == "log_link")
        assert link["target_stem"] == "my-note"

    def test_trackers_preserved_alongside_conversion(self):
        """Tracker updates survive the log_entry → log_link conversion."""
        daily = _daily_with_log_entry()
        daily["updates"].append({
            "kind": "tracker",
            "field": "Sport",
            "value": True,
            "reason": "Running",
        })
        actions = [_atomic(0.6), daily]
        result = enforce(actions)

        daily_result = next(a for a in result if a["kind"] == "update_daily")
        tracker_count = sum(1 for u in daily_result["updates"] if u["kind"] == "tracker")
        assert tracker_count == 1


class TestCoexistenceLowWorthiness:
    def test_atomic_suppressed_log_entry_kept(self):
        """Worthiness < 0.5 + log_entry: atomic flagged suppressed (kept), log_entry kept.

        Contract change (#88): the sub-worthy atomic is no longer DROPPED — it is
        flagged `suppressed` so the item still renders a light kept-in-inbox block.
        """
        actions = [_atomic(0.3), _daily_with_log_entry()]
        result = enforce(actions)

        atomic = next(a for a in result if a["kind"] == "create_atomic_note")
        assert atomic.get("suppressed") is True

        daily = next(a for a in result if a["kind"] == "update_daily")
        assert "log_entry" in [u["kind"] for u in daily["updates"]]

    def test_sub_worthy_with_log_link_suppressed(self):
        """#88 regression: sub-0.5 + log_link → atomic suppressed (was surviving)."""
        actions = [_atomic(0.4), _daily_with_log_link()]
        result = enforce(actions)

        atomic = next(a for a in result if a["kind"] == "create_atomic_note")
        assert atomic.get("suppressed") is True
        # log_link is untouched (no survivor → no conversion needed).
        daily = next(a for a in result if a["kind"] == "update_daily")
        assert "log_link" in [u["kind"] for u in daily["updates"]]

    def test_sub_worthy_no_daily_suppressed(self):
        """Sub-0.5 with no daily → atomic suppressed but KEPT (so the item surfaces)."""
        actions = [_atomic(0.4)]
        result = enforce(actions)
        assert len(result) == 1
        assert result[0].get("suppressed") is True

    def test_force_atomic_not_suppressed(self):
        """force_atomic overrides sub-0.5 — the escape hatch survives, unflagged."""
        actions = [_atomic(0.4, force_atomic=True), _daily_with_log_link()]
        result = enforce(actions)
        atomic = next(a for a in result if a["kind"] == "create_atomic_note")
        assert not atomic.get("suppressed")


class TestCoexistenceNoViolation:
    def test_atomic_with_log_link_passes_through(self):
        """No violation: atomic + log_link is allowed."""
        actions = [_atomic(0.8), _daily_with_log_link()]
        result = enforce(actions)

        kinds = [a["kind"] for a in result]
        assert "create_atomic_note" in kinds
        assert "update_daily" in kinds

    def test_atomic_only_passes_through(self):
        """No daily update at all — no violation."""
        actions = [_atomic(0.9)]
        result = enforce(actions)
        assert len(result) == 1
        assert result[0]["kind"] == "create_atomic_note"

    def test_daily_only_passes_through(self):
        """No atomic note — no violation."""
        actions = [_daily_with_log_entry()]
        result = enforce(actions)
        assert len(result) == 1
        assert result[0]["kind"] == "update_daily"

    def test_tracker_only_daily_passes_through(self):
        """Atomic + tracker-only daily is fine."""
        actions = [_atomic(0.7), _daily_with_tracker()]
        result = enforce(actions)

        kinds = [a["kind"] for a in result]
        assert "create_atomic_note" in kinds
        assert "update_daily" in kinds

    def test_empty_actions_passes_through(self):
        result = enforce([])
        assert result == []
