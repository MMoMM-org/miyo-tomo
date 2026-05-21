#!/usr/bin/env python3
# version: 0.1.0
"""test_inbox_discovery.py — Behavioural tests for inbox-discovery.py.

Covers T3.1 (F-47 Phase 3): unified byFrontmatter discovery, client-side
bucketing by doc_type/state, drift detection, and newSources set-diff.

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
AC:   AC-2.1 (one byFrontmatter call per bucket + one listDir)
      AC-2.3 (empty inbox: both calls still execute)
      AC-5a.1 (drift: captured > 0 AND pending* == 0)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "inbox-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

def _inject_doc_frontmatter_fake() -> None:
    """Inject a minimal doc_frontmatter fake so inbox-discovery.py loads
    without jsonschema on the host.
    """
    if "lib.doc_frontmatter" in sys.modules:
        return
    fake = types.ModuleType("lib.doc_frontmatter")
    fake.build_tomo_block = MagicMock(return_value={})
    sys.modules["lib.doc_frontmatter"] = fake


def _load_script() -> types.ModuleType:
    """Load inbox-discovery.py as a module without executing __main__."""
    _inject_doc_frontmatter_fake()
    spec = importlib.util.spec_from_file_location("inbox_discovery", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

INBOX_PATH = "100 Inbox/"


def _make_hit(path: str, doc_type: str, state: str) -> dict:
    """Build a byFrontmatter result item."""
    return {
        "path": path,
        "modified": 1716300000000,
        "frontmatter": {
            "tomo": {
                "doc_type": doc_type,
                "state": state,
                "run_id": "test-run",
                "updated_at": "2026-05-21T12:00:00Z",
            }
        },
    }


def _make_listdir_item(path: str) -> dict:
    """Build a listDir result item."""
    return {"path": path, "type": "file", "modified": 1716300000000, "size": 100}


# ---------------------------------------------------------------------------
# Test: mixed pending inbox — correct bucketing
# ---------------------------------------------------------------------------

def test_bucketing_with_mixed_pending():
    """Fixture with 5 tomo-managed + 1 untagged source; buckets must be correct."""
    mod = _load_script()

    sugg_path = INBOX_PATH + "2026-05-01_suggestions.md"
    moc_path = INBOX_PATH + "2026-05-01_moc-proposal-x.md"
    instr_path = INBOX_PATH + "2026-05-01_instructions.md"
    cap_path1 = INBOX_PATH + "note-captured-a.md"
    cap_path2 = INBOX_PATH + "note-captured-b.md"
    new_path = INBOX_PATH + "note-new.md"

    pending_hits = [
        _make_hit(sugg_path, "suggestions", "pending-approval"),
        _make_hit(moc_path, "moc-proposal", "pending-accept"),
        _make_hit(instr_path, "instructions", "pending-apply"),
    ]
    captured_hits = [
        _make_hit(cap_path1, "source", "captured"),
        _make_hit(cap_path2, "source", "captured"),
    ]
    listdir_items = [
        _make_listdir_item(sugg_path),
        _make_listdir_item(moc_path),
        _make_listdir_item(instr_path),
        _make_listdir_item(cap_path1),
        _make_listdir_item(cap_path2),
        _make_listdir_item(new_path),
    ]

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [pending_hits, captured_hits]
    mock_client.list_dir.return_value = listdir_items

    result = mod.discover(mock_client, INBOX_PATH)

    assert len(result["buckets"]["pendingApproval"]) == 1
    assert result["buckets"]["pendingApproval"][0]["path"] == sugg_path
    assert len(result["buckets"]["pendingAccept"]) == 1
    assert result["buckets"]["pendingAccept"][0]["path"] == moc_path
    assert len(result["buckets"]["pendingApply"]) == 1
    assert result["buckets"]["pendingApply"][0]["path"] == instr_path
    assert len(result["buckets"]["captured"]) == 2
    assert len(result["buckets"]["newSources"]) == 1
    assert result["buckets"]["newSources"][0]["path"] == new_path


# ---------------------------------------------------------------------------
# Test: empty inbox — no drift
# ---------------------------------------------------------------------------

def test_empty_inbox_returns_empty_buckets_no_drift():
    """Empty inbox: all buckets empty, drift=False."""
    mod = _load_script()

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], []]
    mock_client.list_dir.return_value = []

    result = mod.discover(mock_client, INBOX_PATH)

    assert result["buckets"]["pendingApproval"] == []
    assert result["buckets"]["pendingAccept"] == []
    assert result["buckets"]["pendingApply"] == []
    assert result["buckets"]["captured"] == []
    assert result["buckets"]["newSources"] == []
    assert result["drift"] is False


# ---------------------------------------------------------------------------
# Test: drift — captured present, no pending
# ---------------------------------------------------------------------------

def test_drift_triggers_when_captured_and_no_pending():
    """3 captured notes, 0 pending workflow docs → drift=True."""
    mod = _load_script()

    cap_paths = [
        INBOX_PATH + f"note-captured-{i}.md" for i in range(3)
    ]
    captured_hits = [_make_hit(p, "source", "captured") for p in cap_paths]
    listdir_items = [_make_listdir_item(p) for p in cap_paths]

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], captured_hits]
    mock_client.list_dir.return_value = listdir_items

    result = mod.discover(mock_client, INBOX_PATH)

    assert result["drift"] is True


# ---------------------------------------------------------------------------
# Test: no drift when any pending present
# ---------------------------------------------------------------------------

def test_no_drift_when_any_pending_present():
    """1 captured + 1 pending-approval → drift=False (pending exists)."""
    mod = _load_script()

    cap_path = INBOX_PATH + "note-captured.md"
    pend_path = INBOX_PATH + "2026-05-01_suggestions.md"

    pending_hits = [_make_hit(pend_path, "suggestions", "pending-approval")]
    captured_hits = [_make_hit(cap_path, "source", "captured")]
    listdir_items = [
        _make_listdir_item(cap_path),
        _make_listdir_item(pend_path),
    ]

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [pending_hits, captured_hits]
    mock_client.list_dir.return_value = listdir_items

    result = mod.discover(mock_client, INBOX_PATH)

    assert result["drift"] is False


# ---------------------------------------------------------------------------
# Test: non-.md files excluded from newSources
# ---------------------------------------------------------------------------

def test_non_md_files_excluded_from_new_sources():
    """listDir returns .mp3, .json, and .md; only untagged .md lands in newSources."""
    mod = _load_script()

    md_path = INBOX_PATH + "note-new.md"
    mp3_item = {"path": INBOX_PATH + "recording.mp3", "type": "file", "modified": 0, "size": 0}
    json_item = {"path": INBOX_PATH + "data.json", "type": "file", "modified": 0, "size": 0}
    md_item = _make_listdir_item(md_path)

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], []]
    mock_client.list_dir.return_value = [mp3_item, json_item, md_item]

    result = mod.discover(mock_client, INBOX_PATH)

    paths = [item["path"] for item in result["buckets"]["newSources"]]
    assert md_path in paths
    assert INBOX_PATH + "recording.mp3" not in paths
    assert INBOX_PATH + "data.json" not in paths


# ---------------------------------------------------------------------------
# Test: path_prefix passed to both search_by_frontmatter calls
# ---------------------------------------------------------------------------

def test_filter_path_passed_to_kado_client():
    """Both search_by_frontmatter calls receive path_prefix=inbox_path."""
    mod = _load_script()

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], []]
    mock_client.list_dir.return_value = []

    mod.discover(mock_client, INBOX_PATH)

    calls = mock_client.search_by_frontmatter.call_args_list
    assert len(calls) == 2
    for c in calls:
        _, kwargs = c
        assert kwargs.get("path_prefix") == INBOX_PATH


# ---------------------------------------------------------------------------
# Test: unknown doc_type logged to stderr and skipped
# ---------------------------------------------------------------------------

def test_unknown_doc_type_in_hit_logged_and_skipped(capsys):
    """Hit with tomo.doc_type=mystery must not land in any bucket; stderr warns."""
    mod = _load_script()

    mystery_path = INBOX_PATH + "2026-05-01_mystery.md"
    mystery_hit = _make_hit(mystery_path, "mystery", "pending-approval")

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[mystery_hit], []]
    mock_client.list_dir.return_value = [_make_listdir_item(mystery_path)]

    result = mod.discover(mock_client, INBOX_PATH)

    # Must not appear in any named bucket
    for bucket in ("pendingApproval", "pendingAccept", "pendingApply", "captured"):
        assert all(
            item["path"] != mystery_path for item in result["buckets"][bucket]
        ), f"mystery doc found in bucket {bucket}"

    captured_err = capsys.readouterr().err
    assert "mystery" in captured_err, "stderr must mention the unknown doc_type"


# ---------------------------------------------------------------------------
# Test: exactly two search_by_frontmatter calls
# ---------------------------------------------------------------------------

def test_two_byfrontmatter_calls_made():
    """discover() must call search_by_frontmatter exactly twice."""
    mod = _load_script()

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], []]
    mock_client.list_dir.return_value = []

    mod.discover(mock_client, INBOX_PATH)

    assert mock_client.search_by_frontmatter.call_count == 2

    # Verify query content: first call targets pending-*, second targets captured
    calls = mock_client.search_by_frontmatter.call_args_list
    first_query = calls[0][0][0] if calls[0][0] else calls[0][1].get("query", "")
    second_query = calls[1][0][0] if calls[1][0] else calls[1][1].get("query", "")

    assert "pending" in first_query, f"First call should query pending-*, got: {first_query!r}"
    assert "captured" in second_query, f"Second call should query captured, got: {second_query!r}"
