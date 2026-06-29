#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_client_path_exists.py — Unit tests for KadoClient.path_exists.

Regression coverage for spec 026 live-walk bug: path_exists must route the
existence probe BY EXTENSION. Kado's operation=frontmatter (and note) reject
non-.md paths with VALIDATION_ERROR — NOT NOT_FOUND — so a .md-only probe
makes the existence check error out for every .base/.canvas path. That broke
`kado-write-file.py --no-overwrite` for exactly the non-.md artifact types
spec 026 introduced (collision guard never reached; write fell back / blocked).

Spec: docs/XDD/specs/026-companion-p1-authoring-skills/ (ADR-7 collision guard)
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"
sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.kado_client` works

from lib.kado_client import KadoClient, KadoNotFoundError  # noqa: E402


def _make_client() -> KadoClient:
    return KadoClient(base_url="http://localhost:23026", token="test-token")


def test_path_exists_md_uses_frontmatter_probe():
    """A .md path is probed via operation=frontmatter (the cheap metadata read)."""
    client = _make_client()
    captured: dict = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["operation"] = arguments.get("operation")
        return {"content": {}, "modified": 1}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    assert client.path_exists("100 Inbox/note.md") is True
    assert captured["operation"] == "frontmatter"


def test_path_exists_non_md_uses_file_probe():
    """A non-.md path (.base/.canvas) is probed via operation=file, NOT frontmatter.

    This is the regression guard: frontmatter on a .base path returns
    VALIDATION_ERROR, which must never be the existence-probe path.
    """
    client = _make_client()
    captured: dict = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["operation"] = arguments.get("operation")
        return {"content": "", "modified": 1}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    assert client.path_exists("100 Inbox/Reading List.base") is True
    assert captured["operation"] == "file"


def test_path_exists_canvas_uses_file_probe():
    """A .canvas path is also probed via operation=file."""
    client = _make_client()
    captured: dict = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["operation"] = arguments.get("operation")
        return {"content": "", "modified": 1}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    assert client.path_exists("100 Inbox/board.canvas") is True
    assert captured["operation"] == "file"


def test_path_exists_returns_false_on_not_found():
    """A genuine NOT_FOUND means the path does not exist (both families)."""
    client = _make_client()

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        raise KadoNotFoundError("not found")

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    assert client.path_exists("100 Inbox/missing.md") is False
    assert client.path_exists("100 Inbox/missing.base") is False
