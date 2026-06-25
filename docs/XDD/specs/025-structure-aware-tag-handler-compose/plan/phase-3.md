---
title: "Phase 3: Producer-Chain Propagation"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Producer-Chain Propagation

## Phase Context

**GATE**: Read before starting.
- `[ref: SDD/ADR... Producer-chain propagation]` (the research-found gap)
- `tomo/scripts/tag-handler-resolve.py` (`resolve_item` :118, return dict :206-215)
- `tomo/scripts/tag-handler-group.py` (`group_handled` :33/:61-70)

**Key Decisions**: `output_format` must flow resolve → group → stub, or it never reaches the interpreter.
This is additive plumbing; the schema (Phase 1) must already accept the field.

**Dependencies**: **Phase 1 complete & green** (CON-1 gate).

---

## Tasks

Carries the new config field through the producer hops so the interpreter receives it.

- [x] **T3.1 Resolver carries `output_format`** `[activity: backend-logic]`
  1. Prime: read `resolve_item` and its return dict `[ref: SDD/CON-1]`
  2. Test (RED): a handler config with `output_format` → `resolve_item` return dict includes `output_format`
     verbatim; a config without it → key absent/None (backward compat).
  3. Implement (GREEN): add `output_format` to the `resolve_item` return dict (:206-215). Bump version.
  4. Validate: `./venv/bin/python -m pytest tests/ -k tag_handler_resolve -q`; ruff clean.
  - Success: `[ref: PRD/FR-15]` output_format survives resolution.

- [x] **T3.2 Grouper carries `output_format` into the stub** `[activity: backend-logic]`
  1. Prime: read `group_handled` carry-through `[ref: SDD/Runtime View]`
  2. Test (RED): grouping handled items that share (handler,target) → the stub carries `output_format`;
     mixed handlers keep their own; absent → absent.
  3. Implement (GREEN): propagate `output_format` in `group_handled` (:61-70) into the stub JSON. Bump version.
  4. Validate: grouper tests green; ruff clean.
  - Success: `[ref: SDD/Runtime View step 3]` stub carries output_format end-to-end.

- [x] **T3.3 Phase Validation** `[activity: validate]`
  - Resolve→group round-trip test proving `output_format` reaches the stub unchanged; full suite green for
    touched modules; ruff clean.
