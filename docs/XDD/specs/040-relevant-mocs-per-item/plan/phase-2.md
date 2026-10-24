---
title: "Phase 2: Reader selector modes"
status: pending
version: "1.1"
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
- `--mocs-from` never fails the call for an unknown name (opposite of `--fields`); documented in the script's docstring.
- Names arrive in a file because titles are not safe on a command line.
- Every failure exits `1` with one stderr line. Tests assert the exact code and text: on `main` an unknown flag already exits non-zero (argparse, code 2), so "non-zero" proves nothing.

**Dependencies**: Phase 1 (T1.4 — `mocs[].name`, `placeholder_targets`).

---

## Tasks

Lets the analyst read the names of all MOCs and the detail of a chosen few, and refuse a context from another run.

- [ ] **T2.1 `--moc-names`, `--mocs-from`, `--run-id`** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `tomo/scripts/read-shared-ctx.py` (whole file); `tests/test_read_shared_ctx.py`; `docs/tomo/scripts/read-shared-ctx.md` `[ref: SDD/ADR-2, ADR-8]`
  2. Test (RED, exit codes asserted as `== 1` with the SDD's stderr text):
     - `--moc-names` prints every `name` in `mocs` order as compact JSON
     - `--mocs-from` returns exactly one entry per delivered name, including a path-form name; a case/whitespace/NFC variant resolves when unique and is `unresolved` when ambiguous; unknown names land in `unresolved` with exit 0; blank lines and duplicates ignored; the 21st distinct name lands in `omitted`
     - `--mocs-from` with a missing file and with an unreadable file → exit 1, stderr names the file, no stdout
     - `--run-id` mismatch → exit 1, stderr "shared-ctx belongs to run <x>, expected <id>", no stdout; works with every mode including `--fields`; a match changes nothing
     - a context without `name` → `--moc-names` exit 1 "context predates spec 040"
     - exactly-one-mode rule covers five modes
     - a 512-MOC context's `--moc-names` output ≤ 12 KB
  3. Implement: the two modes and the guard; docstring states the non-failing selector semantics and why; WHY in `docs/tomo/scripts/read-shared-ctx.md` (file input, cap, run id); bump version
  4. Validate: RED on `main`; GREEN here; ruff clean
  5. Success: `[ref: PRD/F1-AC1, F1-AC5, F1-AC6, F2-AC5, F6-AC2]`

- [ ] **T2.2 Rebuild the reader's contract fixture from the builder** `[activity: test-practices]`

  1. Prime: `tests/test_read_shared_ctx.py:32-66` (hand-written fixture: `placeholder_links` as strings, no `is_classification`, `tag_prefixes` as `{prefix, values}`), `:136-158` (spill tests: Step-1 batch and a `--fields mocs,…,placeholder_links` call), `:188-194` (`TestKeys` pins `placeholder_links`), `:225-252` (`TestAgainstTheRealContract`) `[ref: SDD/Technical Debt]`
  2. Test: the fixture validates against `shared-ctx.schema.json`; `TestKeys` expects `placeholder_targets`; the spill tests measure the Step-1 batch and `--moc-names`; `TestAgainstTheRealContract` still resolves every `shared_ctx.<path>` the current analyst prose names
  3. Implement: generate the fixture with the builder's functions over a small cache fixture; update the three test groups with the reason
  4. Validate: suite green; ruff clean
  5. Success: the contract test checks the real shape, not a stale copy `[ref: SDD/Technical Debt]`
