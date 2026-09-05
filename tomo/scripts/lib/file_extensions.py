#!/usr/bin/env python3
# version: 0.1.0
"""file_extensions.py — Owns the Obsidian-resolvable extension allowlist.

Split out of render_actions.py (spec 031 T1.1 code-quality fix) so that a pure
text library (attachment_index.py) can classify a wikilink target as a file
vs. a note without transitively importing the render pipeline — render_actions
pulls in ~175 modules and executes tag-handler-group.py at import time, which
is incompatible with ADR-2's pure-library boundary.
"""
from __future__ import annotations

# Obsidian-resolvable extensions seen in vault paths derived from wikilinks.
# Used by `_ensure_md_extension` to discriminate a real file extension
# (`Voice.m4a`, `Notes.html`) from a dotted note name (`Foo.Bar`,
# `2026-04-29.draft`). Obsidian allows dots in note titles, so "any dot
# means extension" is wrong — match against this allowlist instead.
KNOWN_FILE_EXTENSIONS = frozenset({
    "md",
    "m4a", "mp3", "wav", "flac", "ogg", "aac", "opus",
    "mp4", "mov", "webm", "mkv", "avi",
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
    "pdf", "html", "txt", "csv", "json", "yaml", "yml",
    "zip",
})
