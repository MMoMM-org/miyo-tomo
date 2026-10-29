# version: 0.1.0
"""moc_discovery_existing_up.py — Phase 6.5 of moc-discovery: existing-`up::` validation.

Reads each kept cluster child once through Kado and classifies its declared
parent as absent / valid / broken against the cached MOC and note stems, so
the proposal can say which children already have a parent and why one is
broken. `moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_existing_up.md (issue #216).
"""
from __future__ import annotations

from lib.moc_discovery_common import Candidate, _log, _stem_from_path
from lib.up_parse import parse_up_from_content, up_marker_re
from lib.up_state import BROKEN, classify_up_target


# ──────────────────────────────────────────────────────────────────────────────
# Phase 6.5 — Existing-`up::` validation per candidate
# ──────────────────────────────────────────────────────────────────────────────

# Match a single inline parent-marker relationship line whose target is a
# wikilink. T2.2: target RESOLUTION goes through lib/up_parse.parse_up_from_content
# (dual-up: inline + frontmatter). The inline-count regex is retained ONLY to
# count inline markers for the multi-marker malformed-note warning — it no longer
# resolves the target. The marker literal is injected from the active profile
# (spec 028 T3.3) via lib.up_parse.up_marker_re, so the warning matches what
# up_parse would pick as the inline candidate.


def _moc_stems_from_cache(cache: dict) -> set[str]:
    """Build a stem-set of every MOC indexed in `cache.map_notes`.

    Phase 6.5 consults this set to decide whether an extracted `up::`
    target is "valid" (target stem present in cache) or "broken"
    (target stem absent). Path is reduced to its basename without
    `.md` to match the wikilink-target shape (which carries the stem,
    not the full path).
    """
    stems: set[str] = set()
    for entry in cache.get("map_notes") or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if path:
            stems.add(_stem_from_path(path))
        # Honour explicit titles too — a wikilink target may use the
        # human-readable title rather than the file stem when they differ.
        title = (entry.get("title") or "").strip()
        if title:
            stems.add(title)
    return stems


def _note_stems_from_cache(cache: dict) -> set[str]:
    """Stems of every cached non-MOC note (`entries` with kind == "note")."""
    stems: set[str] = set()
    for entry in cache.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("kind") != "note":
            continue
        stem = entry.get("stem") or _stem_from_path((entry.get("path") or "").strip())
        if stem:
            stems.add(stem)
    return stems


