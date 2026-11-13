# WHY: schemas/instructions.schema.json

> Rationale for decisions in `tomo/schemas/instructions.schema.json` — Tomo's
> PRODUCER copy of the instruction-set wire schema. Its sibling
> `hashi-instructions.schema.json` is the CONTRACT: a verbatim mirror of
> Hashi's live wire schema, re-vendored from Hashi and never edited here.

## WHY Two Documents, and Which One Is Edited

The producer copy is what Tomo validates its own output against before it
reaches the wire; the contract is what the consumer validates with. They
agree on the action contract (`tests/test_tomo_schema_parity.py`, both
directions) and differ by design in two places: the Tomo-owned
`properties.tomo` block (agreed permissive, miyo-tomo#74) and any action
Hashi ships that Tomo has no emitter for (`MIRROR_ONLY_ACTIONS`). Since
spec 035 ADR-6 they carry distinct `$id`s so a consumer cannot diff the
wrong file.

Only this file changes when Tomo starts emitting something. An action
Hashi already executes is **copied from the contract** into the `$defs`
and the `actions.items.oneOf` list here, text for text; the contract
stays byte-identical until Hashi's own next release is re-vendored.

## WHY `replace_section` Entered the Producer Copy (spec 045, ADR-3)

Until spec 045 the contract carried a `replace_section` definition the
producer copy lacked — Hashi executes it, nothing in Tomo emitted it, so
it sat in `MIRROR_ONLY_ACTIONS` and the wire-snapshot report sanctioned
the `/$defs/replace_section` delta. `/review` changed that: a first
delivery lands the review section with `insert_under_marker`, and a rerun
over the same period overwrites it with `replace_section` on the heading
above the `%% tomo-review <period> %%` marker (SDD ADR-3). That is the
first Tomo emitter, so the definition moved in verbatim from
`hashi-instructions.schema.json`, the mirror-only exemption and the
sanctioned-asymmetry prefix went out in the same commit, and
`test_hashi_instructions_schema.py` now asserts the action is present
here. The definition is placed directly after `insert_under_marker` in
the `oneOf` (the overall order differs from the contract's); the
schema-parity test compares the ref sets, not their order.

### Why the shape manifest was regenerated at `schema_version` 3, without a version move

The wire gate (`lib/wire_gate.py`, spec 035 ADR-3) reads the added
`/$defs/replace_section` as a consumer-affecting change and, while the
manifest `tomo/schemas/shapes/instructions.shape.json` is stale, demands
`move_version` + `handover`. Both demands were weighed and the version
move was declined on purpose: the contract pins `schema_version` to
`const "3"` and Hashi's live schema at that version **already contains**
`replace_section`. This change narrows the producer towards the contract
instead of widening the wire — a bump to "4" would be the only thing that
breaks the consumer, because every set Tomo then emits fails Hashi's
`schema_version` const. The manifest was regenerated with
`scripts/wire-shape.py --regenerate` (the explicit, printed act ADR-3
requires), the obligation row recorded as `version '3' -> '3'`, and the
"handover" half is the Kokoro FYI handoff of spec 045 T1.7, which states
that no Hashi change is asked. The gate's demand list is a reading of the
stale manifest, not a rule that an affecting delta must always move the
version; the case the demand exists for is a shape the consumer does not
yet accept, and this is its mirror image.

The definition is copied, not rewritten, because it is the consumer's
behaviour the description documents — heading-scoped anchor, body replaced
with the heading line preserved, graceful no-op on a missing anchor or
target. Rendering of the action for a user without Hashi lives in
`lib/render_md.py` (spec 045 T1.5), not in this schema.
