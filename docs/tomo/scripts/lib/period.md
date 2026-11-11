# WHY: lib/period.py

> Rationale for decisions in `tomo/scripts/lib/period.py`.
> The module owns week and month arithmetic for `/review` (spec 045, T1.1):
> the week rule, the `Period` value, periodic name formats and the parsing of
> the `/review` argument into a request or an error object.

## WHY a Week Rule Instead of `date.isocalendar()`

The ISO calendar is one way to count weeks: Monday first, week 1 the week with
at least four days in the new year. Obsidian users set a first day of the week
and some count week 1 as the week containing 1 January. A review that numbers
weeks by ISO for such a user targets a note that does not exist and creates a
duplicate weekly note (PRD risk 1, F1-AC5, F2-AC9). `WeekRule(first_day,
min_days_in_first_week)` generalises the counting; `ISO == WeekRule(0, 4)` is an
invariant tested against `date.isocalendar()` for every day 2020-2030, so the
common case cannot drift from the stdlib.

`week_of` tries the week years `d.year + 1`, `d.year`, `d.year - 1` in that
order and takes the first whose week 1 starts on or before the date. The order
matters: the last days of December can already belong to week 1 of the next
year, and the first days of January to week 52/53 of the previous one.

`weeks_in(week_year)` is the distance between two consecutive week-1 starts
divided by seven, so a 53-week year falls out of the rule itself rather than
from a table of leap years.

## WHY Years Are Limited to `MIN_YEAR..MAX_YEAR` (0002..9998)

The argument and name regexes accept any four digits, so `0000-W13` and
`9999-W01` reach the arithmetic. `date()` holds years 1..9999 only, and a week
may start in the year before its week year or end in the year after it:
`weeks_in(9999)` needs the start of week 1 of 10000, and under a Sunday-first
rule week 1 of year 1 starts before 0001-01-01. Left alone these surface as a
`ValueError` or `OverflowError` out of `review-session.py` (planned, spec 045
Phase 2) instead of the JSON error object the skill expects (code review of
T1.1).

Two guards, so every entry point fails the same way: `weeks_in`, `week_of`,
`week_start` and `Period.month` refuse a year outside `MIN_YEAR..MAX_YEAR` with
`InvalidPeriod` up front, and `week_start_of_year` — the only place a date is
built from a week year — turns a `ValueError`/`OverflowError` from `date()`
into `InvalidPeriod` as well, for the one-year margin the guards leave open.
One year of margin on each side of `date()`'s range is enough because a week
spills at most six days past a year end.

For the user this means: `2026-W54`, `0000-W13` and `9999-W01` are all
`invalid-period` — the first with the last week of the named year as the
example, the other two with the supported range in `expected` and the last
finished period as the example (no week of year 0 could be offered). On the
`@` path an unrepresentable year behaves like every other name that does not
fit the format: `parse_name` returns None and the error is `not-periodic-note`,
because the user pointed at a note, not at a period, and the note's name is
what does not denote one.

`today` is taken from the clock by the caller and must itself lie in the
range; the lib does not guard it.

## WHY `Period` Carries Its Dates and No Rule

A `Period` is a value: kind, year, number, first and last day. Two weeks with
the same number under different rules differ in their dates, so equality
compares them correctly without storing the rule. The rule is needed only to
build a week (`Period.week(year, number, rule)`) and to enumerate the weeks
overlapping a month (`weeks_overlapping(rule)`); rendering and `note_paths`
take their numbers from the period itself. That is why `note_paths` has no
rule parameter although the SDD sketch listed one: an unused argument invites
a caller to pass the wrong rule and believe it mattered.

`name` is the canonical form (`2026-W13`, `2026-03`) used by stems, error
messages and the `request.period` field, independent of the user's name
format. The vault note name is rendered separately from the configured format.

## WHY `is_finished` Is `end < today`

A period that ends today is still running until midnight: the day's daily note
is being written. Reviewing it would read a half day and the next `/review`
would find the review already written (F2-AC6).

## WHY Note Paths Are Flat, Then the Year Folder

Periodic Notes and Calendar users keep weekly notes either directly in the
folder or in a per-year subfolder. Both are probed, flat first. For weeks the
subfolder is the week year (`2026-W53` lives in `2026/` although it ends on
2027-01-03); for months the calendar year. Guessing the calendar year for
weeks would miss exactly the week-53 note (F2-AC9).

## WHY Upper-Case Week Tokens Are ISO and Lower-Case Follow the Rule

