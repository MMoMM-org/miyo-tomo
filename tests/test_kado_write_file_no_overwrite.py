#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_write_file_no_overwrite.py — Tests for kado-write-file.py --no-overwrite.

Spec 026, T1.2 (Companion Mode P1 — Deterministic Safety Scripts).
ADR-7, ADR-9: --no-overwrite must refuse the write and return an 'exists' signal
(exit 3 + EXISTS:<path> on stdout) when the vault path is already present.

Contract (locked for T4.2): exit code 3 + "EXISTS:<vault-path>" on stdout.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPT_PATH = REPO_ROOT / "tomo" / "scripts" / "kado-write-file.py"
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

# Ensure lib is importable so KadoError is the same class the script uses.
sys.path.insert(0, str(LIB_DIR.parent))
from lib.kado_client import KadoError  # noqa: E402


def _load_script():
    """Load kado-write-file.py as a module (importlib handles the hyphen)."""
    spec = importlib.util.spec_from_file_location("kado_write_file", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load once; individual tests patch KadoClient on this module object.
kado_write_file = _load_script()


def _run(monkeypatch, argv_tail: list[str], fake_client_cls) -> int:
    """Call main() with given CLI args and a fake KadoClient; return exit code."""
    monkeypatch.setattr(sys, "argv", ["kado-write-file.py"] + argv_tail)
    monkeypatch.setattr(kado_write_file, "KadoClient", fake_client_cls)
    try:
        return kado_write_file.main()
    except SystemExit as exc:
        # argparse may raise SystemExit on unknown flags before we implement them
        return exc.code if exc.code is not None else 1


# ---------------------------------------------------------------------------
# --no-overwrite: existing path → exit 3
# ---------------------------------------------------------------------------


def test_no_overwrite_existing_path_exits_3(tmp_path, monkeypatch, capsys):
    """--no-overwrite + existing vault path must exit 3 without writing."""
    local = tmp_path / "artifact.md"
    local.write_text("some content")
    vault = "100 Inbox/existing-note.md"

    class FakeClient:
        def __init__(self):
            pass

        def path_exists(self, path: str) -> bool:
            return True

        def write_note(self, path, content):
            raise AssertionError("must not write when path already exists")

    rc = _run(monkeypatch, ["--no-overwrite", "--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 3


def test_no_overwrite_existing_path_prints_exists_signal(tmp_path, monkeypatch, capsys):
    """--no-overwrite + existing vault path must print EXISTS:<path> on stdout."""
    local = tmp_path / "artifact.md"
    local.write_text("some content")
    vault = "100 Inbox/existing-note.md"

    class FakeClient:
        def __init__(self):
            pass

        def path_exists(self, path: str) -> bool:
            return True

        def write_note(self, path, content):
            raise AssertionError("must not write")

    _run(monkeypatch, ["--no-overwrite", "--vault", vault, "--local", str(local)], FakeClient)
    out, _ = capsys.readouterr()
    assert f"EXISTS:{vault}" in out


# ---------------------------------------------------------------------------
# --no-overwrite: absent path → writes normally, exit 0
# ---------------------------------------------------------------------------


def test_no_overwrite_absent_path_writes_and_exits_0(tmp_path, monkeypatch, capsys):
    """--no-overwrite + absent vault path must write normally and exit 0."""
    local = tmp_path / "new-note.md"
    local.write_text("hello vault")
    vault = "100 Inbox/new-note.md"
    write_calls: list[str] = []

    class FakeClient:
        def __init__(self):
            pass

        def path_exists(self, path: str) -> bool:
            return False

        def write_note(self, path: str, content: str) -> dict:
            write_calls.append(path)
            return {"path": path, "modified": 1}

    rc = _run(
        monkeypatch,
        ["--no-overwrite", "--vault", vault, "--local", str(local)],
        FakeClient,
    )
    assert rc == 0
    assert write_calls == [vault]


# ---------------------------------------------------------------------------
# Non-.md extension (.base) → operation=file / write_file happy path
# ---------------------------------------------------------------------------


def test_non_md_extension_uses_write_file(tmp_path, monkeypatch, capsys):
    """A .base vault path must use write_file (operation=file) and exit 0."""
    local = tmp_path / "frame.base"
    local.write_bytes(b'{"type": "base", "items": []}')
    vault = "100 Inbox/frame.base"
    write_calls: list[str] = []

    class FakeClient:
        def __init__(self):
            pass

        def write_file(self, path: str, data: bytes) -> dict:
            write_calls.append(path)
            return {"path": path, "modified": 1}

        def write_note(self, path, content):
            raise AssertionError("must not call write_note for a .base file")

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 0
    assert write_calls == [vault]


# ---------------------------------------------------------------------------
# --no-overwrite: KadoError during path_exists() → exit 1
# ---------------------------------------------------------------------------


def test_no_overwrite_path_check_kado_error_exits_1(tmp_path, monkeypatch, capsys):
    """KadoError raised by path_exists() under --no-overwrite must exit 1, not traceback."""
    local = tmp_path / "artifact.md"
    local.write_text("content")
    vault = "100 Inbox/some-note.md"

    class FakeClient:
        def __init__(self):
            pass

        def path_exists(self, path: str) -> bool:
            raise KadoError("connection refused")

        def write_note(self, path, content):
            raise AssertionError("must not reach write when path_exists fails")

    rc = _run(monkeypatch, ["--no-overwrite", "--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 1


# ---------------------------------------------------------------------------
# Write-denial (KadoError during write) → exit 1
# ---------------------------------------------------------------------------


def test_write_denial_exits_1(tmp_path, monkeypatch, capsys):
    """A KadoError raised during write must result in exit 1."""
    local = tmp_path / "denied.md"
    local.write_text("content that will be denied")
    vault = "100 Inbox/denied.md"

    class FakeClient:
        def __init__(self):
            pass

        def path_exists(self, path: str) -> bool:
            return False

        def write_note(self, path: str, content: str) -> dict:
            raise KadoError("path not allowed by ACL")

    rc = _run(monkeypatch, ["--vault", vault, "--local", str(local)], FakeClient)
    assert rc == 1
