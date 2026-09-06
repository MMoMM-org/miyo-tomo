#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t2_4_state_joins_on_item_key.py — state-update.py joins inbox-state.jsonl on
`item_key`, not `stem`.

Covers T2.4 (XDD 034 Phase 2): inbox-state.jsonl is an append-only log, replayed last-wins
per key (state-update.py:39,52,76,82 pre-fix). Today that key is the bare `stem`. Once
inbox discovery is recursive (Phase 3), two notes in different subfolders can share a
filename — so one item's state entry silently masks the other's carried-forward `path`,
and a later status update for item A can be built from item B's prior entry instead of
its own `[ref: PRD/AC Feature 2]`.

A count-only assertion (`len(replayed) == 2`) would pass against a broken implementation
that returns two copies of the *same* entry, so every masking assertion below checks the
*specific* value (path, status, error) carried by each item's own last-wins entry, not
just how many entries exist.

Invokes state-update.py as a CLI subprocess (as production does), never by importing an
internal helper directly for the masking scenario — the bug lives in what gets appended
to disk, so the on-disk artifact is what gets asserted on.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPT = REPO_ROOT / "tomo" / "scripts" / "state-update.py"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "state-entry.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _update(state: Path, *, item_key: str, stem: str, status: str, run_id: str,
            path: str | None = None, error_kind: str | None = None,
            error_msg: str | None = None) -> subprocess.CompletedProcess:
    args = [
        sys.executable, str(SCRIPT),
        "--state", str(state),
        "--item-key", item_key,
        "--stem", stem,
        "--status", status,
        "--run-id", run_id,
    ]
    if path is not None:
        args += ["--path", path]
    if error_kind is not None:
        args += ["--error-kind", error_kind]
    if error_msg is not None:
        args += ["--error-msg", error_msg]
    return subprocess.run(args, capture_output=True, text=True)


def _entries(state: Path) -> list[dict]:
    return [json.loads(line) for line in state.read_text(encoding="utf-8").splitlines() if line.strip()]


def _last(state: Path, item_key: str) -> dict:
    matches = [e for e in _entries(state) if e["item_key"] == item_key]
    assert matches, f"no entries for item_key={item_key!r}"
    return matches[-1]


# ---------------------------------------------------------------------------
# Two items sharing a filename record independent entries, and a later
# transition for one does not carry forward the other's path.
# ---------------------------------------------------------------------------


def test_two_same_stem_items_record_independent_entries_and_transitions(tmp_path):
    state = tmp_path / "inbox-state.jsonl"
    run_id = "run-clash"
    key_a = "100 Inbox/Places/Dresden.md"
    key_b = "100 Inbox/Archive/Dresden.md"

    # Both items share the bare stem "Dresden" but have distinct item_keys.
    proc = _update(state, item_key=key_a, stem="Dresden", status="running", run_id=run_id, path=key_a)
    assert proc.returncode == 0, proc.stderr
    proc = _update(state, item_key=key_b, stem="Dresden", status="running", run_id=run_id, path=key_b)
    assert proc.returncode == 0, proc.stderr

    # Transition A to done WITHOUT --path: state-update must carry A's own
    # path forward from A's own prior entry, not from B's (the entry most
    # recently appended for the shared stem).
    proc = _update(state, item_key=key_a, stem="Dresden", status="done", run_id=run_id)
    assert proc.returncode == 0, proc.stderr

    # Transition B to failed, also without --path.
    proc = _update(state, item_key=key_b, stem="Dresden", status="failed", run_id=run_id,
                    error_kind="parser_error", error_msg="malformed frontmatter")
    assert proc.returncode == 0, proc.stderr

    last_a = _last(state, key_a)
    last_b = _last(state, key_b)

    # Item A's own last entry must carry A's own path and status — not B's.
    assert last_a["status"] == "done"
    assert last_a["path"] == key_a, f"A's path was masked by B: {last_a['path']!r}"
    assert last_a["attempts"] == 1
    assert last_a["error"] is None

    # Item B's own last entry must carry B's own path, status and error.
    assert last_b["status"] == "failed"
    assert last_b["path"] == key_b, f"B's path was masked by A: {last_b['path']!r}"
    assert last_b["attempts"] == 1
    assert last_b["error"]["kind"] == "parser_error"

    # The two entries must not be the same object replayed twice.
    assert last_a != last_b