Moment's `GGGG`/`WW` are ISO week year and week; `gggg`/`ww` are the locale
week. The Periodic Notes plugin uses the same letters. Rendering `GGGG-[W]WW`
therefore takes the ISO week of the period's first day, whatever the
configured rule, and `gggg-[W]ww` the period's own numbers. Under the ISO rule
both agree. Under another rule they do not, so `check_format` refuses
upper-case week tokens unless the rule is ISO (`iso-tokens-need-iso-rule`),
and refuses a format mixing both cases (`mixed-week-tokens`): a name that
numbers the week by ISO while its days follow a Sunday-first rule would
target a note whose days are not the ones reviewed.

## WHY `YYYY` With a Week Token Is Refused With a Dated Example

`YYYY-[W]WW` names 2027-01-01 as `2027-W53`, but that day belongs to ISO
week 2026-W53. The owner's monthly template carries exactly this bug (SDD
Known Technical Issues). The refusal names the first year-end date after
today's year where the calendar year and the week year differ, the wrong name
and the right one, so the user sees why the format cannot be saved rather
than a rule about token letters (SDD walkthrough row 2027-01-01). The date is
searched from 25 December to 7 January of the following year under the
configured rule, because under a Sunday-first one-day rule the mismatch sits
in December (2026-12-27 is week 1 of 2027), not in January.

## WHY Literals With `/`, `\` or `..` Are Refused

A name format is user configuration that ends up in a path under the
periodic-note folder and in the inbox. A literal `/`, `\` or `..` would let a
name leave its folder. The whole format string is checked, bracketed or not,
because no token contains those characters and a bare `/` is a literal in
Moment anyway (`unsafe-format`).

## WHY `parse_name` Returns None and `Period.week` Raises

`parse_name` answers "does this note name fit the format?" for the `@` path
and the setup's match preview over hundreds of names; a non-fitting name is
the normal case there. `Period.week`/`Period.month` guard the arithmetic and
raise `InvalidPeriod` on a week or month number outside the year, so a
`2026-W54` typed by the user or found in a note name becomes an error object
with an example instead of a date 7 days past the year's end.

## WHY Argument Parsing Returns an Object Instead of Raising

`review-session.py start` (planned, spec 045 Phase 2) prints one JSON object
and exits 0 for every outcome the skill can act on (SDD Internal API Changes). `parse_args` returns either a
`Request` or a `RequestError` whose `to_dict()` is that JSON. `today` is a
required keyword so a test can fix the calendar; the lib never calls
`date.today()` itself.

The grammar is deliberately small: empty, `week`, `month`, `setup`, a period
name with or without year (`2026-W13`, `W13`, `2026-03`, `M03`), an optional
kind word before a period name, and `@<path>`. A kind word in front of a period
of the other kind (`month 2026-W13`) is an `invalid-period`, not silently
reinterpreted (F2-AC7). Everything else is `unknown-argument` with the whole
grammar as `expected`.

The words `week`, `month` and `setup` are matched case-insensitively (`Setup`,
`Month 2026-03`), as `W13`/`w13` and `M03`/`m03` already were: a capitalised
word at the start of a chat message is the normal case, and refusing `Setup`
with the whole grammar as the answer would tell the user nothing they could
act on.

The `example` of an error is always a period the user could type and have
accepted: for an out-of-range week of a named year the last week of that year
(`2025-W53` → `2025-W52`, SDD walkthrough), otherwise the last finished period
of the expected kind.

## WHY a Missing Year Walks Back to the Latest Finished Period

`W13` means "the most recent week 13 that is over" (F2-AC4). Week 53 exists
only in some years, so the walk back can cross several years (`W53` on
2026-11-11 is `2020-W53`); the search stops after 60 years and reports
`invalid-period` if no year had that week.

## WHY `@<path>` Uses the Name Only

The picker hands over a vault path. Only the stem decides whether the note is a
weekly or monthly note: it is matched against the configured week format and
then the month format. The folder is not compared because a user may keep an
old year's notes elsewhere, and the setup has already told the reader where to
look (F2-AC3, F2-AC5). `[[...]]` and `.md` are stripped so a pasted link works
too. A name that fits neither format is `not-periodic-note` with both formats
in `expected`.

## WHY an Unfinished Period Is Checked Last

Validity (does the week exist?) comes before finishedness (is it over?), so
`2026-W54` is `invalid-period` even though it would also be unfinished. The
unfinished error carries `last_finished` as its own field as well as in
`example`, so the skill can name it without parsing the example (F2-AC6).
