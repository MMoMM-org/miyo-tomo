---
title: "Phase 2: Reader selector modes"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Reader selector modes

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-2]` — `--moc-names`, `--mocs-from <file>`, output shape, cap
- `[ref: SDD/ADR-8]` — `--run-id`
- `[ref: SDD/Interface Specifications; "read-shared-ctx.py"]`
- `[ref: SDD/Error Handling]`

**Key Decisions**:
- `--mocs-from` never fails the call for an unknown name (opposite of `--fields`); this is deliberate and documented in the script's docstring.
- Names arrive in a file because titles are not safe on a command line.

**Dependencies**: Phase 1 (T1.3 — `mocs[].name` exists).

---

## Tasks

Lets the analyst read the names of all MOCs and the detail of a chosen few, and refuse a context from another run.

- [ ] **T2.1 `--moc-names`, `--mocs-from`, `--run-id`** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `tomo/scripts/read-shared-ctx.py` (whole file, `:52-141`); `tests/test_read_shared_ctx.py`; `docs/tomo/scripts/read-shared-ctx.md` `[ref: SDD/ADR-2, ADR-8]`
  2. Test (RED): `--moc-names` prints every `name` in `mocs` order as compact JSON; `--mocs-from` returns exactly one entry per delivered name, including a path-form name; a name differing only in case/whitespace/NFC resolves when unique and is `unresolved` when ambiguous; unknown names land in `unresolved`, exit 0; blank lines and duplicates ignored; the 21st distinct name lands in `omitted`; `--run-id` mismatch exits 1 with no stdout and works with every mode, including `--fields`; a context without `name` makes `--moc-names` exit 1 with "context predates spec 040"; exactly-one-mode rule extended to five modes; a 512-MOC context's `--moc-names` output ≤ 12 KB
  3. Implement: the two modes and the guard in `read-shared-ctx.py`; docstring states the selector's non-failing semantics and why; `docs/tomo/scripts/read-shared-ctx.md` gains the WHY (file input, cap, run-id); bump version
  4. Validate: RED on main; GREEN here; ruff clean
  5. Success: `[ref: PRD/F1-AC1, F1-AC5, F1-AC6, F2-AC5, F6-AC2]`

- [ ] **T2.2 Rebuild the reader's contract fixture from the builder** `[activity: test-practices]`

  1. Prime: `tests/test_read_shared_ctx.py:33-66` (hand-written fixture, already off-schema), `:225-252` (`TestAgainstTheRealContract`) `[ref: SDD/Technical Debt; SDD/Implementation Gotchas]`
  2. Test: the fixture validates against `shared-ctx.schema.json`; `TestAgainstTheRealContract` still resolves every `shared_ctx.<path>` named in today's analyst prose (Phase 4 will add new names)
  3. Implement: generate the fixture from `shared-ctx-builder` functions over a small cache fixture instead of hand-writing it; keep the spill-floor tests meaningful (they now measure the Step-1 batch and `--moc-names`, not `--field mocs`)
  4. Validate: suite green; ruff clean
  5. Success: the contract test checks the real shape, not a stale copy `[ref: SDD/Technical Debt]`
