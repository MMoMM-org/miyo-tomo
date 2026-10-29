# version: 0.1.0
"""moc_discovery_topics.py — Phases 2 and 3 of moc-discovery: topics and clusters.

Phase 2 resolves each candidate's topics cache-first and batches the misses
for an LLM under a hard cap; Phase 3 groups the candidates by normalised topic
through `lib.topic_clusters`. `moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_topics.md (issue #216).
"""
from __future__ import annotations

import math
from typing import Protocol

from lib.moc_discovery_common import Candidate, _log


# Phase 2 LLM batching — fixed at 10 per SDD §Pseudocode line 864 (chunk(misses, 10)).
LLM_BATCH_SIZE = 10


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — Topic extraction (cache lookup + bounded LLM batching)
# ──────────────────────────────────────────────────────────────────────────────


class LLMClient(Protocol):
    """Minimal LLM-batch-extract surface consumed by Phase 2.

    Implementations take a list of cache-miss `Candidate`s and return one
    dict per candidate, shaped `{"path": str, "topics": list[str]}`. Phase 2
    splits misses into chunks of `LLM_BATCH_SIZE` (10) and fans out one call
    per chunk; the real production client lives outside T2.3 and gets wired
    in `main()` later (T2.8).
    """

    def batch_extract(self, batch: list["Candidate"]) -> list[dict]: ...  # pragma: no cover


def _build_topics_index(cache: dict) -> dict[str, list[str]]:
    """Index cache entries by path → topics for O(1) hit lookup in Phase 2.

    Indexes two sources (last-writer-wins on duplicate paths — the cache-builder
    dedupes, this is a defensive belt-and-braces):

    1. `cache["entries"]` (kind==moc AND kind==note) — covers scan-mode candidates
       whose topics come from the cache entry rather than from an LLM call.
       Before T5.1 this was a miss for kind==note paths, forcing spurious LLM
       batching for every scan candidate.

    2. `cache["map_notes"]` (kind==moc shim, populated by apply_shim in the
       loader) — kept for backward compat with title/free-text mode, which
       constructs candidates from map_notes and needs its hits to resolve here.
    """
    out: dict[str, list[str]] = {}

    # Pass 1: all entries (moc + note) from the unified entries list.
    for entry in cache.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if not path:
            continue
        topics = [str(t) for t in (entry.get("topics") or []) if t]
        out[path] = topics

    # Pass 2: map_notes shim — applies on top so MOC hits from the shim layer
    # are never shadowed by a stale entries pass.
    for entry in cache.get("map_notes") or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if not path:
            continue
        topics = [str(t) for t in (entry.get("topics") or []) if t]
        out[path] = topics

    return out


def _batch_llm_extract(
    candidates: list[Candidate],
    llm_client: LLMClient,
    batch_size: int = LLM_BATCH_SIZE,
) -> list[Candidate]:
    """Chunk cache-miss candidates and call the LLM once per chunk.

    Returns the input candidates with their `topics` field populated from the
    LLM response. Order is preserved within and across chunks so callers can
    re-merge with cache hits without losing per-mode ordering.

    Pre-condition: caller has already verified `ceil(len(candidates)/batch_size)
    <= cache_miss_max_batches`. This helper does NOT enforce the cap — that
    decision is the caller's so the abort path can short-circuit before any
    LLM contact.
    """
    if not candidates:
        return []

    # Index input candidates by path so we can apply the LLM response onto
    # the same instances (preserving any existing fields downstream phases set).
    by_path: dict[str, Candidate] = {c.path: c for c in candidates}

    for start in range(0, len(candidates), batch_size):
        chunk = candidates[start : start + batch_size]
        response = llm_client.batch_extract(chunk)
        for entry in response or []:
            path = entry.get("path")
            topics = entry.get("topics") or []
            if not path or path not in by_path:
                continue
            by_path[path].topics = [str(t) for t in topics if t]

    return candidates


