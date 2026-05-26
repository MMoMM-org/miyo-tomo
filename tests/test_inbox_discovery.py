#!/usr/bin/env python3
# version: 0.2.0
"""test_inbox_discovery.py — Behavioural tests for inbox-discovery.py.

Covers T3.1 (F-47 Phase 3): unified byFrontmatter discovery, client-side
bucketing by doc_type/state, drift detection, and newSources set-diff.

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
AC:   AC-2.1 (four byFrontmatter calls: 3 pending-<value> + 1 captured + 1 listDir)
      AC-2.3 (empty inbox: all four calls still execute)
      AC-5a.1 (drift: captured > 0 AND pending* == 0)

Note on wildcard: Kado frontmatterValueMatches (search-adapter.ts:381) performs
strict equality only.  "tomo.state=pending-*" returns ZERO hits in production.
Three separate pending-<value> calls are the correct implementation.
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
    """Fixture with 5 tomo-managed + 1 untagged source; buckets must be correct.

    search_by_frontmatter is called 4 times: once per pending-<value> (3 states)
    then once for captured.  Each call returns hits for the matching state only.
    """
    mod = _load_script()

    sugg_path = INBOX_PATH + "2026-05-01_suggestions.md"
    moc_path = INBOX_PATH + "2026-05-01_moc-proposal-x.md"
    instr_path = INBOX_PATH + "2026-05-01_instructions.md"
    cap_path1 = INBOX_PATH + "note-captured-a.md"
    cap_path2 = INBOX_PATH + "note-captured-b.md"
    new_path = INBOX_PATH + "note-new.md"

    # Call order: pending-approval, pending-accept, pending-apply, captured
    pending_approval_hits = [_make_hit(sugg_path, "suggestions", "pending-approval")]
    pending_accept_hits = [_make_hit(moc_path, "moc-proposal", "pending-accept")]
    pending_apply_hits = [_make_hit(instr_path, "instructions", "pending-apply")]
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
    mock_client.search_by_frontmatter.side_effect = [
        pending_approval_hits,
        pending_accept_hits,
        pending_apply_hits,
        captured_hits,
    ]
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
    """Empty inbox: all buckets empty, drift=False.

    All four byFrontmatter calls still execute (AC-2.3).
    """
    mod = _load_script()

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], [], [], []]
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
    mock_client.search_by_frontmatter.side_effect = [[], [], [], captured_hits]
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

    # pending-approval call returns 1 hit; pending-accept + pending-apply empty
    pending_approval_hits = [_make_hit(pend_path, "suggestions", "pending-approval")]
    captured_hits = [_make_hit(cap_path, "source", "captured")]
    listdir_items = [
        _make_listdir_item(cap_path),
        _make_listdir_item(pend_path),
    ]

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [
        pending_approval_hits,
        [],
        [],
        captured_hits,
    ]
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
    mock_client.search_by_frontmatter.side_effect = [[], [], [], []]
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
    """All four search_by_frontmatter calls receive path_prefix=inbox_path."""
    mod = _load_script()

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], [], [], []]
    mock_client.list_dir.return_value = []

    mod.discover(mock_client, INBOX_PATH)

    calls = mock_client.search_by_frontmatter.call_args_list
    assert len(calls) == 4
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

    # mystery_hit has state=pending-approval so it comes back on call 1
    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[mystery_hit], [], [], []]
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
# Test: exactly four search_by_frontmatter calls
# ---------------------------------------------------------------------------

def test_four_byfrontmatter_calls_made():
    """discover() must call search_by_frontmatter exactly four times.

    Call order and query strings:
      1. tomo.state=pending-approval
      2. tomo.state=pending-accept
      3. tomo.state=pending-apply
      4. tomo.state=captured

    Kado strict-equality constraint: the original "ONE call for pending-*"
    (AC-2.1 wildcard assumption) is not achievable; three calls are required.
    """
    mod = _load_script()

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], [], [], []]
    mock_client.list_dir.return_value = []

    mod.discover(mock_client, INBOX_PATH)

    assert mock_client.search_by_frontmatter.call_count == 4

    calls = mock_client.search_by_frontmatter.call_args_list
    _query = lambda c: c[0][0] if c[0] else c[1].get("query", "")  # noqa: E731
    queries = [_query(c) for c in calls]

    assert queries[0] == "tomo.state=pending-approval", f"Call 1: {queries[0]!r}"
    assert queries[1] == "tomo.state=pending-accept",   f"Call 2: {queries[1]!r}"
    assert queries[2] == "tomo.state=pending-apply",    f"Call 3: {queries[2]!r}"
    assert queries[3] == "tomo.state=captured",         f"Call 4: {queries[3]!r}"


# ---------------------------------------------------------------------------
# Test (new): suggestions-fan routes to pendingApproval bucket
# ---------------------------------------------------------------------------

def test_suggestions_fan_routes_to_pending_approval():
    """A suggestions-fan doc with state=pending-approval lands in pendingApproval.

    doc_type=suggestions-fan shares the pendingApproval bucket with
    doc_type=suggestions (per _DOC_TYPE_TO_BUCKET mapping).
    """
    mod = _load_script()

    fan_path = INBOX_PATH + "inbox_x.md"
    fan_hit = {
        "path": fan_path,
        "frontmatter": {
            "tomo": {
                "doc_type": "suggestions-fan",
                "state": "pending-approval",
                "run_id": "r",
                "updated_at": "2026-05-21T00:00:00Z",
            }
        },
    }

    mock_client = MagicMock()
    # Call order: pending-approval returns the fan hit; others empty
    mock_client.search_by_frontmatter.side_effect = [[fan_hit], [], [], []]
    mock_client.list_dir.return_value = [_make_listdir_item(fan_path)]

    result = mod.discover(mock_client, INBOX_PATH)

    assert len(result["buckets"]["pendingApproval"]) == 1
    assert result["buckets"]["pendingApproval"][0]["path"] == fan_path
    assert result["buckets"]["pendingAccept"] == []
    assert result["buckets"]["pendingApply"] == []
    assert result["buckets"]["captured"] == []
    assert result["buckets"]["newSources"] == []


# ---------------------------------------------------------------------------
# Test (new): path_prefix normalization
# ---------------------------------------------------------------------------

def test_inbox_path_without_trailing_slash_is_normalized():
    """inbox_path without trailing slash must be normalized by discover().

    Calls discover(mock_client, "100 Inbox") with NO trailing slash.
    All four search_by_frontmatter calls + the list_dir call must carry
    path_prefix="100 Inbox/" (with trailing slash added by normalization
    at inbox-discovery.py:73 — inbox_path.rstrip("/") + "/").
    """
    mod = _load_script()

    inbox_path_no_slash = "100 Inbox"
    expected_path_prefix = "100 Inbox/"

    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], [], [], []]
    mock_client.list_dir.return_value = []

    mod.discover(mock_client, inbox_path_no_slash)

    # Verify all four search_by_frontmatter calls carry the normalized path_prefix
    calls = mock_client.search_by_frontmatter.call_args_list
    assert len(calls) == 4, f"Expected 4 calls, got {len(calls)}"
    for i, c in enumerate(calls):
        _, kwargs = c
        actual_prefix = kwargs.get("path_prefix")
        assert (
            actual_prefix == expected_path_prefix
        ), f"Call {i+1}: expected path_prefix={expected_path_prefix!r}, got {actual_prefix!r}"

    # Verify list_dir also carries the normalized path_prefix (as first positional arg)
    list_dir_call = mock_client.list_dir.call_args
    args, _ = list_dir_call
    actual_list_dir_prefix = args[0] if args else None
    assert (
        actual_list_dir_prefix == expected_path_prefix
    ), f"list_dir: expected path_prefix={expected_path_prefix!r}, got {actual_list_dir_prefix!r}"


def test_metrics_block_present_with_all_prd_properties():
    """Verify the PRD §7 metrics block is emitted with all required properties
    (token_estimate, byFrontmatter_hits, listDir_hits, phase_a_duration_ms, run_id).

    Spec: PRD §7 Tracking Requirements — lifecycle.discovery event property list.
    """
    mod = _load_script()
    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [
        [{"path": "100 Inbox/x.md", "modified": 1, "frontmatter": {"tomo": {"doc_type": "suggestions", "state": "pending-approval"}}}],
        [],
        [],
        [],
    ]
    mock_client.list_dir.return_value = []

    result = mod.discover(mock_client, "100 Inbox/", run_id="test-run-123")

    assert "metrics" in result, "metrics block missing from discover() return"
    m = result["metrics"]

    # Required PRD §7 properties
    assert m["run_id"] == "test-run-123", "run_id not echoed correctly"
    assert m["byFrontmatter_hits"] == 1, f"expected 1 hit, got {m['byFrontmatter_hits']}"
    assert m["listDir_hits"] == 0
    assert isinstance(m["phase_a_duration_ms"], int) and m["phase_a_duration_ms"] >= 0
    assert isinstance(m["token_estimate"], int) and m["token_estimate"] >= 0


def test_run_id_auto_generated_when_omitted():
    """If --run-id is not provided, discover() generates a UTC ISO timestamp."""
    mod = _load_script()
    mock_client = MagicMock()
    mock_client.search_by_frontmatter.side_effect = [[], [], [], []]
    mock_client.list_dir.return_value = []

    result = mod.discover(mock_client, "100 Inbox/")
    run_id = result["metrics"]["run_id"]

    # ISO 8601 UTC format: 2026-05-21T15:30:00.123456+00:00
    assert "T" in run_id and "+00:00" in run_id, f"unexpected run_id format: {run_id!r}"
