# review_match.py — the setup proposal of /review: match the notes of a period kind and propose the setup.
# version: 0.3.0
"""The proposal behind ``review-session.py match`` (spec 045 F1; ADR-1, ADR-4; spec 046 T2.1, ADR-9, ADR-13).

``propose(open_vault, config, profile, args)`` lists the folder of one period
kind, matches the existing names against the proposed format, infers the week
rule from the notes' own dates, classifies the template and builds the
``match`` output: ``proposal``, ``evidence`` and the optional keys the skill
asks about (``template_candidates``, ``needs_anchor``, ``needs_template_ok``,
``daily_path_fix``, ``hints``). The unsafe-format and ``Stopped`` outputs are
built here too, so the script only prints what comes back.

``sections`` is always in an ``ok`` output: one candidate per template heading
(``lib/review_mapping.analyse_template``) with ``defaults`` and the ``saved`` row
of the resolved template, the saved ``off_limits`` rows, ``mappable`` and
``dropped`` (after a template change the earlier rows the template lacks, and
on every run the saved rows of the template whose heading it lost);
``candidates`` is ``[]`` and ``mappable`` false when no heading
takes a row. A typed or configured template Kado does not find becomes
``template_not_found`` with a null template and the candidates listed. The
configured anchor counts only while the resolved template is the configured
one. A quarter's format, with none typed or configured, is the
``QUARTER_FORMATS`` entry that parses the most note names.

``match`` keeps the rows it shows in ``<args.tmp>/rows-<kind>.json`` (setup
text only: ``ROW_FIELDS``) with the template's ``outline``
(``lib/review_mapping.outline``) and ``resolved {template, kind}`` — the name it
tried and its ``template_kind`` — for ``setup-input``, and reads the previous
file for ``dropped``; a template not found or unreadable shows no rows and
keeps the file's template, rows and outline, updating ``resolved`` only.

``open_vault`` is a zero-argument callable returning the ``Vault``; the script
passes ``lambda: Vault(KadoClient)`` so the client stays patchable where the
script names it, and nothing is opened before the format is known to be safe.
``args`` is the parsed ``match`` namespace and is read for ``kind``, ``folder``,
``format``, ``first_day``, ``min_days``, ``template``, ``anchor``,
``template_frontmatter_ok``, ``tmp`` and ``today``.

``configured_rule`` and the ``str_value``/``str_list``/``review_section``
config readers are shared with ``review-session.py start``; ``match_names``
and ``day_name`` serve the proposal only.

No clock of its own, no stdout, no exit code; the rows file is its only write. Design notes: docs/tomo/scripts/lib/review_match.md
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Callable, List, Optional, Tuple

from lib import review_config as rc
from lib.note_io import atomic_write_text
from lib.period import DAY_NAMES, DEFAULT_FORMATS, ISO, QUARTER, WEEK, WeekRule, check_format, parse_name
from lib.review_mapping import AUTOMATIC, TemplateHeading, analyse_template, dropped, outline, row_key
from lib.review_templates import (
    NO_TEMPLATE, anchor_candidates_from_notes, daily_sections_from, propose_anchor, resolve_template,
    template_anchor_candidates, template_has_frontmatter, template_vault_path,
)
from lib.review_vault import Stopped, Vault, headings
from lib.vault_config_edit import get_path
from lib.week_rule_inference import Checked, Inference, infer_rule

DEFAULT_HEADING = "Tomo Review"
NON_ISO_WEEK_FORMAT = "gggg-[W]ww"
QUARTER_FORMATS = ("YYYY-[Q]Q", "YYYY [Q]Q", "YYYY_[Q]Q", "[Q]Q YYYY", "[Q]Q-YYYY")
OFFERED = "offered"
END, REVIEW = "end", "review"         # an offered heading's default placement; an automatic one's only one
ROW_FIELDS = ("heading", "level", "parent", "occurrence", "description", "keywords", "placement", "cap")
NO_OUTLINE = {"headings": [], "top": []}

FOLDER_HINT = ("Kado returned none for {folder}: the folder may be empty, or the Kado key "
               "may not reach it. Ask before proposing to create notes there.")
NO_NOTES_HINT = ("Found no notes to compare with in {folder}: the default naming is proposed. "
                 "Say so when showing the proposal.")


def str_value(value) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def str_list(value) -> Optional[List[str]]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def review_section(config: dict, granularity: str) -> dict:
    section = get_path(config, ("review", granularity))[1]
    return section if isinstance(section, dict) else {}


def configured_rule(config: dict) -> Optional[WeekRule]:
    week = get_path(config, ("review", "week"))[1]
    if not isinstance(week, dict) or "first_day" not in week:
        return None
    try:
        return WeekRule.from_config(week.get("first_day"), week.get("min_days_in_first_week", 4))
    except (ValueError, TypeError):
        return None


def day_name(rule: WeekRule) -> str:
    return DAY_NAMES[rule.first_day]


def match_names(notes: List[Tuple[str, str]], fmt: str, rule: WeekRule, kind: str,
                checked: List[Checked]) -> Tuple[List[str], List[str]]:
    """Names under ``matched``/``unmatched``, one entry per note (a duplicated stem once per path)."""
    starts = {c.path: c.start for c in checked if c.start is not None}
    matched, unmatched = [], []
    for stem, path in notes:
        period = parse_name(stem, fmt, rule) if kind == WEEK else parse_name(stem, fmt)
        fits = period is not None and (path not in starts or period.start == starts[path])
        (matched if fits else unmatched).append(stem)
    return matched, unmatched


def notes_format(notes: List[Tuple[str, str]], kind: str) -> Optional[str]:
    """The ``QUARTER_FORMATS`` entry that parses the most note names (the first on a tie); None for another kind
    or when no name parses."""
    if kind != QUARTER:
        return None
    best, most = None, 0
    for fmt in QUARTER_FORMATS:
        count = sum(parse_name(stem, fmt) is not None for stem, _ in notes)
        if count > most:
            best, most = fmt, count
    return best


# --- the section mapping (spec 046 T2.1) ----------------------------------------------------

def rows_path(tmp: str, kind: str) -> Path:
    return Path(tmp) / f"rows-{kind}.json"


def read_rows(path: Path) -> Optional[dict]:
    """``{template, rows, outline}`` of the rows file; None when it is absent or not the file ``write_rows``
    writes."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return None
    return {"template": data.get("template"), "rows": [r for r in data["rows"] if isinstance(r, dict)],
            "outline": data.get("outline", NO_OUTLINE)}


