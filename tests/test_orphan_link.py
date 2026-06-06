#!/usr/bin/env python3
# version: 0.1.0
"""test_orphan_link.py — Behavioural tests for lib.orphan_link (spec 021 T2.3).

The case-(a) orphan pass runs AFTER moc_cache_loader provides cache.entries. It
scans entries[up_state=="absent"] (notes AND MOCs), scores each against
entries[kind=="moc"] by topic-keyword overlap (the Phase-5/6 approach), and emits
one OrphanLinkSuggestion per orphan:

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

from lib.orphan_link import emit_orphan_suggestions  # noqa: E402


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


def test_orphan_moc_is_eligible():
    """An orphan MOC (kind==moc, up_state==absent) is treated like any orphan (H3)."""
    entries = [
        _moc("Parent", ["pkm", "notes", "linking"]),
        _moc("OrphanMOC", ["pkm", "notes"], up_state="absent"),
    ]
    out = emit_orphan_suggestions(entries)
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
    out = emit_orphan_suggestions(entries)
    s = next(x for x in out if x["stem"] == "OrphanMOC")
    # No other MOC to link to → create_new; self must be excluded from candidates.
    assert s["mode"] == "create_new"
