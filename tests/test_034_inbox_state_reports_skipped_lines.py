#!/usr/bin/env python3
# version: 0.1.0
"""test_034_inbox_state_reports_skipped_lines.py — a corrupt state line is audible.

`lib.inbox_state.last_state_per_item_key` fails open on a malformed or
key-less line in `inbox-state.jsonl`: the run continues, but before this test
the skip left no counter, no diagnostic, no trace anywhere. Spec 034's T2.3
already converted a silent `continue` past a missing analyst result into a
reported `needs_attention` entry plus a stderr line naming the item — this is
the same hardening one layer down, at the state-replay helper both
`suggestions-reducer.py` and `mark-captured.py` build on.

Four cases:
  1. a malformed-JSON line is skipped AND counted
  2. a line with no `item_key` is skipped AND counted
  3. a well-formed log reports ZERO skips (negative control — the counter
     must not simply always fire)
  4. each caller, invoked the way production invokes it, emits a stderr
     diagnostic naming how many lines were skipped

The helper keeps its fail-open contract: a corrupt line never aborts the
run, and the `{item_key: entry}` return shape is unchanged. Visibility is
opt-in via a `skip_report` dict the caller passes in and reads back.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
REDUCER = SCRIPTS_DIR / "suggestions-reducer.py"
MARK_CAPTURED = SCRIPTS_DIR / "mark-captured.py"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.inbox_state import last_state_per_item_key  # noqa: E402

_DEPS = "/tmp/claude/py_deps"
_ENV = {
    **os.environ,
    "PYTHONPATH": ":".join(
        p for p in [_DEPS, str(SCRIPTS_DIR)] if os.path.isdir(p) or p == _DEPS
    )
    + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}

RUN_ID = "run-034-skip"


# ---------------------------------------------------------------------------
# 1-3: the helper itself, direct
# ---------------------------------------------------------------------------


def test_malformed_json_line_is_skipped_and_counted(tmp_path):
    state = tmp_path / "inbox-state.jsonl"
    state.write_text(
        json.dumps({"item_key": "100 Inbox/Good.md", "status": "done"}) + "\n"
        "{this is not valid json\n",
        encoding="utf-8",
    )
    skip_report: dict[str, int] = {}
    result = last_state_per_item_key(state, skip_report=skip_report)

    assert "100 Inbox/Good.md" in result, "the well-formed line must still replay"
    assert skip_report.get("malformed_json") == 1, skip_report
    assert skip_report.get("missing_item_key", 0) == 0, skip_report


def test_missing_item_key_line_is_skipped_and_counted(tmp_path):
    state = tmp_path / "inbox-state.jsonl"
    state.write_text(
        json.dumps({"item_key": "100 Inbox/Good.md", "status": "done"}) + "\n"
        + json.dumps({"status": "done", "path": "100 Inbox/NoKey.md"}) + "\n",
        encoding="utf-8",
    )
    skip_report: dict[str, int] = {}
    result = last_state_per_item_key(state, skip_report=skip_report)

    assert list(result.keys()) == ["100 Inbox/Good.md"]
    assert skip_report.get("missing_item_key") == 1, skip_report
    assert skip_report.get("malformed_json", 0) == 0, skip_report


def test_well_formed_log_reports_zero_skips(tmp_path):
    """Negative control: nothing corrupt in the log, so nothing is counted."""
    state = tmp_path / "inbox-state.jsonl"
    state.write_text(
        "\n".join(
            json.dumps({"item_key": f"100 Inbox/N{i}.md", "status": "done"})
            for i in range(3)
        )
        + "\n",
        encoding="utf-8",
    )
    skip_report: dict[str, int] = {}
    result = last_state_per_item_key(state, skip_report=skip_report)

    assert len(result) == 3
    assert sum(skip_report.values()) == 0, skip_report


# ---------------------------------------------------------------------------
# 4a: suggestions-reducer.py, invoked as a CLI subprocess (production path)
# ---------------------------------------------------------------------------


def _minimal_shared_ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": RUN_ID,
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")


def test_reducer_cli_reports_skipped_state_lines(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    shared_ctx = tmp_path / "shared-ctx.json"
    _minimal_shared_ctx(shared_ctx)
    output = tmp_path / "doc.json"

    state = tmp_path / "inbox-state.jsonl"
    # One well-formed entry (so the run has something to do) plus one
    # malformed-JSON line and one missing-item_key line.
    state.write_text(
        json.dumps({
            "item_key": "100 Inbox/Real.md", "path": "100 Inbox/Real.md",
            "stem": "Real", "status": "failed", "run_id": RUN_ID,
            "error": {"kind": "test", "message": "n/a"},
        }) + "\n"
        "not json at all\n"
        + json.dumps({"status": "done", "path": "100 Inbox/NoKey.md"}) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable, str(REDUCER),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", RUN_ID,
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--no-kado",
            "--output", str(output),
        ],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert result.returncode == 0, (
        f"reducer exit {result.returncode}; stderr:\n{result.stderr}"
    )
    assert "malformed_json=1" in result.stderr, result.stderr
    assert "missing_item_key=1" in result.stderr, result.stderr


# ---------------------------------------------------------------------------
# 4b: mark-captured.py, invoked through its real CLI entry point (main()
# reading sys.argv) with only the Kado network client mocked — the same
# in-process pattern test_mark_captured.py already uses for this script,
# since a genuine OS subprocess would need a live Kado server to talk to.
# ---------------------------------------------------------------------------


def _load_mark_captured_module():
    import importlib.util

    # mark-captured.py transitively imports lib.squelch_persist ->
    # suggestion-parser.py, which is owned by a concurrent agent in this
    # session and mid-flight. This test never exercises the MOC-proposal
    # squelch path (no moc-proposal-*.md item in its fixture), so stub the
    # whole module out rather than ride that transitive chain.
    if "lib.squelch_persist" not in sys.modules:
        fake_mod = types.ModuleType("lib.squelch_persist")
        fake_mod.persist_rejected_clusters = lambda *a, **k: 0  # type: ignore[attr-defined]
        sys.modules.setdefault("lib.squelch_persist", fake_mod)

    spec = importlib.util.spec_from_file_location("mark_captured", MARK_CAPTURED)
    assert spec and spec.loader, f"Cannot load module from {MARK_CAPTURED}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mark_captured_cli_reports_skipped_state_lines(tmp_path, monkeypatch, capsys):
    mod = _load_mark_captured_module()

    fake_client = MagicMock()
    fake_client.read_frontmatter.return_value = {"modified": 1}
    fake_client.write_frontmatter.return_value = {"path": "100 Inbox/Real.md", "modified": 2}
    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    state = tmp_path / "inbox-state.jsonl"
    state.write_text(
        json.dumps({
            "item_key": "100 Inbox/Real.md", "path": "100 Inbox/Real.md",
            "stem": "Real", "status": "done", "run_id": RUN_ID,
        }) + "\n"
        "not json at all\n"
        + json.dumps({"status": "done", "path": "100 Inbox/NoKey.md"}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(state), "--run-id", RUN_ID],
    )
    rc = mod.main()
    captured = capsys.readouterr()

    assert rc == 0, f"expected exit 0, got {rc}; stderr:\n{captured.err}"
    assert "malformed_json=1" in captured.err, captured.err
    assert "missing_item_key=1" in captured.err, captured.err
