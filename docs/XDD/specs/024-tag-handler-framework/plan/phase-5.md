---
title: "Phase 5: Authoring wizard + Tsukai handler + docs"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Authoring wizard + Tsukai handler + docs

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Section 7; lines: 144-148]` — `tomo-tag-handler-wizard` skill (AskUserQuestion → atomic write → schema-validated)
- `[ref: PRD/FR-13,FR-14; lines: 82-86]` — wizard authoring (no skill authoring); ship a Tsukai reference handler
- `[ref: PRD/Section 6; lines: 88-103]` — concrete Tsukai handler JSON
- `[ref: PRD/AC-2,AC-6; lines: 108,113]` — user-authored handler drives detection+handling; documented in config/inbox docs

**Key Decisions**:
- The wizard mirrors `tomo-trackers-wizard` / `tomo-daily-log-wizard`: AskUserQuestion-driven, writes `config/tag-handlers/<feature>.json` via a `vault-config-writer`-style atomic write, validated against the schema — **no skill authoring** (SDD §7).
- Ship `config/tag-handlers/tsukai.json` so the feature works out-of-the-box once the user fills `repo_note_map` (`target.map`) (FR-14, NG3).
- WHY-docs for the resolver / interpreter skill / wizard live in `docs/tomo/` (mirrored-path WHY-persistence layer, per repo CLAUDE.md); runtime files stay imperative-only.

**Dependencies**:
- Phases 1–4 (schema, resolver, pipeline) define what the wizard writes and the handler drives.

---

## Tasks

Makes the framework user-operable end-to-end: a wizard authors handlers as pure data, a Tsukai reference handler ships, and the why is documented.

- [x] **T5.1 `tomo-tag-handler-wizard` skill** `[activity: frontend-ui]`

  1. Prime: Read the wizard spec `[ref: SDD/Section 7; lines: 144-148]` and the `tomo-trackers-wizard` skill it mirrors.
  2. Test (RED): wizard collects `tag_prefix`, `capture_segments`, `read_fields`, `action`, `target.map`, `marker`, `compose` via AskUserQuestion; writes `config/tag-handlers/<feature>.json`; the written file **validates against `tag-handler.schema.json`**; an invalid combination is rejected before write (atomic — no partial file); AskUserQuestion option-count stays ≤4.
  3. Implement: Author the `tomo-tag-handler-wizard` skill (AskUserQuestion flow + schema-validated atomic write).
  4. Validate: wizard produces a schema-valid handler; lint/skill-author audit clean.
  5. Success: A user can author a handler with no skill authoring `[ref: PRD/FR-13; lines: 82-84]` `[ref: PRD/AC-2; lines: 108]`.

- [x] **T5.2 Ship `config/tag-handlers/tsukai.json` reference handler** `[activity: data-architecture]`

  1. Prime: Read the concrete Tsukai handler `[ref: PRD/Section 6; lines: 88-103]` and `[ref: SDD/Section 2; lines: 24-39]`.
  2. Test (RED): `tsukai.json` validates against `tag-handler.schema.json`; matches `MiYo/Tsukai/` with segment `repo`, field `category`, action `insert_under_marker`, marker `## Captures`, compose directive; `target.map` (`repo_note_map`) is present as a user-fill stub.
  3. Implement: Add `config/tag-handlers/tsukai.json` per the PRD §6 JSON (user fills `repo_note_map`).
  4. Validate: schema-validation test passes; resolver matches it on a Tsukai-tagged fixture.
  5. Success: Tsukai works out-of-the-box once the user fills `repo_note_map` `[ref: PRD/FR-14; lines: 85-86]`.

- [ ] **T5.3 Docs — config/inbox docs + `docs/tomo/` WHY-docs** `[activity: documentation]`

  1. Prime: Read the doc-routing rules (repo CLAUDE.md: `docs/tomo/<mirrored-path>.md` is the WHY layer) and `[ref: PRD/AC-6; lines: 113]`.
  2. Test (acceptance): config/inbox user docs describe the tag-handler framework + wizard; `docs/tomo/` WHY-docs cover the resolver, the interpreter skill, and the wizard (no executor internals leaked into user-facing docs).
  3. Implement: Write the config/inbox docs and the `docs/tomo/` WHY-docs for resolver/interpreter/wizard.
  4. Validate: docs match shipped behavior; no Hashi/script internals in user-facing docs.
  5. Success: Framework documented in Tomo's config/inbox docs `[ref: PRD/AC-6; lines: 113]`.

- [ ] **T5.4 Phase Validation** `[activity: validate]`

  - Run all Phase 5 tests under `./venv/bin/python`. Verify a wizard-authored handler validates and the Tsukai reference handler resolves. Confirm docs cover the framework + WHY-docs exist. Lint/skill-author audit clean. **Gate: handler authorable end-to-end (AC-2, AC-6).**
