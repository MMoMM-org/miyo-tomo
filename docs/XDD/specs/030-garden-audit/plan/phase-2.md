---
title: "Phase 2: Scan Orchestrator"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Scan Orchestrator

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — garden-audit.py]`
- `[ref: SDD/ADR-5 — check→action mapping + data-source split]`
- `[ref: SDD/Runtime View — Primary Flow steps 3-4]`
- `tomo/scripts/lib/orphan_link.py`, `tomo/scripts/lib/moc_cache_loader.py`, `tomo/scripts/moc-tree-builder.py` (up_state/up_target)

**Key Decisions**: ADR-5 (cache for unparented/broken-`up::`/duplicate-stems; `graph_audit` for orphan/dead-link; `listDir` modified for stale-MOC). Broken-`up::` is cache-only.

**Dependencies**: Phase 1 (T1.1 `graph_audit`, T1.2 exclusions).

---

## Tasks

Produces the classified, prioritised, exclusion-filtered findings as `garden-audit-doc.json`.

- [ ] **T2.1 `garden-audit.py` scan orchestrator** `[activity: backend]`

  1. Prime: Read orphan_link (`emit_orphan_suggestions`), moc_cache_loader (`cache.entries` fields), moc-tree-builder (`up_state`/`up_target`), and `[ref: SDD/ADR-5]`.
  2. Test (per check, with fake cache + fake graph_audit + fake listDir):
     - unparented (`up_state=="absent"`) → finding with candidate MOCs (reuse orphan_link scoring);
     - orphan (from `graph_audit orphans[]`);
     - broken-`up::` (`up_state=="broken"` + `up_target`) — **no graph call**;
     - dead-link (from `graph_audit deadLinks[]`, source+target+count);
     - duplicate-stems (group `entries[].stem`);
     - stale-MOC (`listDir` modified older than threshold);
     - exclusions filter applied (per-check + complete); severity ordering (integrity > structure > advisory);
     - empty cache / zero findings / graph-unavailable (checks 2+4 marked "not run", cache checks still produced).
  3. Implement: `tomo/scripts/garden-audit.py` + `tomo/schemas/garden-audit-doc.schema.json`. Emits `garden-audit-doc.json`.
  4. Validate: `pytest tests/test_garden_audit_scan.py`; schema-valid output; ruff clean.
  - Success: all six checks produced + filtered + severity-ordered `[ref: PRD/Feature 1 ACs]`; broken-`up::` uses zero graph calls `[ref: SDD/ADR-5]`; graceful partial on graph-unavailable `[ref: SDD/Error Handling]`.

- [ ] **T2.2 Phase Validation** `[activity: validate]`

  - Run all Phase 2 tests; ruff clean. Verify `garden-audit-doc.json` conforms to its schema and covers every PRD Feature-1 check.
