# review_config.py — the /review setup: read it, validate it, map it onto config keys.
# version: 0.1.3
"""The ``/review`` setup of one period kind (spec 045, T2.1).

One owner for the config keys the setup lives in — ``concepts.calendar.
granularities.<weekly|monthly>`` (config over profile), ``naming.
calendar_patterns.<kind>``, ``templates.mapping.<kind>`` and the ``review:``
section — so what ``review-session.py start`` reads and what
``vault-config-writer.py review`` writes cannot drift.

``folder_for(config, profile, granularity)`` resolves one periodic folder
(config over profile, None when disabled or blank) for the reader and for the
setup preview alike.
``review_setup(config, profile, kind)`` returns a ``ReviewSetup``, None while
the setup is missing, or raises ``SetupInvalid`` (JSON pointers) when a
present setup is broken. ``input_problems(data, today=...)`` checks a writer
input against ``tomo/schemas/vault-config-review.schema.json`` and the name
format through ``period.check_format``; ``writer_edits(data)`` turns it into
``(path, value)`` leaf edits, None meaning "remove the key". ``place_level``
is the only owner of the heading-level rule (before = the anchor's level,
inside = one deeper, after refused; the review heading may not exceed level 5
so its groups stay <= 6); ``inbox_path`` is the guard every review write goes
through.

Needs PyYAML (profile) and jsonschema (a Tomo runtime dependency).

Design notes: docs/tomo/scripts/lib/review_config.md
"""
from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lib.period import ISO, KINDS, MONTH, WEEK, WeekRule, check_format
from lib.vault_config_edit import get_path

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "vault-config-review.schema.json"

GRANULARITY = {WEEK: "weekly", MONTH: "monthly"}
BEFORE = "before"
INSIDE = "inside"
PLACEMENTS = (BEFORE, INSIDE)
MAX_REVIEW_LEVEL = 5    # the review's group headings sit one level deeper and must stay <= 6
DEFAULT_LANGUAGE = "en"
DEFAULT_MAX_CHARS = 12000
_UNSAFE = ("/", "\\", "..")
_TRACKER_LISTS = (
    ("trackers", "daily_note_trackers", "today_fields"),
    ("trackers", "daily_note_trackers", "yesterday_fields"),
    ("trackers", "end_of_day_fields", "fields"),
)

Edit = Tuple[Tuple[str, ...], Any]


class SetupInvalid(ValueError):
    """A present setup the reader cannot use; ``pointers`` name the config keys."""

    def __init__(self, pointers: List[str]):
        super().__init__("review setup invalid: " + ", ".join(pointers))
        self.pointers = pointers


class PlaceRefused(ValueError):
    """The placement or the resulting heading level is not allowed."""


class PlaceMissing(LookupError):
    """The anchor heading is not among the target's headings."""


class UnsafePath(ValueError):
    """A name that would leave the inbox."""


@dataclass(frozen=True)
class Problem:
    pointer: str
    kind: str          # "schema" or a period.FormatProblem kind
    example: str = ""

    def to_dict(self) -> Dict[str, str]:
        out = {"pointer": self.pointer, "kind": self.kind}
        if self.example:
            out["example"] = self.example
        return out


@dataclass(frozen=True)
class ReviewSetup:
    kind: str
    folder: str
    format: str
    rule: WeekRule
    heading: str
    anchor: str
    placement: str
    inbox: str
    language: str = DEFAULT_LANGUAGE
    template: Optional[str] = None
    template_base: Optional[str] = None
    template_variant: Optional[str] = None
    own_sections: List[str] = field(default_factory=list)
    daily_sections: List[str] = field(default_factory=list)
    skip_sections: List[str] = field(default_factory=list)
    task_notes: List[str] = field(default_factory=list)
    max_chars_per_day: int = DEFAULT_MAX_CHARS
    tracker_types: Dict[str, str] = field(default_factory=dict)

    def place_level(self, target_headings: Sequence[Tuple[int, str]]) -> int:
        """Level of the review heading in a target with these ``(level, text)`` headings."""
        for level, text in target_headings:
            if text == self.anchor:
                return place_level(self.placement, level)
        raise PlaceMissing(f"anchor heading not found in the target ({len(target_headings)} headings)")

    def inbox_path(self, name: str) -> str:
        return inbox_path(self.inbox, name)


# --- reading -------------------------------------------------------------------------

