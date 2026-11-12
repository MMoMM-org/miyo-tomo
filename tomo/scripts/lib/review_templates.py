# review_templates.py — the template candidates and the anchor candidates of the /review setup preview.
# version: 0.1.0
"""The two questions ``review-session.py match`` can leave open (spec 045 F1-AC7, ADR-8).

``template_candidates(vault, base_path, kind)`` lists the notes of
``templates.base_path`` whose file name fits the kind (``week``/``woche``,
``month``/``monat``; case-insensitive), as names below the base path without
``.md``, sorted case-insensitively; None when Kado answered with nothing.
``template_name(text)`` normalises a ``--template`` value to its ``.md`` file
name and raises ``ValueError`` for a name that would leave the folder.
``anchor_candidates_from_notes(vault, notes, fmt, rule, kind)`` reads the two
periodic notes with the latest period under the proposed format and rule and
returns their headings below the title, most recent first, duplicates dropped.
``template_anchor_candidates``, ``propose_anchor`` (the last of the shallowest
headings) and ``daily_sections_from`` are what a template's headings propose.

Design notes: docs/tomo/scripts/lib/review_templates.md
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import List, Optional, Tuple

from lib.period import MONTH, WEEK, WeekRule, parse_name
from lib.review_vault import TEMPLATER_MARK, headings

KIND_WORDS = {WEEK: ("week", "woche"), MONTH: ("month", "monat")}
RECENT_NOTES = 2
_UNSAFE = ("..", "\\")


def template_candidates(vault, base_path: str, kind: str) -> Optional[List[str]]:
    """Names below ``base_path`` whose file name fits ``kind``; None for a ``kado-none`` listing."""
    paths = vault.list_notes(base_path)
    if paths is None:
        return None
    base = base_path.rstrip("/") + "/"
    names = []
    for path in paths:
        name = path[len(base):] if path.startswith(base) else PurePosixPath(path).name
        stem = name[:-3]
        if any(word in PurePosixPath(stem).name.lower() for word in KIND_WORDS[kind]):
            names.append(stem)
    return sorted(names, key=str.lower)


def template_name(text: str) -> str:
    """The ``.md`` file name of a ``--template`` value; ``ValueError`` for an unsafe or blank name."""
    name = text.strip()
    if not name or name == "." or name.startswith("/") or any(mark in name for mark in _UNSAFE):
        raise ValueError("a template name below templates.base_path, without .., \\ or a leading /")
    return name if name.endswith(".md") else name + ".md"


def template_anchor_candidates(template_headings: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """The headings below the title that carry no Templater code."""
    return [(level, text) for level, text in template_headings
            if level >= 2 and TEMPLATER_MARK not in text and text]


def propose_anchor(candidates: List[Tuple[int, str]]) -> Optional[str]:
    """The last of the shallowest candidate headings."""
    if not candidates:
        return None
    shallowest = min(level for level, _ in candidates)
    return [text for level, text in candidates if level == shallowest][-1]


def daily_sections_from(template_text: str) -> List[str]:
    """The daily template's headings below the title, minus Templater code and links (their text changes per day)."""
    return [text for level, text in headings(template_text)
            if level >= 2 and text and TEMPLATER_MARK not in text and "[[" not in text]


def anchor_candidates_from_notes(vault, notes: List[Tuple[str, str]], fmt: str, rule: WeekRule,
                                 kind: str) -> List[str]:
    """Headings of the ``RECENT_NOTES`` latest periodic notes, most recent first, each once."""
    dated = []
    for stem, path in notes:
        period = parse_name(stem, fmt, rule) if kind == WEEK else parse_name(stem, fmt)
        if period is not None:
            dated.append((period.start, path))
    found: List[str] = []
    for _, path in sorted(dated, reverse=True)[:RECENT_NOTES]:
        text = vault.note(path)
        if not text:
            continue
        for _, heading in template_anchor_candidates(headings(text)):
            if heading not in found:
                found.append(heading)
    return found
