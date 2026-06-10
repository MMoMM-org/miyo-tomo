# version: 0.2.0
"""placeholder_detect.py — Wikilink placeholder detection for MOC bodies.

Extracted from moc-tree-builder.py's detect_placeholders for use by the
MOC-structure cache builder (spec 021, T1.3).

Key change vs the original: the denominator is `in_scope_vault_paths`, the
FULL set of in-scope vault notes — not just the 89-MOC set. This eliminates
the 224 false-positive placeholders that inflated the shared-ctx budget.

Algorithm (verbatim from SDD §placeholder-correction):
    For each wikilink L in each MOC body:
        note = strip_anchor(L)          # "X#^id"/"X#Heading" → "X"; "" → skip
        if resolves_to_known_moc(note): continue
        if note in real_in_scope_vault_set: continue   # the 224 fix
        emit {target: note, referenced_by: moc_path}, deduped per (note, moc)

Public API:
    detect_placeholders(
        mocs: dict[str, dict],
        known_moc_paths: set[str],
        in_scope_vault_paths: set[str],
    ) -> list[dict[str, str]]

    Returns list of {"target": str, "referenced_by": str}, one entry per
    (missing-note, referencing-MOC) pair.  The shape is identical to the
    legacy detect_placeholders output so T1.4 can wire this in without a
    consumer change.
"""
from __future__ import annotations

import os
import re

# Periodic-note (daily/weekly/monthly) target shapes. A date is never a MOC, and
# daily notes live outside the MOC scope_paths so links into them cannot resolve
# against in_scope_vault_paths — without this guard they leak as placeholder MOCs.
# Matches the exact target only (start/end anchored): daily YYYY-MM-DD, weekly
# YYYY-Www, monthly YYYY-MM. Year-themed MOCs ("2024 Goals", "2024-Q1 Review")
# carry a suffix and do NOT match, so they remain genuine placeholders.
_PERIODIC_NOTE_RE = re.compile(r"^\d{4}-(?:\d{2}-\d{2}|W\d{2}|\d{2})$", re.IGNORECASE)


def _is_periodic_note_target(note_target: str) -> bool:
    """Return True if note_target is a date-shaped periodic note (daily/weekly/monthly)."""
    return bool(_PERIODIC_NOTE_RE.match(note_target))


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _basename_no_ext(path: str) -> str:
    """Return filename without .md extension."""
    name = os.path.basename(path)
    if name.endswith(".md"):
        name = name[:-3]
    return name


def _strip_link_anchor(target: str) -> str:
    """Strip an Obsidian anchor (#heading or #^blockid) from a wikilink target.

    Returns the note portion of the link. A same-note anchor such as
    "#^9c2026" or "#Some Heading" has no note portion and yields "".
    """
    return target.split("#", 1)[0].strip()


def _build_stem_index(paths: set[str]) -> dict[str, str]:
    """Build a {stem.lower(): path} index for O(1) name-based lookup.

    Precomputed once per call so MOC-name resolution is O(1) per link
    instead of the O(M) scan resolve_link_to_path did on every link.
    """
    return {_basename_no_ext(p).lower(): p for p in paths}


