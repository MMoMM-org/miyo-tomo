# WHY: lib/review_habits.py

> Rationale for decisions in `tomo/scripts/lib/review_habits.py`.
> The module owns the habits group of a review (spec 045, T3.5, PRD F8): one
> pure function from the tracker definitions, the raw per-day field values of
> the period and the review language to the habit items — a day count per
> yes/no tracker, an average per number tracker — plus the English/German
> line each item is rendered as. No Kado, no model, no file I/O.

## WHY a Script Computes the Habits, Not the Model (ADR-12)

The owner's weekly note sums the habits with Dataview queries; a user without
Dataview has no sum at all. Counting days and averaging numbers is
arithmetic, and arithmetic done by the model is unverifiable: a hallucinated
"5 of 7 days" looks exactly like a counted one. So the habits group is
computed here, `proposals.json` never carries it (the schema rejects it) and
`review-doc.py` renders these items beside the model's groups. The rendered
line lives in this module too, so the number and its wording come from the
same place; a label table (de, en; English for every other language,
SDD System-Wide Patterns i18n) keeps the model out of the wording as well.

## WHY the Input Is the Tracker List Plus Raw Values

`review_day.py` parses `Name:: value` and `**Name**:: value` into
`ReadResult.days[].fields` as raw strings and does not interpret them: it
does not know the tracker types. This module is the only place that turns a
raw value into a boolean, a number, a duration or a time, so the type rules
below have one owner. The trackers come from the existing
`trackers.daily_note_trackers` (`today_fields`, `yesterday_fields`) and
`trackers.end_of_day_fields.fields` (SDD Data Storage Changes: F8 reuses
them, never a second tracker list). `review_config.tracker_types()` already
flattens the three lists to `{name: type}` in config order, and that is all
this module needs: which list a tracker came from does not matter here (next
section), so `tracker_defs(config)` is a thin wrapper over `tracker_types()`
and carries no `yesterday` flag. Config order is kept so the items appear in
the order the user wrote the setup.

`active: false` does not exclude a tracker: that switch exists for inbox
classification ("does Tomo propose this field"); a value that is in the daily
is the user's record and is summed like any other.

## WHY This Module Never Shifts `yesterday_fields`

A `yesterday_fields` value written in the daily of D describes D−1 (the
owner's `Sleep` of last night is written in the morning). That shift has
exactly one owner: the period reader, `review_day.py`. It attributes
yesterday fields to D−1 when it parses them, and it reads the daily of the
day *after* the period for its yesterday fields only, so the period's last
day is not always missing (SDD "Daily note reading", step 5; coordinator
decision in commit `ba97337f`). `ReadResult.days[].fields` therefore arrive
here already keyed by the day they describe, and this module takes them as
given: a value under date D counts for D, whichever tracker list the name
came from.

An earlier version shifted here too, behind a `shift_yesterday` flag with a
`yesterday` flag per tracker. Two modules that each know the rule is one
module too many: the default of the flag decided whether a value was moved
once or twice, and a double shift moves every value two days back and
silently misreports. Dropping the shift here, together with the flag and the
second read of the `yesterday_fields` list, leaves nothing to get wrong on
this side; a wrong attribution is now a reader bug, visible in the reader's
own tests.

## WHY a Later Daily for the Same Day Wins

`ReadResult.days[]` can carry the same date twice: the reader reports a
duplicate daily (flat folder and `<folder>/<YYYY>/`, SDD step 0) rather than
choosing. This module keeps the *last* entry's value for a date and ignores
the earlier ones. The reader lists the duplicate in its findings, so the user
is told; picking one value here keeps the item's arithmetic deterministic
instead of averaging a day with itself or naming it both missing and
unreadable. "Later wins" rather than "first wins" because the reader appends
in read order and the later file is the one it read last — the rule is
stated so a test can pin it, not because either order is more correct.

## WHY Missing and Unreadable Days Are Named, Never Zero (F8-AC2)

A day without the field, or with an empty value, is *missing*: the user did
not record it. A value that does not fit the type — "ja" for a number, "7"
for a yes/no field, an unrun Templater tag `<% … %>` left by a template that
was never executed — is *unreadable*: the user recorded something the type
rule cannot read. Both are listed by date in the item, and neither is counted
as zero or false: a zero would pull an average down and a false would lower
a day count, and the user could not tell a recorded zero from a gap.
`days_with_value` is therefore the denominator of every count and average.
The two lists are kept apart because the fixes differ: a missing day is a
gap in the journal, an unreadable one is a type mismatch the setup can
repair (SDD: the setup may propose `Sleep` `text` → `duration`).

## WHY These Value Rules

- **boolean**: true is `true`, `yes`, `ja`, `y`, `j`, `x`, `1`, `✅`,
  `done` or a ticked checkbox `[x]`; false is `false`, `no`, `nein`, `n`,
  `0`, `❌`, `-` or an unticked checkbox `[ ]` / `[]`; all case-insensitive.
  These are the spellings the trackers wizard and the owner's dailies use,
  plus the one-letter German/English shorthands and the `done` / `-` pair a
  hand-written journal falls into; anything else is unreadable.
- **integer**: an integer or a decimal (`7.5` or German `7,5`). The type says
  integer, but a `7.5` energy is still a number and refusing it would name
  half the owner's days unreadable; the average is rendered with one
  decimal either way.
- **duration**: `7h30`, `7h 30m`, `7:30`, `450m`, `90 min`, `1.5h`, and a
  plain number read as hours (the schema's scale hint for such fields is
  `hours`). Averaged in minutes, rendered back as `7h 40m`.
- **time**: `HH:mm` (`H:mm`, optional seconds), averaged in minutes since
  midnight and rendered as `HH:mm`. The mean is arithmetic, not circular: a
  wake-up time does not straddle midnight, and a bedtime tracker that does
  would average wrongly — a known limit, named here rather than guessed at.
- **text**: skipped (F8 is about numbers; a text field has no sum).

## WHY the Group Can Be Absent (F8-AC3)

A tracker without a value on any day gives no item (a "0 of 0 days" line
says nothing), and a vault without trackers or without any value gives an
empty list, which `review-doc.py` reads as "no habits group" — the group
heading is not rendered with a "nothing found" line like the model groups,
because the user never asked for habits they did not configure.

## Output Shape

Each item: `tracker`, `type`, `kind` (`count` for boolean, `average`
otherwise), `value` (the count, or the average: a number, minutes for
duration and time), `rendered` (the value as text), `days_with_value`,
`days_in_period`, `missing` and `unreadable` (ISO dates, sorted) and `text`
(the whole line in the review language). Dates are the only daily-note
content in the item; the values are the user's own numbers, and they go to
the document, never to stdout or stderr.
