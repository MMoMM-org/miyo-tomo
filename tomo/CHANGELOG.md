# Tomo Schema Changelog

> Tracks every change to `tomo/schemas/instructions.schema.json` — the
> authoritative producer/consumer contract between Tomo's Pass-2 renderer
> and Tomo Hashi's instruction executor. Companion prose contract:
> [`docs/instructions-json.md`](../docs/instructions-json.md).

This file is the drift signal between Tomo (producer) and Hashi
(vendored consumer copy at `src/schema/instructions.schema.json`). Hashi
cannot detect schema drift on its own; this changelog is the explicit
upstream signal that lets Hashi vendor with confidence.

## When to update this file

**Required**: any commit that modifies `tomo/schemas/instructions.schema.json`
MUST add a row to the table below in the same commit. Skipping the entry
breaks the drift signal Hashi relies on.

## Classification rules

Classify the change before bumping anything:

| Change                                                  | Classification | `schema_version` |
|---------------------------------------------------------|----------------|------------------|
| Add an optional field (not in `required[]`)             | Additive       | unchanged        |
| Add a new action `kind`                                 | Additive       | unchanged        |
| Add a value to an existing enum                         | Additive       | unchanged        |
| Add a new required field                                | **Breaking**   | bump             |
| Remove a field                                          | **Breaking**   | bump             |
| Rename a field                                          | **Breaking**   | bump             |
| Change a field's type or shape                          | **Breaking**   | bump             |
| Change the canonical execution order of action kinds    | **Breaking**   | bump             |

`schema_version` is a string `const` in the schema (currently `"1"`).
Bumping = update the `const` value and ship a coordinated Hashi release.

## Coordination rule for breaking changes

**Before** merging any breaking change to Tomo `main`:

1. Open an outbound handoff in `_outbox/for-hashi/` flagging the bump and
   target Tomo version. Use the same handoff lane as
   `2026-04-25_hashi-to-tomo_applied-field.md` (additive precedent).
2. Wait for Hashi to confirm vendored-schema upgrade. Hashi's vendored copy
   at `src/schema/instructions.schema.json` plus the regression test
   `test/unit/schema/vendored-schema.test.ts` (asserts `schema_version`
   pin) are the consumer-side gate.
3. Merge the Tomo schema change only after the Hashi side has cut a
   release that vendors the new shape.

Additive changes do not need this dance — Hashi vendors them on its
normal cadence and missing fields validate as `null`/absent.

## History

Most-recent first. Format:
`Date | Tomo commit / version | Classification | Schema version | Summary | Notes`.

| Date       | Tomo commit / version       | Classification | Schema version  | Summary | Notes |
|------------|-----------------------------|----------------|-----------------|---------|-------|
| 2026-04-26 | `feat/hashi-path-contract-and-changelog` | Process | v1 (unchanged) | Documented Path Shape Contract in `docs/instructions-json.md`; added renderer-side `_validate_action_paths` guard in `instruction-render.py` v0.7.1 (aborts Pass-2 with exit 2 on non-conforming path emission). Codified the schema-change discipline this file embodies. | No schema field change; defensive guard only. Hashi handoffs `path-emission-contract` + `schema-changelog-discipline`. |
| 2026-04-25 | `f3ad49d` / v0.7.0          | Additive       | v1 (unchanged) | Added optional `applied: boolean` (default `false`) to every action kind via `$defs/applied_field`. Hashi flips `false → true` after a successful apply; monotonic. | Consumers can ignore until they want partial-resume. Missing field tolerated as `false` for v0.5.x backwards-compat. Handoff: `_outbox/for-tomo/2026-04-25_hashi-to-tomo_applied-field.md`. |
| 2026-04-23 | `bb99b36` / v0.6.0+         | Additive       | v1 (unchanged) | Added optional top-level `md_peer` field — explicit stem of the companion human-readable markdown sibling. Replaces convention-based discovery. | Always populated by `instruction-render.py` v0.6.0+; older v0.5.x artefacts may lack it. Per Kokoro 2026-04-23 review. |
| 2026-04-15 | `4f74e35` / xdd-008 phase 1 | Additive       | v1 (unchanged) | Added `supporting_items` to `create_moc`; clarified action ordering; tightened path semantics in field descriptions. | Pre-MVP iteration; no consumer impact. |
| 2026-04-15 | `8c61983` / xdd-008 phase 1 | Initial        | v1              | First published shape — 8 action kinds (`create_moc`, `move_note`, `link_to_moc`, `update_tracker`, `update_log_entry`, `update_log_link`, `delete_source`, `skip`), envelope with `schema_version`, `type`, `generated`, `profile`, `actions[]`. | The v1 baseline against which all later rows compare. |

## See also

- [`docs/instructions-json.md`](../docs/instructions-json.md) — prose contract,
  per-action field reference, execution semantics, idempotency rules.
- [`docs/XDD/specs/`](../docs/XDD/specs/) — Tomo-side specs that touched the
  schema (xdd-008 phase 1 + applied-field handoff response).
- Hashi spec 002 SDD ADR-1 / ADR-2 — vendored-schema decision and the
  drift-detection assumption that this file enables.