def _resolves_to_moc(note_target: str, moc_stem_index: dict[str, str]) -> bool:
    """Return True if note_target resolves to a known MOC by path or filename."""
    bare = note_target[:-3] if note_target.endswith(".md") else note_target
    # Filename (case-insensitive) match — handles both plain and path-qualified links
    link_name_lower = bare.split("/")[-1].lower()
    return link_name_lower in moc_stem_index


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def detect_placeholders(
    mocs: dict[str, dict],
    known_moc_paths: set[str],
    in_scope_vault_paths: set[str],
) -> list[dict[str, str]]:
    """Find wikilink targets in MOC bodies that don't resolve to any known note.

    A placeholder is a wikilink target that, once anchor-stripped:
    - Is non-empty (a bare "#^block"/"#heading" same-note anchor is not a link
      to a missing note)
    - Does not resolve to a known MOC (by filename, case-insensitive)
    - Does not match any in-scope vault note (by filename, case-insensitive)

    Block-reference and heading anchors ("Note#^id", "Note#Heading") are
    reduced to their target note before the dead-link test, and results are
    deduped per (note, referencing MOC) — multiple anchored references into one
    existing note collapse to nothing; multiple anchored references into one
    *missing* note produce exactly one placeholder entry.

    Args:
        mocs: mapping of {moc_path: moc_dict}; each dict must have
            "linked_notes_raw": list[str] with raw wikilink targets.
        known_moc_paths: full set of discovered MOC paths (e.g. from moc-scan).
            Used to exclude MOC-to-MOC links from the placeholder set.
        in_scope_vault_paths: the FULL set of in-scope vault note paths
            (replaces the legacy all_vault_paths that was only the MOC set).
            This is the fix for the 224 false-positive inflation.

    Returns:
        list of {"target": str, "referenced_by": str}, deduped per (note, moc).
        Shape is identical to the legacy detect_placeholders output.
    """
    placeholders, _stats = detect_placeholders_with_stats(
        mocs, known_moc_paths, in_scope_vault_paths
    )
    return placeholders


def detect_placeholders_with_stats(
    mocs: dict[str, dict],
    known_moc_paths: set[str],
    in_scope_vault_paths: set[str],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Same detection as `detect_placeholders`, plus a build-stats breakdown.

    The stats power the PRD `placeholder.build` observability event (M2/M4):

        raw_count               — note-link references examined (non-empty after
                                   anchor strip); the pre-correction candidate pool
        anchor_dropped          — same-note anchors (#heading/#^block) skipped
        date_dropped            — date-shaped periodic-note targets skipped
        moc_resolved            — links that resolve to a known MOC (MOC↔MOC)
        vault_resolved          — links resolving to a real in-scope note (the 224 fix)
        false_positive_dropped  — vault_resolved + date_dropped (the correction)
        kept_count              — genuine placeholders emitted (post per-(note,moc) dedup)
    """
    # Precompute O(1) lookup indexes — one scan of each set, never per-link
    moc_stem_index = _build_stem_index(known_moc_paths)
    vault_stem_index = _build_stem_index(in_scope_vault_paths)

    placeholders: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    stats = {
        "raw_count": 0,
        "anchor_dropped": 0,
        "date_dropped": 0,
        "moc_resolved": 0,
        "vault_resolved": 0,
        "false_positive_dropped": 0,
        "kept_count": 0,
    }

    for moc_path, moc in mocs.items():
        for link in moc.get("linked_notes_raw", []):
            note_target = _strip_link_anchor(link)
            # Same-note anchor (#heading / #^block) — not a missing-note link.
            if not note_target:
                stats["anchor_dropped"] += 1
                continue
            stats["raw_count"] += 1
            # Date-shaped periodic note (daily/weekly/monthly) — never a MOC.
            if _is_periodic_note_target(note_target):
                stats["date_dropped"] += 1
                continue
            # Resolves to a known MOC?
            if _resolves_to_moc(note_target, moc_stem_index):
                stats["moc_resolved"] += 1
                continue
            # Resolves to any in-scope vault note by filename?
            link_name = note_target.split("/")[-1].lower()
            if link_name.endswith(".md"):
                link_name = link_name[:-3]
            if link_name in vault_stem_index:
                stats["vault_resolved"] += 1
                continue
            # Genuine placeholder — dedupe by (resolved-note, moc-path)
            key = (note_target, moc_path)
            if key not in seen:
                seen.add(key)
                placeholders.append({"target": note_target, "referenced_by": moc_path})

    stats["false_positive_dropped"] = stats["vault_resolved"] + stats["date_dropped"]
    stats["kept_count"] = len(placeholders)
    return placeholders, stats
