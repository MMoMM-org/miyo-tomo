#!/usr/bin/env python3
# version: 0.2.0
"""test_review_mapping.py — lib.review_mapping: template analysis, off-limits, landing check
(spec 046 T1.2; PRD F2-AC3, F2-AC5, F2-AC11; SDD ADR-8, ADR-9, ADR-10, "Template analysis").

Covers:
- each left-out rule names its reason: templater, link, per-period-parent (a templater
  ancestor, the same heading under >= 3 parents, an empty container of such headings only),
  off-limits (heading only, with sub-sections), automatic (own body, empty container)
- first rule wins; flags mixed, container, under-own; cursor placeholders, callouts and
  comments are neutral; a `---` is own-writable
- a heading-looking line inside a `<%* ... %>` block or in the frontmatter is no heading;
  `%% fold %%` is kept verbatim; duplicates are keyed by (text, level, parent, occurrence)
- landing_off_limits: a named row, an ancestor with sub-sections, an ancestor without
- row ids s<n> kept per heading key, never reusing a number; dropped rows after a change
- outline / from_outline classify as analyse_template does (T2.2); a stored outline of another
  shape raises; landing names the heading whose body receives a before / under / end placement
- the offered / left-out sets of the five test-vault templates (structure only, no journal
  text) match the SDD's Template analysis example
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tomo" / "scripts"))

from lib import review_mapping as rm  # noqa: E402

AUTO, TPL, PPP, OFF = "automatic", "templater", "per-period-parent", "off-limits"
C, M, U = "container", "mixed", "under-own"


def fence(info: str, body: str = "x: 1") -> str:
    return f"```{info}\n{body}\n```"


def verdicts(text: str, off_limits=()) -> list[tuple]:
    return [(h.heading, h.reason, tuple(sorted(h.flags))) for h in rm.analyse_template(text, list(off_limits))]


def by_text(text: str, off_limits=()) -> dict:
    return {h.heading: h for h in rm.analyse_template(text, list(off_limits))}


def row(heading, level, parent=None, occurrence=1, with_subsections=False) -> dict:
    return {"heading": heading, "level": level, "parent": parent, "occurrence": occurrence,
            "with_subsections": with_subsections}


# --- structural fixtures of the test vault's templates (headings and line shapes only) -----

_HEAD = "<%*\nlet tw = 1\n-%>\n<% await tp.file.include(\"[[x_frontmatter]]\") -%>\nweek: <% tw %>\n---\n"
_DAY = ('### <%"["%>[<%tp.date.now("YYYY-MM-DD", -{n}, nw)%>|<%tp.date.now("YYYY-MM-DD ddd", -{n}, nw)%>]] \n')
_NAV = '<%"["%>[<%tp.date.now("YYYY-MM-DD", 0, tw)%>]] ==> <%"["%>[<%tp.date.now("YYYY-MM-DD", 6, tw)%>]] '
_META = "---\n> [!METADATA]-\n> - Week:: <%\"[\"%>[<% tw %>]]\n> - Year:: [[<% year %>]]\n"

WEEK_PRIVAT = (
    _HEAD + '# Weekly Review: <%"["%>[<% tw %>]]\n\n' + fence("toc") + "\n<% tp.file.cursor(1)%>\n"
    + fence("calendar-nav", "") + "\n\n> [!sun] Rise\n"
    "## Theme of the week\n\n> [!sparkles] Theme\n\n"
    "In <% tp.date.now(\"MMMM\") %>, words **`=this.month.Theme`**, words\n"
    "- words **`=this.last-week.to-improve`**\n\n"
    "### Get Started\n-  [ ] task\n-  [ ] task\n\n"
    "## Overview\n\n> [!recycle] callout\n\n"
    "### Habits\n\n" + fence("dataview") + "\n### Language Learning\n" + fence("dataviewjs") + "\n\n"
    "### Temperature\n" + fence("dataviewjs") + "\n\n### Energy and Sleep\n\n"
    + fence("tracker") + "\n" + fence("tracker") + " \n\n\n> [!activity] callout\n"
    "## Review of the Week\n\n### Notes Created This Week\n\n" + _NAV + "\n\n"
    + "".join(_DAY.format(n=n) + "#### Notes of the Day %% fold %%\n" + fence("quoth")
              + f"\n#### My final thoughts for that day\n- <% tp.file.cursor({n}) %>\n\n" for n in range(7, 0, -1))
    + "#### Review Check\n-  [ ] task\n\n> [!training] callout\n\n"
    "### Learnings of the Week\n\n" + fence("dataview") + "\n\nLearnedLog:: <%tp.file.cursor(8) %>\n\n"
    "### Reflections\n\n> [!award] Gratitude\n\n- _words_: `=this.days.gratitude`\n\n"
    "- **Gratitude**:: <% tp.file.cursor(9) %>\n\n-  [ ] task\n\n> [!connect] callout\n"
    "### In my own words\n<% tp.file.cursor(14) %>\n\n"
    "#### What Went Well This Week?\n<% tp.file.cursor(15) %>\n\n"
    "#### What Should I Start Doing?\n<% tp.file.cursor(16) %>\n\n"
    "#### What Should I Stop Doing?\n<% tp.file.cursor(17) %>\n\n"
    "#### What Should I Continue Doing?\n<% tp.file.cursor(18) %>\n\n"
    "### Check My Own Words\n- [ ] task\n\n> [!calendar] callout\n"
    "## Organisation\n\n### Planning\n\n- [ ] task\n\t- Tuesday::\n\t- Monday::\n\n" + fence("meta-bind-button") + "\n\n"
    "### Last Check\n" + fence("dataview", "TASK") + "\n\n\n> [!watch] ## Shut Down\n> \"quote\"\n\n"
    "> [!METADATA]-\n> - Week:: <%\"[\"%>[<% tw %>]]\n"
)

WEEK_WORK = (
    _HEAD + '# Weekly Review: <%"["%>[<% tw %>]]\n\n' + fence("toc") + "\n---\n<% tp.file.cursor(1)%>\n"
    "## Overview\n" + fence("calendar-nav", "") + "\n\n"
    "### Reporting\n\n" + fence("dataview") + "\n\n" + fence("meta-bind-button") + "\n\n"
    "### Working Times\n\n" + fence("meta-bind-button") + "\n\n"
    "### Get Started\n-  [ ] task\n\n### Notes Created This Week\n\n" + _NAV + "\n\n"
    + "".join(_DAY.format(n=n) + fence("quoth") + "\n\n" for n in range(7, 2, -1))
    + "### My final thoughts for that week\n- <% tp.file.cursor(2) %>\n\n#### Review Check\n-  [ ] task\n\n"
    "### Learnings of the Week\n\n" + fence("dataview") + "\n\nLearnedLog:: <%tp.file.cursor(8) %>\n\n"
    "### In my own words\n\n#### What Went Well This Week?\n<% tp.file.cursor(14) %>\n"
    "#### What Should I Start Doing?\n<% tp.file.cursor(15) %>\n"
    "#### What Should I Stop Doing?\n<% tp.file.cursor(16) %>\n"
    "#### What Should I Continue Doing?\n<% tp.file.cursor(17) %>\n\n"
    "### Check My Own Words\n- [ ]  task\n\n## Organisation\n\n### Planning\n\n-  [ ] task\n\n"
    "### Last Check\n" + fence("dataview", "TASK") + "\n\n### Shut Down\n\"words\"\n\n" + _META
)

_COMMENTS = "".join(f'- [[<% tp.date.weekday("YYYY-[W]ww", {n}, tm) %>]]\n'
                    f'\t- ![[<% tp.date.weekday("YYYY-[W]ww", {n}, tm) %>#In my own words]]\n' for n in (0, 7, 14))
_MONTH_META = ("---\n> [!METADATA]-\n> - Month:: [[<% tm %>]]\n> - Weeks:: <%* \nlet weekLinks = [];\n"
               "tR += weekLinks.join(\", \");\n%>\n> - Last Month:: [[<% pm %>]]\n")

MONTH_PRIVAT = (
    _HEAD.replace("week", "month") + '# Monthly Review: <%"["%>[<% tm %>]]\n' + fence("calendar-nav", "")
    + "\n\n> [!sun] Rise\n## Theme of the Month\n\n> [!connect] Yearly Theme\n\n"
    "[[<% year %>]]: *`=this.year.Theme`*\n\n> [!sparkles] Last\n\n`=this.last-month.desired-outcome`\n\n"
    "Theme:: <%tp.file.cursor(1)%>\n\n" + fence("meta-bind-button") + "\n\n> [!locate] callout\n"
    "## Outlook\n\n### Goals and Wishes\n\n"
    "#### Work\n<%tp.file.cursor(2)%>\n\n#### Contacts\n<%tp.file.cursor(3)%>\n\n"
    "#### Health\n<%tp.file.cursor(4)%>\n\n#### Spare Time\n<%tp.file.cursor(5)%>\n\n"
    "### I look forward to\n<%tp.file.cursor(6)%>\n\n### This will be challenging\n<%tp.file.cursor(7)%>\n\n"
    "> [!success] callout\n\n### ToDos for this month\n- [ ] <%tp.file.cursor(8)%>\n\n"
    "### Goals and Milestones\nWords?\n![[520 Goals & Milestones#Aktive Milestones]]\n\n![[520 Goals#Aktive Goals]]\n\n\n"
    "> [!recycle] callout\n## Overview\n<%tp.file.cursor(9)%>\n"
    "### Habits %% fold %%\n\n" + fence("dataview") + "\n### Language Learning %% fold %%\n\n" + fence("dataviewjs")
    + "\n### Body Values %% fold %%\n\n" + fence("tracker") + "\n\n### Temperature %% fold %%\n" + fence("dataviewjs")
    + "\n\n### Energy and Sleep\n\n" + fence("tracker") + "\n\n" + fence("tracker") + "\n\n"
    "### Learnings of the Month  %% fold %%\n\n" + fence("dataview") + "\n\n> [!activity] callout\n"
    "## Review of the month\n\n### Comments from this month\n" + _COMMENTS
    + "### In my own words\n\n<%tp.file.cursor(10)%>\n\n#### Things I did well this month\n<%tp.file.cursor(11)%>\n\n"
    "#### Things which were hard this month\n<%tp.file.cursor(12)%>\n\n\n"
    "### Reflections\n\n> [!recycle] Reflect\n\n- _Words **\"Gratitude\"** were_: `=this.weeks.gratitude`\n\n"
    "- **Gratitude**:: <%tp.file.cursor(13)%>\n\n\n> [!shipwheel] The Spiderweb\n> Rate the ten areas\n\n"
    "LN-Sinnerfüllung::\nLN-Mentale Gesundheit::\n\n" + fence("chartsview", "#----#\ntype: Radar") + "\n\n\n"
    "> [!orbit] callout\n\n### I like about myself\n\n"
    '!<%"["%>[<% tp.date.now("YYYY",0, title, "YYYY-MM") %> Assessment#Words, words]]\n\n\n'
    "### The following is good for me\n\n"
    '!<%"["%>[<% tp.date.now("YYYY",0, title, "YYYY-MM") %> Assessment#Words]]\n\n\n> [!calendar] callout\n\n'
    "## Plan\n\n" + fence("meta-bind-button") + "\n\n\n" + _MONTH_META
)

MONTH_WORK = (
    _HEAD.replace("week", "month") + '# Monthly Review: <%"["%>[<% tm %>]]\n' + fence("calendar-nav", "")
    + "\n\n## Planing\nWords?\n\n<%tp.file.cursor(0)%>\n\n\n## Overview\n\n### Reporting %% fold %%\n\n"
    + fence("dataview") + "\n\n### Learnings of the Month %% fold %%\n\n" + fence("dataview") + "\n\n"
    "##  Working Times\n\n<% await tp.file.include(\"[[i_timeTable]]\") %>\n\n## Review\n\n"
    "### Comments from this month\n" + _COMMENTS + "### In my own words\n\n<%tp.file.cursor(8)%>\n\n"
    "#### Things I did well this month\n<%tp.file.cursor(9)%>\n\n"
    "#### Things which were hard this month\n<%tp.file.cursor(10)%>\n\n"
    "## Plan\n\n" + fence("meta-bind-button") + "\n\n\n"
    "---\n> [!METADATA]-\n> - Month:: [[<% tm %>]]\n> - Weeks:: <%* for(;;) { %>[[<% year %>]]<%* } %>\n"
)

_HABIT = "### {name}\n\n```dynbedded\n[[Universal Trackers#{name}]]\n```\n"
_MONTH_HEAD = '#### <%tp.date.now("YYYY-MM", {o}, tq, "YYYY-[Q]Q")%>\n' \
              '!<%"["%>[<%tp.date.now("YYYY-MM", {o}, tq, "YYYY-[Q]Q")%>#In my own words]] \n- <% tp.file.cursor(1) %>\n\n'

QUARTER_PRIVAT = (
    "<%*\nlet tq = 1\n-%>\n<% await tp.file.include(\"[[x_frontmatter]]\") -%>\nquarter: <% tq %>\n"
    "<%*  \nfunction f(m) {\n## not a heading in the block\n}\ntR += \"journal-end-date: \" + lm;  \n%>  \n---\n"
    '# Quarterly Review: <%"["%>[<% tq %>]]\n' + fence("calendar-nav", "") + "\n\n" + fence("meta-bind-button")
    + "\n\n> [!recycle] callout\n## Review of Habits\n\n"
    + "".join(_HABIT.format(name=n) for n in ("Healthfood", "Sport", "Bewegungs Break", "Entspannung", "Alcohol"))
    + "### Junk Food\n\n``` dynbedded\n[[Universal Trackers#JunkFood]]\n```\n\n"
    "## Body Values\n\n" + fence("tracker") + "\n\n> [!shipwheel] callout\n## Web of Life\n\n" + fence("tracker")
    + "\n\n\n> [!recycle] Reflect\n## Notes Created This Quarter\n\n### Review of Monthly Reviews\n\n"
    '<%"["%>[<%tp.date.now("YYYY-MM", 0, tq)%>]] ==> <%"["%>[<% lm %>]] \n\n'
    + "".join(_MONTH_HEAD.format(o=o) for o in ("0", '"P+1M"', '"P+2M"'))
    + "### Review Of Weekly Reviews\n- Words:\n" + fence("dataview") + "\n\n"
    "#### What were the 3 most important lessons I learned\n\n1. <% tp.file.cursor(4) %>\n\n"
    "> [!activity] callout\n## Goals and Projects Review\n\n### Review Of Milestones\n\n" + fence("dataview")
    + "\n\n- Words\n- Words?\n\n- <% tp.file.cursor(5) %>\n\n### Review Of Projects\n\n" + fence("dataview")
    + "\n\n- Words\n\n- <% tp.file.cursor(6) %>\n\n## Burnout Reflexion\n\n" + fence("meta-bind-button")
    + '\n\n\n!<%"["%>[<% ty %> Burnout#Reflexion]]\n\n> [!orbit] callout\n'
    "## Bucket List\n> Words?\n![[Bucket List#Die Liste]]\n\n\n> [!success] callout\n"
    "## Conclusions\n\n### Start Stop Continue\n#### What should I start doing next quarter?\n<% tp.file.cursor(7) %>\n"
    "#### What should I stop doing next quarter?\n<% tp.file.cursor(8) %>\n"
    "#### What should I continue doing next quarter?\n<% tp.file.cursor(9) %>\n\n> [!calendar] callout\n"
    "### Setting New Goals\n- Words\n- Words\n"
)


def _o(heading, *flags):
    return (heading, None, tuple(sorted(flags)))


def _l(heading, reason):
    return (heading, reason, ())


_DAYS_PRIVAT = [v for n in range(7, 0, -1) for v in (
    _l(_DAY.format(n=n)[4:].strip(), TPL), _l("Notes of the Day %% fold %%", PPP),
    _l("My final thoughts for that day", PPP))]

EXPECTED = {
    "t_week_privat": [
        _o("Theme of the week"), _o("Get Started"), _l("Overview", AUTO), _l("Habits", AUTO),
        _l("Language Learning", AUTO), _l("Temperature", AUTO), _l("Energy and Sleep", AUTO),
        _o("Review of the Week", C), _l("Notes Created This Week", AUTO), *_DAYS_PRIVAT,
        _l("Review Check", PPP), _l("Learnings of the Week", AUTO), _o("Reflections", M),
        _o("In my own words", C), _o("What Went Well This Week?"), _o("What Should I Start Doing?"),
        _o("What Should I Stop Doing?"), _o("What Should I Continue Doing?"), _o("Check My Own Words"),
        _o("Organisation", C), _o("Planning", M), _l("Last Check", AUTO)],
    "t_week_work": [
        _l("Overview", AUTO), _l("Reporting", AUTO), _l("Working Times", AUTO), _o("Get Started"),
        _l("Notes Created This Week", AUTO), *[_l(_DAY.format(n=n)[4:].strip(), TPL) for n in range(7, 2, -1)],
        _o("My final thoughts for that week", C), _o("Review Check"), _l("Learnings of the Week", AUTO),
        _o("In my own words", C), _o("What Went Well This Week?"), _o("What Should I Start Doing?"),
        _o("What Should I Stop Doing?"), _o("What Should I Continue Doing?"), _o("Check My Own Words"),
        _o("Organisation", C), _o("Planning"), _l("Last Check", AUTO), _o("Shut Down")],
    "t_month_privat": [
        _l("Theme of the Month", AUTO), _o("Outlook", C), _o("Goals and Wishes", C), _o("Work"), _o("Contacts"),
        _o("Health"), _o("Spare Time"), _o("I look forward to"), _o("This will be challenging"),
        _o("ToDos for this month"), _o("Goals and Milestones", M), _l("Overview", AUTO),
        _l("Habits %% fold %%", AUTO), _l("Language Learning %% fold %%", AUTO), _l("Body Values %% fold %%", AUTO),
        _l("Temperature %% fold %%", AUTO), _l("Energy and Sleep", AUTO),
        _l("Learnings of the Month  %% fold %%", AUTO), _o("Review of the month", C),
        _l("Comments from this month", AUTO), _o("In my own words", C), _o("Things I did well this month"),
        _o("Things which were hard this month"), _o("Reflections", M), _l("I like about myself", AUTO),
        _l("The following is good for me", AUTO), _o("Plan", M)],
    "t_month_work": [
        _o("Planing"), _l("Overview", AUTO), _l("Reporting %% fold %%", AUTO),
        _l("Learnings of the Month %% fold %%", AUTO), _l("Working Times", AUTO), _o("Review", C),
        _l("Comments from this month", AUTO), _o("In my own words", C), _o("Things I did well this month"),
        _o("Things which were hard this month"), _o("Plan", M)],
    "t_quarter_privat": [
        _l("Review of Habits", AUTO), *[_l(n, AUTO) for n in (
            "Healthfood", "Sport", "Bewegungs Break", "Entspannung", "Alcohol", "Junk Food", "Body Values",
            "Web of Life")],
        _o("Notes Created This Quarter", C), _l("Review of Monthly Reviews", AUTO),
        *[_l(f'<%tp.date.now("YYYY-MM", {o}, tq, "YYYY-[Q]Q")%>', TPL) for o in ("0", '"P+1M"', '"P+2M"')],
        _o("Review Of Weekly Reviews", M), _o("What were the 3 most important lessons I learned"),
        _o("Goals and Projects Review", C), _o("Review Of Milestones", M), _o("Review Of Projects", M),
        _l("Burnout Reflexion", AUTO), _o("Bucket List", M), _o("Conclusions", C), _o("Start Stop Continue", C),
        _o("What should I start doing next quarter?"), _o("What should I stop doing next quarter?"),
        _o("What should I continue doing next quarter?"), _o("Setting New Goals")],
}
TEMPLATES = {"t_week_privat": WEEK_PRIVAT, "t_week_work": WEEK_WORK, "t_month_privat": MONTH_PRIVAT,
             "t_month_work": MONTH_WORK, "t_quarter_privat": QUARTER_PRIVAT}


@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_the_five_templates_give_the_sdd_sets(name: str) -> None:
    assert verdicts(TEMPLATES[name]) == EXPECTED[name]


def test_the_sdd_example_names_the_expected_sets_of_all_five_templates() -> None:
    sdd = (Path(__file__).resolve().parent.parent / "docs" / "XDD" / "specs" / "046-review-template-sections"
           / "solution.md").read_text(encoding="utf-8")
    for name, expected in EXPECTED.items():
        line = next((ln for ln in sdd.splitlines() if ln.startswith(f"- `{name}` — offered:")), None)
        assert line, name
        offered, left = line.split(" Left out: ")
        for heading, reason, flags in expected:
            if "<%" in heading:
                continue
            assert heading in (offered if reason is None else left), (name, heading)


# --- each rule names its reason -------------------------------------------------------------

def test_a_heading_with_templater_code_is_left_out_as_templater() -> None:
    assert verdicts("## Day <% tp.date.now() %>\nwords\n") == [_l("Day <% tp.date.now() %>", TPL)]


def test_a_heading_with_a_link_is_left_out_as_link() -> None:
    assert verdicts("## See [[Note]]\nwords\n") == [_l("See [[Note]]", "link")]


def test_templater_wins_over_link_first_rule_wins() -> None:
    assert verdicts('## <%"["%>[<% x %>]]\nwords\n')[0][1] == TPL


def test_a_heading_under_a_templater_heading_is_per_period() -> None:
    assert verdicts("## Day <% x %>\n### Thoughts\nwords\n")[1] == _l("Thoughts", PPP)


def test_the_same_heading_under_three_parents_is_per_period_two_are_not() -> None:
    three = "## Days\n" + "".join(f"### {d}\nwords\n#### Notes\nwords\n" for d in ("Mon", "Tue", "Wed"))
    two = "## Days\n" + "".join(f"### {d}\nwords\n#### Notes\nwords\n" for d in ("Mon", "Tue"))
    assert {r for h, r, _ in verdicts(three) if h == "Notes"} == {PPP}
    assert {r for h, r, _ in verdicts(two) if h == "Notes"} == {None}


def test_an_empty_container_of_per_period_headings_only_is_per_period() -> None:
    text = "## Days\n\n" + "".join(f"### {d}\n#### Notes\nwords\n" for d in ("Mon", "Tue", "Wed"))
    assert verdicts(text)[0] == _l("Days", PPP)
    assert verdicts(text + "### Notes of my own\nwords\n")[0] == _o("Days", C)


def test_a_section_of_automatic_lines_only_is_left_out_as_automatic() -> None:
    for body in (fence("dataview"), fence("tasks"), fence("toc"), "![[Note#Part]]", "Mood:: 3",
                 "`=this.mood`", "`BUTTON[next]`", '<%"["%>[<% tw %>]] ==> <%"["%>[<% nw %>]]',
                 "<%* \nlet x = 1\n%>"):
        assert verdicts(f"## S\n\n> [!info] callout\n{body}\n\n")[0] == _l("S", AUTO), body


def test_an_empty_container_whose_sub_headings_are_all_automatic_is_automatic() -> None:
    text = "## Overview\n> [!recycle] callout\n### A\n" + fence("dataview") + "\n### B\n" + fence("tracker") + "\n"
    assert verdicts(text)[0] == _l("Overview", AUTO)
    assert verdicts(text + "### C\nwords\n")[0] == _o("Overview", C)


def test_automatic_and_own_lines_make_a_mixed_heading_that_is_offered() -> None:
    assert verdicts("## S\n" + fence("dataview") + "\n- [ ] task\n") == [_o("S", M)]


def test_a_cursor_placeholder_a_callout_and_a_comment_count_as_empty() -> None:
    body = "<% tp.file.cursor(1) %>\n- <% tp.file.cursor(2) %>\n1. <%tp.file.cursor(3)%>\n- [ ] <% tp.file.cursor(4) %>\n" \
           "%% note %%\n> [!sun] Rise\n> words in the callout\n"
    assert verdicts("## S\n" + body) == [_o("S")]
    assert verdicts("## S\n" + body + "### T\nwords\n")[0] == _o("S", C)


def test_words_next_to_an_inline_query_and_a_plain_quote_and_a_rule_are_own_writable() -> None:
    for line in ("- _I was grateful for_: `=this.days.gratitude`", "> words", "---", "<% x %> words"):
        assert verdicts(f"## S\n{line}\n")[0] == _o("S"), line


def test_a_heading_looking_line_in_a_templater_block_or_the_frontmatter_is_no_heading() -> None:
    text = "---\ntitle: x\n## not a heading\n---\n<%*\n## not a heading either\n%>\n## Real\nwords\n"
    found = rm.analyse_template(text, [])
    assert [h.heading for h in found] == ["Real"]
    assert found[0].line == 8


def test_fold_suffix_and_double_spaces_are_kept_verbatim() -> None:
    assert [h.heading for h in rm.analyse_template("## Habits  %% fold %%\nwords\n", [])] == ["Habits  %% fold %%"]


def test_duplicates_are_keyed_by_text_level_parent_and_occurrence() -> None:
    text = ("## Review\n### In my own words\nw\n### In my own words\nw\n"
            "## In my own words\nw\n### Part\n#### In my own words\nw\n")
    keys = [h.key for h in rm.analyse_template(text, [])]
    words = [k for k in keys if k.heading == "In my own words"]
    assert words == [("In my own words", 3, "Review", 1), ("In my own words", 3, "Review", 2),
                     ("In my own words", 2, None, 1), ("In my own words", 4, "Part", 1)]
    assert rm.analyse_template(text, [])[1].as_dict()["heading_key"] == {
        "heading": "In my own words", "level": 3, "parent": "Review", "occurrence": 1}


def test_a_level_one_heading_is_never_offered_nor_a_parent() -> None:
    found = rm.analyse_template("# Title\n## Part\nwords\n", [])
    assert [(h.heading, h.parent) for h in found] == [("Part", None)]


# --- off-limits ---------------------------------------------------------------------------------

_OWN = WEEK_PRIVAT


def test_nothing_is_off_limits_without_a_row() -> None:
    assert OFF not in {h.reason for h in rm.analyse_template(_OWN, [])}


def test_off_limits_heading_only_leaves_its_children_offered_under_own() -> None:
    heads = by_text(_OWN, [row("In my own words", 3, "Review of the Week")])
    assert heads["In my own words"].reason == OFF
    child = heads["What Went Well This Week?"]
    assert (child.reason, child.flags) == (None, {U})


def test_off_limits_with_sub_sections_leaves_its_children_out() -> None:
    heads = by_text(_OWN, [row("In my own words", 3, "Review of the Week", with_subsections=True)])
    assert [heads[t].reason for t in ("In my own words", "What Went Well This Week?",
                                      "What Should I Continue Doing?")] == [OFF, OFF, OFF]
    assert heads["Check My Own Words"].reason is None


def test_a_row_names_only_its_own_identity() -> None:
    heads = by_text(_OWN, [row("In my own words", 2, None)])
    assert heads["In my own words"].reason is None


def test_structural_rules_win_over_off_limits() -> None:
    heads = by_text(_OWN, [row("Overview", 2, None), row("Review Check", 4, _DAY.format(n=1)[4:].strip())])
    assert (heads["Overview"].reason, heads["Review Check"].reason) == (OFF, PPP)


def test_landing_off_limits_named_row_ancestor_with_and_without_sub_sections() -> None:
    heads = by_text(_OWN)
    child = heads["What Went Well This Week?"]
    named = row("What Went Well This Week?", 4, "In my own words")
    with_subs = row("In my own words", 3, "Review of the Week", with_subsections=True)
    heading_only = row("In my own words", 3, "Review of the Week")
    assert rm.landing_off_limits(child, [named]) == named
    assert rm.landing_off_limits(child, [with_subs]) == with_subs
    assert rm.landing_off_limits(child, [heading_only]) is None
    assert rm.landing_off_limits(heads["In my own words"], [heading_only]) == heading_only
    assert rm.landing_off_limits(heads["Organisation"], [with_subs]) is None


# --- row ids and dropped ------------------------------------------------------------------------

def test_new_rows_get_the_next_number_above_every_known_id() -> None:
    previous = [{"id": "s1", **row("A", 2)}, {"id": "s3", **row("B", 2)}]
    rows = [row("A", 2), row("C", 2), row("D", 2)]
    assert [r["id"] for r in rm.assign_ids(rows, previous)] == ["s1", "s4", "s5"]


def test_a_corrected_row_keeps_its_id() -> None:
    rows = [{"id": "s2", **row("A", 2), "cap": 4}, row("B", 3, "A")]
    assert [r["id"] for r in rm.assign_ids(rows, [])] == ["s2", "s3"]
    assert "id" not in rows[1]


def test_dropped_names_previous_rows_the_new_template_lacks() -> None:
    heads = rm.analyse_template("## A\nw\n### B\nw\n", [])
    previous = [row("A", 2), row("B", 3, "A", occurrence=2), row("B", 3, None), row("Gone", 2)]
    assert rm.dropped(previous, heads) == [{"heading": "B", "level": 3, "parent": None},
                                           {"heading": "Gone", "level": 2, "parent": None}]


# --- the outline setup-input checks against, and the landing (spec 046 T2.2) --------------------

_OUTLINE = ("---\na: 1\n---\n# Title\n\n## Habits\n```dataview\nLIST\n```\n\n## <% tp.date.now() %>\n### Day\n\n"
            "## Mixed\nown words\n`= this.x`\n\n## Box\n### Inner\nw\n### Last\nw\n# Second\n## After\nw\n")


@pytest.mark.parametrize("off_limits", [(), (row("Inner", 3, "Box"),), (row("Box", 2, with_subsections=True),),
                                        (row("Habits", 2),)])
def test_from_outline_classifies_as_analyse_template_does(off_limits) -> None:
    stored = rm.outline(_OUTLINE)
    again = rm.from_outline(stored, list(off_limits))
    direct = rm.analyse_template(_OUTLINE, list(off_limits))
    assert [h.as_dict() for h in again] == [h.as_dict() for h in direct]
    assert [h.ancestors for h in again] == [h.ancestors for h in direct]


def test_the_outline_holds_the_structural_reason_only_and_the_level_1_lines() -> None:
    stored = rm.outline(_OUTLINE)
    reasons = {h["heading"]: h["reason"] for h in stored["headings"]}
    assert reasons["Habits"] is None, "automatic depends on the off-limits rows: not stored"
    assert reasons["<% tp.date.now() %>"] == TPL and reasons["Day"] == PPP
    assert stored["top"] == [{"heading": "Title", "line": 4}, {"heading": "Second", "line": 23}]


@pytest.mark.parametrize("broken", [None, [], {"headings": [{"heading": "A"}], "top": []},
                                    {"headings": [], "top": [{"line": "x"}]}])
def test_a_stored_outline_of_another_shape_raises_value_error(broken) -> None:
    with pytest.raises(ValueError):
        rm.from_outline(broken, [])


@pytest.mark.parametrize("heading,placement,expected", [
    ("Box", "before", "Mixed"),          # the body of the heading above
    ("Box", "under", "Box"),
    ("Box", "end", "Last"),              # the last heading inside the range, sub-sections included
    ("Inner", "end", "Inner"),
    ("Habits", "before", None),          # below a level-1 heading: never coverable
    ("After", "before", None),
    ("Second", "end", "After"),          # an anchor at level 1 ("Tomo Review" inside)
    ("Title", "end", "Last"),            # a level-1 range ends at the next level-1 heading
])
def test_landing_names_the_heading_whose_body_receives_the_lines(heading, placement, expected) -> None:
    stored = rm.outline(_OUTLINE)
    heads, top = rm.from_outline(stored, []), rm.outline_top(stored)
    line = next(e["line"] for e in [*stored["headings"], *stored["top"]] if e["heading"] == heading)
    found = rm.landing(heads, top, line, placement)
    assert (found.heading if found else None) == expected
