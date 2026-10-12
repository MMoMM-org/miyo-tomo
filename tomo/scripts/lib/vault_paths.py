# version: 0.2.1
"""vault_paths.py — the destination-join helpers every vault-path comparison
is built with, and the one key (`path_key`) every such comparison uses.

Lives below both `render_actions` and `vault_folder_lookup` so the folder
lookup can key by these helpers without an import cycle; `render_actions`
re-exports the two join helpers. Rationale: docs/tomo/scripts/lib/vault_paths.md.
"""
from __future__ import annotations

import unicodedata

from lib.obsidian_filename import sanitize_stem


def path_key(path: str) -> str:
    """The one comparison key for a vault path or file name: NFC, then casefold."""
    return unicodedata.normalize("NFC", path).casefold()


def nfc_lower(text: str) -> str:
    """NFC, then `.lower()` — the audio-transcript pairing key, deliberately NOT `path_key`."""
    return unicodedata.normalize("NFC", text).lower()


def same_spelling(a: str, b: str) -> bool:
    """True when `a` and `b` are one visible spelling (equal after NFC)."""
    return unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b)


def _dest_join(folder: str, title: str) -> str:
    """Join destination folder + Obsidian-safe title as filename (with .md)."""
    if not folder:
        folder = ""
    folder = folder.rstrip("/") + "/"
    # Obsidian allows Umlauts, em-dash etc. — no slug. Forbidden chars
    # (\ / : * ? " < > |) in the title would crash Hashi's rename/create, so
    # the filename stem is sanitised; the note's displayed title (frontmatter/H1)
    # keeps the original. Link targets are sanitised the same way (_wikilink).
    stem = title[:-3] if title.endswith(".md") else title
    return f"{folder}{sanitize_stem(stem)}.md"


def _asset_dest_join(asset_folder: str, source_path: str) -> str:
    """Join the asset folder with the source path's basename, preserving it verbatim.

    Never _dest_join (appends a '.md' suffix) or _ensure_md_extension (a silent
    no-op for an allowlisted extension, a corrupting '.md' append for anything
    else) — an attachment's basename must survive exactly as-is, uppercase,
    unusual extension, and all, or the embed referencing it stops resolving.

    Raises ValueError if source_path has no basename (empty, or ending in
    "/") rather than silently returning a bare folder path.
    """
    basename = source_path.rsplit("/", 1)[-1]
    if not basename:
        raise ValueError(f"attachment source path has no filename: {source_path!r}")
    folder = (asset_folder or "").rstrip("/") + "/"
    return f"{folder}{basename}"
