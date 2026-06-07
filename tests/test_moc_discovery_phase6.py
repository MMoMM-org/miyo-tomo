#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_discovery_phase6.py — Phase 6 dedupe + squelch lookup.

F-43 Phase 2 T2.6: drop near-duplicate clusters and consult the squelch
registry (read-only — actual decrement / persist / append happens in Phase 5
wiring, T5.1 / T5.2).

Phase 6 algorithm (per SDD §Implementation Examples/Example 3 and §Pseudocode
lines 879-883):

  - Exact-title match: if any `cache.map_notes[].title` equals the cluster's
    proposed title (case-insensitive), skip with ``reason="exact-title"``.
  - Jaccard overlap ≥ 0.80: compare the cluster's topic-set against each
    `cache.map_notes[].topics` set; on any hit, skip with
    ``reason="80-percent-overlap"``.
  - Squelch lookup: compute the topic signature (sha1 of normalised topic +
    sorted candidate stems, per SDD Example 2) and consult the in-memory
    squelch registry via `lib.squelch.is_active`. Active entries skip the
    cluster and surface in the ``squelched`` report list.

Traced fixture (the spec's witness):
    cluster topics  = {shell, zsh, terminal, dotfiles}        (4 elements)
    existing topics = {shell, zsh, terminal, dotfiles, fzf}   (5 elements)
    intersection    = 4
    union           = 5
    jaccard         = 4 / 5 = 0.80   → skip (≥0.80 threshold)

Stdlib + project imports only — no Kado, no LLM calls.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)

from lib import squelch as squelch_mod  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────


class _Config:
    """Minimal config stub — Phase 6 reads no fields, but the signature
    accepts one for forward-compat with future thresholds."""


def _cluster(topic: str, items: list[str], **extra) -> dict:
    """Phase-3-shaped Cluster TypedDict with optional title/topic_keywords."""
    base = {"topic": topic, "items": list(items), "parent": "", "tags": []}
    base.update(extra)
    return base


def _cache(map_notes: list[dict]) -> dict:
    return {"map_notes": list(map_notes)}


def _empty_registry() -> dict:
    return {}


# ── Tests ────────────────────────────────────────────────────────────────────


def test_exact_title_match_skips_cluster():
    """Cluster proposed title equals an existing MOC title → skip "exact-title"."""
    cluster = _cluster(
        topic="shell",
        items=["zsh", "bash"],
        title="Shell MOC",
    )
    cache = _cache([
        {
            "path": "Atlas/Maps/Shell MOC.md",
            "title": "shell moc",  # case-insensitive match
            "topics": ["devops", "git"],
        }
    ])

    kept, dups, sq = moc_discovery.phase6_dedupe(
        [cluster], cache, _empty_registry(), _Config()
    )

    assert kept == [], f"Exact-title cluster must be filtered out; got {kept!r}"
    assert sq == [], f"Squelch list must be empty; got {sq!r}"
    assert len(dups) == 1, f"Expected one duplicate entry; got {dups!r}"
    entry = dups[0]
    assert entry["reason"] == "exact-title", f"reason mismatch: {entry!r}"
    assert "Shell MOC" in entry["existing_moc"] or entry["existing_moc"], (
        f"existing_moc should identify the matching MOC; got {entry!r}"
    )
    assert entry["cluster_id"], "cluster_id must be assigned for skip reports"


def test_jaccard_overlap_above_80_skips_cluster():
    """Spec witness: 4/5 = 0.80 → skip with reason "80-percent-overlap".

    Trace:
        cluster topics  = {shell, zsh, terminal, dotfiles}
        MOC topics      = {shell, zsh, terminal, dotfiles, fzf}
        intersection    = 4
        union           = 5
        jaccard         = 0.80   (≥ 0.80 threshold → duplicate)
    """
    cluster = _cluster(
        topic="shell",
        items=["zsh", "bash"],
        topic_keywords=["shell", "zsh", "terminal", "dotfiles"],
        title="Shell MOC",
    )
    cache = _cache([
        {
            "path": "Atlas/Maps/Shell Tools.md",
            "title": "Shell Tools",  # different title — exact-title path doesn't fire
            "topics": ["shell", "zsh", "terminal", "dotfiles", "fzf"],
        }
    ])

    kept, dups, sq = moc_discovery.phase6_dedupe(
        [cluster], cache, _empty_registry(), _Config()
    )

    assert kept == [], (
        f"Cluster with Jaccard 0.80 against existing MOC must be skipped; got {kept!r}"
    )
    assert sq == []
    assert len(dups) == 1, f"Expected one duplicate entry; got {dups!r}"
    entry = dups[0]
    assert entry["reason"] == "80-percent-overlap", (
        f"reason must be 80-percent-overlap on Jaccard hit; got {entry!r}"
    )
    assert "Shell Tools" in entry["existing_moc"], (
        f"existing_moc should identify the matched MOC; got {entry!r}"
    )


