# review_growth.py — the "Vault growth" group of the /review document, built from the created notes of the period.
# version: 0.4.0
"""The Vault growth group of the Pass 1 document (spec 047 T9.3, F-R1-3, F-R1-4, F-R3-1, F-R3b-4; PRD F2-AC1).

Every note created in the period is in the group exactly once, whatever a section item or the proposer says
about it. ``group(read, language, calendar_base)`` builds the items ``{text, links}``:

- the created notes are ``read["growth"]["created"]``, grouped by parent folder (the path before the last ``/``;
  a note at the top of the vault has the folder ``""``);
- a folder under ``calendar_base`` (the folder itself or below it; leading, trailing and surrounding blanks and
  slashes of the base ignored), or one with more than ``LINKS_MAX`` created notes, is a count item: text the
  ``language``'s ``growth_folder_one`` (1 note) or ``growth_folder_many`` (``{n}`` notes) with ``{folder}`` the
  folder path, or the ``growth_root`` label word for the vault root; no links;
- any other folder is a link item: text the folder path (``growth_root`` for the vault root), links its notes in
  path order;
- no ``calendar_base`` (None or blank) → no folder is a calendar folder;
- folder items in folder path order, whatever their kind;
- a note's link is its stem, or its path without ``.md`` when another created note or MOC has the same stem;
- after the folder items, the MOC items of ``read["growth"]``: ``mocs_changed`` as one item (text the
  ``language``'s label word ``growth_mocs_changed``, links its MOCs), then ``mocs_linked_by_new`` minus the
  changed ones as one item (``growth_mocs_linked``); a MOC that is a created note is in neither; links in path
  order; an item without a MOC is left out.

No created note and no MOC item → ``[]`` (the group renders empty as before). An item holds folder paths, a count,
label words and links, nothing of a note's text.

No Kado, no model, no file read.

Design notes: docs/tomo/scripts/lib/review_growth.md
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from lib.review_doc import labels
from lib.review_sources import note_stem

LINKS_MAX = 10
MOC_LISTS = (("mocs_changed", "growth_mocs_changed"), ("mocs_linked_by_new", "growth_mocs_linked"))


def _links_of(paths: Sequence[str]) -> Dict[str, str]:
    """Path → its link: the stem, or the path without ``.md`` when the stem is not unique among ``paths``."""
    stems: Dict[str, int] = {}
    for path in paths:
        stems[note_stem(path)] = stems.get(note_stem(path), 0) + 1
    return {path: (note_stem(path) if stems[note_stem(path)] == 1 else path[:-3] if path.endswith(".md") else path)
            for path in paths}


def _mocs(growth: dict, created: Sequence[str]) -> List[Tuple[str, List[str]]]:
    """``[(label key, MOC paths)]`` of the MOC items: each MOC once, the first list it is in; none created."""
    seen = set(created)
    out = []
    for key, word in MOC_LISTS:
        paths = sorted({str(p) for p in growth.get(key) or [] if p} - seen)
        seen.update(paths)
        if paths:
            out.append((word, paths))
    return out


def _under(folder: str, base: Optional[str]) -> bool:
    """``folder`` is the calendar base folder or below it."""
    root = (base or "").strip().strip("/")
    return bool(root) and (folder == root or folder.startswith(root + "/"))


def _folders(paths: Sequence[str], link: Dict[str, str], words: Dict[str, str], base: Optional[str]) -> List[dict]:
    """One item per parent folder of ``paths``, in folder path order: a count item or a link item."""
    by_folder: Dict[str, List[str]] = {}
    for path in paths:
        by_folder.setdefault(path.rsplit("/", 1)[0] if "/" in path else "", []).append(path)
    out = []
    for folder, notes in sorted(by_folder.items()):
        name = folder or words["growth_root"]
        if _under(folder, base) or len(notes) > LINKS_MAX:
            word = words["growth_folder_one"] if len(notes) == 1 else words["growth_folder_many"]
            out.append({"text": word.format(folder=name, n=len(notes)), "links": []})
        else:
            out.append({"text": name, "links": [link[path] for path in sorted(notes)]})
    return out


def group(read: dict, language: str = "en", calendar_base: Optional[str] = None) -> List[dict]:
    """The group's items ``{text, links}``: the folder items, then the MOC items (module docstring)."""
    growth = read.get("growth") or {}
    created = sorted({str(c["path"]) for c in growth.get("created") or [] if isinstance(c, dict) and c.get("path")})
    mocs = _mocs(growth, created)
    link = _links_of([*created, *(path for _, paths in mocs for path in paths)])
    words = labels(language)
    out = _folders(created, link, words, calendar_base)
    return out + [{"text": words[word], "links": [link[path] for path in paths]} for word, paths in mocs]
