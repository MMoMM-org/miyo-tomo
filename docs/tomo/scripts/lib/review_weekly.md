# WHY: lib/review_weekly.py

> Rationale for decisions in `tomo/scripts/lib/review_weekly.py`.
> The module owns the text side of `lib/review_period.py` (spec 045, T3.3;
> PRD F3-AC5; SDD Complex Logic "month reading", Implementation Gotchas):
> the daily name format, link targets and their comparison key, and the
> split of one weekly note into day blocks and week-level text. It makes no
> Kado call; `review_period` reads, this module parses.

## WHY a Second Module

WHY: Constitution L2 (dense files stay ~300–500 LOC) and the T3.3 brief
(`review_period.py` ≤ ~400 lines, split when weekly parsing pushes it over).
The first draft reached 516 lines; what moved is everything that is pure
text — testable without a vault, reusable by the review-document side later
(the same link rules decide what a proposal may cite). `review_period`
imports from here; nothing here imports `review_period`, so the dependency
runs one way.

## WHY the Daily Name Format Is Rendered Here

WHY: `lib/period.py` renders week and month names; a daily name
(`naming.calendar_patterns.daily`, default `YYYY-MM-DD`) is a third format
with `DD`, and `period.format_kind` refuses it. `daily_name` / `daily_date`
support exactly `YYYY`, `MM`, `DD` and `[literal]` — what a periodic daily
name needs — and `daily_date` is also how a weekly note's day heading is
keyed (`### [[2026-03-23|2026-03-23 Mon]]`): the first link in the heading
whose stem parses as a daily name gives the block's date. An impossible date
(`2026-13-05`) is no daily name, not an error.

## WHY Day Blocks End at the Next Heading of Their Level and Skip Sections

WHY: SDD Implementation Gotchas. In the owner's weekly notes each day is a
level-3 heading linking the daily, with `#### Notes of the Day` and
`#### My final thoughts` below it; the Sunday block also holds `#### Review
Check` (a task about the review itself, done the next week) and the note
continues with `## Organisation` (next week's planning, with day headings of
the following days). A block therefore ends at the next heading of its own
or a higher level, and sections whose heading starts with a skip prefix
(`DEFAULT_WEEKLY_SKIP`: `Review Check`, `Organisation`) are cut out of every
block and never start one — a day heading inside `Organisation` would
otherwise count planning as a day of the month. Blocks dated outside the
period are dropped (F3-AC5: "leaves out weekly content tied to a day outside
the month"). The skip list is a parameter with the module default, because
the setup has no weekly skip key; `/review setup` can grow one later without
touching the parser. Headings inside code fences are not headings (the
weekly's Dataview blocks print `#` lines).

Week-level text is the weekly note's `own_sections` (the hand-written
sections the setup already names: "In my own words", "Reflections") — the
Overview's Dataview sections and "Notes Created This Week" are queries, not
the user's words. The heading line itself is not part of a block or a
section: the date is the block's key, the section name its key, and the day
heading's link to the daily would otherwise make every weekly "mention"
every daily.

## WHY Link Targets Compare by the Stem's `path_key`

WHY: Obsidian links are case-insensitive and usually bare stems; a daily may
write `[[Alpha]]` where the weekly writes `[[Notes/alpha]]`. `link_key`
takes the last path component without `.md` through `vault_paths.path_key`
(NFC, casefold), the one comparison key for vault paths. Targets are cleaned
of `|alias` and `#heading` because Kado's `listNotes` `links` field carries
raw `metadataCache` link text, and a hand-written weekly does too. The first
spelling seen is reported, so the model cites what the user wrote.