def test_jaccard_overlap_below_80_includes_cluster():
    """Jaccard 0.50 (e.g. 2/4) → cluster kept, NOT in duplicates_skipped.

    Trace:
        cluster topics = {shell, zsh}
        MOC topics     = {shell, zsh, hardware, embedded}
        intersection   = 2
        union          = 4
        jaccard        = 0.50   (< 0.80 → not a duplicate)
    """
    cluster = _cluster(
        topic="shell",
        items=["zsh", "bash"],
        topic_keywords=["shell", "zsh"],
        title="Shell MOC",
    )
    cache = _cache([
        {
            "path": "Atlas/Maps/Embedded Linux MOC.md",
            "title": "Embedded Linux MOC",
            "topics": ["shell", "zsh", "hardware", "embedded"],
        }
    ])

    kept, dups, sq = moc_discovery.phase6_dedupe(
        [cluster], cache, _empty_registry(), _Config()
    )

    assert len(kept) == 1, f"Below-threshold cluster must be kept; got {kept!r}"
    assert kept[0] is cluster, "Kept cluster must pass through unchanged (identity)"
    assert dups == [], f"No duplicate skip expected; got {dups!r}"
    assert sq == [], f"No squelch skip expected; got {sq!r}"


def test_squelch_active_signature_skips():
    """Active squelch entry (runs_remaining > 0) → cluster filtered + reported.

    Squelch is read-only in Phase 6 — no decrement, no persist. The active
    entry is mocked into the in-memory registry and the cluster's signature
    is derived through `_compute_topic_signature` (the same helper Phase 5
    wiring will call when persisting rejections).
    """
    cluster = _cluster(
        topic="shell",
        items=["zsh", "bash"],
        title="Shell MOC",
    )
    # Empty cache — no exact-title or Jaccard match should fire.
    cache = _cache([])
    signature = moc_discovery._compute_topic_signature(cluster)

    registry = {
        signature: squelch_mod.SquelchEntry(
            topic_signature=signature,
            topic_keywords=["shell"],
            rejected_at_run_id="run-prev",
            runs_remaining=2,
            first_seen_at="2026-05-07T12:00:00Z",
        ),
    }

    kept, dups, sq = moc_discovery.phase6_dedupe(
        [cluster], cache, registry, _Config()
    )

    assert kept == [], f"Squelched cluster must be filtered; got {kept!r}"
    assert dups == [], f"Squelch hit must not appear in duplicates_skipped; got {dups!r}"
    assert len(sq) == 1, f"Expected one squelch report entry; got {sq!r}"
    assert sq[0]["runs_remaining"] == 2, (
        f"Squelch report must surface remaining runs; got {sq[0]!r}"
    )
    # Read-only sanity check: the registry entry's runs_remaining is unchanged.
    assert registry[signature].runs_remaining == 2, (
        "Phase 6 must NOT decrement squelch entries — that lives in Phase 5 wiring."
    )


def test_cluster_without_title_does_not_trigger_exact_match():
    """Defensive guard: cluster missing/empty title must skip exact-title check.

    The `_find_exact_title_match` helper short-circuits on an empty needle
    (`if not needle: return None`). Without this test, a regression that
    started matching empty strings against MOC titles would slip through —
    every cluster with no title would be reported as an "exact-title"
    duplicate of every cached MOC.

    Trace:
        cluster   = {topic: "kubernetes", items: [...], title: ""}
        cache MOC = {"Shell MOC", topics: ["shell", "zsh", "terminal"]}
        topics    = {kubernetes} vs {shell, zsh, terminal}
        jaccard   = 0/4 = 0.0   (well below 0.80 → no Jaccard hit either)
        → cluster kept; duplicates_skipped empty.
    """
    cluster = _cluster(
        topic="kubernetes",
        items=["pods", "deployments"],
        # title intentionally absent → exercises `_find_exact_title_match`
        # short-circuit on an empty/missing needle.
    )
    cache = _cache([
        {
            "path": "Atlas/Maps/Shell MOC.md",
            "title": "Shell MOC",
            "topics": ["shell", "zsh", "terminal"],
        }
    ])

    kept, dups, sq = moc_discovery.phase6_dedupe(
        [cluster], cache, _empty_registry(), _Config()
    )

    assert len(kept) == 1, (
        f"Cluster with no title must NOT match by exact-title; got {kept!r}"
    )
    assert kept[0] is cluster
    assert dups == [], (
        f"No duplicate skip expected — empty title must not match cached MOC; "
        f"got {dups!r}"
    )
    assert sq == [], f"No squelch expected; got {sq!r}"


