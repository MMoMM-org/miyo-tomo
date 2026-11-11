#!/usr/bin/env python3
# version: 0.1.0
"""test_review_habits.py — Behavioural tests for lib.review_habits (spec 045 T3.5, PRD F8).

Covers the habits group as numbers:
- boolean trackers give a day count over the days with a value (F8-AC1)
- integer, duration and time trackers give an average over the days with a
  value; duration and HH:mm time are averaged in minutes and rendered back
- missing days (no field, empty value) and unreadable values ("ja" for a
  number, "7" for a yes/no field, an unrun Templater `<% … %>`) are named
  by date and never counted as zero (F8-AC2)
- yesterday_fields values shift to the previous day: the value in the
  period's first daily is dropped, the value in the daily after the period
  counts for the last day; shift_yesterday=False leaves them in place
- text trackers are skipped; no trackers, or no value on any day → the item
  or the whole result is absent (F8-AC3)
- the rendered line follows the de/en label table, English otherwise
- tracker_defs reads the three tracker lists of the config in order, with
  the yesterday flag

All data is synthetic.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import review_habits as rh  # noqa: E402

FIRST = date(2026, 3, 23)
PERIOD = [FIRST + timedelta(days=i) for i in range(7)]  # 2026-03-23 .. 2026-03-29


def day(d: date, **fields) -> dict:
    return {"date": d.isoformat(), "fields": dict(fields)}


def tracker(name: str, type_: str, yesterday: bool = False) -> rh.TrackerDef:
    return rh.TrackerDef(name=name, type=type_, yesterday=yesterday)


def one(items: list, name: str) -> dict:
    found = [i for i in items if i["tracker"] == name]
    assert len(found) == 1, f"{name}: {len(found)} items"
    return found[0]


# --- booleans as day counts ----------------------------------------------------------

def test_boolean_counts_days_true_over_days_with_value():
    days = [
        day(PERIOD[0], Sport="true"),
        day(PERIOD[1], Sport="false"),
        day(PERIOD[2], Sport="yes"),
        day(PERIOD[3], Sport="no"),
        day(PERIOD[4], Sport="x"),
    ]
    items = rh.habits([tracker("Sport", "boolean")], days, PERIOD, "en")
    item = one(items, "Sport")
    assert item["kind"] == "count"
    assert item["type"] == "boolean"
    assert item["value"] == 3
    assert item["days_with_value"] == 5
    assert item["days_in_period"] == 7
    assert item["missing"] == ["2026-03-28", "2026-03-29"]
    assert item["unreadable"] == []


@pytest.mark.parametrize("raw,expected", [
    ("true", True), ("True", True), ("yes", True), ("ja", True), ("x", True), ("X", True),
    ("1", True), ("✅", True), ("[x]", True), (True, True),
    ("false", False), ("no", False), ("nein", False), ("0", False), ("❌", False),
    ("[ ]", False), (False, False),
])
def test_boolean_spellings(raw, expected):
    items = rh.habits([tracker("Sport", "boolean")], [day(PERIOD[0], Sport=raw)], PERIOD, "en")
    item = one(items, "Sport")
    assert item["days_with_value"] == 1
    assert item["value"] == (1 if expected else 0)


def test_boolean_number_is_unreadable_not_false():
    items = rh.habits(
        [tracker("Sport", "boolean")],
        [day(PERIOD[0], Sport="7"), day(PERIOD[1], Sport="true")],
        PERIOD, "en",
    )
    item = one(items, "Sport")
    assert item["unreadable"] == ["2026-03-23"]
    assert item["days_with_value"] == 1
    assert item["value"] == 1


# --- numbers as averages -------------------------------------------------------------

def test_integer_average_over_days_with_value():
    days = [day(PERIOD[0], Energy="3"), day(PERIOD[1], Energy="4"), day(PERIOD[3], Energy="5")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["kind"] == "average"
    assert item["value"] == pytest.approx(4.0)
    assert item["rendered"] == "4.0"
    assert item["days_with_value"] == 3
    assert item["missing"] == ["2026-03-25", "2026-03-27", "2026-03-28", "2026-03-29"]


def test_integer_accepts_decimal_with_dot_or_comma_and_native_numbers():
    days = [day(PERIOD[0], Energy="3.5"), day(PERIOD[1], Energy="4,5"), day(PERIOD[2], Energy=4)]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["days_with_value"] == 3
    assert item["value"] == pytest.approx(4.0)


def test_word_for_a_number_is_unreadable_never_zero():
    days = [day(PERIOD[0], Energy="ja"), day(PERIOD[1], Energy="4"), day(PERIOD[2], Energy="6")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["unreadable"] == ["2026-03-23"]
    assert item["days_with_value"] == 2
    assert item["value"] == pytest.approx(5.0)  # 4 and 6, the "ja" day is not a 0


def test_unrun_templater_tag_is_unreadable_for_every_type():
    tag = '<% tp.date.now("HH:mm") %>'
    defs = [tracker("Sport", "boolean"), tracker("Energy", "integer"),
            tracker("Sleep", "duration"), tracker("WakeUp", "time")]
    days = [
        day(PERIOD[0], Sport=tag, Energy=tag, Sleep=tag, WakeUp=tag),
        day(PERIOD[1], Sport="true", Energy="4", Sleep="7h", WakeUp="06:30"),
    ]
    items = rh.habits(defs, days, PERIOD, "en")
    for name in ("Sport", "Energy", "Sleep", "WakeUp"):
        item = one(items, name)
        assert item["unreadable"] == ["2026-03-23"], name
        assert item["days_with_value"] == 1, name


def test_empty_value_is_missing_not_unreadable():
    days = [day(PERIOD[0], Energy=""), day(PERIOD[1], Energy="   "), day(PERIOD[2], Energy="4")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert "2026-03-23" in item["missing"]
    assert "2026-03-24" in item["missing"]
    assert item["unreadable"] == []
    assert item["days_with_value"] == 1


def test_duration_averaged_in_minutes_and_rendered_back():
    days = [day(PERIOD[0], Sleep="7h30"), day(PERIOD[1], Sleep="7:30"), day(PERIOD[2], Sleep="8h")]
    item = one(rh.habits([tracker("Sleep", "duration")], days, PERIOD, "en"), "Sleep")
    assert item["kind"] == "average"
    assert item["value"] == pytest.approx(460.0)  # minutes: (450 + 450 + 480) / 3
    assert item["rendered"] == "7h 40m"


@pytest.mark.parametrize("raw,minutes", [
    ("7h30", 450), ("7h 30m", 450), ("7:30", 450), ("450m", 450), ("90 min", 90),
    ("1.5h", 90), ("7", 420), ("7,5", 450), ("0h45", 45), ("2 h", 120),
])
def test_duration_spellings(raw, minutes):
    item = one(rh.habits([tracker("Sleep", "duration")], [day(PERIOD[0], Sleep=raw)], PERIOD, "en"), "Sleep")
    assert item["days_with_value"] == 1
    assert item["value"] == pytest.approx(minutes)


def test_duration_word_is_unreadable():
    item = one(rh.habits([tracker("Sleep", "duration")],
                         [day(PERIOD[0], Sleep="gut"), day(PERIOD[1], Sleep="7h")], PERIOD, "en"), "Sleep")
    assert item["unreadable"] == ["2026-03-23"]
    assert item["value"] == pytest.approx(420)


def test_time_averaged_in_minutes_since_midnight_rendered_hh_mm():
    days = [day(PERIOD[0], WakeUp="06:30"), day(PERIOD[1], WakeUp="7:30"), day(PERIOD[2], WakeUp="07:00:00")]
    item = one(rh.habits([tracker("WakeUp", "time")], days, PERIOD, "en"), "WakeUp")
    assert item["value"] == pytest.approx(420.0)
    assert item["rendered"] == "07:00"


def test_time_without_colon_or_out_of_range_is_unreadable():
    days = [day(PERIOD[0], WakeUp="seven"), day(PERIOD[1], WakeUp="25:00"), day(PERIOD[2], WakeUp="07:00")]
    item = one(rh.habits([tracker("WakeUp", "time")], days, PERIOD, "en"), "WakeUp")
    assert item["unreadable"] == ["2026-03-23", "2026-03-24"]
    assert item["days_with_value"] == 1


# --- yesterday fields ----------------------------------------------------------------

def test_yesterday_field_counts_for_the_previous_day():
    after = PERIOD[-1] + timedelta(days=1)
    days = [
        day(PERIOD[0], Sleep="1h"),   # about the day before the period: dropped
        day(PERIOD[1], Sleep="7h"),   # about PERIOD[0]
        day(PERIOD[2], Sleep="8h"),   # about PERIOD[1]
        day(after, Sleep="6h"),       # about PERIOD[-1]: counts
    ]
    item = one(rh.habits([tracker("Sleep", "duration", yesterday=True)], days, PERIOD, "en"), "Sleep")
    assert item["days_with_value"] == 3
    assert item["value"] == pytest.approx(420.0)  # (7 + 8 + 6) h / 3, the 1h is not in the period
    assert item["missing"] == ["2026-03-25", "2026-03-26", "2026-03-27", "2026-03-28"]


def test_yesterday_unreadable_is_named_by_the_day_it_describes():
    days = [day(PERIOD[1], Sleep="<% tp.x %>"), day(PERIOD[2], Sleep="7h")]
    item = one(rh.habits([tracker("Sleep", "duration", yesterday=True)], days, PERIOD, "en"), "Sleep")
    assert item["unreadable"] == ["2026-03-23"]


def test_shift_yesterday_false_keeps_values_on_their_day():
    days = [day(PERIOD[0], Sleep="7h"), day(PERIOD[1], Sleep="8h")]
    item = one(rh.habits([tracker("Sleep", "duration", yesterday=True)], days, PERIOD, "en",
                         shift_yesterday=False), "Sleep")
    assert item["days_with_value"] == 2
    assert "2026-03-23" not in item["missing"]


def test_today_field_is_not_shifted():
    days = [day(PERIOD[0], Sport="true")]
    item = one(rh.habits([tracker("Sport", "boolean")], days, PERIOD, "en"), "Sport")
    assert item["days_with_value"] == 1
    assert "2026-03-23" not in item["missing"]


def test_a_day_outside_the_period_is_ignored_for_today_fields():
    days = [day(PERIOD[-1] + timedelta(days=1), Sport="true"), day(FIRST - timedelta(days=1), Sport="true")]
    assert rh.habits([tracker("Sport", "boolean")], days, PERIOD, "en") == []


# --- absence ---------------------------------------------------------------------------

def test_text_trackers_are_skipped():
    days = [day(PERIOD[0], Highlights="a fine day", Sport="true")]
    items = rh.habits([tracker("Highlights", "text"), tracker("Sport", "boolean")], days, PERIOD, "en")
    assert [i["tracker"] for i in items] == ["Sport"]


def test_no_trackers_gives_empty_result():
    assert rh.habits([], [day(PERIOD[0], Sport="true")], PERIOD, "en") == []


def test_tracker_without_a_value_on_any_day_is_absent():
    days = [day(PERIOD[0], Sport="true"), day(PERIOD[1])]
    items = rh.habits([tracker("Sport", "boolean"), tracker("Energy", "integer")], days, PERIOD, "en")
    assert [i["tracker"] for i in items] == ["Sport"]


def test_only_unreadable_values_give_no_item():
    days = [day(PERIOD[0], Energy="ja"), day(PERIOD[1], Energy="<% tp.x %>")]
    assert rh.habits([tracker("Energy", "integer")], days, PERIOD, "en") == []


def test_no_values_at_all_gives_empty_result():
    assert rh.habits([tracker("Sport", "boolean")], [day(PERIOD[0]), day(PERIOD[1])], PERIOD, "en") == []


def test_items_follow_tracker_order():
    days = [day(PERIOD[0], Sport="true", Energy="4", Sleep="7h")]
    defs = [tracker("Sleep", "duration"), tracker("Sport", "boolean"), tracker("Energy", "integer")]
    items = rh.habits(defs, days, PERIOD, "en")
    assert [i["tracker"] for i in items] == ["Sleep", "Sport", "Energy"]


def test_a_day_lists_dates_sorted_and_only_once():
    days = [day(PERIOD[2], Energy="x"), day(PERIOD[0], Energy="4"), day(PERIOD[2], Energy="y")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["unreadable"] == ["2026-03-25"]
    assert item["missing"] == sorted(item["missing"])


# --- rendered line (label table) -------------------------------------------------------

def test_english_line_for_a_count_names_missing_and_unreadable():
    days = [day(PERIOD[0], Sport="true"), day(PERIOD[1], Sport="7"), day(PERIOD[2], Sport="false")]
    item = one(rh.habits([tracker("Sport", "boolean")], days, PERIOD, "en"), "Sport")
    assert item["text"] == (
        "Sport: 1 of 2 days (7 days in the period; "
        "missing: 2026-03-26, 2026-03-27, 2026-03-28, 2026-03-29; unreadable: 2026-03-24)"
    )


def test_english_line_for_an_average_without_gaps():
    days = [day(d, Energy="4") for d in PERIOD]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["text"] == "Energy: average 4.0 over 7 days (7 days in the period)"


def test_german_line_uses_german_labels_and_decimal_comma():
    days = [day(PERIOD[0], Energy="3"), day(PERIOD[1], Energy="4")] + [day(d, Energy="4") for d in PERIOD[2:]]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "de"), "Energy")
    assert item["rendered"] == "3,9"
    assert item["text"] == "Energy: Durchschnitt 3,9 über 7 Tage (7 Tage im Zeitraum)"


def test_german_count_line_with_gaps():
    days = [day(PERIOD[0], Sport="ja"), day(PERIOD[1], Sport="nein"), day(PERIOD[2], Sport="7")]
    item = one(rh.habits([tracker("Sport", "boolean")], days, PERIOD, "de"), "Sport")
    assert item["text"] == (
        "Sport: 1 von 2 Tagen (7 Tage im Zeitraum; "
        "fehlt: 2026-03-26, 2026-03-27, 2026-03-28, 2026-03-29; unlesbar: 2026-03-25)"
    )


def test_duration_and_time_render_the_same_in_both_languages():
    days = [day(PERIOD[0], Sleep="7h30", WakeUp="06:45")]
    defs = [tracker("Sleep", "duration"), tracker("WakeUp", "time")]
    for lang in ("de", "en"):
        items = rh.habits(defs, days, PERIOD, lang)
        assert one(items, "Sleep")["rendered"] == "7h 30m"
        assert one(items, "WakeUp")["rendered"] == "06:45"


def test_other_language_falls_back_to_english():
    days = [day(PERIOD[0], Sport="true")]
    fr = one(rh.habits([tracker("Sport", "boolean")], days, PERIOD, "fr"), "Sport")
    en = one(rh.habits([tracker("Sport", "boolean")], days, PERIOD, "en"), "Sport")
    assert fr["text"] == en["text"]
    assert fr["text"].startswith("Sport: 1 of 1 days")


# --- tracker_defs from the config ------------------------------------------------------

def test_tracker_defs_reads_the_three_lists_in_order_with_the_yesterday_flag():
    config = {"trackers": {
        "daily_note_trackers": {
            "today_fields": [{"name": "Sport", "type": "boolean"}, {"name": "Energy", "type": "integer"}],
            "yesterday_fields": [{"name": "Sleep", "type": "duration"}],
        },
        "end_of_day_fields": {"fields": [{"name": "Highlights", "type": "text"}]},
    }}
    defs = rh.tracker_defs(config)
    assert [(d.name, d.type, d.yesterday) for d in defs] == [
        ("Sport", "boolean", False), ("Energy", "integer", False),
        ("Sleep", "duration", True), ("Highlights", "text", False),
    ]


def test_tracker_defs_without_trackers_is_empty():
    assert rh.tracker_defs({}) == []
    assert rh.tracker_defs({"trackers": {"daily_note_trackers": {"today_fields": "nope"}}}) == []
