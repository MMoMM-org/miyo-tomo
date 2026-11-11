# WHY: schemas/doc-frontmatter.schema.json

> Rationale for decisions in `tomo/schemas/doc-frontmatter.schema.json`.
> The schema of the `tomo:` frontmatter block every Tomo producer writes
> (spec 017), validated at write time by `lib/doc_frontmatter.build_tomo_block`
> under `TOMO_SCHEMA_STRICT=1`.

## WHY the Block Is Closed and the Root Is Open

`tomo` has `additionalProperties: false`: the block is Tomo's lifecycle
truth and every key in it is read by triage, the promoter or a consumer,
so an unknown key is a producer bug, not an extension. The root object has
`additionalProperties: true`: a note's other frontmatter (the user's keys,
a producer's own top-level keys) is none of this schema's business.

## WHY States Are Constrained per Doc Type Through `oneOf`

`state` is a free string at the property level and pinned per `doc_type`
in a `oneOf` branch. A single enum of all states would let a `suggestions`
document carry `pending-apply`; the branches make the pair the unit of
validity, which is what `tomo_lifecycle.STATE_MACHINE` also encodes. Every
new doc type adds both the enum member and a branch — one without the
other is caught by `tests/test_doc_frontmatter.py`
(`test_every_doc_type_has_exactly_one_state_branch`), and a branch whose
states drift from `STATE_MACHINE[doc_type]["states"]` by
`test_state_branches_equal_the_lifecycle_state_machine`. The one member
the state machine does not know is `rendered-note` — Hashi strips the
block on apply, so it has no lifecycle — and that test pins it by name.

## WHY `review` Carries Only the Four Lifecycle Keys (spec 045, ADR-10)

`/review` (spec 045) adds `doc_type: review` with `pending-approval` →
`approved`, the same shape as `suggestions`. The review document needs
more than that to find itself again (period, kind, target note, whether
the target exists, language, tmp stem) — and those keys are **top-level
frontmatter**, deliberately outside the `tomo:` block (SDD ADR-2 amendment
and `ENTITY: ReviewDoc`, 2026-11-11). Opening the block for one producer
would either loosen `additionalProperties` for every producer or grow a
per-type property set inside the `oneOf`, and both make the block's
closed-set guarantee conditional. The open root is the place such keys
were always meant to live; `review_doc_parse` and `review_state` read them
there. The `tomo:` block of a review document is therefore
schema-identical to a `suggestions` block except for `doc_type`.
