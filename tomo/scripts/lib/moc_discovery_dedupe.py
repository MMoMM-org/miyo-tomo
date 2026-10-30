# version: 0.2.0
"""moc_discovery_dedupe.py — Phase 6 and D3 of moc-discovery: duplicate and overlap filtering.

Phase 6 drops proposed clusters that duplicate an existing MOC (exact title,
weighted topic overlap, or members inside a folder-home MOC's folder) or are
squelched; D3 drops proposed clusters whose
members sit inside a larger proposed cluster. `moc-discovery.py` re-exports
every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_dedupe.md (issue #216).
"""
from __future__ import annotations

from lib.moc_discovery_common import _log, _stem_from_path
from lib.topic_match import weighted_overlap
from lib.topic_signature import (
    candidate_stems as _lib_candidate_stems,
    cluster_topic_set as _lib_cluster_topic_set,
    compute_topic_signature as _lib_compute_topic_signature,
)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 6 — Duplicate detection (Jaccard ≥ 0.80) + squelch read-only lookup
# ──────────────────────────────────────────────────────────────────────────────

# Jaccard threshold for duplicate detection (SDD §Implementation Examples /
# Example 3, line 704). A cluster whose topic-set has ≥ 0.80 set-similarity
# with any existing MOC's topic-set is treated as a duplicate and skipped.
JACCARD_DUP_THRESHOLD = 0.80


def _cluster_topic_set(cluster: dict) -> set[str]:
    """Normalised topic bag for Jaccard comparison.

    Delegates to lib.topic_signature.cluster_topic_set — single implementation
    shared with squelch-persist (T5.2 factoring).
    """
    return _lib_cluster_topic_set(cluster)


def _moc_topic_set(map_note: dict) -> set[str]:
    """Lowercased topic-set for an existing MOC entry from `cache.map_notes`."""
    topics = map_note.get("topics") or []
    out: set[str] = set()
    for t in topics:
        if t:
            norm = str(t).strip().lower()
            if norm:
                out.add(norm)
    return out


def _candidate_stems(cluster: dict) -> list[str]:
    """Pull the cluster's per-candidate identifiers for signature stability.

    Delegates to lib.topic_signature.candidate_stems — single implementation
    shared with squelch-persist (T5.2 factoring).
    """
    return _lib_candidate_stems(cluster)


def _compute_topic_signature(cluster: dict) -> str:
    """Stable hash for squelch keying — SDD §Implementation Examples / Example 2.

    Delegates to lib.topic_signature.compute_topic_signature — single
    implementation shared with squelch-persist (T5.2 factoring).
    """
    return _lib_compute_topic_signature(cluster)


def _normalise_title(title: str) -> str:
    """Case-insensitive title comparator — strip + lower."""
    return (title or "").strip().lower()


def _find_exact_title_match(
    cluster_title: str, map_notes: list[dict]
) -> str | None:
    """Return the matching MOC's title (or stem) on a case-insensitive title hit."""
    needle = _normalise_title(cluster_title)
    if not needle:
        return None
    for entry in map_notes or []:
        if not isinstance(entry, dict):
            continue
        existing_title = _normalise_title(entry.get("title") or "")
        if existing_title and existing_title == needle:
            # Prefer the human-readable title for the report; fall back to
            # path stem so the agent always has something to surface.
            return (
                str(entry.get("title")
                    or _stem_from_path(entry.get("path") or ""))
            )
    return None


def _find_jaccard_match(
    cluster_topics: set[str], cluster_title: str, map_notes: list[dict]
) -> tuple[str | None, float]:
    """Scan map_notes for the first MOC whose weighted topic overlap ≥ 0.80.

    Uses Ruzicka-style weighted overlap (via lib.topic_match.weighted_overlap)
    so that a topic appearing in a title receives W_TITLE weight (×2).
    A cluster whose flat Jaccard would clear 0.80 but whose title theme
    disagrees with the MOC's title theme may score below the threshold and
    will NOT be flagged as a duplicate (spec-029 SDD Runtime View Flow A).

    Returns (existing_moc_label, weighted_score) — `(None, 0.0)` when no MOC
    clears the threshold. Stops on the first hit so the report names a single
    "winning" duplicate (matches SDD Example 3's early-return).
    """
    if not cluster_topics:
        return (None, 0.0)
    for entry in map_notes or []:
        if not isinstance(entry, dict):
            continue
        moc_topics = _moc_topic_set(entry)
        if not moc_topics:
            continue
        score = weighted_overlap(
            cluster_topics,
            cluster_title,
            moc_topics,
            entry.get("title") or "",
        )
        if score >= JACCARD_DUP_THRESHOLD:
            label = (
                str(entry.get("title")
                    or _stem_from_path(entry.get("path") or ""))
            )
            return (label, score)
    return (None, 0.0)


# Share of a cluster's located members that must sit inside a folder-home MOC's
# folder for the cluster to count as that MOC's duplicate.
FOLDER_HOME_THRESHOLD = 0.80


