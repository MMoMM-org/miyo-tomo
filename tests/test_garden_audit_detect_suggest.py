#!/usr/bin/env python3
# version: 0.1.0
"""test_garden_audit_detect_suggest.py — bare /garden-audit suggest auto-detection.

garden-audit-detect-suggest.py decides whether a bare /garden-audit should run a suggest
enrichment: it finds the NEWEST inbox garden-audit report and returns its .md path iff
the report has un-run suggestion requests — via the wire's top-level suggest_pending
(editor channel) OR an unfulfilled markdown `- [x] Suggest targets` block (.md-only).
Fail-open: no report / Kado error → nothing (→ fresh audit).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


det = _load("garden_audit_detect_suggest", "garden-audit-detect-suggest.py")

INBOX = "100 Inbox/"


class FakeKado:
    def __init__(self, wires=None, files=None, notes=None, raise_on=None):
        self._wires = wires or []          # search_by_name results
        self._files = files or {}          # path -> bytes
        self._notes = notes or {}          # path -> body str
        self._raise_on = raise_on or set()

    def search_by_name(self, query, limit=500):
        return list(self._wires)

    def read_file_bytes(self, path):
        if path in self._raise_on:
            from lib.kado_client import KadoError
            raise KadoError("boom")
        return self._files[path]

    def read_note(self, path):
        if path in self._raise_on:
            from lib.kado_client import KadoError
            raise KadoError("boom")
        return {"content": self._notes.get(path, ""), "modified": 0}


def _wire_bytes(*, suggest_pending):
    return json.dumps({
        "schema_version": "1", "approved": False,
        "suggest_pending": suggest_pending,
        "findings": [], "emit_digest": "sha256:" + "0" * 64,
    }).encode("utf-8")


def _hit(name, modified):
    return {"path": INBOX + name, "modified": modified}


# ── Wire channel (editor) ─────────────────────────────────────────────────────

def test_wire_suggest_pending_returns_report_path():
    j = INBOX + "2026-07-25_0745_garden-audit.json"
    k = FakeKado(
        wires=[_hit("2026-07-25_0745_garden-audit.json", 100)],
        files={j: _wire_bytes(suggest_pending=True)},
    )
    assert det.detect(k) == INBOX + "2026-07-25_0745_garden-audit.md"


def test_wire_not_pending_and_no_md_tick_returns_none():
    j = INBOX + "2026-07-25_0745_garden-audit.json"
    m = INBOX + "2026-07-25_0745_garden-audit.md"
    k = FakeKado(
        wires=[_hit("2026-07-25_0745_garden-audit.json", 100)],
        files={j: _wire_bytes(suggest_pending=False)},
        notes={m: "### F01 — Dead link\n- [ ] Apply\n- [ ] Suggest targets\n"},
    )
    assert det.detect(k) is None


# ── Markdown channel (.md-only fallback) ──────────────────────────────────────

def test_markdown_unfulfilled_suggest_returns_path():
    j = INBOX + "2026-07-25_0745_garden-audit.json"
    m = INBOX + "2026-07-25_0745_garden-audit.md"
    k = FakeKado(
        wires=[_hit("2026-07-25_0745_garden-audit.json", 100)],
        files={j: _wire_bytes(suggest_pending=False)},
        notes={m: "### F01 — Dead link\n- [x] Suggest targets — tick then run\n"},
    )
    assert det.detect(k) == m


def test_markdown_fulfilled_suggest_returns_none():
    j = INBOX + "2026-07-25_0745_garden-audit.json"
    m = INBOX + "2026-07-25_0745_garden-audit.md"
    body = (
        "### F01 — Dead link\n- [x] Suggest targets — tick then run\n"
        "  Pick one (tick a candidate, or type your own above):\n"
        "  - [ ] [[Cand]] (0.9)\n"
    )
    k = FakeKado(
        wires=[_hit("2026-07-25_0745_garden-audit.json", 100)],
        files={j: _wire_bytes(suggest_pending=False)},
        notes={m: body},
    )
    assert det.detect(k) is None


# ── Newest-wins + fail-open ───────────────────────────────────────────────────

def test_picks_newest_report():
    old = INBOX + "2026-07-24_1055_garden-audit.json"
    new = INBOX + "2026-07-25_0745_garden-audit.json"
    k = FakeKado(
        wires=[_hit("2026-07-24_1055_garden-audit.json", 50),
               _hit("2026-07-25_0745_garden-audit.json", 100)],
        files={old: _wire_bytes(suggest_pending=True),   # old pending — ignored
               new: _wire_bytes(suggest_pending=False)}, # newest wins → not pending
        notes={INBOX + "2026-07-25_0745_garden-audit.md": "no suggest here\n"},
    )
    assert det.detect(k) is None


def test_no_report_returns_none():
    assert det.detect(FakeKado(wires=[])) is None


def test_kado_error_on_wire_falls_back_to_md_then_none():
    j = INBOX + "2026-07-25_0745_garden-audit.json"
    m = INBOX + "2026-07-25_0745_garden-audit.md"
    k = FakeKado(
        wires=[_hit("2026-07-25_0745_garden-audit.json", 100)],
        files={}, notes={m: "no ticks\n"},
        raise_on={j},  # wire read raises → fall through to md → not pending → None
    )
    assert det.detect(k) is None


def test_non_report_json_names_ignored():
    # A byName glob could surface unrelated .json — only *_garden-audit.json count.
    k = FakeKado(wires=[{"path": INBOX + "something-else.json", "modified": 999}])
    assert det.detect(k) is None
