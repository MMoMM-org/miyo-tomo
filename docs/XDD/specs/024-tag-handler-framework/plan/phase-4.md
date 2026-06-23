---
title: "Phase 4: Pass-2 render + guards"
status: in_progress
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

> **Build decomposition note**: the Explore map found approved tag-handler groups are NOT wired from
> suggestions-doc → suggestion-parser → instruction-render. P4 expands to T4.0 (schema $def) + T4.1
> (approval linkage + render) + T4.2 (guards) + T4.3 (validation). Approval linkage = a deterministic
> `group_id()` from (handler, target_path) in `tag-handler-group.py`; reducer renders it as the suggestion
> id, parser extracts approved ids, instruction-render recomputes + matches and reads the group-result
> JSONs as the data source-of-truth. Run sequentially (same files).

Enables Pass-2 to render an approved group into a Hashi `insert_under_marker` instruction and to fail safely when the target note or marker is absent.

- [x] **T4.0 `hashi-instructions.schema.json` — `insert_under_marker` $def** `[activity: data-architecture]`

  1. Prime: Read the current schema (9 actions, shared `anchor`/`placement` $defs) and the handoff contract `[ref: SDD/Section 6; lines: 122-132]`.
  2. Test (RED): a valid `insert_under_marker` instruction (`target_path`, `anchor{type:heading,value}`, `placement`, multi-line `content`) validates; missing `content`/`target_path` fails; reuses the existing `anchor`/`placement` $defs; existing instructions still validate (no regression).
  3. Implement: Add the `insert_under_marker` $def to the `actions[]` oneOf, reusing `anchor`/`placement`.
  4. Validate: `./venv/bin/python` schema tests pass; existing hashi-instructions fixtures still validate.
  5. Success: Schema admits `insert_under_marker` matching the T1.1a handoff contract `[ref: SDD/Section 6; lines: 122-128]`.

- [x] **T4.1 Approval linkage + render: parser + `instruction-render.py` → `insert_under_marker`** `[activity: backend-api]`

  1. Prime: Read the Pass-2 render spec `[ref: SDD/Section 5; lines: 104-110]`, the instruction shape `[ref: SDD/Section 6; lines: 122-128]`, `build_actions`/`_build_*_actions` in instruction-render.py, the suggestion_id convention, and `render_tag_handler_group` in suggestions-reducer.py.
  2. Test (RED): `group_id(group)` is a deterministic slug of (handler, target_path); reducer renders the id as the suggestion id; suggestion-parser extracts approved group ids → confirmed list; `_build_insert_under_marker_actions` loads approved group-result JSONs and emits the instruction (`target_path`, `anchor{type:"heading", value:<marker w/o ##>}`, `placement`, multi-line `content`); `marker`→`anchor.value` strips the `#`-run; cadence appends a new dated block (never replaces); a skipped group emits NO instruction.
  3. Implement: `group_id()` in tag-handler-group.py; reducer renders it; suggestion-parser extracts approved ids; instruction-render `_build_insert_under_marker_actions` (reads `--tag-handler-groups-dir`, matches approved ids).
  4. Validate: `./venv/bin/python` tests pass; emitted instruction matches SDD §6 JSON; approve/skip honored; lint clean.
  5. Success: Approved group → valid `insert_under_marker` instruction `[ref: PRD/FR-10; lines: 73-74]` `[ref: SDD/Section 6; lines: 122-128]`.

- [ ] **T4.2 Guards — missing target (checkbox) + missing marker (error)** `[activity: backend-api]`

  1. Prime: Read the guard spec `[ref: SDD/Section 5; lines: 106-110]` and `[ref: PRD/FR-11,FR-12; lines: 76-80]`.
  2. Test (RED): target_path missing on disk → "create it first" checkbox (daily-note-existence pattern, reducer), **no instruction** until it exists; marker absent in an existing target → error item, **no instruction** (no silent append/relocate); both paths exercised via a **fake-vault read** for marker-existence (FR-12 is a filesystem-access path); happy path (target+marker present) → instruction emitted.
  3. Implement: Add the two guards to the reducer/render path.
  4. Validate: `./venv/bin/python` guard tests pass (both denial paths, Constitution L1); lint clean.
  5. Success: Missing target → checkbox; missing marker → error `[ref: PRD/AC-4; lines: 111]` `[ref: PRD/FR-11,FR-12; lines: 76-80]`.

- [ ] **T4.3 Phase Validation** `[activity: validate]`

  - Run all Phase 4 tests under `./venv/bin/python`. Verify the instruction matches SDD §6 and that both guard denial paths fire (incl. the fake-vault marker read). Lint clean. **Gate: instruction emitted; guards fire (AC-4).**
