---
title: "Phase 2: Triage detection"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Triage detection

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Section 5; lines: 84-93]` — triage integration: run resolver after `compute_new_sources`, add `handled[]`, exclude from `suggest` lane
- `[ref: PRD/FR-3; lines: 54-55]` — mark matched item with handler id + bound vars; unmatched unchanged
- `[ref: PRD/AC-5; lines: 112]` — empty-registry run byte-identical
- `[ref: PRD/C1; lines: 117-118]` — additive-only on hot paths

**Key Decisions**:
- `routing-plan.schema.json` is `additionalProperties:false`, so it **must be extended** with `handled[]` (and possibly a `handle` action value) before triage can emit it — this is the one non-pure-additive change (SDD §5).
- To preserve AC-5, triage **omits the `handled` key entirely** when the registry is empty / nothing matched — an empty `handled:[]` would validate but emitting nothing keeps the run byte-identical and schema-valid before the extension lands (SDD §5).

**Dependencies**:
- Phase 1 (T1.3 resolver) must be complete — triage calls the resolver.
- T2.0 (schema extension) is a **prereq for T2.1**.

---

## Tasks

Enables `/inbox` triage to recognize registered-tag notes and partition them out of the generic suggest lane — without changing behavior when no handler is registered.

- [x] **T2.0 Extend `tomo/schemas/routing-plan.schema.json`** `[activity: data-architecture]`

  1. Prime: Read the schema-change requirement `[ref: SDD/Section 5; lines: 89-93]` and the current `routing-plan.schema.json` (`additionalProperties:false`).
  2. Test (RED): a routing plan **with** a `handled[]` array validates; the `handled[]` entry shape (`{path, handler, vars, target_path, action, …}`) validates; a routing plan **without** `handled` still validates (omission is legal); add the `handle` action enum value only if needed and assert pre-existing plans remain valid.
  3. Implement: Extend `tomo/schemas/routing-plan.schema.json` with the `handled[]` property (and `handle` action value if required).
  4. Validate: `./venv/bin/python` schema tests pass; existing routing-plan fixtures still validate.
  5. Success: Schema admits `handled[]` while keeping every current plan valid `[ref: SDD/Section 5; lines: 89-93]`.

- [ ] **T2.1 `inbox-triage.py` — detect & partition handled items** `[activity: backend-api]`

  1. Prime: Read the triage integration spec `[ref: SDD/Section 5; lines: 84-93]` and the resolver output contract `[ref: SDD/Section 3; lines: 56-67]`.
  2. Test (RED): handled-item partition (matched item → `handled[]`, excluded from `suggest` lane); **empty-registry identity** (no `handled` key emitted, output byte-identical & schema-valid — AC-5); mixed batch (some handled, some generic → both lanes correct); unmatched item path unchanged.
  3. Implement: In `inbox-triage.py`, after `compute_new_sources`, run `tag-handler-resolve` over each new source's tags+frontmatter; add `handled[]` to `routing-plan.json`; exclude handled items from `suggest`. **Omit the `handled` key entirely when empty.**
  4. Validate: `./venv/bin/python` triage tests pass; empty-registry golden run diff is empty; lint clean.
  5. Success: Handled items partitioned; empty registry byte-identical `[ref: PRD/AC-5; lines: 112]` `[ref: PRD/FR-3; lines: 54-55]`.

- [ ] **T2.2 Phase Validation** `[activity: validate]`

  - Run all Phase 2 tests under `./venv/bin/python`. Verify the byte-identity gate (empty registry → no `handled` key, identical output) and the handled/suggest partition against SDD §5. Lint clean. **Gate: empty-registry byte-identity (AC-5).**
