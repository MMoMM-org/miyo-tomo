# topic_clusters.py — Pure clustering helper for atomic-note → Proposed MOC.
# version: 0.5.0
"""Group atomic-note candidates into Proposed MOC clusters.

Why this lives in a module of its own:
The same algorithm has two callers — `suggestions-reducer.py` (existing inbox
flow, where each cluster comes from a `create_atomic_note` action that flagged
`needs_new_moc=True`) and the upcoming `moc-discovery.py` (Phase 2, F-43,
where clusters come from cache-extracted topics over an existing tag/folder
slice). Both need the *same* normalisation + threshold + parent-vote +
shared-tag-fold semantics, so we extract to a pure function rather than
duplicating the loop.

Pure: no I/O, no globals; output is a fresh list per call and inputs are not
mutated. The only non-stdlib dependency is the shared `marker_word` helper from
`profile_conventions` (F-55 S1), which is itself pure.

Public surface:
    ClusterCandidate    — dataclass; one per item being considered for a MOC.
    Cluster             — TypedDict; one emitted Proposed-MOC group.
    build_topic_clusters(items, threshold) -> list[Cluster]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TypedDict

try:
    from .profile_conventions import marker_word
except ImportError:  # loaded with the lib dir directly on sys.path
    from profile_conventions import marker_word  # type: ignore

# The MOC-marker strip regex is built from the active profile's suffix (F-55 /
# spec 028 T2.2), not hardcoded — its core word is the alphanumeric part of the
# suffix (miyo " (MOC)" → "MOC"). The matched forms mirror the legacy pattern:
# a trailing marker preceded by whitespace ("X MOC") or wrapped in parentheses
# ("X (MOC)" / "X(MOC)"). A word boundary before the core word keeps mid-word
# endings like "biomoc" / "Thermoc" unchanged. Empty suffix → no marker → no-op.
_DEFAULT_MARKER_WORD = "MOC"


def _moc_marker_re(word: str) -> "re.Pattern[str] | None":
    """Compile the trailing-marker strip regex for a marker word; empty → None."""
    if not word:
        return None
    return re.compile(
        rf"(\s*\(\s*{re.escape(word)}\s*\)|\s+{re.escape(word)})\s*$",
        re.IGNORECASE,
    )


# ── Public types ─────────────────────────────────────────────────────────────


@dataclass
class ClusterCandidate:
    """One item that may contribute to a Proposed MOC cluster.

    `section_id` is the caller-defined identifier preserved in the emitted
    cluster's `items` list (e.g. `"S01"` for the inbox reducer, or a
    candidate stem for `moc-discovery.py`).

    `topic` is the human-readable topic phrase. It is normalised internally
    (lowercase, punctuation stripped, naive plural fold) for grouping; the
    *first* candidate's original casing wins as the emitted cluster's
    display topic.

    `parent` is an optional parent classification (e.g. a Dewey category).
    If multiple candidates in a cluster carry parents, the most-common one
    wins; ties fall back to insertion order via `max(set(...), key=count)`.

    `tags` are the leaf tags the candidate carries. The emitted cluster's
    `tags` field is computed by `_compute_moc_tags` — leaf tags that share
    a parent path are folded to the parent.
    """

    section_id: str
    topic: str
    parent: str = ""
    tags: list[str] = field(default_factory=list)


class Cluster(TypedDict):
    """One Proposed-MOC group emitted by `build_topic_clusters`."""

    topic: str
    items: list[str]
    parent: str
    tags: list[str]


# ── Public helpers ───────────────────────────────────────────────────────────


def strip_moc_marker(topic: str, suffix: str | None = None) -> str:
    """Remove trailing MOC marker(s) from a topic phrase, returning the bare form.

    The marker is derived from `suffix` (the active profile's MOC suffix):
      - `suffix=None`  → legacy default (miyo's "(MOC)" / " MOC").
      - `suffix=""`    → no-op (lyt): nothing is stripped.
      - otherwise      → strip the suffix's core word in both the parenthesised
                         ("X (MOC)", "X(MOC)") and whitespace ("X MOC") forms.

    Case-insensitive, whitespace-tolerant. Iterates until stable so double-
    suffixed forms ("X (MOC) (MOC)") are fully stripped in a single call.

    Word-boundary rule: the marker word is only stripped when preceded by
    whitespace or a parenthesised block. Mid-word endings such as "biomoc" or
    "Thermoc" are left unchanged.

    Guard: if stripping would empty the entire string (e.g. bare "MOC" or
    "(MOC)"), the original string is returned unchanged. Only trailing markers
    are removed — leading/mid-string occurrences are kept.
    """
    word = _DEFAULT_MARKER_WORD if suffix is None else marker_word(suffix)
    marker_re = _moc_marker_re(word)
    t = topic.strip()
    if marker_re is None:
        return t
    while True:
        stripped = marker_re.sub("", t).strip()
        if stripped == t or not stripped:
            break
        t = stripped
    return t if t else topic.strip()


# ── Internal helpers (kept private — `suggestions-reducer.py` re-exports its
#     own `normalise_topic` for backwards compatibility with existing tests
#     that import it by name) ─────────────────────────────────────────────────


def normalise_topic(topic: str) -> str:
    """Lowercase, strip punctuation, naive English plural fold.

    Mirrors the original inline implementation in `suggestions-reducer.py`
    so existing fixtures and topic phrasing produce identical groupings.
    """
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


def _compute_moc_tags(items_tags: list[list[str]]) -> list[str]:
    """Compute shared parent tags for a Proposed MOC.

    For hierarchical tags (slash-separated), if a parent path has children
    contributed by 2+ different leaf tags, the parent replaces the children.
    Single-item MOCs or tags without shared parents are kept as-is.

    Example:
        [['topic/games/boardgames/catan'], ['topic/games/boardgames/gloomhaven']]
        → ['topic/games/boardgames']
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


# ── Public API ───────────────────────────────────────────────────────────────


def build_topic_clusters(
    items: list[ClusterCandidate], threshold: int, suffix: str | None = None
) -> list[Cluster]:
    """Group candidates into Proposed-MOC clusters.

    Args:
        items: Per-candidate input; each carries a `section_id` (preserved
            in the cluster's `items` list), a raw topic phrase, an optional
            parent classification, and optional leaf tags.
        threshold: Minimum cluster size for emission. Clusters with fewer
            than `threshold` candidates are dropped.
        suffix: The active profile's MOC suffix, threaded to `strip_moc_marker`
            for topic normalisation. `None` → legacy default; `""` → no strip.

    Returns:
        A new list of `Cluster` dicts in insertion order of first occurrence.
        Pure — input is not mutated; a fresh list and fresh inner lists are
        returned on each call.
    """
    grouped: dict[str, list[tuple[str, str, str, list[str]]]] = {}
    for candidate in items:
        topic_raw = strip_moc_marker((candidate.topic or "").strip(), suffix)
        if not topic_raw:
            continue
        norm = normalise_topic(topic_raw)
        grouped.setdefault(norm, []).append(
            (
                candidate.section_id,
                topic_raw,
                candidate.parent,
                list(candidate.tags),
            )
        )

    out: list[Cluster] = []
    for _norm, hits in grouped.items():
        if len(hits) < threshold:
            continue
        display_topic = hits[0][1]  # first occurrence's bare casing
        parents = [h[2] for h in hits if h[2]]
        parent = max(set(parents), key=parents.count) if parents else ""
        # Tags: compute shared parent tags instead of dumping all leaf tags.
        tags = _compute_moc_tags([h[3] for h in hits])
        # Dedup section_ids order-preservingly (ADR-13 D4): a candidate whose
        # topics contain two phrases that normalise to the same key produces two
        # ClusterCandidate rows for the same cluster — first occurrence wins.
        seen_ids: set[str] = set()
        unique_items: list[str] = []
        for h in hits:
            if h[0] not in seen_ids:
                seen_ids.add(h[0])
                unique_items.append(h[0])
        out.append(
            {
                "topic": display_topic,
                "items": unique_items,
                "parent": parent,
                "tags": tags,
            }
        )
    return out