def write_rows(path: Path, kind: str, shown: dict, resolved: dict) -> None:
    """``shown`` is ``{template, rows, outline}`` of the template whose rows were shown last."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"kind": kind, "template": shown["template"], "rows": shown["rows"], "outline": shown["outline"],
            "resolved": resolved}
    atomic_write_text(path, json.dumps(data, ensure_ascii=True, indent=2) + "\n")


def _defaults(head: TemplateHeading, saved: Optional[dict]) -> Optional[dict]:
    if saved is not None:
        return {"placement": saved["placement"], "cap": saved["cap"]}
    if head.state == OFFERED:
        return {"placement": END, "cap": rc.DEFAULT_CAP}
    if head.reason == AUTOMATIC:
        return {"placement": REVIEW, "cap": rc.DEFAULT_CAP}
    return None


def _candidate(head: TemplateHeading, saved: Optional[dict]) -> dict:
    out = head.as_dict()
    out.pop("line")
    out["defaults"] = _defaults(head, saved)
    out["saved"] = saved
    return out


def _shown_row(head: TemplateHeading, saved: Optional[dict]) -> Optional[dict]:
    """The row the table shows for ``head``: its saved row, else a default row for an offered heading."""
    if saved is None and head.state != OFFERED:
        return None
    source = saved or {**head.key._asdict(), "keywords": [], "placement": END, "cap": rc.DEFAULT_CAP}
    return {name: source[name] for name in ROW_FIELDS if name in source}


def section_proposal(config: dict, kind: str, template: Optional[str], text: Optional[str],
                     previous: Optional[dict]) -> Tuple[dict, List[dict]]:
    """``(sections, rows shown)`` for the resolved ``template`` and its ``text`` (None: nothing to analyse);
    ``dropped`` names the ``previous`` rows the template lacks when ``previous`` was for another template."""
    pointers: List[str] = []
    saved_rows = rc.template_rows(config, kind, template, rc.SECTIONS, pointers)
    off_limits = rc.template_rows(config, kind, template, rc.OFF_LIMITS, pointers)
    heads = analyse_template(text, off_limits) if text is not None else []
    saved = {row_key(r): r for r in saved_rows}
    mappable = any(h.state == OFFERED or h.reason == AUTOMATIC for h in heads)
    shown_heads = heads if mappable else []
    shown = [row for row in (_shown_row(h, saved.get(h.key)) for h in shown_heads) if row is not None]
    changed = previous is not None and previous["template"] != template
    lost = dropped(previous["rows"], heads) if changed else []
    if text is not None:
        lost += [r for r in dropped(saved_rows, heads) if r not in lost]
    sections = {
        "template": template,
        "mappable": mappable,
        "candidates": [_candidate(h, saved.get(h.key)) for h in shown_heads],
        "off_limits": off_limits,
        "dropped": lost,
    }
    return sections, shown


def propose(open_vault: Callable[[], Vault], config: dict, profile, args) -> dict:
    kind = args.kind
    granularity = rc.GRANULARITY[kind]
    templates = config.get("templates") if isinstance(config.get("templates"), dict) else {}
    section = review_section(config, granularity)
    review = config.get("review") if isinstance(config.get("review"), dict) else {}
    hints: List[str] = []

    folder = args.folder or rc.folder_for(config, profile, granularity) or ""
    configured_fmt = str_value(get_path(config, ("naming", "calendar_patterns", granularity))[1])
    fmt_for_names = args.format or configured_fmt or DEFAULT_FORMATS[kind]
    if any(mark in fmt_for_names for mark in ("/", "\\", "..")):
        return {"status": "stopped", "kind": kind, "error": {"kind": "unsafe-format"}}

    try:
        vault = open_vault()
        paths = vault.list_notes(folder) if folder else None
        listing = "kado-none" if paths is None else "found"
        if paths is None:
            hints.append(FOLDER_HINT.format(folder=folder))
            paths = []
        notes = [(PurePosixPath(p).name[:-3], p) for p in paths]

        inference = Inference("default")
        if kind == WEEK and notes:
            inference = infer_rule(vault, notes, fmt_for_names)
        rule = configured_rule(config) or inference.rule or ISO
        if args.first_day is not None:
            rule = WeekRule.from_config(args.first_day, args.min_days)
        if kind == WEEK:
            default_fmt = DEFAULT_FORMATS[WEEK] if rule == ISO else NON_ISO_WEEK_FORMAT
        else:
            default_fmt = DEFAULT_FORMATS[kind]
        fmt = args.format or configured_fmt or notes_format(notes, kind) or default_fmt
        problems = check_format(fmt, kind, rule, today=args.today)
        matched, unmatched = match_names(notes, fmt, rule, kind, inference.checked)
        if listing == "found" and inference.verdict == "default" and not matched:
            hints.append(NO_NOTES_HINT.format(folder=folder))

        base = str_value(templates.get("base_path"))
        no_template = args.template == NO_TEMPLATE
        configured_template = str_value(get_path(templates, ("mapping", granularity))[1])
        template = None if no_template else args.template or configured_template
        template_kind, template_text, candidates, hint = resolve_template(vault, base, template, kind,
                                                                          no_template=no_template)
        not_found = None
        if template is not None and template_kind == "missing":
            not_found = {"name": template, "source": "typed" if args.template else "configured"}
            template = None
            _, _, candidates, hint = resolve_template(vault, base, None, kind)
        if hint is not None:
            hints.append(hint)
        rows_shown = not_found is None and template_kind != "unreadable"
        template_headings = template_anchor_candidates(headings(template_text)) if template_text else []
        template_frontmatter = template_has_frontmatter(template_text) if template_text is not None else None
        needs_template_ok = template_frontmatter is False and args.template_frontmatter_ok != template

        place = section.get("place") if isinstance(section.get("place"), dict) else {}
        configured_anchor = str_value(place.get("anchor")) if template == configured_template else None
        anchor = args.anchor or configured_anchor or propose_anchor(template_headings)
        anchor_candidates = anchor_candidates_from_notes(vault, notes, fmt, rule, kind) if anchor is None else None

        daily_sections = str_list(get_path(review, ("daily", "sections"))[1])
        if daily_sections is None:
            daily_sections = []
            daily_path = template_vault_path(base, str_value(get_path(templates, ("mapping", "daily"))[1]))
            if daily_path is not None:
                _, daily_text = vault.template(daily_path)
                if daily_text:
                    daily_sections = daily_sections_from(daily_text)

        result: dict = {"status": "ok", "kind": kind}
        daily_configured = rc.folder_for(config, profile, "daily")
        if daily_configured and daily_configured != daily_configured.strip():
            trimmed = daily_configured.strip()
            if vault.folder_listed(trimmed):
                result["daily_path_fix"] = {"configured": daily_configured, "found": trimmed}
    except Stopped as stop:
        return {"status": "stopped", "kind": kind, "error": {"kind": stop.kind, "detail": stop.detail}}

    path = rows_path(args.tmp, kind)
    previous = read_rows(path)
    sections, shown = section_proposal(config, kind, template, template_text if rows_shown else None,
                                       previous if rows_shown else None)
    resolved = {"template": not_found["name"] if not_found else template, "kind": template_kind}
    if rows_shown:
        kept = {"template": template, "rows": shown, "outline": outline(template_text) if template_text else NO_OUTLINE}
    else:
        kept = previous or {"template": None, "rows": [], "outline": NO_OUTLINE}
    write_rows(path, kind, kept, resolved)
    placement = place.get("placement") if place.get("placement") in rc.PLACEMENTS else rc.BEFORE
    language = (str_value(review.get("language"))
                or next((c.locale for c in inference.checked if c.locale), None)
                or rc.DEFAULT_LANGUAGE)
    result["proposal"] = {
        "folder": folder,
        "format": fmt,
        "first_day": day_name(rule) if kind == WEEK else None,
        "min_days": rule.min_days_in_first_week if kind == WEEK else None,
        "template": template,
        "template_kind": template_kind,
        "template_frontmatter": template_frontmatter,
        "heading": str_value(section.get("heading")) or DEFAULT_HEADING,
        "place": {"anchor": anchor, "placement": placement},
        "own_sections": str_list(section.get("own_sections")) or [],
        "daily_sections": daily_sections,
        "language": language,
    }
    result["evidence"] = {
        "matched": matched,
        "unmatched": unmatched,
        "week_rule": "given" if args.first_day is not None else inference.verdict,
        "notes_checked": len(inference.checked),
        "folder_listing": listing,
        "format_problems": [{"kind": p.kind, "example": p.example} for p in problems],
        "template_headings": [{"level": level, "text": text} for level, text in template_headings],
    }
    result["sections"] = sections
    if not_found is not None:
        result["template_not_found"] = not_found
    if candidates is not None:
        result["template_candidates"] = candidates
    if anchor_candidates is not None:
        result["needs_anchor"] = True
        result["anchor_candidates"] = anchor_candidates
    if needs_template_ok:
        result["needs_template_ok"] = True
    result["hints"] = hints
    return result
