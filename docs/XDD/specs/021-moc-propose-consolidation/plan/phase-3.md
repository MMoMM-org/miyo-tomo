---
title: "Phase 3: Inbox retire B / keep A+C / Feature 5 / budget"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Inbox retire B / keep A+C / Feature 5 / budget

## Phase Context

**GATE**: Read before starting.

**Specification References**:
- `[ref: SDD/Runtime View Secondary Flow /inbox; ADR-4,10]`
- `[ref: SDD/Cross-Cutting cleanup discipline]`
- `[ref: PRD/Feature 4, Feature 5]`

**Key Decisions**:
- Retire accumulation (Condition B) by deletion, including scaffolding (ADR-10).
- Keep Condition A + Condition C; C now fed by the corrected lean placeholder list.
- Raise `--max-bytes` default 15360 → 40960; `placeholder_mocs` never trimmed (ADR-4).
- Feature 5: `shared_ctx.mocs` is the complete tag-discovered set (notes-area in, template-vault out).

**Dependencies**: Phase 1 (cache feeds shared-ctx via the same `map_notes`). Independent of Phase 2 — `[parallel: true]` with Phase 2 once Phase 1 is done.

---

## Tasks

This phase removes the inbox hot-path coupling and verifies the inbox now matches against the complete, corrected MOC set.

- [ ] **T3.1 Remove accumulation + raise budget in shared-ctx-builder** `[activity: backend-api]` `[ref: SDD/ADR-4,10; shared-ctx-builder.py:229,258,559-639,657]`
  1. Prime: `build_accumulation_index:258`, `enforce_budget:559-639` (Pass-6 trim), `--max-bytes:657`, `build_mocs:209`, `build_placeholder_mocs:229`.
  2. Test (RED): no `accumulation_index` in output; `enforce_budget` no longer references accumulation; `--max-bytes` default 40960; `placeholder_mocs` never trimmed even when over a smaller budget; envelope with corrected placeholder fits.
  3. Implement: delete `build_accumulation_index` + Pass-6 block + the acc counters/return-tuple shape; update callers; raise default; keep placeholder un-trimmed.
  4. Validate: `pytest tests/test_shared_ctx_no_accumulation.py` + existing shared-ctx tests; lint.
  5. Success: accumulation gone, A/C unaffected `[ref: PRD/AC F4#1]`; placeholder un-trimmed @40KB `[ref: PRD/AC F4#5, M6]`.

- [ ] **T3.2 inbox-analyst: delete Condition B, keep A + C** `[activity: backend-api]` `[ref: inbox-analyst.md Step 4; PRD/Feature 4]`
  1. Prime: Step 4 Condition A (Classification Guard), B (Accumulation trigger), C (Placeholder), the A7-vs-B STRICT block (`:162-166`).
  2. Test (RED): with no `accumulation_index`, Conditions A and C produce identical output to pre-021 on a fixed fixture set; placeholder still wins over inferred label (A7 intent preserved without the B block).
  3. Implement: remove the Accumulation sub-block + A7-vs-B STRICT; keep A + C; bump `# version:`. WHY → `docs/tomo/...`.
  4. Validate: fixture-based agent-contract test; confirm no dangling `accumulation_index` reference.
  5. Success: B removed, A/C zero-regression `[ref: PRD/AC F4#1; M3]`; placeholder precedence kept `[ref: PRD/AC F4#4]`.

- [ ] **T3.3 Retire accumulation scaffolding** `[activity: refactor]` `[ref: SDD/Cross-Cutting cleanup; ADR-10; cache-builder.py:312,344-350,428-433]`
  1. Prime: `atomic-note-indexer.py` consumers; `cache-builder` `unclassified_topic_clusters` lift; `/explore-vault` Step 9 invocation.
  2. Test (RED): grep proves no remaining consumer of `atomic-note-indexer` output or `unclassified_topic_clusters`; pipeline still green without them.
  3. Implement: remove `atomic-note-indexer.py` (confirm no other consumer first), the cache-builder lift, and the `/explore-vault` Step 9 accumulation call. Default-to-delete, not patch (`feedback_post_refactor_drop_scaffolding_not_patch`).
  4. Validate: full `pytest`; lint; confirm vault-explorer still runs.
  5. Success: scaffolding gone, suite green `[ref: SDD/ADR-10]`.

- [ ] **T3.4 Feature 5 — inbox sees the complete MOC set** `[activity: backend-api]` `[ref: PRD/Feature 5; M8]`
  1. Prime: `build_mocs:209` reads `cache.map_notes` (now the corrected tag-discovered set from Phase 1).
  2. Test (RED): a notes-area `#type/others/moc` MOC appears in `shared_ctx.mocs` and is offered in `candidate_mocs[]` for a matching item; a template-vault (`X/…`) MOC is absent; item matching a notes-area MOC links to it instead of firing `needs_new_moc`.
  3. Implement: verify the single `map_notes` source feeds `shared_ctx.mocs` (no separate path-only list); add the regression test. (Mostly verification — the fix rides Phase 1.)
  4. Validate: `pytest` Feature-5 test; lint.
  5. Success: notes-area MOC visible, template MOC absent `[ref: PRD/AC F5; M8]`.

- [ ] **T3.5 Phase 3 Validation** `[activity: validate]`
  - Full `pytest`; lint. Verify `shared-ctx.build` emits `accumulation_present=false` and `mocs_count` reflecting the complete set. Confirm Conditions A/C unchanged on fixtures.
