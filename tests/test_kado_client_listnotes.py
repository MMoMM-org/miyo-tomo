#!/usr/bin/env python3
# version: 0.4.0
"""test_kado_client_listnotes.py — Unit tests for KadoClient.list_notes
and KadoClient.read_inline_fields.

Covers T1.1 (F-34 Phase 1): verifies call-shape, pagination, and return
normalisation for the two new KadoClient methods that support MSP
Condition B accumulation. Also the universal ``filter`` pass-through on
list_notes and _search_all (spec 045, ADR-4).

Spec: docs/XDD/specs/015-msp-condition-b-accumulation/
      docs/XDD/specs/045-weekly-monthly-review/ (SDD ADR-4)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.kado_client` works

from lib.kado_client import KadoClient, KadoNotFoundError  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> KadoClient:
    """Return a KadoClient with dummy config (no live server needed)."""
    return KadoClient(base_url="http://localhost:23026", token="test-token")


def _make_search_page(items: list[dict], next_cursor: str | None = None) -> dict:
    """Build a Kado-shape search result page as returned by _call_tool."""
    return {"items": items, "nextCursor": next_cursor}


def _make_rpc_response_ctx(payload: dict) -> MagicMock:
    """Return a urlopen context-manager mock yielding a JSON-RPC-wrapped payload.

    Exercises the real _call_tool → _search_all → SSE/RPC unwrap path, unlike
    the _call_tool-stub tests which never touch the transport.
    """
    rpc = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = rpc
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=resp)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_list_notes_end_to_end_through_transport():
    """list_notes reaches the real transport and parses a listNotes page.

    Patches urlopen (not _call_tool) so a wrong tool-name or broken RPC unwrap
    in the public method would actually fail — covers the wiring the
    _call_tool-stub tests cannot see.
    """
    client = _make_client()
    page = _make_search_page(
        [{"path": "200 Notes/A.md", "tags": ["topic/x"]}], next_cursor=None
    )

    with patch("urllib.request.urlopen", return_value=_make_rpc_response_ctx(page)):
        result = client.list_notes("200 Notes/", fields=["tags"])

    assert result == [{"path": "200 Notes/A.md", "tags": ["topic/x"]}]


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
# filter — Kado's universal filter, passed through verbatim (spec 045, ADR-4)
# ---------------------------------------------------------------------------

_WEEK_FILTER = {"createdAfter": 1774828800000, "createdBefore": 1775433599999}


def test_list_notes_passes_filter_through_on_every_cursor_page():
    """Kado's cursor is a bare offset, so the filter must be repeated per page."""
    client = _make_client()
    seen: list[dict] = []

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        seen.append(arguments)
        if len(seen) == 1:
            return _make_search_page([{"path": "Calendar/a.md"}], next_cursor="c1")
        return _make_search_page([{"path": "Calendar/b.md"}], next_cursor=None)

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    results = client.list_notes("Calendar/", filter=_WEEK_FILTER)

    assert [r["path"] for r in results] == ["Calendar/a.md", "Calendar/b.md"]
    assert len(seen) == 2
    assert seen[0]["filter"] == _WEEK_FILTER
    assert seen[1]["filter"] == _WEEK_FILTER
    assert seen[1]["cursor"] == "c1"
    assert seen[0]["operation"] == "listNotes" and seen[0]["path"] == "Calendar/"


def test_list_notes_omits_filter_when_none():
    """filter=None (default) leaves the request body as before — no filter key."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_page([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.list_notes("200 Notes/")

    assert "filter" not in captured["args"]


def test_search_all_passes_filter_for_any_operation():
    """_search_all accepts filter for every operation, not only listNotes."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_page([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client._search_all("byName", query="Review", filter={"modifiedAfter": 1})

    assert captured["args"]["operation"] == "byName"
    assert captured["args"]["query"] == "Review"
    assert captured["args"]["filter"] == {"modifiedAfter": 1}


def test_list_notes_filter_reaches_the_wire_unchanged():
    """Through the real transport: the filter object is sent verbatim in the JSON-RPC body."""
    client = _make_client()
    page = _make_search_page([], next_cursor=None)

    with patch("urllib.request.urlopen", return_value=_make_rpc_response_ctx(page)) as mock_open:
        client.list_notes("Calendar/", filter=_WEEK_FILTER)

    req = mock_open.call_args.args[0]
    sent = json.loads(req.data.decode("utf-8"))
    assert sent["params"]["arguments"]["filter"] == _WEEK_FILTER


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


# ---------------------------------------------------------------------------
# read_inline_fields — failure path
# ---------------------------------------------------------------------------


def test_read_inline_fields_propagates_KadoNotFoundError():
    """read_inline_fields lets KadoNotFoundError from _call_tool propagate unchanged."""
    client = _make_client()

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        raise KadoNotFoundError("kado-read: path not found: 200 Notes/missing.md")

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    with pytest.raises(KadoNotFoundError) as exc_info:
        client.read_inline_fields("200 Notes/missing.md")

    assert "missing.md" in str(exc_info.value)


# ---------------------------------------------------------------------------
# list_notes — fields persist across all pages during pagination
# ---------------------------------------------------------------------------


def test_list_notes_fields_present_on_every_page():
    """fields= is included in both the first and subsequent page requests."""
    client = _make_client()

    page1_items = [{"path": "200 Notes/a.md", "name": "a"}]
    page2_items = [{"path": "200 Notes/b.md", "name": "b"}]
    captured_pages: list[dict] = []

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured_pages.append(dict(arguments))
        if len(captured_pages) == 1:
            return _make_search_page(page1_items, next_cursor="cursor-xyz")
        return _make_search_page(page2_items, next_cursor=None)

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    results = client.list_notes("200 Notes/", fields=["links"])

    assert len(captured_pages) == 2, "expected two page requests"
    assert captured_pages[0].get("fields") == ["links"], "fields missing on page 1"
    assert captured_pages[1].get("fields") == ["links"], "fields missing on page 2"
    assert len(results) == 2
