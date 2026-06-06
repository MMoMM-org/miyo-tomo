# version: 0.1.2
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
    # Precompute O(1) lookup indexes — one scan of each set, never per-link
    moc_stem_index = _build_stem_index(known_moc_paths)
    vault_stem_index = _build_stem_index(in_scope_vault_paths)

    placeholders: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for moc_path, moc in mocs.items():
        for link in moc.get("linked_notes_raw", []):
            note_target = _strip_link_anchor(link)
            # Same-note anchor (#heading / #^block) — not a missing-note link.
            if not note_target:
                continue
            # Resolves to a known MOC?
            if _resolves_to_moc(note_target, moc_stem_index):
                continue
            # Resolves to any in-scope vault note by filename?
            link_name = note_target.split("/")[-1].lower()
            if link_name.endswith(".md"):
                link_name = link_name[:-3]
            if link_name in vault_stem_index:
                continue
            # Genuine placeholder — dedupe by (resolved-note, moc-path)
            key = (note_target, moc_path)
            if key not in seen:
                seen.add(key)
                placeholders.append({"target": note_target, "referenced_by": moc_path})

    return placeholders
