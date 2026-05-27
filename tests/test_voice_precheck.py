#!/usr/bin/env python3
# version: 0.1.0
"""test_voice_precheck.py — Behavioural tests for voice-precheck.py.

Verifies that precheck():
- Returns all_cached=True when every audio file has a sibling .md transcript.
- Returns all_cached=False with missing list when some transcripts are absent.
- Returns all_cached=False and audio_count=0 when no audio files are in the inbox.
- Applies sanitize_stem for special characters in audio filenames.
- Returns all_cached=False and audio_count=0 when the inbox is empty.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "voice-precheck.py"

sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_module():
    spec = importlib.util.spec_from_file_location("voice_precheck", SCRIPT_PATH)
    assert spec and spec.loader, f"Cannot load module from {SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file_item(path: str) -> dict:
    return {"path": path, "type": "file"}


def _fake_client(items: list[dict]) -> MagicMock:
    """Return a MagicMock KadoClient whose list_dir returns the given items."""
    client = MagicMock()
    client.list_dir.return_value = items
    return client


# ---------------------------------------------------------------------------
# T1 — all audio files cached → all_cached=True
# ---------------------------------------------------------------------------


def test_all_cached_returns_true(monkeypatch):
    """When every audio file has a sibling .md transcript, all_cached is True."""
    mod = _load_module()

    items = [
        _make_file_item("100 Inbox/memo.m4a"),
        _make_file_item("100 Inbox/memo.md"),
        _make_file_item("100 Inbox/recording.mp3"),
        _make_file_item("100 Inbox/recording.md"),
    ]
    fake_client = _fake_client(items)
    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    result = mod.precheck("100 Inbox")

    assert result["all_cached"] is True
    assert result["audio_count"] == 2
    assert result["cached_count"] == 2
    assert result["missing_count"] == 0
    assert result["missing"] == []


# ---------------------------------------------------------------------------
# T2 — some files missing → all_cached=False, missing list populated
# ---------------------------------------------------------------------------


def test_some_missing_returns_false_with_missing_list(monkeypatch):
    """When some transcripts are absent, all_cached is False and missing lists them."""
    mod = _load_module()

    items = [
        _make_file_item("100 Inbox/memo.m4a"),
        _make_file_item("100 Inbox/memo.md"),
        _make_file_item("100 Inbox/lecture.mp3"),
        # lecture.md is absent
    ]
    fake_client = _fake_client(items)
    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    result = mod.precheck("100 Inbox")

    assert result["all_cached"] is False
    assert result["audio_count"] == 2
    assert result["cached_count"] == 1
    assert result["missing_count"] == 1
    assert "100 Inbox/lecture.mp3" in result["missing"]


# ---------------------------------------------------------------------------
# T3 — no audio files in inbox → all_cached=False, audio_count=0
# ---------------------------------------------------------------------------


def test_no_audio_files_returns_false_with_zero_count(monkeypatch):
    """When no audio files are present, all_cached is False and audio_count is 0."""
    mod = _load_module()

    items = [
        _make_file_item("100 Inbox/note.md"),
        _make_file_item("100 Inbox/another-note.md"),
    ]
    fake_client = _fake_client(items)
    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    result = mod.precheck("100 Inbox")

    assert result["all_cached"] is False
    assert result["audio_count"] == 0
    assert result["cached_count"] == 0
    assert result["missing_count"] == 0
    assert result["missing"] == []


# ---------------------------------------------------------------------------
# T4 — sanitize_stem integration: special characters in audio filename
# ---------------------------------------------------------------------------


def test_sanitize_stem_applied_to_audio_path(monkeypatch):
    """Audio filenames with Obsidian-forbidden chars resolve to the sanitised .md path."""
    mod = _load_module()

    # Colon in filename is forbidden by Obsidian — sanitize_stem replaces it with "-"
    items = [
        _make_file_item("100 Inbox/memo 11:48:29.m4a"),
        _make_file_item("100 Inbox/memo 11-48-29.md"),  # sanitised sibling
    ]
    fake_client = _fake_client(items)
    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    result = mod.precheck("100 Inbox")

    assert result["all_cached"] is True
    assert result["audio_count"] == 1
    assert result["cached_count"] == 1
    assert result["missing"] == []


# ---------------------------------------------------------------------------
# T5 — empty inbox (no files at all) → all_cached=False, audio_count=0
# ---------------------------------------------------------------------------


def test_empty_inbox_returns_false_with_zero_counts(monkeypatch):
    """An empty inbox results in all_cached=False and all counts at zero."""
    mod = _load_module()

    fake_client = _fake_client([])
    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    result = mod.precheck("100 Inbox")

    assert result["all_cached"] is False
    assert result["audio_count"] == 0
    assert result["cached_count"] == 0
    assert result["missing_count"] == 0
    assert result["missing"] == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