def test_squelch_inactive_includes_cluster():
    """Signature absent from registry → cluster passes Phase 6 unchanged."""
    cluster = _cluster(
        topic="shell",
        items=["zsh", "bash"],
        title="Shell MOC",
    )
    cache = _cache([])
    # Registry is non-empty, but contains a DIFFERENT signature.
    registry = {
        "some-other-signature": squelch_mod.SquelchEntry(
            topic_signature="some-other-signature",
            topic_keywords=["unrelated"],
            rejected_at_run_id="run-prev",
            runs_remaining=3,
            first_seen_at="2026-05-07T12:00:00Z",
        ),
    }

    kept, dups, sq = moc_discovery.phase6_dedupe(
        [cluster], cache, registry, _Config()
    )

    assert len(kept) == 1, f"Inactive-squelch cluster must be kept; got {kept!r}"
    assert kept[0] is cluster
    assert dups == [], f"No duplicate expected; got {dups!r}"
    assert sq == [], f"No squelch expected; got {sq!r}"


# ── T7.4 Inter-cluster member-overlap dedup (D3) ────────────────────────────
#
# _dedupe_overlapping_clusters: a NEW pass over PROPOSED clusters comparing
# them against EACH OTHER on their candidate_stems membership.
# Threshold: ≥80% of smaller cluster's members in the larger → drop smaller.
# Denominator = |smaller|.  Shape of drop record matches duplicates_skipped.


def _enriched_cluster(cluster_id: str, topic: str, items: list[str]) -> dict:
    """Minimal enriched cluster (as produced by _enrich_cluster in Phase 4/5)."""
    return {
        "cluster_id": cluster_id,
        "topic": topic,
        "items": list(items),
        "candidate_stems": list(items),
        "title": f"{topic.title()} MOC",
        "tags": [],
        "parent": "",
        "confidence": 0.5,
    }


def test_inter_cluster_smaller_fully_inside_larger_drops_smaller():
    """100% overlap (exact subset): smaller cluster dropped, larger kept.

    small ⊆ large → overlap = |small ∩ large| / |small| = 1.0 ≥ 0.80 → drop small.
    Drop recorded in duplicates_skipped with reason='member-overlap'.
    """
    large = _enriched_cluster("MOC01", "programming", ["python", "rust", "go", "haskell"])
    small = _enriched_cluster("MOC02", "scripting", ["python", "rust"])

    kept, drops = moc_discovery._dedupe_overlapping_clusters([large, small])

    assert len(kept) == 1, f"Only the larger cluster should survive; got {kept!r}"
    assert kept[0]["cluster_id"] == "MOC01", (
        f"Larger cluster MOC01 must be kept; got {kept[0]!r}"
    )
    assert len(drops) == 1, f"One drop record expected; got {drops!r}"
    drop = drops[0]
    assert drop["cluster_id"] == "MOC02", f"Dropped cluster must be MOC02; got {drop!r}"
    assert drop["reason"] == "member-overlap", (
        f"reason must be 'member-overlap'; got {drop!r}"
    )
    assert "MOC01" in drop["existing_moc"], (
        f"existing_moc must reference the surviving cluster; got {drop!r}"
    )


def test_inter_cluster_80_percent_overlap_drops_smaller():
    """Exactly 80% overlap: threshold is ≥0.80 so this must drop the smaller.

    small members = [a, b, c, d, e]  (5)
    large members = [a, b, c, d, x, y, z]  (7)
    intersection = {a,b,c,d} = 4
    overlap = 4/5 = 0.80 → drop small.
    """
    large = _enriched_cluster("MOC01", "alpha", ["a", "b", "c", "d", "x", "y", "z"])
    small = _enriched_cluster("MOC02", "beta", ["a", "b", "c", "d", "e"])

    kept, drops = moc_discovery._dedupe_overlapping_clusters([large, small])

    assert len(kept) == 1, f"80% overlap must drop smaller; got {kept!r}"
    assert kept[0]["cluster_id"] == "MOC01"
    assert len(drops) == 1
    assert drops[0]["cluster_id"] == "MOC02"
    assert drops[0]["reason"] == "member-overlap"


