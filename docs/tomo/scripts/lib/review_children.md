# WHY: lib/review_children.py

> Rationale for decisions in `tomo/scripts/lib/review_children.py`.
> The module owns the child-review notes of a period read (spec 046, T3.2;
> ADR-6; PRD F6-AC4, F6-AC5; SDD Complex Logic "Quarter marks"): finding the
> weekly notes of the weeks a month or quarter overlaps and the monthly notes
> of a quarter's months in their folder listing, reading and splitting them,
> the per-note report rows and the `<label>_status` of a level. Which levels
> a period reads, and which one it marks against, is `lib/review_period.py`'s
> `CHILD` table; reaching Kado is `lib/review_reader.py`'s.

## WHY a Module of Its Own

WHY: ADR-6 and the plan's line limit. Spec 045 read one child level (the
weekly notes of a month) inside `review_period.py`, which then stood at 421
of its 450 lines. A quarter reads two levels (weekly notes as sources,
monthly notes with marks), and writing the second as a copy of the first
would have pushed the file over its limit and doubled the finding, reading
and status logic. One `ChildNotes` value (kind, folder, name format, own
sections) describes a level; the same four functions (`find`, `prefetch`,
`read`, `status`) serve both, so a weekly note of a month and a monthly note
of a quarter are found, read, reported and statused by one code path.

## WHY Entries and Rows Are Keyed by the Child's Kind

WHY: the month's keys stay (ADR-6, CON-2). A month's weekly entries and
report rows carried `week: <name>` since spec 045, and the golden test pins
them. The kind constants are the key words (`WEEK = "week"`, `MONTH =
"month"`), so a weekly row is `{week, path, state}` and a monthly row is
`{month, path, state}` without a mapping table, and `review_period` finds a
day's child note by `entry[kind]` against `Period.containing(kind, day)`.
The status and list names come from `review_config.GRANULARITY` (`weekly`,
`monthly`): `weekly_status` / `weekly_notes` stay, the quarter adds
`monthly_status` / `monthly_notes`, and the `kado_empty` name of a level is
its label.

A monthly entry's own-section text is `month_text`, not `week_text`: a
model reading `read.json` should not be told a monthly review is a week.
`review_weekly.weekly_content` takes the key as `text_key` (default
`week_text`), so the split itself is the weekly note's — see
`review_weekly.md`.

## WHY `overlap_days` on Every Entry

WHY: SDD Constraint "WHILE a week overlaps two quarters" (accepted
deviation). A boundary week's day blocks are clipped to the period's days by
`weekly_content`, but its week-level text cannot be clipped and is read for
both periods; `overlap_days` (days of the child inside the period) lets the
model weigh a two-day overlap against a full week, as spec 045 did for a
month. A month inside its quarter always overlaps fully; the field is kept
for one entry shape.

## WHY the Status States Are Spec 045's

WHY: F6-AC5 ("the report says which monthly and weekly notes were not
found") reuses spec 045's F3-AC6 wording, so the five states and their
order are the month's (`review_period.md`, "WHY a Month Always Says
Something About Its Weekly Notes"): `not-configured` (no folder or format,
no Kado call), `found`, `none-found` (the listing had entries, none
matched), `kado-empty` (the listing returned nothing; the access hint), and
`not-read` (the listing failed after the end pass). An absent month is a
row `{month, path: None, state: absent}` only when the listing answered —
with no listing no month was looked for, so none is "absent".

## WHY Reading Is Split Into `prefetch` and `read`

WHY: the end pass (spec 045 F3-AC12). Every Kado call of a run is made
before `PacedReader.finish()`; `prefetch` reads the child notes then, so a
rate-limited one is retried by the end pass. `read` runs after it and is
served from the cache, except for the notes of a listing the end pass
recovered — those are read there for the first time, and a failure is final
and lands in `not_read` (`review_period.md`, "WHY a Recovered Folder Listing
Re-Reads Its Period").

See also: [review_period](review_period.md), [review_sources](review_sources.md).
