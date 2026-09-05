---
title: "Phase 5: Pipeline wiring and cost accounting"
status: completed
version: "1.0"
phase: 5
---

# Phase 5: Pipeline wiring and cost accounting

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2, ADR-4]`
- `[ref: SDD/Constraints; CON-4]` — constant Kado call cost
- `[ref: SDD/Cross-Cutting Concepts; "Fail open, never guess"]`
- `[ref: PRD/Business rules 3, 9, 10]`, `[ref: PRD/Success Metrics; Cost]`
- Source to read: `inbox-triage.py:150-176` (`discover_files` — `list_dir(inbox_path, depth=1)`, so subfolders are unseen today), `:1521-1533` (`_count_kado_calls`), `:158-175` (the `#93` partition — **must not change**); `kado_client.py:235` (`list_dir`), `:597-617` (pagination), `:33-37` and `:669-679` (retry/429)

**Key Decisions**:
- **ADR-1** — one recursive `list_dir` of the inbox, in addition to the existing `depth=1` call. Do **not** change the existing call's depth; `discover_files` and the `#93` partition depend on its current shape.
- **ADR-2** — extraction runs via `list_notes(inbox_path, fields=["links"])`, filtered to `kind=='embed'` — NOT via regex over note bodies, which the pipeline does not read for fresh inbox items (bodies are read per item inside the inbox-analyst subagent's fan-out, invisible to this pipeline). No analyst change.
- **ADR-4** — correct `_count_kado_calls` here, and note the corrected baseline in the cost log rather than silently rebasing it.

**Dependencies**: Phases 1–4. This phase connects Phase 1's output to the consumers built in 2–4.

---

## Tasks

Connects detection to the run and makes the cost claim measurable.

- [x] **T5.1 Inbox attachment index in the run** `[activity: backend-logic]`

  1. **Prime**: Read `discover_files` at `inbox-triage.py:150-176`. The existing `list_dir(inbox_path, depth=1)` stays exactly as it is; this adds a second, recursive call whose result feeds `build_inbox_index`.
  2. **Test** (RED):
     - the recursive listing is requested once per run, regardless of note count `[ref: CON-4]`
     - the index is built from it and passed to resolution
     - a `KadoError` on the recursive call yields an empty index and the run continues — no exception escapes `[ref: PRD/Business rule 10]`
     - the existing `depth=1` partition behaviour is untouched: a `.png` at the inbox root is still not partitioned as an item `[ref: #93]`
     - pagination is exercised: a subtree of more than 500 entries is fully indexed `[ref: kado_client.py:597-617]`
  3. **Implement**: add the recursive listing and index construction; attach resolved attachment paths to each item before the suggestions stage.
  4. **Validate**: unit tests with a faked `list_dir`; `ruff` clean; `# version:` bumped.
  5. **Success**:
     - [ ] Exactly one additional listing per run `[ref: PRD/Business rule 9]`
     - [ ] Only inbox paths can be resolved `[ref: PRD/Business rule 3]`
     - [ ] The `#93` partition is unchanged `[ref: SDD/Implementation Boundaries; Must Not Touch]`

  **Note — what shipped (Phase 5 is closed; the code is the authority here):** extraction is one
  `list_notes(inbox_path, fields=["links"])` per run, filtering `kind == 'embed'` (ADR-2). Resolution
  happens in `inbox-triage.py` and is persisted to `tomo-tmp/resolved-attachments.json`, keyed by
  source path. `suggestions-reducer.py` merges that map onto each item as it loads
  `items/<stem>.result.json`. `inbox-triage` and `suggestions-reducer` are separate processes, which
  is why this is a file rather than in-memory state.

- [x] **T5.2 Correct the Kado call counter** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: Read `_count_kado_calls` at `:1521-1533`. Its docstring says *"1 listDir + 7 byFrontmatter + N body reads"* but it returns `5 + body_reads`, and it ignores the per-item reads at `:242`, `:315` and `:583`.
  2. **Test** (RED):
     - a run with a known call pattern reports the **actual** number, counted against the faked client's invocation log rather than against a hardcoded expectation `[ref: memory: validators must model execution]`
     - the count includes the per-item reads the current implementation omits
     - the count includes the new recursive listing from T5.1
  3. **Implement**: correct the arithmetic and the docstring together.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**:
     - [ ] The reported number matches the observed call count `[ref: ADR-4]`
     - [ ] The correction is noted in `docs/evolution/inbox-cost-log.md` so historical entries are not silently rebased

- [x] **T5.3 Unresolved and ambiguous reporting** `[activity: backend-logic]`

  1. **Prime**: Read `[ref: SDD/Cross-Cutting Concepts; System-Wide Patterns]` — stderr with the existing `[triage]` prefix convention, plus the suggestions-doc line from T3.2.
  2. **Test** (RED):
     - an unresolved embed emits one stderr line naming the source note and the target
     - an ambiguous embed emits a line naming the candidate count `[ref: PRD/AC-F2.4]`
     - neither produces an action `[ref: PRD/AC-F2.3]`
     - a fully-resolving run emits no such lines
  3. **Implement**: thread the non-resolved refs to the reporting surface.
  4. **Validate**: unit tests capture stderr; `ruff` clean.
  5. **Success**: a silent skip is impossible — every non-resolution is visible `[ref: PRD/Tracking Requirements]`

- [x] **T5.4 Phase Validation** `[activity: validate]`

  - Run all Phase 5 tests plus the full suite. Assert the cost claim directly: a run over 1 note and a run over 20 notes issue the **same** number of Kado calls for attachment handling `[ref: CON-4]`. Confirm no live Kado call is made in tests. `ruff` clean.
