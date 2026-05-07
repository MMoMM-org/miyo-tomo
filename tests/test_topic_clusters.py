#!/usr/bin/env python3
# version: 0.2.0
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

The regression test below re-implements the pre-refactor inline algorithm
(grouping loop + `normalise_topic` + `_compute_moc_tags`) from scratch — no
imports from the production module — and asserts byte-for-byte parity with
`build_topic_clusters`. The two sides are independent so any future drift in
the production normalisation or tag-fold helpers surfaces as a test failure.
"""
from __future__ import annotations

import re
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
    """Byte-for-byte parity with the pre-refactor inline algorithm.

    Compares `build_topic_clusters` output against `_legacy_topic_clusters`,
    which independently re-implements the pre-refactor grouping loop along
    with its own copies of `normalise_topic` and `_compute_moc_tags`. The
    two sides share no code, so future drift in the production helpers will
    surface here as a regression failure rather than being masked by a shared
    import.

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


# ── Reference implementation (independent re-impl of pre-refactor inline) ───
#
# The bodies below are hand-copied from `suggestions-reducer.py` at commit
# 83f3ffb (the commit immediately before the F-43 T1.5 extraction in eb20d1f).
# They MUST stay independent of `lib.topic_clusters` — no imports — so that a
# future change to the production `normalise_topic` or `_compute_moc_tags`
# surfaces as a `test_existing_inbox_run_regression` failure rather than
# silently passing because both sides call the same code object.


def _legacy_normalise_topic(topic: str) -> str:
    """Lowercase, strip punctuation, naive plural fold (pre-refactor copy)."""
    if not topic:
        return ""
    t = topic.strip().lower()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Naive pluralisation fold (English):
    #  - "ies" → "y" (e.g. "stories" → "story")
    #  - sibilant-"es" → strip "es" (buses, boxes, buzzes, churches, dishes)
    #  - trailing "s" → strip (tools → tool, routines → routine)
    if t.endswith("ies") and len(t) > 3:
        t = t[:-3] + "y"
    elif len(t) > 3 and t.endswith(("ses", "xes", "zes", "ches", "shes")):
        t = t[:-2]
    elif t.endswith("s") and not t.endswith("ss") and len(t) > 3:
        t = t[:-1]
    return t


def _legacy_compute_moc_tags(items_tags: list[list[str]]) -> list[str]:
    """Compute shared parent tags for a Proposed MOC (pre-refactor copy).

    For hierarchical tags (slash-separated), if a parent path has children
    contributed by 2+ different leaf tags, the parent replaces the children.
    Single-item MOCs or tags without shared parents are kept as-is.
    """
    all_tags: list[str] = []
    for tags in items_tags:
        all_tags.extend(tags)
    if not all_tags:
        return []

    # Group tags by their parent path (strip last segment)
    parent_children: dict[str, set[str]] = {}
    leaf_tags: list[str] = []
    for tag in all_tags:
        parts = tag.split("/")
        if len(parts) > 1:
            parent_path = "/".join(parts[:-1])
            parent_children.setdefault(parent_path, set()).add(tag)
        else:
            leaf_tags.append(tag)

    result: list[str] = []
    seen: set[str] = set()
    # Parents with 2+ children → emit parent instead of leaves
    covered: set[str] = set()
    for parent_path, children in sorted(parent_children.items()):
        if len(children) >= 2:
            if parent_path not in seen:
                result.append(parent_path)
                seen.add(parent_path)
            covered.update(children)

    # Tags not covered by a shared parent → keep as-is
    for tag in all_tags:
        if tag not in covered and tag not in seen:
            result.append(tag)
            seen.add(tag)

    return result


def _legacy_topic_clusters(
    items: list[ClusterCandidate], threshold: int
) -> list[dict]:
    """Self-contained re-implementation of the pre-refactor inline algorithm.

    No production-code imports — uses `_legacy_normalise_topic` and
    `_legacy_compute_moc_tags` defined above. This is the regression test's
    independent oracle.
    """
    grouped: dict[str, list[tuple[str, str, str, list[str]]]] = {}
    for c in items:
        topic_raw = (c.topic or "").strip()
        if not topic_raw:
            continue
        norm = _legacy_normalise_topic(topic_raw)
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
        all_tags = _legacy_compute_moc_tags([h[3] for h in hits])
        out.append({
            "topic": display_topic,
            "items": [h[0] for h in hits],
            "parent": parent,
            "tags": all_tags,
        })
    return out