def phase2_extract_topics(
    candidates: list[Candidate],
    cache: dict,
    config,
    llm_client: LLMClient | None,
) -> tuple[list[Candidate], str | None]:
    """Resolve topics per candidate via cache-first lookup + bounded LLM fallback.

    Returns
    -------
    (candidates_with_topics, abort_reason)
        On success: (merged hits + LLM-extracted misses, None).
        On `cache-miss-cap-exceeded`: ([], "cache-miss-cap-exceeded").

    Algorithm (SDD §Pseudocode lines 861-867):
      hits   := [c for c in candidates if c in cache]
      misses := [c for c in candidates if c not in cache]
      batches := chunk(misses, 10)
      if len(batches) > config.cache_miss_max_batches → abort
      extracted := llm_batch_extract(batches)
      candidates_with_topics := merge(hits, extracted)
    """
    topics_by_path = _build_topics_index(cache)

    hits: list[Candidate] = []
    misses: list[Candidate] = []
    for c in candidates:
        # T6.5: short-circuit on pre-populated topics (--phase1-input flow).
        # The moc-architect agent ran a topic-extract subagent between
        # --emit-phase1 and --phase1-input, so cache misses are already
        # resolved at the candidate level — no LLM call needed here.
        if c.topics:
            hits.append(c)
            continue
        cached = topics_by_path.get(c.path)
        if cached is not None:
            # Copy onto the candidate so downstream phases see populated topics.
            c.topics = list(cached)
            hits.append(c)
        else:
            misses.append(c)

    cap = getattr(config, "cache_miss_max_batches", 5)
    batches_needed = math.ceil(len(misses) / LLM_BATCH_SIZE) if misses else 0
    if batches_needed > cap:
        _log(
            f"phase2: cache-miss-cap-exceeded "
            f"(misses={len(misses)} → batches={batches_needed} > cap={cap})"
        )
        return ([], "cache-miss-cap-exceeded")

    _log(
        f"phase2: cache-hits={len(hits)} cache-misses={len(misses)} "
        f"batches={batches_needed}"
    )

    if misses:
        if llm_client is None:
            # Caller has not wired an LLM client yet (T2.8 production wiring).
            # Surface clearly rather than silently emitting empty topics.
            raise RuntimeError(
                "phase2_extract_topics: llm_client is required when there are "
                "cache misses. Pass a real LLMClient or ensure the cache covers "
                "every Phase 1 candidate."
            )
        _batch_llm_extract(misses, llm_client)

    # Merge preserves input order: a candidate's position in the output
    # matches its position in the input list. Each candidate appears exactly
    # once because hits and misses are disjoint by construction.
    return (list(candidates), None)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3 — Cluster detection (thin wrapper around lib.topic_clusters)
# ──────────────────────────────────────────────────────────────────────────────


def phase3_cluster(
    candidates_with_topics: list[Candidate], config, moc_suffix: str | None = None
) -> list[dict]:
    """Group candidates by normalised topic — thin wrapper around T1.5.

    `moc_suffix` is the active profile's MOC suffix, threaded into
    `build_topic_clusters` for topic normalisation (F-55 / spec 028 T2.2).

    Each candidate from Phase 2 carries `topics: list[str]` (one or more).
    The reducer's existing algorithm operates on one `ClusterCandidate` per
    `(candidate, topic)` pair, so a candidate that carries `[shell, terminal]`
    contributes to BOTH the `shell` cluster and the `terminal` cluster — the
    "shared note across clusters" case the SDD calls out for `/moc-propose`.

    Per SDD §Pseudocode lines 869-871:
        clusters := topic_clusters(candidates_with_topics, threshold=config.min_notes)
        if len(clusters) == 0 → return empty report (NOT an abort; the user-facing
                                "no significant clusters" message is surfaced by
                                the outer pipeline).

    Phase 3 itself never aborts — empty output is a valid normal outcome.
    Aborts in this pipeline live in Phase 1 (zero-candidates,
    candidate-cap-exceeded) and Phase 2 (cache-miss-cap-exceeded).

    Args:
        candidates_with_topics: Phase-2-enriched Candidates with `topics`
            populated (cache hits + LLM-extracted misses, merged in input order).
        config: Anything exposing `min_notes: int` — typically a
            `MocProposalConfig` from `shared-ctx-builder.load_moc_proposal_config`.

    Returns:
        `list[Cluster]` from `lib.topic_clusters.build_topic_clusters` (a list
        of `{topic, items, parent, tags}` TypedDicts). `items` carries the
        contributing candidate stems (preserved as `section_id` upstream).
        Pure: input is not mutated; a fresh list is returned each call.
    """
    # Local import keeps the lib dependency colocated with its only consumer
    # in this module (mirrors the other helpers' file-local-import pattern).
    from lib.topic_clusters import ClusterCandidate, build_topic_clusters

    # Explode one ClusterCandidate per (candidate, topic) pair. Candidates
    # without topics are skipped — `build_topic_clusters` would drop them
    # anyway via its empty-topic guard, but skipping here is explicit and
    # avoids feeding the lib pointless rows.
    items: list[ClusterCandidate] = []
    for c in candidates_with_topics:
        for topic in c.topics or []:
            items.append(
                ClusterCandidate(
                    section_id=c.stem,
                    topic=topic,
                    # No parent at Phase 3 — parent_options land in Phase 5.
                    parent="",
                    # Candidate carries no leaf tags in Phase 3 yet; tag-fold
                    # in `_compute_moc_tags` is a no-op on empty input.
                    tags=[],
                )
            )

    threshold = getattr(config, "min_notes", 3)
    return build_topic_clusters(items, threshold=threshold, suffix=moc_suffix)
