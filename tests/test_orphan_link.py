#!/usr/bin/env python3
# version: 0.4.0
"""test_orphan_link.py — Behavioural tests for lib.orphan_link (spec 021 T2.3, T6.2).

The case-(a) orphan pass runs AFTER moc_cache_loader provides cache.entries. It
scans entries[up_state=="absent"] filtered by `kinds` (default notes-only, ADR-12),
scores each against entries[kind=="moc"] by topic-keyword overlap (the Phase-5/6
approach), and emits one OrphanLinkSuggestion per orphan, ordered link_existing
first (ADR-12):

  - ≥1 MOC at/above LINK_THRESHOLD → mode="link_existing", candidates=top-3
    [{target_moc, score}] sorted by score DESC (OQ-4).
  - no MOC clears the threshold      → mode="create_new" + a reason string.

H2: this is a NEW pass over the cache, NOT an edit to Phase 6 duplicates_skipped.
H3: orphan MOCs are eligible simply because they are cache entries — no relaxing
of restrict_to_atomic_note_paths (that pre-filter is untouched; not exercised here).
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.orphan_link import LINK_THRESHOLD, emit_orphan_suggestions  # noqa: E402
from lib.moc_tags import EXCLUDE_MOC_TAG  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _entry(
    stem: str,
    *,
    kind: str = "note",
    up_state: str = "absent",
    topics: list[str] | None = None,
    path: str | None = None,
) -> dict:
    return {
        "path": path or f"Atlas/202 Notes/{stem}.md",
        "stem": stem,
        "kind": kind,
        "title": stem,
        "topics": topics or [],
        "up_state": up_state,
        "up_target": None,
        "up_source": None,
        "tags": [],
    }


def _moc(stem: str, topics: list[str], *, up_state: str = "valid") -> dict:
    return _entry(
        stem, kind="moc", up_state=up_state, topics=topics,
        path=f"Atlas/200 Maps/{stem}.md",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Orphan selection — entries[up_state=="absent"], notes AND MOCs
# ──────────────────────────────────────────────────────────────────────────────

def test_only_absent_entries_are_orphans():
    """Entries with up_state valid/broken are NOT orphans; only absent ones are."""
    entries = [
        _moc("Knowledge", ["pkm", "notes"]),
        _entry("HasParent", up_state="valid", topics=["pkm"]),
        _entry("Broken", up_state="broken", topics=["pkm"]),
        _entry("Orphan", up_state="absent", topics=["pkm", "notes"]),
    ]
    out = emit_orphan_suggestions(entries)
    stems = {s["stem"] for s in out}
    assert stems == {"Orphan"}, f"only absent entries are orphans; got {stems}"


def test_orphan_moc_is_eligible_when_kinds_includes_moc():
    """An orphan MOC (kind==moc, up_state==absent) is eligible when kinds asks (H3)."""
    entries = [
        _moc("Parent", ["pkm", "notes", "linking"]),
        _moc("OrphanMOC", ["pkm", "notes"], up_state="absent"),
    ]
    out = emit_orphan_suggestions(entries, kinds=("note", "moc"))
    by_stem = {s["stem"]: s for s in out}
    assert "OrphanMOC" in by_stem
    assert by_stem["OrphanMOC"]["kind"] == "moc"


# ──────────────────────────────────────────────────────────────────────────────
# link_existing — top-3, sorted by score DESC, threshold-gated
# ──────────────────────────────────────────────────────────────────────────────

def test_orphan_matching_moc_emits_link_existing():
    entries = [
        _moc("Knowledge", ["pkm", "notes", "linking"]),
        _entry("Orphan", up_state="absent", topics=["pkm", "notes", "linking"]),
    ]
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "Orphan")
    assert s["mode"] == "link_existing"
    assert s["candidates"][0]["target_moc"] == "Knowledge"
    assert s["candidates"][0]["score"] > 0


def test_link_existing_caps_at_top_3_sorted_desc():
    orphan_topics = ["a", "b", "c", "d"]
    entries = [
        _moc("M4", ["a", "b", "c", "d"]),   # full overlap → highest
        _moc("M3", ["a", "b", "c"]),
        _moc("M2", ["a", "b"]),
        _moc("M1", ["a"]),
        _entry("Orphan", up_state="absent", topics=orphan_topics),
    ]
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "Orphan")
    assert s["mode"] == "link_existing"
    cands = s["candidates"]
    assert len(cands) == 3, f"top-3 cap (OQ-4); got {len(cands)}"
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores, reverse=True), f"must be DESC; got {scores}"
    assert [c["target_moc"] for c in cands] == ["M4", "M3", "M2"]


# ──────────────────────────────────────────────────────────────────────────────
# create_new — no MOC clears the threshold → reason
# ──────────────────────────────────────────────────────────────────────────────

def test_orphan_with_no_match_emits_create_new_with_reason():
    entries = [
        _moc("Cooking", ["recipes", "food"]),
        _entry("Orphan", up_state="absent", topics=["quantum", "physics"]),
    ]
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "Orphan")
    assert s["mode"] == "create_new"
    assert isinstance(s.get("reason"), str) and s["reason"], "create_new must carry a reason"
    assert not s.get("candidates"), "create_new has no link candidates"


def test_orphan_with_no_topics_emits_create_new():
    entries = [
        _moc("Knowledge", ["pkm", "notes"]),
        _entry("Topicless", up_state="absent", topics=[]),
    ]
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "Topicless")
    assert s["mode"] == "create_new"
    assert s["reason"]


def test_below_threshold_match_is_create_new():
    """A weak overlap below LINK_THRESHOLD → create_new, not link_existing."""
    # 1 shared topic out of 5 orphan topics → ratio 0.2, below a 0.5-ish threshold.
    entries = [
        _moc("Weak", ["pkm"]),
        _entry("Orphan", up_state="absent", topics=["pkm", "a", "b", "c", "d"]),
    ]
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "Orphan")
    assert s["mode"] == "create_new", (
        f"weak overlap must not produce link_existing; got {s}"
    )
    # The orphan DID share a topic with "Weak" (just below threshold), so the
    # reason must come from the had_any_overlap=True branch of _build_reason —
    # distinguishing it from the no-overlap-at-all branch.
    assert "link threshold" in s["reason"], (
        f"below-threshold reason must reflect partial overlap; got {s['reason']!r}"
    )


def test_overlap_exactly_at_threshold_is_link_existing():
    """Boundary: overlap ratio == LINK_THRESHOLD exactly → link_existing (>= gate).

    Orphan has 2 topics, the MOC shares exactly 1 → ratio 1/2 == LINK_THRESHOLD
    (0.5). Proves the gate is inclusive (>=), per OQ-4.
    """
    # Construct an orphan whose ratio against the MOC equals LINK_THRESHOLD.
    # With 2 orphan topics and 1 shared, ratio = 0.5; assert the constant rather
    # than a hardcoded number so the test tracks the threshold if it ever moves.
    assert LINK_THRESHOLD == 0.5, (
        "this boundary fixture assumes a 2-topic / 1-shared = 0.5 ratio; "
        f"adjust the fixture if LINK_THRESHOLD changes (now {LINK_THRESHOLD})"
    )
    entries = [
        _moc("Edge", ["pkm", "unrelated"]),  # shares exactly 1 of the orphan's 2
        _entry("Orphan", up_state="absent", topics=["pkm", "notes"]),
    ]
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "Orphan")
    assert s["mode"] == "link_existing", (
        f"ratio == LINK_THRESHOLD must link (inclusive >=); got {s}"
    )
    assert s["candidates"][0]["target_moc"] == "Edge"
    assert s["candidates"][0]["score"] == LINK_THRESHOLD


# ──────────────────────────────────────────────────────────────────────────────
# Shape + edge cases
# ──────────────────────────────────────────────────────────────────────────────

def test_suggestion_carries_stem_path_kind():
    entries = [
        _moc("Knowledge", ["pkm", "notes"]),
        _entry("Orphan", up_state="absent", topics=["pkm", "notes"],
               path="Atlas/202 Notes/Sub/Orphan.md"),
    ]
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "Orphan")
    assert s["path"] == "Atlas/202 Notes/Sub/Orphan.md"
    assert s["kind"] == "note"
    assert s["stem"] == "Orphan"


def test_empty_entries_returns_empty():
    assert emit_orphan_suggestions([]) == []


def test_no_orphans_returns_empty():
    entries = [
        _moc("Knowledge", ["pkm"]),
        _entry("HasParent", up_state="valid", topics=["pkm"]),
    ]
    assert emit_orphan_suggestions(entries) == []


def test_orphan_does_not_match_itself_when_it_is_a_moc():
    """An orphan MOC must not be offered as a link candidate to itself."""
    entries = [
        _moc("OrphanMOC", ["pkm", "notes"], up_state="absent"),
    ]
    out = emit_orphan_suggestions(entries, kinds=("moc",))
    s = next(x for x in out if x["stem"] == "OrphanMOC")
    # No other MOC to link to → create_new; self must be excluded from candidates.
    assert s["mode"] == "create_new"


# ──────────────────────────────────────────────────────────────────────────────
# kinds filter (ADR-12 / T6.2) — default notes-only; opt-in MOCs
# ──────────────────────────────────────────────────────────────────────────────

def test_default_excludes_moc_orphans():
    """Default kinds=("note",) → orphan MOCs are NOT emitted (whole-vault scan)."""
    entries = [
        _moc("Parent", ["pkm", "notes", "linking"]),
        _moc("OrphanMOC", ["pkm", "notes"], up_state="absent"),
        _entry("OrphanNote", up_state="absent", topics=["pkm", "notes"]),
    ]
    out = emit_orphan_suggestions(entries)  # default
    stems = {s["stem"] for s in out}
    assert stems == {"OrphanNote"}, f"default must exclude MOC orphans; got {stems}"


def test_kinds_moc_only_returns_only_mocs():
    """kinds=("moc",) → the focused MOC-uplink audit: only orphan MOCs."""
    entries = [
        _moc("Parent", ["pkm", "notes", "linking"]),
        _moc("OrphanMOC", ["pkm", "notes"], up_state="absent"),
        _entry("OrphanNote", up_state="absent", topics=["pkm", "notes"]),
    ]
    out = emit_orphan_suggestions(entries, kinds=("moc",))
    stems = {s["stem"] for s in out}
    assert stems == {"OrphanMOC"}, f"moc-only must exclude note orphans; got {stems}"


def test_kinds_both_returns_notes_and_mocs():
    entries = [
        _moc("Parent", ["pkm", "notes", "linking"]),
        _moc("OrphanMOC", ["pkm", "notes"], up_state="absent"),
        _entry("OrphanNote", up_state="absent", topics=["pkm", "notes"]),
    ]
    out = emit_orphan_suggestions(entries, kinds=("note", "moc"))
    stems = {s["stem"] for s in out}
    assert stems == {"OrphanMOC", "OrphanNote"}


# ──────────────────────────────────────────────────────────────────────────────
# Display ordering (ADR-12 / T6.2) — link_existing first, by top score DESC
# ──────────────────────────────────────────────────────────────────────────────

def test_link_existing_sorted_before_create_new():
    """Most-actionable first: every link_existing precedes every create_new."""
    entries = [
        _moc("Knowledge", ["pkm", "notes", "linking"]),
        # A: no overlap → create_new
        _entry("AlphaOrphan", up_state="absent", topics=["quantum", "physics"]),
        # B: full overlap → link_existing
        _entry("BetaOrphan", up_state="absent", topics=["pkm", "notes", "linking"]),
    ]
    out = emit_orphan_suggestions(entries)
    modes = [s["mode"] for s in out]
    assert modes == ["link_existing", "create_new"], (
        f"link_existing must sort ahead of create_new regardless of input order; got {modes}"
    )


def test_link_existing_sorted_by_top_candidate_score_desc():
    """Within link_existing, higher top-candidate score comes first."""
    entries = [
        _moc("Strong", ["a", "b", "c", "d"]),
        _moc("Weakish", ["a", "b"]),
        # Low first in input order: shares 2/4 → 0.5
        _entry("LowScore", up_state="absent", topics=["a", "b", "x", "y"], path="Atlas/202 Notes/LowScore.md"),
        # High second in input order: shares 4/4 → 1.0
        _entry("HighScore", up_state="absent", topics=["a", "b", "c", "d"], path="Atlas/202 Notes/HighScore.md"),
    ]
    out = emit_orphan_suggestions(entries)
    link = [s["stem"] for s in out if s["mode"] == "link_existing"]
    assert link[:2] == ["HighScore", "LowScore"], (
        f"link_existing must be ordered by top-candidate score DESC; got {link}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# exclude/moc tag (ADR-13 B-moc / PRD F8 AC4, AC5) — T7.2
# ──────────────────────────────────────────────────────────────────────────────

def _moc_with_tags(stem: str, topics: list[str], tags: list[str], *, up_state: str = "valid") -> dict:
    """Build a MOC entry carrying explicit tags (mirrors T7.1 cache shape)."""
    return {
        "path": f"Atlas/200 Maps/{stem}.md",
        "stem": stem,
        "kind": "moc",
        "title": stem,
        "topics": topics,
        "up_state": up_state,
        "up_target": None,
        "up_source": None,
        "tags": tags,
    }


def test_excluded_moc_not_emitted_by_orphan_audit():
    """AC4/AC5: a MOC tagged exclude/moc is NOT emitted by emit_orphan_suggestions(kinds=("moc",)).

    The MOC is orphaned (up_state==absent) but carries the exclude tag — it must be
    silently skipped in the audit output.
    """
    entries = [
        _moc_with_tags("RootIndex", ["index", "overview"], [EXCLUDE_MOC_TAG], up_state="absent"),
        _moc("Parent", ["pkm", "notes"]),
    ]
    out = emit_orphan_suggestions(entries, kinds=("moc",))
    stems = {s["stem"] for s in out}
    assert "RootIndex" not in stems, (
        f"MOC tagged {EXCLUDE_MOC_TAG!r} must NOT appear in orphan audit; got {stems}"
    )


def test_excluded_moc_remains_in_link_candidate_pool():
    """AC4: excluded MOC stays in the link-candidate pool (pool-retention invariant).

    An orphan note is scored against all MOC entries including the excluded one.
    The excluded MOC must appear as a candidate in the orphan note's suggestion —
    proving it was NOT removed from the scoring pool, only from the audit output.
    """
    excluded_moc = _moc_with_tags(
        "RootIndex", ["pkm", "notes", "overview"], [EXCLUDE_MOC_TAG], up_state="absent"
    )
    orphan_note = _entry("MyNote", up_state="absent", topics=["pkm", "notes", "overview"])
    entries = [excluded_moc, orphan_note]

    out = emit_orphan_suggestions(entries, kinds=("note",))
    note_suggestion = next((s for s in out if s["stem"] == "MyNote"), None)
    assert note_suggestion is not None, "orphan note must get a suggestion"
    candidate_targets = [c["target_moc"] for c in note_suggestion.get("candidates", [])]
    assert "RootIndex" in candidate_targets, (
        f"excluded MOC {EXCLUDE_MOC_TAG!r} must remain in the link-candidate pool; "
        f"got candidates: {candidate_targets}"
    )


def test_root_moc_tagged_exclude_moc_not_flagged_as_orphan():
    """AC5: root MOC (0-index, carrying exclude/moc) is not flagged — tag-driven, no path heuristic."""
    entries = [
        _moc_with_tags("000 Index", ["home", "index"], [EXCLUDE_MOC_TAG], up_state="absent"),
        _moc("Parent", ["home"]),
    ]
    out = emit_orphan_suggestions(entries, kinds=("moc",))
    stems = {s["stem"] for s in out}
    assert "000 Index" not in stems, (
        "root MOC carrying exclude/moc must not appear in orphan audit"
    )


def test_non_excluded_moc_still_emitted():
    """Regression: MOC orphans WITHOUT the exclude tag are still emitted normally."""
    entries = [
        _moc_with_tags("NormalOrphan", ["pkm", "notes"], [], up_state="absent"),
        _moc("Parent", ["pkm", "notes", "linking"]),
    ]
    out = emit_orphan_suggestions(entries, kinds=("moc",))
    stems = {s["stem"] for s in out}
    assert "NormalOrphan" in stems, (
        "MOC orphan without exclude tag must still appear in audit output"
    )
