# WHY: lib/review_carried.py

> Rationale for decisions in `tomo/scripts/lib/review_carried.py` (spec 047
> T5.3; SDD ADR-6, "A carried item checked (traced)"; PRD F4-AC6, F4-AC7,
> F4-AC10, F5-AC3). The module owns every document-level rule of a carried
> item: what the proposer marked as carried from a previous review
> (`carried` + `carried_ids` in `proposals.json`). No Kado, no model, no file
> I/O.

## WHY a Module of Its Own (CON-5)

`lib/review_doc.py` and `lib/review_sections.py` are near the size guide
(Constitution L2). The carried rules cut across both: a group item and a
section item may be carried, and both must obey the same rules. One module,
called by an explicit carried branch at each call site
(`review_doc.check_items` with `in_section=False`, `review_sections.check`
with `in_section=True` and the item's mark), keeps the rules in one place and
keeps the 045/046 path (`check_item`) unchanged for every item that is not
carried.

## WHY Every Failure Is an Error, Never a Rejection

A non-carried item that breaks the source rule becomes a `rejected` row and
silently leaves the document. A carried item is a promise from the previous
review: dropping it would lose exactly the follow-up spec 047 adds. So every
carried failure is an `errors` entry, the document is refused
`proposals-invalid`, and the skill re-dispatches the proposer once with the
errors verbatim. `check` returns the error code without a pointer (the call
site knows the pointer); `coverage` walks the whole document and returns
`"<pointer>: <error>"` strings itself, except `carried-missing (<id>)`, which
has no item to point at and stays bare.

## WHY These Checks in This Order (`check`)

1. `carried-without-carryover`: no passed carryover means the proposer had no
   carried items to work from; any `carried` field is invented.
2. `carried-not-allowed (<group>)` (groups only): `done` stands only in the
   done group, `still_open` / `not_mentioned` only in open and themes; the
   other groups (growth, the child groups) take none. A section takes any
   value: a section is the user's own heading, not a status group.
3. `carried-mark-conflict` (sections only, with a child mark): `*_only` means
   no day holds the item, but a carried item that is still worked on needs a
   day; `not_in_weekly` / `not_in_monthly` needs a daily source, which
   `not_mentioned` forbids. So only `not_in_*` with `done` / `still_open`.
   This is checked before the sources, so the conflict is named, not a
   day-rule symptom of it.
4. `carried-needs-previous-note`: the previous-note entry of `sources` is the
   link back to the review the item came from (F5-AC3). Without one the user
   sees a carried mark with nothing to follow.
5. `carried-source-not-its-note (<first id>)`: the item's previous-note
   sources must lie within the union of the sources of its `carried_ids`.
   Both fields stay: ids are identity and coverage, sources are the links
   every renderer already resolves; the subset rule stops a link to an
   unrelated note. Stems are compared through `note_stem`, so a carryover
   source given as a path and a proposals source given as a stem agree, as
   they do in `lib/review_digest.py`. When an id is unknown the rule is
   skipped: `coverage` names that id, and a subset error against a
   half-known union would be a second, misleading error for one cause.
6. Day rule (PRD amendment Rule 4): `not_mentioned` means no day of the
   period mentions it again, so a day source is `carried-gone-has-day`;
   `done` / `still_open` rest on at least one day of the period
   (`carried-needs-day`).

Not applied: the two-day theme rule. A carried theme is a theme of the
previous review; one day of this period is enough to say it is still open.

Sources resolve through `review_sources.resolve_sources` — the one loop
(ADR-6) — without a child group, because a carried item never rests on a
child note (`*_only` is refused in step 3). The returned links are the
resolver's links in source order: previous notes and days together.

## WHY `coverage` Owns Ids Across the Document

Carryover ids have one home per level: `lib/review_digest.py` checks the file
(ids unique, pattern, sources among the found notes); this module checks the
document. Every id exactly once (F4-AC1): `carried-missing (<id>)` when no
item lists it, `carried-twice (<id>)` on the later item, in the 046 document
order (sections, then the groups in table order). One item may list several
ids (F4-AC7: one finding from both previous notes is one item, not two), and
a carried item the days also hold is that one item with the note and the
days as sources (F4-AC6), not a second item. `carried-unknown (<id>)` is an
exact-match lookup: the schema's id pattern is evaluated with `re.search`,
where `$` matches before a trailing `\n`, so `"c1\n"` passes the schema; no
strip or normalisation happens here, so it is refused as `carried-unknown
(c1\n)`. `carried-theme-done (<id>)`: a theme is never finished, only still
there or gone (F4-AC3).

## WHY `overflow` Moves Instead of Refusing (F4-AC10, Owner 2026-11-23)

A section has a cap (`cap` of its definition, `DEFAULT_CAP` otherwise — the
same rule `review_sections` applies). A rewrite to make a full section fit
would cost an opus run and could still drop the carried item. So `overflow`
runs before the section checks: while a section holds more items than its
cap and one of them is carried, it moves the last carried item (document
order) into the group of its mark — `done` → done; `still_open` /
`not_mentioned` → themes when every id is a `theme` item, else open. The
child mark is dropped with the move, because groups carry no mark (046
CON-2). The result is the `carried-moved` notice rows `{key, to, count}`
(counts only, no item text). Non-carried items are never moved: an over-cap
section without a carried item keeps spec 046's `over-cap` refusal. The input
is not mutated; the caller gets a new proposals dict.

The cap comes from `review_sections.section_cap` through a call-time import:
`review_sections` will import this module for its carried branch (T5.4), so
a module-level import would be a cycle, and a second cap rule would drift.
The document order of `coverage` (`review_doc.MODEL_GROUPS`) is imported at
call time for the same reason: `review_doc.check_items` will call `check`.

## WHY the Call-Time Imports Stay (Spec 047 T5.4, 0.1.1)

T5.4 wired the call sites: `review_doc` imports this module at module level
(`check_carried`), and `review_sections` reaches it through `review_doc`.
The two names this module needs back — `review_doc.MODEL_GROUPS` and
`review_sections.section_cap` (public since T5.4, was `_cap`) — stay
call-time imports. Moving them into the leaf `review_sources` would put the
group table and the cap rule into a module about sources, which they are
not; the call-time import keeps each rule in its owner at the cost of one
import line inside two functions.

See also: [review_doc](review_doc.md), [review_sections](review_sections.md), [review_sources](review_sources.md).
