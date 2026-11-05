#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_client_transport_errors.py — KadoClient._call_tool wraps transport errors.

A timeout or reset while the response is read (TimeoutError,
ConnectionResetError: OSError) and a truncated body (http.client.IncompleteRead:
HTTPException, not OSError) must reach callers as KadoConnectionError, chained
to the original, so every `except KadoError` handles them. HTTPError keeps its
own mapping, and none of these is retried.

Spec: docs/XDD/specs/044-note-from-template/ (issue #169)
"""
from __future__ import annotations

import http.client
import sys
import urllib.error
from http.client import HTTPMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tomo" / "scripts"))

from lib.kado_client import (  # noqa: E402
    KadoAuthError, KadoClient, KadoConnectionError, KadoError,
)


def _client() -> KadoClient:
    return KadoClient(base_url="http://localhost:23026", token="test-token")


def _response_whose_read_raises(exc: BaseException) -> MagicMock:
    resp = MagicMock()
    resp.read.side_effect = exc
    ctx = MagicMock()
    ctx.__enter__.return_value = resp
    ctx.__exit__.return_value = False
    return ctx


TRANSPORT_ERRORS = [
    TimeoutError("timed out"),
    ConnectionResetError("Connection reset by peer"),
    http.client.IncompleteRead(b"{\"jsonrpc\"", 100),
]


@pytest.mark.parametrize("error", TRANSPORT_ERRORS, ids=lambda e: type(e).__name__)
def test_read_error_becomes_kado_connection_error(error):
    with patch("lib.kado_client.urllib.request.urlopen",
               return_value=_response_whose_read_raises(error)) as urlopen:
        with pytest.raises(KadoConnectionError) as info:
            _client().read_note("Inbox/x.md")
    assert info.value.__cause__ is error
    assert isinstance(info.value, KadoError)
    assert urlopen.call_count == 1


@pytest.mark.parametrize("error", TRANSPORT_ERRORS, ids=lambda e: type(e).__name__)
def test_urlopen_error_becomes_kado_connection_error(error):
    with patch("lib.kado_client.urllib.request.urlopen", side_effect=error) as urlopen:
        with pytest.raises(KadoConnectionError) as info:
            _client().path_exists("Inbox/x.md")
    assert info.value.__cause__ is error
    assert urlopen.call_count == 1


def test_http_error_keeps_its_own_mapping():
    error = urllib.error.HTTPError("http://localhost:23026/mcp", 401, "Unauthorized",
                                   HTTPMessage(), None)
    with patch("lib.kado_client.urllib.request.urlopen", side_effect=error):
        with pytest.raises(KadoAuthError):
            _client().read_note("Inbox/x.md")
