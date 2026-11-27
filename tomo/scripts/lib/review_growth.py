# review_growth.py — the "Vault growth" group of the /review document, built from the created notes of the period.
# version: 0.3.0
"""The Vault growth group of the Pass 1 document (spec 047 T9.3, F-R1-3, F-R1-4, F-R3-1; PRD F2-AC1).

Every note created in the period is in the group exactly once, whatever a section item or the proposer says
about it. ``candidates(stage, read)`` loads the growth candidates ``{text, notes}`` of every digest whose unit
``condensed.json`` marks passed (unit order, then digest order); a digest that is missing, not JSON or of
another read gives none. ``group(read, candidates)`` builds the items ``{text, links}``:

- the created notes are ``read["growth"]["created"]`` (each with its creation ``day``);
- a candidate becomes one item: its ``text``, its notes that are created notes and not yet in an earlier item;
  a candidate left without a note is dropped (so notes of several units' digests are merged, none twice);
- a candidate item's links: the links of its notes, then the stems of the dailies of the notes' creation days
  (the read's ``Sources``, so a day of a not-condensed unit links no daily);
- a note's link is its stem, or its path without ``.md`` when another created note has the same stem;
- notes in an item by (creation day, path); candidate items by (their first note's creation day, its path);
- after the candidate items, one folder item per parent folder of the created notes in no candidate, in folder
  path order: text the ``language``'s ``growth_folder_one`` (1 note) or ``growth_folder_many`` (``{n}`` notes)
  with ``{folder}`` the folder path, or the ``growth_root`` label word for a note at the top of the vault; no links;
- after the folder items, the MOC items of ``read["growth"]``: ``mocs_changed`` as one item (text the
  ``language``'s label word ``growth_mocs_changed``, links its MOCs), then ``mocs_linked_by_new`` minus the
  changed ones as one item (``growth_mocs_linked``); a MOC that is a created note is in neither; links in path
  order; an item without a MOC is left out;
- a MOC's link follows the created notes' rule over the created notes and the MOCs together.

No created note and no MOC item → ``[]`` (the group renders empty as before). The texts of the candidates are
the digester's words; they reach the written document only, never stdout, stderr or ``meta.json``; a MOC item
holds a label word and links, a folder item a folder path, a count and label words, nothing of a note's text.

No Kado, no model; reads the stage's ``digests/`` files only.

Design notes: docs/tomo/scripts/lib/review_growth.md
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from lib.review_doc import labels
from lib.review_sources import Sources, note_stem

DIGESTS = "digests"
PASSED = "passed"
MOC_LISTS = (("mocs_changed", "growth_mocs_changed"), ("mocs_linked_by_new", "growth_mocs_linked"))


def candidates(stage: Path, read: dict) -> List[dict]:
    """The growth candidates ``{text, notes}`` of the passed units' digests, in unit order, then digest order."""
    condensed = read.get("condensed") or {}
    read_id = condensed.get("read_id")
    out: List[dict] = []
    for unit, job in (condensed.get("units") or {}).items():
        if (job or {}).get("state") != PASSED:
            continue
        try:
            data = json.loads((Path(stage) / DIGESTS / f"{unit}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("read_id") != read_id:
            continue
        for candidate in data.get("growth") or []:
            if isinstance(candidate, dict):
                out.append({"text": str(candidate.get("text") or ""),
                            "notes": [str(n) for n in candidate.get("notes") or []]})
    return out


def _links_of(paths: Sequence[str]) -> Dict[str, str]:
    """Path → its link: the stem, or the path without ``.md`` when the stem is not unique among ``paths``."""
    stems: Dict[str, int] = {}
    for path in paths:
        stems[note_stem(path)] = stems.get(note_stem(path), 0) + 1
    return {path: (note_stem(path) if stems[note_stem(path)] == 1 else path[:-3] if path.endswith(".md") else path)
            for path in paths}


def _mocs(growth: dict, created: Dict[str, str]) -> List[Tuple[str, List[str]]]:
    """``[(label key, MOC paths)]`` of the MOC items: each MOC once, the first list it is in; none created."""
    seen = set(created)
    out = []
    for key, word in MOC_LISTS:
        paths = sorted({str(p) for p in growth.get(key) or [] if p} - seen)
        seen.update(paths)
        if paths:
            out.append((word, paths))
    return out


def _day_links(read: dict) -> Dict[str, List[str]]:
    """Day → the stems of its dailies that may be a source (``Sources``: none of a not-condensed unit's day)."""
    out: Dict[str, List[str]] = {}
    for day, stem in Sources.of(read).dailies.values():
        stems = out.setdefault(day.isoformat(), [])
        if stem not in stems:
            stems.append(stem)
    return out


def _folders(paths: Sequence[str], words: Dict[str, str]) -> List[dict]:
    """One item ``{text, links: []}`` per parent folder of ``paths``, in folder path order, with its note count."""
    counts: Dict[str, int] = {}
    for path in paths:
        folder = path.rsplit("/", 1)[0] if "/" in path else ""
        counts[folder] = counts.get(folder, 0) + 1
    return [{"text": (words["growth_folder_one"] if n == 1 else words["growth_folder_many"]).format(
                folder=folder or words["growth_root"], n=n), "links": []}
            for folder, n in sorted(counts.items())]


def group(read: dict, found: Sequence[dict], language: str = "en") -> List[dict]:
    """The group's items ``{text, links}``: the candidate items, the folder items, the MOC items (module docstring)."""
    growth = read.get("growth") or {}
    created = {str(c["path"]): str(c.get("day") or "") for c in growth.get("created") or []
               if isinstance(c, dict) and c.get("path")}
    mocs = _mocs(growth, created)
    link = _links_of([*created, *(path for _, paths in mocs for path in paths)])
    days = _day_links(read)
    order = lambda path: (created[path], path)              # noqa: E731 - the one sort key of notes
    taken: set = set()
    items: List[Tuple[str, List[str]]] = []                 # (candidate text, its notes)
    for candidate in found:
        notes = []
        for path in candidate["notes"]:
            if path in created and path not in taken:
                taken.add(path)
                notes.append(path)
        if notes:
            items.append((candidate["text"], sorted(notes, key=order)))
    items.sort(key=lambda item: order(item[1][0]))
    out = []
    for text, notes in items:
        links = [link[path] for path in notes]
        for day in sorted({created[path] for path in notes}):
            links += [stem for stem in days.get(day, []) if stem not in links]
        out.append({"text": text, "links": links})
    words = labels(language)
    out += _folders([path for path in created if path not in taken], words)
    return out + [{"text": words[word], "links": [link[path] for path in paths]} for word, paths in mocs]
