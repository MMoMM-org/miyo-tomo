---
title: "Phase 1: Data & Config Foundations"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Data & Config Foundations

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — kado_client.graph_audit()]`
- `[ref: SDD/Interface Specifications — Exclusion config]`
- `[ref: SDD/ADR-2, ADR-5]`
- `[ref: SDD/Constraints — CON-4]`
- `_inbox/from-kado/2026-07-18_kado-to-tomo_graph-audit-contract.md` (response shape)

**Key Decisions**: ADR-2 (skill-owned instance exclusion config, seed pattern), ADR-5 (data-source split; `kado-graph-audit` for orphan/dead-link).

**Dependencies**: none — these are the primitives every later phase consumes.

---

## Tasks

Establishes the two external/data primitives (bulk graph access, exclusion config) and guarantees the config survives instance updates.

- [x] **T1.1 `kado_client.graph_audit()` wrapper + fixtures** `[activity: integration]` `[parallel: true]`

  1. Prime: Read `tomo/scripts/lib/kado_client.py` (`_call_tool` retry/backoff, existing cursor loops) and the kado-graph-audit contract.
  2. Test: cursor pagination concatenates orphans-first-then-deadLinks across ≥2 pages; single-page (`cursor:null`) returns all; `include`/`limit` passthrough; **camelCase `deadLinks`** read correctly; empty response → empty arrays. Use a fake client + a real-shaped fixture.
  3. Implement: add `graph_audit(include=None, limit=None)` to `KadoClient` (cursor loop; inherits 429/backoff).
  4. Validate: `pytest tests/test_kado_client_graph_audit.py`; ruff clean.
  - Success: vault-wide orphans + deadLinks fetched in O(1)-per-page calls `[ref: PRD/Feature 4 AC-1]`; contract fields match `[ref: SDD/ADR-5]`.

- [x] **T1.2 `lib/garden_exclusions.py` + config schema** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/Interface Specifications — Exclusion config]` and an existing schema (e.g. `tomo/schemas/suggestions-wire.schema.json`) for style.
  2. Test: `is_excluded(entry, check)` honours target type note/path/tag × scope per-check/complete; permanent always excludes; temporary excludes only before `until`; expired temporary → not excluded AND surfaced as "reappeared"; malformed/missing config → empty (fail-open, no crash).
  3. Implement: `tomo/scripts/lib/garden_exclusions.py` (load, expire, `is_excluded`) + `tomo/schemas/garden-audit-exclusions.schema.json`.
  4. Validate: `pytest tests/test_garden_exclusions.py`; schema validates the sample config; ruff clean.
  - Success: exclusions filter per-check or complete, permanent + temporary-with-expiry `[ref: PRD/Feature 5 ACs]`.

- [x] **T1.3 Seed the exclusion config + update-script protection (CON-4)** `[activity: platform]` `[parallel: true]`

  1. Prime: Read `scripts/update-tomo.sh` (`add_seed`/`scan_seed`, the `config/tag-handlers/*` seed loop, the retire sweep) and `scripts/install-tomo.sh` config handling.
  2. Test: after `update-tomo` on an instance with a user-edited `config/garden-audit-exclusions.yaml`, the file is **unchanged** (create-only); on a fresh instance it is **created**; it is NEVER listed for retire/delete. Cover via an isolated-tmpdir install/update test (never touch the real instance).
  3. Implement: register `config/garden-audit-exclusions.yaml` with `add_seed` in BOTH `install-tomo.sh` and `update-tomo.sh`; ensure the retire sweep excludes it.
  4. Validate: `pytest`/integration test in an isolated tmpdir; manual `scan_seed` dry-run shows `current|user-owned (preserved)`.
  - Success: permanent exclusions are never deleted by an update `[ref: SDD/CON-4]` `[ref: SDD/Risks — update-script config protection]`.

- [x] **T1.4 Phase Validation** `[activity: validate]`

  - Run all Phase 1 tests; ruff clean. Confirm the three primitives are independently usable by Phase 2.
