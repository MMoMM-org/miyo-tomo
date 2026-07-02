# version: 1.1.0
"""moc_tags.py — Hardwired tag constants for MOC-proposal exclude semantics (ADR-13).

Single home for exclude-tag strings consumed by orphan_link.py and
moc-discovery.py.  Import from here — do not inline strings.

FRONTMATTER OR INLINE (#50): these tags are read via
moc-tree-builder.extract_tags, which merges the YAML frontmatter `tags:` list
with inline `#tags` from the note body (code blocks skipped). Both forms are
equivalent — matching MOC *discovery* (`#type/others/moc`), which goes through
Kado `search_by_tag` and matches inline + frontmatter. Either works:

    tags: [MiYo/Tomo/exclude/moc]      # frontmatter — or .../exclude/note
    #MiYo/Tomo/exclude/moc             # inline in the body

Spec: docs/XDD/specs/021-moc-propose-consolidation/ — SDD ADR-13 B-moc, B-note.
"""
from __future__ import annotations

# ADR-13 B-moc: skip entry in emit_orphan_suggestions(kinds=("moc",));
# the MOC STAYS in the cache + link-candidate pool.
EXCLUDE_MOC_TAG = "MiYo/Tomo/exclude/moc"

# ADR-13 B-note: filter at the scan candidate source (_handle_scan, cache-based)
# so a tagged note is never clustered into a proposed MOC.
EXCLUDE_NOTE_TAG = "MiYo/Tomo/exclude/note"
