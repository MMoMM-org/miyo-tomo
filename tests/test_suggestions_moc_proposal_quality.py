#!/usr/bin/env python3
# version: 0.3.0
"""test_suggestions_moc_proposal_quality.py — F-34 MOC quality fixes (b/a/c).

Tests (ordered b→a→c, fix-first):

  (b) Naming consistency — "Notemaking MOC" topic → "Notemaking (MOC)" name,
      no double-suffix when topic already ends "MOC".

  (a) Dedup item↔proposal — needs_new_moc item has ONE place where the MOC
      decision lives (Proposed MOCs section); no redundant create-framing in
      the item's own section. Deferral **Note:** pointer must still appear.
      Heading still resolves via **Suggested name:**.

  (c) Supporting NOTE titles + reason — proposed_mocs entry carries real
      note_titles (not bare S02) and a reason phrase; renderer shows
      **Supporting notes:** and **Why:** lines.

  Note: fix (d) overlap-merge was reverted — the /inbox reducer clusters never
  share notes (each item yields one proposed_moc_topic), so Jaccard dedup is
  inert here. The real overlap lives in the accumulation_index / /moc-propose
  path which already has its own Jaccard-0.80 dedup.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REDUCER = REPO_ROOT / "tomo" / "scripts" / "suggestions-reducer.py"
RENDER_SCRIPT = REPO_ROOT / "tomo" / "scripts" / "suggestions-render.py"
SCRIPTS_DIR = str(REPO_ROOT / "tomo" / "scripts")

_DEPS = "/tmp/claude/py_deps"
_extra = ":".join(p for p in [_DEPS, SCRIPTS_DIR] if os.path.isdir(p))
_ENV = {
    **os.environ,
    "PYTHONPATH": _extra + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}


# ── Shared fixture helpers ────────────────────────────────────────────────────


def _minimal_shared_ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": "test-run",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")


def _write_state(path: Path, stems: list[str]) -> None:
    lines = [
        json.dumps({
            "stem": stem,
            "path": f"100 Inbox/{stem}.md",
            "status": "done",
            "run_id": "test-run",
            "ts": "2026-06-04T12:00:00Z",
        })
        for stem in stems
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_result(
    items_dir: Path,
    stem: str,
    *,
    needs_new_moc: bool = False,
    proposed_moc_topic: str | None = None,
    suggested_title: str | None = None,
    candidate_mocs: list | None = None,
    tags_to_add: list | None = None,
    classification: dict | None = None,
    atomic_note_worthiness: float = 0.7,
) -> None:
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.8,
        "force_atomic": False,
        "actions": [
            {
                "kind": "create_atomic_note",
                "suggested_title": suggested_title or stem,
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": candidate_mocs or [],
                "tags_to_add": tags_to_add or [],
                "needs_new_moc": needs_new_moc,
                "proposed_moc_topic": proposed_moc_topic,
                "classification": classification or {"category": "2600 - Applied Sciences", "confidence": 0.6},
                "atomic_note_worthiness": atomic_note_worthiness,
                "alternatives": [],
            }
        ],
        "candidate_mocs": candidate_mocs or [],
        "classification": classification or {"category": "2600 - Applied Sciences", "confidence": 0.6},
        "needs_new_moc": needs_new_moc,
        "proposed_moc_topic": proposed_moc_topic,
        "tags_to_add": tags_to_add or [],
        "atomic_note_worthiness": atomic_note_worthiness,
        "alternatives": [],
        "issues": [],
        "duration_ms": 0,
    }), encoding="utf-8")


def _run_reducer(tmp_path: Path, stems: list[str], results_fn=None, threshold: int = 1) -> dict:
    """Run reducer and return parsed doc."""
    items_dir = tmp_path / "items"
    items_dir.mkdir(exist_ok=True)
    shared_ctx = tmp_path / "shared-ctx.json"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    _minimal_shared_ctx(shared_ctx)
    _write_state(state, stems)
    if results_fn:
        results_fn(items_dir)
    result = subprocess.run(
        [
            sys.executable, str(REDUCER),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", "test-run",
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--threshold", str(threshold),
            "--output", str(output),
        ],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert result.returncode == 0, f"reducer exit {result.returncode}; stderr:\n{result.stderr}"
    return json.loads(output.read_text(encoding="utf-8"))


def _run_render(tmp_path: Path, doc: dict) -> str:
    """Run renderer on a doc dict and return output markdown."""
    doc_path = tmp_path / "render_input.json"
    out_path = tmp_path / "render_output.md"
    doc_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable, str(RENDER_SCRIPT),
            "--input", str(doc_path),
            "--output", str(out_path),
        ],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert result.returncode == 0, f"render exit {result.returncode}; stderr:\n{result.stderr}"
    return out_path.read_text(encoding="utf-8")


# ── (b) Naming consistency ────────────────────────────────────────────────────


class TestNamingConsistency:
    """Fix (b): proposed_moc name uses (MOC) convention without double-suffix."""

    def test_topic_ending_moc_does_not_double_suffix(self, tmp_path):
        """Topic 'Notemaking MOC' → name 'Notemaking (MOC)', NOT 'Notemaking MOC (MOC)'."""
        stems = ["note-a", "note-b", "note-c"]

        def make_results(items_dir: Path):
            for stem in stems:
                _write_result(
                    items_dir, stem,
                    needs_new_moc=True,
                    proposed_moc_topic="Notemaking MOC",
                    suggested_title=f"{stem} atomic",
                )

        doc = _run_reducer(tmp_path, stems, make_results, threshold=1)
        assert doc["proposed_mocs"], "Expected at least one proposed MOC"
        pm = doc["proposed_mocs"][0]
        name = pm.get("name", "")
        # Must be exactly "Notemaking (MOC)", not "Notemaking MOC (MOC)"
        assert name == "Notemaking (MOC)", (
            f"Expected 'Notemaking (MOC)', got {name!r} — double-suffix bug"
        )
        # Verify it does NOT contain the double-suffix pattern
        assert "MOC (MOC)" not in name, f"Double-suffix present: {name!r}"

    def test_topic_without_moc_gets_suffix(self, tmp_path):
        """Topic 'Notemaking' → name 'Notemaking (MOC)'."""
        stems = ["note-a", "note-b", "note-c"]

        def make_results(items_dir: Path):
            for stem in stems:
                _write_result(
                    items_dir, stem,
                    needs_new_moc=True,
                    proposed_moc_topic="Notemaking",
                    suggested_title=f"{stem} atomic",
                )

        doc = _run_reducer(tmp_path, stems, make_results, threshold=1)
        pm = doc["proposed_mocs"][0]
        assert pm.get("name") == "Notemaking (MOC)", pm.get("name")

    def test_render_uses_name_field_not_raw_topic(self, tmp_path):
        """Renderer reads pm['name'] — output contains 'Notemaking (MOC)' not 'Notemaking MOC (MOC)'."""
        stems = ["note-a", "note-b", "note-c"]

        def make_results(items_dir: Path):
            for stem in stems:
                _write_result(
                    items_dir, stem,
                    needs_new_moc=True,
                    proposed_moc_topic="Notemaking MOC",
                    suggested_title=f"{stem} atomic",
                )

        doc = _run_reducer(tmp_path, stems, make_results, threshold=1)
        md = _run_render(tmp_path, doc)
        assert "Notemaking (MOC)" in md, f"Expected 'Notemaking (MOC)' in render output"
        assert "Notemaking MOC (MOC)" not in md, f"Double-suffix in rendered output:\n{md}"


# ── (a) Dedup item↔proposal ───────────────────────────────────────────────────


class TestDedupItemVsProposal:
    """Fix (a): needs_new_moc item appears ONCE (in Proposed MOCs), not twice."""

    def test_needs_new_moc_section_has_no_redundant_moc_create_framing(self, tmp_path):
        """Item section for needs_new_moc should NOT contain create-MOC decision UI."""
        stems = ["kyoto-trip", "nara-deer", "tokyo-skyline"]

        def make_results(items_dir: Path):
            for stem in stems:
                _write_result(
                    items_dir, stem,
                    needs_new_moc=True,
                    proposed_moc_topic="Japan Travel",
                    suggested_title=f"{stem.replace('-', ' ').title()} Note",
                )

        doc = _run_reducer(tmp_path, stems, make_results, threshold=1)
        # Render and examine the item-section portion (before ## Proposed MOCs)
        md = _run_render(tmp_path, doc)
        assert "## Proposed MOCs" in md, "render must produce a Proposed MOCs section"
        suggestions_part, proposed_part = md.split("## Proposed MOCs", 1)

        # Positive anchor: the create-MOC UI MUST render in the Proposed MOCs
        # section — otherwise the absence checks below are vacuous (they would
        # pass even if dedup were removed but the create UI simply never rendered).
        assert "Approve (create this MOC" in proposed_part, (
            "create-MOC UI must appear in the Proposed MOCs section"
        )
        # The per-item section must NOT duplicate the create-MOC decision UI.
        assert "Approve (create this MOC" not in suggestions_part, (
            "Item section contains create-MOC approve UI — redundant with Proposed MOCs"
        )
        assert "Skip — don't create" not in suggestions_part, (
            "Item section contains skip-MOC UI — redundant with Proposed MOCs"
        )

    def test_needs_new_moc_item_still_has_deferral_note(self, tmp_path):
        """Item section must still have a **Note:** deferral pointer to Proposed MOCs."""
        stems = ["kyoto-trip", "nara-deer", "tokyo-skyline"]

        def make_results(items_dir: Path):
            for stem in stems:
                _write_result(
                    items_dir, stem,
                    needs_new_moc=True,
                    proposed_moc_topic="Japan Travel",
                    suggested_title=f"{stem.replace('-', ' ').title()} Note",
                )

        doc = _run_reducer(tmp_path, stems, make_results, threshold=1)
        md = _run_render(tmp_path, doc)
        suggestions_part = md.split("## Proposed MOCs")[0] if "## Proposed MOCs" in md else md

        # The deferral pointer must be present in the item section
        assert "**Note:**" in suggestions_part, (
            "Item section missing **Note:** deferral pointer to Proposed MOCs"
        )
        assert "Proposed MOCs" in suggestions_part, (
            "Item section missing reference to Proposed MOCs section"
        )

    def test_heading_still_resolves_via_suggested_name(self, tmp_path):
        """Section heading derives from **Suggested name:** even when needs_new_moc."""
        stems = ["kyoto-trip", "nara-deer", "tokyo-skyline"]

        def make_results(items_dir: Path):
            for i, stem in enumerate(stems):
                _write_result(
                    items_dir, stem,
                    needs_new_moc=True,
                    proposed_moc_topic="Japan Travel",
                    suggested_title="My Kyoto Note",
                )

        doc = _run_reducer(tmp_path, ["kyoto-trip"], lambda d: _write_result(
            d, "kyoto-trip",
            needs_new_moc=True,
            proposed_moc_topic="Japan Travel",
            suggested_title="My Kyoto Note",
        ), threshold=1)
        md = _run_render(tmp_path, doc)
        # The heading should use the suggested title
        assert "S01 — My Kyoto Note" in md, (
            f"Section heading did not resolve via **Suggested name:**\n{md[:500]}"
        )

    def test_proposed_mocs_section_still_present(self, tmp_path):
        """## Proposed MOCs section appears once and contains the topic."""
        stems = ["kyoto-trip", "nara-deer", "tokyo-skyline"]

        def make_results(items_dir: Path):
            for stem in stems:
                _write_result(
                    items_dir, stem,
                    needs_new_moc=True,
                    proposed_moc_topic="Japan Travel",
                    suggested_title=f"{stem} Note",
                )

        doc = _run_reducer(tmp_path, stems, make_results, threshold=1)
        md = _run_render(tmp_path, doc)
        assert "## Proposed MOCs" in md, "## Proposed MOCs section missing"
        assert "Japan Travel" in md.split("## Proposed MOCs")[1], (
            "Japan Travel topic missing from Proposed MOCs section"
        )


