#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_client_listnotes.py — Unit tests for KadoClient.list_notes
and KadoClient.read_inline_fields.

Covers T1.1 (F-34 Phase 1): verifies call-shape, pagination, and return
normalisation for the two new KadoClient methods that support MSP
Condition B accumulation.

Spec: docs/XDD/specs/015-msp-condition-b-accumulation/
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.kado_client` works

from lib.kado_client import KadoClient  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> KadoClient:
    """Return a KadoClient with dummy config (no live server needed)."""
    return KadoClient(base_url="http://localhost:23026", token="test-token")


def _make_search_page(items: list[dict], next_cursor: str | None = None) -> dict:
    """Build a Kado-shape search result page as returned by _call_tool."""
    return {"items": items, "nextCursor": next_cursor}


# ---------------------------------------------------------------------------
# list_notes — call shape
# ---------------------------------------------------------------------------


def test_list_notes_call_shape():
    """list_notes sends operation=listNotes, path, fields, and limit to kado-search."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["tool"] = tool_name
        captured["args"] = arguments
        return _make_search_page([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.list_notes(
        "200 Notes/",
        fields=["links", "headings", "tags"],
        limit=100,
    )

    assert captured["tool"] == "kado-search"
    assert captured["args"]["operation"] == "listNotes"
    assert captured["args"]["path"] == "200 Notes/"
    assert captured["args"]["fields"] == ["links", "headings", "tags"]
    assert captured["args"]["limit"] == 100


def test_list_notes_default_limit_is_500():
    """list_notes sends limit=500 when caller omits the limit."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_page([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.list_notes("200 Notes/")

    assert captured["args"]["limit"] == 500


# ---------------------------------------------------------------------------
# list_notes — pagination
# ---------------------------------------------------------------------------


def test_list_notes_paginates_via_cursor():
    """list_notes follows nextCursor and merges items across pages."""
    client = _make_client()

    page1_items = [{"path": "200 Notes/a.md", "name": "a"}]
    page2_items = [{"path": "200 Notes/b.md", "name": "b"}]
    call_count = [0]

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_search_page(page1_items, next_cursor="cursor-abc")
        # second call must include cursor
        assert arguments.get("cursor") == "cursor-abc"
        return _make_search_page(page2_items, next_cursor=None)

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    results = client.list_notes("200 Notes/")

    assert call_count[0] == 2
    assert len(results) == 2
    assert results[0]["path"] == "200 Notes/a.md"
    assert results[1]["path"] == "200 Notes/b.md"


# ---------------------------------------------------------------------------
# list_notes — optional fields behaviour
# ---------------------------------------------------------------------------


def test_list_notes_omits_fields_when_none():
    """list_notes omits the fields key from the payload when fields=None (default)."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_page([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.list_notes("200 Notes/")

    assert "fields" not in captured["args"]


def test_list_notes_includes_depth_when_provided():
    """list_notes passes depth into the payload when the caller supplies it."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_page([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.list_notes("200 Notes/", depth=2)

    assert captured["args"]["depth"] == 2


def test_list_notes_omits_depth_when_none():
    """list_notes omits the depth key when depth=None (default)."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_page([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.list_notes("200 Notes/")

    assert "depth" not in captured["args"]


# ---------------------------------------------------------------------------
# read_inline_fields — call shape
# ---------------------------------------------------------------------------


def test_read_inline_fields_call_shape():
    """read_inline_fields calls kado-read with operation=dataview-inline-field."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["tool"] = tool_name
        captured["args"] = arguments
        return {"up": ["[[Some MOC]]"]}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.read_inline_fields("200 Notes/some-note.md")

    assert captured["tool"] == "kado-read"
    assert captured["args"]["operation"] == "dataview-inline-field"
    assert captured["args"]["path"] == "200 Notes/some-note.md"


# ---------------------------------------------------------------------------
# read_inline_fields — return value
# ---------------------------------------------------------------------------


def test_read_inline_fields_returns_dict():
    """read_inline_fields returns the raw dict from _call_tool."""
    client = _make_client()
    inline_data = {"up": ["[[MOC Root]]"], "status": ["active"]}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        return inline_data

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    result = client.read_inline_fields("200 Notes/some-note.md")

    assert result == inline_data
    assert result["up"] == ["[[MOC Root]]"]


def test_read_inline_fields_returns_empty_dict_when_no_fields():
    """read_inline_fields returns an empty dict when the note has no inline fields."""
    client = _make_client()

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        return {}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    result = client.read_inline_fields("200 Notes/bare-note.md")

    assert result == {}


# ---------------------------------------------------------------------------
# _search_all — fields passthrough
# ---------------------------------------------------------------------------


def test_search_all_fields_passthrough():
    """_search_all includes fields in args only when set (not None)."""
    client = _make_client()
    captured_with_fields: dict = {}
    captured_without_fields: dict = {}

    def fake_call_with(tool_name: str, arguments: dict) -> dict:
        captured_with_fields.update(arguments)
        return _make_search_page([])

    def fake_call_without(tool_name: str, arguments: dict) -> dict:
        captured_without_fields.update(arguments)
        return _make_search_page([])

    # Call with fields
    client._call_tool = fake_call_with  # type: ignore[method-assign]
    client._search_all("listNotes", path="Notes/", fields=["links", "tags"])
    assert captured_with_fields.get("fields") == ["links", "tags"]

    # Call without fields
    client._call_tool = fake_call_without  # type: ignore[method-assign]
    client._search_all("listNotes", path="Notes/")
    assert "fields" not in captured_without_fields


# ---------------------------------------------------------------------------
# Regression: existing _search_all callers unaffected
# ---------------------------------------------------------------------------


def test_list_dir_still_works_after_search_all_change():
    """list_dir continues to work without fields (no regression on _search_all)."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_page([{"path": "folder/", "type": "folder"}])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    results = client.list_dir("folder/", depth=1)

    assert captured["args"]["operation"] == "listDir"
    assert "fields" not in captured["args"]
    assert len(results) == 1
