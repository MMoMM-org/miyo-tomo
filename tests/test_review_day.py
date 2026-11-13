#!/usr/bin/env python3
# version: 0.3.3
"""test_review_day.py — Behavioural tests for lib.review_day and the markdown
layer it applies, lib.review_md (spec 045 T3.2; PRD F3-AC1, F3-AC2, F3-AC3,
F3-AC4, F3-AC8; SDD "same-day reading of one daily").

Covers one day's reading:
- the quoth embed under the daily-changing `## [[DP-…|Dayplanner]]` heading is
  collected and read; tomorrow's planner link is ignored; the daily's own name
  is never re-read, even when the daily links itself
- a day token matches on digit boundaries: `6.3.2026` is not in `16.3.2026`;
  a navigation line with a bare other date stays; with a year-less `D.M`
  format only the token decides whether a link target is dated
- an other-day section of a linked note ends at a thematic break; the
  own-day prose behind the rule survives
- configured sections are kept with their subsections; "On This Day" is
  skipped and its embed not collected
- dataview/dataviewjs blocks, inline `= …` queries and quoth/dynbedded blocks
  are dropped, never executed
- the 5J note is read with its earlier-years subsections and embeds dropped
- `Name:: v` and `**Name**:: v` fields are parsed, a trailing link cut
- yesterday fields are separated and attribute_yesterday moves them to D-1
  (dropped before the period; the after-period daily lands on the last day)
- tasks carry their ✅ date across files; done_in_period counts by that date;
  task-note open tasks are "open today"; read_day never reads a task note
- a plain-text daily still has content; a skeleton-only daily has none
- a daily in which no configured heading is found is read whole under the
  `text` key (title heading, unconfigured headings), skip sections still
  excluded; one configured heading found → no fallback
- a same-day note loses its METADATA callout and its navigation-only lines
- a thematic break ends nothing by itself: prose after a `---` stays in its
  section or under `text`; only the trailing navigation block behind the
  rule (METADATA callout, callout of links, navigation-only lines) is
  dropped; a skipped section is cut at a rule
- a bare `-` field value passes through unchanged
- a day over max_chars_per_day is cut at a section boundary, partly_read;
  a day that fits the cap exactly is read whole
- done_in_period includes ticks dated exactly on the period's first and last day
- a missing or unreadable linked note is a problem of that day, the day read

All fixtures are synthetic: same structure as the owner's vault, no journal text.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import review_day as rd  # noqa: E402
from lib.review_pacer import ReviewPacer  # noqa: E402
from lib.review_reader import PacedReader  # noqa: E402
from review_fake_vault import ReviewFakeVault  # noqa: E402

DAY = date(2026, 3, 26)
DAILY_PATH = "Calendar/301 Daily/2026-03-26.md"

SETTINGS = {
    "sections": ["Habit", "5 Year Journal", "Start of the Day", "ToDos", "Daily Log", "End of the Day"],
    "skip_sections": ["On This Day... last year"],
    "task_notes": ["Efforts/500 OnGoing/Next Todos.md"],
    "max_chars_per_day": 12000,
    "date_format": "YYYY-MM-DD",
    "yesterday_fields": ["Entspannung", "Alcohol", "ToBed"],
}

DAILY = """---
day: 2026-03-26
locale: de
---
# Thursday 26 Mar 2026
<div data-timeline="85"></div>

```calendar-nav
```

## Wetter

> [!rainbow] Cloudy
> Temperature:: 4.8° C

