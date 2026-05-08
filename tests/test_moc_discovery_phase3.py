#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_phase3.py — Phase 3 cluster detection for moc-discovery.py.

F-43 Phase 2 T2.4: thin wrapper around `lib.topic_clusters.build_topic_clusters`.

Phase 3 takes the candidates-with-topics from Phase 2 and groups them into
Proposed-MOC clusters using the same normalisation + threshold + parent-vote +
shared-tag-fold algorithm extracted in T1.5. The wrapper:

  - Explodes one `ClusterCandidate` per `(candidate, topic)` pair so a
    candidate carrying multiple topics participates in every relevant cluster.
  - Passes `threshold=config.min_notes` through to the lib helper (default 3).
  - Returns the lib's `list[Cluster]` directly — no further transformation.
  - Returns `[]` for "no clusters above threshold"; an empty list is a valid
    Phase 3 outcome (the discovery report stays non-aborted, surfacing
    "no significant clusters" to the user). Phase 3 itself never aborts.

Tests exercise `phase3_cluster` directly with hand-built `Candidate` lists.
No Kado, no LLM, no fixtures on disk — pure-function territory.
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

from lib.topic_clusters import (  # noqa: E402  — must come after sys.path insert
    ClusterCandidate,
    build_topic_clusters,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


class _Cfg:
    """Minimal stand-in for `MocProposalConfig`. The wrapper only reads
    `min_notes`; tests construct one per-call to vary the threshold."""

    def __init__(self, min_notes: int = 3) -> None:
        self.min_notes = min_notes


def _candidate(stem: str, topics: list[str]) -> "moc_discovery.Candidate":
    """Build a Phase-2-shaped Candidate (stem, path, topics populated)."""
    return moc_discovery.Candidate(
        stem=stem,
        path=f"Atlas/202 Notes/2611 Code Snippets/{stem}.md",
        topics=list(topics),
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_cluster_threshold_default():
    """Default `min_notes=3` keeps 3+ shared-topic groups, drops smaller ones.

    Builds three candidates around `shell` (cluster), two around `cooking`
    (below threshold), and one singleton (`isolated`). With the spec default
    threshold of 3 only the `shell` cluster survives.
    """
    candidates = [
        _candidate("zsh", ["shell"]),
        _candidate("bash", ["shell"]),
        _candidate("fish", ["shell"]),
        _candidate("recipe1", ["cooking"]),
        _candidate("recipe2", ["cooking"]),
        _candidate("orphan", ["isolated"]),
    ]

    clusters = moc_discovery.phase3_cluster(candidates, _Cfg(min_notes=3))

    assert len(clusters) == 1, (
        f"Expected one cluster above threshold=3; got {[c['topic'] for c in clusters]}"
    )
    cluster = clusters[0]
    assert cluster["topic"] == "shell"
    assert sorted(cluster["items"]) == ["bash", "fish", "zsh"]


def test_multi_cluster_shared_notes_highest_weight_wins():
    """A candidate with multiple topics participates in every matching cluster.

    The lib's existing reducer algorithm explodes one `ClusterCandidate` per
    topic, so a candidate that carries `[shell, terminal]` shows up in BOTH
    the `shell` cluster (4 members) and the `terminal` cluster (3 members).
    The wrapper must replicate the lib's behaviour byte-for-byte — we assert
    that by feeding the same logical input into `build_topic_clusters`
    directly and comparing.
    """
    # Three candidates exclusive to `shell`, two exclusive to `terminal`,
    # plus one shared (`fzf`) carrying both topics. Result:
    #   shell    cluster: [zsh, bash, fish, fzf]   (4 members)
    #   terminal cluster: [tmux, alacritty, fzf]   (3 members)
    candidates = [
        _candidate("zsh", ["shell"]),
        _candidate("bash", ["shell"]),
        _candidate("fish", ["shell"]),
        _candidate("tmux", ["terminal"]),
        _candidate("alacritty", ["terminal"]),
        _candidate("fzf", ["shell", "terminal"]),
    ]

    actual = moc_discovery.phase3_cluster(candidates, _Cfg(min_notes=3))

    # Independently exploded oracle: one ClusterCandidate per (stem, topic) pair.
    oracle_input: list[ClusterCandidate] = []
    for c in candidates:
        for topic in c.topics:
            oracle_input.append(
                ClusterCandidate(
                    section_id=c.stem,
                    topic=topic,
                    parent="",
                    tags=[],
                )
            )
    expected = build_topic_clusters(oracle_input, threshold=3)

    assert actual == expected, (
        "Wrapper output must match build_topic_clusters on exploded input.\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )

    # Spot-checks on the structural claim: fzf appears in both clusters.
    by_topic = {c["topic"]: c for c in actual}
    assert "shell" in by_topic and "terminal" in by_topic
    assert "fzf" in by_topic["shell"]["items"]
    assert "fzf" in by_topic["terminal"]["items"]


def test_zero_clusters_returns_empty_report_not_abort():
    """Below-threshold input → `[]`; phase3 never aborts.

    Each candidate carries a unique topic, so no group reaches `min_notes=3`.
    Per SDD §Pseudocode lines 869-871 the discovery report stays non-aborted —
    `phase3_cluster` returns an empty list and the outer pipeline surfaces the
    user-facing "no significant clusters" message rather than treating empty as
    a fault. The wrapper itself only returns `list[Cluster]` (no abort_reason
    tuple), proving by signature that empty is a normal outcome.
    """
    candidates = [
        _candidate("zsh", ["shell"]),
        _candidate("vim", ["editor"]),
        _candidate("git", ["vcs"]),
    ]

    clusters = moc_discovery.phase3_cluster(candidates, _Cfg(min_notes=3))

    assert clusters == [], (
        f"Expected zero clusters with all-unique topics at threshold=3; got {clusters}"
    )
    # Sanity: the wrapper is single-return — empty is by-construction valid.
    assert isinstance(clusters, list)
