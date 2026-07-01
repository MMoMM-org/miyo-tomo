#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_topic_normalization.py — Tests for strip_moc_marker() + integration.

RED-first TDD for the bug fix that ensures proposed_moc_topic is always bare
(no trailing " MOC" / " (MOC)" / "(MOC)") before clustering and display.

Bug confirmed: Analyst emits mixed forms ("Board Games" vs "Board Games (MOC)")
which hash to different normalise_topic() keys and produce duplicate Proposed MOC
clusters for the same real MOC.

Fix: strip_moc_marker() in lib/topic_clusters.py, applied at:
  1. build_topic_clusters() input — bare topic becomes the cluster key+display
  2. suggestions-reducer.py Per-Atomic **Note:** line — bare topic shown
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.topic_clusters import (  # noqa: E402
    ClusterCandidate,
    build_topic_clusters,
    strip_moc_marker,
)

# Load suggestions-reducer via importlib (hyphen-less for import)
_sr_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py"
)
_sr_mod = importlib.util.module_from_spec(_sr_spec)
_sr_spec.loader.exec_module(_sr_mod)

_ensure_moc_suffix = _sr_mod._ensure_moc_suffix
_enrich_proposed_mocs = _sr_mod._enrich_proposed_mocs


def _candidate(
    section_id: str,
    topic: str,
    parent: str = "",
    tags: list[str] | None = None,
) -> ClusterCandidate:
    return ClusterCandidate(
        section_id=section_id,
        topic=topic,
        parent=parent,
        tags=list(tags or []),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. strip_moc_marker unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStripMocMarker:
    def test_bare_topic_unchanged(self):
        assert strip_moc_marker("Board Games") == "Board Games"

    def test_strip_trailing_moc_suffix(self):
        assert strip_moc_marker("Board Games MOC") == "Board Games"

    def test_strip_trailing_moc_in_parens(self):
        assert strip_moc_marker("Board Games (MOC)") == "Board Games"

    def test_strip_moc_no_space_before_paren(self):
        assert strip_moc_marker("Board Games(MOC)") == "Board Games"

    def test_case_insensitive(self):
        assert strip_moc_marker("board games moc") == "board games"

    def test_case_insensitive_parens(self):
        assert strip_moc_marker("board games (moc)") == "board games"

    def test_guard_standalone_moc(self):
        """Standalone "MOC" must not be emptied."""
        assert strip_moc_marker("MOC") == "MOC"

    def test_guard_standalone_moc_in_parens(self):
        """Standalone "(MOC)" must not be emptied."""
        assert strip_moc_marker("(MOC)") == "(MOC)"

    def test_leading_moc_not_stripped(self):
        """Only trailing — 'MOC Design Patterns' must stay untouched."""
        assert strip_moc_marker("MOC Design Patterns") == "MOC Design Patterns"

    def test_mid_moc_not_stripped(self):
        """Mid-string MOC must not be touched."""
        assert strip_moc_marker("Using MOC Patterns") == "Using MOC Patterns"

    def test_whitespace_tolerant(self):
        assert strip_moc_marker("Board Games  (MOC)  ") == "Board Games"

    def test_empty_string(self):
        assert strip_moc_marker("") == ""

    # W1: word-boundary guards — must NOT strip mid-word "moc"
    def test_no_strip_biomoc(self):
        """'biomoc' ends with 'moc' but has no boundary — must be unchanged."""
        assert strip_moc_marker("biomoc") == "biomoc"

    def test_no_strip_thermoc(self):
        """'Thermoc' ends with 'moc' but has no boundary — must be unchanged."""
        assert strip_moc_marker("Thermoc") == "Thermoc"

    def test_no_strip_mocha(self):
        """'Mocha' does not end with 'moc' — must be unchanged."""
        assert strip_moc_marker("Mocha") == "Mocha"

    # W3: iterative strip — double-suffix must be fully removed in one call
    def test_double_suffix_stripped(self):
        """'Board Games (MOC) (MOC)' must yield 'Board Games' (iterative strip)."""
        assert strip_moc_marker("Board Games (MOC) (MOC)") == "Board Games"

    # ── Phase 2 (F-55 / spec 028 T2.2): suffix is a parameter ────────────────
    def test_explicit_miyo_suffix_parity_parens(self):
        """Passing the miyo suffix reproduces the legacy '(MOC)' strip."""
        assert strip_moc_marker("Board Games (MOC)", " (MOC)") == "Board Games"

    def test_explicit_miyo_suffix_parity_space_form(self):
        """The bare ' MOC' word form is still stripped when suffix is ' (MOC)'."""
        assert strip_moc_marker("Board Games MOC", " (MOC)") == "Board Games"

    def test_explicit_miyo_suffix_case_insensitive(self):
        assert strip_moc_marker("board games (moc)", " (MOC)") == "board games"

    def test_empty_suffix_is_noop(self):
        """Empty suffix (lyt) strips nothing — the marker is preserved verbatim."""
        assert strip_moc_marker("Board Games (MOC)", "") == "Board Games (MOC)"
        assert strip_moc_marker("Board Games MOC", "") == "Board Games MOC"

    def test_build_topic_clusters_empty_suffix_keeps_marker(self):
        """With suffix='' the marker is not stripped, so marked/bare topics do
        NOT merge and the display topic keeps its marker."""
        items = [
            _candidate("S01", "Board Games (MOC)"),
            _candidate("S02", "Board Games (MOC)"),
        ]
        clusters = build_topic_clusters(items, threshold=2, suffix="")
        assert clusters[0]["topic"] == "Board Games (MOC)", (
            f"empty suffix must keep marker; got {clusters[0]['topic']!r}"
        )

    def test_build_topic_clusters_miyo_suffix_strips(self):
        """With the miyo suffix the marker is stripped (parity with default)."""
        items = [
            _candidate("S01", "Board Games (MOC)"),
            _candidate("S02", "Board Games"),
        ]
        clusters = build_topic_clusters(items, threshold=2, suffix=" (MOC)")
        assert clusters[0]["topic"] == "Board Games"
        assert clusters[0]["items"] == ["S01", "S02"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Clustering merges mixed-form topics into one cluster
# ─────────────────────────────────────────────────────────────────────────────


class TestClusteringMergesMixedForms:
    def test_bare_and_moc_suffix_merge(self):
        """'Board Games' and 'Board Games MOC' must land in the same cluster."""
        items = [
            _candidate("S01", "Board Games"),
            _candidate("S02", "Board Games MOC"),
            _candidate("S03", "Board Games (MOC)"),
        ]
        clusters = build_topic_clusters(items, threshold=2)
        assert len(clusters) == 1, f"Expected 1 cluster, got {len(clusters)}: {clusters}"
        assert clusters[0]["items"] == ["S01", "S02", "S03"]

    def test_cluster_display_topic_is_bare(self):
        """Cluster display topic must be the bare form, no MOC marker."""
        items = [
            _candidate("S01", "Board Games"),
            _candidate("S02", "Board Games (MOC)"),
            _candidate("S03", "Board Games MOC"),
        ]
        clusters = build_topic_clusters(items, threshold=2)
        assert clusters[0]["topic"] == "Board Games", (
            f"Expected bare 'Board Games', got '{clusters[0]['topic']}'"
        )

    def test_moc_first_display_topic_is_still_bare(self):
        """Even when the first occurrence has a MOC marker, display topic is bare."""
        items = [
            _candidate("S01", "Board Games (MOC)"),
            _candidate("S02", "Board Games"),
            _candidate("S03", "Board Games MOC"),
        ]
        clusters = build_topic_clusters(items, threshold=2)
        assert clusters[0]["topic"] == "Board Games", (
            f"Expected bare 'Board Games', got '{clusters[0]['topic']}'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Proposed MOC name has suffix ONCE; reason shows bare topic
# ─────────────────────────────────────────────────────────────────────────────


class TestProposedMocEnrichment:
    def _make_proposed_moc(self, topic: str, items: list[str]) -> dict:
        return {"topic": topic, "items": items, "parent": "", "tags": []}

    def test_moc_name_has_suffix_once(self):
        """_enrich_proposed_mocs must yield 'X (MOC)' not 'X (MOC) (MOC)'."""
        pm = self._make_proposed_moc("Board Games", ["S01", "S02"])
        _enrich_proposed_mocs([pm], {"S01": "Catan", "S02": "Wingspan"}, " (MOC)")
        assert pm["name"] == "Board Games (MOC)", f"Got: {pm['name']}"

    def test_reason_shows_bare_topic(self):
        """reason must show bare topic, not 'Board Games (MOC)'."""
        pm = self._make_proposed_moc("Board Games", ["S01", "S02"])
        _enrich_proposed_mocs([pm], {"S01": "Catan", "S02": "Wingspan"}, " (MOC)")
        assert "Board Games (MOC)" not in pm["reason"], (
            f"reason must not contain the MOC-suffixed form; got: {pm['reason']}"
        )
        assert "Board Games" in pm["reason"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Per-Atomic Note line shows bare topic (via render_atomic_action)
# ─────────────────────────────────────────────────────────────────────────────


class TestAtomicNoteLine:
    def test_note_line_shows_bare_topic(self):
        """The **Note:** line for a needs_new_moc action must show the bare topic."""
        render_create_atomic_note = _sr_mod.render_create_atomic_note
        action = {
            "action": "create_atomic_note",
            "suggested_title": "Gloomhaven Review",
            "needs_new_moc": True,
            "proposed_moc_topic": "Board Games (MOC)",
            "tags_to_add": [],
            "candidate_mocs": [],
        }
        result = render_create_atomic_note(action, "inbox-item")
        # The **Note:** line must contain bare "Board Games" but not "(MOC)"
        note_line = next(
            (line for line in result.split("\n") if "No good thematic MOC" in line),
            None,
        )
        assert note_line is not None, "Expected a **Note:** line for needs_new_moc"
        assert "Board Games (MOC)" not in note_line, (
            f"Note line must not show MOC-suffixed topic; got: {note_line}"
        )
        assert "Board Games" in note_line, (
            f"Note line must show bare topic; got: {note_line}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Real-case regression: 3 items (2 bare + 1 with suffix) → EXACTLY one MOC
# ─────────────────────────────────────────────────────────────────────────────


class TestRealCaseRegression:
    def test_catan_wingspan_gloomhaven_one_moc(self):
        """Catan/Wingspan with bare + Gloomhaven with (MOC) must yield ONE cluster."""
        items = [
            _candidate("S01", "Board Games", tags=["topic/games/boardgames/catan"]),
            _candidate("S02", "Board Games", tags=["topic/games/boardgames/wingspan"]),
            _candidate("S03", "Board Games (MOC)", tags=["topic/games/boardgames/gloomhaven"]),
        ]
        clusters = build_topic_clusters(items, threshold=2)
        assert len(clusters) == 1, (
            f"Expected exactly 1 Proposed MOC cluster, got {len(clusters)}: {clusters}"
        )
        cluster = clusters[0]
        assert cluster["items"] == ["S01", "S02", "S03"], (
            f"All 3 items must be in the cluster; got {cluster['items']}"
        )
        # Enrich and verify final MOC name
        section_titles = {"S01": "Catan", "S02": "Wingspan", "S03": "Gloomhaven"}
        pm = {"topic": cluster["topic"], "items": cluster["items"], "parent": "", "tags": []}
        _enrich_proposed_mocs([pm], section_titles, " (MOC)")
        assert pm["name"] == "Board Games (MOC)", f"Final MOC name: {pm['name']}"
        assert pm["note_titles"] == ["Catan", "Wingspan", "Gloomhaven"]
