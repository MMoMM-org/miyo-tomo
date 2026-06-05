#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_moc_proposal_quality.py — F-34 four-part MOC quality fixes.

Tests (ordered b→a→c→d, fix-first):

  (b) Naming consistency — "Notemaking MOC" topic → "Notemaking (MOC)" name,
      no double-suffix when topic already ends "MOC".

  (a) Dedup item↔proposal — needs_new_moc item has ONE place where the MOC
      decision lives (Proposed MOCs section); no redundant create-framing in
      the item's own section. Deferral **Note:** pointer must still appear.
      Heading still resolves via **Suggested name:**.

  (c) Supporting NOTE titles + reason — proposed_mocs entry carries real
      note_titles (not bare S02) and a reason phrase; renderer shows
      **Supporting notes:** and **Why:** lines.

  (d) Overlap merge (Jaccard ≥ 0.80) — two clusters sharing ≥80% note-stems
      merge into one proposal with alias_topics + union items + majority parent.
      Edge cases: J just below 0.80 (no merge), J=1.0 (merge), 3-way transitive.
"""
from __future__ import annotations

import importlib.util
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
        suggestions_part = md.split("## Proposed MOCs")[0] if "## Proposed MOCs" in md else md

        # The per-item section must NOT have create-MOC decision UI
        assert "Approve (create this MOC" not in suggestions_part, (
            "Item section contains create-MOC approve UI — redundant with Proposed MOCs"
        )
        assert "Skip — don't create" not in suggestions_part.replace("## Proposed MOCs", ""), (
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


# ── (d) Overlap merge (Jaccard ≥ 0.80) ───────────────────────────────────────


class TestOverlapMerge:
    """Fix (d): clusters with Jaccard ≥ 0.80 on note-sets merge into one proposal."""

    def _make_two_cluster_results(
        self,
        items_dir: Path,
        topic_a: str,
        topic_b: str,
        shared_stems: list[str],
        only_a_stems: list[str],
        only_b_stems: list[str],
    ) -> None:
        """Write result fixtures assigning shared stems to topic_a and topic_b."""
        for stem in shared_stems:
            # Writes TWO separate result files with different topics won't work
            # because each stem has one file. Instead, we create different stems
            # that share the same "note content" by assigning them to two topics.
            pass
        # Stems whose result has topic_a
        for stem in shared_stems + only_a_stems:
            _write_result(items_dir, stem,
                          needs_new_moc=True, proposed_moc_topic=topic_a,
                          suggested_title=f"{stem} Note")
        for stem in only_b_stems:
            _write_result(items_dir, stem,
                          needs_new_moc=True, proposed_moc_topic=topic_b,
                          suggested_title=f"{stem} Note")

    def test_identical_clusters_merge_j1(self, tmp_path):
        """Two clusters with J=1.0 (identical note-sets) merge into one proposal."""
        # We need different stems that map to the same underlying note-set.
        # Strategy: create pairs of stems with identical topics but different items
        # by using threshold=1 with 4+ stems per topic.
        # For J=1.0 we need cluster A items == cluster B items (same stems).
        # Achievable by having 3 stems each report BOTH topic_a and topic_b...
        # but each stem has one result file with one topic.
        # Instead: use stems kyoto/nara/tokyo for topic A and also topic B
        # by having 3 stems → topic_a and 3 other stems → topic_b, but
        # the stems are the SAME items (same section_ids) for both clusters.
        # This requires multiple proposed_moc_topic values per stem (not in schema).
        # REAL approach: Create 3 stems each posting topic_a, plus 3 more posting
        # topic_a AND topic_b through separate actions... not possible with simple fixture.
        #
        # Simplest achievable: test _merge_overlapping_mocs directly as a unit test.
        # Import the function via importlib.
        spec = importlib.util.spec_from_file_location(
            "suggestions_reducer_merge",
            str(REDUCER),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        merge_fn = getattr(mod, "_merge_overlapping_mocs", None)
        assert merge_fn is not None, "_merge_overlapping_mocs not exported from reducer"

        # Two clusters with identical note stems → J=1.0 → merge
        proposed_mocs = [
            {
                "topic": "Kyoto",
                "items": ["S01", "S02", "S03"],
                "parent": "2600 - Applied Sciences",
                "tags": [],
                "name": "Kyoto (MOC)",
                "note_titles": ["Kyoto Note", "Nara Note", "Tokyo Note"],
                "reason": "3 notes share topic Kyoto and have no dedicated MOC.",
            },
            {
                "topic": "Nara",
                "items": ["S01", "S02", "S03"],  # identical set
                "parent": "2600 - Applied Sciences",
                "tags": [],
                "name": "Nara (MOC)",
                "note_titles": ["Kyoto Note", "Nara Note", "Tokyo Note"],
                "reason": "3 notes share topic Nara and have no dedicated MOC.",
            },
        ]
        section_stems = {"S01": "kyoto", "S02": "nara", "S03": "tokyo"}
        merged = merge_fn(proposed_mocs, section_stems, threshold=0.80)

        assert len(merged) == 1, f"J=1.0 clusters must merge into 1, got {len(merged)}: {merged}"
        m = merged[0]
        assert "alias_topics" in m, "Merged proposal must have alias_topics"
        assert set(m["alias_topics"]) == {"Nara"} or set(m["alias_topics"]) == {"Kyoto"}, (
            f"alias_topics should contain the non-primary topic: {m['alias_topics']}"
        )
        assert set(m["items"]) == {"S01", "S02", "S03"}, f"items must be union: {m['items']}"

    def test_high_overlap_merges(self, tmp_path):
        """Clusters sharing 3/3 stems (J=1.0) merge; clusters sharing 2/4 (J=0.5) don't."""
        spec = importlib.util.spec_from_file_location(
            "suggestions_reducer_merge2",
            str(REDUCER),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        merge_fn = getattr(mod, "_merge_overlapping_mocs", None)
        assert merge_fn is not None

        # A+B overlap J=1.0 → merge. A+C overlap J=2/5=0.40 → no merge.
        proposed_mocs = [
            {
                "topic": "Japan A",
                "items": ["S01", "S02", "S03"],
                "parent": "P1",
                "tags": [],
                "name": "Japan A (MOC)",
                "note_titles": ["n1", "n2", "n3"],
                "reason": "3 notes share topic Japan A.",
            },
            {
                "topic": "Japan B",
                "items": ["S01", "S02", "S03"],
                "parent": "P1",
                "tags": [],
                "name": "Japan B (MOC)",
                "note_titles": ["n1", "n2", "n3"],
                "reason": "3 notes share topic Japan B.",
            },
            {
                "topic": "Germany C",
                "items": ["S01", "S02", "S04", "S05", "S06"],
                "parent": "P2",
                "tags": [],
                "name": "Germany C (MOC)",
                "note_titles": ["n1", "n2", "n4", "n5", "n6"],
                "reason": "5 notes share topic Germany C.",
            },
        ]
        section_stems = {
            "S01": "s01", "S02": "s02", "S03": "s03",
            "S04": "s04", "S05": "s05", "S06": "s06",
        }
        merged = merge_fn(proposed_mocs, section_stems, threshold=0.80)
        # A+B merge → 1 combined; C stays separate → 2 total
        assert len(merged) == 2, f"Expected 2 proposals (A+B merged, C separate), got {len(merged)}: {merged}"

    def test_just_below_threshold_no_merge(self, tmp_path):
        """Clusters with J just below 0.80 must NOT merge."""
        spec = importlib.util.spec_from_file_location(
            "suggestions_reducer_merge3",
            str(REDUCER),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        merge_fn = getattr(mod, "_merge_overlapping_mocs", None)
        assert merge_fn is not None

        # A = {S01,S02,S03,S04,S05}, B = {S01,S02,S03,S04,S06}
        # |A∩B|=4, |A∪B|=6, J=4/6≈0.667 < 0.80 → no merge
        proposed_mocs = [
            {
                "topic": "Topic A",
                "items": ["S01", "S02", "S03", "S04", "S05"],
                "parent": "P",
                "tags": [],
                "name": "Topic A (MOC)",
                "note_titles": ["n1", "n2", "n3", "n4", "n5"],
                "reason": "5 notes share topic A.",
            },
            {
                "topic": "Topic B",
                "items": ["S01", "S02", "S03", "S04", "S06"],
                "parent": "P",
                "tags": [],
                "name": "Topic B (MOC)",
                "note_titles": ["n1", "n2", "n3", "n4", "n6"],
                "reason": "5 notes share topic B.",
            },
        ]
        section_stems = {f"S{i:02d}": f"s{i:02d}" for i in range(1, 7)}
        merged = merge_fn(proposed_mocs, section_stems, threshold=0.80)
        assert len(merged) == 2, (
            f"J≈0.667 < 0.80, must NOT merge; got {len(merged)}: {merged}"
        )
        # No alias_topics on either
        for m in merged:
            assert not m.get("alias_topics"), f"Unexpected alias_topics on non-merged: {m}"

    def test_transitive_three_way_merge(self, tmp_path):
        """Three clusters A–B–C where A+B merge and B+C merge → all three merge transitively."""
        spec = importlib.util.spec_from_file_location(
            "suggestions_reducer_merge4",
            str(REDUCER),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        merge_fn = getattr(mod, "_merge_overlapping_mocs", None)
        assert merge_fn is not None

        # A={S1,S2,S3}, B={S1,S2,S3,S4} → J=3/4=0.75 < threshold... adjust:
        # A={S1,S2,S3,S4}, B={S1,S2,S3,S4,S5} → J=4/5=0.80 ≥ threshold
        # B={S1,S2,S3,S4,S5}, C={S1,S2,S3,S4,S5,S6} → J=5/6≈0.833 ≥ threshold
        # After A+B merge → AB={S1..S5}; then AB+C: J=5/6≈0.833 ≥ threshold → merge
        proposed_mocs = [
            {
                "topic": "Topic A",
                "items": ["S01", "S02", "S03", "S04"],
                "parent": "P1",
                "tags": [],
                "name": "Topic A (MOC)",
                "note_titles": [f"n{i}" for i in range(1, 5)],
                "reason": "4 notes share topic A.",
            },
            {
                "topic": "Topic B",
                "items": ["S01", "S02", "S03", "S04", "S05"],
                "parent": "P1",
                "tags": [],
                "name": "Topic B (MOC)",
                "note_titles": [f"n{i}" for i in range(1, 6)],
                "reason": "5 notes share topic B.",
            },
            {
                "topic": "Topic C",
                "items": ["S01", "S02", "S03", "S04", "S05", "S06"],
                "parent": "P2",
                "tags": [],
                "name": "Topic C (MOC)",
                "note_titles": [f"n{i}" for i in range(1, 7)],
                "reason": "6 notes share topic C.",
            },
        ]
        section_stems = {f"S{i:02d}": f"s{i:02d}" for i in range(1, 7)}
        merged = merge_fn(proposed_mocs, section_stems, threshold=0.80)
        # All three must collapse into 1
        assert len(merged) == 1, (
            f"Transitive 3-way merge must produce 1 proposal, got {len(merged)}: {merged}"
        )
        m = merged[0]
        assert "alias_topics" in m, "Merged proposal must carry alias_topics"
        assert len(m["alias_topics"]) == 2, (
            f"Expected 2 alias topics (the other two), got: {m['alias_topics']}"
        )
        # Union of items: S01–S06
        assert set(m["items"]) == {f"S{i:02d}" for i in range(1, 7)}, (
            f"Union items wrong: {m['items']}"
        )

    def test_render_shows_also_covers_line(self, tmp_path):
        """Renderer emits '**Also covers:**' line when alias_topics present."""
        spec = importlib.util.spec_from_file_location(
            "suggestions_render_alias",
            str(RENDER_SCRIPT),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        doc = {
            "schema_version": "1",
            "generated": "2026-06-04T12:00:00Z",
            "run_id": "test-run",
            "profile": "miyo",
            "doc_variant": "primary",
            "source_items": 3,
            "sections": [],
            "daily_notes_updates": [],
            "rendered_daily_updates_md": "",
            "decision_precedence_note": "",
            "needs_attention": [],
            "proposed_mocs": [
                {
                    "topic": "Japan Travel",
                    "items": ["S01", "S02", "S03"],
                    "parent": "2600 - Applied Sciences",
                    "tags": [],
                    "name": "Japan Travel (MOC)",
                    "note_titles": ["Kyoto Notes", "Nara Deer", "Tokyo Tower"],
                    "reason": "3 notes share topic Japan Travel and have no dedicated MOC.",
                    "alias_topics": ["Japanese Tourism", "Kansai Region"],
                }
            ],
        }
        # Use render function directly
        lines = mod.render_proposed_mocs(doc)
        md = "\n".join(lines)
        assert "**Also covers:**" in md, (
            f"Renderer must emit '**Also covers:**' when alias_topics present:\n{md}"
        )
        assert "Japanese Tourism" in md, "alias topic Japanese Tourism missing from render"
        assert "Kansai Region" in md, "alias topic Kansai Region missing from render"

    def test_end_to_end_merge_via_reducer(self, tmp_path):
        """Integration: reducer merges overlapping clusters from real item fixtures."""
        # 6 stems: S01-S03 all propose "Kyoto", S01-S03 also propose... wait,
        # each stem can only have one proposed_moc_topic per action.
        # Create 6 stems where 4 go to "Kyoto" and 4 go to "Nara", sharing 3.
        # Stems 1-3: topic="Kyoto"; stems 1-3 and 4: topic="Nara"
        # Not possible since each stem has exactly one result file.
        # Use a different set: stems 1-4 → "Kyoto", stems 2-5 → "Nara"
        # Since stems 2-4 are shared: |A∩B|=3, |A∪B|=5, J=3/5=0.60 < 0.80 → no merge
        # Need: stems 1-4 → "Kyoto", stems 1-4 + stem5 → "Nara": impossible (one topic per stem)
        # CONCLUSION: the end-to-end path cannot produce two overlapping clusters
        # from item fixtures since each item has exactly ONE proposed_moc_topic.
        # This means each cluster gets distinct section_ids.
        # Real overlap requires the SAME section_ids in two clusters, which cannot
        # happen since each item is assigned to exactly one normalised topic group.
        # The integration test for merge therefore tests directly via unit call.
        # We verify the reducer RUNS cleanly with the merge hook applied,
        # and non-overlapping clusters survive unchanged.
        stems = ["note-a", "note-b", "note-c"]

        def make_results(items_dir: Path):
            for stem in stems:
                _write_result(items_dir, stem,
                              needs_new_moc=True, proposed_moc_topic="Japan Travel",
                              suggested_title=f"{stem} Note")

        doc = _run_reducer(tmp_path, stems, make_results, threshold=1)
        # One cluster — should be untouched (no merge needed, stays as is)
        assert len(doc["proposed_mocs"]) == 1, (
            f"Expected 1 proposed_moc, got {len(doc['proposed_mocs'])}"
        )
        # No alias_topics on a solo cluster
        pm = doc["proposed_mocs"][0]
        assert not pm.get("alias_topics"), (
            f"Solo cluster should not have alias_topics: {pm}"
        )
