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

## WHY the Quarter Is a Third Kind With the Month's Rules (spec 046, ADR-6)

`kind: quarter` saves into the same four sections a month does, under the
`quarterly` key: `concepts.calendar.granularities.quarterly`,
`naming.calendar_patterns.quarterly`, `templates.mapping.quarterly` and
`review.quarterly`. The MiYo profile already names
`granularities.quarterly`, so the folder falls back to it exactly as the
month's does, and one reader serves all three kinds through
`review_config.GRANULARITY`. A quarter forbids `first_day` and `min_days`
for the month's reason: they are the week setup's keys. Each kind keeps its
own `allOf` branch keyed by `kind` `const`, so the required keys of a kind
can be read off one clause (`tests/test_review_privacy_docs.py`).

## WHY Section Rows Carry the Full Heading Key (spec 046, ADR-3)

A row names its template heading by `heading`, `level`, `parent` and
`occurrence` — the identity `review_mapping.row_key` builds — not by the
bare text `own_sections` uses. Templates repeat heading texts (one
"Notes" per weekday, the same question under two parents), so text alone
would map one row onto several sections. All four fields are required: a
writer input that leaves one out would store a row whose identity depends
on a default the next reader may not share. `off_limits` rows carry the
same four fields plus `with_subsections`, which is required for the same
reason — whether the mark covers the sub-headings is the user's answer,
not a default (`landing_off_limits` covers sub-headings only on `true`).

## WHY `sections` and `off_limits` Need a Named Template

The rows are stored per template, under
`review.<g>.sections.<template>` and `review.<g>.off_limits.<template>`,
so the private and the work variant of a template, and the templates of
two kinds, never share a mapping (PRD F2-AC8). The input therefore cannot
carry rows without saying whose they are: `dependentSchemas` requires a
non-null `template` whenever `sections` or `off_limits` is present. The key
is the `templates.mapping.<g>` name, never the `_tomo` variant, because the
mapping is what the user confirmed; the variant is derived from it.

## WHY the Row Fields Are Closed and Bounded

- `id` matches `^s[0-9]{1,3}$`: it is opaque and assigned at save
  (`review_mapping.assign_ids`, ADR-10), and it becomes part of the
  section markers in the delivered note. A free-form id could collide with
  marker syntax or carry note text into a marker.
- `placement` is `before | under | end | review`; `review` marks an
  analysis row whose text lands in the "Tomo Review" section (F2-AC12).
  Which headings may take which placement depends on the template analysis,
  so that check is `setup-input`'s (Phase 2), not the schema's.
- `cap` is 1..30 and optional (the reader's default is 8): the proposal
  check refuses an over-cap section rather than truncating it (ADR-2), so
  the bound has to be a number the model can merge down to.
- `description` is non-empty: it is the only instruction the model gets
  for the section. `keywords` holds at most 12 entries.
- `groups` names spec 045 groups as starting points (F2-AC7) and never
  `habits`: the habits are computed by a script and always stay in the
  "Tomo Review" section. The allowed set depends on the kind — the month
  adds `weekly_only` and `not_in_weekly`, the quarter `monthly_only` and
  `not_in_monthly` (F6-AC4; its weekly notes are sources, not marked) —
  so each kind's `allOf` branch narrows `groups` to `$defs/<kind>Group`.
  A mark the kind does not compute would name a group that is always empty.
- `additionalProperties: false` on both row shapes: the stored rows are
  setup text the user confirmed; an unknown field would be stored unseen.
