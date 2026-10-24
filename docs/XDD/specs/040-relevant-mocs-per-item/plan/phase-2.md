---
title: "Phase 2: Reader selector modes"
status: in_progress
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

Lets the analyst read the names of all MOCs and the detail of a nominated few, and refuse a context from another run.

- [x] **T2.1 `--moc-names`, `--mocs-from`, `--run-id`** `[activity: backend-api]` `[parallel: true]`

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

  6. Notes recorded during implementation (2026-10-24):
     - Tests in `tests/test_040_reader_modes.py` run the script as a subprocess, so exit codes and stdout/stderr are asserted exactly as the analyst's Bash call sees them. RED: 23 of 23 fail against `main`'s reader.
     - Contexts in those tests are built with the builder's `build_mocs`, so `name` follows the real collision rule.
     - "Distinct" means distinct lines after stripping. Two lines that resolve to the same MOC (`Projects`, `projects`) count toward the cap of 20 separately but return one entry.
     - The usage-error test asserts the rule's own text (`choose exactly one of`). Without that, the two-mode case passed on `main`, because argparse's "unrecognized arguments" also names both flags.

- [x] **T2.2 Rebuild the reader's contract fixture from the builder** `[activity: test-practices]`

  1. Prime: `tests/test_read_shared_ctx.py:32-66` (hand-written fixture: `placeholder_links` as strings, no `is_classification`, `tag_prefixes` as `{prefix, values}`), `:136-158` (spill tests: Step-1 batch and a `--fields mocs,…,placeholder_links` call), `:188-194` (`TestKeys` pins `placeholder_links`), `:225-252` (`TestAgainstTheRealContract`) `[ref: SDD/Technical Debt]`
  2. Test: the fixture validates against `shared-ctx.schema.json`; `TestKeys` expects `placeholder_targets`; the spill tests measure the Step-1 batch and `--moc-names`; `TestAgainstTheRealContract` still resolves every `shared_ctx.<path>` the current analyst prose names
  3. Implement: generate the fixture with the builder's functions over a small cache fixture; update the three test groups with the reason
  4. Validate: suite green; ruff clean
  5. Success: the contract test checks the real shape, not a stale copy `[ref: SDD/Technical Debt]`

  6. Findings recorded during implementation (2026-10-24):
     - The fixture is the builder's own output: `shared-ctx-builder.py` runs once per session over a small cache and vault-config (`_built()`), and `test_fixture_is_a_valid_built_context` validates it against the schema.
     - The real shape surfaced a pre-existing dead reference. `inbox-analyst.md` Step 8 branches on `shared_ctx.daily_notes.daily_log.enabled`, but the builder never emits that key and the schema forbids it. The hand-written fixture modelled the key, so the contract test had passed. It is out of scope for spec 040. It is recorded in `docs/XDD/backlog.md` and listed as `KNOWN_DEAD_REFERENCES` in the test.
     - `TestAgainstTheRealContract` now asserts the exact set of unresolved paths. `PENDING_PHASE_4 = ["placeholder_links"]` is the tripwire: once T4.2 rewrites Step 4, the test fails until that entry is removed.
     - The spill test "loading every contract key stays under the whole file" was replaced by "`--moc-names` costs less than a third of `--field mocs`". The old call loaded `placeholder_links`, which no longer exists.
     - `read-shared-ctx.py` 0.3.1: its `--field` help example named the dead key; it now uses `cutoff_days`.
