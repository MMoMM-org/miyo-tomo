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
