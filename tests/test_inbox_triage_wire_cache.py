#!/usr/bin/env python3
# version: 0.1.0
"""test_inbox_triage_wire_cache.py — an unreadable wire sibling must not
silently degrade a Hashi-edited doc to the markdown path.

Defect (found during spec 038 T5.3 live validation, 2026-10-10 — NOT the
cause of that run's own failure, which was an unticked Approved box that
never reached this code at all): `inbox-triage.py`'s `_cache_wire_sibling`
caught the BASE `KadoError`, so a genuinely absent sibling (KadoNotFoundError)
and a permission refusal / validation error / connection failure (KadoToolError,
KadoConnectionError, ...) collapsed to the same `None` — read by the caller as
"no sibling, fall back to markdown". For a Hashi user the markdown is stale by
construction, so that fallback silently applies decisions the user never made.

Covers two scripts:
  - inbox-triage.py's _cache_wire_sibling / read_approval_state: the catch is
    narrowed to KadoNotFoundError only; every other KadoError now makes the
    doc excluded from Pass 2 (warn + drift indicator + skip), rather than
    silently falling back.
  - suggestion-parser.py's load_changed_wire: the "unchanged wire" return-None
    route now logs a line on stderr, symmetric with the positive "edited wire
    is authoritative" line, so an owner can tell "nothing changed in the
    editor" apart from "my edit never reached the parser".

See docs/tomo/scripts/inbox-triage.md and docs/tomo/scripts/suggestion-parser.md
for the WHY. Mock-at-the-orchestrator throughout: a fake Kado client drives
read_approval_state directly; no live Kado, no container, no vault.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import (  # noqa: E402
    KadoConnectionError,
    KadoNotFoundError,
    KadoToolError,
)


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_triage = _load("inbox_triage_wire_cache", "inbox-triage.py")
_parser_mod = _load("suggestion_parser_wire_cache", "suggestion-parser.py")
_render_mod = _load("suggestions_render_wire_cache", "suggestions-render.py")


# ---------------------------------------------------------------------------
# inbox-triage.py — read_approval_state / _cache_wire_sibling
# ---------------------------------------------------------------------------

DOC_PATH = "100 Inbox/2026-10-10_1000_suggestions.md"
APPROVED_BODY = "- [x] Approved\n\n## Summary\n\n- Items processed: 0\n"

_STATE_KEYS = (
    "approved_suggestions", "approved_fan", "approved_moc_proposals",
    "approved_garden_audits", "force_atomic_items", "pending_approval",
    "drift_indicators", "manifest",
)


class _FakeClient:
    """Answers read_note with a fixed body; read_file_bytes either raises the
    configured exception or returns the configured bytes. Mirrors only the
    two KadoClient methods read_approval_state actually calls."""

    def __init__(self, *, note_body: str, wire_error: Exception | None = None,
                 wire_bytes: bytes | None = None):
        self._note_body = note_body
        self._wire_error = wire_error
        self._wire_bytes = wire_bytes
        self.calls: list[tuple[str, str]] = []

    def read_note(self, path: str) -> dict:
        self.calls.append(("read_note", path))
        return {"content": self._note_body, "modified": 0}

    def read_file_bytes(self, path: str) -> bytes:
        self.calls.append(("read_file_bytes", path))
        if self._wire_error is not None:
            raise self._wire_error
        if self._wire_bytes is not None:
            return self._wire_bytes
        raise KadoNotFoundError(f"not found: {path}")


def _hit(path: str = DOC_PATH) -> dict:
    return {
        "path": path,
        "modified": 1234,
        "frontmatter": {"tomo": {"doc_type": "suggestions"}},
    }


def _run(client, tmp_path) -> dict:
    result = _triage.read_approval_state(client, [_hit()], [], str(tmp_path))
    return dict(zip(_STATE_KEYS, result))


def test_wire_sibling_kado_not_found_no_warning(tmp_path, capsys):
    """The no-Hashi path: a genuinely absent sibling must stay silent and the
    doc must still be approved and processed — this is the regression this
    whole fix must NOT introduce.

    Mutation (sanity, not the headline one): make KadoNotFoundError NOT
    caught at all (e.g. catch only KadoToolError). That turns this test red
    with an uncaught exception, proving the test actually drives the real
    exception type rather than a string match.
    """
    client = _FakeClient(note_body=APPROVED_BODY, wire_error=KadoNotFoundError("nope"))
    state = _run(client, tmp_path)

    assert len(state["approved_suggestions"]) == 1
    assert "wire_cache_path" not in state["approved_suggestions"][0]
    assert state["drift_indicators"] == []

    err = capsys.readouterr().err
    assert "WARNING" not in err
    assert "wire_sibling_unreadable" not in err


def test_wire_sibling_kado_tool_error_warns_and_excludes(tmp_path, capsys):
    """A validation/permission-shaped Kado failure must exclude the doc from
    Pass 2 rather than silently falling back to the (stale, for a Hashi user)
    markdown.

    Headline mutation: revert `_cache_wire_sibling`'s catch to
    `except KadoError: return None` (the base class). KadoToolError is a
    KadoError subclass, so it would again be swallowed exactly like
    KadoNotFoundError — wire_cache becomes None, the doc falls back to the
    markdown path, IS appended to approved_suggestions, and no drift
    indicator is recorded. That turns THIS test red (approved_suggestions
    would hold 1 entry, not 0; drift_indicators would be empty) while
    test_wire_sibling_kado_not_found_no_warning and test_wire_sibling_success
    stay green — proving the rule under test is "NOT_FOUND is the only silent
    case", not an accident of this one error type.
    """
    client = _FakeClient(note_body=APPROVED_BODY, wire_error=KadoToolError("boom"))
    state = _run(client, tmp_path)

    assert state["approved_suggestions"] == []
    assert len(state["drift_indicators"]) == 1
    drift = state["drift_indicators"][0]
    assert drift["path"] == DOC_PATH
    assert drift["type"] == "wire_sibling_unreadable"
    assert drift["type"] != "missing_source"  # distinct from the read_note failure type

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert DOC_PATH in err


def test_wire_sibling_kado_connection_error_warns_and_excludes(tmp_path, capsys):
    """Same as the KadoToolError case, with a different KadoError subclass —
    proves the rule is "everything except NOT_FOUND", not an allow-list of
    one sibling exception class.

    Mutation: same headline mutation as the KadoToolError test (revert the
    catch to `except KadoError`). KadoConnectionError is also a KadoError
    subclass, so it is swallowed the same way and this test goes red for the
    same reason: approved_suggestions holds the doc, drift_indicators is
    empty.
    """
    client = _FakeClient(note_body=APPROVED_BODY, wire_error=KadoConnectionError("down"))
    state = _run(client, tmp_path)

    assert state["approved_suggestions"] == []
    assert len(state["drift_indicators"]) == 1
    drift = state["drift_indicators"][0]
    assert drift["path"] == DOC_PATH
    assert drift["type"] == "wire_sibling_unreadable"

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert DOC_PATH in err


def test_wire_sibling_success(tmp_path):
    """Unchanged behaviour: a present, readable sibling is cached and
    wire_cache_path lands on the entry, same as before this fix."""
    client = _FakeClient(note_body=APPROVED_BODY, wire_bytes=b"{}")
    state = _run(client, tmp_path)

    assert len(state["approved_suggestions"]) == 1
    entry = state["approved_suggestions"][0]
    assert entry["wire_cache_path"].endswith(".json")
    assert Path(entry["wire_cache_path"]).read_bytes() == b"{}"
    assert state["drift_indicators"] == []


# ---------------------------------------------------------------------------
# suggestion-parser.py — load_changed_wire's silent "unchanged" route
# ---------------------------------------------------------------------------

def _wire_doc() -> dict:
    """Minimal suggestions-doc.json shape — enough for build_wire_payload to
    project a schema-current, digest-sealed wire (see suggestions-render.py)."""
    return {
        "schema_version": "1",
        "generated": "2026-10-10T10:00:00Z",
        "run_id": "2026-10-10-1000-wire-cache",
        "profile": "miyo",
        "source_items": 1,
        "sections": [
            {
                "id": "S01",
                "stem": "memo",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "suggestion_id": "S01",
                        "item": {
                            "title": "My Note", "template": "t_note_tomo.md",
                            "location": "Atlas/202 Notes/", "tags": [],
                            "audio_peer": None, "worthiness": 0.8,
                            "suppressed": False, "force_atomic": False,
                        },
                        "candidate_mocs": [],
                    }
                ],
            }
        ],
        "proposed_mocs": [],
        "needs_attention": [],
    }


def test_load_changed_wire_unchanged_logs_markdown_fallback(tmp_path, capsys):
    """An unedited wire (emit_digest matches a recomputation) still takes the
    markdown path — `load_changed_wire` still returns None — but it must now
    say so on stderr. Built through `build_wire_payload` (not a hand-rolled
    dict) so `schema_version` comes from the schema itself: a hardcoded
    version would drift the moment the schema moves and take the markdown
    path for the WRONG reason (a version mismatch, not "unchanged"),
    making the stderr assertion below pass vacuously.

    Mutation: delete the new `print(..., file=sys.stderr)` call, leaving the
    bare `return None`. `result is None` stays green (unchanged behaviour),
    but the stderr assertions go red — proving this test exercises the new
    line specifically, not just the pre-existing fallback.
    """
    wire = _render_mod.build_wire_payload(_wire_doc())  # emit_digest matches payload
    wire_path = tmp_path / "2026-10-10_1000_suggestions.json"
    wire_path.write_text(json.dumps(wire), encoding="utf-8")

    result = _parser_mod.load_changed_wire(str(wire_path))

    assert result is None
    err = capsys.readouterr().err
    assert "unchanged" in err
    assert "markdown" in err.lower()
