---
title: "Phase 5: Integration, Live Test & Migration"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Integration, Live Test & Migration

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Deployment View; lines: 873-887]`
- `[ref: SDD/Quality Requirements; lines: 1014-1022]`
- `[ref: SDD/Acceptance Criteria; lines: 1025-1059]`
- `[ref: PRD/AC-11; lines: 316-320]`
- `[ref: PRD/AC-12; lines: 322-329]`
- `[ref: PRD/§9 Risks; lines: 469-477]`

**Key Decisions**:
- ADR-6: Big-bang migration order — build → test → live-test → delete (last commit)
- Live-test on Privat-Test vault is the acceptance gate (Marcus runs /inbox end-to-end)
- Token cost measurement via `measure-inbox-pass-2-token-cost.py`
- Legacy deletion is a named commit, not a side-effect

**Dependencies**:
- Phase 1 (schema foundation — all tasks complete)
- Phase 2 (triage script — all tasks complete)
- Phase 3 (skills + WHY docs — all tasks complete)
- Phase 4 (conductors + router — all tasks complete)

---

## Tasks

Validates the complete pipeline end-to-end, measures token cost, and executes the big-bang migration (legacy deletion).

- [ ] **T5.1 Cross-phase integration tests** `[activity: integration-test]`

  1. Prime: Read SDD sequence diagrams for all 5 flows (suggest, fan-resolve, synthesize, idle, transcribe) `[ref: SDD/Runtime View; lines: 715-869]`; read existing integration test patterns `[ref: tests/integration/]`
  2. Test: Triage → routing-plan → conductor dispatch chain works end-to-end for all 5 action types; routing-plan.json consumed correctly by /inbox router; conductors load correct skills per action; coverage computation prevents re-processing across runs (multi-run scenario); moc-proposal → synthesis path works (AC-1, AC-2); mixed approved suggestions + moc-proposal produces single instructions doc (AC-2); unticked moc-proposal routes to suggest, not synthesize (AC-3)
  3. Implement: Create integration tests in `tests/integration/test_018_pipeline.py` (or extend existing). Mock Kado responses to test full triage → routing-plan → conductor selection chain. Test multi-run coverage accumulation
  4. Validate: `python3 -m pytest tests/integration/ -v`; `python3 -m pytest tests/ -v` (full suite — verify no regressions)
  5. Success:
     - [ ] All 5 action paths produce correct conductor selection `[ref: SDD/Complex Logic: Action Determination]`
     - [ ] MOC-proposal triggers Pass 2 `[ref: PRD/AC-1]`
     - [ ] Combined sources produce single instructions doc `[ref: PRD/AC-2]`
     - [ ] Coverage prevents re-processing `[ref: PRD/AC-7]` `[ref: PRD/AC-8]`
     - [ ] Full test suite passes with zero regressions

- [ ] **T5.2 Live-test on Privat-Test vault** `[activity: e2e-test]`

  1. Prime: Sync to instance via `bash scripts/update-tomo.sh`; verify instance has all new files (conductors, skills, triage script, schemas); verify old files still present (safety net per ADR-6)
  2. Test: Operator (Marcus) runs `/inbox` end-to-end for: (a) Pass 1 — fresh inbox items → suggestions doc produced; (b) Pass 2 — approve suggestions, re-run → instructions doc produced with sources[]; (c) MOC-proposal — approve moc-proposal, run /inbox → synthesis picks it up (AC-1); (d) Idle — no actionable items → idle_reasons surfaced (AC-6); (e) FAN resolve — mark force-atomic, run /inbox → fan-resolve produces fan companion doc
  3. Implement: This is a manual operator activity. Prepare a test script/checklist documenting the exact steps and expected outputs for each scenario
  4. Validate: All scenarios produce expected outputs; no errors in conductor execution; routing-plan.json written correctly for each scenario
  5. Success:
     - [ ] Pass 1 end-to-end: suggestions doc produced `[ref: PRD/F-3]`
     - [ ] Pass 2 end-to-end: instructions doc with sources[] `[ref: PRD/F-4]` `[ref: PRD/F-6]`
     - [ ] MOC-proposal pickup works `[ref: PRD/AC-1]` `[ref: PRD/AC-2]`
     - [ ] Idle surfaces reasons `[ref: PRD/AC-6]`

- [ ] **T5.3 Token cost measurement** `[activity: validate]`

  1. Prime: Read token budget targets `[ref: SDD/Quality Requirements; lines: 1014-1022]`; read measurement script `[ref: scripts/measure-inbox-pass-2-token-cost.py]`
  2. Test: Pass-2 peak context ≤ 40k tokens (hard cap), target ≤ 30k; Pass-1 main-thread cost ≤ 75% of pre-018 baseline
  3. Implement: Run `python3 scripts/measure-inbox-pass-2-token-cost.py --session-latest` after live-test Pass-2 run. Compare against baseline. If over cap: identify which component (conductor spec, loaded skills, cached doc sizes) contributes most, propose reduction
  4. Validate: Measurement recorded; numbers meet targets
  5. Success: Peak Pass-2 context ≤ 40k tokens `[ref: PRD/AC-12]`

- [ ] **T5.4 Legacy file deletion** `[activity: backend-implementation]`

  1. Prime: Read ADR-6 migration order `[ref: SDD/Architecture Decisions — ADR-6; lines: 987-993]`; read deployment view for sync implications `[ref: SDD/Deployment View; lines: 873-887]`; verify live-test (T5.2) passed
  2. Test: After deletion: `ls tomo/dot_claude/agents/` does NOT contain inbox-orchestrator.md or instruction-builder.md (AC-11); `ls tomo/scripts/` does NOT contain inbox-discovery.py; `update-tomo.sh` sync handles deletions correctly (old files removed from instance); no references to deleted files remain in active runtime files (conductors, /inbox, skills)
  3. Implement: Delete `tomo/dot_claude/agents/inbox-orchestrator.md`, delete `tomo/dot_claude/agents/instruction-builder.md`, delete `tomo/scripts/inbox-discovery.py`. Update/remove `tests/test_inbox_discovery.py` (old tests for deleted script). Verify no dangling references with `rg inbox-orchestrator tomo/dot_claude/ tomo/scripts/` and `rg instruction-builder tomo/dot_claude/ tomo/scripts/` and `rg inbox-discovery tomo/dot_claude/ tomo/scripts/`
  4. Validate: `bash scripts/update-tomo.sh` — verify sync removes old files from instance; `python3 -m pytest tests/ -v` — full suite passes; grep confirms no dangling references
  5. Success:
     - [ ] Legacy agents deleted `[ref: PRD/AC-11]`
     - [ ] Legacy discovery script deleted `[ref: PRD/F-1]`
     - [ ] No dangling references in active codebase
     - [ ] update-tomo.sh sync clean

- [ ] **T5.5 Final specification compliance** `[activity: business-acceptance]`

  Verify all PRD acceptance criteria:
  - [ ] AC-1: moc-proposal triggers Pass 2 `[ref: PRD/AC-1]`
  - [ ] AC-2: combined sources produce one instructions doc `[ref: PRD/AC-2]`
  - [ ] AC-3: unticked moc-proposal routes correctly `[ref: PRD/AC-3]`
  - [ ] AC-4: triage is the only routing computation `[ref: PRD/AC-4]`
  - [ ] AC-5: cache prevents re-reads `[ref: PRD/AC-5]`
  - [ ] AC-6: idle with explanation `[ref: PRD/AC-6]`
  - [ ] AC-7: covered docs skipped `[ref: PRD/AC-7]`
  - [ ] AC-8: partial coverage triggers partial processing `[ref: PRD/AC-8]`
  - [ ] AC-9: conductors orchestration-only `[ref: PRD/AC-9]`
  - [ ] AC-10: force-atomic via skill `[ref: PRD/AC-10]`
  - [ ] AC-11: legacy agents deleted `[ref: PRD/AC-11]`
  - [ ] AC-12: token cost within bounds `[ref: PRD/AC-12]`
  - [ ] AC-13: runtime hygiene clean `[ref: PRD/AC-13]`
  - [ ] AC-14: WHY docs preserved `[ref: PRD/AC-14]`
  - [ ] DRIFT-1: checksum mismatch surfaced `[ref: SDD/DRIFT-1]`
  - [ ] DRIFT-2: drift is non-blocking `[ref: SDD/DRIFT-2]`
  - [ ] SKILL-QA: all skills pass audit `[ref: SDD/Quality Requirements — SKILL-QA]`
  - [ ] AGENT-QA: all conductors pass audit `[ref: SDD/Quality Requirements — AGENT-QA]`

  Verify all SDD components implemented: Layer A (triage), Layer B (conductors), Layer C (skills), Layer D (schema). Full test suite passes. lint + typecheck clean. Ready for merge.
