---
title: "Phase 4: Integration, E2E & live validation"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Integration, E2E & live validation

## Phase Context

**GATE**: Read before starting.

**Specification References**:
- `[ref: PRD/Success Metrics M1–M8; Tracking Requirements]`
- `[ref: SDD/Runtime View all flows; Quality Requirements]`
- `[ref: SDD/Risks and Technical Debt — gotchas]`

**Key Decisions**:
- Live validation uses the host-vs-Kado diagnostic technique (`reference_run_tomo_scripts_from_host_against_kado`).
- `update-tomo --yolo` before any in-instance run; bump versions or sync ships nothing.

**Dependencies**: Phases 1–3 complete.

---

## Tasks

This phase proves the three flows work end-to-end and the success metrics hold on the real vault.

- [x] **T4.1 E2E tests across the three flows** `[activity: integration-testing]` `[ref: SDD/Runtime View; PRD/M1,M3,M5,M8]`
  1. Prime: existing `tests/integration/` incl. `tests/integration/test_moc_propose_e2e.py` (the moc-propose E2E to EXTEND for cache-backed flow + case-(a)) and top-level `tests/test_f34_e2e.py` (the F-34 accumulation E2E to DELETE — superseded by the inbox no-accumulation E2E); conftest fakes.
  2. Test (RED): (a) cache build → `/moc-propose` emits link-or-create from cache, no full MOC tree-build when fresh; (b) stale cache → inline rebuild then propose; (c) `/inbox` with no `accumulation_index` → Conditions A + C intact, complete MOC set, lean placeholder; (d) `/explore-vault` force-rebuilds the cache.
  3. Implement: E2E tests with production-shape fixtures through the public entry points (`feedback_mock_at_orchestrator_not_helper`); EXTEND `test_moc_propose_e2e.py`, DELETE `test_f34_e2e.py` (its scenarios are covered by the no-accumulation inbox E2E).
  4. Validate: `pytest tests/integration/ -q`; lint.
  5. Success: all three flows pass `[ref: PRD/M1,M3,M5,M8]`.

- [x] **T4.2 WHY docs + version bumps + reference-doc refresh** `[activity: documentation]` `[ref: SDD/CON-4; Directory Map docs/tomo]`
  1. Prime: `docs/tomo/` mirror convention; tier-2/3 reference docs touching moc/inbox/accumulation.
  2. Test (RED): each new `lib/` module + the rebuilt builder has a `docs/tomo/<mirrored-path>.md` WHY doc; deferred R11/R13 (context.md) MOC-area items addressed; no runtime file carries rationale prose (CON-4).
  3. Implement: write WHY docs (cache rebuild, up_parse SSoT, loader, orphan_link, placeholder_detect); update tier-2/3 reference docs that described accumulation/tag-captured/old lifecycle; bump all modified `# version:`.
  4. Validate: skill/agent author audit on edited agent files (`feedback_audit_skills_agents_after_edits`); doc gap-scan.
  5. Success: WHY layer complete `[ref: SDD/CON-4]`.

- [x] **T4.3 Live validation against the real vault** `[activity: validate]` `[ref: PRD/M1,M2,M4,M5,M7,M8]`
  1. Prime: `update-tomo --yolo`; host-vs-Kado technique; `inbox-cost-log.md`.
  2. Test (RED) / measure: placeholder 397 → ~171 (M2/M4); dual-`up` no longer false-orphans frontmatter-`up` MOCs (M5); `/moc-propose` no full pull when cache fresh (M1); 0 daily/template in candidates (M7); inbox `shared_ctx.mocs` includes notes-area MOCs, excludes `X/…` (M8); envelope 54.5KB → ~34–36KB (M6).
  3. Implement: sync instance; run `/explore-vault` (force-rebuild) → `/moc-propose` → `/inbox`; capture metrics; record a run entry in `docs/evolution/inbox-cost-log.md`.
  4. Validate: metrics meet targets; no regression in A/C output.
  5. Success: M1–M8 confirmed on real data `[ref: PRD/Success Metrics]`.
  - **DONE 2026-06-09** (clean post-reset vault, `/inbox --recover`, 18/18 items). M2/M4 re-baselined (397→196 detection / 38 MOC-named Condition C feed; date fix removed 23 periodic-note FPs); M3 accumulation absent; M6 envelope 35,664 B (≤36KB); M7/M8 0 `X/` leaks, 63 MOCs; M1/M5/M9/F7 prior-evidenced. Two latent bugs found+fixed during validation: date-shaped placeholder FPs (`placeholder_detect` v0.2.0) and `--recover` empty-dispatch (`inbox-triage` v0.8.0); telemetry added. Cost-log entry recorded (token cost not instrumented this run). Out-of-scope finding → #49 (later closed not-a-bug 2026-06-10: created MOC names use the normalized `name` field which DOES apply the convention; initial report misread the raw `topic` field).

- [x] **T4.4 Final validation & spec finalize** `[activity: validate]`
  - Full `pytest` green; lint; all PRD ACs traced to passing tests. Update spec README to Implemented via xdd-meta Finalize with shipping notes (branch, version bumps, metrics). Confirm issue #45 still tracks the deferred per-item shaping.
  - **DONE 2026-06-09** — full suite 924 passed (only 8 pre-existing `ide_bridge`/spec-019 failures), ruff clean on all touched files. Issue #45 confirmed OPEN (deferred per-item context shaping). NOTE: spec-wide `xdd-meta Finalize` to Implemented is GATED on T7.6 (Phase 7 / Feature 8 live validation), which is still open — the inbox/placeholder track (Phases 1–4) is done, F8 live validation is the remaining gate.
