# WHY: schemas/vault-config-review.schema.json

> Rationale for decisions in `tomo/schemas/vault-config-review.schema.json`.
> The input contract of `vault-config-writer.py review` (spec 045, ADR-5):
> one confirmed `/review` setup for one period kind, validated by
> `lib/review_config.input_problems` before any edit, never hand-composed
> YAML. The config keys each input key lands in are listed in the SDD's
> Data Storage Changes; `review_config.writer_edits` is the one mapping.

## WHY `placement` Allows `before` and `inside` Only

Hashi's `insert_under_marker` knows three placements. `after` on a heading
anchor inserts directly below the heading line, before that heading's own
body (`Hashi/src/actions/anchorResolver.ts:30-40`): the user's text under
the anchor would become part of Tomo's section, and a rerun's
`replace_section` would delete it. So the enum is `before` (the review
heading at the anchor's level, above it) and `inside` (one level deeper, at
the end of the anchor's section), and `after` is refused at input time —
the question never reaches delivery (SDD ADR-3, `review_config.place_level`).

## WHY a Month Forbids the Week Keys

`first_day` and `min_days` are required for `kind: week` and must be absent
for `kind: month`. Accepting them on a month would write `review.week.*` from
a monthly setup — a key the week setup owns, confirmed in a dialogue that
never showed it. The `allOf` with two `if`/`then` branches makes the pair the
unit of validity, the way the doc-frontmatter schema pins states per doc
type.

## WHY a `null` Template Removes the Key

`template` and `template_variant` take a string or `null`. The setup reader
treats an absent key and `null` alike, so the writer removes the config key
on `null` rather than writing `template: null`: a mapping that names a file
the user just said is not the template would be read back as the template on
the next run. An *absent* input key changes nothing (F1-AC2: only what the
user confirms is saved), which is why "remove" needs an explicit value.

## WHY `{"not": {}}` Instead of `false`

The month branch forbids the week keys with `"first_day": { "not": {} }`.
Draft 2020-12 allows the boolean schema `false` for the same meaning, but
`jsonschema` reports a `false` schema with an empty error path ("False
schema does not allow 'monday'" at `/`), so the JSON pointer the setup
dialogue needs (`/first_day`) is lost; `{"not": {}}` fails at the property
and keeps the pointer (verified with the venv's `jsonschema`, 2026-11-11). The schema's job is to return
pointers the dialogue can ask again for (SDD Error Handling: "refused with
pointers"), not only a verdict.
