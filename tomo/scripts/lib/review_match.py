# review_match.py — the setup proposal of /review: match the notes of a period kind and propose the setup.
# version: 0.1.0
"""The proposal behind ``review-session.py match`` (spec 045 F1; ADR-1, ADR-4).

``propose(open_vault, config, profile, args)`` lists the folder of one period
kind, matches the existing names against the proposed format, infers the week
rule from the notes' own dates, classifies the template and builds the
``match`` output: ``proposal``, ``evidence`` and the optional keys the skill
asks about (``template_candidates``, ``needs_anchor``, ``needs_template_ok``,
``daily_path_fix``, ``hints``). The unsafe-format and ``Stopped`` outputs are
built here too, so the script only prints what comes back.

``open_vault`` is a zero-argument callable returning the ``Vault``; the script
passes ``lambda: Vault(KadoClient)`` so the client stays patchable where the
script names it, and nothing is opened before the format is known to be safe.
``args`` is the parsed ``match`` namespace and is read for ``kind``, ``folder``,
``format``, ``first_day``, ``min_days``, ``template``, ``anchor``,
``template_frontmatter_ok`` and ``today``.

``configured_rule`` and the ``str_value``/``str_list``/``review_section``
config readers are shared with ``review-session.py start``; ``match_names``
and ``day_name`` serve the proposal only.

No clock of its own, no stdout, no exit code. Design notes: docs/tomo/scripts/lib/review_match.md
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Callable, List, Optional, Tuple

from lib import review_config as rc
from lib.period import DAY_NAMES, DEFAULT_FORMATS, ISO, MONTH, WEEK, WeekRule, check_format, parse_name
from lib.review_templates import (
    NO_TEMPLATE, anchor_candidates_from_notes, daily_sections_from, propose_anchor, resolve_template,
    template_anchor_candidates, template_has_frontmatter, template_vault_path,
)
from lib.review_vault import Stopped, Vault, headings
from lib.vault_config_edit import get_path
from lib.week_rule_inference import Checked, Inference, infer_rule

DEFAULT_HEADING = "Tomo Review"
NON_ISO_WEEK_FORMAT = "gggg-[W]ww"

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
            default_fmt = DEFAULT_FORMATS[MONTH]
        fmt = args.format or configured_fmt or default_fmt
        problems = check_format(fmt, kind, rule, today=args.today)
        matched, unmatched = match_names(notes, fmt, rule, kind, inference.checked)
        if listing == "found" and inference.verdict == "default" and not matched:
            hints.append(NO_NOTES_HINT.format(folder=folder))

        base = str_value(templates.get("base_path"))
        no_template = args.template == NO_TEMPLATE
        template = None if no_template else args.template or str_value(get_path(templates, ("mapping", granularity))[1])
        template_kind, template_text, candidates, hint = resolve_template(vault, base, template, kind,
                                                                          no_template=no_template)
        if hint is not None:
            hints.append(hint)
        template_headings = template_anchor_candidates(headings(template_text)) if template_text else []
        template_frontmatter = template_has_frontmatter(template_text) if template_text is not None else None
        needs_template_ok = template_frontmatter is False and args.template_frontmatter_ok != template

        place = section.get("place") if isinstance(section.get("place"), dict) else {}
        anchor = args.anchor or str_value(place.get("anchor")) or propose_anchor(template_headings)
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
    if candidates is not None:
        result["template_candidates"] = candidates
    if anchor_candidates is not None:
        result["needs_anchor"] = True
        result["anchor_candidates"] = anchor_candidates
    if needs_template_ok:
        result["needs_template_ok"] = True
    result["hints"] = hints
    return result
