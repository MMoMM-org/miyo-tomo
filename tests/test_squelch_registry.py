#!/usr/bin/env python3
# version: 0.1.1
"""test_squelch_registry.py — Tests for the squelch sidecar state helper.

Covers F-43 Phase 1 T1.3: load/save roundtrip with atomic-write semantics,
graceful handling of missing/corrupt state, decrement-and-prune, and
signature-collision replacement.

The on-disk shape is the schema documented in SDD/Data Storage Changes:

    {
      "schema_version": "1",
      "last_run_id": "<UUID>",
      "rejections": [
        {
          "topic_signature": "...",
          "topic_keywords": [...],
          "rejected_at_run_id": "...",
          "runs_remaining": 3,
          "first_seen_at": "2026-05-07T14:30:00Z"
        }
      ]
    }

The in-memory shape is a `dict[str, SquelchEntry]` keyed by
`topic_signature` for O(1) lookups.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.squelch` works

from lib import squelch  # noqa: E402


def _make_entry(
    signature: str = "abc123",
    keywords: list[str] | None = None,
    runs_remaining: int = 3,
    rejected_at_run_id: str = "run-aaa",
    first_seen_at: str = "2026-05-07T14:30:00Z",
) -> squelch.SquelchEntry:
    return squelch.SquelchEntry(
        topic_signature=signature,
        topic_keywords=keywords if keywords is not None else ["zsh", "shell"],
        rejected_at_run_id=rejected_at_run_id,
        runs_remaining=runs_remaining,
        first_seen_at=first_seen_at,
    )


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    """Absent file → empty registry, no exception raised."""
    state_file = tmp_path / "moc-squelch.json"
    assert not state_file.exists()

    registry = squelch.load_registry(state_file)

    assert registry == {}


def test_load_corrupt_returns_empty_with_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Corrupt JSON → empty registry + stderr warning, no crash."""
    state_file = tmp_path / "moc-squelch.json"
    state_file.write_text("{not: valid json", encoding="utf-8")

    registry = squelch.load_registry(state_file)

    assert registry == {}
    captured = capsys.readouterr()
    assert captured.err  # warning emitted to stderr
    assert "moc-squelch" in captured.err or "squelch" in captured.err.lower()


def test_atomic_write_roundtrip(tmp_path: Path) -> None:
    """save_registry_atomic followed by load_registry yields equal data."""
    state_file = tmp_path / "moc-squelch.json"
    entry_a = _make_entry(signature="sig-a", runs_remaining=3)
    entry_b = _make_entry(
        signature="sig-b",
        keywords=["python", "asyncio"],
        runs_remaining=1,
        rejected_at_run_id="run-bbb",
        first_seen_at="2026-05-07T15:00:00Z",
    )
    registry = {entry_a.topic_signature: entry_a, entry_b.topic_signature: entry_b}

    squelch.save_registry_atomic(state_file, registry, last_run_id="run-zzz")

    # File exists and is valid JSON with documented schema
    assert state_file.exists()
    raw = json.loads(state_file.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "1"
    assert raw["last_run_id"] == "run-zzz"
    assert isinstance(raw["rejections"], list)
    assert len(raw["rejections"]) == 2

    # Roundtrip yields equal dataclass instances
    loaded = squelch.load_registry(state_file)
    assert loaded == registry


def test_atomic_write_no_tmp_file_left_behind(tmp_path: Path) -> None:
    """The .tmp staging file is cleaned up after successful rename."""
    state_file = tmp_path / "moc-squelch.json"
    registry = {e.topic_signature: e for e in [_make_entry()]}

    squelch.save_registry_atomic(state_file, registry, last_run_id="run-1")

    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_decrement_and_remove_zero() -> None:
    """Entries that hit runs_remaining=0 after decrement are removed."""
    entry_will_remain = _make_entry(signature="keep", runs_remaining=3)
    entry_will_drop_after = _make_entry(signature="drop-soon", runs_remaining=1)
    registry = {
        entry_will_remain.topic_signature: entry_will_remain,
        entry_will_drop_after.topic_signature: entry_will_drop_after,
    }

    decremented = squelch.decrement_all(registry)

    assert "keep" in decremented
    assert decremented["keep"].runs_remaining == 2
    # runs_remaining=1 → 0 → removed
    assert "drop-soon" not in decremented

    # Original registry untreated (pure function expectation)
    assert registry["keep"].runs_remaining == 3
    assert registry["drop-soon"].runs_remaining == 1


def test_signature_collision_replaces() -> None:
    """add_or_replace with an existing signature replaces, no duplicates."""
    original = _make_entry(
        signature="sig-x",
        keywords=["old"],
        runs_remaining=3,
        rejected_at_run_id="run-old",
    )
    registry = {original.topic_signature: original}

    replacement = _make_entry(
        signature="sig-x",
        keywords=["new", "fresh"],
        runs_remaining=5,
        rejected_at_run_id="run-new",
        first_seen_at="2026-05-07T16:00:00Z",
    )
    updated = squelch.add_or_replace(registry, replacement)

    assert len(updated) == 1
    assert updated["sig-x"] == replacement
    assert updated["sig-x"].topic_keywords == ["new", "fresh"]
    assert updated["sig-x"].runs_remaining == 5


def test_is_active_true_when_signature_present_and_runs_remaining() -> None:
    entry = _make_entry(signature="sig-active", runs_remaining=2)
    registry = {entry.topic_signature: entry}

    assert squelch.is_active(registry, "sig-active") is True
    assert squelch.is_active(registry, "sig-missing") is False


def test_load_non_list_rejections_returns_empty_with_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`rejections` present but not a list (e.g. null) → empty + stderr warning.

    The sidecar file is structurally a JSON object with the right keys, but the
    `rejections` value is the wrong shape. The loader must not crash; it must
    log a warning and treat the registry as empty so the run continues.
    """
    state_file = tmp_path / "moc-squelch.json"
    state_file.write_text(
        json.dumps({"schema_version": "1", "rejections": None}),
        encoding="utf-8",
    )

    registry = squelch.load_registry(state_file)

    assert registry == {}
    captured = capsys.readouterr()
    assert captured.err  # warning emitted to stderr
    assert "non-list" in captured.err or "rejections" in captured.err


def test_load_partial_corrupt_rows_skips_bad_keeps_good(tmp_path: Path) -> None:
    """One valid row + one malformed row → registry contains only the valid one.

    The loader skips individual malformed rows (non-dict, missing
    `topic_signature`, empty signature) rather than failing the whole load.
    """
    state_file = tmp_path / "moc-squelch.json"
    valid_row = {
        "topic_signature": "sig-good",
        "topic_keywords": ["zsh", "shell"],
        "rejected_at_run_id": "run-aaa",
        "runs_remaining": 3,
        "first_seen_at": "2026-05-07T14:30:00Z",
    }
    malformed_row = "garbage"  # non-dict — must be skipped
    state_file.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "last_run_id": "run-zzz",
                "rejections": [valid_row, malformed_row],
            }
        ),
        encoding="utf-8",
    )

    registry = squelch.load_registry(state_file)

    assert len(registry) == 1
    assert "sig-good" in registry
    assert registry["sig-good"].topic_keywords == ["zsh", "shell"]
    assert registry["sig-good"].runs_remaining == 3
