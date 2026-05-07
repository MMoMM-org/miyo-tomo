#!/usr/bin/env python3
# version: 0.1.0
"""test_topic_clusters.py — Tests for the extracted topic-clusters helper.

Covers F-43 Phase 1 T1.5: pure-function extraction of the clustering algorithm
that previously lived inline in `suggestions-reducer.py` (lines 598-651).

The helper takes a list of `ClusterCandidate`s — one per atomic-note action
that flagged `needs_new_moc=True` — groups them by normalised topic, drops
groups that fall below the configured threshold, and emits one `Cluster` per
qualifying group:

    {
      "topic":   "<first occurrence's original casing>",
      "items":   ["<section_id>", ...],
      "parent":  "<mode of contributing parent classifications>",
      "tags":    ["<shared parent tag>", ...],
    }

The pre-refactor algorithm lived inline in `suggestions-reducer.py`; the
regression test below loads that legacy code path via `importlib`, runs it
against the same synthetic inbox fixture, and asserts byte-for-byte parity
with `build_topic_clusters` — that's what proves "no behavioural change".
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
LIB_DIR = SCRIPTS_DIR / "lib"

sys.path.insert(0, str(SCRIPTS_DIR))  # so `import lib.topic_clusters` works

from lib.topic_clusters import (  # noqa: E402
    ClusterCandidate,
    build_topic_clusters,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


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


def _load_reducer_module():
    """Import `suggestions-reducer.py` as a module under a Python-safe name."""
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ── Tests ────────────────────────────────────────────────────────────────────


def test_threshold_excludes_small_clusters():
    """A 2-note topic cluster is dropped when threshold=3."""
    items = [
        _candidate("S01", "Boardgames", parent="Hobbies", tags=["topic/games/boardgames/catan"]),
        _candidate("S02", "Boardgames", parent="Hobbies", tags=["topic/games/boardgames/gloomhaven"]),
        # An unrelated 1-note cluster — also under threshold
        _candidate("S03", "Cooking", parent="Lifestyle", tags=["topic/cooking"]),
    ]

    clusters = build_topic_clusters(items, threshold=3)

    assert clusters == [], (
        "Expected no clusters above threshold=3; "
        f"got {[c['topic'] for c in clusters]}"
    )


def test_normalised_topic_grouping():
    """Different casings/whitespace/punctuation collapse to one cluster."""
    items = [
        _candidate("S01", "Boardgames", parent="Hobbies", tags=["topic/games/boardgames/catan"]),
        _candidate("S02", "boardgames", parent="Hobbies", tags=["topic/games/boardgames/gloomhaven"]),
        _candidate("S03", " boardgames ", parent="Hobbies", tags=["topic/games/boardgames/wingspan"]),
    ]

    clusters = build_topic_clusters(items, threshold=2)

    assert len(clusters) == 1, f"Expected one merged cluster; got {clusters}"
    cluster = clusters[0]
    assert cluster["topic"] == "Boardgames", "First occurrence's casing wins"
    assert cluster["items"] == ["S01", "S02", "S03"]
    assert cluster["parent"] == "Hobbies"
    # All three children share `topic/games/boardgames/*`; helper folds to parent.
    assert cluster["tags"] == ["topic/games/boardgames"]


def test_pure_function_no_side_effects():
    """Same input → same output; the helper does not mutate its arguments."""
    items = [
        _candidate("S01", "Routines", parent="Personal", tags=["topic/personal/habits"]),
        _candidate("S02", "routines", parent="Personal", tags=["topic/personal/habits"]),
        _candidate("S03", "Routines!", parent="Productivity", tags=["topic/personal/habits"]),
    ]
    snapshot = [
        ClusterCandidate(
            section_id=c.section_id,
            topic=c.topic,
            parent=c.parent,
            tags=list(c.tags),
        )
        for c in items
    ]

    first = build_topic_clusters(items, threshold=2)
    second = build_topic_clusters(items, threshold=2)

    assert first == second, "Repeated calls must produce identical output"
    # Inputs unchanged
    assert items == snapshot, "Helper must not mutate its input list/items"
    # Returned lists are not aliased — caller can mutate without breaking re-runs
    assert first is not second
    if first:
        assert first[0]["items"] is not second[0]["items"]


def test_existing_inbox_run_regression():
    """Output matches the pre-refactor inline algorithm from suggestions-reducer.

    Synthetic fixture mirrors a plausible inbox-batch shape: three boardgame
    atomic notes (cluster), two routine atomic notes (cluster, mixed parents
    so the mode-vote matters), and one stand-alone topic that should drop out
    at threshold=2.
    """
    items = [
        _candidate(
            "S01", "Boardgames",
            parent="Hobbies",
            tags=["topic/games/boardgames/catan"],
        ),
        _candidate(
            "S02", "boardgames",
            parent="Hobbies",
            tags=["topic/games/boardgames/gloomhaven"],
        ),
        _candidate(
            "S03", "Boardgames!",
            parent="Leisure",
            tags=["topic/games/boardgames/wingspan"],
        ),
        _candidate(
            "S04", "Routine",
            parent="Personal",
            tags=["topic/personal/habits"],
        ),
        _candidate(
            "S05", "Routines",
            parent="Productivity",
            tags=["topic/personal/habits"],
        ),
        _candidate(
            "S06", "Cooking",
            parent="Lifestyle",
            tags=["topic/cooking"],
        ),
    ]

    expected = _legacy_topic_clusters(items, threshold=2)
    actual = build_topic_clusters(items, threshold=2)

    assert actual == expected, (
        "Refactored helper must match pre-refactor inline algorithm.\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


# ── Reference implementation (mirrors suggestions-reducer.py:598-651) ────────


def _legacy_topic_clusters(
    items: list[ClusterCandidate], threshold: int
) -> list[dict]:
    """Re-implementation of the pre-refactor inline algorithm.

    Imports `normalise_topic` and `_compute_moc_tags` directly from the
    reducer module so we exercise the *real* helpers — only the grouping
    loop is replicated here. Drift in the helpers will surface as a test
    failure on the public regression test above.
    """
    reducer = _load_reducer_module()
    normalise_topic = reducer.normalise_topic
    _compute_moc_tags = reducer._compute_moc_tags

    grouped: dict[str, list[tuple[str, str, str, list[str]]]] = {}
    for c in items:
        topic_raw = (c.topic or "").strip()
        if not topic_raw:
            continue
        norm = normalise_topic(topic_raw)
        grouped.setdefault(norm, []).append(
            (c.section_id, topic_raw, c.parent, list(c.tags))
        )

    out: list[dict] = []
    for _norm, hits in grouped.items():
        if len(hits) < threshold:
            continue
        display_topic = hits[0][1]
        parents = [h[2] for h in hits if h[2]]
        parent = max(set(parents), key=parents.count) if parents else ""
        all_tags = _compute_moc_tags([h[3] for h in hits])
        out.append({
            "topic": display_topic,
            "items": [h[0] for h in hits],
            "parent": parent,
            "tags": all_tags,
        })
    return out
