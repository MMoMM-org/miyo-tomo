#!/usr/bin/env python3
# version: 0.1.1
"""test_review_config.py — Behavioural tests for lib.review_config (spec 045 T2.1).

Covers the /review setup model:
- review_setup layers config over profile (folders from the profile, the rest
  from the config), returns None while the setup is missing, validates a present
  one and reports JSON pointers
- input_problems validates the writer input against
  vault-config-review.schema.json (pointers) and refuses an unusable name format
- writer_edits maps a confirmed input onto the config key paths, writes only
  what the input carries, removes a key on null, fixes the daily path only when told
- place_level: before = anchor level, inside = +1, after refused; the review
  heading may not exceed level 5 (its groups stay <= 6); missing anchor reported
- inbox_path refuses "/", "\\", "..", an empty name, an empty inbox and any
  result outside the inbox; an inbox spelled "./Inbox" or "a/./b" is normalised
  before the comparison and accepted
- tracker_types reads trackers.daily_note_trackers and end_of_day_fields
"""
from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import review_config as rc  # noqa: E402
from lib.period import ISO, WeekRule  # noqa: E402

TODAY = date(2026, 11, 11)

PROFILE = {
    "concept_defaults": {
        "inbox": "100 Inbox/",
        "calendar": {
            "granularities": {
                "weekly": {"enabled": True, "path": "Calendar/302 Weekly/"},
                "monthly": {"enabled": True, "path": "Calendar/303 Monthly/"},
            }
        },
    }
}

CONFIG = {
    "concepts": {
        "inbox": "100 Inbox/",
        "calendar": {"granularities": {"daily": {"enabled": True, "path": "Calendar/301 Daily/ "}}},
    },
    "naming": {"calendar_patterns": {"weekly": "gggg-[W]ww", "monthly": "YYYY-MM"}},
    "templates": {"base_path": "X/900 Support/930 Templater/", "mapping": {"weekly": "t_week_privat.md"}},
    "trackers": {
        "daily_note_trackers": {
            "today_fields": [{"name": "Sport", "type": "boolean"}, {"name": "Sleep", "type": "text"}],
            "yesterday_fields": [{"name": "DayEnergy", "type": "integer"}],
        },
        "end_of_day_fields": {"fields": [{"name": "Gratitude", "type": "text"}]},
    },
    "review": {
        "language": "de",
        "week": {"first_day": "sunday", "min_days_in_first_week": 1},
        "daily": {"sections": ["Habit", "Daily Log"], "skip_sections": ["On This Day"],
                  "task_notes": ["Efforts/Next Todos.md"], "max_chars_per_day": 9000},
        "weekly": {"heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
                   "own_sections": ["In my own words"], "template_variant": None},
        "monthly": {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"}},
    },
}

WEEK_INPUT = {
    "kind": "week", "folder": "Calendar/302 Weekly/", "format": "gggg-[W]ww",
    "first_day": "sunday", "min_days": 1, "template": "t_week_privat.md", "template_variant": None,
    "heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
    "own_sections": ["In my own words", "Reflections"],
    "daily_sections": ["Habit", "Daily Log"], "skip_sections": ["On This Day"],
    "task_notes": ["Efforts/Next Todos.md"], "max_chars_per_day": 12000, "language": "de",
}

MONTH_INPUT = {
    "kind": "month", "folder": "Calendar/303 Monthly/", "format": "YYYY-MM", "template": None,
    "heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "inside"}, "language": "en",
}


# --- review_setup --------------------------------------------------------------------

def test_setup_layers_config_over_profile():
    setup = rc.review_setup(CONFIG, PROFILE, "week")
    assert setup is not None
    assert setup.folder == "Calendar/302 Weekly/"          # from the profile
    assert setup.format == "gggg-[W]ww"
    assert setup.rule == WeekRule(6, 1)
    assert setup.language == "de"
    assert setup.template == "t_week_privat.md" and setup.template_base == "X/900 Support/930 Templater/"
    assert setup.template_variant is None
    assert setup.heading == "Tomo Review" and setup.anchor == "In my own words" and setup.placement == "before"
    assert setup.own_sections == ["In my own words"]
    assert setup.daily_sections == ["Habit", "Daily Log"] and setup.skip_sections == ["On This Day"]
    assert setup.task_notes == ["Efforts/Next Todos.md"] and setup.max_chars_per_day == 9000
    assert setup.inbox == "100 Inbox/"
    assert setup.tracker_types == {"Sport": "boolean", "Sleep": "text", "DayEnergy": "integer", "Gratitude": "text"}


def test_config_folder_wins_over_profile_and_enabled_false_means_no_folder():
    config = copy.deepcopy(CONFIG)
    config["concepts"]["calendar"]["granularities"]["weekly"] = {"enabled": True, "path": "Weeks/"}
    assert rc.review_setup(config, PROFILE, "week").folder == "Weeks/"
    config["concepts"]["calendar"]["granularities"]["weekly"]["enabled"] = False
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, PROFILE, "week")
    assert "/concepts/calendar/granularities/weekly/path" in exc.value.pointers


