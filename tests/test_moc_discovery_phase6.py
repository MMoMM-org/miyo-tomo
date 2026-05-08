#!/usr/bin/env python3
# version: 0.1.0
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
