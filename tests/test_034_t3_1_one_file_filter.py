#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t3_1_one_file_filter.py — spec 034 Phase 3 T3.1.

Before this task, `inbox-triage.py`'s `discover_files` and
`lib/attachment_index.py`'s `build_inbox_index` each carried their own
listDir file-type filter, and the two disagreed: `discover_files` lowercased
the type and tolerated `None`/missing keys, `build_inbox_index` did an exact
`== "file"` match. They agreed for everything Kado actually sends (the
gateway only ever emits the lowercase literal), so a test built from
realistic Kado data would be green before this task started and prove
nothing — the divergence only shows up on inputs Kado never sends: case
variants, `None`, a missing key, and a non-dict entry.

Two layers, per the approved test plan:

  Layer 1 — absolute correctness of the new shared predicate
  (`lib.attachment_index.is_file_entry`) against a fixed-expectation table.
  This alone must fail an always-False impl, an always-True impl, and a
  case-sensitive impl.

  Layer 2 — the agreement invariant: `discover_files` and
  `build_inbox_index` must classify every table entry identically. This
  drives the two real call sites (not just the shared predicate a second
  time), so a future edit that re-forks one side is caught.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.attachment_index import build_inbox_index, is_file_entry  # noqa: E402


def _load_inbox_triage():
    """Load inbox-triage.py as a module (hyphenated filename — house pattern)."""
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage_t3_1", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t3_1"] = mod
    spec.loader.exec_module(mod)
    return mod


inbox_triage = _load_inbox_triage()


class _FakeClient:
    """Minimal KadoClient stand-in: list_dir returns whatever it's given."""

    def __init__(self, items):
        self._items = items

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        return self._items


# The inputs where the two pre-T3.1 predicates genuinely diverged (or where
# either could plausibly crash): case variants, None, a missing key, and a
# non-dict entry. `{"type": "file"}` / `{"type": "folder"}` anchor the table
# to Kado's real lowercase literals so a broken predicate can't pass by
# accident.
FILE_TYPE_TABLE: list[tuple[object, bool]] = [
    ({"type": "file"}, True),      # Kado's real lowercase literal
    ({"type": "folder"}, False),   # folder entries excluded
    ({"type": "File"}, True),      # AC Feature 10: case-insensitive
    ({"type": "FILE"}, True),      # AC Feature 10: case-insensitive
    ({"type": None}, False),
    ({}, False),                   # missing `type` key
    ("not a dict", False),
    (None, False),
]


# ---------------------------------------------------------------------------
# Layer 1 — absolute correctness, fixed expectations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entry,expected", FILE_TYPE_TABLE)
def test_is_file_entry_correctness(entry, expected):
    assert is_file_entry(entry) is expected


# ---------------------------------------------------------------------------
# Layer 2 — the agreement invariant
# ---------------------------------------------------------------------------

def _with_path(entry):
    """Attach a real path to a dict entry so it can flow through both real
    call sites (discover_files buckets by suffix; build_inbox_index indexes
    by basename — both need a `path` to do anything at all). Non-dict
    entries are left untouched; both consumers must reject them before ever
    touching `.get`.
    """
    if isinstance(entry, dict):
        return {**entry, "path": "100 Inbox/sample.md"}
    return entry


def _discover_files_admits(entry) -> bool:
    """True if inbox-triage's discover_files treats `entry` as a file."""
    live_entry = _with_path(entry)
    client = _FakeClient([live_entry])
    _all_files, audio_files, md_files = inbox_triage.discover_files(client, "100 Inbox/")
    return any(f is live_entry for f in md_files) or any(f is live_entry for f in audio_files)


def _build_inbox_index_admits(entry) -> bool:
    """True if build_inbox_index keeps `entry` in the resulting index."""
    index = build_inbox_index([_with_path(entry)])
    return "sample.md" in index


@pytest.mark.parametrize("entry,_expected", FILE_TYPE_TABLE)
def test_discover_files_and_build_inbox_index_agree(entry, _expected):
    assert _discover_files_admits(entry) == _build_inbox_index_admits(entry)
