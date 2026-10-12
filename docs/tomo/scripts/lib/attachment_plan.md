# WHY: lib/attachment_plan.py

> Rationale for decisions in `tomo/scripts/lib/attachment_plan.py` (spec 039
> K1, T4.2). Only non-obvious decisions are recorded here.

## One decision site (SDD ADR-1)

Before spec 039 an attachment's fate was decided twice: the move builder
(`render_actions._build_move_asset_actions`) ran the typed-name check, the
remedies and the run-level claim, and the embed rewrite ran the typed-name
check again (`backlog.md:1917`). A withheld move could still rewrite its embed
(`backlog.md:1956`). Spec 039 adds vault occupancy and a vault-wide uniqueness
count, and the embed now depends on every other attachment's target, so a
third copy of the rules was the alternative. The plan is built once, before
the render loop (the last point a note body can change), and both former sites
become projections of it (T4.3, T4.4).

## Every branch of the old builder is a row

The rows reproduce today's `skipped_assets` entries byte for byte — keys,
key order, `destination` values and `reason` strings for `no_basename`,
`vault_collision_held` (both the Keep and the lost-name reason),
`typed_name_refused` and `collision` — and the same `[warn]` lines on stderr
for `no_basename` and `collision`. That is what lets T4.3 turn the builder into
a projection without changing an existing assertion. The plan prints those
lines because it is where the decision is made; the projection must not print
them again. It also prints them for attachments of an item that later fails to
render — those attachments are planned too (ADR-1 trade-off).

New kinds: `typed_folder_refused` (carries `refusal_reason`, `destination`
None — the default folder is never a fallback, F2-AC6) and `vault_occupied`
(`destination` is the occupied target; the sentence lives in
`lib/refusal_sentences.py`).

## Two passes (SDD Decision table)

Pass A decides an outcome for every source in first-appearance order. Pass B
decides embeds only after that, because uniqueness depends on the complete set
of moved targets: a target planned later still counts for an earlier source,
and a target withheld later (row 7 or 8) never counts. A single pass gets one
of the two wrong whichever order it uses.

## The census adjustment (SDD ADR-3, PRD Rule 3)

`others = vault hits − this run's moved inbox sources with that basename +
this run's other moved targets with it`. Without the subtraction every filed
attachment counts its own inbox copy and every embed is qualified — the
mutation test removes it and `test_f4_ac4_moved_inbox_sources_are_not_counted`
fails. A source that is withheld stays in the inbox, so its copy is not
subtracted. Names are compared NFC-normalised and case-folded, the census's own
key, so the subtraction matches what the census counted.

## Ignore is exempt from the vault check only (PRD Rule 4, ADR-7)

Ignore skips row 8 but not row 7: a target this run already gave to another
attachment still withholds it. Under Ignore the occupier is a vault hit at the
target itself, so the census qualifies the embed with the target path, which
names the occupier.

## Unanswered is never favourable (ADR-8, PRD Rule 5)

A folder Kado did not answer for is moved and flagged `unchecked`; only Kado's
`Path not found` reads as `absent` (`folder_created`). The embed follows the
census even then (spec README, 2026-10-12 clarification); only a census `None`
qualifies as `unanswered`.

## Which folder counts as typed

A folder that is not owner-supplied, is null, or equals the asset folder
spelled as a folder (the configured value without its trailing separator) is
the configured asset folder from Pass 2's config. Comparing against the config
value verbatim would have accepted the Pass-1 default plus a trailing `/` as
the default whenever the config carries one (`Atlas/.../295 Attachments/`),
which contradicts the rule that such a folder is refused
`trailing_separator` on both paths. Only an owner-typed folder reaches
`check_typed_folder`, with the vault-relative inbox path — otherwise
`inside_inbox` never matches. An owner-supplied `""` (empty, malformed or
contradictory folder lines, Phase 3) is refused `blank`, never defaulted.

An empty name beside a typed folder is refused `blank` (F1-AC11): the original
basename is never filled in for the owner. Beside the default folder it keeps
today's degrade to `vault_collision_held`.

## Owners in full

Every owning note is recorded for every source, moved or withheld, in confirmed
order; the old builder kept only the first owner of a moved attachment. The
delete guard (T5.2) needs all of them. The owner key is computed by
`render_actions._ensure_md_extension`, imported inside the function so the
plan and the builder share one key without an import cycle once
`render_actions` imports this module.

## Test helper location

`plan_from_remedies` lives in `tests/attachment_plan_fakes.py`, not here: it
supplies a fake vault and is never a production code path, and `tomo/` is
synced into the instance.
