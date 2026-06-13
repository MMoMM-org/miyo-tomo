#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_daily_existence.py — I38 Pass-1 surfacing.

The Pass-1 suggestions doc must warn when a daily-log entry targets a daily
note that does not exist — Hashi modifies daily notes, it cannot create them.
PR #58 added the Pass-2 backstop (instruction-render.filter_missing_daily_notes);
this test covers the symmetric Pass-1 surfacing in suggestions-reducer:

  1. render_daily_notes_updates_block: exists=False → ⚠️ heading; exists=True → plain.
  2. annotate_daily_note_existence: KadoNotFoundError → exists=False;
     transient error → exists=True (fail-open); client=None → unchanged.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

_reducer_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py"
)
_reducer_mod = importlib.util.module_from_spec(_reducer_spec)
assert _reducer_spec.loader is not None
sys.modules["suggestions_reducer"] = _reducer_mod
_reducer_spec.loader.exec_module(_reducer_mod)

render_daily_notes_updates_block = _reducer_mod.render_daily_notes_updates_block
annotate_daily_note_existence = _reducer_mod.annotate_daily_note_existence
KadoNotFoundError = _reducer_mod.KadoNotFoundError


def _entry(stem: str, exists: bool) -> dict:
    return {
        "daily_note_stem": stem,
        "exists": exists,
        "trackers": [],
        "log_entries": [
            {
                "time": "09:00",
                "position": "after_last_line",
                "content": "Morgen-Routine durchgezogen",
                "reason": "fleeting log",
                "source_stem": "voice-memo",
                "source_section": "S01",
            }
        ],
        "log_links": [],
    }


# ── 1. Render heading ────────────────────────────────────────────────────────

def test_missing_daily_note_warns_in_heading() -> None:
    md = render_daily_notes_updates_block([_entry("2026-04-29", exists=False)])
    assert (
        "### [[2026-04-29]] ⚠️ daily note doesn't exist — "
        "create it first or the entry is skipped"
    ) in md
    # User-facing doc must not leak the Hashi implementation detail.
    assert "Hashi" not in md


def test_existing_daily_note_renders_plain_heading() -> None:
    md = render_daily_notes_updates_block([_entry("2026-04-29", exists=True)])
    assert "### [[2026-04-29]]\n" in md
    assert "⚠️" not in md


# ── 2. Existence check (fail-open) ────────────────────────────────────────────

class _FakeKado:
    """Minimal KadoClient stand-in: read_note raises the configured error."""

    def __init__(self, exc: Exception | None) -> None:
        self._exc = exc
        self.reads: list[str] = []

    def read_note(self, path: str) -> dict:
        self.reads.append(path)
        if self._exc is not None:
            raise self._exc
        return {"path": path}


def _groups() -> tuple[dict, dict]:
    groups = {"2026-04-29": _entry("2026-04-29", exists=True)}
    paths = {"2026-04-29": "Calendar/2026-04-29.md"}
    return groups, paths


def test_not_found_flags_missing() -> None:
    groups, paths = _groups()
    client = _FakeKado(KadoNotFoundError("no such note"))
    missing = annotate_daily_note_existence(groups, paths, client)
    assert missing == 1
    assert groups["2026-04-29"]["exists"] is False
    assert client.reads == ["Calendar/2026-04-29.md"]


def test_existing_note_stays_true() -> None:
    groups, paths = _groups()
    missing = annotate_daily_note_existence(groups, paths, _FakeKado(None))
    assert missing == 0
    assert groups["2026-04-29"]["exists"] is True


def test_transient_error_is_fail_open() -> None:
    groups, paths = _groups()
    missing = annotate_daily_note_existence(
        groups, paths, _FakeKado(RuntimeError("connection reset"))
    )
    assert missing == 0
    assert groups["2026-04-29"]["exists"] is True


def test_none_client_leaves_groups_unchanged() -> None:
    groups, paths = _groups()
    missing = annotate_daily_note_existence(groups, paths, None)
    assert missing == 0
    assert groups["2026-04-29"]["exists"] is True


def test_dedup_one_read_per_path() -> None:
    groups = {
        "2026-04-29": _entry("2026-04-29", exists=True),
        "dup": _entry("2026-04-29-alias", exists=True),
    }
    paths = {"2026-04-29": "Calendar/2026-04-29.md", "dup": "Calendar/2026-04-29.md"}
    client = _FakeKado(KadoNotFoundError("missing"))
    missing = annotate_daily_note_existence(groups, paths, client)
    assert missing == 2  # both groups flagged
    assert client.reads == ["Calendar/2026-04-29.md"]  # but only one Kado read
