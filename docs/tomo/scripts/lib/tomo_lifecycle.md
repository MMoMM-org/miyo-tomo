# WHY: lib/tomo_lifecycle.py

> Rationale for decisions in `tomo/scripts/lib/tomo_lifecycle.py`.
> The pure-data state machine for every Tomo-produced doc type (spec 017 ADR-1).

## WHY a Dict, Not a Class Hierarchy

Spec 017 ADR-1: the state machine is a plain dict-of-dicts so that it is
importable anywhere (stdlib only), auditable by reading, and coupled to no
producer or consumer. `validate_transition`, `is_terminal` and `is_pending`
are the whole API; `state-promoter.py` is the only write path (see
`docs/tomo/dot_claude/skills/tomo-lifecycle-states.md`).

## WHY `review` Is Its Own Doc Type (spec 045, ADR-10)

`/review` (spec 045) stamps its inbox document `<period-name> Review.md`
with `doc_type: review` and the states `pending-approval` → `approved` —
the same two-state shape as `suggestions`, with the user's tick of the
`- [ ] Approved` line as the trigger.

Reusing an existing doc type was ruled out in ADR-10: `pending-accept`
falls back to the moc-proposal route in `inbox-triage.py`, and a new
state under an existing type would make `/inbox` treat the document as a
new item. A distinct type lets triage skip the document before any read
(the filename rule ` Review` inside the Tomo-stamped buckets, T1.6) and
lets `/review` find its own open documents by frontmatter even after a
rename.

The review-specific keys (`review_period`, `review_kind`, `review_target`,
`review_target_exists`, `review_language`, `review_stem`) are **top-level
frontmatter**, not members of the `tomo:` block — the block's schema is
closed (`additionalProperties: false`) and holds only `doc_type`, `state`,
`run_id`, `updated_at` and `sources` (ADR-2 amendment, 2026-11-11). This
module therefore learns nothing about them; the lifecycle entry is the
same four keys every other type carries.

The transition trigger names the step that flips the state: the `doc_mark`
step of `review-instructions.py deliver` (SDD Primary Flow step 9), the
last of `note → set_json → set_md → doc_mark`, so that `approved` in the
frontmatter means "the instruction set for this document was written" —
`review_state` reads `approved` without a set JSON as a failed delivery to
resume. The user's tick alone does not change the frontmatter; it is read
by `review-doc.py parse` and refused as `not-approved` when absent.
