# WHY: lib/up_state.py

> Rationale for decisions in `tomo/scripts/lib/up_state.py`.
> The module turns a parsed `up` target into `(up_state, up_broken_reason)`.

## One Classification, Two Callers (#216)

WHY: `moc-tree-builder.py` `build_entries` (writes `up_state` and
`up_broken_reason` into the MOC-structure cache) and `moc-discovery.py`
`phase65_validate_existing_up` (decorates topic members with `state` and
`reason`) classify the same target the same way: no target is `absent`, a MOC
stem is `valid`, an in-scope note stem is `broken` / `not-a-moc`, anything else
is `broken` / `unresolved`. Until #216 discovery carried a copy of the rule
("mirrored, not imported") because the builder is a hyphenated script whose
import pulls in the whole cache build. Two copies of a rule drift; the cache
and the proposal would then disagree on the same note. The rule now lives in
this library module, which both scripts import.

WHY a module of its own and not `up_parse`: `up_parse` answers "what parent
does this note declare?" from the note's text alone and deliberately knows
nothing about the vault (M1, see `up_parse.md`). Classification needs the MOC
and note stem sets, which are vault state. Keeping it apart keeps `up_parse`
testable without a vault, as M1 intends.

WHY the stem sets stay with the callers: each caller builds them from the data
it already holds. The builder uses the scanned MOC and note paths; discovery
uses the cache's `map_notes` (stems and titles) and its `kind == "note"`
entries. The inputs differ by source, not by rule, so only the rule is shared.

## The MOC Wins a Tie

WHY: a stem present in both sets (a MOC also listed as a note, or a MOC title
equal to a note stem) resolves `valid`. That is the pre-existing MOC-first
precedence of `up_state` (spec 033 ADR-2).

## Reason Tokens Are Fixed

WHY: `not-a-moc` and `unresolved` are written into the cache and the discovery
report and read by the reducer and by garden-audit (`up_broken_reason`). They
are tokens, not display text, and are never localised. `unresolved` means "not
found in the scanned scope", not "absent from the vault" (see
`moc-tree-builder.md`).
