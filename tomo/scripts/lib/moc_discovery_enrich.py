# version: 0.1.0
"""moc_discovery_enrich.py — Phases 4 and 5 of moc-discovery: titles, parents, cluster metadata.

Phase 4 turns a cluster topic into a proposed MOC title with the profile's
suffix; Phase 5 offers up to three classification parents by keyword overlap.
`_enrich_cluster` applies both plus the cluster metadata the reducer renders.
`moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_enrich.md (issue #216).
"""
from __future__ import annotations

from dataclasses import dataclass

from lib.moc_discovery_common import DEFAULT_PROFILES_DIR
from lib.profile_conventions import ensure_suffix, resolve_conventions
from lib.slugify import slugify


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 — Title generation (per-profile suffix + mode override)
# ──────────────────────────────────────────────────────────────────────────────


def _topic_title(cluster: dict) -> str:
    """Title-case a cluster's normalised topic into a TopicTitle.

    Phase 3's reducer normalises topics (lowercase, plural-fold) and emits the
    cluster keyed off the normalised form. For display we Title-Case it —
    "shell" → "Shell". Multi-word topics have their internal whitespace
    preserved ("knowledge management" → "Knowledge Management").
    """
    topic_raw = (cluster.get("topic") or "").strip()
    if not topic_raw:
        return ""
    # `str.title()` is good enough here: cluster topics are short
    # noun-phrases produced by Phase 2's topic extractor and Phase 3's
    # normalisation already lower-cased them.
    return topic_raw.title()


def phase4_title(
    cluster: dict,
    profile: dict,
    mode: str,
    trigger_arg: str,
) -> str:
    """Per-cluster title generation, profile- and mode-aware.

    Args:
        cluster: A Phase-3 `Cluster` dict (`{topic, items, parent, tags}`).
        profile: The active profile dict (post-`yaml.safe_load`). The MOC-title
            suffix is read from its `concept_defaults.map_note.name_suffix`
            (via `resolve_conventions`), not a name-keyed hardcoded table.
        mode: The /moc-propose run mode (`tag` / `folder` / `class` / `title`
            / `free-text` / `scan`).
        trigger_arg: The mode's argument; used verbatim when `mode == "title"`.

    Returns:
        The proposed MOC title string.

    Behaviour:
      - `mode == "title"` → user input wins regardless of profile.
      - Otherwise: TitleCase(cluster.topic) + profile suffix (apply-once).

    Pure: input dicts are not mutated.
    """
    # User-provided title — verbatim, untouched (PRD AC-2.4).
    if mode == "title":
        return trigger_arg

    topic_title = _topic_title(cluster)
    suffix = resolve_conventions(
        profile_dict=profile, profiles_dir=DEFAULT_PROFILES_DIR
    ).moc_suffix
    if suffix and topic_title.endswith(" MOC"):
        topic_title = topic_title[:-4]
    if topic_title.strip().upper() == "MOC":
        return topic_title
    return ensure_suffix(topic_title, suffix)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 5 — Parent resolution (classification keyword overlap)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ParentOption:
    """One offered parent for a Proposed MOC.

    Per SDD §Application Data Models line 547:
        parent_options_per_cluster: dict[cluster_id, list of {moc_stem,
                                                              confidence,
                                                              label}]
    """

    moc_stem: str
    confidence: float
    label: str


def _cluster_topic_keywords(cluster: dict) -> list[str]:
    """Extract the keyword bag a cluster will be scored against.

    Two shapes are supported:
      - Phase-3 default: only `cluster.topic` (single normalised string).
        Returns `[topic]`.
      - Future / explicit: `cluster.topic_keywords: list[str]` set upstream
        by callers carrying multi-keyword context.

    The result is lower-cased, whitespace-trimmed, and de-duplicated — same
    treatment the lib applies to candidates.
    """
    raw: list[str] = []
    if isinstance(cluster.get("topic_keywords"), list):
        raw.extend(str(t) for t in cluster["topic_keywords"] if t)
    if cluster.get("topic"):
        raw.append(str(cluster["topic"]))

    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        norm = t.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _category_keywords(cat: dict) -> list[str]:
    """Lower-cased, deduplicated keyword list from a profile category."""
    raw = cat.get("keywords") or []
    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        norm = str(t).strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _format_parent_label(klass: str, name: str) -> str:
    """Human-readable label, e.g. `"Applied Sciences (Dewey 2600)"`."""
    return f"{name} (Dewey {klass})"


