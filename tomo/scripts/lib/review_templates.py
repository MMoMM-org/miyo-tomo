# review_templates.py — the template candidates and the anchor candidates of the /review setup preview.
# version: 0.2.2
"""The questions ``review-session.py match`` can leave open (spec 045 F1-AC7, ADR-8), and their answers.

``template_candidates(vault, base_path, kind)`` lists the notes of
``templates.base_path`` whose file name — the basename alone, never a folder
above it — holds a kind word as a substring (``week``/``woche``,
``month``/``monat``; case-insensitive; ``t_weekend`` counts), as names below
the base path without ``.md``, sorted case-insensitively; None when Kado
answered with nothing. ``template_name(text)`` normalises a trimmed
``--template`` value to its ``.md`` file name and raises ``ValueError`` for a
name that would leave the folder (a ``..`` segment, ``\\``, a leading ``/``)
or spans lines; ``template_choice(text)`` is the same with the trimmed word
``none`` — the user's "no template" answer — returned as ``NO_TEMPLATE``, so a
template file called ``none.md`` is chosen with its extension only;
``anchor_text(text)`` is the ``--anchor`` answer, trimmed, one non-blank line
or ``ValueError``.
``template_vault_path(base_path, name)`` is where the script reads a template;
``resolve_template(vault, base_path, name, kind, no_template=...)`` reads and
classifies the named template or, with no name and ``no_template`` False, lists
the candidates once, returning the hint sentence of an unreadable template or
a ``kado-none`` templates folder. ``template_has_frontmatter(text)`` says
whether a template text opens a YAML frontmatter block at its first line and
closes it — by the rule of ``doc_frontmatter.body_after_frontmatter``, the
same test Pass 2's merge applies, so a template whose opening ``---`` is only
rendered by a Templater include, a lone unclosed ``---`` and an empty text are
"no block" (the setup asks before Tomo would prepend a second block).
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

from lib.doc_frontmatter import body_after_frontmatter
from lib.period import MONTH, WEEK, WeekRule, parse_name
from lib.review_vault import TEMPLATER_MARK, headings

KIND_WORDS = {WEEK: ("week", "woche"), MONTH: ("month", "monat")}
RECENT_NOTES = 2
NO_TEMPLATE = "none"
CLIMB = ".."
_UNSAFE = ("\\", "\n", "\r")
TEMPLATE_HINT = ("Kado could not read the template {path}; the Kado key may have no access "
                 "to it. A plain note (title and review section) is proposed instead.")
TEMPLATES_FOLDER_HINT = ("Kado returned none for the templates folder {folder}: it may be empty, or the Kado "
                         "key may not reach it. No template is proposed.")


def template_candidates(vault, base_path: str, kind: str) -> Optional[List[str]]:
    """Names below ``base_path`` whose basename (not a folder above it) holds a word of ``kind`` as a substring;
    None for a ``kado-none`` listing."""
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


def template_vault_path(base_path: Optional[str], name: Optional[str]) -> Optional[str]:
    """The vault path of a template name below ``base_path`` (the bare name without one); None for no name."""
    if name is None:
        return None
    if base_path is None:
        return name
    return base_path.rstrip("/") + "/" + name


def resolve_template(vault, base_path: Optional[str], name: Optional[str], kind: str, *,
                     no_template: bool = False) -> Tuple[str, Optional[str], Optional[List[str]], Optional[str]]:
    """``(template_kind, template_text, candidates, hint)``: the named template read and classified (candidates
    None), or — with no name and ``no_template`` False — the candidates of ``base_path`` listed once (``[]``
    without a base path or for a ``kado-none`` listing); ``no_template`` is the "no template" answer: nothing
    listed, candidates None. ``hint`` is the sentence for an unreadable template or a ``kado-none`` folder."""
    path = template_vault_path(base_path, name)
    if path is not None:
        template_kind, text = vault.template(path)
        return template_kind, text, None, TEMPLATE_HINT.format(path=path) if template_kind == "unreadable" else None
    if no_template:
        return "missing", None, None, None
    candidates = template_candidates(vault, base_path, kind) if base_path else []
    if candidates is None:
        return "missing", None, [], TEMPLATES_FOLDER_HINT.format(folder=base_path)
    return "missing", None, candidates, None


def template_has_frontmatter(text: str) -> bool:
    """True when ``text`` opens a frontmatter block at its first line and closes it: the merge's own test."""
    return body_after_frontmatter(text) != text


def template_name(text: str) -> str:
    """The ``.md`` file name of a trimmed ``--template`` value; ``ValueError`` for a blank name, a ``..`` path
    segment (``t_week..old`` is a name), ``\\``, a line break or a leading ``/``."""
    name = text.strip()
    if (not name or name == "." or name.startswith("/") or CLIMB in name.split("/")
            or any(mark in name for mark in _UNSAFE)):
        raise ValueError("a template name below templates.base_path on one line, without a .. segment, \\ "
                         "or a leading /")
    return name if name.endswith(".md") else name + ".md"


def template_choice(text: str) -> str:
    """``NO_TEMPLATE`` for the trimmed word ``none`` (the ``0 none`` answer), else ``template_name``; a template
    file called ``none.md`` is reached with its extension only."""
    return NO_TEMPLATE if text.strip() == NO_TEMPLATE else template_name(text)


def anchor_text(text: str) -> str:
    """The ``--anchor`` answer trimmed; ``ValueError`` unless it is one non-blank line."""
    anchor = text.strip()
    if not anchor or "\n" in anchor or "\r" in anchor:
        raise ValueError("one non-blank line, the text of the heading")
    return anchor


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
