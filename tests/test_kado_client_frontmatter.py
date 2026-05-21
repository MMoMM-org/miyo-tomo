#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_client_frontmatter.py — Unit tests for KadoClient.write_frontmatter
and KadoClient.search_by_frontmatter.

Covers T1.3 (F-47 Phase 1): verifies call-shape, error mapping, and return
normalisation for the two new KadoClient methods added to support the F-47
lifecycle state flip hot-path.

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
AC:   AC-2.1 (write_frontmatter call shape), AC-2.2 (search_by_frontmatter call shape)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.kado_client` works

from lib.kado_client import (  # noqa: E402
    KadoConcurrencyError,
    KadoClient,
    KadoToolError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> KadoClient:
    """Return a KadoClient with dummy config (no live server needed)."""
    return KadoClient(base_url="http://localhost:23026", token="test-token")


def _make_search_sse_response(items: list[dict]) -> dict:
    """Build a Kado-shape search result dict (as returned by _call_tool after SSE unwrap)."""
    return {"items": items, "nextCursor": None}


# ---------------------------------------------------------------------------
# write_frontmatter — call shape
# ---------------------------------------------------------------------------


def test_write_frontmatter_merge_mode_call_shape():
    """write_frontmatter sends operation=frontmatter, mode=merge, path, and frontmatter."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["tool"] = tool_name
        captured["args"] = arguments
        return {"path": "100 Inbox/note.md", "modified": 1716300000000}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    result = client.write_frontmatter(
        "100 Inbox/note.md",
        {"tomo": {"state": "approved"}},
        mode="merge",
    )

    assert captured["tool"] == "kado-write"
    assert captured["args"]["operation"] == "frontmatter"
    assert captured["args"]["mode"] == "merge"
    assert captured["args"]["path"] == "100 Inbox/note.md"
    assert captured["args"]["frontmatter"] == {"tomo": {"state": "approved"}}
    assert "expectedModified" not in captured["args"]
    assert result["path"] == "100 Inbox/note.md"


def test_write_frontmatter_replace_mode_call_shape():
    """write_frontmatter sends mode=replace when caller specifies it."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return {"path": "Notes/page.md", "modified": 1716300001000}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.write_frontmatter(
        "Notes/page.md",
        {"title": "New Title"},
        mode="replace",
    )

    assert captured["args"]["mode"] == "replace"
    assert captured["args"]["operation"] == "frontmatter"


def test_write_frontmatter_expected_modified_included_when_provided():
    """write_frontmatter includes expectedModified in the payload when supplied."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return {"path": "100 Inbox/note.md", "modified": 1716300002000}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.write_frontmatter(
        "100 Inbox/note.md",
        {"tomo": {"state": "approved"}},
        expected_modified=1716300000000,
    )

    assert captured["args"]["expectedModified"] == 1716300000000


def test_write_frontmatter_expected_modified_absent_when_not_provided():
    """write_frontmatter omits expectedModified when caller does not supply it."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return {"path": "100 Inbox/note.md", "modified": 1716300003000}

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.write_frontmatter(
        "100 Inbox/note.md",
        {"tomo": {"state": "pending-approval"}},
    )

    assert "expectedModified" not in captured["args"]


# ---------------------------------------------------------------------------
# write_frontmatter — concurrency error mapping
# ---------------------------------------------------------------------------


def test_write_frontmatter_concurrency_error_raises_KadoConcurrencyError():
    """KadoConcurrencyError is raised when Kado signals an expectedModified mismatch."""
    client = _make_client()

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        raise KadoToolError(
            "kado-write returned an error: expectedModified mismatch: "
            "expected 1716300000000, got 1716300001000"
        )

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    with pytest.raises(KadoConcurrencyError) as exc_info:
        client.write_frontmatter(
            "100 Inbox/note.md",
            {"tomo": {"state": "approved"}},
            expected_modified=1716300000000,
        )

    assert "expectedModified" in str(exc_info.value)


def test_write_frontmatter_non_concurrency_tool_error_propagates_as_KadoToolError():
    """Non-concurrency KadoToolError from _call_tool propagates unchanged."""
    client = _make_client()

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        raise KadoToolError("kado-write returned an error: path not allowed")

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    with pytest.raises(KadoToolError) as exc_info:
        client.write_frontmatter("Notes/blocked.md", {"x": 1})

    # Must NOT be promoted to KadoConcurrencyError
    assert type(exc_info.value) is KadoToolError


def test_write_frontmatter_validation_error_mentioning_expectedModified_propagates_as_KadoToolError():
    """KadoToolError whose message mentions 'expectedModified' as a field name (not a
    mismatch) must NOT be promoted to KadoConcurrencyError."""
    client = _make_client()

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        raise KadoToolError(
            "kado-write returned an error: expectedModified must be an integer"
        )

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    with pytest.raises(KadoToolError) as exc_info:
        client.write_frontmatter(
            "100 Inbox/note.md",
            {"tomo": {"state": "approved"}},
            expected_modified=1716300000000,
        )

    # Validation error mentions the field name but NOT "mismatch" —
    # must remain a KadoToolError, not be promoted to KadoConcurrencyError.
    assert type(exc_info.value) is KadoToolError
    assert "expectedModified" in str(exc_info.value)


# ---------------------------------------------------------------------------
# search_by_frontmatter — call shape
# ---------------------------------------------------------------------------


def test_search_by_frontmatter_query_call_shape():
    """search_by_frontmatter sends operation=byFrontmatter and the query string."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["tool"] = tool_name
        captured["args"] = arguments
        return _make_search_sse_response([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.search_by_frontmatter("tomo.state=pending-approval")

    assert captured["tool"] == "kado-search"
    assert captured["args"]["operation"] == "byFrontmatter"
    assert captured["args"]["query"] == "tomo.state=pending-approval"


def test_search_by_frontmatter_default_limit_is_500():
    """search_by_frontmatter sends limit=500 when caller omits the limit."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_sse_response([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.search_by_frontmatter("tomo.state=captured")

    assert captured["args"]["limit"] == 500


def test_search_by_frontmatter_with_path_prefix():
    """search_by_frontmatter passes path_prefix as filter.path."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_sse_response([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.search_by_frontmatter(
        "tomo.state=pending-approval",
        path_prefix="100 Inbox/",
    )

    assert captured["args"].get("filter", {}).get("path") == "100 Inbox/"


def test_search_by_frontmatter_with_modified_after():
    """search_by_frontmatter passes modified_after as filter.modifiedAfter."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_sse_response([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    ts = 1716300000000
    client.search_by_frontmatter(
        "tomo.state=captured",
        modified_after=ts,
    )

    assert captured["args"].get("filter", {}).get("modifiedAfter") == ts


def test_search_by_frontmatter_filter_absent_when_no_options():
    """filter key is absent from the payload when neither path_prefix nor modified_after is supplied."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_sse_response([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.search_by_frontmatter("tomo.state=pending-apply")

    assert "filter" not in captured["args"]


# ---------------------------------------------------------------------------
# search_by_frontmatter — return value normalisation
# ---------------------------------------------------------------------------


def test_search_by_frontmatter_returns_list_of_path_modified_frontmatter():
    """search_by_frontmatter returns list of {path, modified, frontmatter} dicts."""
    client = _make_client()
    raw_items = [
        {
            "path": "100 Inbox/note-a.md",
            "modified": 1716300000001,
            "frontmatter": {"tomo": {"state": "pending-approval"}},
        },
        {
            "path": "100 Inbox/note-b.md",
            "modified": 1716300000002,
            "frontmatter": {"tomo": {"state": "pending-approval"}, "title": "B"},
        },
    ]

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        return _make_search_sse_response(raw_items)

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    results = client.search_by_frontmatter("tomo.state=pending-approval")

    assert len(results) == 2
    assert results[0]["path"] == "100 Inbox/note-a.md"
    assert results[0]["modified"] == 1716300000001
    assert results[0]["frontmatter"] == {"tomo": {"state": "pending-approval"}}
    assert results[1]["path"] == "100 Inbox/note-b.md"
    assert results[1]["frontmatter"]["title"] == "B"


def test_search_by_frontmatter_returns_empty_list_when_no_matches():
    """search_by_frontmatter returns an empty list when Kado returns no items."""
    client = _make_client()

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        return _make_search_sse_response([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    results = client.search_by_frontmatter("tomo.state=approved")

    assert results == []


def test_search_by_frontmatter_path_prefix_and_modified_after_combined():
    """Both filter.path and filter.modifiedAfter appear when both options are supplied."""
    client = _make_client()
    captured = {}

    def fake_call_tool(tool_name: str, arguments: dict) -> dict:
        captured["args"] = arguments
        return _make_search_sse_response([])

    client._call_tool = fake_call_tool  # type: ignore[method-assign]

    client.search_by_frontmatter(
        "tomo.state=pending-apply",
        path_prefix="200 Notes/",
        modified_after=1716200000000,
    )

    filt = captured["args"].get("filter", {})
    assert filt.get("path") == "200 Notes/"
    assert filt.get("modifiedAfter") == 1716200000000


# ---------------------------------------------------------------------------
# KadoConcurrencyError — inheritance
# ---------------------------------------------------------------------------


def test_KadoConcurrencyError_is_subclass_of_KadoToolError():
    """KadoConcurrencyError must inherit from KadoToolError for catch-all handling."""
    assert issubclass(KadoConcurrencyError, KadoToolError)
