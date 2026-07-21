#!/usr/bin/env python3
# version: 0.2.0
"""test_target_suggest.py — Behavioural tests for lib.target_suggest (spec 030 T7.1).

On-demand candidate suggestions for two fixable garden-audit checks (Phase 7, D3):

  suggest_dead_link_targets(dead_target, stems, *, cutoff, top_n)
    difflib stem fuzzy-match of the dead wikilink target against all cache note
    stems → top_n [{target, score}] above cutoff, DESC, deterministic ties.

  suggest_repoint_mocs(note_entry, moc_entries, broken_target, *, top_n)
    orphan_link topic-overlap of the note (as pseudo-orphan) against MOCs MERGED
    with stem-similarity of the broken up-target against MOC stems (mistyped MOC),
    deduped by MOC stem, top_n, DESC.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.target_suggest import (  # noqa: E402
    suggest_dead_link_targets,
    suggest_repoint_mocs,
)


def _moc(stem: str, *, topics: list[str] | None = None, path: str | None = None) -> dict:
    return {
        "stem": stem,
        "kind": "moc",
        "path": path or f"MOCs/{stem}.md",
        "topics": topics or [],
    }


# ──────────────────────────────────────────────────────────────────────────────
# suggest_dead_link_targets — difflib stem fuzzy-match
# ──────────────────────────────────────────────────────────────────────────────

class TestDeadLinkTargets:
    def test_typo_target_surfaces_correct_stem_as_top(self):
        # "Ohne Tipfehler" (typo) → "OhneTippfehler" is the closest stem.
        stems = ["OhneTippfehler", "Something Else", "Totally Unrelated"]
        out = suggest_dead_link_targets("Ohne Tipfehler", stems)
        assert out, "expected at least one candidate"
        assert out[0]["target"] == "OhneTippfehler"
        assert 0.0 < out[0]["score"] <= 1.0

    def test_below_cutoff_noise_excluded(self):
        stems = ["Totally Unrelated Thing", "Another Random Note"]
        out = suggest_dead_link_targets("Xyzzy", stems, cutoff=0.6)
        assert out == []

    def test_empty_on_no_stems(self):
        assert suggest_dead_link_targets("Anything", []) == []

    def test_empty_dead_target_returns_empty(self):
        assert suggest_dead_link_targets("", ["A", "B"]) == []

    def test_results_sorted_desc_and_capped(self):
        # Several near-misses of "Report" — cap at top_n=3, DESC.
        stems = ["Reports", "Report ", "Reporter", "Reported", "Repost", "Zebra"]
        out = suggest_dead_link_targets("Report", stems, cutoff=0.5, top_n=3)
        assert len(out) <= 3
        scores = [c["score"] for c in out]
        assert scores == sorted(scores, reverse=True)

    def test_case_only_difference_scores_near_one(self):
        # A dead link differing from a real stem only by case is a strong fix
        # candidate (difflib is case-folded here) — the exact-string self-match
        # is excluded, but a case variant is a distinct, high-scoring stem.
        out = suggest_dead_link_targets("exact note", ["Exact Note", "Other"])
        assert out[0]["target"] == "Exact Note"
        assert out[0]["score"] == 1.0

    def test_deterministic_tie_break_is_stable(self):
        # Two stems equally close → deterministic order across repeated calls.
        stems = ["Aaa", "Aab"]
        first = suggest_dead_link_targets("Aac", stems, cutoff=0.0, top_n=2)
        second = suggest_dead_link_targets("Aac", stems, cutoff=0.0, top_n=2)
        assert first == second

    def test_self_reference_dead_target_excluded(self):
        # The dead target must never suggest itself (a note linking to its own
        # exact stem would already resolve — not a dead link).
        out = suggest_dead_link_targets("Same", ["Same", "Samey"], cutoff=0.0)
        targets = [c["target"] for c in out]
        assert "Same" not in targets


# ──────────────────────────────────────────────────────────────────────────────
# suggest_repoint_mocs — topic overlap MERGED with broken-target stem similarity
# ──────────────────────────────────────────────────────────────────────────────

class TestRepointMocs:
    def test_near_miss_moc_stem_surfaces_that_moc(self):
        # broken up-target "Writng MOC" (typo) → "Writing MOC" by stem similarity.
        note = {"stem": "Some Note", "path": "Notes/Some Note.md", "topics": []}
        mocs = [_moc("Writing MOC"), _moc("Cooking MOC"), _moc("Code MOC")]
        out = suggest_repoint_mocs(note, mocs, "Writng MOC")
        assert out, "expected a candidate from stem similarity"
        assert out[0]["target"] == "Writing MOC"

    def test_topic_overlap_moc_surfaces_even_with_different_name(self):
        # No stem similarity to the broken target, but strong topic overlap.
        note = {"stem": "Endurance", "path": "N/Endurance.md",
                "topics": ["fitness", "running", "cardio"]}
        mocs = [
            _moc("ZZZ", topics=["fitness", "running", "cardio"]),
            _moc("Unrelated", topics=["cooking"]),
        ]
        out = suggest_repoint_mocs(note, mocs, "No Match Broken Target")
        targets = [c["target"] for c in out]
        assert "ZZZ" in targets

    def test_no_topics_unrelated_mocs_excluded_by_stem_cutoff(self):
        # W1 regression: a note with NO topics (signal 1 → []) and a broken target
        # that shares only the common " MOC" suffix with the MOC stems (each ≈ 0.4,
        # below the 0.6 stem_cutoff) must yield NO candidates — without the cutoff,
        # every unrelated MOC would fill the pick list as a confident-looking-but-
        # wrong candidate. FAILS without W1's gate, passes with it.
        note = {"stem": "Some Note", "path": "N/Some Note.md", "topics": []}
        mocs = [_moc("Writing MOC"), _moc("Cooking MOC"), _moc("Fitness MOC")]
        out = suggest_repoint_mocs(note, mocs, "Zqxjv MOC")
        assert out == [], f"unrelated MOCs must not appear, got {out!r}"

    def test_merged_deduped_by_moc_stem(self):
        # A MOC that matches BOTH by stem similarity AND topic overlap appears once.
        note = {"stem": "N", "path": "N/N.md", "topics": ["writing", "prose"]}
        mocs = [_moc("Writing MOC", topics=["writing", "prose"])]
        out = suggest_repoint_mocs(note, mocs, "Writing MOC")
        stems = [c["target"] for c in out]
        assert stems.count("Writing MOC") == 1

    def test_capped_at_top_n(self):
        note = {"stem": "N", "path": "N/N.md", "topics": ["x"]}
        mocs = [_moc(f"MOC {i}", topics=["x"]) for i in range(10)]
        out = suggest_repoint_mocs(note, mocs, "MOC 0", top_n=3)
        assert len(out) <= 3

    def test_sorted_desc(self):
        note = {"stem": "N", "path": "N/N.md", "topics": ["a", "b"]}
        mocs = [
            _moc("Weak", topics=["a"]),
            _moc("Strong", topics=["a", "b"]),
        ]
        out = suggest_repoint_mocs(note, mocs, "zzz nomatch")
        scores = [c["score"] for c in out]
        assert scores == sorted(scores, reverse=True)

    def test_empty_on_no_mocs(self):
        note = {"stem": "N", "path": "N/N.md", "topics": ["a"]}
        assert suggest_repoint_mocs(note, [], "Anything") == []

    def test_result_shape_is_target_score(self):
        note = {"stem": "N", "path": "N/N.md", "topics": ["writing"]}
        mocs = [_moc("Writing MOC", topics=["writing"])]
        out = suggest_repoint_mocs(note, mocs, "Writing MOC")
        assert out
        for c in out:
            assert set(c.keys()) == {"target", "score"}
            assert isinstance(c["target"], str)
            assert 0.0 <= c["score"] <= 1.0

    def test_deterministic_across_calls(self):
        note = {"stem": "N", "path": "N/N.md", "topics": ["a", "b"]}
        mocs = [_moc("Aaa", topics=["a"]), _moc("Bbb", topics=["b"])]
        first = suggest_repoint_mocs(note, mocs, "Aab")
        second = suggest_repoint_mocs(note, mocs, "Aab")
        assert first == second
