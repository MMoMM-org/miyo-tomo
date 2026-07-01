#!/usr/bin/env python3
# version: 0.1.0
"""test_027_t3_2_audio_peer_move_note.py — spec 027 / T3.2 audio_peer threading.

Verifies that:
  1. _build_move_note_actions carries audio_peer from the manifest entry into
     the emitted move_note action dict — vault-relative paths pass through
     unchanged; bare basenames get joined with inbox_path (no .md coercion).
  2. A manifest entry without audio_peer → move_note action has audio_peer=None.
  3. The .m4a extension is never coerced to .md via _ensure_md_extension.
  4. suggestion-parser.py extracts audio_peer (second wikilink) from a
     "**Source:** [[stem]] + [[audio.m4a]]" line into the confirmed item.

Tests are RED against current code (no audio_peer in move_note / no parser
extraction) and GREEN after T3.2.

Spec: docs/XDD/specs/027-suggestions-source-model/ ADR-1, ADR-2; PRD AC F3.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"
REDUCER_PATH = SCRIPTS_DIR / "suggestions-reducer.py"
PARSER_PATH = SCRIPTS_DIR / "suggestion-parser.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py via importlib (hyphen in name).
_ir_spec = importlib.util.spec_from_file_location("instruction_render_t32", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_t32"] = ir
_ir_spec.loader.exec_module(ir)

# Load suggestions-reducer for render_create_atomic_note.
_rr_spec = importlib.util.spec_from_file_location("suggestions_reducer_t32", REDUCER_PATH)
rr = importlib.util.module_from_spec(_rr_spec)
assert _rr_spec.loader is not None
sys.modules["suggestions_reducer_t32"] = rr
_rr_spec.loader.exec_module(rr)

render_create_atomic_note = rr.render_create_atomic_note  # type: ignore[attr-defined]

INBOX = "100 Inbox"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _manifest_entry(audio_peer=None, source_path="note.md") -> dict:
    """Minimal manifest entry (as produced by render_notes)."""
    entry: dict = {
        "title": "Test Note",
        "source_path": source_path,
        "template": "Atomic Note.md",
        "rendered_file": "20260608_1200-test-note.md",
        "rendered_path": "/tmp/tomo-out/20260608_1200-test-note.md",
        "destination": "200 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
        "supporting_items": None,
    }
    if audio_peer is not None:
        entry["audio_peer"] = audio_peer
    return entry


def _call_build_move_note(manifest: list[dict], inbox: str = INBOX) -> list[dict]:
    """Call _build_move_note_actions and return the action list."""
    counter = [0]
    return ir._build_move_note_actions(manifest, inbox, counter)


# ── Tests: _build_move_note_actions carries audio_peer ───────────────────────


def test_build_move_note_carries_vault_relative_audio_peer():
    """Vault-relative audio_peer passes through unchanged (no join, no .md coercion)."""
    peer = "100 Inbox/2026-04-08_1430_interview.m4a"
    actions = _call_build_move_note([_manifest_entry(audio_peer=peer)])
    assert len(actions) == 1
    assert actions[0].get("audio_peer") == peer, (
        f"Expected audio_peer='{peer}'; got {actions[0].get('audio_peer')!r}"
    )


def test_build_move_note_joins_bare_basename_audio_peer():
    """Bare basename audio_peer (no path) gets joined with inbox_path."""
    actions = _call_build_move_note([_manifest_entry(audio_peer="interview.m4a")])
    assert len(actions) == 1
    expected = f"{INBOX}/interview.m4a"
    assert actions[0].get("audio_peer") == expected, (
        f"Expected joined audio_peer '{expected}'; got {actions[0].get('audio_peer')!r}"
    )


def test_build_move_note_audio_peer_extension_not_coerced():
    """The .m4a extension is never changed to .md — _ensure_md_extension must NOT run."""
    actions = _call_build_move_note([_manifest_entry(audio_peer="recording.m4a")])
    ap = actions[0].get("audio_peer", "")
    assert ".m4a" in ap, f"Expected .m4a in audio_peer; got {ap!r}"
    assert ap.endswith(".m4a"), f"audio_peer must end with .m4a, not .md; got {ap!r}"


def test_build_move_note_no_audio_peer_is_none():
    """Manifest entry without audio_peer → move_note has audio_peer=None (or absent)."""
    actions = _call_build_move_note([_manifest_entry()])  # no audio_peer key
    assert len(actions) == 1
    ap = actions[0].get("audio_peer")
    assert ap is None, (
        f"Expected audio_peer=None when manifest entry has none; got {ap!r}"
    )


def test_build_move_note_explicit_none_audio_peer():
    """Manifest entry with audio_peer=None → move_note has audio_peer=None."""
    entry = _manifest_entry()
    entry["audio_peer"] = None
    actions = _call_build_move_note([entry])
    assert actions[0].get("audio_peer") is None


def test_build_move_note_source_inbox_item_unaffected():
    """Adding audio_peer does not change how source_inbox_item is built."""
    peer = "100 Inbox/audio.m4a"
    actions = _call_build_move_note([_manifest_entry(audio_peer=peer, source_path="note.md")])
    origin = actions[0].get("source_inbox_item", "")
    assert origin.endswith(".md"), (
        f"source_inbox_item must keep .md extension; got {origin!r}"
    )
    assert "audio" not in origin, (
        "source_inbox_item must not be the audio peer; it's the transcript source"
    )


# ── Tests: parser extracts audio_peer from source set line ───────────────────


def _minimal_doc_md(rendered_md: str) -> str:
    return "\n".join([
        "---",
        "type: tomo-suggestions",
        "generated: 2026-06-11T10:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: t32-test",
        "---",
        "",
        "# Inbox Suggestions — 2026-06-11",
        "",
        "- [x] Approved — check this box when you have finished reviewing",
        "",
        "## Summary",
        "",
        "- Items processed: 1",
        "",
        "## Suggestions",
        "",
        "### S01 — Sample Note",
        "",
        rendered_md,
        "",
    ])


def _run_parser(md: str, tmp_path: Path) -> dict:
    p = tmp_path / "suggestions.md"
    p.write_text(md)
    cmd = [sys.executable, str(PARSER_PATH), "--file", str(p)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, (
        f"parser exit {result.returncode}; stderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def _audio_action(audio_peer: str = "Inbox/2026-04-08_1430_interview.m4a") -> dict:
    return {
        "suggested_title": "Interview Notes",
        "atomic_note_worthiness": 0.8,
        "template": None,
        "location": None,
        "audio_peer": audio_peer,
        "candidate_mocs": [],
        "tags_to_add": [],
        "classification": {},
        "alternatives": [],
    }


def test_parser_extracts_audio_peer_from_source_set_line(tmp_path):
    """Parser extracts audio_peer (second wikilink) from Source: [[stem]] + [[audio.m4a]]."""
    rendered = render_create_atomic_note(
        _audio_action("Inbox/2026-04-08_1430_interview.m4a"),
        "interview-transcript",
    )
    # Verify the rendered source line has the set format
    assert "[[interview-transcript]] + [[2026-04-08_1430_interview.m4a]]" in rendered

    doc = _minimal_doc_md(rendered)
    out = _run_parser(doc, tmp_path)

    confirmed = out.get("confirmed_items", [])
    assert len(confirmed) == 1, f"Expected 1 confirmed item; got {confirmed!r}"
    ap = confirmed[0].get("audio_peer")
    assert ap == "2026-04-08_1430_interview.m4a", (
        f"Expected audio_peer='2026-04-08_1430_interview.m4a' (basename); got {ap!r}"
    )


def test_parser_no_audio_peer_when_single_source(tmp_path):
    """Parser leaves audio_peer None/absent when Source line has only one wikilink."""
    action = {
        "suggested_title": "Plain Note",
        "atomic_note_worthiness": 0.8,
        "template": None,
        "location": None,
        "candidate_mocs": [],
        "tags_to_add": [],
        "classification": {},
        "alternatives": [],
    }
    rendered = render_create_atomic_note(action, "plain-note")
    assert "+" not in rendered.split("**Source:**")[1].split("\n")[0], (
        "Single-source render must not contain '+'"
    )
    doc = _minimal_doc_md(rendered)
    out = _run_parser(doc, tmp_path)

    confirmed = out.get("confirmed_items", [])
    assert len(confirmed) == 1
    ap = confirmed[0].get("audio_peer")
    assert ap is None, (
        f"Expected audio_peer=None for single-source item; got {ap!r}"
    )