def _format_parent_stem(klass: str, name: str) -> str:
    """Canonical classification-MOC stem, e.g. `"2600 - Applied Sciences"`.

    Mirrors the existing convention seen across miyo vault MOCs and the
    tier-3 docs (e.g. `Atlas/200 Maps/2600 - Applied Sciences.md`).
    """
    return f"{klass} - {name}"


def phase5_resolve_parents(
    cluster: dict,
    profile: dict,
    cache: dict,
) -> list[ParentOption]:
    """Match cluster topics against profile classification → top-3 ParentOptions.

    Args:
        cluster: Phase-3 `Cluster` (or enriched with `topic_keywords`).
        profile: The active profile dict. Reads
            `profile.classification.categories` — a mapping
            `{NNNN: {name, keywords}}`.
        cache: The discovery cache. Reserved for future MOC-level matching
            (per SDD line 877 — `cache.moc_likes`); currently unused by the
            classification-only resolver.

    Returns:
        List of `ParentOption` sorted by `confidence` DESC, capped at 3
        entries. Categories with zero keyword overlap are excluded. An
        empty list signals "no confident parent" (the caller should fall
        back to top-level placement per SDD §Pseudocode line 877 +
        tier-3/lyt-moc/moc-matching.md §5).

    Pure: input dicts are not mutated.
    """
    del cache  # reserved for MOC-level matching in T2.6+

    classification = profile.get("classification") or {}
    categories = classification.get("categories") or {}
    if not categories:
        return []

    cluster_keywords = _cluster_topic_keywords(cluster)
    if not cluster_keywords:
        return []
    cluster_set = set(cluster_keywords)

    scored: list[ParentOption] = []
    for klass_key, cat in categories.items():
        if not isinstance(cat, dict):
            continue
        klass = str(klass_key)
        name = (cat.get("name") or "").strip()
        cat_keywords = _category_keywords(cat)
        if not cat_keywords:
            continue
        cat_set = set(cat_keywords)
        overlap = cluster_set & cat_set
        if not overlap:
            continue
        # Overlap-ratio score, denominator = max(len(cluster_keywords), 1)
        # to prevent div-by-zero on degenerate empty input (already
        # short-circuited above, but kept defensive).
        confidence = len(overlap) / max(len(cluster_keywords), 1)
        scored.append(
            ParentOption(
                moc_stem=_format_parent_stem(klass, name),
                confidence=round(confidence, 4),
                label=_format_parent_label(klass, name),
            )
        )

    # Sort descending by confidence; stable on ties (insertion order = profile
    # iteration order, which is YAML-key order — deterministic).
    scored.sort(key=lambda p: p.confidence, reverse=True)
    return scored[:3]


# ──────────────────────────────────────────────────────────────────────────────
# Cluster enrichment (Phase 4 + Phase 5 + metadata)
# ──────────────────────────────────────────────────────────────────────────────


def _enrich_cluster(
    cluster: dict,
    idx: int,
    profile_dict: dict,
    cache: dict,
    mode: str,
    trigger_arg: str,
    denom: int,
    moc_location: str,
) -> tuple[dict, list[dict]]:
    """Apply Phase 4 (title) + Phase 5 (parents) + metadata to one raw cluster.

    Returns (enriched_cluster, parent_options_list). Pure — does not mutate input.
    """
    cluster_id = f"MOC{idx:02d}"
    title = phase4_title(cluster, profile_dict, mode, trigger_arg)
    parent_opts = phase5_resolve_parents(cluster, profile_dict, cache)

    confidence = round(len(cluster.get("items") or []) / denom, 4)
    topic_kw = [cluster["topic"]] if cluster.get("topic") else []

    enriched = dict(cluster)
    enriched.update({
        "cluster_id": cluster_id,
        "title": title,
        "confidence": confidence,
        "candidate_stems": list(cluster.get("items") or []),
        "topic_keywords": topic_kw,
        "location": moc_location,
        "template": "t_moc_tomo",
        "slug": slugify(title),
        "existing_up": [],
    })
    return enriched, _serialise_parents(parent_opts)


def _serialise_parents(parent_opts: list[ParentOption]) -> list[dict]:
    return [
        {"moc_stem": p.moc_stem, "confidence": p.confidence, "label": p.label}
        for p in parent_opts
    ]


def _moc_location(profile_dict: dict) -> str:
    """Folder for a new MOC: the profile's first `map_note.paths` entry."""
    map_note_cfg = (profile_dict.get("concept_defaults") or {}).get("map_note") or {}
    return (map_note_cfg.get("paths") or ["Atlas/200 Maps/"])[0]