## Habit
### Yesterday
- Entspannung:: false
- Alcohol:: true
- ToBed:: 23:30
### Today
- Sleep:: 06:45
- Sport:: false
- DayPlanner:: false [[DP-2026-03-27]]
- Japanese:: false[Manabi Vault](obsidian://open?vault=Manabi)

## 5 Year Journal

JahresJournal:: true [[5J-2026-03-26]]

## On This Day... last year - Wednesday
![[LastYear-2026-03-26#Daily Log]]

## Start of the Day

> [!sparkles] Improvements
**Yesterday I wanted to:** `=this.yesterday.to-improve`

- Desired Outcome:: `INPUT[text(class(large)):DP-2026-03-26#Theme]`

## [[DP-2026-03-26|Dayplanner]]

```quoth
path: [[DP-2026-03-26]]
ranges: after "# Schedule"
display: inline
```

## ToDos

- [x] Make Weekly Note [[2026-W12]] ✅ 2026-03-26
- [ ] Call the dentist

``` dataviewjs
let page = dv.page("2026-03-25");
dv.paragraph("# From Yesterday " + page["Next Up"]);
```

> [!rocket] Off you go...
> ## [[Next Todos#Up Next]]
>
> ```dynbedded
> path: [[Next Todos#Up Next]]
> ```

## Daily Log

- 08:08: Slept badly again, the alarm went off anyway.
- 13:30: Did the weekly review and went to the physio.
- 21:00: Linked today's own note [[2026-03-26]] by mistake.

## Language Learning

- Learned Words::

## End of the Day
> [!activity] Today I wanted to:
> `=this.desired-outcome`

- [x] **Anything to change for tomorrow?** ✅ 2026-03-27
- **DayJournal**:: true
- **DayEnergy**:: 3
- **Highlights**:: Finally did the weekly review

>[!EXAMPLE]- New Notes Today
>```dataview
>LIST
>WHERE file.cday = this.file.day
>```

---
> [!METADATA]-
> - Week:: [[2026-W13]]
---
"""

PLANNER = """---
Day: 2026-03-26
tags:
  - type/timeline/dayplanner
Theme: Physio and docs
---

# [[DP-2026-03-25|Yesterday]] <== [[2026-03-26|Thursday 26 Mar 2026]] ==> [[DP-2026-03-27|Tomorrow]]

## Theme
`INPUT[text(class(large)):Theme]`

# Schedule

- 06:00 - 06:30 Get up
- **12:00 - 12:30 Lunch**
- 15:00 - 16:00 Physio appointment
- [x] Book the next physio slot ✅ 2026-03-26
"""

JOURNAL = """---
day: 5J-2026-03-26
tags: type/timeline/5year
---
> [!METADATA]-
> - QuestionOfTheDay:: What do you like to do when you are alone?
---
# Thursday 26th Mar 2026
[[5J-2026-03-25]] <== 2026-03-26 ==> [[5J-2026-03-27]]
## Frage des Tages in den letzten Jahren

### 5J-2022-03-26
```quoth
path: [[5J-2022-03-26#What do you like to do when you are alone]]
show: title
```
### 5J-2025-03-26
```quoth
path: [[5J-2025-03-26#What do you like to do when you are alone]]
show: title
```

## What do you like to do when you are alone?

Reading and a long walk, mostly.

![[rain.png]]
"""

TASK_NOTE = """---
title: Next Todos
aliases:
  - Up Next
---
# [[Next Todos]]

## Up Next

- [x] Learn the cloud basics - [[2025-10]] ✅ 2025-11-27
- [x] Sort the photo archive ✅ 2026-03-25
- [ ] Define the values list - [[Assessment]]
- [ ] Update the goals note
"""

NOTES = {"DP-2026-03-26": PLANNER, "5J-2026-03-26": JOURNAL}


def reader(notes=None):
    """An in-test read_note: records what was asked, returns the dict's text or None."""
    store = NOTES if notes is None else notes
    asked: list[str] = []

    def read_note(target: str):
        asked.append(target)
        return store.get(target)

    read_note.asked = asked  # type: ignore[attr-defined]
    return read_note


def read(daily=DAILY, settings=SETTINGS, notes=None, day=DAY, path=DAILY_PATH):
    read_note = reader(notes)
    entry = rd.read_day(day, {path: daily}, settings, read_note)
    return entry, read_note.asked


# --- same-day links and embeds (SDD step 1) -------------------------------------------

def test_quoth_embed_under_dayplanner_heading_is_collected_and_read():
    entry, asked = read()
    assert "DP-2026-03-26" in asked
    kinds = {item["path"]: item["kind"] for item in entry["linked"]}
    assert kinds["DP-2026-03-26"] == "planner"
    assert "Physio appointment" in next(i["text"] for i in entry["linked"] if i["path"] == "DP-2026-03-26")


def test_tomorrows_planner_link_is_ignored():
    _, asked = read()
    assert "DP-2026-03-27" not in asked
    assert "DP-2026-03-25" not in asked


def test_the_dailys_own_name_and_the_task_note_are_never_read():
    """The daily links itself in the log ([[2026-03-26]]); it is never re-read and never a problem."""
    entry, asked = read(notes=dict(NOTES))
    assert "[[2026-03-26]]" in entry["sections"]["Daily Log"], "the self-link is in the kept text"
    assert "2026-03-26" not in asked
    assert "2026-03-26" not in [p["path"] for p in entry["problems"]]
    assert entry["problems"] == []
    assert "Next Todos" not in asked
    assert "Next Todos#Up Next" not in asked


def test_a_day_token_matches_on_digit_boundaries_only():
    """`D.M.YYYY`: day 6 is `6.3.2026`, which is a substring of `16.3.2026` and `26.3.2026`."""
    settings = dict(SETTINGS, sections=["Daily Log"], date_format="D.M.YYYY")
    daily = "## Daily Log\n- see [[Plan 6.3.2026]], [[Plan 16.3.2026]] and [[Plan 26.3.2026]]\n"
    notes = {"Plan 6.3.2026": "# six\n- walk\n", "Plan 16.3.2026": "# sixteen\n- run\n",
             "Plan 26.3.2026": "# twenty-six\n- swim\n"}
    entry, asked = read(daily=daily, settings=settings, notes=notes, day=date(2026, 3, 6),
                        path="Calendar/6.3.2026.md")
    assert asked == ["Plan 6.3.2026"]
    assert [i["path"] for i in entry["linked"]] == ["Plan 6.3.2026"]


def test_a_navigation_line_recognises_the_day_token_on_digit_boundaries():
    """In a linked note, `[[Plan 5.3.2026]] <== 6.3.2026 ==> [[Plan 7.3.2026]]` is navigation: the
    bare date is the day's own token. `[[Plan 5.3.2026]] <== 16.3.2026 ==> [[Plan 7.3.2026]]` is
    not: the bare `16.3.2026` is another date, so the line stays. `[[Plan 16.3.2026]] has the
    notes` stays for its words."""
    settings = dict(SETTINGS, sections=["Daily Log"], date_format="D.M.YYYY")
    note = ("# Plan\n[[Plan 5.3.2026]] <== 6.3.2026 ==> [[Plan 7.3.2026]]\n"
            "[[Plan 5.3.2026]] <== 16.3.2026 ==> [[Plan 7.3.2026]]\n"
            "[[Plan 16.3.2026]] has the notes\n- walk\n")
    entry, _ = read(daily="## Daily Log\n- see [[Plan 6.3.2026]]\n", settings=settings,
                    notes={"Plan 6.3.2026": note}, day=date(2026, 3, 6), path="Calendar/6.3.2026.md")
    text = entry["linked"][0]["text"]
    assert "<== 6.3.2026 ==>" not in text
    assert "[[Plan 5.3.2026]] <== 16.3.2026 ==> [[Plan 7.3.2026]]" in text
    assert "[[Plan 16.3.2026]] has the notes" in text
    assert "- walk" in text


def test_a_year_less_day_token_decides_a_navigation_line_on_digit_boundaries():
    """With `D.M` no target carries a year, so only the day token says whether a link is dated:
    `[[16.3]] | [[26.3]]` is not navigation for day 6 (`6.3` is inside both numbers) and stays;
    `[[6.3|Today]]` carries the token and goes."""
    settings = dict(SETTINGS, sections=["Daily Log"], date_format="D.M")
    note = "# Plan\n[[6.3|Today]]\n[[16.3]] | [[26.3]]\n- walk\n"
    entry, _ = read(daily="## Daily Log\n- see [[Plan 6.3]]\n", settings=settings,
                    notes={"Plan 6.3": note}, day=date(2026, 3, 6), path="Calendar/6.3.md")
    text = entry["linked"][0]["text"]
    assert "[[16.3]] | [[26.3]]" in text
    assert "[[6.3|Today]]" not in text
    assert "- walk" in text


def test_same_day_note_is_read_once_although_linked_twice():
    _, asked = read()
    assert asked.count("DP-2026-03-26") == 1


def test_a_target_named_like_a_task_note_is_not_read_per_day():
    settings = dict(SETTINGS, task_notes=["Efforts/Todos 2026-03-26.md"])
    daily = DAILY + "\n- see [[Todos 2026-03-26]]\n"
    _, asked = read(daily=daily, settings=settings)
    assert "Todos 2026-03-26" not in asked


def test_embed_in_skipped_section_is_not_collected():
    """The embed's target carries the day's own date, so only the skip filter keeps it out."""
    entry, asked = read()
    assert "LastYear-2026-03-26" not in asked
    assert not any(target.startswith("LastYear-") for target in asked)
    assert "LastYear-2026-03-26" not in entry["links"]


def test_skipped_subsection_inside_a_kept_section_is_neither_collected_nor_kept():
    """Only the skip filter stands here: the link is same-day and sits in a configured section."""
    daily = ("## Daily Log\n- a real line\n"
             "### On This Day... last year - Monday\n"
             "![[2025-03-26#Daily Log]]\n- last year's note [[Old-2026-03-26]]\n")
    entry, asked = read(daily=daily, notes={"Old-2026-03-26": "# old\n- text\n"})
    assert asked == []
    assert entry["sections"]["Daily Log"] == "- a real line"
    assert entry["links"] == []
    assert entry["linked"] == []


def test_date_format_decides_what_same_day_means():
    settings = dict(SETTINGS, date_format="DD.MM.YYYY")
    daily = "## Daily Log\n- a day with [[Plan 26.03.2026]] and [[DP-2026-03-26]]\n"
    _, asked = read(daily=daily, settings=dict(settings, sections=["Daily Log"]),
                    notes={"Plan 26.03.2026": "# Plan\n- walk\n"})
    assert asked == ["Plan 26.03.2026"]


# --- sections (SDD steps 2, 3) ---------------------------------------------------------

def test_configured_sections_kept_in_setup_order_with_subsections():
    entry, _ = read()
    assert list(entry["sections"]) == ["Habit", "5 Year Journal", "Start of the Day", "ToDos",
                                       "Daily Log", "End of the Day"]
    assert "### Yesterday" in entry["sections"]["Habit"]
    assert "Sleep:: 06:45" in entry["sections"]["Habit"]


def test_unconfigured_and_skipped_sections_are_absent():
    entry, _ = read()
    text = "\n".join(entry["sections"].values())
    assert "Temperature" not in text
    assert "Learned Words" not in text
    assert "On This Day" not in text
    assert "LastYear-2026-03-26" not in text
    assert "Week:: [[2026-W13]]" not in text


def test_dataview_blocks_and_inline_queries_are_dropped():
    entry, _ = read()
    text = "\n".join(entry["sections"].values())
    assert "dv.page" not in text
    assert "dataviewjs" not in text
    assert "WHERE file.cday" not in text
    assert "=this.yesterday.to-improve" not in text
    assert "=this.desired-outcome" not in text


def test_quoth_and_dynbedded_blocks_are_dropped_from_the_kept_text():
    entry, _ = read()
    text = "\n".join(entry["sections"].values())
    assert "ranges: after" not in text
    assert "dynbedded" not in text


def test_a_hash_inside_a_code_fence_is_not_a_heading():
    entry, _ = read()
    assert "From Yesterday" not in entry["sections"]
    assert "Daily Log" in entry["sections"]


def test_a_trailing_navigation_block_after_a_thematic_break_is_dropped():
    daily = "## Daily Log\n- the log line\n\n---\n> [!METADATA]-\n> - Week:: [[2026-W13]]\n> - Yesterday:: [[2026-03-25]]\n"
    entry, _ = read(daily=daily, notes={})
    assert entry["sections"]["Daily Log"] == "- the log line"
    assert entry["links"] == []
    assert "Week" not in entry["fields"]


def test_the_real_daily_footer_rule_callout_rule_is_dropped_whole():
    """The owner's daily ends `---`, METADATA callout, `---`: both rules and the callout go."""
    entry, _ = read()
    end = entry["sections"]["End of the Day"]
    assert "---" not in end and "METADATA" not in end and "2026-W13" not in end
    assert end.endswith("New Notes Today"), "the callout title before the footer is the last kept line"
    assert "2026-W13" not in entry["links"]


def test_prose_after_a_thematic_break_stays_in_its_section():
    daily = "## Daily Log\n- a\n---\n- b\n"
    entry, _ = read(daily=daily, notes={})
    assert entry["sections"]["Daily Log"] == "- a\n- b"


def test_prose_after_a_thematic_break_stays_under_text_in_the_fallback():
    entry, _ = read(daily="Slept.\n\n---\nmore text\n", notes={})
    text = entry["sections"]["text"]
    assert "Slept." in text and "more text" in text
    assert "---" not in text


def test_rule_then_navigation_then_prose_drops_only_the_navigation_line():
    """The first non-navigation line ends the block; a dated link line after it is the day's words."""
    daily = ("## Daily Log\n- a\n\n---\n[[2026-03-25]] | [[2026-03-27]]\nmore prose after the footer\n"
             "[[2026-03-24]] | [[2026-03-28]]\n")
    entry, _ = read(daily=daily, notes={})
    assert entry["sections"]["Daily Log"] == "- a\n\nmore prose after the footer\n[[2026-03-24]] | [[2026-03-28]]"
    assert entry["links"] == ["2026-03-24", "2026-03-28"]


def test_a_callout_of_links_only_after_a_rule_is_dropped_a_callout_with_words_stays():
    nav = "## Daily Log\n- a\n---\n> [!nav]-\n> [[Assessment]] · [[Goals]]\n"
    entry, _ = read(daily=nav, notes={})
    assert entry["sections"]["Daily Log"] == "- a"
    assert entry["links"] == []
    words = "## Daily Log\n- a\n---\n> [!note]\n> remember [[Assessment]]\n"
    entry, _ = read(daily=words, notes={})
    assert entry["sections"]["Daily Log"] == "- a\n> [!note]\n> remember [[Assessment]]"
    assert entry["links"] == ["Assessment"]


def test_a_skipped_section_is_cut_at_a_thematic_break_the_prose_after_it_is_the_days():
    """Skip ranges stop at a rule: the prose after it belongs to no section (read in the fallback,
    not swallowed into the skip); the embed before the rule is still neither collected nor kept."""
    daily = ("# 2026-03-26\n- the day's own line\n\n## On This Day... last year - Wednesday\n"
             "![[LastYear-2026-03-26#Daily Log]]\n- last year's line\n\n---\n"
             "Back to today: prose after the separator\n")
    entry, asked = read(daily=daily, notes={})
    assert asked == []
    text = entry["sections"]["text"]
    assert "the day's own line" in text and "Back to today" in text
    assert "last year's line" not in text and "LastYear" not in text
    assert entry["links"] == []


def test_daily_sections_key_is_accepted_as_alias():
    settings = {k: v for k, v in SETTINGS.items() if k != "sections"}
    settings["daily_sections"] = ["Daily Log"]
    entry, _ = read(settings=settings)
    assert list(entry["sections"]) == ["Daily Log"]


def test_links_are_the_targets_of_the_kept_text():
    entry, _ = read()
    assert "2026-W12" in entry["links"]
    assert "DP-2026-03-26" in entry["links"]
    assert "5J-2026-03-26" in entry["links"]
    assert "2026-W13" not in entry["links"]      # metadata callout, not a configured section
    assert "LastYear-2026-03-26" not in entry["links"]    # skipped section
    assert entry["links"].count("DP-2026-03-26") == 1


# --- the linked note (SDD step 4) ------------------------------------------------------

def test_journal_read_with_earlier_years_subsections_dropped():
    entry, _ = read()
    journal = next(i for i in entry["linked"] if i["path"] == "5J-2026-03-26")
    assert journal["kind"] == "journal"
    assert "Reading and a long walk" in journal["text"]
    assert "5J-2022-03-26" not in journal["text"]
    assert "5J-2025-03-26" not in journal["text"]
    assert "![[rain.png]]" not in journal["text"]


def test_planner_heading_naming_other_days_is_dropped_schedule_kept():
    entry, _ = read()
    planner = next(i for i in entry["linked"] if i["path"] == "DP-2026-03-26")
    assert "DP-2026-03-25" not in planner["text"]
    assert "INPUT[" not in planner["text"]
    assert "Get up" in planner["text"]


def test_journal_metadata_callout_and_navigation_line_are_dropped():
    entry, _ = read()
    journal = next(i for i in entry["linked"] if i["path"] == "5J-2026-03-26")
    assert "QuestionOfTheDay" not in journal["text"]
    assert "METADATA" not in journal["text"]
    assert "5J-2026-03-25" not in journal["text"]
    assert "5J-2026-03-27" not in journal["text"]
    assert "<==" not in journal["text"]
    assert "Reading and a long walk" in journal["text"]


def test_a_line_linking_an_undated_note_stays_in_a_linked_note():
    note = "# Plan\n[[DP-2026-03-25]] <== [[2026-03-26]] ==> [[DP-2026-03-27]]\n[[Assessment]]\n- walk\n"
    daily = "## Daily Log\n- see [[Plan-2026-03-26]]\n"
    entry, _ = read(daily=daily, notes={"Plan-2026-03-26": note})
    text = entry["linked"][0]["text"]
    assert "[[Assessment]]" in text
    assert "DP-2026-03-25" not in text and "DP-2026-03-27" not in text
    assert "- walk" in text


def test_an_other_day_section_in_a_linked_note_ends_at_a_thematic_break():
    """`## 2026-03-25` runs to the end of the note by heading level alone; the `---` after it cuts
    the other-day section, so the own-day prose behind the rule survives and only the section goes."""
    note = "# Plan\n## 2026-03-25\n- yesterday's line\n\n---\nown-day prose after the rule\n- walk\n"
    daily = "## Daily Log\n- see [[Plan-2026-03-26]]\n"
    entry, _ = read(daily=daily, notes={"Plan-2026-03-26": note})
    text = entry["linked"][0]["text"]
    assert "own-day prose after the rule" in text
    assert "- walk" in text
    assert "2026-03-25" not in text and "yesterday's line" not in text
    assert "---" not in text


def test_linked_note_fields_are_not_parsed_as_the_days_fields():
    entry, _ = read()
    assert "QuestionOfTheDay" not in entry["fields"]
    assert "Theme" not in entry["fields"]


def test_missing_linked_note_is_a_problem_of_that_day_and_the_day_still_read():
    entry, _ = read(notes={"DP-2026-03-26": PLANNER})
    assert {"kind": "linked-missing", "path": "5J-2026-03-26"} in entry["problems"]
    assert [i["path"] for i in entry["linked"]] == ["DP-2026-03-26"]
    assert entry["has_content"] is True
    assert "Daily Log" in entry["sections"]


def test_unreadable_linked_note_reported_the_same_way():
    """F3-AC8 at the day level: a linked note Kado cannot deliver (every read turned away, as production sees
    it) is a `linked-missing` problem of the day exactly like one that does not exist, and the day is still
    read. Run through the real reader, so the two are told apart where production tells them apart: only the
    unreadable one is in `not_read`."""
    planner = "Efforts/300 Planner/DP-2026-03-26.md"
    vault = ReviewFakeVault({DAILY_PATH: DAILY, planner: PLANNER})          # the 5J note does not exist
    vault.rate_limit(planner)                                               # the planner is never delivered
    with ReviewPacer(vault) as pacer:
        reader = PacedReader(vault, pacer)
        reader.finish()                                                     # end pass first: reads fail for good
        entry = rd.read_day(DAY, {DAILY_PATH: DAILY}, SETTINGS, reader.target)
    paths = sorted(p["path"] for p in entry["problems"] if p["kind"] == "linked-missing")
    assert paths == ["5J-2026-03-26", "DP-2026-03-26"]
    assert entry["linked"] == [] and entry["has_content"] is True and "Daily Log" in entry["sections"]
    assert reader.not_read == [planner], "only the unreadable note is not_read; the missing one is not"
    assert planner not in reader.missing


# --- fields (SDD step 5) ---------------------------------------------------------------

def test_plain_and_bold_fields_parsed_as_raw_strings():
    entry, _ = read()
    assert entry["fields"]["Sleep"] == "06:45"
    assert entry["fields"]["Sport"] == "false"
    assert entry["fields"]["DayJournal"] == "true"
    assert entry["fields"]["DayEnergy"] == "3"
    assert entry["fields"]["Highlights"] == "Finally did the weekly review"


def test_trailing_link_is_cut_from_a_field_value():
    entry, _ = read()
    assert entry["fields"]["DayPlanner"] == "false"
    assert entry["fields"]["Japanese"] == "false"
    assert entry["fields"]["JahresJournal"] == "true"


def test_a_bare_dash_value_passes_through_unchanged():
    """`Sleep:: -` is the owner's "nothing" mark; review_habits reads `-` as missing, so it must arrive raw."""
    from lib import review_habits as rh

    entry, _ = read(daily=DAILY.replace("Sleep:: 06:45", "Sleep:: -"))
    assert entry["fields"]["Sleep"] == "-"
    assert rh.parse_value("time", entry["fields"]["Sleep"]) is None, "review_habits reads the raw dash as missing"


def test_fields_outside_kept_sections_are_not_parsed():
    entry, _ = read()
    assert "Temperature" not in entry["fields"]
    assert "Week" not in entry["fields"]
    assert "Learned Words" not in entry["fields"]


def test_yesterday_fields_are_separated_from_todays():
    entry, _ = read()
    assert entry["previous_day_fields"] == {"Entspannung": "false", "Alcohol": "true", "ToBed": "23:30"}
    assert "Entspannung" not in entry["fields"]
    assert "ToBed" not in entry["fields"]


def test_yesterday_fields_function_reads_only_those_of_one_text():
    assert rd.yesterday_fields(DAILY, SETTINGS) == {"Entspannung": "false", "Alcohol": "true", "ToBed": "23:30"}
    assert rd.yesterday_fields("## Daily Log\n- nothing\n", SETTINGS) == {}


def test_attribute_yesterday_moves_fields_to_the_day_before():
    d24 = {"date": "2026-03-24", "fields": {"Sleep": "7h"}, "previous_day_fields": {"ToBed": "22:00"}}
    d25 = {"date": "2026-03-25", "fields": {"Sleep": "6h"}, "previous_day_fields": {"ToBed": "23:00"}}
    d26 = {"date": "2026-03-26", "fields": {"Sleep": "5h"}, "previous_day_fields": {"ToBed": "23:30"}}
    out = rd.attribute_yesterday([d26, d24, d25], {"ToBed": "00:15", "Alcohol": "false"})
    assert [e["date"] for e in out] == ["2026-03-24", "2026-03-25", "2026-03-26"]
    assert out[0]["fields"] == {"Sleep": "7h", "ToBed": "23:00"}
    assert out[1]["fields"] == {"Sleep": "6h", "ToBed": "23:30"}
    assert out[2]["fields"] == {"Sleep": "5h", "ToBed": "00:15", "Alcohol": "false"}
    assert all("previous_day_fields" not in e for e in out)
    assert d24["fields"] == {"Sleep": "7h"}, "input entries are not mutated"


def test_attribute_yesterday_drops_fields_of_the_day_before_the_period():
    d23 = {"date": "2026-03-23", "fields": {}, "previous_day_fields": {"ToBed": "21:00"}}
    out = rd.attribute_yesterday([d23], None)
    assert out == [{"date": "2026-03-23", "fields": {}}]
    assert all(e["date"] >= "2026-03-23" for e in out)


def test_attribute_yesterday_skips_a_gap_day():
    d23 = {"date": "2026-03-23", "fields": {}, "previous_day_fields": {}}
    d25 = {"date": "2026-03-25", "fields": {}, "previous_day_fields": {"ToBed": "22:30"}}
    out = rd.attribute_yesterday([d23, d25], None)
    assert out[0]["fields"] == {}
    assert out[1]["fields"] == {}


def test_attribute_yesterday_lands_on_the_last_duplicate_of_a_date():
    a = {"date": "2026-03-25", "dailies": ["a"], "fields": {}, "previous_day_fields": {}}
    b = {"date": "2026-03-25", "dailies": ["b"], "fields": {}, "previous_day_fields": {}}
    c = {"date": "2026-03-26", "fields": {}, "previous_day_fields": {"ToBed": "23:30"}}
    out = rd.attribute_yesterday([a, b, c], None)
    assert out[0]["fields"] == {}
    assert out[1]["dailies"] == ["b"] and out[1]["fields"] == {"ToBed": "23:30"}


def test_read_day_then_attribute_feeds_review_habits_as_is():
    from lib import review_habits as rh

    entry, _ = read()
    nxt, _ = read(daily=DAILY.replace("ToBed:: 23:30", "ToBed:: 00:30"), day=date(2026, 3, 27),
                  path="Calendar/301 Daily/2026-03-27.md")
    days = rd.attribute_yesterday([entry], rd.yesterday_fields(DAILY.replace("ToBed:: 23:30", "ToBed:: 00:30"),
                                                                SETTINGS))
    assert days[0]["fields"]["ToBed"] == "00:30"
    items = rh.habits([rh.TrackerDef("ToBed", "time"), rh.TrackerDef("DayEnergy", "integer")], days, [DAY], "en")
    by = {i["tracker"]: i for i in items}
    assert by["ToBed"]["rendered"] == "00:30" and by["ToBed"]["missing"] == []
    assert by["DayEnergy"]["value"] == 3.0
    assert nxt["previous_day_fields"]["ToBed"] == "00:30"


# --- tasks (SDD step 6) ----------------------------------------------------------------

def test_tasks_from_daily_and_linked_notes_carry_their_done_date_and_source():
    entry, _ = read()
    by_text = {t["text"]: t for t in entry["tasks"]}
    weekly = by_text["Make Weekly Note [[2026-W12]]"]
    assert weekly["done"] is True and weekly["done_date"] == "2026-03-26" and weekly["source"] == DAILY_PATH
    dentist = by_text["Call the dentist"]
    assert dentist["done"] is False and dentist["done_date"] is None
    physio = by_text["Book the next physio slot"]
    assert physio["done_date"] == "2026-03-26" and physio["source"] == "DP-2026-03-26"


def test_next_day_tick_keeps_its_own_date():
    entry, _ = read()
    nxt = next(t for t in entry["tasks"] if "Anything to change" in t["text"])
    assert nxt["done"] is True and nxt["done_date"] == "2026-03-27"
    assert "✅" not in nxt["text"]


@pytest.mark.parametrize("mark", ["✅", "✅\ufe0f"], ids=["plain-check", "with-variation-selector"])
def test_the_done_marker_is_read_with_or_without_the_emoji_variation_selector(mark):
    """U+FE0F after the check mark (a keyboard or editor adds it) is part of the Tasks done marker: the tick keeps
    its date and the marker, selector included, leaves the task text."""
    tasks = rd.task_note_tasks("n.md", f"- [x] Pay the invoice {mark} 2026-03-26\n- [x] Call back {mark}2026-03-27\n")
    assert [(t["text"], t["done"], t["done_date"]) for t in tasks] == [
        ("Pay the invoice", True, "2026-03-26"), ("Call back", True, "2026-03-27")]


def test_done_in_period_counts_by_tick_date_whichever_file_holds_it():
    entry, _ = read()
    tasks = entry["tasks"] + rd.task_note_tasks("Efforts/500 OnGoing/Next Todos.md", TASK_NOTE)
    done = rd.done_in_period(tasks, date(2026, 3, 23), date(2026, 3, 29))
    texts = sorted(t["text"] for t in done)
    assert texts == ["**Anything to change for tomorrow?**", "Book the next physio slot",
                     "Make Weekly Note [[2026-W12]]", "Sort the photo archive"]
    assert all(t["done_date"] for t in done)
    outside = rd.done_in_period(tasks, date(2026, 3, 23), date(2026, 3, 26))
    assert "**Anything to change for tomorrow?**" not in [t["text"] for t in outside]


def test_task_note_open_tasks_are_open_today():
    tasks = rd.task_note_tasks("Efforts/500 OnGoing/Next Todos.md", TASK_NOTE)
    open_ = [t for t in tasks if not t["done"]]
    assert [t["text"] for t in open_] == ["Define the values list - [[Assessment]]", "Update the goals note"]
    assert all(t["label"] == "open today" for t in open_)
    assert all(t["source"] == "Efforts/500 OnGoing/Next Todos.md" for t in tasks)
    assert all("label" not in t for t in tasks if t["done"])


def test_done_in_period_includes_the_first_and_the_last_day_of_the_period():
    tasks = rd.task_note_tasks("n.md", "- [x] before ✅ 2026-03-22\n- [x] first ✅ 2026-03-23\n"
                                       "- [x] inside ✅ 2026-03-26\n- [x] last ✅ 2026-03-29\n"
                                       "- [x] after ✅ 2026-03-30\n")
    done = rd.done_in_period(tasks, date(2026, 3, 23), date(2026, 3, 29))
    assert [t["text"] for t in done] == ["first", "inside", "last"]


def test_a_tick_without_a_date_never_counts_as_done_in_the_period():
    tasks = rd.task_note_tasks("n.md", "- [x] ticked without a date\n- [x] dated ✅ 2026-03-24\n")
    assert [t["text"] for t in rd.done_in_period(tasks, date(2026, 3, 23), date(2026, 3, 29))] == ["dated"]


# --- content (SDD steps 7, 8) -----------------------------------------------------------

def test_plain_text_daily_still_yields_content():
    daily = "Just a few lines today.\n\nWent for a walk, then read on the balcony.\n"
    entry, _ = read(daily=daily, settings=dict(SETTINGS, sections=["Daily Log"]))
    assert entry["has_content"] is True
    assert "Went for a walk" in "\n".join(entry["sections"].values())


PLAIN_TITLED = """# 2026-03-26

Slept in, then a long call with Anna about the move.

- Sleep:: 7h
- [x] Pay the deposit ✅ 2026-03-26
- [ ] Call the landlord

## Abends

Cooked, read [[Assessment]] again.

---
[[2026-03-25]] | [[2026-03-27]]
"""


def test_plain_daily_with_a_title_heading_is_read_whole_under_text():
    entry, _ = read(daily=PLAIN_TITLED, notes={})
    assert list(entry["sections"]) == ["text"]
    assert entry["has_content"] is True
    text = entry["sections"]["text"]
    assert "long call with Anna" in text and "Cooked, read" in text
    assert entry["fields"]["Sleep"] == "7h"
    assert sorted(t["text"] for t in entry["tasks"]) == ["Call the landlord", "Pay the deposit"]
    assert next(t for t in entry["tasks"] if t["text"] == "Pay the deposit")["done_date"] == "2026-03-26"
    assert entry["links"] == ["Assessment"]
    assert "2026-03-25" not in text, "the navigation block after the thematic break is not the day's words"


def test_plain_daily_with_only_unconfigured_headings_is_read_whole():
    daily = "## Morgens\n- up early, swim\n\n## Abends\n- Sport:: true\n"
    entry, _ = read(daily=daily, notes={})
    assert list(entry["sections"]) == ["text"]
    assert "up early, swim" in entry["sections"]["text"]
    assert entry["fields"]["Sport"] == "true"
    assert entry["has_content"] is True


def test_skip_section_inside_a_whole_read_daily_stays_excluded():
    daily = ("# 2026-03-26\n- the day's own line\n\n## On This Day... last year - Wednesday\n"
             "![[LastYear-2026-03-26#Daily Log]]\n- last year's line\n\n## Abends\n- evening line\n")
    entry, asked = read(daily=daily, notes={})
    assert asked == []
    text = entry["sections"]["text"]
    assert "the day's own line" in text and "evening line" in text
    assert "last year's line" not in text and "LastYear" not in text
    assert entry["links"] == []


def test_one_configured_section_found_means_no_fallback():
    daily = "# 2026-03-26\n- a free line outside any section\n\n## Daily Log\n- the log line\n\n## Abends\n- evening\n"
    entry, _ = read(daily=daily, notes={})
    assert list(entry["sections"]) == ["Daily Log"]
    assert entry["sections"]["Daily Log"] == "- the log line"
    assert "free line" not in "\n".join(entry["sections"].values())


def test_an_empty_configured_section_is_still_no_fallback():
    daily = "# 2026-03-26\n- a free line\n\n## Daily Log\n\n## Abends\n- evening\n"
    entry, _ = read(daily=daily, notes={})
    assert "text" not in entry["sections"]
    assert "free line" not in "\n".join(entry["sections"].values())
    assert entry["has_content"] is False


SKELETON = """---
day: 2026-03-26
---
# Thursday 26 Mar 2026
<div data-timeline="85"></div>

## Habit
### Yesterday
- Entspannung::
- ToBed::
### Today
- Sleep::
- Sport::

## 5 Year Journal

JahresJournal::

## Start of the Day

> [!sparkles] Improvements
**Yesterday I wanted to:** `=this.yesterday.to-improve`
- Desired Outcome:: `INPUT[text(class(large)):DP-2026-03-26#Theme]`

## ToDos

-

``` dataviewjs
dv.paragraph("x");
```

## Daily Log

-

## End of the Day
> [!activity] Today I wanted to:
> `=this.desired-outcome`

My WakeUpEnergy: `=this.WakeUpEnergy`

- **DayJournal**::
- **DayEnergy**:: <% tp.file.cursor() %>
- **Highlights**::

---
"""


def test_skeleton_only_daily_has_no_content():
    entry, _ = read(daily=SKELETON, notes={})
    assert entry["has_content"] is False
    # the unrun Templater tag stays raw so review_habits names the day unreadable (F8-AC2);
    # empty fields and the meta-bind INPUT placeholder are no value
    assert entry["fields"] == {"DayEnergy": "<% tp.file.cursor() %>"}
    assert entry["partly_read"] is False


def test_a_single_value_makes_content():
    entry, _ = read(daily=SKELETON.replace("- **DayEnergy**:: <% tp.file.cursor() %>", "- **DayEnergy**:: 4"),
                    notes={})
    assert entry["has_content"] is True


def test_a_day_over_the_cap_is_cut_at_a_section_boundary_and_partly_read():
    log = "## Daily Log\n" + "".join(f"- {i:02d}:00 a line of the log\n" for i in range(40))
    end = "## End of the Day\n- **Highlights**:: the one that matters\n"
    daily = "## Habit\n- Sleep:: 7h\n\n" + log + "\n" + end
    full, _ = read(daily=daily, notes={})
    assert full["partly_read"] is False
    cap = len(full["sections"]["Habit"]) + len(full["sections"]["Daily Log"]) // 2
    cut, _ = read(daily=daily, settings=dict(SETTINGS, max_chars_per_day=cap), notes={})
    assert cut["partly_read"] is True
    assert list(cut["sections"]) == ["Habit"]
    assert cut["sections"]["Habit"] == full["sections"]["Habit"]
    assert "Highlights" not in cut["fields"]


def test_a_day_that_fits_the_cap_exactly_is_read_whole():
    daily = "## Habit\n- Sleep:: 7h\n\n## Daily Log\n- the log line\n"
    full, _ = read(daily=daily, notes={})
    cap = sum(len(t) for t in full["sections"].values())
    entry, _ = read(daily=daily, settings=dict(SETTINGS, max_chars_per_day=cap), notes={})
    assert entry["partly_read"] is False
    assert entry["sections"] == full["sections"]


def test_the_first_section_alone_over_the_cap_is_kept_cut_hard():
    daily = "## Daily Log\n" + "- a line\n" * 100
    entry, _ = read(daily=daily, settings=dict(SETTINGS, max_chars_per_day=45), notes={})
    assert entry["partly_read"] is True
    assert len(entry["sections"]["Daily Log"]) <= 45
    assert entry["sections"]["Daily Log"] == "- a line\n" * 4 + "- a line", "cut on a line end, newline stripped"
    assert entry["has_content"] is True


def test_linked_notes_count_toward_the_cap_after_the_sections():
    cap = sum(len(t) for t in read()[0]["sections"].values()) + 10
    entry, asked = read(settings=dict(SETTINGS, max_chars_per_day=cap))
    assert entry["partly_read"] is True
    assert entry["linked"] == []
    assert len(asked) == 2, "the notes are still read; only their text is dropped"


# --- the entry shape --------------------------------------------------------------------

def test_entry_shape():
    entry, _ = read()
    assert set(entry) == {"date", "dailies", "sections", "fields", "previous_day_fields", "partly_read",
                          "has_content", "links", "problems", "tasks", "linked"}
    assert entry["date"] == "2026-03-26"
    assert entry["dailies"] == [DAILY_PATH]
    assert entry["problems"] == []


def test_two_dailies_for_one_day_are_both_read():
    other = "## Daily Log\n- the second copy says this\n- Sleep:: 5h\n"
    read_note = reader()
    entry = rd.read_day(DAY, {DAILY_PATH: DAILY, "Calendar/301 Daily/2026/2026-03-26.md": other},
                        SETTINGS, read_note)
    assert entry["dailies"] == [DAILY_PATH, "Calendar/301 Daily/2026/2026-03-26.md"]
    assert "the second copy says this" in entry["sections"]["Daily Log"]
    assert "13:30" in entry["sections"]["Daily Log"]
    assert entry["fields"]["Sleep"] == "5h", "the later daily's value wins, as review_habits keeps the later entry"
    assert read_note.asked.count("DP-2026-03-26") == 1


def test_no_daily_text_gives_an_empty_entry():
    entry = rd.read_day(DAY, {}, SETTINGS, reader({}))
    assert entry["dailies"] == [] and entry["sections"] == {} and entry["has_content"] is False


# --- settings helpers --------------------------------------------------------------------

def test_day_settings_from_setup_and_config():
    from lib.review_config import ISO, ReviewSetup

    setup = ReviewSetup(kind="week", folder="Calendar/302 Weekly/", format="GGGG-[W]WW", rule=ISO,
                        heading="Tomo Review", anchor="In my own words", placement="before", inbox="Inbox/",
                        daily_sections=["Habit", "Daily Log"], skip_sections=["On This Day"],
                        task_notes=["Efforts/500 OnGoing/Next Todos.md"], max_chars_per_day=9000)
    config = {"trackers": {"daily_note_trackers": {
        "today_fields": [{"name": "Sleep", "type": "text"}],
        "yesterday_fields": [{"name": "Entspannung", "type": "boolean"}, {"name": "ToBed", "type": "text"}],
    }}}
    settings = rd.day_settings(setup, config)
    assert settings == {
        "sections": ["Habit", "Daily Log"], "skip_sections": ["On This Day"],
        "task_notes": ["Efforts/500 OnGoing/Next Todos.md"], "max_chars_per_day": 9000,
        "date_format": "YYYY-MM-DD", "yesterday_fields": ["Entspannung", "ToBed"],
    }
    assert rd.yesterday_field_names({}) == []


def test_day_settings_takes_a_configured_daily_pattern():
    from lib.review_config import ISO, ReviewSetup

    setup = ReviewSetup(kind="week", folder="w/", format="GGGG-[W]WW", rule=ISO, heading="h", anchor="a",
                        placement="before", inbox="Inbox/")
    config = {"naming": {"calendar_patterns": {"daily": "DD.MM.YYYY"}}}
    assert rd.day_settings(setup, config)["date_format"] == "DD.MM.YYYY"
