# version: 0.2.0
"""target_suggest.py — on-demand target candidates for garden-audit (spec 030 Phase 7).

Two second-pass suggesters, computed ONLY on a `/garden-audit --suggest`
re-invocation for findings the user opted into (D2) — never during the Pass-1
scan. Both return ``[{"target": str, "score": float}]`` sorted by score DESC,
capped, threshold-gated, with a deterministic tie-break (stem asc) so repeated
runs are byte-stable.

D3 candidate sources:
  dead_link  → difflib (stdlib, NO new dependency) stem fuzzy-match of the dead
               wikilink target against all cache note stems.
  broken_up  → orphan_link topic-overlap of the note (as a pseudo-orphan) against
               MOCs MERGED with stem-similarity of the broken up-target against
               MOC stems (a mistyped MOC name), deduped by MOC stem (max score).
"""
from __future__ import annotations

from difflib import SequenceMatcher

from lib.orphan_link import TOP_N, _score_against_mocs


def _similarity(a: str, b: str) -> float:
    """difflib ratio between two strings (case-insensitive), 0.0–1.0."""
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def suggest_dead_link_targets(
    dead_target: str,
    stems: list[str],
    *,
    cutoff: float = 0.6,
    top_n: int = 3,
) -> list[dict]:
    """Fuzzy-match a dead wikilink target against cache note stems (D3).

    Returns up to ``top_n`` ``{"target", "score"}`` entries whose difflib ratio
    to ``dead_target`` is >= ``cutoff``, sorted by score DESC then target ASC
    (deterministic ties). The dead target's own exact stem is never suggested (a
    self-link would already resolve — it would not be a dead link).
    """
    target = (dead_target or "").strip()
    if not target:
        return []

    scored: list[dict] = []
    for stem in stems:
        s = (stem or "").strip()
        if not s or s == target:
            continue  # skip empties and an exact self-reference
        score = _similarity(target, s)
        if score >= cutoff:
            scored.append({"target": s, "score": round(score, 4)})

    scored.sort(key=lambda c: (-c["score"], c["target"]))
    return scored[:top_n]


def suggest_repoint_mocs(
    note_entry: dict,
    moc_entries: list[dict],
    broken_target: str,
    *,
    top_n: int = TOP_N,
    stem_cutoff: float = 0.6,
) -> list[dict]:
    """Suggest repoint MOCs for a broken ``up::`` (D3).

    Merges two signals, deduped by MOC stem (keeping the higher score):
      1. topic overlap — the note scored against every MOC via the shared
         ``orphan_link._score_against_mocs`` (the note as a pseudo-orphan);
         gated by orphan_link's own ``LINK_THRESHOLD``.
      2. stem similarity — difflib ratio of the broken up-target against each
         MOC stem (catches a mistyped MOC name with no topic overlap); gated by
         ``stem_cutoff`` so unrelated MOCs sharing only the common `` MOC``
         suffix (e.g. ``Writing MOC`` vs ``Cooking MOC`` ≈ 0.64) don't fill the
         pick list as confident-looking-but-wrong candidates.

    Returns up to ``top_n`` ``{"target", "score"}`` entries, sorted by score
    DESC then target ASC (deterministic ties).
    """
    if not moc_entries:
        return []

    best: dict[str, float] = {}

    # Signal 1: topic overlap (reuse the orphan scorer — note as pseudo-orphan).
    # _score_against_mocs returns [{target_moc, score}] threshold-gated + capped;
    # we take its scores and merge, so a below-threshold topic match simply does
    # not contribute (the stem signal may still surface the MOC).
    for cand in _score_against_mocs(note_entry, moc_entries):
        stem = cand.get("target_moc") or ""
        if stem:
            best[stem] = max(best.get(stem, 0.0), float(cand.get("score", 0.0)))

    # Signal 2: stem similarity of the broken up-target against MOC stems,
    # gated by stem_cutoff (parallels suggest_dead_link_targets' cutoff).
    broken = (broken_target or "").strip()
    if broken:
        for moc in moc_entries:
            stem = (moc.get("stem") or moc.get("title") or "").strip()
            if not stem:
                continue
            score = round(_similarity(broken, stem), 4)
            if score >= stem_cutoff:
                best[stem] = max(best.get(stem, 0.0), score)

    merged = [{"target": stem, "score": score} for stem, score in best.items()]
    merged.sort(key=lambda c: (-c["score"], c["target"]))
    return merged[:top_n]
