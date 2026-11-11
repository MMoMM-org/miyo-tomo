#!/usr/bin/env python3
# review-session.py — Deterministic session start and setup preview of /review.
# version: 0.1.0
"""Preview the /review setup of one period kind and build the writer input.

/review reads a finished week or month and proposes a review section for its
periodic note. Before the first review of a kind the user confirms where those
notes live, how they are named, how weeks are counted, which template they
use, where the review goes and which daily sections count (spec 045 F1). This
script makes that preview the same on every run: ``match`` lists the folder,
matches the existing names against the proposed format, infers the week rule
from the notes' own dates (never from the Obsidian plugin configuration),
classifies the template and proposes heading, place, daily sections and
language; ``setup-input`` turns the confirmed proposal into the input of
``vault-config-writer.py review``. Nothing is saved by either subcommand.

Usage (cwd = instance root):
    python3 scripts/review-session.py match --kind week|month
        [--folder P] [--format F] [--first-day D] [--min-days N] [--today YYYY-MM-DD]
    python3 scripts/review-session.py setup-input --kind week|month --confirmed <json>
        [--output tomo-tmp/review/setup-<kind>.json] [--today YYYY-MM-DD]

Output: one JSON object on stdout, ASCII-escaped.
    match: status ok|stopped, kind,
           proposal {folder, format, first_day, min_days, template, template_kind
                     plain|templater|missing|unreadable, heading, place {anchor, placement},
                     own_sections, daily_sections, language},
           evidence {matched, unmatched, week_rule inferred|ambiguous|default,
                     notes_checked, folder_listing found|kado-none, format_problems,
                     template_headings},
           daily_path_fix {configured, found} (only when the other spelling exists),
           hints [plain sentences for the skill],
           error {kind kado-unreachable|kado-auth|unsafe-format, detail?}
    setup-input: status ok, input_path, kind
               | status invalid, errors [json pointers], problems [{pointer, kind, example?}]

Rules:
    Flags win over the config, the config over the inference, the inference
    over the defaults (ISO weeks ``GGGG-[W]WW``, months ``YYYY-MM``).
    ``evidence.week_rule`` always reports what the notes showed.
    Up to 8 recent weekly notes are read for their dates; a dated note is
    matched only when the proposal's format and rule reproduce its name on
    its start date. No note text reaches stdout or stderr.

Exit codes:
    0 — output usable (every status, every error object)
    1 — unexpected exception; stderr carries the exception class name only
    2 — bad invocation (unknown subcommand or flag, bad value, unreadable --confirmed file)

Design notes: docs/tomo/scripts/review-session.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import review_config as rc  # noqa: E402
from lib.kado_client import (  # noqa: E402
    KadoAuthError, KadoClient, KadoConnectionError, KadoError, KadoNotFoundError,
)
from lib.note_io import ConfigError, atomic_write_text, load_vault_config  # noqa: E402
from lib.period import (  # noqa: E402
    DAY_NAMES, DEFAULT_FORMATS, ISO, KINDS, MONTH, WEEK, WeekRule, check_format, parse_name,
)
from lib.vault_config_edit import get_path  # noqa: E402
from lib.vault_folder_lookup import VaultFolderLookup  # noqa: E402

DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
DEFAULT_HEADING = "Tomo Review"
NOTES_TO_CHECK = 8
NON_ISO_WEEK_FORMAT = "gggg-[W]ww"
START_KEYS = ("journal-start-date",)
END_KEYS = ("journal-end-date",)
TEMPLATER_MARK = "<%"
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_DAY_LINK_RE = re.compile(r"\[\[(\d{4}-\d{2}-\d{2})")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")

FOLDER_HINT = ("Kado returned none for {folder}: the folder may be empty, or the Kado key "
               "may not reach it. Ask before proposing to create notes there.")
TEMPLATE_HINT = ("Kado could not read the template {path}; the Kado key may have no access "
                 "to it. A plain note (title and review section) is proposed instead.")


class Stopped(Exception):
    """Kado cannot be used for this preview; ``kind`` names the error kind."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


# ---------------------------------------------------------------- config