def phase65_validate_existing_up(
    clusters: list[dict],
    candidates: list[Candidate],
    kado_client,
    cache: dict,
    parent_marker: str = "up::",
) -> list[dict]:
    """Decorate each cluster's children with their existing-`up::` state.

    For every child stem in ``cluster.items``, read the candidate's note
    body via Kado, extract the first `up::` marker, and classify it
    against `cache.map_notes`:

      - No `up::` line                 → state="absent",  target=None
      - `up:: [[X]]` and X in cache    → state="valid",   target="X"
      - `up:: [[X]]` and X NOT in cache → state="broken",  target="X",
        reason="not-a-moc" (X is a cached non-MOC note) or "unresolved"

    Multiple `up::` lines on the same child surface as a stderr WARN —
    Phase 6.5 keeps the first match and downstream Rule 4.2 / 4.5 logic
    operates on it. Reading from Kado is the only side-effect.

    .. note::
        The plan signature is documented as ``(clusters, kado_client)``;
        the implementation accepts ``candidates`` and ``cache`` too because
        (a) Phase-3 clusters carry stems but not paths, so we need the
        upstream candidates list to resolve stem → path for Kado reads,
        and (b) cache.map_notes is the authoritative MOC index used to
        classify `valid` vs. `broken` targets without an extra Kado round
        trip per candidate. Documented as a deviation in plan/phase-2.md
        T2.7.

    Args:
        clusters: Phase-6-kept clusters (`{topic, items, parent, tags,
            ...}`). Each cluster's `items` is a list of candidate stems.
        candidates: The Phase-1/2 candidate list, used to resolve
            stem → path. Stems missing from the lookup map are skipped
            (defensive — should never happen in normal flow).
        kado_client: Anything exposing ``read_note(path) -> {"content": str, ...}``.
        cache: Discovery cache dict; Phase 6.5 reads `map_notes` only.

    Returns:
        The input clusters, each augmented in-place with an
        ``existing_up: list[{stem, state, target[, reason]}]`` field. Order follows
        ``cluster.items`` for deterministic downstream rendering.

    Side effects:
        - One `kado_client.read_note` call per candidate.
        - Stderr WARN per multi-`up::` body.
        - Stderr WARN per failed Kado read (treated as absent, loop continues).
    """
    stem_to_path: dict[str, str] = {c.stem: c.path for c in candidates if c.stem}
    moc_stems = _moc_stems_from_cache(cache)
    note_stems = _note_stems_from_cache(cache)
    inline_marker_re = up_marker_re(parent_marker)

    multi_up_count = 0

    for cluster in clusters or []:
        rows: list[dict] = []
        for item in cluster.get("items") or []:
            # Cluster items can be plain stems (Phase-3 default) OR enriched
            # dicts (forward-compat with downstream tasks). Normalise here.
            if isinstance(item, str):
                stem = item
            elif isinstance(item, dict):
                stem = item.get("stem") or item.get("path") or ""
            else:
                continue
            if not stem:
                continue

            path = stem_to_path.get(stem)
            if not path:
                # Defensive: cluster references a stem that never appeared
                # in candidates — skip rather than guess at a path.
                _log(
                    f"phase6.5: WARN: cluster item {stem!r} not in candidate "
                    f"list; skipping existing-up:: validation for this child"
                )
                continue

            # Guard against Kado read failures (note deleted between
            # candidate collection and Phase 6.5, network error, permission
            # denied, …). A single failing read must NOT abort decoration of
            # the remaining candidates — we treat the unreadable child as
            # `state="absent"` so downstream rendering keeps moving.
            try:
                note = kado_client.read_note(path)
            except Exception as exc:  # noqa: BLE001 — defensive boundary
                _log(
                    f"phase6.5: WARN: kado read_note({path!r}) failed "
                    f"({type(exc).__name__}: {exc}); treating as absent"
                )
                rows.append({"stem": stem, "state": "absent", "target": None})
                continue

            content = note.get("content", "") if isinstance(note, dict) else ""

            # Multi-inline-`up::` detection: count inline marker hits before
            # resolving so the warning fires per-note, not per-cluster. (The
            # warning is inline-specific — a single frontmatter `up:` plus one
            # inline `up::` is the normal conflict case, resolved by inline-wins,
            # not a malformed multi-marker note.)
            inline_targets = inline_marker_re.findall(content)
            if len(inline_targets) > 1:
                multi_up_count += 1
                _log(
                    f"WARN: multiple {parent_marker} markers in {path}; using first "
                    f"({inline_targets[0]!r}, dropped {len(inline_targets) - 1} more)"
                )

            # T2.2 (C1/ADR-6): resolve the `up` relationship from the SAME
            # read_note content via the up_parse SSoT — recognises both inline
            # `up:: [[X]]` and frontmatter `up:` (inline wins on conflict),
            # splitting the frontmatter block locally with no extra Kado call.
            target = parse_up_from_content(content, parent_marker).target
            state, reason = classify_up_target(target, moc_stems, note_stems)
            row = {"stem": stem, "state": state, "target": target}
            if state == BROKEN:
                row["reason"] = reason
            rows.append(row)

        cluster["existing_up"] = rows

    _log(
        f"phase6.5: decorated {len(clusters or [])} cluster(s); "
        f"multi-up:: warnings={multi_up_count}"
    )
    return list(clusters or [])
