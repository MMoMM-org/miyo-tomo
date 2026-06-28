---
title: "Phase 1: Deterministic Safety Scripts (L1 gate)"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Deterministic Safety Scripts (L1 gate)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-9]` — extract safety logic to testable scripts (Constitution L1)
- `[ref: SDD/ADR-4]` — `.base`/`.canvas` parse-gate before write
- `[ref: SDD/ADR-7]` — collision via `--no-overwrite`
- `[ref: SDD/Test Strategy]` — happy + failure per write path
- `[ref: tomo/scripts/kado-write-file.py; lines: 78-84]` — existing extension branch to extend

**Key Decisions**:
- Safety properties (no malformed JSON written, no silent overwrite) must be deterministic + unit-tested,
  not LLM-judged. `inbox-author` invokes these scripts; it does not implement the logic in prose.

**Dependencies**: none. **This phase gates Phases 3 and 4.**

---

## Tasks

This phase delivers the two deterministic guards the skills depend on, each with happy + failure tests.

- [ ] **T1.1 validate-json.py parse-gate** `[activity: backend-api]`

  1. Prime: Read ADR-4/ADR-9 and the staging flow `[ref: SDD/Runtime View; SDD/ADR-9]`.
  2. Test (`tests/test_validate_json.py`): valid `.base`/`.canvas` JSON → exit 0; malformed JSON → exit 1
     with an error message on stderr; the validator writes nothing; non-existent input → exit 1.
  3. Implement: `tomo/scripts/validate-json.py <path>` — `json.loads` the file; exit 0/1; print parse
     error on failure. Header `# version: 0.1.0`. Docstring carries the WHY (script-header carve-out).
  4. Validate: `./venv/bin/python -m pytest tests/test_validate_json.py`; `./venv/bin/ruff check`.
  5. Success: invalid JSON never passes the gate `[ref: PRD/Feature 4 AC; SDD/Test Strategy]`; WHY doc
     `docs/tomo/scripts/validate-json.md` exists.

- [ ] **T1.2 kado-write-file.py --no-overwrite** `[activity: backend-api]`

  1. Prime: Read the existing write branch `[ref: tomo/scripts/kado-write-file.py; lines: 78-84]` and
     `kado_client` read methods for existence checks `[ref: tomo/scripts/lib/kado_client.py]`.
  2. Test (`tests/test_kado_write_file_no_overwrite.py`, fake/mock Kado — patch `client._call_tool`
     per the existing fake-Kado pattern): `--no-overwrite` + existing vault path → refuses with the
     **defined "exists" signal: exit code 3 + `EXISTS:<vault-path>` on stdout** (lock this contract
     here — T4.2 reads it); absent path → writes normally (exit 0); exercise a non-`.md` extension
     (`.base`/`.canvas`) through `operation=file`/`write_file` (happy) and a write-denial (failure).
  3. Implement: add `--no-overwrite` to `kado-write-file.py`; pre-check vault-path existence via
     `kado_client`; on exists print `EXISTS:<path>` and exit 3 without writing. Bump `# version`.
  4. Validate: `./venv/bin/python -m pytest tests/test_kado_write_file_no_overwrite.py`; ruff clean.
  5. Success: collision is detected deterministically `[ref: PRD/Feature 4 AC; SDD/ADR-7]`; non-`.md`
     write path tested `[ref: SDD/Test Strategy]`.

- [ ] **T1.3 Phase Validation** `[activity: validate]`

  - Run all Phase 1 tests under `./venv/bin/python`. Confirm both scripts fail-closed on the failure
    cases. Lint clean. No skill work begins until this phase is green.
