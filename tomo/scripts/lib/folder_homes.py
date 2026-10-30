# version: 0.1.0
"""folder_homes.py — find folder-home MOCs and the notes they already hold.

A folder-home MOC is named like the folder it sits in
(``Atlas/202 Notes/2821 Quotes/2821 Quotes.md``) and lists that folder's notes
itself. moc-discovery drops such notes from its candidates, and
``NodeEligibility`` refuses them as link members.

Rationale: docs/tomo/scripts/lib/folder_homes.md.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable, TypeVar

T = TypeVar("T")


def atomic_roots(vault_cfg: dict | None, profile: dict | None) -> list[str]:
    """Base folders that hold every atomic note — never folder-homes, nor their ancestors.

    User config ``concepts.atomic_note`` (scalar, ``path``, ``base_path`` or
    ``paths``) wins; the profile's ``concept_defaults.atomic_note.base_path`` is
    the fallback. Profile ``subdirectories`` are left out: they are the very
    folders a folder-home MOC sits in.
    """
    node = ((vault_cfg or {}).get("concepts") or {}).get("atomic_note")
    if isinstance(node, str):
        roots = [node]
    elif isinstance(node, dict):
        roots = [node.get("path"), node.get("base_path"), *(node.get("paths") or [])]
    else:
        roots = []
    roots = [r for r in roots if isinstance(r, str) and r.strip("/")]
    if roots:
        return roots
    base = (((profile or {}).get("concept_defaults") or {}).get("atomic_note") or {}).get("base_path")
    return [base] if isinstance(base, str) and base.strip("/") else []


def folder_homes(map_notes: list[dict], container_roots: list[str]) -> list[tuple[str, str]]:
    """``(folder, label)`` for every MOC whose stem equals its folder's name.

    A folder that is a configured container root (``container_roots``) or an
    ancestor of one holds every atomic note, so its home note is no folder-home.
    Deepest folders come first, so ``home_of`` names the innermost home.
    """
    roots = [r.strip("/").casefold() for r in container_roots or [] if r.strip("/")]
    homes: list[tuple[str, str]] = []
    for entry in map_notes or []:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        folder, _, name = path.rpartition("/")
        if not folder:
            continue
        stem = name[:-3] if name.endswith(".md") else name
        if stem.casefold() != folder.rpartition("/")[2].casefold():
            continue
        key = folder.casefold()
        if any(r == key or r.startswith(key + "/") for r in roots):
            continue
        homes.append((folder, str(entry.get("title") or stem)))
    homes.sort(key=lambda h: h[0].count("/"), reverse=True)
    return homes


def home_of(path: str, homes: list[tuple[str, str]]) -> str | None:
    """Label of the folder-home whose folder (or a subfolder of it) holds ``path``."""
    folded = (path or "").casefold()
    for folder, label in homes:
        if folded.startswith(folder.casefold() + "/"):
            return label
    return None


def drop_home_members(
    items: Iterable[T], homes: list[tuple[str, str]]
) -> tuple[list[T], Counter]:
    """Split ``items`` (anything with a ``path``) → (kept, dropped count per home label)."""
    kept: list[T] = []
    dropped: Counter = Counter()
    for item in items:
        label = home_of(getattr(item, "path", "") or "", homes)
        if label is None:
            kept.append(item)
        else:
            dropped[label] += 1
    return kept, dropped
