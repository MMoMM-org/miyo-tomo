---
title: "Phase 6: Integration, regression and documentation"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Integration, regression and documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]` — the full table is this phase's checklist
- `[ref: SDD/Deployment View]`
- `[ref: PRD/Success Metrics]`
- `[ref: CON-8]` — additive only; attachment-free runs must be byte-identical
- Reference artefact: `tomo-instance/tomo-tmp/rendered-hashi/instructions.json` — the hand-composed set that motivated the spec, and the shape the pipeline must now produce on its own

**Key Decisions**:
- The headline metric is measured **against the vault**, not self-reported: attachment files left in the inbox after an all-approved run must reach zero.
- Live-test cycles are expensive and rate-limited. Batch everything needing a live run into **one** cycle `[ref: memory: minimize live-test cycles]`.

**Dependencies**: Phases 1–5 complete.

---

## Tasks

Proves the chain end to end and leaves the repo documented and synced.

- [ ] **T6.1 End-to-end pipeline test** `[activity: integration-testing]`

  1. **Prime**: Read `[ref: SDD/Building Block View; Components]`. The test drives the public entry point, not the helpers `[ref: memory: mock at orchestrator, not helper]`.
  2. **Test** (RED) — one scenario mirroring the motivating import:
     - inbox contains notes in one subfolder and images in a sibling subfolder
     - notes embed the images by bare filename
     - after approval, the rendered instruction set contains the expected `move_note` **and** `move_asset` actions, with attachments moved to the asset concept
     - the set validates against `tomo/schemas/instructions.schema.json` `[ref: PRD/AC-F4.4]`
     - `instructions-diff` reconciles with no mismatch `[ref: PRD/AC-F5.1]`
     - `instructions-dryrun` exits 0 `[ref: PRD/AC-F5.4]`
     - a shared image embedded by two approved notes yields exactly one action `[ref: PRD/AC-F4.2]`
  3. **Implement**: the fixture and test; no production code should be needed here — if it is, an earlier phase was incomplete.
  4. **Validate**: the test passes without touching a live vault.
  5. **Success**: the pipeline reproduces, deterministically, what previously had to be hand-composed `[ref: PRD/User Research]`

- [ ] **T6.2 Regression: attachment-free runs unchanged** `[activity: integration-testing]` `[parallel: true]`

  1. **Prime**: `[ref: CON-8]`. Tomo is near MVP; hot paths take additive changes only.
  2. **Test** (RED):
     - a fixture with no embeds produces an instruction set **byte-identical** to the pre-change golden file, except for action IDs where the new slot shifts them
     - the suggestions document for such an item contains no attachment line and no unresolved line `[ref: PRD/AC-F3.2]`
     - a voice item's `audio_peer` behaviour is untouched, including its paired `delete_source`
  3. **Implement**: regenerate goldens **only** where the ID shift explains the diff; any other difference is a defect, not a golden update.
  4. **Validate**: full suite green.
  5. **Success**: no behavioural change for items without attachments `[ref: CON-8]`

- [ ] **T6.3 Cost verification** `[activity: integration-testing]` `[parallel: true]`

  1. **Prime**: `[ref: PRD/Success Metrics; Cost]` and the corrected counter from T5.2.
  2. **Test** (RED):
     - attachment-related Kado calls are constant as note count varies from 1 to 20 `[ref: CON-4]`
     - the reported per-run count matches the faked client's observed invocations
  3. **Implement**: assertions only.
  4. **Validate**: passes.
  5. **Success**: the O(1) claim is enforced by a test, not by argument `[ref: ADR-1]`

- [ ] **T6.4 Documentation and sync** `[activity: documentation]`

  1. **Prime**: Read the WHY-layer rule in `CLAUDE.md` and `[ref: SDD/Deployment View]`.
  2. **Test**: n/a.
  3. **Implement**:
     - `docs/tomo/scripts/lib/attachment_index.md` — completed in T1.4, reviewed here for drift
     - `docs/instructions-json.md` — the `move_asset` section already ships; update the "Who emits it" paragraph now that the deterministic pipeline emits it, not only session-composed sets
     - `docs/XDD/backlog.md` — F-57 already reads RESOLVED; add the pointer to spec 031
     - `docs/evolution/inbox-cost-log.md` — record the corrected counter baseline (T5.2) as its own entry
     - verify every touched `tomo/scripts/` file has a bumped `# version:` — grep, do not assume `[ref: CON-7]`
  4. **Validate**: `scripts/update-tomo.sh` dry run shows every intended file as changed; a file listed as unchanged means a missed version bump.
  5. **Success**: the instance would receive every change `[ref: CON-7]`

- [ ] **T6.5 Live validation** `[activity: validate]`

  1. **Prime**: Batch this into a **single** live cycle `[ref: memory: minimize live-test cycles]`. Run `scripts/update-tomo.sh` first, then `/inbox` in the container.
  2. **Test**: against a small real inbox containing at least one note with an embedded image in a subfolder:
     - the suggestions document names the attachment and its destination
     - after approval and apply, the image is at the asset concept path
     - the embed still renders in the moved note
     - **the inbox contains no leftover attachment** — the headline metric, checked in the vault `[ref: PRD/Success Metrics; residue]`
  3. **Implement**: n/a — validation only.
  4. **Validate**: record the outcome and the observed Kado call count in `docs/evolution/inbox-cost-log.md`.
  5. **Success**: inbox residue reaches zero for an all-approved run `[ref: PRD/Success Metrics]`

- [ ] **T6.6 Phase Validation** `[activity: validate]`

  - Full suite green; `ruff` clean. Walk the SDD Quality Requirements table and confirm each row has a passing test. Walk the PRD acceptance criteria and confirm each maps to a green test. Update the spec README status to `Implemented` via `xdd-meta finalize`.
