#!/usr/bin/env python3
# version: 0.3.0
"""test_mark_captured.py — Behavioural tests for mark-captured.py.

Verifies that mark-captured.py:
- Writes tomo.state=captured via write_frontmatter (not regex YAML edit)
- Propagates run_id from --run-id CLI arg
- Does NOT write any tag field (no legacy #<prefix>/captured tag)
- Handles non-markdown paths by skipping them
- Is idempotent (write call made; no exception on re-run)

The old test_tag_captured.py tested the regex-YAML edit path which no longer
exists. It is deleted and replaced by this file.

Implementation note on module loading:
    mark-captured.py imports lib.doc_frontmatter which in turn imports
    jsonschema (an external dependency not available on every host Python
    installation). Tests inject a lightweight fake into sys.modules before
    loading the script module so the import chain succeeds without requiring
    jsonschema to be installed on the host.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "mark-captured.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def _make_fake_build_tomo_block():
    """Return a fake build_tomo_block that mimics the real one without jsonschema."""
    import datetime

    def fake_build_tomo_block(doc_type: str, state: str, run_id: str, **source_refs: str) -> dict:
        block: dict = {
            "doc_type": doc_type,
            "state": state,
            "run_id": run_id,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            **source_refs,
        }
        return block

    return fake_build_tomo_block


def _inject_doc_frontmatter_fake():
    """Inject a fake lib.doc_frontmatter into sys.modules.

    This avoids pulling in jsonschema (which may not be installed on the host
    Python used to run these tests).  The fake preserves the interface that
    mark-captured.py requires: build_tomo_block().
    """
    fake_mod = types.ModuleType("lib.doc_frontmatter")
    fake_mod.build_tomo_block = _make_fake_build_tomo_block()  # type: ignore[attr-defined]

    class FakeSchemaValidationError(Exception):
        pass

    fake_mod.SchemaValidationError = FakeSchemaValidationError  # type: ignore[attr-defined]

    # Register under both qualified and short names so either import form works.
    sys.modules.setdefault("lib.doc_frontmatter", fake_mod)
    sys.modules.setdefault("doc_frontmatter", fake_mod)
    return fake_mod


# Inject once at module load time.
_FAKE_DOC_FM = _inject_doc_frontmatter_fake()


def _load_script_module():
    """Load mark-captured.py as a module, reusing the already-injected fakes."""
    spec = importlib.util.spec_from_file_location("mark_captured", SCRIPT_PATH)
    assert spec and spec.loader, f"Cannot load module from {SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def state_file(tmp_path):
    """Write a state-file with one .md (done) and one .m4a (done) item."""
    path = tmp_path / "inbox-state.jsonl"
    entries = [
        {
            "stem": "Asahikawa",
            "path": "100 Inbox/Asahikawa.md",
            "status": "done",
            "run_id": "run-fixture",
        },
        {
            "stem": "memo-audio",
            "path": "100 Inbox/memo.m4a",
            "status": "done",
            "run_id": "run-fixture",
        },
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


@pytest.fixture()
def two_md_state_file(tmp_path):
    """Write a state-file with two .md (done) items."""
    path = tmp_path / "inbox-state.jsonl"
    entries = [
        {
            "stem": "NoteA",
            "path": "100 Inbox/NoteA.md",
            "status": "done",
            "run_id": "run-fixture",
        },
        {
            "stem": "NoteB",
            "path": "100 Inbox/NoteB.md",
            "status": "done",
            "run_id": "run-fixture",
        },
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


# ---------------------------------------------------------------------------
# T1 — writes tomo.state=captured via write_frontmatter
# ---------------------------------------------------------------------------


def test_writes_tomo_state_captured(state_file, monkeypatch):
    """Script calls write_frontmatter with the correct tomo block per .md item."""
    mod = _load_script_module()

    fake_client = MagicMock()
    fake_client.write_frontmatter.return_value = {"path": "100 Inbox/Asahikawa.md", "modified": 1}

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(state_file), "--run-id", "run-fixture"],
    )
    rc = mod.main()

    assert rc == 0, f"expected exit 0, got {rc}"

    # Exactly one call for the single .md item
    assert fake_client.write_frontmatter.call_count == 1

    call_kwargs = fake_client.write_frontmatter.call_args
    _path, frontmatter = call_kwargs.args[0], call_kwargs.args[1]
    assert _path == "100 Inbox/Asahikawa.md"

    tomo_block = frontmatter["tomo"]
    assert tomo_block["doc_type"] == "source"
    assert tomo_block["state"] == "captured"
    assert "updated_at" in tomo_block

    # mode must be "merge" (positional-or-keyword)
    mode_val = call_kwargs.kwargs.get("mode")
    assert mode_val == "merge", f"Expected mode='merge', got {mode_val!r}"


# ---------------------------------------------------------------------------
# T2 — idempotent on already-captured
# ---------------------------------------------------------------------------


def test_writes_multiple_items_in_one_invocation(two_md_state_file, monkeypatch):
    """Script processes multiple .md items in one invocation, calling write_frontmatter twice."""
    mod = _load_script_module()

    fake_client = MagicMock()
    fake_client.write_frontmatter.return_value = {"path": "", "modified": 1}

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(two_md_state_file), "--run-id", "run-fixture"],
    )
    rc = mod.main()

    assert rc == 0, f"expected exit 0, got {rc}"

    # Two .md items should result in two write_frontmatter calls
    assert fake_client.write_frontmatter.call_count == 2

    # Verify both calls use mode="merge"
    calls = fake_client.write_frontmatter.call_args_list
    assert len(calls) == 2

    for i, call in enumerate(calls):
        call_kwargs = call
        mode_val = call_kwargs.kwargs.get("mode")
        assert mode_val == "merge", f"Call {i}: Expected mode='merge', got {mode_val!r}"

    # Verify the two paths are the correct markdown files
    paths = [call.args[0] for call in calls]
    assert "100 Inbox/NoteA.md" in paths
    assert "100 Inbox/NoteB.md" in paths


# ---------------------------------------------------------------------------
# T2 — idempotent on already-captured
# ---------------------------------------------------------------------------


def test_idempotent_on_already_captured(state_file, monkeypatch):
    """Second run makes the write call without raising (merge-mode is idempotent)."""
    mod = _load_script_module()

    fake_client = MagicMock()
    fake_client.write_frontmatter.return_value = {"path": "100 Inbox/Asahikawa.md", "modified": 2}

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    # Re-run the SAME run_id twice (the realistic idempotency case: a re-run
    # after a partial failure). Both must match the fixture's run_id (#116).
    for attempt in ("first", "second"):
        monkeypatch.setattr(
            sys, "argv",
            ["mark-captured.py", "--state", str(state_file), "--run-id", "run-fixture"],
        )
        rc = mod.main()
        assert rc == 0, f"attempt {attempt}: expected exit 0, got {rc}"

    # Each run issues one call; two runs = two calls, no exceptions raised
    assert fake_client.write_frontmatter.call_count == 2


# ---------------------------------------------------------------------------
# T3 — no legacy tag written
# ---------------------------------------------------------------------------


def test_no_legacy_tag_written(state_file, monkeypatch):
    """write_frontmatter payload must not contain a 'tags' key or any /captured tag."""
    mod = _load_script_module()

    captured_payloads = []

    def fake_write_frontmatter(path, frontmatter, mode="merge", expected_modified=None):
        captured_payloads.append(frontmatter)
        return {"path": path, "modified": 1}

    fake_client = MagicMock()
    fake_client.write_frontmatter.side_effect = fake_write_frontmatter

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(state_file), "--run-id", "run-fixture"],
    )
    mod.main()

    assert captured_payloads, "No write_frontmatter calls were made"

    def _has_captured_tag(obj) -> bool:
        if isinstance(obj, str):
            return "/captured" in obj
        if isinstance(obj, dict):
            if "tags" in obj:
                return True
            return any(_has_captured_tag(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_has_captured_tag(item) for item in obj)
        return False

    for payload in captured_payloads:
        assert not _has_captured_tag(payload), (
            f"Legacy tag found in write_frontmatter payload: {payload}"
        )


# ---------------------------------------------------------------------------
# T4 — run_id propagated from --run-id argv
# ---------------------------------------------------------------------------


def test_run_id_propagated_from_argv(tmp_path, monkeypatch):
    """The run_id passed via --run-id appears in the tomo block's run_id field.

    Uses a dedicated state file seeded with the same unique run_id so the item
    survives the #116 run_id filter — otherwise there would be nothing to mark.
    """
    mod = _load_script_module()

    unique_run_id = "run-unique-abc123"
    state_file = tmp_path / "inbox-state.jsonl"
    state_file.write_text(json.dumps({
        "stem": "Asahikawa",
        "path": "100 Inbox/Asahikawa.md",
        "status": "done",
        "run_id": unique_run_id,
    }) + "\n")

    captured_tomo_blocks = []

    def fake_write_frontmatter(path, frontmatter, mode="merge", expected_modified=None):
        captured_tomo_blocks.append(frontmatter.get("tomo", {}))
        return {"path": path, "modified": 1}

    fake_client = MagicMock()
    fake_client.write_frontmatter.side_effect = fake_write_frontmatter

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(state_file), "--run-id", unique_run_id],
    )
    mod.main()

    assert captured_tomo_blocks, "No write_frontmatter calls were made"
    for block in captured_tomo_blocks:
        assert block.get("run_id") == unique_run_id, (
            f"Expected run_id={unique_run_id!r}, got {block.get('run_id')!r}"
        )


# ---------------------------------------------------------------------------
# T5 — no regex / re module used for YAML editing
# ---------------------------------------------------------------------------


def test_no_regex_yaml_edit():
    """mark-captured.py must not use re.sub/re.compile for YAML frontmatter editing."""
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    # The old script used import re + re.match/re.sub for YAML parsing.
    # The new script must not import re (or if it does, not for YAML editing).
    # Asserting 'import re' absent is the cleanest check since the old regex
    # block was the only reason re was imported.
    assert "import re" not in script_text, (
        "mark-captured.py still imports 're' — the regex YAML edit block must be removed"
    )

    assert "re.sub" not in script_text, "re.sub found — regex YAML edit not fully removed"
    assert "re.compile" not in script_text, "re.compile found — regex YAML edit not fully removed"


# ---------------------------------------------------------------------------
# T6 — non-markdown paths are skipped (regression guard from test_tag_captured.py)
# ---------------------------------------------------------------------------


def test_non_md_paths_are_skipped(state_file, monkeypatch, capsys):
    """Non-.md paths must be skipped before any Kado call."""
    mod = _load_script_module()

    fake_client = MagicMock()
    fake_client.write_frontmatter.return_value = {"path": "100 Inbox/Asahikawa.md", "modified": 1}

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(state_file), "--run-id", "run-fixture"],
    )
    rc = mod.main()

    assert rc == 0, f"expected exit 0, got {rc}"

    # Only the .md item should reach write_frontmatter
    assert fake_client.write_frontmatter.call_count == 1
    call_path = fake_client.write_frontmatter.call_args.args[0]
    assert call_path.endswith(".md"), f"Non-.md path reached Kado: {call_path}"
    assert ".m4a" not in call_path


# ---------------------------------------------------------------------------
# T7 — write failure returns exit code 1 with error count in stderr
# ---------------------------------------------------------------------------


def test_write_failure_returns_exit_code_1(state_file, monkeypatch, capsys):
    """When write_frontmatter raises KadoError, main() returns 1 and reports errors."""
    from lib.kado_client import KadoError

    mod = _load_script_module()

    fake_client = MagicMock()
    fake_client.read_frontmatter.return_value = {"modified": 1}
    fake_client.write_frontmatter.side_effect = KadoError("write denied")

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(state_file), "--run-id", "run-fixture"],
    )
    rc = mod.main()

    assert rc == 1, f"expected exit 1 on write failure, got {rc}"

    captured = capsys.readouterr()
    assert "errors=1" in captured.err


# ---------------------------------------------------------------------------
# T8 — nonexistent state file is not an error (tag-handler-only batch) → exit 0
# ---------------------------------------------------------------------------


def test_missing_state_file_returns_exit_code_0(tmp_path, monkeypatch, capsys):
    """A nonexistent --state path is not an error: a batch of only tag-handler
    captures records no per-item state, so there is simply nothing to mark.
    main() returns 0 with a clear note and no FATAL (and never reaches Kado)."""
    mod = _load_script_module()

    nonexistent = tmp_path / "no-such-file.jsonl"

    # KadoClient must NOT be constructed — the missing-file check returns first.
    monkeypatch.setattr(
        mod, "KadoClient",
        lambda: (_ for _ in ()).throw(AssertionError("KadoClient must not be called")),
    )
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(nonexistent), "--run-id", "run-t8"],
    )
    rc = mod.main()

    assert rc == 0, f"expected exit 0 for missing state file, got {rc}"

    captured = capsys.readouterr()
    assert "no state-file" in captured.err
    assert "FATAL" not in captured.err


# ---------------------------------------------------------------------------
# T9 — Kado connection failure returns exit code 2 with FATAL in stderr
# ---------------------------------------------------------------------------


def test_kado_connection_failure_returns_exit_code_2(state_file, monkeypatch, capsys):
    """When KadoClient() raises KadoError, main() returns 2 with FATAL message."""
    from lib.kado_client import KadoError

    mod = _load_script_module()

    def failing_client():
        raise KadoError("no connection")

    monkeypatch.setattr(mod, "KadoClient", failing_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(state_file), "--run-id", "run-t9"],
    )
    rc = mod.main()

    assert rc == 2, f"expected exit 2 for Kado connection failure, got {rc}"

    captured = capsys.readouterr()
    assert "FATAL" in captured.err


# ---------------------------------------------------------------------------
# T10 — stale prior-run done stems are NOT re-stamped (#116)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mixed_run_state_file(tmp_path):
    """State-file with two done .md items from DIFFERENT runs.

    inbox-state.jsonl is append-only and never truncated, so a fresh run sees
    prior-run entries too. mark-captured must only re-stamp the current run's
    stems — otherwise it re-marks source notes that may no longer exist.
    """
    path = tmp_path / "inbox-state.jsonl"
    entries = [
        {
            "stem": "StaleNote",
            "path": "100 Inbox/StaleNote.md",
            "status": "done",
            "run_id": "run-OLD",
        },
        {
            "stem": "FreshNote",
            "path": "100 Inbox/FreshNote.md",
            "status": "done",
            "run_id": "run-NEW",
        },
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


def test_stale_run_stems_are_not_marked(mixed_run_state_file, monkeypatch):
    """Invoked with --run-id run-NEW, only FreshNote is stamped; StaleNote is
    skipped because its entry carries a different run_id (#116)."""
    mod = _load_script_module()

    marked_paths = []

    def fake_write_frontmatter(path, frontmatter, mode="merge", expected_modified=None):
        marked_paths.append(path)
        return {"path": path, "modified": 1}

    fake_client = MagicMock()
    fake_client.write_frontmatter.side_effect = fake_write_frontmatter

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(mixed_run_state_file), "--run-id", "run-NEW"],
    )
    rc = mod.main()

    assert rc == 0, f"expected exit 0, got {rc}"
    assert marked_paths == ["100 Inbox/FreshNote.md"], (
        f"expected only the current-run stem to be marked; got {marked_paths}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