def load_config(path: str) -> dict:
    try:
        return load_vault_config(path)
    except ConfigError:
        return {}


def _str(value) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _str_list(value) -> Optional[List[str]]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def configured_folder(config: dict, profile: dict, granularity: str) -> Optional[str]:
    """``concepts.calendar.granularities.<g>.path``, config over profile; None when disabled."""
    for root, head in ((config, "concepts"), (profile, "concept_defaults")):
        found, entry = get_path(root, (head, "calendar", "granularities", granularity))
        if found and isinstance(entry, dict):
            if entry.get("enabled") is False:
                return None
            return entry.get("path") if isinstance(entry.get("path"), str) else None
    return None


def _review_section(config: dict, granularity: str) -> dict:
    section = get_path(config, ("review", granularity))[1]
    return section if isinstance(section, dict) else {}


def _configured_rule(config: dict) -> Optional[WeekRule]:
    week = get_path(config, ("review", "week"))[1]
    if not isinstance(week, dict) or "first_day" not in week:
        return None
    try:
        return WeekRule.from_config(week.get("first_day"), week.get("min_days_in_first_week", 4))
    except (ValueError, TypeError):
        return None


def _template_path(templates: dict, name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    base = _str(templates.get("base_path"))
    if base is None:
        return name
    return base.rstrip("/") + "/" + name


# ---------------------------------------------------------------- Kado access

class Vault:
    """The Kado calls ``match`` makes, each mapped onto the SDD's error kinds."""

    def __init__(self, client_factory):
        try:
            self.client = client_factory()
        except KadoError as exc:
            raise Stopped("kado-unreachable", str(exc)) from None

    def _guard(self, exc: KadoError) -> None:
        if isinstance(exc, KadoAuthError):
            raise Stopped("kado-auth", str(exc)) from None
        if isinstance(exc, KadoConnectionError):
            raise Stopped("kado-unreachable", str(exc)) from None

    def list_notes(self, folder: str) -> Optional[List[str]]:
        """Paths of the ``.md`` files in ``folder`` and its direct subfolders;
        None when Kado answered with nothing (an empty listing or ``Path not found``)."""
        try:
            items = self.client.list_dir(folder, depth=2)
        except KadoNotFoundError:
            return None
        except KadoError as exc:
            self._guard(exc)
            raise Stopped("kado-unreachable", str(exc)) from None
        if not items:
            return None
        return [str(i.get("path")) for i in items
                if i.get("type") == "file" and str(i.get("path", "")).endswith(".md")]

    def frontmatter(self, path: str) -> Optional[dict]:
        try:
            content = self.client.read_frontmatter(path).get("content")
        except KadoError as exc:
            self._guard(exc)
            return None
        return content if isinstance(content, dict) else None

    def note(self, path: str) -> Optional[str]:
        try:
            content = self.client.read_note(path).get("content")
        except KadoError as exc:
            self._guard(exc)
            return None
        return content if isinstance(content, str) else None

    def template(self, path: str) -> Tuple[str, Optional[str]]:
        """``(kind, text)``: plain | templater | missing | unreadable."""
        try:
            content = self.client.read_note(path).get("content")
        except KadoNotFoundError:
            return "missing", None
        except KadoError as exc:
            self._guard(exc)
            return "unreadable", None
        text = content if isinstance(content, str) else ""
        return ("templater" if TEMPLATER_MARK in text else "plain"), text

    def folder_listed(self, folder: str) -> bool:
        lookup = VaultFolderLookup(self.client)
        state = lookup.state(folder)
        if state == "unanswered":
            # the lookup swallowed the error; a dead connection must still stop the preview
            try:
                self.client.list_dir(folder, depth=1)
            except KadoError as exc:
                self._guard(exc)
        return state == "listed"


# ---------------------------------------------------------------- dates and headings

def _as_date(value) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def frontmatter_start(frontmatter: dict) -> Optional[date]:
    for key in START_KEYS:
        start = _as_date(frontmatter.get(key))
        if start is not None:
            return start
    for key in END_KEYS:
        end = _as_date(frontmatter.get(key))
        if end is not None:
            return end - timedelta(days=6)
    return None


def headings(text: str) -> List[Tuple[int, str]]:
    """``(level, text)`` of every heading outside code fences."""
    found: List[Tuple[int, str]] = []
    fence: Optional[str] = None
    for line in text.splitlines():
        opener = _FENCE_RE.match(line)
        if opener:
            mark = opener.group(1)[0]
            if fence is None:
                fence = mark
            elif mark == fence:
                fence = None
            continue
        if fence is not None:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((len(match.group(1)), match.group(2).strip()))
    return found


def heading_start(text: str) -> Optional[date]:
    """The week's first day from day-heading links, only when they cover a full week."""
    dates: Set[date] = set()
    for _, heading in headings(text):
        for raw in _DAY_LINK_RE.findall(heading):
            d = _as_date(raw)
            if d is not None:
                dates.add(d)
    if len(dates) != 7 or (max(dates) - min(dates)).days != 6:
        return None
    return min(dates)


# ---------------------------------------------------------------- the week rule

@dataclass
class Checked:
    stem: str
    start: Optional[date]
    locale: Optional[str]


@dataclass
class Inference:
    verdict: str                          # inferred | ambiguous | default
    rule: Optional[WeekRule] = None
    checked: List[Checked] = field(default_factory=list)


def rules_fitting(year: int, number: int, start: date) -> Set[WeekRule]:
    """Every rule starting on ``start``'s weekday under which (year, number) begins on ``start``."""
    first_day = start.weekday()
    fitting: Set[WeekRule] = set()
    for min_days in range(1, 8):
        rule = WeekRule(first_day, min_days)
        try:
            if rule.week_of(start) == (year, number):
                fitting.add(rule)
        except Exception:  # noqa: BLE001 — a date outside the supported years fits nothing
            continue
    return fitting


def choose_rule(fitting: Set[WeekRule]) -> WeekRule:
    """ISO's 4 when the notes allow it, else 1 (week 1 holds 1 January), else the smallest."""
    by_min_days = {rule.min_days_in_first_week: rule for rule in fitting}
    for preferred in (4, 1):
        if preferred in by_min_days:
            return by_min_days[preferred]
    return by_min_days[min(by_min_days)]


def recent_candidates(stems: Dict[str, str], fmt: str) -> List[Tuple[str, str, int, int]]:
    """``(stem, path, year, number)`` of the names that parse, most recent first."""
    found = []
    for stem, path in stems.items():
        period = parse_name(stem, fmt, ISO)
        if period is not None:
            found.append((stem, path, period.year, period.number))
    found.sort(key=lambda item: (item[2], item[3]), reverse=True)
    return found[:NOTES_TO_CHECK]


def infer_rule(vault: Vault, stems: Dict[str, str], fmt: str) -> Inference:
    candidates = recent_candidates(stems, fmt)
    if not candidates:
        return Inference("default")
    checked: List[Checked] = []
    fitting: Optional[Set[WeekRule]] = None
    for stem, path, year, number in candidates:
        frontmatter = vault.frontmatter(path) or {}
        locale = _str(frontmatter.get("locale"))
        start = frontmatter_start(frontmatter)
        if start is None:
            text = vault.note(path)
            start = heading_start(text) if text else None
        checked.append(Checked(stem, start, locale))
        if start is None:
            continue
        rules = rules_fitting(year, number, start)
        fitting = rules if fitting is None else fitting & rules
    if not fitting:
        return Inference("ambiguous", None, checked)
    return Inference("inferred", choose_rule(fitting), checked)


# ---------------------------------------------------------------- the proposal

def _day_name(rule: WeekRule) -> str:
    return DAY_NAMES[rule.first_day]


def anchor_candidates(template_headings: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
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
    return [text for level, text in headings(template_text)
            if level >= 2 and text and TEMPLATER_MARK not in text and "[[" not in text]


def _match_names(stems: Dict[str, str], fmt: str, rule: WeekRule, kind: str,
                 checked: List[Checked]) -> Tuple[List[str], List[str]]:
    starts = {c.stem: c.start for c in checked if c.start is not None}
    matched, unmatched = [], []
    for stem in stems:
        period = parse_name(stem, fmt, rule) if kind == WEEK else parse_name(stem, fmt)
        fits = period is not None and (stem not in starts or period.start == starts[stem])
        (matched if fits else unmatched).append(stem)
    return matched, unmatched


def match(args: argparse.Namespace) -> dict:
    kind = args.kind
    granularity = rc.GRANULARITY[kind]
    config = load_config(args.config)
    profile = rc.load_profile(Path(args.profiles_dir), config)
    templates = config.get("templates") if isinstance(config.get("templates"), dict) else {}
    section = _review_section(config, granularity)
    review = config.get("review") if isinstance(config.get("review"), dict) else {}
    hints: List[str] = []

    folder = args.folder or configured_folder(config, profile, granularity) or ""
    configured_fmt = _str(get_path(config, ("naming", "calendar_patterns", granularity))[1])
    fmt_for_names = args.format or configured_fmt or DEFAULT_FORMATS[kind]
    if any(mark in fmt_for_names for mark in ("/", "\\", "..")):
        return {"status": "stopped", "kind": kind, "error": {"kind": "unsafe-format"}}

    try:
        vault = Vault(KadoClient)
        paths = vault.list_notes(folder) if folder else None
        listing = "kado-none" if paths is None else "found"
        if paths is None:
            hints.append(FOLDER_HINT.format(folder=folder))
            paths = []
        stems = {PurePosixPath(p).name[:-3]: p for p in paths}

        inference = Inference("default")
        if kind == WEEK and paths:
            inference = infer_rule(vault, stems, fmt_for_names)
        rule = inference.rule or _configured_rule(config) or ISO
        if args.first_day is not None or args.min_days is not None:
            rule = WeekRule.from_config(
                args.first_day if args.first_day is not None else rule.first_day,
                args.min_days if args.min_days is not None else rule.min_days_in_first_week)
        if kind == WEEK:
            default_fmt = DEFAULT_FORMATS[WEEK] if rule == ISO else NON_ISO_WEEK_FORMAT
        else:
            default_fmt = DEFAULT_FORMATS[MONTH]
        fmt = args.format or configured_fmt or default_fmt
        problems = check_format(fmt, kind, rule, today=args.today)
        matched, unmatched = _match_names(stems, fmt, rule, kind, inference.checked)

        template_name = _str(get_path(templates, ("mapping", granularity))[1])
        template_path = _template_path(templates, template_name)
        template_kind, template_text = "missing", None
        if template_path is not None:
            template_kind, template_text = vault.template(template_path)
            if template_kind == "unreadable":
                hints.append(TEMPLATE_HINT.format(path=template_path))
        template_headings = anchor_candidates(headings(template_text)) if template_text else []

        daily_sections = _str_list(get_path(review, ("daily", "sections"))[1])
        if daily_sections is None:
            daily_sections = []
            daily_path = _template_path(templates, _str(get_path(templates, ("mapping", "daily"))[1]))
            if daily_path is not None:
                daily_kind, daily_text = vault.template(daily_path)
                if daily_text:
                    daily_sections = daily_sections_from(daily_text)

        result: dict = {"status": "ok", "kind": kind}
        daily_configured = configured_folder(config, profile, "daily")
        if daily_configured and daily_configured != daily_configured.strip():
            trimmed = daily_configured.strip()
            if vault.folder_listed(trimmed):
                result["daily_path_fix"] = {"configured": daily_configured, "found": trimmed}
    except Stopped as stop:
        return {"status": "stopped", "kind": kind, "error": {"kind": stop.kind, "detail": stop.detail}}

    place = section.get("place") if isinstance(section.get("place"), dict) else {}
    anchor = _str(place.get("anchor")) or propose_anchor(template_headings)
    placement = place.get("placement") if place.get("placement") in rc.PLACEMENTS else rc.BEFORE
    language = (_str(review.get("language"))
                or next((c.locale for c in inference.checked if c.locale), None)
                or rc.DEFAULT_LANGUAGE)
    result["proposal"] = {
        "folder": folder,
        "format": fmt,
        "first_day": _day_name(rule) if kind == WEEK else None,
        "min_days": rule.min_days_in_first_week if kind == WEEK else None,
        "template": template_name,
        "template_kind": template_kind,
        "heading": _str(section.get("heading")) or DEFAULT_HEADING,
        "place": {"anchor": anchor, "placement": placement},
        "own_sections": _str_list(section.get("own_sections")) or [],
        "daily_sections": daily_sections,
        "language": language,
    }
    result["evidence"] = {
        "matched": matched,
        "unmatched": unmatched,
        "week_rule": inference.verdict,
        "notes_checked": len(inference.checked),
        "folder_listing": listing,
        "format_problems": [{"kind": p.kind, "example": p.example} for p in problems],
        "template_headings": [{"level": level, "text": text} for level, text in template_headings],
    }
    result["hints"] = hints
    return result


# ---------------------------------------------------------------- setup-input

_INPUT_KEYS = ("folder", "format", "first_day", "min_days", "template", "template_variant", "heading",
               "place", "own_sections", "daily_sections", "skip_sections", "task_notes",
               "max_chars_per_day", "language")


def writer_input(confirmed: dict, kind: str) -> dict:
    """The writer's shape from a confirmed proposal: the preview-only keys dropped."""
    data: dict = {"kind": confirmed.get("kind", kind)}
    for key in _INPUT_KEYS:
        if key in confirmed:
            data[key] = confirmed[key]
    if kind == MONTH:
        for key in ("first_day", "min_days"):
            if data.get(key) is None:
                data.pop(key, None)
    fix = confirmed.get("daily_path_fix")
    if isinstance(fix, dict):
        fix = fix.get("found")
    if fix is not None:
        data["daily_path_fix"] = fix
    return data


def setup_input(args: argparse.Namespace) -> dict:
    kind = args.kind
    try:
        confirmed = json.loads(Path(args.confirmed).read_text(encoding="utf-8"))
    except ValueError:
        confirmed = None
    if not isinstance(confirmed, dict):
        return {"status": "invalid", "kind": kind, "errors": ["/"],
                "problems": [{"pointer": "/", "kind": "not-an-object"}]}
    data = writer_input(confirmed, kind)
    if data["kind"] != kind:
        return {"status": "invalid", "kind": kind, "errors": ["/kind"],
                "problems": [{"pointer": "/kind", "kind": "kind-mismatch"}]}
    problems = rc.input_problems(data, today=args.today)
    if problems:
        return {"status": "invalid", "kind": kind, "errors": [p.pointer for p in problems],
                "problems": [p.to_dict() for p in problems]}
    output = Path(args.output or f"tomo-tmp/review/setup-{kind}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(data, ensure_ascii=True, indent=2) + "\n")
    return {"status": "ok", "kind": kind, "input_path": str(output)}


# ---------------------------------------------------------------- main

def _date_arg(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from None


def _min_days_arg(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected an integer 1..7") from None
    if not 1 <= value <= 7:
        raise argparse.ArgumentTypeError("expected an integer 1..7")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Session start and setup preview for /review.")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR), help="framework profiles directory")
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("match", help="Preview the setup of one period kind against the existing notes")
    m.add_argument("--kind", required=True, choices=KINDS)
    m.add_argument("--folder", help="Folder of the periodic notes (default: config, then profile)")
    m.add_argument("--format", help="Name format (default: config, then inferred)")
    m.add_argument("--first-day", choices=DAY_NAMES, help="First day of the week (default: inferred)")
    m.add_argument("--min-days", type=_min_days_arg, help="Days week 1 must hold in the new year (default: inferred)")
    m.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)

    s = sub.add_parser("setup-input", help="Build the vault-config-writer review input from a confirmed proposal")
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--confirmed", required=True, help="JSON file with the confirmed proposal")
    s.add_argument("--output", help="Where to write the writer input (default: tomo-tmp/review/setup-<kind>.json)")
    s.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "setup-input" and not Path(args.confirmed).is_file():
            print("review-session: --confirmed file not readable (FileNotFoundError)", file=sys.stderr)
            return 2
        result = match(args) if args.command == "match" else setup_input(args)
    except Exception as exc:  # noqa: BLE001 — the contract: class name only, exit 1
        print(type(exc).__name__, file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
