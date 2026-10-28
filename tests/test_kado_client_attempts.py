#!/usr/bin/env python3
# version: 0.1.0
"""test_kado_client_attempts.py — attempt budget, gate and pacing in KadoClient._call_tool.

Spec: docs/XDD/specs/042-moc-propose-link-members/ (PRD F5-AC2, F5-AC3; SDD ADR-4)
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

from lib.kado_client import KadoBudgetExhausted, KadoClient, KadoError  # noqa: E402


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


def _429() -> urllib.error.HTTPError:
    h = HTTPMessage()
    h["Retry-After"] = "0"
    return urllib.error.HTTPError("http://x/mcp", 429, "Too Many", h, io.BytesIO(b""))


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
