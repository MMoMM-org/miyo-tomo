#!/usr/bin/env python3
# version: 0.1.0
"""test_027_t2_2_3_source_set_and_parser.py — spec 027 / Phase 2 / T2.2 + T2.3.

T2.2 — Voice source rendered as a file set:
  Given an action with audio_peer, the **Source:** line renders as
  ``[[stem]] + [[peer.m4a]]`` (peer basename, extension preserved, never coerced
  to .md). Without a peer, the existing single-source rendering is unchanged.

T2.3 — Parser matches new "Keep source files" label:
  Round-trip render→parse: a checked "Keep source files" box → keep_source=True;
  unchecked → keep_source=False. Un-approved item → approved=False (skip implicit).
  The legacy "Delete source" disposition flow must still parse via the skipped-items
  path (parser line 412 is unchanged).

Spec: docs/XDD/specs/027-suggestions-source-model/
SDD: ADR-1 (audio_peer field), ADR-4 (two-box block + keep source wording)
PRD: AC F3 (voice source set), AC F1/F2 (keep source label round-trip)
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
PARSER = SCRIPTS_DIR / "suggestion-parser.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load suggestions-reducer.py (hyphen filename → importlib).
_reducer_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer_t2_23", SCRIPTS_DIR / "suggestions-reducer.py"
)
_reducer_mod = importlib.util.module_from_spec(_reducer_spec)
assert _reducer_spec.loader is not None
sys.modules["suggestions_reducer_t2_23"] = _reducer_mod
_reducer_spec.loader.exec_module(_reducer_mod)

render_create_atomic_note = _reducer_mod.render_create_atomic_note  # type: ignore[attr-defined]


# ── Shared helpers ────────────────────────────────────────────────────────────


def _action(audio_peer: str | None = None, worthiness: float = 0.8) -> dict:
    """Minimal create_atomic_note action."""
    base: dict = {
        "suggested_title": "Sample Note",
        "atomic_note_worthiness": worthiness,
        "template": None,
        "location": None,
        "candidate_mocs": [],
        "tags_to_add": [],
        "classification": {},
        "alternatives": [],
    }
    if audio_peer is not None:
        base["audio_peer"] = audio_peer
    return base


def _minimal_doc_md(rendered_md: str, source_items: int = 1) -> str:
    """Wrap a rendered_md block into a minimal parseable suggestions document."""
    return "\n".join([
        "---",
        "type: tomo-suggestions",
        "generated: 2026-06-11T10:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        f"source_items: {source_items}",
        "run_id: 2026-06-11-1000-t2test",
        "---",
        "",
        "# Inbox Suggestions — 2026-06-11",
        "",
        "- [x] Approved — check this box when you have finished reviewing",
        "",
        "## Summary",
        "",
        f"- Items processed: {source_items}",
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
    cmd = [sys.executable, str(PARSER), "--file", str(p)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, (
        f"parser exit {result.returncode}; stderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


# ── T2.2: audio peer source rendering ─────────────────────────────────────────


def test_audio_peer_renders_source_as_set():
    """When action has audio_peer, Source line is [[stem]] + [[peer_basename]] (F3)."""
    md = render_create_atomic_note(
        _action(audio_peer="Inbox/Recordings/interview-2026.m4a"), "my-note"
    )
    assert "**Source:** [[my-note]] + [[interview-2026.m4a]]" in md, (
        f"Expected audio-peer set source line; got:\n{md}"
    )


def test_audio_peer_preserves_extension():
    """audio_peer display must keep the .m4a extension — never coerce to .md (ADR-1)."""
    md = render_create_atomic_note(
        _action(audio_peer="Inbox/Recordings/podcast.m4a"), "transcript"
    )
    assert "[[podcast.m4a]]" in md, (
        "Expected .m4a extension preserved in audio peer wikilink"
    )
    assert "[[podcast.md]]" not in md, (
        "audio peer must NOT be coerced to .md"
    )


def test_audio_peer_uses_basename_only():
    """Only the filename (not full path) is used in the wikilink (F3)."""
    md = render_create_atomic_note(
        _action(audio_peer="Deep/Nested/Path/voice.m4a"), "note-stem"
    )
    assert "[[voice.m4a]]" in md, "Expected basename-only wikilink for audio peer"
    assert "Deep/Nested/Path" not in md, "Path prefix must not appear in wikilink"


def test_no_audio_peer_renders_single_source():
    """Without audio_peer, Source line is the plain [[stem]] wikilink (unchanged)."""
    md = render_create_atomic_note(_action(audio_peer=None), "my-note")
    assert "**Source:** [[my-note]]" in md, "Expected single-source line without peer"
    assert "**Source:** [[my-note]] + " not in md, "No peer set in source line when no peer"


# ── T2.3: atomic parser label round-trip ─────────────────────────────────────


def test_keep_source_checked_sets_keep_source_true(tmp_path):
    """Parse a block with [x] Keep source files → confirmed item has keep_source=True."""
    rendered = render_create_atomic_note(_action(), "my-note")
    # Flip the Keep source files checkbox to checked.
    rendered_checked = rendered.replace(
        "- [ ] Keep source files", "- [x] Keep source files", 1
    )
    doc_md = _minimal_doc_md(rendered_checked)
    out = _run_parser(doc_md, tmp_path)

    confirmed = out.get("confirmed_items", [])
    assert len(confirmed) == 1, f"Expected 1 confirmed item; got {confirmed!r}"
    assert confirmed[0].get("keep_source") is True, (
        f"Expected keep_source=True when 'Keep source files' is checked; "
        f"item: {confirmed[0]!r}"
    )


def test_keep_source_unchecked_gives_keep_source_false(tmp_path):
    """Parse a block with [ ] Keep source files → confirmed item has keep_source=False."""
    rendered = render_create_atomic_note(_action(), "my-note")
    # Default rendered block has the checkbox unchecked.
    doc_md = _minimal_doc_md(rendered)
    out = _run_parser(doc_md, tmp_path)

    confirmed = out.get("confirmed_items", [])
    assert len(confirmed) == 1, f"Expected 1 confirmed item; got {confirmed!r}"
    keep = confirmed[0].get("keep_source")
    assert keep is False, (
        f"Expected keep_source=False when unchecked (checkbox present but unticked); got {keep!r}"
    )


def test_unapproved_item_becomes_skipped(tmp_path):
    """Un-approved atomic block ([ ] Approve) → item ends up in skipped_items (ADR-4)."""
    rendered = render_create_atomic_note(_action(worthiness=0.3), "my-note")
    # Ensure Approve is unchecked (low worthiness → already [ ])
    assert "- [ ] Approve" in rendered
    doc_md = _minimal_doc_md(rendered)
    out = _run_parser(doc_md, tmp_path)

    confirmed = out.get("confirmed_items", [])
    skipped = out.get("skipped", [])
    assert len(confirmed) == 0, f"Un-approved item must NOT be confirmed; got {confirmed!r}"
    assert len(skipped) >= 1, f"Un-approved item must go to skipped; got {skipped!r}"


def test_delete_source_disposition_still_parses(tmp_path):
    """The legacy 'Delete source' checkbox (line 412) still routes to disposition=delete_source.

    This validates that removing the per-atomic Delete-source from the RENDERER
    does not break the parser's ability to handle existing/manual 'Delete source'
    checkboxes (e.g. an inbox note the user manually marked for deletion).
    """
    # Build a manual section with an un-approved item + Delete source checked.
    delete_md = "\n".join([
        "**Source:** [[old-note]]",
        "**Suggested name:** Old Note",
        "",
        "**Decision (atomic note):**",
        "- [ ] Approve",
        "- [ ] Keep source files",
        "      (don't delete the original(s) after the note is created — you may still need them)",
        "- [x] Delete source",
    ])
    doc_md = _minimal_doc_md(delete_md)
    out = _run_parser(doc_md, tmp_path)

    skipped = out.get("skipped", [])
    delete_source_items = [s for s in skipped if s.get("disposition") == "delete_source"]
    assert len(delete_source_items) >= 1, (
        f"Expected a skipped item with disposition=delete_source; "
        f"skipped_items={skipped!r}"
    )
