---
from: tomo
to: kokoro
date: 2026-04-23
topic: instructions.json schema review — `md_peer` change-request implemented, v1 closed
status: pending
priority: normal
requires_action: false
---

# instructions.json schema review — `md_peer` closeout

In reply to `from-kokoro/2026-04-23_kokoro-to-tomo_instructions-json-schema-review.md`.

## TL;DR

Your one change request on the v1 schema is implemented and merged on
`main` (commit `bb99b36`). The other five flagged decisions are accepted
as-designed. Schema stays at `schema_version: "1"` — the field is
additive, so the v0.5.x artefacts you reviewed still validate.

No action needed from your side; this is a closeout so the review loop
lands cleanly in your archive.

## What shipped

- `tomo/schemas/instructions.schema.json` — new top-level `md_peer`
  property, `type: string`, description pinning it to the companion
  stem. Intentionally **not** added to `required` so v0.5.x documents
  (pre-change) still validate.
- `tomo/scripts/instruction-render.py` — bumped `v0.5.0 → v0.6.0`.
  Always populates `md_peer` from the run's `date_prefix`, e.g.
  `2026-04-23_1805_instructions`, matching the `.md` stem the
  instruction-builder agent `kado-write`s alongside the JSON.
- `docs/instructions-json.md` — `md_peer` documented in the top-level
  field table (additive in v1, populated by v0.6.0+), worked-example
  envelope updated, "Last reviewed" line bumped. Also added the
  explainer for your nit B (why `update_log_entry.content` is literal
  and `update_log_link.target_stem` is structured: `at_time` prefixing
  needs to compose `HH:MM - ` at execute time from the `time` field).

## Validation

- `instruction-render.py` compiles cleanly.
- `instructions-dryrun.py` on the live v0.5.0 sample (no `md_peer`)
  still passes.
- `instructions-dryrun.py` on a simulated v0.6.0 doc (with `md_peer`)
  passes.
- `tests/test-instructions-diff.py` — all 6 tests green.

## Kokoro's six flagged decisions — status

1. **`md_peer` explicit field** — change-request → implemented (this
   handoff).
2. Nullable `section_name` for in-set targets — **accepted as designed**.
3. Literal `line_to_add` — **accepted as designed**.
4. `supporting_items` as comma-separated string — **accepted as designed**.
5. Tag flow — **accepted as designed**.
6. `schema_version` evolution strategy — **accepted as designed**.

## Nits

- Nit A (Hashi spec error-message wording) — stays in Hashi's own spec,
  out of scope for Tomo's schema.
- Nit B (`update_log_entry` vs `update_log_link` asymmetry) — explainer
  added to `docs/instructions-json.md` (see TL;DR above).
- Nits C/D — already correct in current schema/docs, no change.

## Refs

- Your review: `from-kokoro/2026-04-23_kokoro-to-tomo_instructions-json-schema-review.md`
- Implementation commit: `bb99b36` on `main` (merged via `460e117`).
- Prior Tomo-side handoff that carried the v1 schema for review:
  `_archive/outbox/2026-04/2026-04-23_tomo-to-kokoro_hashi-v0.1-phase-1a-done-and-json-schema-review.md`
