#!/usr/bin/env python3
# version: 0.1.0
"""obsidian_filename.py — Obsidian-safe filename sanitisation.

Obsidian rejects filenames containing any of `\\ / : * ? " < > |` or null
bytes. Audio files created by external recorders (iOS Voice Memos, desktop
recorders) routinely carry colons in timestamp portions like
`memo 2026-04-20 11:48:29.m4a` — Obsidian's filesystem bridge tolerates
those on read, but `kado-write` rejects them on creation.

The voice-transcription pipeline needs both the CLI (`voice-transcribe.py`)
and the voice-transcriber agent to agree on the transcript target path.
This module is the single source of truth for that conversion.

Usage (Python):

    from lib.obsidian_filename import sanitize_stem
    target_md = sanitize_stem(audio.stem) + ".md"

Usage (CLI, for agent workflows that shell out):

    python3 scripts/lib/obsidian_filename.py "memo 11:48:29"
    # prints: memo 11-48-29
"""
from __future__ import annotations

import sys

# Obsidian-forbidden characters per Obsidian help docs — matches what
# `kado-write` rejects as INTERNAL_ERROR. Replacement char `-` keeps the
# resulting filename human-readable; picking `_` would be equally valid.
FORBIDDEN_CHARS = frozenset('\\/:*?"<>|\x00')
REPLACEMENT = "-"


def sanitize_stem(stem: str) -> str:
    """Return a filename stem with Obsidian-forbidden characters replaced.

    Idempotent: calling twice produces the same result. Empty strings
    pass through unchanged so callers can validate input separately.
    """
    if not stem:
        return stem
    return "".join(REPLACEMENT if c in FORBIDDEN_CHARS else c for c in stem)


def is_obsidian_safe(name: str) -> bool:
    """True iff `name` has no Obsidian-forbidden characters."""
    return not any(c in FORBIDDEN_CHARS for c in name)


def _main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: obsidian_filename.py <stem>\n"
            "  Prints the Obsidian-safe sanitised stem on stdout.",
            file=sys.stderr,
        )
        return 2
    print(sanitize_stem(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