# ── (c) Supporting NOTE titles + reason ──────────────────────────────────────


class TestSupportingNoteTitlesAndReason:
    """Fix (c): proposed_mocs[i] has note_titles list and reason field; renderer uses them."""

    def test_proposed_moc_has_note_titles_not_bare_ids(self, tmp_path):
        """proposed_mocs[0].note_titles contains actual titles, not bare section IDs."""
        def make_results(items_dir: Path):
            _write_result(items_dir, "kyoto-notes",
                          needs_new_moc=True, proposed_moc_topic="Japan Travel",
                          suggested_title="Kyoto Notes")
            _write_result(items_dir, "nara-deer-park",
                          needs_new_moc=True, proposed_moc_topic="Japan Travel",
                          suggested_title="Nara Deer Park")
            _write_result(items_dir, "tokyo-tower",
                          needs_new_moc=True, proposed_moc_topic="Japan Travel",
                          suggested_title="Tokyo Tower")

        doc = _run_reducer(
            tmp_path,
            ["kyoto-notes", "nara-deer-park", "tokyo-tower"],
            make_results,
            threshold=1,
        )
        assert doc["proposed_mocs"], "Expected proposed_mocs to be populated"
        pm = doc["proposed_mocs"][0]

        note_titles = pm.get("note_titles")
        assert note_titles is not None, "proposed_mocs[0] missing 'note_titles' field"
        assert isinstance(note_titles, list), f"note_titles must be a list, got {type(note_titles)}"
        # Must not contain bare section IDs
        for t in note_titles:
            assert not t.startswith("S0"), f"note_titles contains bare ID {t!r}, expected a title"
        # Must contain actual titles
        assert "Kyoto Notes" in note_titles or any("kyoto" in t.lower() for t in note_titles), (
            f"Expected Kyoto Notes title in note_titles, got: {note_titles}"
        )

    def test_proposed_moc_has_reason_field(self, tmp_path):
        """proposed_mocs[0] carries a 'reason' field with a human-readable phrase."""
        def make_results(items_dir: Path):
            for stem in ["note-a", "note-b", "note-c"]:
                _write_result(items_dir, stem,
                              needs_new_moc=True, proposed_moc_topic="Japan Travel",
                              suggested_title=f"{stem} title")

        doc = _run_reducer(
            tmp_path, ["note-a", "note-b", "note-c"], make_results, threshold=1
        )
        pm = doc["proposed_mocs"][0]
        reason = pm.get("reason")
        assert reason is not None, "proposed_mocs[0] missing 'reason' field"
        assert isinstance(reason, str) and len(reason) > 10, (
            f"reason must be a non-trivial string, got: {reason!r}"
        )
        # Should mention count and topic
        assert "Japan Travel" in reason or "japan travel" in reason.lower(), (
            f"reason should mention the topic, got: {reason!r}"
        )

    def test_render_uses_supporting_notes_not_ids(self, tmp_path):
        """Renderer outputs '**Supporting notes:**' with titles, not bare IDs."""
        def make_results(items_dir: Path):
            _write_result(items_dir, "kyoto-notes",
                          needs_new_moc=True, proposed_moc_topic="Japan Travel",
                          suggested_title="Kyoto Notes")
            _write_result(items_dir, "nara-deer",
                          needs_new_moc=True, proposed_moc_topic="Japan Travel",
                          suggested_title="Nara Deer Park")
            _write_result(items_dir, "tokyo-tower",
                          needs_new_moc=True, proposed_moc_topic="Japan Travel",
                          suggested_title="Tokyo Tower")

        doc = _run_reducer(
            tmp_path,
            ["kyoto-notes", "nara-deer", "tokyo-tower"],
            make_results,
            threshold=1,
        )
        md = _run_render(tmp_path, doc)
        moc_section = md.split("## Proposed MOCs")[1] if "## Proposed MOCs" in md else ""
        assert "**Supporting notes:**" in moc_section, (
            "Renderer must emit '**Supporting notes:**' (not bare IDs)"
        )
        # Old pattern must be gone
        assert "**Supporting items:** S0" not in moc_section, (
            "Renderer still emitting old bare-ID '**Supporting items:**' pattern"
        )

    def test_render_includes_why_line(self, tmp_path):
        """Renderer outputs a '**Why:**' line in the Proposed MOC entry."""
        def make_results(items_dir: Path):
            for stem in ["note-a", "note-b", "note-c"]:
                _write_result(items_dir, stem,
                              needs_new_moc=True, proposed_moc_topic="Japan Travel",
                              suggested_title=f"{stem} title")

        doc = _run_reducer(
            tmp_path, ["note-a", "note-b", "note-c"], make_results, threshold=1
        )
        md = _run_render(tmp_path, doc)
        moc_section = md.split("## Proposed MOCs")[1] if "## Proposed MOCs" in md else ""
        assert "**Why:**" in moc_section, (
            "Renderer must emit a '**Why:**' line in the Proposed MOC entry"
        )


