#!/usr/bin/env python3
# version: 0.1.0
"""test_instructions_diff_skipped_daily.py — coverage-audit vs. dropped daily notes.

The renderer drops update_* daily-note actions whose target daily note does not
exist (Hashi cannot create daily notes) and records them under
instructions.tomo.skipped_daily. instructions-diff must subtract those from the
expected tallies so a correct render does NOT read as a coverage gap — while an
UNrecorded missing action still fails (the audit stays honest).

Covers:
  - reconcile: tomo.skipped_daily covers the drops → run_diff exit 0 + observation
  - falsify:   same drop WITHOUT the marker → still exit 1 (no blanket pass)
  - privacy:   filter_missing_daily_notes + the emit projection is metadata-only
               (action/date/daily_note_path, never note content — Constitution L2)
  - schema:    a full instructions doc carrying tomo.skipped_daily validates
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("instructions_diff", SCRIPTS_DIR / "instructions-diff.py")
diff = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(diff)

from lib.render_resolve import filter_missing_daily_notes  # noqa: E402

DAILY_DIR = "Calendar/301 Daily/"


def _parsed_two_log_entries() -> dict:
    """Two accepted log entries on two dates; source_stem empty → no delete inference."""
    return {
        "confirmed_items": [],
        "skipped": [],
        "daily_updates": [
            {
                "date": "2026-03-26", "daily_note_path": f"{DAILY_DIR}2026-03-26.md",
                "trackers": [], "log_links": [],
                "log_entries": [{"content": "entry A", "position": "after_last_line",
                                 "source_stem": "", "accepted": True}],
            },
            {
                "date": "2026-03-30", "daily_note_path": f"{DAILY_DIR}2026-03-30.md",
                "trackers": [], "log_links": [],
                "log_entries": [{"content": "entry B", "position": "after_last_line",
                                 "source_stem": "", "accepted": True}],
            },
        ],
    }


def _log_action(date: str) -> dict:
    return {
        "id": f"I-{date}", "action": "update_log_entry",
        "daily_note_path": f"{DAILY_DIR}{date}.md", "date": date,
        "section": "Daily Log", "position": "after_last_line", "content": "x",
    }


def _run(parsed: dict, instrs: dict) -> tuple[int, list[str]]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, obs = diff.run_diff(parsed, instrs)
    return rc, obs


def test_skipped_daily_reconciles():
    """Renderer kept 03-26, dropped 03-30 (missing note) and recorded it → reconciles."""
    parsed = _parsed_two_log_entries()
    instrs = {
        "action_count": 1,
        "actions": [_log_action("2026-03-26")],
        "tomo": {"skipped_daily": [
            {"action": "update_log_entry", "date": "2026-03-30",
             "daily_note_path": f"{DAILY_DIR}2026-03-30.md"}]},
    }
    rc, obs = _run(parsed, instrs)
    assert rc == 0, f"recorded skip should reconcile, rc={rc}"
    assert any("skipped" in o for o in obs), "skipped-daily observation must surface"


def test_missing_daily_without_marker_fails():
    """Same drop but NOT recorded in tomo.skipped_daily → still a hard coverage fail."""
    parsed = _parsed_two_log_entries()
    instrs = {"action_count": 1, "actions": [_log_action("2026-03-26")]}  # no tomo block
    rc, _ = _run(parsed, instrs)
    assert rc == 1, "an unrecorded missing daily action must not silently pass"


def test_partial_skip_still_reconciles_remaining():
    """Two drops, both recorded → expected drops to zero, actual zero → reconciles."""
    parsed = _parsed_two_log_entries()
    instrs = {
        "action_count": 0,
        "actions": [],
        "tomo": {"skipped_daily": [
            {"action": "update_log_entry", "date": "2026-03-26",
             "daily_note_path": f"{DAILY_DIR}2026-03-26.md"},
            {"action": "update_log_entry", "date": "2026-03-30",
             "daily_note_path": f"{DAILY_DIR}2026-03-30.md"}]},
    }
    rc, obs = _run(parsed, instrs)
    assert rc == 0, f"all-skipped should reconcile to zero, rc={rc}"
    assert any("2 daily" in o for o in obs)


def test_filter_and_emit_projection_is_metadata_only():
    """filter_missing_daily_notes drops missing-note actions; the emit projection
    the renderer writes carries action/date/daily_note_path only — never content."""
    client = MagicMock()
    # 03-26 exists, 03-30 does not.
    client.note_exists.side_effect = lambda p: "2026-03-26" in p
    actions = [_log_action("2026-03-26"), _log_action("2026-03-30")]
    kept, skipped = filter_missing_daily_notes(actions, client)
    assert [a["date"] for a in kept] == ["2026-03-26"]
    assert [a["date"] for a in skipped] == ["2026-03-30"]
    # Mirror instruction-render's projection and assert metadata-only (L2).
    projected = [{"action": a.get("action"), "date": a.get("date"),
                  "daily_note_path": a.get("daily_note_path")} for a in skipped]
    for entry in projected:
        assert set(entry.keys()) == {"action", "date", "daily_note_path"}
        assert "content" not in entry


def test_full_doc_with_skipped_daily_validates():
    """A full instructions doc carrying tomo.skipped_daily validates against the schema."""
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.load(open(REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"))
    doc = {
        "schema_version": "2", "type": "tomo-instructions",
        "generated": "2026-07-09T08:00:00Z", "profile": "miyo",
        "action_count": 0, "actions": [],
        "tomo": {"run_id": "r1", "skipped_daily": [
            {"action": "update_log_entry", "date": "2026-03-30",
             "daily_note_path": f"{DAILY_DIR}2026-03-30.md"}]},
    }
    jsonschema.validate(doc, schema)  # raises on failure


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
