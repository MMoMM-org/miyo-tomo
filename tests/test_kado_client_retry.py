#!/usr/bin/env python3
# version: 0.3.0
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
    _RETRY_AFTER_CAP,
    _RETRY_BACKOFF_BASE,
    _RETRY_BACKOFF_CAP,
    _MAX_RETRIES,
)

# Backoff is jittered (×[0.5, 1.0]); patch random.uniform→1.0 to make the
# exponential sequence deterministic for exact-value assertions.
_NO_JITTER = patch("lib.kado_client.random.uniform", return_value=1.0)


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
    with _NO_JITTER:
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
    with _NO_JITTER:
        delay_high = _retry_delay(exc, 100)  # attempt so high it would overflow without cap
    assert delay_high == _RETRY_BACKOFF_CAP


def test_retry_delay_jitter_within_bounds():
    """Jittered backoff stays within [0.5×base, base] — never 0, never above cap."""
    exc = _make_http_error(429)
    base = min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 1))
    for _ in range(50):
        delay = _retry_delay(exc, 1)  # real random, no patch
        assert 0.5 * base <= delay <= base


def test_retry_delay_honors_retry_after_header():
    """When Retry-After is present and numeric, returns that value (no jitter)."""
    exc = _make_http_error(429, retry_after="7")
    assert _retry_delay(exc, 0) == 7


def test_retry_delay_clamps_retry_after_to_cap():
    """A large Retry-After is clamped to _RETRY_AFTER_CAP — no arbitrary stall."""
    exc = _make_http_error(429, retry_after="3600")
    assert _retry_delay(exc, 0) == _RETRY_AFTER_CAP


def test_retry_delay_ignores_non_numeric_retry_after():
    """Non-numeric Retry-After (e.g. HTTP-date) falls back to exponential backoff."""
    exc = _make_http_error(429, retry_after="Wed, 21 Oct 2099 07:28:00 GMT")
    with _NO_JITTER:
        delay = _retry_delay(exc, 0)
    assert delay == min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 0))


def test_retry_delay_clamps_negative_retry_after():
    """Retry-After: -1 is clamped to 0 — a negative sleep would raise ValueError."""
    exc = _make_http_error(429, retry_after="-1")
    assert _retry_delay(exc, 0) == 0


def test_retry_delay_clamps_zero_retry_after():
    """Retry-After: 0 is accepted as-is (0 seconds — retry immediately)."""
    exc = _make_http_error(429, retry_after="0")
    assert _retry_delay(exc, 0) == 0


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
         _NO_JITTER, \
         patch("time.sleep") as mock_sleep:
        client._call_tool("kado-read", {"operation": "note", "path": "foo.md"})

    expected_delay = min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 0))
    mock_sleep.assert_called_once_with(expected_delay)


def test_retry_through_public_read_note():
    """End-to-end: a public method (read_note) retries 429 then parses the result.

    Guards the public-API → _call_tool wiring, not just the private helper.
    """
    client = _make_client()
    note_payload = {"content": "# Hello", "modified": 1}
    success_ctx = _make_success_response(note_payload)

    with patch("urllib.request.urlopen", side_effect=[_make_http_error(429), success_ctx]), \
         _NO_JITTER, \
         patch("time.sleep") as mock_sleep:
        result = client.read_note("foo.md")

    assert result == note_payload
    assert mock_sleep.call_count == 1


# ---------------------------------------------------------------------------
# note_exists — partial-read existence probe (issue #61)
# ---------------------------------------------------------------------------


def test_note_exists_sends_firstxchars_limit_one():
    """The probe must request a 1-char partial read, not a full body."""
    client = _make_client()
    with patch.object(client, "_call_tool", return_value={"content": "x"}) as mock_call:
        assert client.note_exists("Calendar/2026-04-29.md") is True

    mock_call.assert_called_once_with(
        "kado-read",
        {
            "operation": "note",
            "path": "Calendar/2026-04-29.md",
            "mode": "firstXChars",
            "limit": 1,
        },
    )


def test_note_exists_false_on_not_found():
    """A definitive NOT_FOUND maps to False — the absence signal."""
    client = _make_client()
    with patch.object(client, "_call_tool", side_effect=KadoNotFoundError("missing")):
        assert client.note_exists("Calendar/missing.md") is False


def test_note_exists_propagates_other_errors():
    """Transport/validation errors propagate — the caller owns fail-open policy."""
    client = _make_client()
    with patch.object(client, "_call_tool", side_effect=KadoError("boom")):
        with pytest.raises(KadoError):
            client.note_exists("Calendar/2026-04-29.md")


def test_plain_read_note_omits_partial_params():
    """A full read must not leak mode/limit into the payload (backward compat)."""
    client = _make_client()
    with patch.object(client, "_call_tool", return_value={"content": "body"}) as mock_call:
        client.read_note("foo.md")

    mock_call.assert_called_once_with(
        "kado-read", {"operation": "note", "path": "foo.md"}
    )