def test_month_setup_defaults_and_iso_rule_for_month_reading():
    setup = rc.review_setup(CONFIG, PROFILE, "month")
    assert setup.kind == "month" and setup.folder == "Calendar/303 Monthly/" and setup.format == "YYYY-MM"
    assert setup.placement == "inside" and setup.template is None
    assert setup.own_sections == [] and setup.template_variant is None
    assert setup.rule == WeekRule(6, 1)   # the month's overlapping weeks follow the user's week rule


def test_setup_missing_when_format_or_review_section_absent():
    config = copy.deepcopy(CONFIG)
    del config["naming"]["calendar_patterns"]["monthly"]
    assert rc.review_setup(config, PROFILE, "month") is None
    config = copy.deepcopy(CONFIG)
    del config["review"]["weekly"]
    assert rc.review_setup(config, PROFILE, "week") is None
    assert rc.review_setup({}, PROFILE, "week") is None
    assert rc.setup_present({}, "week") is False and rc.setup_present(CONFIG, "week") is True


def test_setup_defaults_when_present_but_sparse():
    config = {
        "concepts": {"inbox": "In/"},
        "naming": {"calendar_patterns": {"weekly": "GGGG-[W]WW"}},
        "review": {"weekly": {"heading": "Review", "place": {"anchor": "Notes", "placement": "inside"}}},
    }
    setup = rc.review_setup(config, PROFILE, "week")
    assert setup.rule == ISO and setup.language == "en" and setup.daily_sections == []
    assert setup.skip_sections == [] and setup.task_notes == [] and setup.max_chars_per_day == 12000
    assert setup.template is None and setup.template_base is None and setup.tracker_types == {}


def test_present_but_broken_setup_raises_with_pointers():
    config = copy.deepcopy(CONFIG)
    config["review"]["weekly"]["place"]["placement"] = "after"
    config["review"]["week"]["first_day"] = "someday"
    config["naming"]["calendar_patterns"]["weekly"] = "YYYY-[W]WW"
    del config["concepts"]["inbox"]
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, {}, "week")
    assert set(exc.value.pointers) >= {
        "/review/weekly/place/placement", "/review/week/first_day",
        "/naming/calendar_patterns/weekly", "/concepts/inbox",
    }


def test_setup_without_folder_anywhere_is_invalid():
    config = copy.deepcopy(CONFIG)
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, {}, "week")
    assert exc.value.pointers == ["/concepts/calendar/granularities/weekly/path"]


def test_load_profile_reads_the_named_profile_or_nothing(tmp_path):
    (tmp_path / "miyo.yaml").write_text("concept_defaults:\n  inbox: \"I/\"\n", encoding="utf-8")
    assert rc.load_profile(tmp_path, {"profile": "miyo"}) == {"concept_defaults": {"inbox": "I/"}}
    assert rc.load_profile(tmp_path, {}) == {"concept_defaults": {"inbox": "I/"}}
    assert rc.load_profile(tmp_path, {"profile": "other"}) == {}


