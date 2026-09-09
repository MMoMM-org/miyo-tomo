# version: 1.0.0
"""source_link.py — wikilinks that say WHICH note when a filename repeats.

Recursive discovery (spec 034) lets two inbox notes in different subfolders
share a filename, and lets two approved items claim the same note name. A bare
`[[Dresden]]` resolves by name, so the vault picks one of them — the user
cannot tell which note a line is about, and neither can Obsidian.

The remedy is the form the vault itself writes for a duplicate basename:
`[[<path>|<display>]]`. Applied **only** on collision, so a run without
namesakes renders exactly as it did before this spec.

Extracted from `suggestions-reducer.py` (spec 034 T5.1) when the instruction
document turned out to need the same two decisions at three more sites. The
collision rule and the link form live here once — this module's two consumers
have been bitten twice by parallel copies of a shared shape.
"""
from __future__ import annotations

from collections.abc import Iterable


def colliding_names(entries: Iterable[tuple[str, str]]) -> set[str]:
    """The display names carried by more than one distinct path.

    `entries` is a `(display_name, path)` sequence. Distinct **paths** are
    counted, not occurrences: one note is routinely named several times in one
    document — a `move_note`'s source reference and its `delete_source` both
    point at the same origin — and counting those as a collision would qualify
    a link that was never ambiguous.

    A name with no path attached cannot be qualified later, so it is ignored
    here rather than reported as colliding.
    """
    paths_by_name: dict[str, set[str]] = {}
    for name, path in entries:
        if not name or not path:
            continue
        paths_by_name.setdefault(name, set()).add(path)
    return {name for name, paths in paths_by_name.items() if len(paths) > 1}


def qualified_target(path: str, display: str) -> str:
    """The `<path>|<display>` wikilink target for one colliding name.

    The `.md` extension is dropped because Obsidian resolves a wikilink to a
    note, not to a file; `display` is what the reader sees, so callers pass the
    bare filename and never the path.
    """
    target = path[:-3] if path.endswith(".md") else path
    return f"{target}|{display}"


def source_link_targets(items: list[tuple[str, str, dict]]) -> dict[str, str]:
    """item_key -> the wikilink TARGET to render for that item's source note.

    Bare stem while the filename is unique in this run; `<path>|<stem>` once
    two items in the run share one. Display only (ADR-2): the caller keeps
    `stem` for names and `item_key` for identity; neither is rewritten here.

    `items` is the run's (stem, item_key, entry) work list.
    """
    collisions = colliding_names((stem, key) for stem, key, _entry in items)
    targets: dict[str, str] = {}
    for stem, key, _entry in items:
        if not key:
            continue
        targets[key] = (
            qualified_target(key, stem) if stem in collisions else stem
        )
    return targets


def resolve_source_link(
    source_links: dict[str, str] | None, item_key: str | None, stem: str
) -> str:
    """The link target for one item, falling back to the bare stem.

    An absent key, or an item the map does not know about, renders exactly as
    it did before this spec — a document is never worse off for a missing key.
    """
    if source_links and item_key:
        return source_links.get(item_key) or stem
    return stem
