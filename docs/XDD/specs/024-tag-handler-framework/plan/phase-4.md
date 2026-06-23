---
title: "Phase 4: Pass-2 render + guards"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Pass-2 render + guards

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Section 5; lines: 104-114]` — Pass-2 render: approved group → `insert_under_marker` instruction reusing anchor machinery; guards; append-dated-block cadence
- `[ref: SDD/Section 6; lines: 115-132]` — the `insert_under_marker` instruction shape (`anchor{type:heading,value}`, `placement`, `content`)
- `[ref: PRD/FR-10; lines: 73-74]` — Pass-2 renders approved group into the instruction
- `[ref: PRD/FR-11,FR-12; lines: 76-80]` — guards: missing target → "create it first"; missing marker → error
- `[ref: PRD/AC-4; lines: 111]` — missing target checkbox; missing marker error

**Key Decisions**:
- Render reuses the existing `anchor` machinery: `type:"heading"`, `value:"<marker w/o ##>"` + `placement` (SDD §5/§6).
- `marker` → `anchor.value` transform: strip leading `#`-run + following space, trim (SDD §2).
- Update cadence (OQ-3): **append a new dated status block** beneath the marker, never replace — history preserved; user review is the idempotency gate (SDD §5).
- Marker-existence is a **filesystem-access path** (FR-12) → needs a fake-vault read in tests, not pre-supplied input (Constitution L1 denial-path coverage).

**Dependencies**:
- Phase 3 (approved group from Pass-1 suggestions) must be complete.

---

## Tasks

Enables Pass-2 to render an approved group into a Hashi `insert_under_marker` instruction and to fail safely when the target note or marker is absent.

- [ ] **T4.1 `instruction-render.py` — render approved group → `insert_under_marker`** `[activity: backend-api]`

  1. Prime: Read the Pass-2 render spec `[ref: SDD/Section 5; lines: 104-110]` and the instruction shape `[ref: SDD/Section 6; lines: 122-128]`.
  2. Test (RED): approved group renders to an `insert_under_marker` instruction with `target_path`, `anchor{type:"heading", value:<marker w/o ##>}`, `placement`, multi-line `content`; `marker` → `anchor.value` transform strips the `#`-run (`"## Captures"` → `"Captures"`); cadence appends a new dated block (does not replace existing content under the marker).
  3. Implement: Extend `instruction-render.py` to emit the `insert_under_marker` instruction reusing the anchor machinery.
  4. Validate: `./venv/bin/python` render tests pass; emitted instruction matches SDD §6 JSON; lint clean.
  5. Success: Approved group → valid `insert_under_marker` instruction `[ref: PRD/FR-10; lines: 73-74]` `[ref: SDD/Section 6; lines: 122-128]`.

- [ ] **T4.2 Guards — missing target (checkbox) + missing marker (error)** `[activity: backend-api]`

  1. Prime: Read the guard spec `[ref: SDD/Section 5; lines: 106-110]` and `[ref: PRD/FR-11,FR-12; lines: 76-80]`.
  2. Test (RED): target_path missing on disk → "create it first" checkbox (daily-note-existence pattern, reducer), **no instruction** until it exists; marker absent in an existing target → error item, **no instruction** (no silent append/relocate); both paths exercised via a **fake-vault read** for marker-existence (FR-12 is a filesystem-access path); happy path (target+marker present) → instruction emitted.
  3. Implement: Add the two guards to the reducer/render path.
  4. Validate: `./venv/bin/python` guard tests pass (both denial paths, Constitution L1); lint clean.
  5. Success: Missing target → checkbox; missing marker → error `[ref: PRD/AC-4; lines: 111]` `[ref: PRD/FR-11,FR-12; lines: 76-80]`.

- [ ] **T4.3 Phase Validation** `[activity: validate]`

  - Run all Phase 4 tests under `./venv/bin/python`. Verify the instruction matches SDD §6 and that both guard denial paths fire (incl. the fake-vault marker read). Lint clean. **Gate: instruction emitted; guards fire (AC-4).**
