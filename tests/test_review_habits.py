#!/usr/bin/env python3
# version: 0.3.0
"""test_review_habits.py — Behavioural tests for lib.review_habits (spec 045 T3.5, PRD F8).

Covers the habits group as numbers:
- boolean trackers give a day count over the days with a value (F8-AC1); a
  bare `-` is a placeholder, listed as missing, never false
- integer, duration and time trackers give an average over the days with a
  value; duration is averaged in minutes and rendered back; time is averaged
  on the 24 h clock (circular mean: 23:30 and 00:30 give 00:00), and evenly
  spread times give "no clear average" with value None
- no input value makes habits() raise: digit runs of hundreds of characters
  (inf / nan / OverflowError in the old code) are unreadable, never a raise
- a minute part above 59 in an h+m duration is unreadable; 25:00 is a valid
  duration and an unreadable time; rendering rounds halves up
- missing days (no field, empty value) and unreadable values ("ja" for a
  number, "7" for a yes/no field, an unrun Templater `<% … %>`) are named
  by date and never counted as zero (F8-AC2)
- fields are taken as the reader attributed them: a value under date D
  counts for D for every tracker, yesterday_fields included — the reader
  owns the D-1 shift (SDD daily reading step 5), this module never shifts
- a date listed twice keeps the later entry's value
- text trackers are skipped; no trackers, or no value on any day → the item
  or the whole result is absent (F8-AC3)
- the rendered line follows the de/en label table, English otherwise
- tracker_defs reads the three tracker lists of the config in order

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


def tracker(name: str, type_: str) -> rh.TrackerDef:
    return rh.TrackerDef(name=name, type=type_)


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
    ("1", True), ("✅", True), ("[x]", True), ("[X]", True), (True, True),
    ("done", True), ("Done", True), ("y", True), ("Y", True), ("j", True), ("J", True),
    ("false", False), ("no", False), ("nein", False), ("0", False), ("❌", False),
    ("[ ]", False), ("[]", False), (False, False),
    ("n", False), ("N", False),
])
def test_boolean_spellings(raw, expected):
    items = rh.habits([tracker("Sport", "boolean")], [day(PERIOD[0], Sport=raw)], PERIOD, "en")
    item = one(items, "Sport")
    assert item["days_with_value"] == 1
    assert item["value"] == (1 if expected else 0)


def test_boolean_dash_is_a_placeholder_listed_as_missing_not_false():
    days = [day(PERIOD[0], Sport="-"), day(PERIOD[1], Sport="true"), day(PERIOD[2], Sport="false")]
    item = one(rh.habits([tracker("Sport", "boolean")], days, PERIOD, "en"), "Sport")
    assert "2026-03-23" in item["missing"]
    assert item["unreadable"] == []
    assert item["days_with_value"] == 2  # the "-" day is not in the denominator
    assert item["value"] == 1
    assert item["text"].startswith("Sport: 1 of 2 days")


def test_boolean_only_dashes_give_no_item():
    assert rh.habits([tracker("Sport", "boolean")], [day(PERIOD[0], Sport="-")], PERIOD, "en") == []


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


@pytest.mark.parametrize("raw", ["7h 90m", "7h90", "7:90", "7 h 60 min"])
def test_duration_minute_part_above_59_is_unreadable(raw):
    days = [day(PERIOD[0], Sleep=raw), day(PERIOD[1], Sleep="7h")]
    item = one(rh.habits([tracker("Sleep", "duration")], days, PERIOD, "en"), "Sleep")
    assert item["unreadable"] == ["2026-03-23"]
    assert item["value"] == pytest.approx(420)


def test_25_00_is_a_valid_duration_and_an_unreadable_time():
    days = [day(PERIOD[0], Sleep="25:00", ToBed="25:00"), day(PERIOD[1], ToBed="23:00")]
    items = rh.habits([tracker("Sleep", "duration"), tracker("ToBed", "time")], days, PERIOD, "en")
    sleep = one(items, "Sleep")
    assert sleep["unreadable"] == []
    assert sleep["value"] == pytest.approx(1500)  # 25 hours
    assert sleep["rendered"] == "25h 00m"
    bed = one(items, "ToBed")
    assert bed["unreadable"] == ["2026-03-23"]
    assert bed["days_with_value"] == 1


def test_rendering_rounds_a_half_minute_up_not_to_even():
    days = [day(PERIOD[0], Sleep="7h30", WakeUp="06:30"), day(PERIOD[1], Sleep="7h31", WakeUp="06:31")]
    items = rh.habits([tracker("Sleep", "duration"), tracker("WakeUp", "time")], days, PERIOD, "en")
    assert one(items, "Sleep")["value"] == pytest.approx(450.5)
    assert one(items, "Sleep")["rendered"] == "7h 31m"  # round() would give 450 → "7h 30m"
    assert one(items, "WakeUp")["value"] == pytest.approx(390.5)
    assert one(items, "WakeUp")["rendered"] == "06:31"


def test_time_averaged_in_minutes_since_midnight_rendered_hh_mm():
    days = [day(PERIOD[0], WakeUp="06:30"), day(PERIOD[1], WakeUp="7:30"), day(PERIOD[2], WakeUp="07:00:00")]
    item = one(rh.habits([tracker("WakeUp", "time")], days, PERIOD, "en"), "WakeUp")
    assert item["value"] == pytest.approx(420.0)
    assert item["rendered"] == "07:00"


def test_time_without_colon_or_out_of_range_is_unreadable():
    days = [day(PERIOD[0], WakeUp="seven"), day(PERIOD[1], WakeUp="25:00"), day(PERIOD[2], WakeUp="07:00"),
            day(PERIOD[3], WakeUp="07:60")]
    item = one(rh.habits([tracker("WakeUp", "time")], days, PERIOD, "en"), "WakeUp")
    assert item["unreadable"] == ["2026-03-23", "2026-03-24", "2026-03-26"]
    assert item["days_with_value"] == 1


# --- time averages on the 24 h clock (circular mean) ------------------------------------

@pytest.mark.parametrize("a,b,expected_minutes,expected_rendered", [
    ("23:30", "00:30", 0, "00:00"),      # bedtimes straddling midnight; arithmetic mean would say 12:00
    ("22:00", "02:00", 0, "00:00"),
    ("07:00", "08:00", 450, "07:30"),    # a wake-up pair stays an ordinary average
    ("23:00", "01:00", 0, "00:00"),
    ("23:45", "00:15", 0, "00:00"),
])
def test_time_average_is_circular_on_the_clock(a, b, expected_minutes, expected_rendered):
    days = [day(PERIOD[0], ToBed=a), day(PERIOD[1], ToBed=b)]
    item = one(rh.habits([tracker("ToBed", "time")], days, PERIOD, "en"), "ToBed")
    assert item["value"] == pytest.approx(expected_minutes, abs=1e-6)
    assert item["rendered"] == expected_rendered
    assert item["days_with_value"] == 2


def test_time_average_across_midnight_with_three_values():
    days = [day(PERIOD[0], ToBed="23:00"), day(PERIOD[1], ToBed="23:30"), day(PERIOD[2], ToBed="00:30")]
    item = one(rh.habits([tracker("ToBed", "time")], days, PERIOD, "en"), "ToBed")
    # points at -60, -30 and +30 minutes around midnight: the mean direction is ~-20 min → 23:40
    # (the vector mean is -20.07, not the arithmetic -20: the three points are not on a line)
    assert item["value"] == pytest.approx(1420.0, abs=0.2)
    assert item["rendered"] == "23:40"


@pytest.mark.parametrize("values", [
    ("00:00", "12:00"),
    ("06:00", "18:00"),
    ("00:00", "08:00", "16:00"),
])
def test_time_average_of_evenly_spread_values_has_no_clear_average(values):
    days = [day(PERIOD[i], ToBed=v) for i, v in enumerate(values)] + [day(PERIOD[5], ToBed="x")]
    item = one(rh.habits([tracker("ToBed", "time")], days, PERIOD, "en"), "ToBed")
    assert item["kind"] == "average"
    assert item["value"] is None
    assert item["rendered"] == "no clear average"
    assert item["days_with_value"] == len(values)
    assert item["unreadable"] == ["2026-03-28"]
    assert len(item["missing"]) == 7 - len(values) - 1
    assert item["text"].startswith(f"ToBed: no clear average over {len(values)} days (7 days in the period;")
    assert "unreadable: 2026-03-28" in item["text"]


def test_no_clear_average_in_german():
    days = [day(PERIOD[0], ToBed="00:00"), day(PERIOD[1], ToBed="12:00")]
    item = one(rh.habits([tracker("ToBed", "time")], days, PERIOD, "de"), "ToBed")
    assert item["value"] is None
    assert item["rendered"] == "kein klarer Durchschnitt"
    assert item["text"] == "ToBed: kein klarer Durchschnitt über 2 Tage (7 Tage im Zeitraum; fehlt: " + ", ".join(
        d.isoformat() for d in PERIOD[2:]) + ")"


def test_duration_average_is_arithmetic_not_circular():
    days = [day(PERIOD[0], Sleep="23:30"), day(PERIOD[1], Sleep="0:30")]
    item = one(rh.habits([tracker("Sleep", "duration")], days, PERIOD, "en"), "Sleep")
    assert item["value"] == pytest.approx(720.0)  # (1410 + 30) / 2 minutes
    assert item["rendered"] == "12h 00m"


# --- no value makes habits() raise ------------------------------------------------------

HUGE = "9" * 400  # float("9"*400) is inf; int("9"*400) is fine but int() of > 4300 digits raises


@pytest.mark.parametrize("type_,raw", [
    ("integer", HUGE),
    ("integer", "-" + HUGE),
    ("integer", HUGE + ".5"),
    ("integer", "1." + HUGE),
    ("duration", HUGE),              # plain number → hours
    ("duration", HUGE + "h"),
    ("duration", HUGE + "h 30m"),
    ("duration", "7h " + HUGE + "m"),
    ("duration", HUGE + "m"),
    ("duration", HUGE + ":30"),
    ("duration", "1." + HUGE + "h"),
    ("time", HUGE + ":00"),
    ("time", "07:" + HUGE),
    ("boolean", HUGE),
], ids=lambda v: v.replace(HUGE, "<400 digits>") if isinstance(v, str) else v)
def test_huge_digit_runs_are_unreadable_never_a_raise(type_, raw):
    good = {"integer": "4", "duration": "7h", "time": "07:00", "boolean": "true"}[type_]
    days = [day(PERIOD[0], X=raw), day(PERIOD[1], X=good)]
    item = one(rh.habits([tracker("X", type_)], days, PERIOD, "en"), "X")
    assert item["unreadable"] == ["2026-03-23"]
    assert item["days_with_value"] == 1
    assert item["value"] is not None
    assert "inf" not in item["text"] and "nan" not in item["text"]


def test_very_long_digit_runs_are_unreadable_never_a_raise():
    """Past int()'s 4300-digit limit `int()` raises ValueError in the old minute regexes."""
    longer = "1" * 5000
    for type_, raw in (("duration", "7h " + longer + "m"), ("duration", longer + "m"), ("integer", longer)):
        items = rh.habits([tracker("X", type_)], [day(PERIOD[0], X=raw)], PERIOD, "en")
        assert items == [], (type_, raw[:20])


