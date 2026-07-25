#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_write_file.py — kado-write-file.py expectedModified auto-resolve (030).

On overwrite, Kado requires the expectedModified optimistic-concurrency guard.
kado-write-file.py auto-resolves it: fetch the target's current `modified` before
the write (read_note for .md, read_file for other); NOT_FOUND → new file → no
guard; an explicit --expected-modified skips the fetch. A concurrency conflict on
write → a distinct exit code (4).

Mocks verified against the real lib (KadoConcurrencyError < KadoToolError < KadoError;
write_note/write_file signatures include expected_modified; read_note/read_file
return {"modified": ...}; KadoNotFoundError on absent read).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPT_PATH = REPO_ROOT / "tomo" / "scripts" / "kado-write-file.py"
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))
from lib.kado_client import (  # noqa: E402
    KadoConcurrencyError,
    KadoError,
    KadoNotFoundError,
)


def _load_script():
    spec = importlib.util.spec_from_file_location("kado_write_file", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kado_write_file = _load_script()


def _run(monkeypatch, argv_tail: list[str], fake_client_cls) -> int:
    monkeypatch.setattr(sys, "argv", ["kado-write-file.py"] + argv_tail)
    monkeypatch.setattr(kado_write_file, "KadoClient", fake_client_cls)
    try:
        return kado_write_file.main()
    except SystemExit as exc:
        return exc.code if exc.code is not None else 1


# ---------------------------------------------------------------------------
# New file (read → NOT_FOUND) → write with expected_modified=None (no guard)
# ---------------------------------------------------------------------------

def test_new_file_writes_without_guard(tmp_path, monkeypatch):
    local = tmp_path / "new.md"
    local.write_text("hello")
    vault = "100 Inbox/2026-07-20_1430_garden-audit.md"
    captured = {}

    class FakeClient:
        def read_note(self, path):
            raise KadoNotFoundError("not found")

        def write_note(self, path, content, expected_modified=None):
            captured["expected_modified"] = expected_modified
            return {"path": path, "modified": 99}

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 0
    assert captured["expected_modified"] is None  # new file → no guard


# ---------------------------------------------------------------------------
# Overwrite (read returns modified=M) → write with expected_modified=M
# ---------------------------------------------------------------------------

def test_overwrite_threads_current_modified_as_guard(tmp_path, monkeypatch):
    local = tmp_path / "over.md"
    local.write_text("updated")
    vault = "100 Inbox/2026-07-20_1430_garden-audit.md"
    captured = {}

    class FakeClient:
        def read_note(self, path):
            return {"content": "old", "modified": 1712345678}

        def write_note(self, path, content, expected_modified=None):
            captured["expected_modified"] = expected_modified
            return {"path": path, "modified": 1712345679}

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 0
    assert captured["expected_modified"] == 1712345678


def test_overwrite_non_md_uses_read_file_and_write_file(tmp_path, monkeypatch):
    local = tmp_path / "wire.json"
    local.write_bytes(b'{"schema_version": "1"}')
    vault = "100 Inbox/2026-07-20_1430_garden-audit.json"
    captured = {}

    class FakeClient:
        def read_file(self, path):
            return {"content": "", "modified": 555}

        def write_file(self, path, data, expected_modified=None):
            captured["expected_modified"] = expected_modified
            return {"path": path, "modified": 556}

        def read_note(self, path):
            raise AssertionError("must not read_note for a .json file")

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 0
    assert captured["expected_modified"] == 555


# ---------------------------------------------------------------------------
# Explicit --expected-modified → used verbatim, NO fetch
# ---------------------------------------------------------------------------

def test_explicit_expected_modified_skips_fetch(tmp_path, monkeypatch):
    local = tmp_path / "x.md"
    local.write_text("body")
    vault = "100 Inbox/note.md"
    captured = {}

    class FakeClient:
        def read_note(self, path):
            raise AssertionError("must NOT fetch when --expected-modified is given")

        def write_note(self, path, content, expected_modified=None):
            captured["expected_modified"] = expected_modified
            return {"path": path, "modified": 124}

    rc = _run(
        monkeypatch,
        ["--vault", vault, "--local", str(local), "--expected-modified", "123"],
        FakeClient,
    )
    assert rc == 0
    assert captured["expected_modified"] == 123


# ---------------------------------------------------------------------------
# --no-overwrite + existing → exit 3, no write, no fetch
# ---------------------------------------------------------------------------

def test_no_overwrite_existing_no_write_no_fetch(tmp_path, monkeypatch):
    local = tmp_path / "a.md"
    local.write_text("content")
    vault = "100 Inbox/exists.md"

    class FakeClient:
        def path_exists(self, path):
            return True

        def read_note(self, path):
            raise AssertionError("must not fetch under --no-overwrite refusal")

        def write_note(self, path, content, expected_modified=None):
            raise AssertionError("must not write under --no-overwrite refusal")

    rc = _run(monkeypatch, ["--no-overwrite", "--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 3


def test_no_overwrite_wins_over_expected_modified(tmp_path, monkeypatch):
    # Both given → --no-overwrite (refuse-if-exists) takes precedence.
    local = tmp_path / "a.md"
    local.write_text("content")
    vault = "100 Inbox/exists.md"

    class FakeClient:
        def path_exists(self, path):
            return True

        def write_note(self, path, content, expected_modified=None):
            raise AssertionError("must not write — --no-overwrite wins")

    rc = _run(
        monkeypatch,
        ["--no-overwrite", "--expected-modified", "9", "--vault", vault, "--local", str(local)],
        FakeClient,
    )
    assert rc == 3


# ---------------------------------------------------------------------------
# Read error (not NOT_FOUND) during guard fetch → exit 1
# ---------------------------------------------------------------------------

def test_read_error_during_fetch_exits_1(tmp_path, monkeypatch):
    local = tmp_path / "a.md"
    local.write_text("content")
    vault = "100 Inbox/note.md"

    class FakeClient:
        def read_note(self, path):
            raise KadoError("connection refused")

        def write_note(self, path, content, expected_modified=None):
            raise AssertionError("must not write when the guard fetch errors")

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 1


# ---------------------------------------------------------------------------
# Concurrency conflict on write → distinct exit code 4
# ---------------------------------------------------------------------------

def test_concurrency_conflict_exits_4(tmp_path, monkeypatch, capsys):
    local = tmp_path / "a.md"
    local.write_text("content")
    vault = "100 Inbox/note.md"

    class FakeClient:
        def read_note(self, path):
            return {"content": "old", "modified": 100}

        def write_note(self, path, content, expected_modified=None):
            raise KadoConcurrencyError("expectedModified mismatch: expected 100, got 200")

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 4
    _, err = capsys.readouterr()
    assert "retry" in err.lower()


def test_conflict_via_generic_tool_error_message_exits_4(tmp_path, monkeypatch, capsys):
    # write_note/write_file raise a generic KadoError (KadoToolError) on mismatch —
    # the message signature ("expectedModified" + "mismatch") must still map to 4.
    local = tmp_path / "a.md"
    local.write_text("content")
    vault = "100 Inbox/note.md"

    class FakeClient:
        def read_note(self, path):
            return {"content": "old", "modified": 100}

        def write_note(self, path, content, expected_modified=None):
            raise KadoError("kado-write returned an error: expectedModified mismatch")

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 4
    _, err = capsys.readouterr()
    assert "retry" in err.lower()


# ---------------------------------------------------------------------------
# A non-conflict write error stays exit 1 (not 4)
# ---------------------------------------------------------------------------

def test_non_conflict_write_error_exits_1(tmp_path, monkeypatch):
    local = tmp_path / "a.md"
    local.write_text("content")
    vault = "100 Inbox/note.md"

    class FakeClient:
        def read_note(self, path):
            return {"content": "old", "modified": 100}

        def write_note(self, path, content, expected_modified=None):
            raise KadoError("path not allowed by ACL")

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 1
