---
title: "Phase 4: Breaking wire rename, schema_version bump & cross-repo handoff"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Breaking wire rename, schema_version bump & cross-repo handoff

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-3]` — hard cutover + schema_version bump
- `[ref: SDD/Interface Specifications; Wire schema change]`
- `[ref: PRD/Feature 4]` — lockstep migration path
- `[ref: miyo-constitution; L2 Architecture]` — breaking-change migration documented

**Key Decisions**:
- ADR-3: HARD CUTOVER. Rename `origin_inbox_item`→`source_inbox_item` in BOTH schemas (no alias);
  bump `schema_version` const `"1"`→`"2"`. Hashi must reject unknown versions (per
  `docs/instructions-json.md`), so a v2 doc on a v1-only Hashi fails loud. Tomo+Hashi deploy in
  lockstep; migration procedure = apply pending instruction sets, THEN upgrade both.

**Dependencies**:
- Phases 1–3 (the new field is emitted alongside the audio-peer behavior). This is the cross-repo
  breaking phase — land last, in the same deploy as Hashi#41.

---

## Tasks

Delivers the clean wire rename with an explicit version cutover and the cross-repo coordination
artifacts. **This phase changes the Tomo↔Hashi contract — do not merge without the Hashi handoff.**

- [ ] **T4.1 Rename wire field + bump schema_version in both schemas** `[activity: backend]`

  1. Prime: Read both schemas `[ref: SDD/Code Context; instructions.schema.json, hashi-instructions.schema.json]`.
  2. Test (red): a doc using `source_inbox_item` + `schema_version:"2"` validates; a doc using the
     old `origin_inbox_item` is REJECTED (additionalProperties:false); `schema_version:"1"` is
     rejected by the bumped const `[ref: PRD/AC F4; constitution L1 reject path]`.
  3. Implement (green): in BOTH schemas rename `origin_inbox_item`→`source_inbox_item` (no alias)
     and change `schema_version` const `"1"`→`"2"`. Keep `additionalProperties:false`.
  4. Validate: schema validation tests pass for both repos' schema files.
  5. Success: only the new field + v2 validate `[ref: SDD/ADR-3]`.

- [ ] **T4.2 Renderer emits source_inbox_item + schema_version 2** `[activity: backend]`

  1. Prime: Read `_build_move_note_actions` (~768) + the doc header emit (`instruction-render.py:2707`).
  2. Test (red): the emitted move_note action key is `source_inbox_item`; the doc header emits
     `schema_version:"2"`; the end-to-end schema-validation test passes against the v2 schema
     `[ref: PRD/AC F4]`.
  3. Implement (green): rename the emitted key (768) and any display (`**Source (reference):**`
     replacing `**Origin (reference):**` at ~1411); bump the emitted `schema_version` to `"2"`.
  4. Validate: instruction-render suite green against v2; lint clean.
  5. Success: Tomo emits the v2 contract `[ref: SDD/ADR-3]`.

- [ ] **T4.3 instructions-diff consumes the new field** `[activity: backend]`

  1. Prime: Read `instructions-diff.py` origin consumer `[ref: SDD/Code Context; instructions-diff.py; lines: 366-368]`.
  2. Test (red): the idempotency diff matches move_note by `source_inbox_item` stem (falls back to
     `rendered_file`) `[ref: PRD/AC F4]`.
  3. Implement (green): switch the consumer from `origin_inbox_item` to `source_inbox_item`.
  4. Validate: instructions-diff suite green.
  5. Success: diff stable under the renamed field `[ref: SDD/ADR-3]`.

- [ ] **T4.4 Docs, CHANGELOG, version bumps** `[activity: backend]` `[parallel: true]`

  1. Prime: `docs/instructions-json.md` (schema_version contract) + `tomo/CHANGELOG.md` table.
  2. Test: N/A.
  3. Implement: update `docs/instructions-json.md` for `source_inbox_item` + schema_version v2;
     add the CHANGELOG row (incompatible-change classification, schema_version "2"); bump
     `# version:` on edited managed scripts; update `docs/tomo` counterparts.
  4. Validate: docs reflect v2; CHANGELOG row present.
  5. Success: wire change is documented `[ref: PRD/AC F4]`.

- [ ] **T4.5 Kokoro ADR + Hashi handoff (cross-repo)** `[activity: coordination]`

  1. Prime: MiYo handoff protocol + the Kokoro ADR convention `[ref: SDD/Integration Points]`.
  2. Test: N/A (coordination artifacts).
  3. Implement: write a Kokoro ADR recording the breaking rename + schema_version v2 + the
     "apply-pending-then-upgrade-both" lockstep procedure; create `_outbox/for-tomo-hashi/` handoff
     for Hashi#41 (accept `source_inbox_item`, apply a `delete_source` per audio peer, gate on
     schema_version v2 — must land in the same deploy).
  4. Validate: handoff file present in `_outbox/for-tomo-hashi/`; ADR drafted for Kokoro.
  5. Success: cross-repo migration coordinated `[ref: PRD/AC F4; constitution L2]`.

- [ ] **T4.6 Phase Validation & integration** `[activity: validate]`

  - Run full suite green. Confirm zero `origin_inbox_item`/`origin` in code, schemas, and
    user-facing text (whole-repo `rg`). Confirm the end-to-end path: voice item → suggestions doc
    (two-box) → confirm → instruction set (v2, `source_inbox_item`, paired transcript+audio
    `delete_source`) validates against the v2 schema. Lint clean. **Do not mark complete until the
    Hashi#41 handoff is recorded.**