# --- input_problems ------------------------------------------------------------------

def test_valid_inputs_have_no_problems():
    assert rc.input_problems(WEEK_INPUT, today=TODAY) == []
    assert rc.input_problems(MONTH_INPUT, today=TODAY) == []


def test_schema_violations_are_reported_as_pointers():
    bad = copy.deepcopy(WEEK_INPUT)
    bad["place"]["placement"] = "after"
    bad["min_days"] = 9
    bad["extra"] = 1
    pointers = [p.pointer for p in rc.input_problems(bad, today=TODAY)]
    assert "/place/placement" in pointers and "/min_days" in pointers and "/" in pointers
    missing = [p.pointer for p in rc.input_problems({"kind": "week"}, today=TODAY)]
    assert "/" in missing
    month = dict(MONTH_INPUT, first_day="monday")
    assert any(p.pointer == "/first_day" for p in rc.input_problems(month, today=TODAY))
    assert any(p.pointer == "/" for p in rc.input_problems([], today=TODAY))


def test_unusable_format_is_a_problem_at_format():
    for fmt in ("YYYY-[W]WW", "GGGG/[W]WW", "YYYY-MM", "GGGG-[W]WW"):
        bad = dict(WEEK_INPUT, format=fmt)        # the Sunday rule refuses ISO tokens too
        problems = rc.input_problems(bad, today=TODAY)
        assert problems and all(p.pointer == "/format" for p in problems), fmt
    kinds = {p.kind for p in rc.input_problems(dict(WEEK_INPUT, format="YYYY-[W]WW"), today=TODAY)}
    assert "calendar-year-with-week" in kinds
    assert rc.input_problems(dict(MONTH_INPUT, format="YYYY-[W]WW"), today=TODAY)[0].kind == "kind-mismatch"


# --- writer_edits --------------------------------------------------------------------

def test_week_input_maps_onto_config_paths_in_sdd_order():
    edits = rc.writer_edits(WEEK_INPUT)
    assert edits == [
        (("concepts", "calendar", "granularities", "weekly", "enabled"), True),
        (("concepts", "calendar", "granularities", "weekly", "path"), "Calendar/302 Weekly/"),
        (("naming", "calendar_patterns", "weekly"), "gggg-[W]ww"),
        (("templates", "mapping", "weekly"), "t_week_privat.md"),
        (("review", "language"), "de"),
        (("review", "week", "first_day"), "sunday"),
        (("review", "week", "min_days_in_first_week"), 1),
        (("review", "daily", "sections"), ["Habit", "Daily Log"]),
        (("review", "daily", "skip_sections"), ["On This Day"]),
        (("review", "daily", "task_notes"), ["Efforts/Next Todos.md"]),
        (("review", "daily", "max_chars_per_day"), 12000),
        (("review", "weekly", "heading"), "Tomo Review"),
        (("review", "weekly", "place", "anchor"), "In my own words"),
        (("review", "weekly", "place", "placement"), "before"),
        (("review", "weekly", "own_sections"), ["In my own words", "Reflections"]),
        (("review", "weekly", "template_variant"), None),
    ]


def test_month_input_writes_only_what_it_carries_and_null_removes():
    edits = rc.writer_edits(MONTH_INPUT)
    assert edits == [
        (("concepts", "calendar", "granularities", "monthly", "enabled"), True),
        (("concepts", "calendar", "granularities", "monthly", "path"), "Calendar/303 Monthly/"),
        (("naming", "calendar_patterns", "monthly"), "YYYY-MM"),
        (("templates", "mapping", "monthly"), None),
        (("review", "language"), "en"),
        (("review", "monthly", "heading"), "Tomo Review"),
        (("review", "monthly", "place", "anchor"), "In my own words"),
        (("review", "monthly", "place", "placement"), "inside"),
    ]
    without_template = {k: v for k, v in MONTH_INPUT.items() if k != "template"}
    assert all(path[0] != "templates" for path, _ in rc.writer_edits(without_template))