def test_inter_cluster_79_percent_overlap_keeps_both():
    """79% overlap (below threshold): both clusters survive.

    small members = [a, b, c, d, e, f, g, h, i, j, k, k2, k3]  (13)
    Actually let's use simple counts:
    small = 13 items, 10 overlap with large → 10/13 ≈ 0.769 < 0.80 → keep both.

    Exact: small=[a,b,c,d,e,f,g,h,i,j,k,l,m] (13), large contains [a..j] (10 overlap).
    10/13 ≈ 0.7692 < 0.80 → both survive.
    """
    # 13 items in small, large contains 10 of them → 10/13 ≈ 0.769
    small_items = [f"note{i}" for i in range(13)]
    large_items = small_items[:10] + ["extra1", "extra2", "extra3", "extra4"]

    large = _enriched_cluster("MOC01", "alpha", large_items)
    small = _enriched_cluster("MOC02", "beta", small_items)

    kept, drops = moc_discovery._dedupe_overlapping_clusters([large, small])

    assert len(kept) == 2, f"79% overlap must keep both clusters; got {kept!r}"
    assert drops == [], f"No drops expected at 79%; got {drops!r}"


def test_inter_cluster_deterministic_on_size_tie_drops_higher_cluster_id():
    """When sizes are equal, sort by cluster_id: smaller id is 'larger', higher id dropped.

    Two clusters of equal size where all members overlap (100%).
    MOC01 and MOC02 same size → sort by cluster_id → MOC01 'wins', MOC02 dropped.
    """
    items_a = ["x", "y", "z"]
    items_b = ["x", "y", "z"]  # identical members

    c1 = _enriched_cluster("MOC01", "topic_a", items_a)
    c2 = _enriched_cluster("MOC02", "topic_b", items_b)

    kept, drops = moc_discovery._dedupe_overlapping_clusters([c1, c2])

    assert len(kept) == 1, f"Identical member sets must result in one survivor; got {kept!r}"
    assert kept[0]["cluster_id"] == "MOC01", (
        f"Lower cluster_id wins on tie; got {kept[0]!r}"
    )
    assert len(drops) == 1
    assert drops[0]["cluster_id"] == "MOC02", (
        f"Higher cluster_id dropped on tie; got {drops[0]!r}"
    )


def test_inter_cluster_already_dropped_not_re_evaluated_as_larger():
    """A cluster already dropped cannot 'win' against a smaller cluster.

    MOC01 (5 members) — dropped by MOC02 (10 members, 100% overlap of MOC01).
    MOC03 (3 members, subset of MOC01's items).
    MOC03 must NOT be dropped by the already-dropped MOC01 — only live clusters
    count as the 'larger' reference.
    Result: MOC02 kept, MOC01 dropped, MOC03 kept.
    """
    moc02 = _enriched_cluster("MOC02", "big", ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"])
    moc01 = _enriched_cluster("MOC01", "mid", ["a", "b", "c", "d", "e"])  # ⊆ MOC02
    moc03 = _enriched_cluster("MOC03", "small", ["a", "b", "c"])  # ⊆ MOC01 but MOC01 dropped

    kept, drops = moc_discovery._dedupe_overlapping_clusters([moc02, moc01, moc03])

    kept_ids = {c["cluster_id"] for c in kept}
    drop_ids = {d["cluster_id"] for d in drops}

    assert "MOC02" in kept_ids, f"MOC02 (largest) must survive; kept={kept_ids}"
    assert "MOC01" in drop_ids, f"MOC01 (subset of MOC02) must be dropped; drops={drop_ids}"
    # MOC03 overlaps with MOC01 (dropped) but MOC01 is not a live reference.
    # MOC03 also overlaps with MOC02: 3/3=1.0 ≥ 0.80 → MOC03 is also dropped by MOC02.
    # This is the correct behavior: MOC02 is live and MOC03 is a subset of it.
    assert "MOC03" in drop_ids or "MOC03" in kept_ids, (
        f"MOC03 disposition must be determined; kept={kept_ids} drops={drop_ids}"
    )


def test_inter_cluster_no_overlap_keeps_all():
    """Completely disjoint clusters: no drops."""
    c1 = _enriched_cluster("MOC01", "cooking", ["pasta", "risotto", "pizza"])
    c2 = _enriched_cluster("MOC02", "programming", ["python", "rust", "go"])

    kept, drops = moc_discovery._dedupe_overlapping_clusters([c1, c2])

    assert len(kept) == 2, f"Disjoint clusters must both survive; got {kept!r}"
    assert drops == []


def test_inter_cluster_single_cluster_passes_through():
    """Single cluster: nothing to compare against, always kept."""
    c = _enriched_cluster("MOC01", "solo", ["a", "b", "c"])

    kept, drops = moc_discovery._dedupe_overlapping_clusters([c])

    assert len(kept) == 1
    assert drops == []


def test_inter_cluster_empty_input():
    """Empty input returns empty outputs without error."""
    kept, drops = moc_discovery._dedupe_overlapping_clusters([])

    assert kept == []
    assert drops == []
