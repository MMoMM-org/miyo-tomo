#!/usr/bin/env python3
# version: 0.2.0
"""test_review_config.py — Behavioural tests for lib.review_config (spec 045 T2.1).

Covers the /review setup model:
- review_setup layers config over profile (folders from the profile, the rest
  from the config), returns None while the setup is missing, validates a present
  one and reports JSON pointers
- folder_for: config over profile, a blank or disabled config entry is None
  and hides the profile (shared with review-session.py match)
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
- the session shapes review-session.py start prints: configured_formats,
  inbox_folder (config over profile), request_dict (plus first and last day),
  current_setup (proposal shape | None | pointers)
- spec 046 T1.3: section rows (each placement incl. review; groups per kind,
  never habits; id ^s[0-9]{1,3}$; cap 1..30; non-empty description; closed
  fields) and off_limits rows need a named template; duplicate heading keys and
  ids are refused; writer_edits touch only review.<g>.sections|off_limits.<template>;
  review_setup reads only the configured template's rows (F2-AC8), defaults cap,
  keywords and groups, and reports escaped pointers for bad rows; the quarter
  validates and reads through the quarterly keys; a config without the new keys
  reads as before
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


def test_folder_for_layers_config_over_profile_and_blank_path_is_none():
    assert rc.folder_for(CONFIG, PROFILE, "weekly") == "Calendar/302 Weekly/"
    assert rc.folder_for(CONFIG, PROFILE, "daily") == "Calendar/301 Daily/ "   # verbatim: the preview trims
    assert rc.folder_for({}, {}, "weekly") is None
    config = copy.deepcopy(CONFIG)
    config["concepts"]["calendar"]["granularities"]["weekly"] = {"enabled": True, "path": "   "}
    assert rc.folder_for(config, PROFILE, "weekly") is None      # blank in the config hides the profile
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, PROFILE, "week")
    assert exc.value.pointers == ["/concepts/calendar/granularities/weekly/path"]
    config["concepts"]["calendar"]["granularities"]["weekly"] = {"enabled": False, "path": "Weeks/"}
    assert rc.folder_for(config, PROFILE, "weekly") is None


def test_month_setup_defaults_and_the_configured_week_rule_for_the_overlapping_weeks():
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


# --- the session shapes (moved from review-session.py, T2.3 review) ------------------

def test_configured_formats_names_only_the_patterns_the_config_holds():
    assert rc.configured_formats(CONFIG) == {"week": "gggg-[W]ww", "month": "YYYY-MM"}
    assert rc.configured_formats({"naming": {"calendar_patterns": {"weekly": " ", "monthly": "YYYY-MM"}}}) == {"month": "YYYY-MM"}
    assert rc.configured_formats({}) == {}


def test_inbox_folder_is_config_over_profile_or_none():
    assert rc.inbox_folder(CONFIG, PROFILE) == "100 Inbox/"
    assert rc.inbox_folder({"concepts": {"inbox": "Eingang/"}}, PROFILE) == "Eingang/"
    assert rc.inbox_folder({}, PROFILE) == "100 Inbox/"
    assert rc.inbox_folder({"concepts": {"inbox": "  "}}, {}) is None


def test_request_dict_adds_the_first_and_last_day():
    from lib.period import Period, Request, SETUP, WEEK
    week = Request(WEEK, Period.week(2027, 1, WeekRule(6, 1)), source="default")
    assert rc.request_dict(week) == {"kind": "week", "period": "2027-W01", "year_inferred": False,
                                     "source": "default", "start": "2026-12-27", "end": "2027-01-02"}
    assert rc.request_dict(Request(SETUP)) == {"kind": "setup"}


def test_current_setup_is_the_proposal_shape_none_or_the_pointers():
    assert rc.current_setup(CONFIG, PROFILE, "week", TODAY) == {
        "folder": "Calendar/302 Weekly/", "format": "gggg-[W]ww", "first_day": "sunday", "min_days": 1,
        "template": "t_week_privat.md", "template_variant": None, "heading": "Tomo Review",
        "place": {"anchor": "In my own words", "placement": "before"},
        "own_sections": ["In my own words"], "daily_sections": ["Habit", "Daily Log"],
        "skip_sections": ["On This Day"], "task_notes": ["Efforts/Next Todos.md"],
        "max_chars_per_day": 9000, "language": "de",
    }
    month = rc.current_setup(CONFIG, PROFILE, "month", TODAY)
    assert month["first_day"] is None and month["min_days"] is None and month["template"] is None
    assert month["place"] == {"anchor": "Reflections", "placement": "inside"}
    assert rc.current_setup({}, PROFILE, "week", TODAY) is None
    broken = copy.deepcopy(CONFIG)
    broken["review"]["weekly"]["place"]["placement"] = "after"
    assert rc.current_setup(broken, PROFILE, "week", TODAY) == {"invalid": ["/review/weekly/place/placement"]}


# --- spec 046 T1.3: section rows, off-limits marks, the quarter ----------------------

ROW = {"id": "s1", "heading": "What Went Well This Week?", "level": 4, "parent": "In my own words",
       "occurrence": 1, "description": "What went well: finished tasks, good days", "placement": "end"}
OFF = {"heading": "Reflections", "level": 3, "parent": "Review of the Week", "occurrence": 1,
       "with_subsections": True}
QUARTER_INPUT = {
    "kind": "quarter", "folder": "Calendar/304 Quarterly/", "format": "YYYY-[Q]Q", "template": "t_quarter_privat.md",
    "heading": "Tomo Review", "place": {"anchor": "Conclusions", "placement": "before"}, "language": "de",
}


def _with_rows(base=WEEK_INPUT, sections=None, off_limits=None, **extra):
    data = dict(copy.deepcopy(base), **extra)
    if sections is not None:
        data["sections"] = sections
    if off_limits is not None:
        data["off_limits"] = off_limits
    return data


def _pointers(data):
    return [p.pointer for p in rc.input_problems(data, today=TODAY)]


@pytest.mark.parametrize("placement", ["before", "under", "end", "review"])
def test_schema_accepts_a_row_with_each_placement(placement):
    row = dict(ROW, placement=placement, keywords=["erledigt", "geschafft"], groups=["done", "themes"], cap=8)
    assert rc.input_problems(_with_rows(sections=[row]), today=TODAY) == []


@pytest.mark.parametrize("field, value, pointer", [
    ("groups", ["done", "habits"], "/sections/0/groups/1"),
    ("id", "s1000", "/sections/0/id"),
    ("id", "S1", "/sections/0/id"),
    ("id", "x1", "/sections/0/id"),
    ("id", "s", "/sections/0/id"),
    ("cap", 0, "/sections/0/cap"),
    ("cap", 31, "/sections/0/cap"),
    ("cap", 8.5, "/sections/0/cap"),
    ("description", "", "/sections/0/description"),
    ("description", "   ", "/sections/0/description"),
    ("placement", "inside", "/sections/0/placement"),
    ("level", 1, "/sections/0/level"),
    ("level", 7, "/sections/0/level"),
    ("occurrence", 0, "/sections/0/occurrence"),
    ("keywords", [f"k{i}" for i in range(13)], "/sections/0/keywords"),
    ("bogus", 1, "/sections/0"),
])
def test_schema_refuses_a_bad_row_at_its_pointer(field, value, pointer):
    assert pointer in _pointers(_with_rows(sections=[dict(ROW, **{field: value})]))


@pytest.mark.parametrize("missing", ["id", "heading", "level", "parent", "occurrence", "description", "placement"])
def test_schema_requires_every_identity_field_of_a_row(missing):
    row = {k: v for k, v in ROW.items() if k != missing}
    assert "/sections/0" in _pointers(_with_rows(sections=[row]))


@pytest.mark.parametrize("cap", [1, 30])
def test_cap_bounds_are_inclusive_and_a_top_level_heading_has_a_null_parent(cap):
    assert _pointers(_with_rows(sections=[dict(ROW, cap=cap, parent=None, level=2)])) == []


def test_off_limits_rows_with_and_without_subsections():
    rows = [OFF, dict(OFF, heading="Notes", with_subsections=False)]
    assert _pointers(_with_rows(off_limits=rows)) == []
    assert "/off_limits/0" in _pointers(_with_rows(off_limits=[{k: v for k, v in OFF.items() if k != "with_subsections"}]))
    assert "/off_limits/0/with_subsections" in _pointers(_with_rows(off_limits=[dict(OFF, with_subsections="yes")]))
    assert "/off_limits/0" in _pointers(_with_rows(off_limits=[dict(OFF, placement="end")]))


def test_rows_need_a_named_template():
    no_template = {k: v for k, v in _with_rows(sections=[ROW]).items() if k != "template"}
    assert "/" in _pointers(no_template)
    assert "/template" in _pointers(_with_rows(sections=[ROW], template=None))
    assert "/template" in _pointers(_with_rows(off_limits=[OFF], template=None))
    assert _pointers(dict(WEEK_INPUT, template=None)) == []          # without rows a null template still removes


@pytest.mark.parametrize("base, group, ok", [
    (WEEK_INPUT, "weekly_only", False), (WEEK_INPUT, "monthly_only", False),
    (MONTH_INPUT, "weekly_only", True), (MONTH_INPUT, "not_in_weekly", True), (MONTH_INPUT, "monthly_only", False),
    (QUARTER_INPUT, "monthly_only", True), (QUARTER_INPUT, "not_in_monthly", True), (QUARTER_INPUT, "weekly_only", False),
    (QUARTER_INPUT, "growth", True), (MONTH_INPUT, "habits", False), (QUARTER_INPUT, "habits", False),
])
def test_groups_follow_the_kind(base, group, ok):
    data = _with_rows(base, sections=[dict(ROW, groups=[group])], template="t.md")
    assert (_pointers(data) == []) is ok, _pointers(data)


def test_quarter_input_is_valid_and_forbids_the_week_keys():
    assert rc.input_problems(QUARTER_INPUT, today=TODAY) == []
    assert "/first_day" in _pointers(dict(QUARTER_INPUT, first_day="monday"))
    assert "/format" in _pointers(dict(QUARTER_INPUT, format="YYYY-MM"))


def test_input_problems_refuse_duplicate_heading_keys_and_ids():
    twice = _with_rows(sections=[ROW, dict(ROW, id="s2")])
    assert [p.to_dict() for p in rc.input_problems(twice, today=TODAY)] == [
        {"pointer": "/sections/1", "kind": "duplicate-section"}]
    same_id = _with_rows(sections=[ROW, dict(ROW, heading="Other")])
    assert [p.to_dict() for p in rc.input_problems(same_id, today=TODAY)] == [
        {"pointer": "/sections/1/id", "kind": "duplicate-section-id"}]
    off_twice = _with_rows(off_limits=[OFF, dict(OFF, with_subsections=False)])
    assert [p.to_dict() for p in rc.input_problems(off_twice, today=TODAY)] == [
        {"pointer": "/off_limits/1", "kind": "duplicate-off-limits"}]
    # the same text under another parent, at another level or a later occurrence is another heading
    others = [ROW, dict(ROW, id="s2", parent="Other"), dict(ROW, id="s3", level=5), dict(ROW, id="s4", occurrence=2)]
    assert rc.input_problems(_with_rows(sections=others), today=TODAY) == []


def test_writer_edits_touch_only_the_named_templates_entries():
    data = _with_rows(sections=[ROW], off_limits=[OFF])
    edits = rc.writer_edits(data)
    assert edits[:len(rc.writer_edits(WEEK_INPUT))] == rc.writer_edits(WEEK_INPUT)
    assert edits[len(rc.writer_edits(WEEK_INPUT)):] == [
        (("review", "weekly", "sections", "t_week_privat.md"), [ROW]),
        (("review", "weekly", "off_limits", "t_week_privat.md"), [OFF]),
    ]
    assert all(path[:3] != ("review", "weekly", "sections") for path, _ in rc.writer_edits(WEEK_INPUT))
    cleared = rc.writer_edits(_with_rows(sections=[]))
    assert (("review", "weekly", "sections", "t_week_privat.md"), []) in cleared


def test_quarter_writer_edits_use_the_quarterly_keys():
    edits = dict(rc.writer_edits(QUARTER_INPUT))
    assert edits[("concepts", "calendar", "granularities", "quarterly", "path")] == "Calendar/304 Quarterly/"
    assert edits[("naming", "calendar_patterns", "quarterly")] == "YYYY-[Q]Q"
    assert edits[("templates", "mapping", "quarterly")] == "t_quarter_privat.md"
    assert edits[("review", "quarterly", "place", "anchor")] == "Conclusions"
    assert not any(path[:2] == ("review", "week") for path in edits)


def _config_with_rows():
    config = copy.deepcopy(CONFIG)
    config["templates"]["mapping"]["monthly"] = "t_month_privat.md"
    weekly, monthly = config["review"]["weekly"], config["review"]["monthly"]
    weekly["sections"] = {"t_week_privat.md": [ROW], "t_week_work.md": [dict(ROW, id="s7", heading="Work")]}
    weekly["off_limits"] = {"t_week_privat.md": [OFF], "t_week_work.md": [dict(OFF, heading="Work")]}
    monthly["sections"] = {"t_month_privat.md": [dict(ROW, id="s3", groups=["weekly_only"], cap=12)]}
    return config


def test_review_setup_reads_only_the_configured_templates_rows_with_defaults():
    config = _config_with_rows()
    week = rc.review_setup(config, PROFILE, "week")
    assert week.sections == [dict(ROW, keywords=[], groups=[], cap=8)]
    assert week.off_limits == [OFF]
    month = rc.review_setup(config, PROFILE, "month")
    assert month.sections == [dict(ROW, id="s3", keywords=[], groups=["weekly_only"], cap=12)]
    assert month.off_limits == []
    config["templates"]["mapping"]["weekly"] = "t_week_work.md"
    work = rc.review_setup(config, PROFILE, "week")
    assert [r["heading"] for r in work.sections] == ["Work"] and [r["heading"] for r in work.off_limits] == ["Work"]
    config["templates"]["mapping"]["weekly"] = "t_week_other.md"
    assert rc.review_setup(config, PROFILE, "week").sections == []
    del config["templates"]["mapping"]["weekly"]
    unmapped = rc.review_setup(config, PROFILE, "week")
    assert unmapped.sections == [] and unmapped.off_limits == []


def test_review_setup_reports_pointers_for_invalid_rows_of_the_configured_template_only():
    config = _config_with_rows()
    config["review"]["weekly"]["sections"]["t_week_privat.md"] = [dict(ROW, cap=99), {**ROW, "bogus": 1}]
    config["review"]["weekly"]["off_limits"]["t_week_privat.md"] = [dict(OFF, with_subsections="yes")]
    config["review"]["weekly"]["sections"]["t_week_work.md"] = [{"junk": True}]   # another template: not read
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, PROFILE, "week")
    assert exc.value.pointers == [
        "/review/weekly/sections/t_week_privat.md/0/cap",
        "/review/weekly/sections/t_week_privat.md/1",
        "/review/weekly/off_limits/t_week_privat.md/0/with_subsections",
    ]
    config["review"]["weekly"]["sections"]["t_week_privat.md"] = [ROW, dict(ROW, id="s2"), dict(ROW, heading="B")]
    config["review"]["weekly"]["off_limits"]["t_week_privat.md"] = [OFF, OFF]
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, PROFILE, "week")
    assert exc.value.pointers == [
        "/review/weekly/sections/t_week_privat.md/1",
        "/review/weekly/sections/t_week_privat.md/2/id",
        "/review/weekly/off_limits/t_week_privat.md/1",
    ]
    config["templates"]["mapping"]["weekly"] = "a/b~c.md"
    config["review"]["weekly"]["sections"] = {"a/b~c.md": "not a list"}
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, PROFILE, "week")
    assert exc.value.pointers == ["/review/weekly/sections/a~1b~0c.md"]
    config["review"]["weekly"]["sections"] = ["not", "a", "mapping"]
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, PROFILE, "week")
    assert exc.value.pointers == ["/review/weekly/sections"]
    config["review"]["monthly"]["sections"] = {"t_month_privat.md": [dict(ROW, groups=["monthly_only"])]}
    with pytest.raises(rc.SetupInvalid) as exc:
        rc.review_setup(config, PROFILE, "month")
    assert exc.value.pointers == ["/review/monthly/sections/t_month_privat.md/0/groups/0"]


def test_a_config_without_the_new_keys_reads_as_before():
    setup = rc.review_setup(CONFIG, PROFILE, "week")
    assert setup.sections == [] and setup.off_limits == []
    assert set(rc.current_setup(CONFIG, PROFILE, "week", TODAY)) == {
        "folder", "format", "first_day", "min_days", "template", "template_variant", "heading", "place",
        "own_sections", "daily_sections", "skip_sections", "task_notes", "max_chars_per_day", "language"}
    assert rc.review_setup(CONFIG, PROFILE, "quarter") is None


def test_quarter_setup_reads_the_quarterly_keys_with_the_profile_folder():
    config = copy.deepcopy(CONFIG)
    config["naming"]["calendar_patterns"]["quarterly"] = "YYYY-[Q]Q"
    config["templates"]["mapping"]["quarterly"] = "t_quarter_privat.md"
    config["review"]["quarterly"] = {"heading": "Tomo Review", "place": {"anchor": "Conclusions", "placement": "before"},
                                     "sections": {"t_quarter_privat.md": [dict(ROW, groups=["not_in_monthly"])]}}
    profile = copy.deepcopy(PROFILE)
    profile["concept_defaults"]["calendar"]["granularities"]["quarterly"] = {"enabled": True, "path": "Calendar/304 Quarterly/"}
    setup = rc.review_setup(config, profile, "quarter")
    assert setup.kind == "quarter" and setup.folder == "Calendar/304 Quarterly/" and setup.format == "YYYY-[Q]Q"
    assert setup.template == "t_quarter_privat.md" and setup.sections[0]["groups"] == ["not_in_monthly"]
    assert rc.configured_formats(config)["quarter"] == "YYYY-[Q]Q"