def _folder_homes(
    map_notes: list[dict], container_roots: list[str]
) -> list[tuple[str, str]]:
    """``(folder, label)`` for every MOC whose stem equals its folder's name.

    A folder that is a configured container root (``container_roots``) or an
    ancestor of one holds every atomic note, so its home note is no folder-home.
    """
    roots = [r.strip("/").casefold() for r in container_roots or [] if r.strip("/")]
    homes: list[tuple[str, str]] = []
    for entry in map_notes or []:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        folder, _, _ = path.rpartition("/")
        if not folder:
            continue
        stem = _stem_from_path(path)
        if stem.casefold() != folder.rpartition("/")[2].casefold():
            continue
        key = folder.casefold()
        if any(r == key or r.startswith(key + "/") for r in roots):
            continue
        homes.append((folder, str(entry.get("title") or stem)))
    return homes


def _find_folder_home_match(
    stems: list[str], member_paths: dict[str, str], homes: list[tuple[str, str]]
) -> str | None:
    """Label of the folder-home MOC whose folder holds ≥ 80 % of the located members."""
    located = [member_paths[s] for s in stems if member_paths.get(s)]
    if not located:
        return None
    for folder, label in homes:
        prefix = folder.casefold() + "/"
        inside = sum(1 for p in located if p.casefold().startswith(prefix))
        if inside / len(located) >= FOLDER_HOME_THRESHOLD:
            return label
    return None


