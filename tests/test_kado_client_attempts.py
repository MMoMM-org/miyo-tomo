#!/usr/bin/env python3
# version: 0.2.0
"""test_kado_client_attempts.py — attempt budget, gate, pacing and wait accounting in KadoClient._call_tool.

Spec: docs/XDD/specs/042-moc-propose-link-members/ (PRD F5-AC2, F5-AC3; SDD ADR-4)
      docs/XDD/specs/045-weekly-monthly-review/ (PRD F3-AC11, F3-AC12; SDD ADR-4) — wait counters
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tomo" / "scripts"))

from lib.kado_client import (  # noqa: E402
    _MAX_RETRIES,
    _RETRY_BACKOFF_BASE,
    _RETRY_BACKOFF_CAP,
    KadoBudgetExhausted,
    KadoClient,
    KadoError,
)


def _client(**kw) -> KadoClient:
    return KadoClient(base_url="http://localhost:23026", token="t", **kw)


def _ok() -> MagicMock:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps({"k": "v"})}]},
    }).encode()
    resp = MagicMock()
    resp.read.return_value = body
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=resp)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _429(retry_after: str = "0") -> urllib.error.HTTPError:
    h = HTTPMessage()
    h["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x/mcp", 429, "Too Many", h, io.BytesIO(b""))


def _503() -> urllib.error.HTTPError:
    # Kado's "Server busy" 503 carries no Retry-After; the client backs off.
    return urllib.error.HTTPError("http://x/mcp", 503, "Busy", HTTPMessage(), io.BytesIO(b""))


def test_retries_count_as_attempts_but_one_call():
    c = _client()
    with patch("lib.kado_client.urllib.request.urlopen",
               side_effect=[_429(), _429(), _ok()]) as op, \
            patch("lib.kado_client.time.sleep"):
        c._call_tool("kado-read", {})
    assert c.attempt_count == 3
    assert c.call_count == 1
    assert op.call_count == 3


def test_gate_false_before_retry_stops_further_sends():
    c = _client()
    answers = iter([True, False])
    c.attempt_gate = lambda: next(answers)
    with patch("lib.kado_client.urllib.request.urlopen",
               side_effect=[_429(), _ok()]) as op, \
            patch("lib.kado_client.time.sleep"):
        with pytest.raises(KadoBudgetExhausted):
            c._call_tool("kado-read", {})
    assert op.call_count == 1
    assert c.attempt_count == 1  # the refused retry is not an attempt


def test_gate_false_before_first_send_sends_nothing():
    c = _client()
    c.attempt_gate = lambda: False
    with patch("lib.kado_client.urllib.request.urlopen") as op:
        with pytest.raises(KadoBudgetExhausted):
            c._call_tool("kado-read", {})
    assert op.call_count == 0
    assert c.attempt_count == 0


def test_budget_exhausted_is_a_kado_error():
    assert issubclass(KadoBudgetExhausted, KadoError)


def test_min_interval_sleeps_the_difference_between_sends():
    c = _client(min_interval=0.3)
    now = [100.0]
    slept: list[float] = []

    def fake_sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    with patch("lib.kado_client.urllib.request.urlopen", side_effect=[_ok(), _ok()]), \
            patch("lib.kado_client.time.monotonic", side_effect=lambda: now[0]), \
            patch("lib.kado_client.time.sleep", side_effect=fake_sleep):
        c._call_tool("kado-read", {})
        now[0] += 0.1  # only 0.1 s pass before the next call
        c._call_tool("kado-read", {})
    assert slept == [pytest.approx(0.2)]


def test_defaults_do_not_sleep_or_gate():
    c = _client()
    assert c.attempt_gate is None and c.min_interval == 0.0
    with patch("lib.kado_client.urllib.request.urlopen", side_effect=[_ok(), _ok()]), \
            patch("lib.kado_client.time.sleep") as sl:
        c._call_tool("kado-read", {})
        c._call_tool("kado-read", {})
    sl.assert_not_called()
    assert c.attempt_count == 2


# ---------------------------------------------------------------------------
# Wait accounting — retry_wait_s and pace_wait_s (spec 045, ADR-4)
# ---------------------------------------------------------------------------


def test_wait_counters_start_at_zero():
    c = _client()
    assert c.retry_wait_s == 0.0
    assert c.pace_wait_s == 0.0


def test_pace_wait_s_accumulates_pacing_sleeps_only():
    """Every sleep _pace makes lands in pace_wait_s; retry_wait_s stays 0 without retries."""
    c = _client(min_interval=0.3)
    now = [100.0]

    def fake_sleep(s: float) -> None:
        now[0] += s

    with patch("lib.kado_client.urllib.request.urlopen", side_effect=[_ok(), _ok(), _ok()]), \
            patch("lib.kado_client.time.monotonic", side_effect=lambda: now[0]), \
            patch("lib.kado_client.time.sleep", side_effect=fake_sleep):
        c._call_tool("kado-read", {})
        now[0] += 0.1  # 0.1 s pass → 0.2 s of pacing
        c._call_tool("kado-read", {})
        now[0] += 0.25  # 0.25 s pass → 0.05 s of pacing
        c._call_tool("kado-read", {})
    assert c.pace_wait_s == pytest.approx(0.25)
    assert c.retry_wait_s == 0.0


def test_retry_wait_s_honours_retry_after_on_429_and_backoff_on_503():
    """retry_wait_s sums exactly what the retry loop hands to time.sleep.

    A 429 contributes its Retry-After value; a 503 (no header) contributes the
    jitter-free backoff for its attempt index (the second retry → base × 2¹).
    Pacing is off, so pace_wait_s stays 0.
    """
    c = _client()
    slept: list[float] = []
    with patch("lib.kado_client.urllib.request.urlopen",
               side_effect=[_429("2"), _503(), _ok()]), \
            patch("lib.kado_client.random.uniform", return_value=1.0), \
            patch("lib.kado_client.time.sleep", side_effect=slept.append):
        c._call_tool("kado-read", {})
    expected_backoff = min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** 1))
    assert slept == [2.0, expected_backoff]
    assert c.retry_wait_s == pytest.approx(2.0 + expected_backoff)
    assert c.pace_wait_s == 0.0
    assert c.attempt_count - c.call_count == 2  # retries are derived, not stored


def test_retry_wait_s_keeps_growing_when_the_retries_are_exhausted():
    """An exhausted chain still accounts every sleep it made before raising."""
    c = _client()
    with patch("lib.kado_client.urllib.request.urlopen", side_effect=_429("1")), \
            patch("lib.kado_client.time.sleep"):
        with pytest.raises(KadoError):
            c._call_tool("kado-read", {})
    assert c.retry_wait_s == pytest.approx(float(_MAX_RETRIES))


def test_wait_counters_accumulate_across_calls_and_kinds():
    """Both counters are run totals: pacing and retry waits from several calls add up separately."""
    c = _client(min_interval=0.5)
    now = [10.0]

    def fake_sleep(s: float) -> None:
        now[0] += s

    with patch("lib.kado_client.urllib.request.urlopen",
               side_effect=[_ok(), _429("3"), _ok(), _ok()]), \
            patch("lib.kado_client.time.monotonic", side_effect=lambda: now[0]), \
            patch("lib.kado_client.time.sleep", side_effect=fake_sleep):
        c._call_tool("kado-read", {})      # first send: no pacing
        c._call_tool("kado-read", {})      # paced 0.5; 429 → retry sleep 3 (> interval, so no pacing)
        c._call_tool("kado-read", {})      # paced 0.5
    assert c.retry_wait_s == pytest.approx(3.0)
    assert c.pace_wait_s == pytest.approx(1.0)  # the retry's own sleep is never double-counted as pacing
