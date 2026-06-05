#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_client_retry.py — Unit tests for HTTP retry-with-backoff in KadoClient._call_tool.

Covers F-34 rate-limit resilience: _call_tool retries on HTTP 429/503 using
exponential backoff, honors the Retry-After header, and raises immediately on
non-retryable codes (401, 403, 404).

Spec: docs/XDD/specs/015-msp-condition-b-accumulation/
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from http.client import HTTPMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.kado_client` works

from lib.kado_client import (  # noqa: E402
    KadoAuthError,
    KadoClient,
    KadoError,
    KadoNotFoundError,
    _retry_delay,
    _RETRY_BACKOFF_BASE,
    _RETRY_BACKOFF_CAP,
    _MAX_RETRIES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> KadoClient:
    """Return a KadoClient with dummy config (no live server needed)."""
    return KadoClient(base_url="http://localhost:23026", token="test-token")


def _make_success_response(payload: dict | None = None) -> MagicMock:
    """Return a context-manager mock that yields a response with valid JSON-RPC bytes."""
    if payload is None:
        payload = {"key": "value"}

    rpc_response = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": json.dumps(payload)}],
        },
    }).encode("utf-8")

    resp_mock = MagicMock()
    resp_mock.read.return_value = rpc_response
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=resp_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    """Build an HTTPError with optional Retry-After header."""
    headers = HTTPMessage()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        url="http://localhost:23026/mcp",
        code=code,
        msg="Mock HTTP error",
        hdrs=headers,
        fp=io.BytesIO(b""),
    )


# ---------------------------------------------------------------------------
# _retry_delay — unit tests
# ---------------------------------------------------------------------------


def test_retry_delay_uses_backoff_when_no_header():
    """Without Retry-After, delay grows exponentially from base, capped at max."""
    exc = _make_http_error(429)
    delay0 = _retry_delay(exc, 0)
    delay1 = _retry_delay(exc, 1)
    delay2 = _retry_delay(exc, 2)

    assert delay0 == min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 0))
    assert delay1 == min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 1))
    assert delay2 == min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 2))
    # Each delay strictly larger than the previous (before cap)
    assert delay1 > delay0
    assert delay2 > delay1


def test_retry_delay_capped_at_max():
    """Backoff never exceeds _RETRY_BACKOFF_CAP regardless of attempt number."""
    exc = _make_http_error(429)
    delay_high = _retry_delay(exc, 100)  # attempt so high it would overflow without cap
    assert delay_high == _RETRY_BACKOFF_CAP


def test_retry_delay_honors_retry_after_header():
    """When Retry-After is present and numeric, returns that integer value."""
    exc = _make_http_error(429, retry_after="7")
    assert _retry_delay(exc, 0) == 7


def test_retry_delay_ignores_non_numeric_retry_after():
    """Non-numeric Retry-After (e.g. HTTP-date) falls back to exponential backoff."""
    exc = _make_http_error(429, retry_after="Wed, 21 Oct 2099 07:28:00 GMT")
    delay = _retry_delay(exc, 0)
    assert delay == min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 0))


# ---------------------------------------------------------------------------
# _call_tool — retry behavior
# ---------------------------------------------------------------------------


def test_429_then_success():
    """429 twice then success: _call_tool returns parsed result; time.sleep called twice."""
    client = _make_client()
    success_ctx = _make_success_response({"key": "value"})

    side_effects = [
        _make_http_error(429),
        _make_http_error(429),
        success_ctx,
    ]

    with patch("urllib.request.urlopen", side_effect=side_effects) as mock_open, \
         patch("time.sleep") as mock_sleep:
        result = client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    assert result == {"key": "value"}
    assert mock_sleep.call_count == 2
    assert mock_open.call_count == 3


def test_429_exhausted_raises():
    """429 every time: raises KadoError after exhausting retries; time.sleep called _MAX_RETRIES times."""
    client = _make_client()

    with patch("urllib.request.urlopen", side_effect=_make_http_error(429)) as mock_open, \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(KadoError) as exc_info:
            client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    assert "429" in str(exc_info.value)
    assert "retries" in str(exc_info.value).lower()
    assert mock_sleep.call_count == _MAX_RETRIES
    assert mock_open.call_count == _MAX_RETRIES + 1


def test_503_then_success():
    """503 once then success: _call_tool retries on 503; time.sleep called once."""
    client = _make_client()
    success_ctx = _make_success_response({"data": "ok"})

    with patch("urllib.request.urlopen", side_effect=[_make_http_error(503), success_ctx]), \
         patch("time.sleep") as mock_sleep:
        result = client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    assert result == {"data": "ok"}
    assert mock_sleep.call_count == 1


def test_retry_after_header_honored():
    """429 with Retry-After: 2 then success: time.sleep called with 2."""
    client = _make_client()
    success_ctx = _make_success_response()

    with patch("urllib.request.urlopen", side_effect=[_make_http_error(429, retry_after="2"), success_ctx]), \
         patch("time.sleep") as mock_sleep:
        client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    mock_sleep.assert_called_once_with(2)


def test_401_no_retry():
    """401 raises KadoAuthError immediately; time.sleep NOT called."""
    client = _make_client()

    with patch("urllib.request.urlopen", side_effect=_make_http_error(401)), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(KadoAuthError):
            client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    mock_sleep.assert_not_called()


def test_403_no_retry():
    """403 raises KadoAuthError immediately; time.sleep NOT called."""
    client = _make_client()

    with patch("urllib.request.urlopen", side_effect=_make_http_error(403)), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(KadoAuthError):
            client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    mock_sleep.assert_not_called()


def test_404_no_retry():
    """404 raises KadoNotFoundError immediately; time.sleep NOT called."""
    client = _make_client()

    with patch("urllib.request.urlopen", side_effect=_make_http_error(404)), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(KadoNotFoundError):
            client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    mock_sleep.assert_not_called()


def test_500_no_retry():
    """500 raises KadoError immediately (not retryable); time.sleep NOT called."""
    client = _make_client()

    with patch("urllib.request.urlopen", side_effect=_make_http_error(500)), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(KadoError) as exc_info:
            client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    assert "500" in str(exc_info.value)
    assert "retries" not in str(exc_info.value).lower()
    mock_sleep.assert_not_called()


def test_retry_sleep_uses_backoff_delay():
    """Without Retry-After, sleep delay follows exponential backoff sequence."""
    client = _make_client()
    success_ctx = _make_success_response()

    with patch("urllib.request.urlopen", side_effect=[_make_http_error(429), success_ctx]), \
         patch("time.sleep") as mock_sleep:
        client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    expected_delay = min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 0))
    mock_sleep.assert_called_once_with(expected_delay)
