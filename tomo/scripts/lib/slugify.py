# slugify.py — Filename-safe slug helper, shared between instruction-render and moc-discovery.
# version: 0.1.0
"""Convert a human title into a filename-safe slug.

Why this lives in a module of its own:
Two callers need byte-identical slugs for vault paths — `instruction-render.py`
(rendering Pass-2 atomic notes and proposed MOCs) and `moc-discovery.py` Phase 4
(deriving the `<slug>.md` filename for a Proposed MOC). The helper used to live
inline in instruction-render.py; it was extracted as part of F-43 Phase 2 T2.5
so moc-discovery can reuse it cleanly without a hyphenated-module import dance.

Pure: stdlib only, no I/O. Inputs are not mutated.
"""
from __future__ import annotations

import re

__all__ = ["slugify"]


def slugify(text: str) -> str:
    """Convert a title to a filename-safe slug.

    Rules (preserved verbatim from the original instruction-render
    implementation so existing rendered filenames stay stable):

      - Lowercase the whole string.
      - German umlauts and ß fold to ASCII (ä→ae, ö→oe, ü→ue, ß→ss).
      - Any run of non-`[a-z0-9]` characters collapses to a single `-`.
      - Leading and trailing `-` are stripped.
      - The result is capped at 80 characters (filename safety on every FS
        Tomo targets).

    Examples:
        >>> slugify("Shell & Terminal MOC")
        'shell-terminal-moc'
        >>> slugify("Größenordnung")
        'groessenordnung'
    """
    s = text.lower()
    s = re.sub(r"[äÄ]", "ae", s)
    s = re.sub(r"[öÖ]", "oe", s)
    s = re.sub(r"[üÜ]", "ue", s)
    s = re.sub(r"ß", "ss", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:80]  # cap length
