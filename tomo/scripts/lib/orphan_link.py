# version: 0.3.0
"""orphan_link.py — Case-(a) orphan pass over the MOC-structure cache (ADR-7).

Runs AFTER moc_cache_loader provides cache.entries. Enumerates orphans —
entries whose `up_state == "absent"` and whose `kind` is in the requested
`kinds` set (default notes-only, ADR-12) — and for each one scores its topic
keywords against the existing MOC set (entries[kind=="moc"]), emitting one
OrphanLinkSuggestion:

    ≥1 MOC at/above LINK_THRESHOLD  → mode="link_existing", candidates=top-3
                                      [{target_moc, score}] sorted by score DESC
                                      (OQ-4).
    no MOC clears the threshold      → mode="create_new" + a human-readable reason
                                      (rendered into the proposal-doc; on accept,
                                      `/inbox` renders the apply instruction — no
                                      vault note is written here).

Design boundaries (SDD ADR-7):
  - H2: this is a NEW pass over the cache. It does NOT modify Phase 6
    `duplicates_skipped` (which dedupes clusters against MOCs — a different unit).
  - H3: orphan MOCs are eligible simply because they are cache entries. This pass
    does NOT relax `restrict_to_atomic_note_paths` (the Phase-1 atomic-note
    pre-filter on the clustering path stays intact and untouched).

Scoring reuses the Phase-5/6 keyword-overlap approach: lowercased topic sets,
overlap ratio = |orphan ∩ moc| / |orphan topics| (the same denominator as
phase5_resolve_parents). Implemented locally rather than imported from the
hyphen-named moc-discovery.py — moc-discovery is this module's CALLER, so a local
scorer avoids a circular import while keeping identical semantics.

Spec: docs/XDD/specs/021-moc-propose-consolidation/ — SDD Implementation Examples
(case-(a)); ADR-7; OQ-4; PRD Feature 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lib.moc_tags import EXCLUDE_MOC_TAG, EXCLUDE_NOTE_TAG  # noqa: F401

# Minimum overlap ratio for an existing MOC to be offered as a link candidate.
# Below this, the orphan gets a create_new proposal instead. Mirrors the
# overlap-ratio scoring of phase5_resolve_parents (|overlap| / |orphan topics|).
LINK_THRESHOLD = 0.5

# Maximum link candidates surfaced per orphan (OQ-4).
TOP_N = 3


# ──────────────────────────────────────────────────────────────────────────────
# Result type
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class OrphanLinkSuggestion:
    """One link-or-create suggestion for an orphan cache entry.

    Mirrors the SDD OrphanLinkSuggestion entity. `candidates` is populated only
    for mode="link_existing"; `reason` only for mode="create_new".
    """

    stem: str
    path: str
    kind: str                                  # "note" | "moc"
    mode: str                                  # "link_existing" | "create_new"
    candidates: list[dict] = field(default_factory=list)  # [{target_moc, score}]
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "stem": self.stem,
            "path": self.path,
            "kind": self.kind,
            "mode": self.mode,
            "candidates": list(self.candidates),
            "reason": self.reason,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Scoring (Phase-5/6 keyword-overlap approach)
# ──────────────────────────────────────────────────────────────────────────────

def _topic_set(entry: dict) -> set[str]:
    """Lowercased, stripped topic set for a cache entry (empty when none)."""
    out: set[str] = set()
    for t in entry.get("topics") or []:
        if t is None:
            continue
        norm = str(t).strip().lower()
        if norm:
            out.add(norm)
    return out


def _overlap_ratio(orphan_topics: set[str], moc_topics: set[str]) -> float:
    """Overlap ratio = |orphan ∩ moc| / |orphan topics|.

    Same denominator as phase5_resolve_parents — "how much of the orphan's topic
    surface this MOC covers". 0.0 when the orphan has no topics (caller routes
    those straight to create_new before reaching here).
    """
    if not orphan_topics:
        return 0.0
    return len(orphan_topics & moc_topics) / len(orphan_topics)


def _score_against_mocs(orphan: dict, moc_entries: list[dict]) -> list[dict]:
    """Score one orphan against every MOC; return [{target_moc, score}] sorted
    DESC, threshold-gated, capped at TOP_N. Excludes the orphan itself (an
    orphan MOC must not link to itself).
    """
    orphan_topics = _topic_set(orphan)
    if not orphan_topics:
        return []

    orphan_path = orphan.get("path")
    scored: list[dict] = []
    for moc in moc_entries:
        if moc.get("path") == orphan_path:
            continue  # never offer self as a candidate
        score = _overlap_ratio(orphan_topics, _topic_set(moc))
        if score >= LINK_THRESHOLD:
            target = moc.get("stem") or moc.get("title") or ""
            scored.append({"target_moc": target, "score": round(score, 4)})

    # DESC by score; stable on ties (insertion order = entries order, deterministic).
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:TOP_N]


def _build_reason(orphan: dict, had_any_overlap: bool) -> str:
    """Human-readable reason for a create_new proposal."""
    topics = [str(t).strip() for t in (orphan.get("topics") or []) if str(t).strip()]
    kind = orphan.get("kind", "note")
    if not topics:
        return (
            f"No topics extracted for this {kind}; no existing MOC could be "
            "matched. Proposing a new MOC."
        )
    topic_str = ", ".join(topics)
    if had_any_overlap:
        return (
            f"No existing MOC covers enough of this {kind}'s topics "
            f"({topic_str}) to meet the link threshold. Proposing a new MOC."
        )
    return (
        f"No existing MOC shares this {kind}'s topics ({topic_str}). "
        "Proposing a new MOC."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def emit_orphan_suggestions(
    entries: list[dict], *, kinds: tuple[str, ...] = ("note",)
) -> list[dict]:
    """Emit one link-or-create suggestion per orphan cache entry.

    Parameters
    ----------
    entries:
        The cache `entries` list (CacheEntry dicts) as provided by
        moc_cache_loader — both notes and MOCs, each carrying `up_state`,
        `topics`, `stem`, `path`, `kind`.
    kinds:
        Which orphan kinds to emit suggestions for (ADR-12). Defaults to
        notes-only (`("note",)`) — the whole-vault scan path. Pass
        `("moc",)` for the on-demand MOC-uplink audit, or `("note", "moc")`
        for both. MOCs are ALWAYS the link-candidate pool regardless of
        `kinds` (an orphan note still links to an existing MOC).

    Returns
    -------
    list[dict] — OrphanLinkSuggestion dicts (see OrphanLinkSuggestion.to_dict),
    one per in-scope orphan (`up_state == "absent"` and `kind in kinds`),
    ordered `link_existing` first (by top-candidate score DESC) then
    `create_new` (input order preserved within each group). Orphans that match
    ≥1 MOC at/above LINK_THRESHOLD get mode="link_existing" with up to TOP_N
    candidates; the rest get mode="create_new" with a reason.
    """
    # moc_entries: ALL MOC cache entries, used as the link-candidate pool.
    # ADR-13 B-moc: excluded MOCs STAY in this pool — only suppressed from audit output.
    moc_entries = [
        e for e in entries
        if isinstance(e, dict) and e.get("kind") == "moc"
    ]

    # Per-kind exclude tag map: kind → tag that suppresses it from the audit.
    _EXCLUDE_TAG_BY_KIND: dict[str, str] = {
        "moc": EXCLUDE_MOC_TAG,
        "note": EXCLUDE_NOTE_TAG,
    }

    orphans = [
        e for e in entries
        if isinstance(e, dict)
        and e.get("up_state") == "absent"
        and e.get("kind") in kinds
        and _EXCLUDE_TAG_BY_KIND.get(e.get("kind", ""), "") not in (e.get("tags") or [])
    ]

    out: list[dict] = []
    for orphan in orphans:
        candidates = _score_against_mocs(orphan, moc_entries)
        if candidates:
            suggestion = OrphanLinkSuggestion(
                stem=orphan.get("stem", ""),
                path=orphan.get("path", ""),
                kind=orphan.get("kind", "note"),
                mode="link_existing",
                candidates=candidates,
            )
        else:
            # Distinguish "had some overlap but below threshold" from "no overlap
            # at all" for a clearer reason string.
            orphan_topics = _topic_set(orphan)
            had_any_overlap = any(
                orphan_topics & _topic_set(m)
                for m in moc_entries
                if m.get("path") != orphan.get("path")
            )
            suggestion = OrphanLinkSuggestion(
                stem=orphan.get("stem", ""),
                path=orphan.get("path", ""),
                kind=orphan.get("kind", "note"),
                mode="create_new",
                reason=_build_reason(orphan, had_any_overlap),
            )
        out.append(suggestion.to_dict())

    # Order for display (ADR-12): most-actionable first — link_existing before
    # create_new; within link_existing, highest top-candidate score first.
    # Stable sort preserves input order within each group (and on score ties).
    def _order_key(s: dict) -> tuple[int, float]:
        if s["mode"] == "link_existing":
            top = s["candidates"][0]["score"] if s["candidates"] else 0.0
            return (0, -top)
        return (1, 0.0)

    out.sort(key=_order_key)
    return out
