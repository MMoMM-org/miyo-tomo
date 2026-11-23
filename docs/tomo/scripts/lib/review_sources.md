# WHY: lib/review_sources.py

> Rationale for decisions in `tomo/scripts/lib/review_sources.py` (spec 047
> T5.2, SDD ADR-6, CON-5). The module owns what a source string of a
> proposal may resolve to and the one loop that resolves it. No Kado, no
> model, no file I/O.

## WHY a Module of Its Own (CON-5, Owner Decision 2026-11-23)

The resolver and `Sources` lived in `lib/review_doc.py`. Spec 047 adds the
previous review notes and the one shared resolver to them, which took
`review_doc.py` to 493 lines against the ≈ 470 the SDD allows (Constitution
L2, 300–500 lines of dense logic). Resolving sources is a seam of its own:
`review_doc.check_item`, `review_sections` (through `check_item`),
`review_digest` (`Sources.of`) and `review_carried` all read it, and none of
it renders anything. The owner chose this split over moving the label
table. `review_doc` re-imports `note_stem`, `Sources`, `Resolved`,
`resolve_sources` and the child-group constants, so every existing caller
(`rd.Sources`, `rd.note_stem`, `rd.WEEKLY_ONLY`, …) keeps working unchanged.

## WHY One Resolver (ADR-6)

A carried item (T5.3, `lib/review_carried.py`) is checked against the same
sources as every other item, plus the previous review notes. Two loops that
each turn a source string into a day, a child note or a previous note would
drift, and the link rule (a link only from a note the read lists,
deduplicated in source order; a model string is a lookup key only) would
have to be kept in step twice. So `resolve_sources` is the one loop: it
returns the days, the count of child-note hits, the previous-note hits and
the links in source order. Resolution order per source: a daily of the
period first, then (only for `weekly_only` / `monthly_only`) a listed child
note, then a found previous note. `review_doc.check_item` is built on it
and keeps spec 045/046 behaviour exactly: a previous note is not a source of
a non-carried item, so `check_item` leaves its stems out of the links and
counts it for nothing; only the carried branch reads `previous`.

## WHY `Sources.previous` Holds Found Notes Only

A link must point at a note Kado returned. An empty, missing, not-set-up or
not-read previous note has no text the proposer saw, so nothing can rest on
it. The rows come from the read's `previous` (the `lib/review_previous`
report rows: `path`, `state`), keyed by path and by stem like the weekly and
monthly notes, so the model may cite either.

## WHY `Sources` Leaves Out the Days of a Not-Condensed Unit

See `docs/tomo/scripts/lib/review_doc.md`, "WHY `Sources` Leaves Out the
Days of a Not-Condensed Unit (Spec 047 T4.4, 0.5.4)" — the rule moved here
with the class unchanged.

## WHY `ONLY_IN_CHILD` Is Public (Spec 047 T5.4, 0.1.1)

`review_doc.check_item` reads it to decide whether an item rests on a child
note or on a day. A leading underscore promised it was private to this
module while another module depended on it; the name is now public.
