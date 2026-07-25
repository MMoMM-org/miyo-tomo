#!/usr/bin/env python3
# version: 0.2.0
"""test_kado_client_graph_audit.py — Unit tests for KadoClient.graph_audit().

Covers the cursor-paginated vault-wide link audit wrapper.
Spec: docs/XDD/specs/030-garden-audit/
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import call, patch

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


def _audit_response(
    orphans: list,
    dead_links: list,
    total: dict,
    cursor: str | None = None,
    truncated: bool = False,
) -> dict:
    """Build a real-shaped kado-graph-audit response fixture."""
    return {
        "operation": "audit-graph",
        "orphans": orphans,
        "deadLinks": dead_links,  # NB: camelCase as Kado emits it
        "total": total,
        "cursor": cursor,
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# Single-page: cursor null, all items returned in one call
# ---------------------------------------------------------------------------


def test_single_page_returns_all_items():
    """A single-page response (cursor: null) returns all orphans and deadLinks."""
    client = _make_client()

    page = _audit_response(
        orphans=[{"path": "Notes/Orphan.md"}],
        dead_links=[{"source": "Notes/Bar.md", "target": "Missing Note", "count": 2}],
        total={"orphans": 1, "deadLinks": 1},
        cursor=None,
    )

    with patch.object(client, "_call_tool", return_value=page) as mock_call:
        result = client.graph_audit()

    mock_call.assert_called_once_with("kado-graph-audit", {})
    assert result["orphans"] == [{"path": "Notes/Orphan.md"}]
    assert result["deadLinks"] == [{"source": "Notes/Bar.md", "target": "Missing Note", "count": 2}]
    assert result["total"] == {"orphans": 1, "deadLinks": 1}


# ---------------------------------------------------------------------------
# Pagination: cursor loop concatenates orphans-first-then-deadLinks across pages
# ---------------------------------------------------------------------------


def test_cursor_pagination_concatenates_across_pages():
    """Two pages concatenate: orphans from p1 before orphans from p2, same for deadLinks."""
    client = _make_client()

    page1 = _audit_response(
        orphans=[{"path": "Notes/Orphan1.md"}],
        dead_links=[{"source": "A.md", "target": "Missing1", "count": 1}],
        total={"orphans": 12, "deadLinks": 47},
        cursor="cursor-token-abc",
        truncated=True,
    )
    page2 = _audit_response(
        orphans=[{"path": "Notes/Orphan2.md"}],
        dead_links=[{"source": "B.md", "target": "Missing2", "count": 3}],
        total={"orphans": 12, "deadLinks": 47},
        cursor=None,
        truncated=False,
    )

    with patch.object(client, "_call_tool", side_effect=[page1, page2]) as mock_call:
        result = client.graph_audit()

    # Two pages fetched
    assert mock_call.call_count == 2
    # First call: no cursor
    assert mock_call.call_args_list[0] == call("kado-graph-audit", {})
    # Second call: cursor from page 1
    assert mock_call.call_args_list[1] == call("kado-graph-audit", {"cursor": "cursor-token-abc"})

    # Concatenation: p1 orphans first, then p2 orphans
    assert result["orphans"] == [
        {"path": "Notes/Orphan1.md"},
        {"path": "Notes/Orphan2.md"},
    ]
    # Concatenation: p1 deadLinks first, then p2 deadLinks
    assert result["deadLinks"] == [
        {"source": "A.md", "target": "Missing1", "count": 1},
        {"source": "B.md", "target": "Missing2", "count": 3},
    ]
    assert result["total"] == {"orphans": 12, "deadLinks": 47}


def test_three_pages_concatenated():
    """Three pages are fully concatenated — loop continues until cursor is null."""
    client = _make_client()

    pages = [
        _audit_response(
            orphans=[{"path": f"Notes/O{i}.md"}],
            dead_links=[{"source": f"S{i}.md", "target": f"T{i}", "count": i}],
            total={"orphans": 3, "deadLinks": 3},
            cursor=f"cursor-{i}" if i < 2 else None,
        )
        for i in range(3)
    ]

    with patch.object(client, "_call_tool", side_effect=pages) as mock_call:
        result = client.graph_audit()

    assert mock_call.call_count == 3
    assert len(result["orphans"]) == 3
    assert len(result["deadLinks"]) == 3


# ---------------------------------------------------------------------------
# include / limit passthrough — keys omitted when None
# ---------------------------------------------------------------------------


def test_include_passed_when_provided():
    """include kwarg is forwarded into tool args when not None."""
    client = _make_client()
    page = _audit_response(orphans=[], dead_links=[], total={}, cursor=None)

    with patch.object(client, "_call_tool", return_value=page) as mock_call:
        client.graph_audit(include=["orphans"])

    mock_call.assert_called_once_with("kado-graph-audit", {"include": ["orphans"]})


def test_limit_passed_when_provided():
    """limit kwarg is forwarded into tool args when not None."""
    client = _make_client()
    page = _audit_response(orphans=[], dead_links=[], total={}, cursor=None)

    with patch.object(client, "_call_tool", return_value=page) as mock_call:
        client.graph_audit(limit=50)

    mock_call.assert_called_once_with("kado-graph-audit", {"limit": 50})


def test_include_and_limit_both_passed():
    """include and limit together both appear in tool args."""
    client = _make_client()
    page = _audit_response(orphans=[], dead_links=[], total={}, cursor=None)

    with patch.object(client, "_call_tool", return_value=page) as mock_call:
        client.graph_audit(include=["deadLinks"], limit=100)

    mock_call.assert_called_once_with(
        "kado-graph-audit", {"include": ["deadLinks"], "limit": 100}
    )


def test_include_none_omitted_from_args():
    """include=None must NOT appear in tool args (default case)."""
    client = _make_client()
    page = _audit_response(orphans=[], dead_links=[], total={}, cursor=None)

    with patch.object(client, "_call_tool", return_value=page) as mock_call:
        client.graph_audit(include=None)

    args_sent = mock_call.call_args[0][1]
    assert "include" not in args_sent


def test_limit_none_omitted_from_args():
    """limit=None must NOT appear in tool args (default case)."""
    client = _make_client()
    page = _audit_response(orphans=[], dead_links=[], total={}, cursor=None)

    with patch.object(client, "_call_tool", return_value=page) as mock_call:
        client.graph_audit(limit=None)

    args_sent = mock_call.call_args[0][1]
    assert "limit" not in args_sent


def test_cursor_forwarded_on_subsequent_pages():
    """On page 2+, cursor is included in args alongside include and limit."""
    client = _make_client()
    # page1 must have at least one item so the secondary guard doesn't exit early
    page1 = _audit_response(
        orphans=[{"path": "Notes/X.md"}], dead_links=[], total={}, cursor="tok123", truncated=True
    )
    page2 = _audit_response(orphans=[], dead_links=[], total={}, cursor=None)

    with patch.object(client, "_call_tool", side_effect=[page1, page2]) as mock_call:
        client.graph_audit(include=["orphans"], limit=20)

    assert mock_call.call_args_list[0] == call(
        "kado-graph-audit", {"include": ["orphans"], "limit": 20}
    )
    assert mock_call.call_args_list[1] == call(
        "kado-graph-audit", {"include": ["orphans"], "limit": 20, "cursor": "tok123"}
    )


# ---------------------------------------------------------------------------
# camelCase deadLinks — NOT snake_case
# ---------------------------------------------------------------------------


def test_camelcase_dead_links_read_correctly():
    """deadLinks (camelCase) from Kado response is read — snake_case dead_links would miss it."""
    client = _make_client()

    # Simulate a response that only has camelCase "deadLinks"
    raw_response = {
        "operation": "audit-graph",
        "orphans": [],
        "deadLinks": [{"source": "X.md", "target": "Y", "count": 5}],
        "total": {"orphans": 0, "deadLinks": 1},
        "cursor": None,
        "truncated": False,
    }

    with patch.object(client, "_call_tool", return_value=raw_response):
        result = client.graph_audit()

    # Must read camelCase deadLinks — not an empty list
    assert result["deadLinks"] == [{"source": "X.md", "target": "Y", "count": 5}]


# ---------------------------------------------------------------------------
# Infinite-loop guard — exit when both arrays empty despite non-null cursor
# ---------------------------------------------------------------------------


def test_loop_exits_when_both_arrays_empty_despite_cursor():
    """Loop must terminate when a page returns empty orphans AND empty deadLinks,
    even if the server returns a non-null cursor (server-bug / partial-failure guard).
    Mirrors the _search_all `or not page_items` secondary break condition."""
    client = _make_client()

    # Both pages carry a non-None cursor but yield no items — without the
    # secondary guard the loop would spin forever.
    page1 = _audit_response(orphans=[], dead_links=[], total={}, cursor="cursor-evil", truncated=True)
    page2 = _audit_response(orphans=[], dead_links=[], total={}, cursor="cursor-evil2", truncated=True)

    with patch.object(client, "_call_tool", side_effect=[page1, page2]) as mock_call:
        result = client.graph_audit()

    # Must have stopped after the first empty page (call_count == 1)
    assert mock_call.call_count == 1
    assert result["orphans"] == []
    assert result["deadLinks"] == []


# ---------------------------------------------------------------------------
# Empty response — both arrays empty
# ---------------------------------------------------------------------------


def test_empty_response_returns_empty_arrays():
    """An empty vault audit returns empty orphans and deadLinks lists."""
    client = _make_client()
    page = _audit_response(orphans=[], dead_links=[], total={"orphans": 0, "deadLinks": 0}, cursor=None)

    with patch.object(client, "_call_tool", return_value=page):
        result = client.graph_audit()

    assert result["orphans"] == []
    assert result["deadLinks"] == []
    assert result["total"] == {"orphans": 0, "deadLinks": 0}


def test_missing_orphans_key_defaults_to_empty():
    """If 'orphans' key is absent from response, default to empty list (not KeyError)."""
    client = _make_client()
    sparse_response = {
        "operation": "audit-graph",
        "deadLinks": [],
        "total": {},
        "cursor": None,
    }

    with patch.object(client, "_call_tool", return_value=sparse_response):
        result = client.graph_audit()

    assert result["orphans"] == []


def test_missing_deadlinks_key_defaults_to_empty():
    """If 'deadLinks' key is absent from response, default to empty list (not KeyError)."""
    client = _make_client()
    sparse_response = {
        "operation": "audit-graph",
        "orphans": [],
        "total": {},
        "cursor": None,
    }

    with patch.object(client, "_call_tool", return_value=sparse_response):
        result = client.graph_audit()

    assert result["deadLinks"] == []