def test_replay_does_not_let_one_items_status_hide_the_other(tmp_path):
    """A third transition on A must not be confused for B's state, and vice
    versa, once both items have several lines on disk for the shared stem."""
    state = tmp_path / "inbox-state.jsonl"
    run_id = "run-replay"
    key_a = "100 Inbox/Places/Dresden.md"
    key_b = "100 Inbox/Archive/Dresden.md"

    _update(state, item_key=key_a, stem="Dresden", status="running", run_id=run_id, path=key_a)
    _update(state, item_key=key_b, stem="Dresden", status="running", run_id=run_id, path=key_b)
    _update(state, item_key=key_a, stem="Dresden", status="failed", run_id=run_id,
            error_kind="kado_read_timeout", error_msg="timed out")
    # B is still running and must be unaffected by A's failure.
    last_b = _last(state, key_b)
    assert last_b["status"] == "running"
    assert last_b["path"] == key_b
    assert last_b["error"] is None

    # A retries and succeeds; B remains untouched throughout.
    proc = _update(state, item_key=key_a, stem="Dresden", status="running", run_id=run_id)
    assert proc.returncode == 0, proc.stderr
    proc = _update(state, item_key=key_a, stem="Dresden", status="done", run_id=run_id)
    assert proc.returncode == 0, proc.stderr

    last_a = _last(state, key_a)
    last_b = _last(state, key_b)
    assert last_a["status"] == "done"
    assert last_a["attempts"] == 2
    assert last_a["path"] == key_a
    assert last_b["status"] == "running"
    assert last_b["path"] == key_b


# ---------------------------------------------------------------------------
# Existing single-item behaviour is unchanged (mirrors the pre-034 shell
# acceptance test in tests/test-004-phase3.sh, updated for --item-key).
# ---------------------------------------------------------------------------


def test_single_item_running_to_done_unchanged(tmp_path):
    state = tmp_path / "inbox-state.jsonl"
    key = "100 Inbox/item-one.md"
    run_id = "run-single"

    _update(state, item_key=key, stem="item-one", status="running", run_id=run_id, path=key)
    proc = _update(state, item_key=key, stem="item-one", status="done", run_id=run_id)
    assert proc.returncode == 0, proc.stderr

    entries = [e for e in _entries(state) if e["item_key"] == key]
    assert len(entries) == 2
    last = entries[-1]
    assert last["status"] == "done"
    assert last["attempts"] == 1
    assert last["started_at"] is not None
    assert last["completed_at"] is not None


def test_single_item_failed_carries_error_object(tmp_path):
    state = tmp_path / "inbox-state.jsonl"
    key = "100 Inbox/item-fail.md"
    run_id = "run-single"

    _update(state, item_key=key, stem="item-fail", status="running", run_id=run_id, path=key)
    proc = _update(state, item_key=key, stem="item-fail", status="failed", run_id=run_id,
                    error_kind="parser_error", error_msg="malformed YAML frontmatter")
    assert proc.returncode == 0, proc.stderr

    last = _last(state, key)
    assert last["status"] == "failed"
    assert last["error"]["kind"] == "parser_error"
    assert "malformed" in last["error"]["message"]


# ---------------------------------------------------------------------------
# Every emitted entry validates against state-entry.schema.json.
# ---------------------------------------------------------------------------


def test_all_emitted_entries_validate_against_schema(tmp_path):
    state = tmp_path / "inbox-state.jsonl"
    run_id = "run-schema"
    key_a = "100 Inbox/Places/Dresden.md"
    key_b = "100 Inbox/Archive/Dresden.md"

    _update(state, item_key=key_a, stem="Dresden", status="running", run_id=run_id, path=key_a)
    _update(state, item_key=key_b, stem="Dresden", status="running", run_id=run_id, path=key_b)
    _update(state, item_key=key_a, stem="Dresden", status="done", run_id=run_id)
    _update(state, item_key=key_b, stem="Dresden", status="failed", run_id=run_id,
            error_kind="x", error_msg="y")

    schema = _schema()
    for entry in _entries(state):
        jsonschema.validate(entry, schema)
