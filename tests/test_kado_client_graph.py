#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_client_graph.py — KadoClient.graph(), the per-note kado-graph walk (#82).

Response shape copied from a live call on the test vault (2026-10-27):
{"source": "020 Active MOC.md", "operation": "outgoing",
 "nodes": [{"path": "000 Index.md", "relation": "outgoing"}, ...]}
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.kado_client` works

from lib.kado_client import KadoClient  # noqa: E402


def _make_client() -> KadoClient:
    return KadoClient(base_url="http://localhost:23026", token="test-token")


def test_returns_the_nodes_and_sends_operation_and_path():
    client = _make_client()
    live = {
        "source": "020 Active MOC.md",
        "operation": "outgoing",
        "nodes": [
            {"path": "000 Index.md", "relation": "outgoing"},
            {"path": "021 Fleeting MOC.md", "relation": "outgoing"},
        ],
    }
    with patch.object(client, "_call_tool", return_value=live) as call:
        nodes = client.graph("outgoing", "020 Active MOC.md")
    call.assert_called_once_with("kado-graph", {"operation": "outgoing", "path": "020 Active MOC.md"})
    assert nodes == live["nodes"]


def test_limit_is_sent_only_when_given():
    client = _make_client()
    with patch.object(client, "_call_tool", return_value={"nodes": []}) as call:
        client.graph("related", "a.md", limit=20)
    call.assert_called_once_with("kado-graph", {"operation": "related", "path": "a.md", "limit": 20})


def test_a_response_without_nodes_is_an_empty_list():
    client = _make_client()
    with patch.object(client, "_call_tool", return_value={"source": "a.md", "operation": "dangling"}):
        assert client.graph("dangling", "a.md") == []
