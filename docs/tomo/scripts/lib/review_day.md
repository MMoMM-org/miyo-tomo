# WHY: lib/review_day.py

> Rationale for decisions in `tomo/scripts/lib/review_day.py`.
> The module owns the reading of one day for `/review` (spec 045, T3.2; PRD
> F3-AC1, F3-AC2, F3-AC3, F3-AC4, F3-AC8; SDD "Example: same-day reading of
> one daily"): from the daily note(s) of a date and the setup's daily settings
> to one `ReadResult.days[]` entry — the kept sections, the fields, the
> tasks, the same-day linked notes, the link targets, the problems — plus
> the two helpers that move `yesterday_fields` onto the day they describe.
> No Kado, no model, no file I/O: every note text comes in through the
> arguments or the injected `read_note` callable. The markdown mechanics it
> applies — body and fences, section spans, thematic breaks and the
> navigation block behind them, query fences, navigation lines, the exact
> day-token test — live in `lib/review_md.py` (WHY in `review_md.md`); this
> module holds the settings-driven decisions.

## WHY the Reader Takes Texts and a Callable, Not a Client

`read_day(day, dailies, settings, read_note)` receives the daily texts the
period reader already fetched and a `read_note(target) -> text | None`
callable for the same-day notes it discovers. The period reader
(`review_period.py`, T3.3) owns Kado, the pacer and the not-read list, and
it resolves a link target to a vault path; this module never sees a client.
That keeps the whole day-reading rule testable with dict fixtures, and it
keeps one owner for every Kado call of the read (ADR-4: the pacer wraps one
client per run). `None` from the callable means "missing or unreadable" and
becomes a `problems` entry `{kind: "linked-missing", path}` for that day —
the day is still read; a missing planner must not lose the log (F3-AC8).

`read_note` is called with the link target *as written* in the daily
(`DP-2026-03-26`, never a folder path): the daily does not know where the
planner lives, and name resolution (Kado byName) is a Kado concern, so it
sits in the caller. The `linked[].path` and `problems[].path` values carry
that same target, so the report names what the daily named.

## WHY the Settings Are a Plain Dict

The seam fixed between T3.2 and T3.3 passes the daily settings as a dict so
the period reader can stub this module in its tests. The keys are the
`review.daily` config keys as `review_config` reads them — `sections`
(`daily_sections` is accepted as the `ReviewSetup` attribute name),
`skip_sections`, `task_notes`, `max_chars_per_day` — plus `date_format`
(how a day appears in a note name; default `YYYY-MM-DD`) and
`yesterday_fields` (the tracker names of
`trackers.daily_note_trackers.yesterday_fields`). `day_settings(setup,
config)` builds this dict from a `ReviewSetup` and the config, so the caller
never hand-composes it; `yesterday_field_names(config)` is the only reader
of the yesterday list by name — `review_config.tracker_types()` flattens the
three lists and so cannot tell a yesterday tracker from a today one.

## WHY Links Are Collected From the Whole Daily, Before the Section Filter

The owner's Dayplanner embed sits under `## [[DP-2026-03-26|Dayplanner]]`,
a heading whose text changes every day; no section list can name it (SDD
Data Storage Changes). So step 1 of the SDD algorithm scans the whole body
— wiki links, embeds, `quoth`/`dynbedded` `path:` lines inside code fences
— and only afterwards step 2 keeps the configured sections. The one
exception is a section matching `skip_sections` (prefix match on the heading
text): "On This Day... last year - Wednesday" embeds `![[2025-03-26#Daily
Log]]`, last year's log, and collecting that link would put another year
into the week.

A target is *same-day* when its name contains the day in `date_format` on
digit boundaries (`review_md.has_token`; a substring test read the 16th's
planner on the 6th under `D.M.YYYY`, WHY in `review_md.md`):
`DP-2026-03-26` and `5J-2026-03-26` are read, `DP-2026-03-27` in the
`DayPlanner::` field is ignored, and the daily's own name (`2026-03-26`) is
never re-read even when the daily links itself (the Today link of a
navigation callout, a self-reference in the log) — reading it would feed
the daily to the model twice and, with the planner's heading rule, drop
half of it as another day's. A target whose name matches one of `task_notes` is skipped
here even if it carried the date: a living task note is read once for the
period by the caller (`task_note_tasks`), not once per day. Anything else is
ignored (SDD step 1: "anything else is ignored").

`links` in the result are the targets of the *kept* sections plus the
same-day notes that were read, not of the whole body: they feed
`dailies_not_in_weekly`, and a link in a skipped or unconfigured section is
not what the day "held". The links *inside* a same-day note are not
collected (the planner's first line links yesterday's and tomorrow's
planner; one hop only).

## WHY a Section Spans Its Subsections

A kept section runs from its heading to the next heading of the same or a
higher level (`review_md.ranges`), so "Habit" carries its "### Yesterday"
and "### Today" subsections and their fields. Heading text is matched
exactly as the setup wrote it (the setup wizard copies heading texts;
`skip_sections` is a prefix match because the owner's skip heading ends in
the weekday name).

A thematic break (`---` on its own line, outside a fence) does **not**
close a kept section: F3-AC4's plain-vault user writes `---` as a
separator inside the day, and the words after it are still the day's. What
is dropped is the rule line and the *trailing navigation block* behind it
— the owner's daily ends with `---` and a `[!METADATA]` callout of
navigation links (week, month, quarter, year, yesterday), which by the
heading rule alone belonged to "End of the Day" and leaked its links into
`dailies_not_in_weekly` as "things the day held". The block rule
(`review_md.trailing_navigation`, WHY there) drops exactly that callout,
a callout of bare links or navigation-only lines, and keeps the first
other line and everything after it. The earlier version closed the
section at the rule, which stopped the leak and lost every plain-vault
line after a separator; the coordinator checked the real dailies — after
a `---` there is always a heading or the METADATA callout, never prose —
so the narrow rule covers both personas. A *skipped* section, by contrast,
is cut at a rule (`cut_at_rule=True`): swallowing the day's words into a
skip is silent loss, showing one extra navigation line is not (WHY
"a break does end a dropped section" in `review_md.md`).

## WHY a Daily Without a Configured Section Is Read Whole, Under `text`

F3-AC4 and the plain-vault persona: a daily that is only free text — no
heading at all, a title heading (`# 2026-03-26`) over free text, or
headings none of which the setup names — must still feed the review. The
section rule alone would keep nothing from such a day and report it as
empty, which the first review of this module found: the fallback fired
only when the daily had *no* heading, so a titled plain daily was read as
no content. The rule now is: when no configured section heading is found
in a daily, its whole body is read as one section keyed `text` — a
literal key, not the first configured name, so the model and the report
never attribute free text to a section the user did not write. Fields,
tasks and links are then taken from that text as from any kept section.

The fallback keeps the other reading rules: a `skip_sections` heading
inside the daily is still excluded with its body (it is other-day content
wherever it stands, cut at a `---` like every skip), query and embed
fences and inline queries are still dropped, and the trailing-block rule
still applies — the `---` and the navigation block behind it (a
`[[2026-03-25]] | [[2026-03-27]]` footer, a METADATA callout) are not read
as the day's words, while prose after a `---` is: `Slept.`, a rule, `more
text` reads as both lines. When one configured
section *is* found, there is no fallback: the rest of the daily stays
dropped as configured, even when that one section is empty — a skeleton
daily is still a skeleton.

## WHY Dataview, Inline Queries and Embed Blocks Are Dropped

F3-AC2: the content comes from the embedded note itself, never from a
plugin's rendering. `review_md.cleaned` removes `dataview`/`dataviewjs`
fences, inline `` `=…` ``/`` `$=…` `` queries and `quoth`/`dynbedded`
embed fences from every kept text (the embed targets were collected in
step 1 and are read as notes of their own); nothing is executed. WHY and
what stays in `review_md.md`.

## WHY a Linked Note Drops Sections That Name Another Date or Year

The 5 Year Journal entry `5J-2026-03-26` carries `### 5J-2022-03-26` …
`### 5J-2025-03-26` subsections with quoth embeds of the earlier years, and
the planner's first heading links yesterday's and tomorrow's planner. Inside
a same-day note, a section whose heading names a date or a four-digit year
other than the day's own is dropped, and every embed line (`![[…]]`) is
dropped too — the same-day note is read for what it says about this day,
and it is never followed further (one hop, SDD step 4). Fields are parsed
from the daily only: the linked notes' `::` lines are the weather callout
and the question of the day, not tracker values.

Two more things in a same-day note are navigation, not the day's words,
and are dropped from `linked[].text`: a `> [!METADATA]` callout (the whole
callout block — the journal's holds the question of the day and the
planner's its links) and a navigation-only line (`review_md.is_navigation`,
called here with the day and its token so the day's own date on the line
does not count as text). Without this rule yesterday's and tomorrow's note
names reached the model as content of the day and the review could name a
day outside the period from them. The other-day sections are cut at a
thematic break like a skipped section of the daily, and the trailing-block
rule runs here too, so a linked note's `---` footer is read like the
daily's. What makes a line navigation is `review_md.md`'s.

## WHY Fields Keep Their Raw Value, Minus a Trailing Link

`Name:: value` and `**Name**:: value` are parsed from the kept sections as
raw strings; `review_habits` is the only module that knows the tracker
types and interprets a value (WHY in `review_habits.md`). One
normalisation happens here: a trailing wiki link or markdown link is cut
from the value, because the owner writes `DayPlanner:: false
[[DP-2026-03-27]]` and `Japanese:: false[Manabi Vault](obsidian://…)` —
the link is navigation beside the value, and a boolean tracker reading
`false [[DP-2026-03-27]]` would be named unreadable on every day. The link
target still reaches the link collection of step 1. A meta-bind
`` `INPUT[…]` `` is no value either (the input renders a field stored
elsewhere) and a field without a value is not recorded — `review_habits`
reads an absent name as *missing*. A bare `-` (`Sleep:: -`, the owner's
"nothing today" mark) passes through as the raw value `-`; it is
`review_habits` that reads it as missing, so the reader must not drop or
rewrite it. An unrun Templater tag `<% … %>` is
kept raw on purpose: F8-AC2 wants that day named *unreadable*, which only
the habits module can decide, and it needs the raw text to do so. At the
same time the content test below treats `<% … %>` as skeleton, so a daily
whose only "value" is an unrun tag has no content — and both are right at
once because they answer different questions: `has_content` asks whether
the user wrote anything that day (an unrun tag is the template, not
writing), while the field asks what the tracker reads (an unrun tag is a
value the tracker cannot read, which is the F8-AC2 signal, not an absent
value, which would be silently *missing*). Dropping the tag from `fields`
would turn an unreadable day into a missing one; counting it as content
would turn a skeleton into a written day.

## WHY the Reader Owns the `yesterday_fields` Shift

A `yesterday_fields` value written in the daily of D describes D−1 (the
owner's `ToBed` of last night is written in the morning). SDD step 5 and the
coordinator decision in commit `ba97337f` give that shift exactly one owner:
this module. `read_day` sorts the parsed fields by name — the yesterday
names go into `previous_day_fields`, everything else into `fields` — and
`attribute_yesterday(entries, after_period)` moves every
`previous_day_fields` into the `fields` of the entry dated D−1, drops it
when D−1 is not in the list (the day before the period), puts
`after_period` — the `yesterday_fields(text, settings)` of the daily after
the period, read by the caller for those fields only — into the last
entry's `fields`, and removes `previous_day_fields` from every entry. The
result never carries an entry dated outside the period, and
`review_habits` takes the fields as given. A shifted value overrides a
same-named field of the target day: the yesterday list is the user's
statement that this name describes the day before, so the morning-after
entry is the authoritative one. When a date appears twice (duplicate
dailies), the shifted fields go to the last entry of that date, which is
the one `review_habits` keeps.

## WHY Tasks Carry Their ✅ Date and Nothing Decides the Period Here

`- [x] text ✅ YYYY-MM-DD` and `- [ ] text` are parsed from the kept daily
text and from the same-day notes into `{text, done, done_date, source}`;
the date is kept as read and the text loses only the ✅ suffix — its
markdown (bold, links) stays, because the model reads it as the user wrote
it and a source link inside the text is evidence. Whether a
task counts as done *in the period* is a question of the period, not of
the day: the owner ticks "Anything to change for tomorrow?" in the daily of
D with ✅ D+1 after midnight, and a task note's ticks fall on any day. So
`done_in_period(tasks, start, end)` is the one rule (✅ date inside the
period, whichever file holds the line; a tick without a date never counts)
and the caller applies it over all days and the task notes alike.
`task_note_tasks(path, text)` is the period-level parse of a living task
note: its open tasks are labelled `open today` — F3-AC3 says they are open
*now*, never open on a past day — and its done tasks carry their date for
the same period rule. `read_day` never reads a task note.

## WHY "Has Content" Means Text Beyond the Skeleton

F3-AC4 and F3-AC8: a plain-text daily must still yield content, and a daily
that is only the rendered template must not. The template's skeleton is
headings, field names without a value, empty list markers, label lines that
end in a colon (`**Yesterday I wanted to:**` once its inline query is
gone), callout title lines (`> [!sun] Rise....`), placeholders (`<% … %>`,
`` `INPUT[…]` ``), fence lines and whatever stands inside a fence, HTML
tags and horizontal rules. A kept section has content when one of its lines
is none of these and still carries a word — a log line, a field with a
value, a task. The rule is on lines, not on a diff against the template:
the reader does not have the template, and a template with Templater code
renders differently every day.

## WHY the Cap Cuts at a Section Boundary

`max_chars_per_day` bounds what one day feeds the model. The kept daily
sections come first in setup order, then the same-day notes; each whole
unit is kept while the running total stays within the cap, and the day is
marked `partly_read` at the first unit that does not fit. A cut inside a
section would hand the model half a sentence and a heading without its
body; a section boundary keeps every kept unit whole; a day whose units add up to
exactly the cap is read whole and is not `partly_read`. When the first
section alone exceeds the cap it is kept and cut hard at the cap (trailing
whitespace of the cut stripped, so the text does not end mid-indent), so a
day is never read as empty because of the cap.

## Output Shape

One `ReadResult.days[]` entry: `date` (ISO), `dailies` (the paths given),
`sections` (`{heading: text}` in setup order, or `{"text": …}` for a
daily in which no configured heading was found; two dailies for one date
are joined), `fields` (`{name: raw}`, today and end-of-day names),
`previous_day_fields` (`{name: raw}`, the yesterday names — removed again by
`attribute_yesterday`), `partly_read`, `has_content`, `links` (targets of
the kept text, in order, once each), `problems` (`[{kind:
"linked-missing", path}]`), `tasks` (`[{text, done, done_date, source}]`),
`linked` (`[{path, kind: planner|journal|other, text}]`). The daily's own
words sit in `sections`, `linked[].text` and `tasks[].text`; they go to
`read.json`, never to stdout or stderr.
