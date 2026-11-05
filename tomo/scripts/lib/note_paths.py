# note_paths.py — the path rules of /note: vault folders, note paths, unsafe characters.
# version: 0.1.0
"""One set of path rules for every /note script.

``note-instructions.py`` validates folders, note paths and titles with these
functions; ``note-process.py`` / ``lib/note_process.py`` validate a process
file's destination with the same ``vault_folder``, so a folder one script saves
is a folder the other accepts.

``vault_folder`` and ``vault_note`` return the stripped value (a folder with
exactly one trailing "/") or None; they never raise and never normalise
Unicode. ``is_inside`` compares ``path_key`` values on a segment boundary.

Stdlib only (plus lib.vault_paths).

Design notes: docs/tomo/scripts/lib/note_paths.md
"""
from __future__ import annotations

import unicodedata

from lib.vault_paths import path_key

_UNSAFE_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})
_TEMPLATE_SYNTAX = ("{{", "<%")


def has_unsafe_char(value: str) -> bool:
    """True for a control, format (zero-width, bidi, BOM), line or paragraph separator character."""
    return any(unicodedata.category(c) in _UNSAFE_CATEGORIES for c in value)


def has_template_syntax(value: str) -> bool:
    """True when value holds '{{' or '<%'."""
    return any(s in value for s in _TEMPLATE_SYNTAX)


def _is_absolute(value: str) -> bool:
    """True for a leading '/' or '~' or a drive letter such as 'C:'."""
    drive = value[:1].isascii() and value[:1].isalpha() and value[1:2] == ":"
    return value.startswith(("/", "~")) or drive


def _vault_relative(value: object) -> str | None:
    """Return value stripped, or None when it is absolute, has '\\', unsafe chars or template syntax."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v or _is_absolute(v) or "\\" in v or has_unsafe_char(v) or has_template_syntax(v):
        return None
    return v


def _segments_visible(path: str) -> bool:
    """True when no segment is blank or starts with '.' ('.', '..' and hidden names)."""
    segments = [s.strip() for s in path.split("/")]
    return all(s and not s.startswith(".") for s in segments)


def vault_folder(value: object) -> str | None:
    """Return value as a relative vault folder with one trailing '/', or None when it is not one."""
    v = _vault_relative(value)
    body = v[:-1] if v and v.endswith("/") else v
    if not body or not _segments_visible(body):
        return None
    return body + "/"


def vault_note(value: object) -> str | None:
    """Return value as a relative vault path of a .md note, or None when it is not one."""
    v = _vault_relative(value)
    if not v or not v.endswith(".md") or not _segments_visible(v):
        return None
    return v


def is_inside(path: str, folder: str) -> bool:
    """True when path lies under folder (a vault_folder value); compared by path_key."""
    return path_key(path).startswith(path_key(folder))
