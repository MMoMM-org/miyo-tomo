#!/usr/bin/env python3
# version: 0.1.0
"""item_key.py — Item identity for the inbox pipeline (spec 034).

Recursive inbox discovery means two notes in different subfolders can share
a filename. Every site that used to key an item by its bare stem would
silently merge those two notes into one. The item key fixes that: it is the
note's vault-relative path itself (ADR-1) — readable in every log and
artefact, and reversible to the file by construction. No slug, no hash of
the value itself.

The only place that needs an encoding step is the filename for an item's
per-item result file (ADR-5): `sanitize_stem` (see obsidian_filename.py) is
deliberately lossy — it replaces forbidden characters but leaves two
distinct paths free to collide on the same readable name, which is the
exact failure this spec removes. `to_filename` instead pairs a readable
stem with a digest of the *exact* key, so it stays distinct even across a
case-insensitive filesystem (CON-6), where the readable half alone would
fold two different paths together.
"""
from __future__ import annotations

import hashlib
import re

# Same forbidden set as obsidian_filename.py — kept independent because this
# module encodes a full path (which legitimately contains "/"), not a bare
# stem, so the two modules solve different problems even though the
# character set they avoid overlaps.
_FORBIDDEN_CHARS = frozenset('\\/:*?"<>|\x00')
_READABLE_MAX_LEN = 40


def derive(source_path: str) -> str:
    """The item key IS the vault-relative path. No transformation, no loss."""
    return source_path


def to_filename(item_key: str) -> str:
    """A filesystem-safe, collision-free name for this key's per-item result file.

    Returns `<readable stem>-<8 hex chars>.result.json`. The digest is taken
    over the exact key (not a lowercased or otherwise normalised form), so
    two keys differing only in letter case still produce different
    filenames even though a case-insensitive filesystem would treat the
    readable half as identical (CON-6).
    """
    if not item_key:
        raise ValueError("item_key must be a non-empty string")
    digest = hashlib.sha256(item_key.encode("utf-8")).hexdigest()[:8]
    readable = _readable_part(item_key)
    return f"{readable}-{digest}.result.json"


def _readable_part(item_key: str) -> str:
    """Best-effort human-legible stem for `to_filename`.

    Not a collision guarantee by itself — that's the digest's job — just
    enough for a human reading tomo-tmp by hand to identify the item.
    """
    stem = item_key.rsplit("/", 1)[-1]
    stem = re.sub(r"\.[^.]+$", "", stem)  # drop extension, if any
    stem = "".join("-" if c in _FORBIDDEN_CHARS or c.isspace() else c for c in stem)
    stem = stem.lower().strip("-") or "item"
    return stem[:_READABLE_MAX_LEN].strip("-") or "item"