def test_mixed_huge_positive_and_negative_are_unreadable_not_nan():
    days = [day(PERIOD[0], Energy="+" + HUGE), day(PERIOD[1], Energy="-" + HUGE), day(PERIOD[2], Energy="4")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["unreadable"] == ["2026-03-23", "2026-03-24"]
    assert item["value"] == pytest.approx(4.0)
    assert "nan" not in item["text"]


def test_native_non_finite_numbers_are_unreadable():
    days = [day(PERIOD[0], Energy=float("inf")), day(PERIOD[1], Energy=float("nan")), day(PERIOD[2], Energy=10**400)]
    assert rh.habits([tracker("Energy", "integer")], days, PERIOD, "en") == []


def test_integer_comma_and_dot_are_decimal_marks_not_thousands_separators():
    days = [day(PERIOD[0], Energy="1,000"), day(PERIOD[1], Energy="1.000")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["value"] == pytest.approx(1.0)


# --- fields are taken as the reader attributed them (the reader owns the D-1 shift) --

def test_yesterday_field_value_counts_for_the_day_it_is_listed_under():
    """A yesterday_fields tracker (the owner's Sleep) is configured as such, yet its value
    under date D counts for D: the reader already moved it to the day it describes."""
    config = {"trackers": {"daily_note_trackers": {
        "today_fields": [],
        "yesterday_fields": [{"name": "Sleep", "type": "duration"}],
    }}}
    after = PERIOD[-1] + timedelta(days=1)
    days = [
        day(PERIOD[0], Sleep="7h"),   # counts for PERIOD[0], not for the day before the period
        day(PERIOD[1], Sleep="8h"),   # counts for PERIOD[1]
        day(after, Sleep="6h"),       # outside the period: ignored, not moved onto PERIOD[-1]
    ]
    item = one(rh.habits(rh.tracker_defs(config), days, PERIOD, "en"), "Sleep")
    assert item["days_with_value"] == 2
    assert item["value"] == pytest.approx(450.0)  # (7 + 8) h / 2; the 6h after the period is not in it
    assert item["missing"] == ["2026-03-25", "2026-03-26", "2026-03-27", "2026-03-28", "2026-03-29"]


def test_unreadable_value_is_named_by_the_date_it_is_listed_under():
    config = {"trackers": {"daily_note_trackers": {
        "yesterday_fields": [{"name": "Sleep", "type": "duration"}],
    }}}
    days = [day(PERIOD[1], Sleep="<% tp.x %>"), day(PERIOD[2], Sleep="7h")]
    item = one(rh.habits(rh.tracker_defs(config), days, PERIOD, "en"), "Sleep")
    assert item["unreadable"] == ["2026-03-24"]


def test_habits_takes_no_shift_switch():
    days = [day(PERIOD[0], Sleep="7h")]
    with pytest.raises(TypeError):
        rh.habits([tracker("Sleep", "duration")], days, PERIOD, "en", shift_yesterday=False)


def test_a_day_outside_the_period_is_ignored():
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


def test_a_date_listed_twice_keeps_the_later_entry():
    days = [day(PERIOD[0], Energy="2"), day(PERIOD[1], Energy="4"), day(PERIOD[0], Energy="6")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["days_with_value"] == 2
    assert item["value"] == pytest.approx(5.0)  # (6 + 4) / 2: the later 6 replaced the 2, not (2 + 4 + 6) / 3


def test_a_later_unreadable_entry_replaces_an_earlier_readable_one():
    days = [day(PERIOD[0], Energy="4"), day(PERIOD[1], Energy="3"), day(PERIOD[0], Energy="ja")]
    item = one(rh.habits([tracker("Energy", "integer")], days, PERIOD, "en"), "Energy")
    assert item["unreadable"] == ["2026-03-23"]
    assert item["days_with_value"] == 1
    assert item["value"] == pytest.approx(3.0)


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

def test_tracker_defs_reads_the_three_lists_in_order():
    config = {"trackers": {
        "daily_note_trackers": {
            "today_fields": [{"name": "Sport", "type": "boolean"}, {"name": "Energy", "type": "integer"}],
            "yesterday_fields": [{"name": "Sleep", "type": "duration"}],
        },
        "end_of_day_fields": {"fields": [{"name": "Highlights", "type": "text"}]},
    }}
    defs = rh.tracker_defs(config)
    assert [(d.name, d.type) for d in defs] == [
        ("Sport", "boolean"), ("Energy", "integer"), ("Sleep", "duration"), ("Highlights", "text"),
    ]
    assert not hasattr(defs[2], "yesterday")


def test_tracker_defs_without_trackers_is_empty():
    assert rh.tracker_defs({}) == []
    assert rh.tracker_defs({"trackers": {"daily_note_trackers": {"today_fields": "nope"}}}) == []
