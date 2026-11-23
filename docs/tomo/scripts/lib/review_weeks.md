# WHY: lib/review_weeks.py

> Rationale for decisions in `tomo/scripts/lib/review_weeks.py`.
> The module owns the units of a `/review` period (spec 047, T2.2; PRD F1-AC1,
> F1-AC2; SDD ADR-2 and "Example: Packing a period into units"): the weeks of
> the period under the configured week rule, clipped to the period, packed into
> units under the unit budget; which day takes part; the digest cap per unit;
> and the size constants of ADR-2. No file I/O, no Kado, no model: day weights
> and the taking-part days come in as arguments.

## WHY Units Exist

A quarter read is too large for one agent to read (spec 047 PRD: the 2026-Q1
read left days unread). The read is condensed per unit by one `review-digester`
each, and the proposer reads the digests instead of the days. A unit is the
smallest piece with a natural meaning for the user — a week — cut further only
when its files would not fit one digester's reading budget.

## WHY Weeks Come From the Configured Week Rule

`units(period, rule, …)` takes the `WeekRule` the setup carries
(`lib/review_config.py`, `review.week`) and asks `Period.weeks_overlapping(rule)`
for the weeks. Hard-coded ISO would name units `2026-W14` for a user whose
weekly notes are counted from Sunday and cut the month on other days than the
user's own weekly notes do, so a unit would not line up with the weekly child
note it sits next to. The tests pin a Sunday/1 rule giving other names and
other edges than ISO.

## WHY a Month or Quarter Clips Its Weeks but a Week Review Does Not

F1-AC2: every day of the period belongs to exactly one unit inside the period.
A month's first and last weeks overlap the neighbouring months; their days
outside the period were not read and belong to another review, so the unit
keeps only `period.start <= d <= period.end`. A week review's period *is* the
week, so it is one unit of all seven days and nothing is clipped (the empty
days at its end are still the user's week).

## WHY Greedy Date-Order Packing, Never Dropping a Day

F1-AC1: every day is read by some digester. Walking the days in date order and
starting a new unit only when the next day would push the current one over
`UNIT_BUDGET` keeps a unit a contiguous run of days, so a digest still reads
as "the first half of the week", and the split names `<week>a`, `<week>b`…
sort in date order. A week has at most seven days, so seven suffixes suffice.
A day heavier than the budget alone becomes a unit of its own — splitting
below a day would split a day's file set between two digesters, and dropping
it would be the very loss the spec removes. `over_budget(units)` names those
units so `review-read.py --measure` can report them; each of their files is
still at or under `FILE_CEILING` (the stage re-cuts a day file that is not).

A day absent from `day_bytes` weighs 0 and is still placed: the unit list is
built from the period's days, not from the weights, so a caller bug in the
weights cannot lose a day.

## WHY a Day Weighs Its Day File Plus Its Growth Files

The digester of a unit reads the day files and the growth files (the notes
created on each day) of that unit. Budgeting on day files alone let a week
with a burst of created notes exceed what one digester reads. The caller
(`lib/review_stage.py`) passes each day's summed, indented UTF-8 bytes; this
module never measures, so the one encoding rule (ADR-2: `indent=1`,
`ensure_ascii=False`) has one owner.

## WHY `takes_part` Reads Plain Dict Fields

A unit with no taking-part day gets no digester; it has nothing to condense
and is not reported "not condensed". A day takes part when it has content,
tasks, linked notes, or at least one created note in `growth/` — a day whose
only trace is three new notes is still part of the user's period. The
function takes the day entry as a plain dict (`has_content`, `tasks`,
`linked`) and the created-note count, so it does not depend on the private
helpers of `lib/review_day.py` and the stage can call it while building
`weeks.json`. `units` takes the resulting set of dates, so the packer stays
independent of the day entry's shape.

## WHY These Constants (ADR-2, SDD v1.3)

- `FILE_CEILING` 32,768 bytes — every agent-read file; ≈ 17.7k tokens at 1.85
  chars/token and ≈ 20k at the poorly tokenizing T1.4 file, under the Read
  tool's 25k limit. Owner 2026-11-23 after T1.4 lowered it from 40,960.
- `UNIT_BUDGET` 131,072 bytes — the indented day + growth bytes of one unit; a
  7-day test-vault week is ≈ 47–58 KB indented, so a normal week is one unit.
  Owner 2026-11-23 after T2.5 raised it from 81,920: the measured bulk-import
  day 2026-01-19 (85,912 B growth + 6,978 B day file = 92,890 B) stood alone
  over the old budget; a haiku digester reading ~5 files of a 128 KB unit is
  ≈ 70k tokens, within its context, and every file still meets the ceiling.
- `DIGEST_TOTAL` 114,688 and `DIGEST_MAX` 8,192 bytes — `digest_cap(n) =
  min(DIGEST_MAX, DIGEST_TOTAL // n)`: 14 units → 8 KB each, 16 → 7 KB each,
  so the proposer's digests stay ≤ 112 KB whatever the unit count.
  `digest_cap(0)` returns `DIGEST_MAX` rather than dividing by zero.

They are code constants, not configuration (SDD: "Configuration: none new"),
set from the Phase 1 measurements and revisited from the live walk.
