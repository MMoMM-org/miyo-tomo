---
title: "Phase 3: Inbox retire B / keep A+C / Feature 5 / budget"
status: in_progress
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

- [x] **T3.0 Capture A/C golden baseline (do FIRST, before removing B)** `[activity: testing]` `[ref: PRD/Should-Have golden baseline; M3; M9]`
  1. Prime: the named inbox fixture set; current Condition A + C output path.
  2. Test (RED): run pre-021 `/inbox` Conditions A + C on the fixtures, capture output as a golden file under `tests/fixtures/021-ac-baseline/`.
  3. Implement: commit the golden file; later tasks assert byte-equality against it.
  4. Validate: golden file exists and is non-empty.
  5. Success: baseline captured before B-removal `[ref: PRD/M3]`.

- [x] **T3.1 Remove accumulation + raise budget in shared-ctx-builder** `[activity: backend-api]` `[ref: SDD/ADR-4,10 (H3); shared-ctx-builder.py:229,258,559-639,657; shared-ctx.schema.json:59]`
  1. Prime: `build_accumulation_index:258`, `enforce_budget:559-639` (Pass-6 trim), `--max-bytes:657`, `build_mocs:209`, `build_placeholder_mocs:229`; the `accumulation_index` property in `shared-ctx.schema.json` (H3).
  2. Test (RED): no `accumulation_index` in output; `enforce_budget` no longer references accumulation; `--max-bytes` default 40960; `placeholder_mocs` never trimmed even when over a smaller budget; envelope with corrected placeholder fits; **schema no longer declares `accumulation_index` and still validates a no-accumulation ctx (H3).**
  3. Implement: delete `build_accumulation_index` + Pass-6 block + the acc counters/return-tuple shape; update callers; raise default; keep placeholder un-trimmed; **remove the `accumulation_index` property from `shared-ctx.schema.json` (H3).**
  4. Validate: `pytest tests/test_shared_ctx_no_accumulation.py` + existing shared-ctx + schema tests; lint.
  5. Success: accumulation gone (incl. schema), A/C unaffected `[ref: PRD/AC F4#1]`; placeholder un-trimmed @40KB `[ref: PRD/AC F4#5, M6]`.

- [x] **T3.2 inbox-analyst: delete Condition B, keep A + C** `[activity: backend-api]` `[ref: inbox-analyst.md Step 4; PRD/Feature 4]`
  1. Prime: Step 4 Condition A (Classification Guard), B (Accumulation trigger), C (Placeholder), the A7-vs-B STRICT block (`:162-166`); the T3.0 golden baseline.
  2. Test (RED): with no `accumulation_index`, Conditions A and C produce output **byte-equal to the T3.0 golden baseline** on the fixture set (not shape-only); **Condition C still emits `needs_new_moc: true` + `proposed_moc_topic = <target>` with verbatim casing on a placeholder-match fixture (F4#2)**; placeholder still wins over inferred label (A7 intent preserved without the B block, F4#4).
  3. Implement: remove the Accumulation sub-block + A7-vs-B STRICT; keep A + C; bump `# version:`. WHY → `docs/tomo/...`.
  4. Validate: golden-baseline + Condition-C-casing tests; confirm no dangling `accumulation_index` reference.
  5. Success: B removed, A/C byte-equal to baseline `[ref: PRD/AC F4#1; M3]`; Condition C casing preserved `[ref: PRD/AC F4#2]`; placeholder precedence kept `[ref: PRD/AC F4#4]`.

- [x] **T3.3 Retire accumulation scaffolding (full scope, H1)** `[activity: refactor]` `[ref: SDD/Cross-Cutting cleanup (H1); ADR-10; cache-builder.py:312,344-350,428-433]`
  1. Prime: ALL accumulation consumers (H1): `atomic-note-indexer.py`; `cache-builder` `unclassified_topic_clusters` lift; `vault-explorer.md` Step 9 indexer call + Step 10 `accumulation_cluster_count`; `vault-summary.py` `_extract_accumulation_count`; `tomo.accumulation` config block; `tomo-help.md` + `lyt-patterns/SKILL.md` prose; `test_shared_ctx_accumulation.py`.
  2. Test (RED): repo-wide `rg` proves zero remaining consumer of `atomic-note-indexer` output, `unclassified_topic_clusters`, or `accumulation_cluster_count`; pipeline green without them.
  3. Implement (delete, don't patch — `feedback_post_refactor_drop_scaffolding_not_patch`): remove `atomic-note-indexer.py`, the cache-builder lift, the `vault-explorer.md` Step 9 indexer call + `--accumulation` (wire force-rebuild of the new builder) + Step 10 field, `vault-summary.py` `_extract_accumulation_count` + output field, the `tomo.accumulation` config block, the help/skill prose; retire/replace `test_shared_ctx_accumulation.py`. Bump versions on every edited runtime file.
  4. Validate: full `pytest`; lint; run `vault-summary`/`vault-explorer` paths; skill/agent author audit on edited agents (`feedback_audit_skills_agents_after_edits`).
  5. Success: scaffolding gone across ALL listed sites, suite green `[ref: SDD/ADR-10 (H1)]`.

- [x] **T3.4 Feature 5 — inbox sees the complete MOC set** `[activity: backend-api]` `[ref: PRD/Feature 5; M8]`
  1. Prime: `build_mocs:209` reads `cache.map_notes` (now the corrected tag-discovered set from Phase 1).
  2. Test (RED) — one per F5 AC:
     - (F5#1) a notes-area `#type/others/moc` MOC appears in `shared_ctx.mocs` AND is offered in `candidate_mocs[]` for a matching item;
     - (F5#2) a template-vault (`X/…`) MOC is ABSENT from `shared_ctx.mocs`;
     - (F5#3) `shared_ctx.mocs` derives from the single `map_notes` source — assert there is NO separate/path-only MOC list in `build_mocs` (negative assertion);
     - (F5#4) an item matching a notes-area MOC links to it instead of firing `needs_new_moc`.
  3. Implement: verify the single `map_notes` source feeds `shared_ctx.mocs`; add the four regression tests. (Mostly verification — the fix rides Phase 1.)
  4. Validate: `pytest` Feature-5 tests; lint.
  5. Success: all four F5 ACs asserted `[ref: PRD/AC F5#1-4; M8]`.

- [ ] **T3.5 Phase 3 Validation** `[activity: validate]`
  - Full `pytest`; lint. Verify `shared-ctx.build` emits `accumulation_present=false` and `mocs_count` reflecting the complete set. Confirm Conditions A/C unchanged on fixtures.