def test_daily_path_fix_only_when_the_input_says_so():
    daily = ("concepts", "calendar", "granularities", "daily", "path")
    assert all(path != daily for path, _ in rc.writer_edits(WEEK_INPUT))
    edits = rc.writer_edits(dict(WEEK_INPUT, daily_path_fix="Calendar/301 Daily/"))
    assert (daily, "Calendar/301 Daily/") in edits


# --- place_level ---------------------------------------------------------------------

def test_place_level_rule():
    assert rc.place_level("before", 3) == 3
    assert rc.place_level("inside", 3) == 4
    assert rc.place_level("before", 5) == 5
    assert rc.place_level("inside", 4) == 5
    with pytest.raises(rc.PlaceRefused):
        rc.place_level("after", 3)


@pytest.mark.parametrize("placement, anchor_level", [("before", 6), ("inside", 5), ("inside", 6), ("before", 7)])
def test_place_level_refuses_a_review_heading_above_5_because_its_groups_would_exceed_6(placement, anchor_level):
    with pytest.raises(rc.PlaceRefused, match="exceed level 6"):
        rc.place_level(placement, anchor_level)


def test_setup_place_level_finds_the_anchor_case_sensitively():
    setup = rc.review_setup(CONFIG, PROFILE, "week")
    headings = [(2, "Week"), (3, "In my own words"), (3, "Reflections")]
    assert setup.place_level(headings) == 3
    inside = rc.review_setup(CONFIG, PROFILE, "month")
    assert inside.place_level(headings) == 4
    with pytest.raises(rc.PlaceMissing):
        setup.place_level([(2, "Week"), (3, "in my own words")])


# --- inbox_path ----------------------------------------------------------------------

def test_inbox_path_joins_inside_the_inbox():
    assert rc.inbox_path("100 Inbox/", "2026-W13 Review.md") == "100 Inbox/2026-W13 Review.md"
    assert rc.inbox_path("100 Inbox", "x.md") == "100 Inbox/x.md"
    setup = rc.review_setup(CONFIG, PROFILE, "week")
    assert setup.inbox_path("2026-W13_review_instructions.json") == "100 Inbox/2026-W13_review_instructions.json"


@pytest.mark.parametrize("name", ["a/b.md", "a\\b.md", "../x.md", "x..md", "..", ".", "", "   "])
def test_inbox_path_refuses_unsafe_names(name):
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path("100 Inbox/", name)


def test_inbox_path_refuses_empty_inbox_and_escapes():
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path("", "x.md")
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path("/", "x.md")
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path("../", "x.md")
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path("a/../b", "x.md")
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path("a\\b", "x.md")
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path(".", "x.md")
    with pytest.raises(rc.UnsafePath):
        rc.inbox_path("./", "x.md")


@pytest.mark.parametrize("inbox, expected", [
    ("./Inbox", "Inbox/x.md"),
    ("./Inbox/", "Inbox/x.md"),
    ("a/./b", "a/b/x.md"),
    ("a//b/", "a/b/x.md"),
])
def test_inbox_path_normalises_the_inbox_folder_before_comparing(inbox, expected):
    assert rc.inbox_path(inbox, "x.md") == expected


# --- tracker_types -------------------------------------------------------------------

def test_tracker_types_reads_all_three_lists_and_tolerates_junk():
    assert rc.tracker_types(CONFIG) == {"Sport": "boolean", "Sleep": "text", "DayEnergy": "integer", "Gratitude": "text"}
    assert rc.tracker_types({}) == {}
    assert rc.tracker_types({"trackers": {"daily_note_trackers": {"today_fields": ["junk", {"name": "X"}]}}}) == {}