def load_profile(profiles_dir: Path, config: dict) -> dict:
    """The profile the config names (default ``miyo``), ``{}`` when the file is missing."""
    import yaml

    name = str(config.get("profile") or "miyo")
    try:
        data = yaml.safe_load((Path(profiles_dir) / f"{name}.yaml").read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _str_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def folder_for(config: dict, profile: dict, granularity: str) -> Optional[str]:
    """``concepts.calendar.granularities.<granularity>.path``, config over profile.

    None when the first entry found is disabled or its path is blank; the profile
    is not consulted behind a config entry.
    """
    for root, head in ((config, "concepts"), (profile, "concept_defaults")):
        found, entry = get_path(root, (head, "calendar", "granularities", granularity))
        if found and isinstance(entry, dict):
            if entry.get("enabled") is False:
                return None
            return _str(entry.get("path"))
    return None


def setup_present(config: dict, kind: str) -> bool:
    """True when the user confirmed a setup for ``kind``: a name format and a review section."""
    granularity = GRANULARITY[kind]
    fmt = get_path(config, ("naming", "calendar_patterns", granularity))[1]
    section = get_path(config, ("review", granularity))[1]
    return _str(fmt) is not None and isinstance(section, dict) and bool(section)


def review_setup(config: dict, profile: dict, kind: str, *, today: Optional[date] = None) -> Optional[ReviewSetup]:
    """The setup of ``kind``; None while missing; ``SetupInvalid`` when present but broken."""
    if kind not in KINDS:
        raise ValueError("kind must be week or month")
    if not setup_present(config, kind):
        return None
    granularity = GRANULARITY[kind]
    pointers: List[str] = []
    section = get_path(config, ("review", granularity))[1]
    review = config.get("review") if isinstance(config.get("review"), dict) else {}

    folder = folder_for(config, profile, granularity)
    if folder is None:
        pointers.append(f"/concepts/calendar/granularities/{granularity}/path")

    inbox = _str(get_path(config, ("concepts", "inbox"))[1]) or _str(get_path(profile, ("concept_defaults", "inbox"))[1])
    if inbox is None:
        pointers.append("/concepts/inbox")

    week = review.get("week") if isinstance(review.get("week"), dict) else {}
    try:
        rule = WeekRule.from_config(week.get("first_day", "monday"), week.get("min_days_in_first_week", 4))
    except (ValueError, TypeError):
        rule = ISO
        pointers.append("/review/week/first_day" if "first_day" in week else "/review/week/min_days_in_first_week")

    fmt = get_path(config, ("naming", "calendar_patterns", granularity))[1]
    if check_format(fmt, kind, rule, today=today or date.today()):
        pointers.append(f"/naming/calendar_patterns/{granularity}")

    heading = _str(section.get("heading"))
    if heading is None:
        pointers.append(f"/review/{granularity}/heading")
    place = section.get("place") if isinstance(section.get("place"), dict) else {}
    anchor = _str(place.get("anchor"))
    if anchor is None:
        pointers.append(f"/review/{granularity}/place/anchor")
    placement = place.get("placement")
    if placement not in PLACEMENTS:
        pointers.append(f"/review/{granularity}/place/placement")
    own_sections = _str_list(section.get("own_sections"))
    if own_sections is None:
        pointers.append(f"/review/{granularity}/own_sections")
    variant = section.get("template_variant")
    if variant is not None and _str(variant) is None:
        pointers.append(f"/review/{granularity}/template_variant")

    daily = review.get("daily") if isinstance(review.get("daily"), dict) else {}
    lists = {name: _str_list(daily.get(name)) for name in ("sections", "skip_sections", "task_notes")}
    for name, value in lists.items():
        if value is None:
            pointers.append(f"/review/daily/{name}")
    max_chars = daily.get("max_chars_per_day", DEFAULT_MAX_CHARS)
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        pointers.append("/review/daily/max_chars_per_day")

    language = review.get("language", DEFAULT_LANGUAGE)
    if _str(language) is None:
        pointers.append("/review/language")

    template = get_path(config, ("templates", "mapping", granularity))[1]
    if template is not None and _str(template) is None:
        pointers.append(f"/templates/mapping/{granularity}")

    if pointers:
        raise SetupInvalid(pointers)
    return ReviewSetup(
        kind=kind, folder=folder, format=fmt, rule=rule, heading=heading, anchor=anchor,
        placement=placement, inbox=inbox, language=language, template=template,
        template_base=_str(get_path(config, ("templates", "base_path"))[1]), template_variant=variant,
        own_sections=own_sections, daily_sections=lists["sections"], skip_sections=lists["skip_sections"],
        task_notes=lists["task_notes"], max_chars_per_day=max_chars, tracker_types=tracker_types(config),
    )


def tracker_types(config: dict) -> Dict[str, str]:
    """``{tracker name: type}`` over the three tracker lists of the config."""
    types: Dict[str, str] = {}
    for path in _TRACKER_LISTS:
        found, fields = get_path(config, path)
        if not found or not isinstance(fields, list):
            continue
        for entry in fields:
            if isinstance(entry, dict) and _str(entry.get("name")) and _str(entry.get("type")):
                types[entry["name"]] = entry["type"]
    return types


# --- the writer input ----------------------------------------------------------------

def _pointer(parts: Sequence[Any]) -> str:
    return "/" + "/".join(str(p) for p in parts) if parts else "/"


def input_problems(data: Any, *, today: Optional[date] = None) -> List[Problem]:
    """Schema violations (kind ``schema``) and name-format problems (pointer ``/format``)."""
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    pointers = sorted({_pointer(err.absolute_path) for err in validator.iter_errors(data)})
    problems = [Problem(p, "schema") for p in pointers]
    if problems:
        return problems
    rule = WeekRule.from_config(data["first_day"], data["min_days"]) if data["kind"] == WEEK else ISO
    for fp in check_format(data["format"], data["kind"], rule, today=today or date.today()):
        problems.append(Problem("/format", fp.kind, fp.example))
    return problems


def writer_edits(data: dict) -> List[Edit]:
    """Leaf edits for a schema-valid input, in the order of the SDD's config example."""
    kind = data["kind"]
    g = GRANULARITY[kind]
    edits: List[Edit] = [
        (("concepts", "calendar", "granularities", g, "enabled"), True),
        (("concepts", "calendar", "granularities", g, "path"), data["folder"]),
        (("naming", "calendar_patterns", g), data["format"]),
    ]
    if "template" in data:
        edits.append((("templates", "mapping", g), data["template"]))
    edits.append((("review", "language"), data["language"]))
    if kind == WEEK:
        edits.append((("review", "week", "first_day"), data["first_day"]))
        edits.append((("review", "week", "min_days_in_first_week"), data["min_days"]))
    for key, config_key in (("daily_sections", "sections"), ("skip_sections", "skip_sections"),
                            ("task_notes", "task_notes"), ("max_chars_per_day", "max_chars_per_day")):
        if key in data:
            edits.append((("review", "daily", config_key), data[key]))
    edits.append((("review", g, "heading"), data["heading"]))
    edits.append((("review", g, "place", "anchor"), data["place"]["anchor"]))
    edits.append((("review", g, "place", "placement"), data["place"]["placement"]))
    if "own_sections" in data:
        edits.append((("review", g, "own_sections"), data["own_sections"]))
    if "template_variant" in data:
        edits.append((("review", g, "template_variant"), data["template_variant"]))
    if "daily_path_fix" in data:
        edits.append((("concepts", "calendar", "granularities", "daily", "path"), data["daily_path_fix"]))
    return edits


# --- the level rule and the inbox guard ----------------------------------------------

def place_level(placement: str, anchor_level: int) -> int:
    """Level of the review heading: ``before`` = the anchor's, ``inside`` = one deeper.

    Refused above ``MAX_REVIEW_LEVEL`` (5): the group headings below it would exceed level 6.
    """
    if placement == BEFORE:
        level = anchor_level
    elif placement == INSIDE:
        level = anchor_level + 1
    else:
        raise PlaceRefused("placement must be before or inside")
    if level > MAX_REVIEW_LEVEL:
        raise PlaceRefused(
            f"review heading level {level} is above {MAX_REVIEW_LEVEL}: its group headings would exceed level 6"
        )
    return level


def inbox_path(inbox: str, name: str) -> str:
    """``<inbox>/<name>``; ``UnsafePath`` for a name or result that leaves the inbox."""
    if not name.strip() or any(mark in name for mark in _UNSAFE) or name.strip() == ".":
        raise UnsafePath("name must be a plain filename without /, \\ or ..")
    raw = inbox.strip().strip("/")
    if not raw or any(mark in raw for mark in ("\\", "..")):
        raise UnsafePath("inbox folder is not configured")
    base = posixpath.normpath(raw)
    if base in ("", "."):
        raise UnsafePath("inbox folder is not configured")
    result = posixpath.normpath(f"{base}/{name}")
    if not result.startswith(base + "/") or result == base + "/":
        raise UnsafePath("result would lie outside the inbox")
    return result
