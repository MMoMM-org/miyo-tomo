#!/usr/bin/env python3
# version: 0.1.3
"""attachment_index.py — Detect and normalise attachment embeds in note bodies."""
from __future__ import annotations

import re

from lib.file_extensions import KNOWN_FILE_EXTENSIONS

# The leading (!) is the whole point — every existing wikilink pattern in this
# repo omits it, so none of them distinguish an embed from a plain link.
_EMBED_RE = re.compile(r"(!)?\[\[([^\[\]]+)\]\]")

# Extensions that name a note or a note-like container, not an attachment file.
# KNOWN_FILE_EXTENSIONS also contains "md" — see _is_attachment_target.
_NOTE_EXTENSIONS = frozenset({"md", "canvas", "base"})


def extract_attachment_embeds(body: str) -> list[str]:
    """Return embed targets that name a FILE (not a note), in document order,
    deduplicated.

    Only `![[...]]` counts. A plain `[[...]]` link is a deliberate reference,
    not a dependency of the note (PRD Feature 1, business rule: embeds are the
    signal).
    """
    out: list[str] = []
    seen: set[str] = set()
    for bang, raw in _EMBED_RE.findall(body):
        if not bang:
            continue  # plain link — not an attachment
        target = _strip_alias_and_anchor(raw)
        if not _is_attachment_target(target):
            continue  # note embed, e.g. ![[Some Note]]
        if target not in seen:
            seen.add(target)
            out.append(target)
    return out


def build_inbox_index(list_dir_result: list[dict] | None) -> dict[str, list[str]]:
    """Index inbox files by basename: basename -> list of vault-relative paths.

    Accepts the flat list of item dicts returned by `KadoClient.list_dir()`,
    each carrying `path` and `type`. Folder entries are excluded; `.md`
    files are indexed like any other file, in list order. Returns `{}` for
    `None`, an empty list, or any other falsy/malformed input — never raises.
    Duplicate identical paths are not deduplicated.
    """
    index: dict[str, list[str]] = {}
    if not list_dir_result:
        return index
    for item in list_dir_result:
        if not isinstance(item, dict) or item.get("type") != "file":
            continue
        path = item.get("path")
        if not path:
            continue
        basename = path.rsplit("/", 1)[-1]
        index.setdefault(basename, []).append(path)
    return index


def _is_attachment_target(target: str) -> bool:
    """True if `target` names a file, not a note.

    Two-step test, not a membership check: KNOWN_FILE_EXTENSIONS also
    contains "md", so a naive `ext in KNOWN_FILE_EXTENSIONS` would classify
    `![[Note.md]]` as an attachment. `canvas` and `base` are not in that
    frozenset today, so they already fall out at step one — they are named
    here anyway to keep the note/attachment partition explicit.
    """
    ext = target.rsplit(".", 1)[-1].lower() if "." in target else ""
    return ext in KNOWN_FILE_EXTENSIONS and ext not in _NOTE_EXTENSIONS


def _strip_alias_and_anchor(raw: str) -> str:
    """Strip alias (|) then anchors (# and ^) from a raw embed target.

    Unlike topic-extract.py's `_strip_link_target`, this does NOT strip the
    path — a path-qualified embed target is already an answer and must be
    preserved (PRD Feature 2, criterion 2).
    """
    target = raw.split("|")[0].strip()   # alias: "karte.jpg|Karte" → "karte.jpg"
    target = target.split("#")[0].strip()  # heading/block anchor
    target = target.split("^")[0].strip()  # defensive: bare "target^block"
    return target
