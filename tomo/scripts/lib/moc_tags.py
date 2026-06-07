# version: 1.0.0
"""moc_tags.py — Hardwired tag constants for MOC-proposal exclude semantics (ADR-13).

Single home for exclude-tag strings consumed by orphan_link.py and
moc-discovery.py.  Import from here — do not inline strings.

Spec: docs/XDD/specs/021-moc-propose-consolidation/ — SDD ADR-13 B-moc, B-note.
"""
from __future__ import annotations

# ADR-13 B-moc: skip entry in emit_orphan_suggestions(kinds=("moc",));
# the MOC STAYS in the cache + link-candidate pool.
EXCLUDE_MOC_TAG = "MiYo/Tomo/exclude/moc"

# ADR-13 B-note: filter at the scan candidate source (_handle_scan, cache-based)
# so a tagged note is never clustered into a proposed MOC.
EXCLUDE_NOTE_TAG = "MiYo/Tomo/exclude/note"
