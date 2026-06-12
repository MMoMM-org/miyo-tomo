---
title: "Phase 2: Analyst Step 7.5 segmentation"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Analyst Step 7.5 segmentation

## Phase Context

**GATE**: Read the referenced files before starting.

**Specification References**:
- `[ref: SDD/Solution Strategy; Runtime View — Primary Flow]`
- `[ref: SDD/ADR-1 agent-side; ADR-2 N actions; ADR-3 >200w gate]`
- `[ref: PRD/A1, A2, A3, §8 OQ2/OQ3/OQ4]`

**Key Decisions**:
- ADR-1: insert `Step 7.5 — Topical segmentation` between `inbox-analyst.md:194` and `:195`.
- ADR-3: gate on body `> 200 words`; ≤200w → `threads = [single_default_thread]` (today's path).
- OQ2: LLM prompt with 2–3 worked examples in the agent body. OQ3: score topics per-thread. OQ4: daily-log entry summarises the daily-log thread ONLY.
- Score each thread against its FULL thread text (mirror the voice-transcript rule at `:178-183`).

**Dependencies**: Phase 1 (source_stem field must exist before the analyst emits it).

---

## Tasks

Delivers the only NEW behaviour: an LLM segmentation pass that turns a long multi-thread item into N atomic actions, each provenance-stamped.

- [x] **T2.1 Step 7.5 segmentation + per-thread emission** `[activity: agent-prompt]`

  1. Prime: Read `inbox-analyst.md` Step 7 (`:167-193`), Step 9 emission (`:456-495`), coexistence table (`:474-482`), voice rules (`:178-183`) `[ref: SDD/Code Context]`
  2. Test (RED) — output-contract tests against `item-result.schema.json`:
     - single-thread item → exactly 1 `create_atomic_note` with `source_stem`, byte-identical fields to today (regression) `[ref: PRD/A1]`
     - multi-thread item (>200w, 2 concepts) → 2 `create_atomic_note`, each thread-scoped title/MOC/tags + shared `source_stem` `[ref: PRD/A2]`
     - ≤200-word item → segmentation skipped, single default thread `[ref: SDD/ADR-3]`
     - 3-thread item (1 daily + 2 atomic) → 2 atomics + 1 `update_daily` summarising the daily thread only `[ref: PRD/A9, OQ4]`
  3. Implement (GREEN): insert Step 7.5 (LLM lists distinct concepts, 2–3 worked examples, per-thread worthiness ≥0.5 gate, >200w pre-check); update Step 9 to iterate threads and stamp `source_stem` on every atomic; bump `# version:`.
  4. Validate: contract tests pass; `./scripts/update-tomo.sh` syncs; live spot-check against the Apothekerpfädchen fixture (deferred full E2E to P6).
  5. Success:
     - [x] multi-thread → N atomics `[ref: PRD/A2]`
     - [x] single-thread regression intact `[ref: PRD/CON-2]`
     - [x] >200w gate honoured `[ref: SDD/ADR-3]`
     - [x] every atomic carries `source_stem` `[ref: PRD/A3]`

- [x] **T2.2 Phase Validation** `[activity: validate]`

  Run analyst contract tests; verify `# version:` bumped + instance synced; confirm no schema-invalid fields emitted (validate-result strips them silently — SDD Gotchas).
