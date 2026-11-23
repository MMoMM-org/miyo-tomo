# WHY: lib/review_stage_codec.py

> Rationale for decisions in `tomo/scripts/lib/review_stage_codec.py`.
> The module holds the byte-level rules of the `/review` stage files (spec 047,
> T2.3; ADR-2): the line-broken encoding and its measure, texts as line arrays,
> the re-cut loop over `review_day.cut_at_boundary`, packing items into parts
> under the ceiling, spilling and merging context lists, and the per-file docs
> of a day, a child note, a previous note and a day's growth. No file I/O:
> `lib/review_stage.py` decides what goes into which file and writes it.

## WHY a Separate Module

WHY: a recorded deviation of T2.3. The plan's validation step asks for
`lib/review_stage.py` ≤ 300 lines and, if it is not, for the encoding
helpers to move out. Writer, loader, discard and the continue check came to
about 500 lines together; the encoding, cutting and packing rules are the
natural seam (they are pure functions of data and the ceiling), so they live
here and `review_stage` keeps the layout. The decisions behind each rule
(why `indent=1` UTF-8, why line arrays and 1,000-character pieces, why three
tries at 1.0 / 0.8 / 0.6 then the hard cut, why limits are clamped to ≥ 1,
why context lists spill into parts) are written once, in
`docs/tomo/scripts/lib/review_stage.md`; this page does not repeat them.

## WHY `fit` Takes a Render Function

WHY: one cut loop for two shapes. A day and a child note are cut the same way
— whole trailing units first, the first section hard-cut last — but rebuild
different entries from the kept units. The caller passes `render(kept)`,
which builds and encodes its entry; `fit` only measures and shrinks, so the
ceiling is always measured on the exact text that is written.

## WHY `pack_parts` Measures the Rendered Part

WHY: the ceiling is a property of the written file, including its header
(`read_id`, `date`, `part`) and its indentation, which depends on how deep
the item sits. Summing item sizes would undercount; rendering the trial part
is exact. A single item over the ceiling still gets a part of its own — an
entry is never cut or dropped (ADR-2: growth entries never split).

## WHY `fit` Ends in a Shrinking Hard Cut

WHY: the cutter counts characters, the ceiling counts bytes of the written
file. A stored line costs about 7 bytes more than its characters (indent,
quotes, comma, newline), so a first section of many short lines can still be
over the ceiling after the hard cut at the last try's limit. The hard cut
then shrinks the limit by the measured overshoot (`limit * room // over`, at
least one less each time) and re-renders, until the file fits or the limit
is 1. Each step is measured on the exact text that is written, so it never
stops early on an estimate; the limit-1 floor ends the loop when the
non-text part alone is over the ceiling (that file is then named in
`manifest.over_ceiling`).

## WHY `day_text` Returns Whether It Re-Cut

WHY: the report is not in the day file. `day_text` re-cuts an oversized day
and sets `partly_read` and a recomputed `has_content` in the day file, but
the report that names a day's dailies lives in the manifest, which
`review_stage.write` builds after all day files. Returning `(text, recut)`
lets `write` collect the re-cut dates without decoding its own output. The
day's sections and linked texts are the cutter's units in `read_day`'s
order, so a re-cut keeps what a smaller `max_chars_per_day` would have kept.

## WHY `child_text` Cuts Own Sections Before Day Blocks Last

WHY: one cut loop, a child note's own shape. A weekly or monthly note has
its own section texts (the `*_text` dict) and its day blocks; both become
units of the one cutter, own sections first, so trailing day blocks go
first when the note is over the ceiling. The unit names carry a `t:` / `d:`
prefix because a heading and a date could be the same string. The file then
carries `clipped: true`, which `child_entry` keeps only when true.

## WHY `mark_partly_read` Deep-Copies the Report

WHY: the caller's result is not the stage's to change. `review_stage.write`
gets the `read_period` result from its caller, who may still use it (a
measure run, a test comparing it to `load`). Marking the re-cut days'
dailies `partly-read` in place would change the caller's report behind its
back; the deep copy changes only the manifest's copy. A `failed` daily stays
`failed`: a failed read is the stronger state.

## WHY `field_aggregates` Lives Here

WHY: the T2.5 follow-up (owner 2026-11-23) moved `context.json` from raw
per-day fields to per-field aggregates. The aggregation is a pure function
of the day entries and the `weeks.json` units, like the other per-file
builders here, and `lib/review_stage.py` is at its ~300-line seam. It
classifies values through `review_habits.parse_value` rather than a parser
of its own; what the aggregates hold and why is in
`docs/tomo/scripts/lib/review_stage.md` ("WHY `context.json` Carries Field
Aggregates").

## WHY a Thousands-Grouped Value Counts Days Only

WHY: `review_habits.parse_value` reads a comma as a decimal mark (`"7,5"`
is 7.5), so `"1,000"` would read as 1 and give a plausible but wrong
min / max / mean, off by a factor of 1,000, while the raw value no longer
reaches `context.json`. `_reading` therefore treats a value shaped like
thousands grouping (`^[+-]?\d{1,3}(,\d{3})+$`) as "has a value, not a
number", so that field's period and unit stats fall back to `{days}`. The
shape is ambiguous: `"7,500"` could be a German decimal 7.5. The guard
resolves it conservatively, as days only: a missing aggregate is visible,
a wrong one is not. The guard lives here, not in `review_habits`, because
the habit check reads its own values and is out of this change's scope.

## WHY `previous_doc` Accepts Lines or a Text

WHY: `review_previous.resolve` gives a found note's sections as line arrays
(the SDD row shape), while a hand-built result may carry texts. `previous_doc`
joins either form (`join_text`) and stores `lines_of` that text, so a line
over the piece length is pieced in both cases and `previous_entry` joins it
back to the same text (T3.2: storing a list through `lines_of` wrote its
Python repr).
