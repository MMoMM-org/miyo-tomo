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

## WHY `replace_between_markers` Moved the Wire to `schema_version` 4 (spec 046, ADR-5)

`/review` fills sections of the user's own weekly, monthly and quarterly
notes. A re-run must refresh only Tomo's block between two opaque marker
lines inside a section the user also writes in; `replace_section` would
discard the user's text. Hashi built `replace_between_markers` from the
handoff of 2026-11-14 (Hashi #179, commit abd92d6), and the definition was
copied here from the contract text for text, placed directly after
`replace_section` in the `oneOf`.

Unlike `replace_section` at version 3, this is a kind the consumer did not
yet accept, so the version moves: the producer declares `const "4"` and
every producer (`/inbox`, `/note`, `/review`) follows through
`wire_schema_version`. The producer keeps a `const`, not Hashi's
`{"enum": ["3", "4"]}`: the contract's enum states what the consumer
accepts (a v3 set is a valid v4 set, so waiting v3 sets still apply and
Tomo builds no converter); the producer states the one version Tomo
writes, and `wire_schema_version` reads exactly that `const`.

The vendored copy was taken from Hashi's branch commit abd92d6 before
Hashi's release, by owner decision (2026-11-17): Hashi releases only after
the joint test-vault run, and that run needs v4 sets from Tomo. Its
byte-identity is re-checked against the released tag before the Tomo PR
merges (`tests/test_046_t6_1_wire_v4.py` pins the sha256). The T5.3
test-only candidate schema, which carried the action in tests until then,
was removed in the same change, so every test validates against the
committed schemas.