def phase6_dedupe(
    clusters: list[dict],
    cache: dict,
    squelch_registry: dict,
    config,
    member_paths: dict[str, str] | None = None,
    container_roots: list[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Filter near-duplicate clusters and consult the squelch registry.

    Four skip checks run in order, each short-circuiting before the next:

      1. **Exact-title match** — cluster's proposed title (case-insensitive)
         equals any `cache.map_notes[].title`. Reported as
         ``reason="exact-title"``.
      2. **Jaccard ≥ 0.80** — cluster's topic-set against each existing MOC's
         topic-set. Reported as ``reason="80-percent-overlap"``.
      3. **Folder-home** — ≥ 80 % of the cluster's members (located through
         ``member_paths``) sit inside the folder of an existing MOC whose
         stem equals that folder's name; a ``container_roots`` folder or its
         ancestor never counts. Reported as
         ``reason="folder-home"``. Skipped when ``member_paths`` is None.
      4. **Active squelch** — topic signature (sha1 of normalised topic +
         sorted candidate stems) is present in `squelch_registry` with
         ``runs_remaining > 0``. Reported in the ``squelched`` list.

    Squelch is **read-only** in this phase. Decrement / persist / append on
    user rejection happens in Phase 5 wiring (T5.1, T5.2) — Phase 6 only
    consults `lib.squelch.is_active`.

    Args:
        clusters: Phase-3 (or Phase-4-enriched) `Cluster` dicts. Each carries
            ``topic`` (str) plus optional ``topic_keywords`` (list[str]),
            ``title`` (str — set by Phase 4), ``items`` (list[str]).
        cache: Discovery cache dict; Phase 6 reads ``map_notes`` only.
        squelch_registry: ``dict[str, SquelchEntry]`` from
            `lib.squelch.load_registry`. Empty dict = no entries active.
        config: Reserved for future tuning (e.g. configurable threshold).
            Not read in this phase — accepting it keeps the signature stable
            for downstream tasks.
        member_paths: candidate stem → vault path, for the folder-home check.
        container_roots: configured concept folders (atomic_note, map_note)
            that are never folder-homes, nor are their ancestors.

    Returns:
        ``(kept_clusters, duplicates_skipped, squelched)`` — matching the
        DiscoveryReport shape (SDD lines 548-549).

        - ``kept_clusters``: subset of `clusters` (identity-preserved) that
          passed all three checks.
        - ``duplicates_skipped``: list of
          ``{cluster_id, reason, existing_moc}`` dicts.
        - ``squelched``: list of ``{cluster_id, runs_remaining}`` dicts.

    Pure: input lists / dicts are not mutated. The squelch registry is
    never decremented or rewritten here.
    """
    del config  # reserved — Phase 6 reads no config fields today.

    map_notes: list[dict] = list(cache.get("map_notes") or [])
    homes = _folder_homes(map_notes, container_roots or []) if member_paths else []

    kept: list[dict] = []
    duplicates_skipped: list[dict] = []
    squelched: list[dict] = []

    # Local import keeps the lib dependency colocated with its only caller in
    # this module — same pattern as `phase3_cluster`.
    from lib.squelch import is_active as _squelch_is_active

    for idx, cluster in enumerate(clusters or [], start=1):
        cluster_id = f"MOC{idx:02d}"

        # ── 1. Exact-title match ────────────────────────────────────────────
        existing = _find_exact_title_match(cluster.get("title") or "", map_notes)
        if existing is not None:
            duplicates_skipped.append({
                "cluster_id": cluster_id,
                "reason": "exact-title",
                "existing_moc": existing,
            })
            _log(
                f"phase6: cluster {cluster_id!r} title={cluster.get('title')!r} "
                f"matches existing MOC {existing!r} — skipping (exact-title)"
            )
            continue

        # ── 2. Jaccard overlap ≥ 0.80 ──────────────────────────────────────
        cluster_topics = _cluster_topic_set(cluster)
        match_label, score = _find_jaccard_match(
            cluster_topics, cluster.get("title") or "", map_notes
        )
        if match_label is not None:
            duplicates_skipped.append({
                "cluster_id": cluster_id,
                "reason": "80-percent-overlap",
                "existing_moc": match_label,
            })
            _log(
                f"phase6: cluster {cluster_id!r} topic-set overlaps "
                f"{match_label!r} (weighted={score:.2f}) — skipping"
            )
            continue

        # ── 3. Folder-home MOC holds the members ───────────────────────────
        home = _find_folder_home_match(
            _candidate_stems(cluster), member_paths or {}, homes
        )
        if home is not None:
            duplicates_skipped.append({
                "cluster_id": cluster_id,
                "reason": "folder-home",
                "existing_moc": home,
            })
            _log(
                f"phase6: cluster {cluster_id!r} members sit in the folder of "
                f"{home!r} — skipping (folder-home)"
            )
            continue

        # ── 4. Squelch lookup (read-only) ──────────────────────────────────
        signature = _compute_topic_signature(cluster)
        if _squelch_is_active(squelch_registry or {}, signature):
            entry = (squelch_registry or {}).get(signature)
            runs_remaining = entry.runs_remaining if entry is not None else 0
            squelched.append({
                "cluster_id": cluster_id,
                "runs_remaining": runs_remaining,
            })
            _log(
                f"phase6: cluster {cluster_id!r} signature={signature!r} is "
                f"squelched (runs_remaining={runs_remaining}) — skipping"
            )
            continue

        kept.append(cluster)

    _log(
        f"phase6: kept={len(kept)} duplicates={len(duplicates_skipped)} "
        f"squelched={len(squelched)}"
    )

    return (kept, duplicates_skipped, squelched)


# ──────────────────────────────────────────────────────────────────────────────
# D3 — Inter-cluster member-overlap dedup (SDD ADR-13 D3, spec 021 T7.4)
# ──────────────────────────────────────────────────────────────────────────────

_MEMBER_OVERLAP_THRESHOLD: float = 0.80


def _dedupe_overlapping_clusters(
    clusters: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Drop proposed clusters whose members are ≥80% inside a larger proposed cluster.

    This is a NEW pass over PROPOSED clusters only — it does NOT touch
    phase6_dedupe's topics-vs-existing-MOC logic.  The denominator is always
    the SMALLER cluster's member count.

    Sort order (stable, deterministic): size DESC, then cluster_id ASC.
    When sizes tie the lower cluster_id is treated as the 'larger' reference so
    the higher id is dropped — giving a deterministic outcome independent of
    input order.

    A dropped cluster is never re-evaluated as a 'larger' reference because only
    clusters in `live` are iterated as refs — a dropped cluster is never appended
    to `live`.

    Returns (kept, drops) where drops entries share the duplicates_skipped
    shape: {cluster_id, reason, existing_moc}.
    """
    if len(clusters) <= 1:
        return list(clusters), []

    sorted_clusters = sorted(
        clusters,
        key=lambda c: (-len(c.get("candidate_stems") or []), c.get("cluster_id", "")),
    )

    # Each entry: (cluster_dict, frozenset_of_members) — member sets built once.
    live: list[tuple[dict, frozenset[str]]] = []
    drops: list[dict] = []

    for candidate in sorted_clusters:
        cid = candidate.get("cluster_id", "")
        cand_members = frozenset(candidate.get("candidate_stems") or [])
        cand_size = len(cand_members)

        if cand_size == 0:
            # Empty cluster cannot be absorbed — treat as surviving.
            live.append((candidate, cand_members))
            continue

        absorbed = False
        for ref, ref_members in live:
            overlap = len(cand_members & ref_members) / cand_size
            if overlap >= _MEMBER_OVERLAP_THRESHOLD:
                drops.append({
                    "cluster_id": cid,
                    "reason": "member-overlap",
                    "existing_moc": ref.get("cluster_id", ""),
                })
                _log(
                    f"d3: cluster {cid!r} member-overlap={overlap:.2f} "
                    f"vs {ref.get('cluster_id')!r} — dropping"
                )
                absorbed = True
                break

        if not absorbed:
            live.append((candidate, cand_members))

    # Restore original input order for the kept set to keep downstream stable.
    kept_ids = {c.get("cluster_id", "") for c, _ in live}
    kept = [c for c in clusters if c.get("cluster_id", "") in kept_ids]
    return kept, drops
