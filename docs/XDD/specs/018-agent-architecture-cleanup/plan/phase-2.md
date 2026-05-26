---
title: "Phase 2: Triage Script (Layer A)"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Triage Script (Layer A)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples — inbox-triage.py Algorithm; lines: 629-693]`
- `[ref: SDD/Implementation Examples — Coverage Computation — Traced Walkthrough; lines: 695-711]`
- `[ref: SDD/Interface Specifications — inbox-cache Structure; lines: 508-520]`
- `[ref: SDD/Runtime View — Complex Logic: Action Determination; lines: 853-869]`
- `[ref: SDD/Implementation Gotchas; lines: 1086-1112]`
- `[ref: PRD/F-1; lines: 128-135]`
- `[ref: PRD/F-5; lines: 155-159]`

**Key Decisions**:
- ADR-1: Triage-first — all routing decisions deterministic, before any LLM context
- ADR-7: `fan-resolve` action routes to suggestion-conductor (analysis work)
- Kado query strategy: 1 listDir + 4 byFrontmatter = 5 Kado calls (SDD §Implementation Gotchas)
- Approval scanning requires full body reads (no Kado partial-body)
- Existing `inbox-discovery.py` (247 lines) is replaced, not wrapped

**Dependencies**:
- Phase 1 (T1.1 routing-plan.schema.json, T1.2 doc-frontmatter sources[]) — triage validates output against routing-plan schema and reads sources[] for coverage

---

## Tasks

Builds the deterministic triage script that replaces LLM-based auto-discovery. The script scans inbox state via Kado, computes routing decisions, and emits `routing-plan.json` + local file cache.

- [ ] **T2.1 inbox-triage.py — discovery, bucketing & caching** `[activity: backend-implementation]`

  1. Prime: Read `tomo/scripts/inbox-discovery.py` (being replaced) `[ref: tomo/scripts/inbox-discovery.py]`; read SDD algorithm steps 1-6 `[ref: SDD/Implementation Examples — inbox-triage.py Algorithm; lines: 629-661]`; read kado_client patterns `[ref: tomo/scripts/lib/kado_client.py]`
  2. Test: Script discovers all file types via listDir; partitions audio vs .md; queries 4 frontmatter buckets (pending-approval, pending-accept, captured, instructions by doc_type); computes new_sources as files not in any bucket; reads approval checkboxes from full doc bodies (`[x] Approved` for suggestions/fan, `[x] Accept` for moc-proposals); detects `[x] Force Atomic Note` per suggestion item; caches read bodies to `tomo-tmp/inbox-cache/` with manifest.json; handles Kado unreachable (exit 1) and kado-read failures (skip + drift indicator)
  3. Implement: Create `tomo/scripts/inbox-triage.py` with CLI interface (`--inbox-path`, `--force-pass1`, `--force-pass2`, `--recover`). Steps 1-6 of SDD algorithm. Uses `kado_client` for Kado calls. Writes cache files with flat naming (vault filename preserved). Writes `manifest.json` with `{filename: {vault_path, checksum, cached_at}}`. Create `tests/test_inbox_triage.py` with comprehensive unit tests
  4. Validate: `python3 -m pytest tests/test_inbox_triage.py -v`; `python3 -m ruff check tomo/scripts/inbox-triage.py`
  5. Success:
     - [ ] MOC-proposals discovered and bucketed correctly `[ref: PRD/AC-1]` `[ref: PRD/AC-3]`
     - [ ] Approval checkbox scanning works for all doc types `[ref: PRD/F-5]`
     - [ ] Cache populated with full doc bodies `[ref: PRD/AC-5]`
     - [ ] Kado failure handling per SDD error table `[ref: SDD/Error Handling]`

- [ ] **T2.2 inbox-triage.py — coverage, drift & action determination** `[activity: backend-implementation]`

  1. Prime: Read SDD algorithm steps 7-11 `[ref: SDD/Implementation Examples — inbox-triage.py Algorithm; lines: 663-693]`; read coverage walkthrough `[ref: SDD/Implementation Examples — Coverage Computation; lines: 695-711]`; read action determination logic `[ref: SDD/Runtime View — Complex Logic: Action Determination; lines: 853-869]`
  2. Test: Coverage computation: reads existing instructions sources[].path to build covered set; `to_process = approved - covered`; skips already-covered docs (AC-7); partial coverage triggers partial processing (AC-8). Drift detection: compares current body checksum against sources[].checksum; surfaces checksum_mismatch in drift_indicators (non-blocking). Action determination: priority order matches SDD exactly (force-pass1 → force-pass2 → transcribe → fan-resolve → synthesize → recover → suggest → idle); idle produces idle_reasons (AC-6). Routing-plan emission: validates against routing-plan.schema.json; writes to tomo-tmp/routing-plan.json; includes metrics (timing breakdown). Schema validation failure exits 2.
  3. Implement: Add steps 7-11 to `inbox-triage.py`. SHA-256 checksum computation. JSON Schema validation of output via `jsonschema`. Timing metrics on stderr. Extend `tests/test_inbox_triage.py` with coverage/drift/action tests
  4. Validate: `python3 -m pytest tests/test_inbox_triage.py -v`; `python3 -m ruff check tomo/scripts/inbox-triage.py`; `python3 -m mypy tomo/scripts/inbox-triage.py` (if type hints added)
  5. Success:
     - [ ] Covered docs are excluded from routing-plan `[ref: PRD/AC-7]`
     - [ ] Partial coverage triggers partial processing `[ref: PRD/AC-8]`
     - [ ] Drift indicators surface checksum mismatches `[ref: SDD/DRIFT-1]`
     - [ ] Action determination matches SDD priority order exactly `[ref: SDD/Complex Logic: Action Determination]`
     - [ ] Routing-plan validates against schema `[ref: SDD/ADR-5]`
     - [ ] Idle action includes idle_reasons `[ref: PRD/AC-6]`

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  Run full test suite: `python3 -m pytest tests/test_inbox_triage.py -v`. Verify coverage computation against SDD traced walkthrough (given vault state → expected routing-plan). Lint and typecheck pass. Manually inspect routing-plan.json output shape matches schema.
