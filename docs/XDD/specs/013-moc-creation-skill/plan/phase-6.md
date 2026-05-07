---
title: "Phase 6: Integration, Live Validation & Docs"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Integration, Live Validation & Docs

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]` — performance + reliability targets to verify under integration.
- `[ref: PRD/Risks and Mitigations]` — risk items to manually validate.
- `[ref: PRD/Constraints/Single-user pre-launch QA]` — Privat-Test + Marcus's real vault.
- `[ref: SDD/Constraints/CON-9]` — Hashi cross-repo dependency.
- All PRD AC and SDD EARS criteria.

**Key Decisions**:
- Pre-launch QA = Privat-Test + Marcus's real vault per `feedback_test_scope_personal_vault.md`. **No synthetic test vault.**
- Hashi handoff (T1.1) **must be confirmed received and shipped** before live-vault validation runs.
- Performance targets: `/moc-propose tag:X` cache-warm < 30s; cache-miss path < 90s; Pass-2 apply for 5-child MOC < 15s.

**Dependencies**:
- All previous phases complete.
- Hashi destination-collision guard (cross-repo, T1.1) confirmed received and shipped on Hashi side.

---

## Tasks

This phase delivers the safety net before launch: integration tests against Privat-Test, live-vault validation on Marcus's real vault, and user-facing documentation. Final phase validation gates F-43 launch.

- [ ] **T6.1 Privat-Test integration suite** `[activity: integration-test]`

  1. Prime: Read PRD/Acceptance Criteria for end-to-end coverage. Verify `Privat-Test/` is reachable and has ≥1 cluster of 3+ atomic notes without dedicated MOC. Read `feedback_test_scripts_must_never_touch_real_install.md` — integration tests MUST use isolated tmpdirs / Privat-Test, never default install paths.
  2. Test: `tests/integration/test_moc_propose_e2e.py` — one parametrised test per input mode:
     - `test_tag_mode_e2e` — `/moc-propose tag:<test-tag>` produces a proposal-doc; tick Accept; run `/inbox`; verify Hashi creates the MOC in `Atlas/200 Maps/`, children get `up::`, no dataview drift.
     - `test_folder_mode_e2e`, `test_class_mode_e2e`, `test_title_mode_e2e`, `test_freetext_e2e`, `test_no_args_e2e` (whole-vault scan).
     - `test_zero_candidates_aborts_no_file_written`.
     - `test_cache_empty_aborts_no_file_written`.
     - `test_override_flow_e2e` — child has existing `up::` to a real classification MOC; ticks Override; verify post-apply child has `up:: <classification>` and `related:: <new MOC>`.
     - `test_collision_guard_e2e` — pre-create the destination file; run /moc-propose accept; verify Hashi returns `applied:false` for the create_moc, downstream children also fail; existing file untouched.
     - `test_squelch_e2e` — propose, reject, re-propose 3× (suppressed), 4th time (re-allowed).
     - `test_perf_cache_warm_under_45s` — wall-clock timing assertion: `assert elapsed_s < 45` for `/moc-propose tag:X` against the Privat-Test fixture with cache populated (45s = 1.5× the SDD `< 30s` target as CI tolerance).
     - `test_perf_pass2_apply_under_25s` — wall-clock timing assertion: `assert elapsed_s < 25` for Pass-2 apply of a 5-child MOC (25s = 1.5× the SDD `< 15s` target).
     - `test_perf_multi_cluster_render_under_8s` — wall-clock timing assertion: `assert elapsed_s < 8` for `suggestions-reducer.py --moc-proposal-mode` on a 5-cluster `DiscoveryReport` fixture (8s = 1.5× the SDD `< 5s` target).
  3. Implement: Add `tests/integration/test_moc_propose_e2e.py` with pytest fixtures spinning up Tomo + Hashi in test mode against Privat-Test. Use `pytest.mark.integration`. Use `time.perf_counter()` around the e2e invocations to capture wall-clock. Document required environment in `tests/integration/README.md` and document the 1.5× CI tolerance rationale (allows for cold runners + small fixture variability while still catching 2-3× regressions).
  4. Validate: `pytest tests/integration/ -v -m integration` — all pass. Manually inspect `Privat-Test/` after each test to confirm no residual state leaks.
  5. Success: All 6 input modes + abort paths + Override + collision guard + squelch pass end-to-end against Privat-Test `[ref: PRD/All AC]`.

- [ ] **T6.2 Live-vault validation on Marcus's real vault** `[activity: e2e-live]`

  1. Prime: Confirm Hashi destination-collision guard handoff (T1.1) has been **shipped** by Hashi team — F-43 launch gated on this. Read all PRD/Risks `[ref: PRD/Risks and Mitigations]`. Snapshot Marcus's vault state (git status / Obsidian sync / backup) before starting.
  2. Test: Manual review (no automated assertions). Per input mode, run one real `/moc-propose` against a known under-MOC'd cluster. Capture wall-clock time; record proposal-doc paths; review:
     - Proposal-doc parses in Obsidian (no broken dataview / wikilinks).
     - Parent-resolution offered the right classification for MiYo profile.
     - Children list matches the user's mental model (precision/recall observation).
     - Override flow correctly preserved at least 1 known existing `up::` link.
     - Multi-cluster `/moc-propose` (no-args) renders ≤5 sections sorted by confidence.
  3. Implement: Run live-vault validation per the test plan; record findings in `docs/XDD/specs/013-moc-creation-skill/live-validation-2026-MM-DD.md`.
  4. Validate: All performance targets met (`< 30s` cache-warm, `< 90s` worst-case cache-miss, `< 15s` Pass-2 apply per cluster). All risks in PRD/Risks have either fired-and-mitigated or not-fired-but-monitored entries. **No regression in existing inbox flow.**
  5. Success: Live-vault validation passes the bar set by PRD Quality Requirements `[ref: SDD/Quality Requirements]` `[ref: PRD/Success Metrics/Quality]` `[ref: PRD/Risks and Mitigations]`.

- [ ] **T6.3 Documentation, release notes & memory updates** `[activity: documentation]`

  1. Prime: Read existing release-notes pattern (if any) under `evolution/YYYY-MM/`. Read `docs/XDD/README.md` consolidated index. Read CLAUDE.md routing rules for memory.
  2. Test: N/A (documentation). Done = each artefact below exists and links resolve.
  3. Implement:
     - **README**: Add `/moc-propose` to top-level `README.md` "Slash commands" section if present.
     - **Evolution log**: Add `evolution/2026-05/F-43-moc-creation-skill.md` summarising: scope shipped, ADRs locked, Hashi dependency, cross-repo handoff outcome.
     - **Kokoro reflection** (Constitution L2 Architecture): record the Tomo↔Hashi `create_moc.destination_exists_check` interaction as a system-level note in MiYo Kokoro — either as an ADR update or as a cross-component protocol entry. Confirm the reflection has landed (file exists in Kokoro's design-notes directory and references this spec by ID `013-moc-creation-skill`). If Kokoro session is the only one allowed to commit there (per L1 Operations on Kouzou-style restrictions), prepare the Kokoro-side file content and stage via the Kokoro session; verify post-merge.
     - **XDD index**: Update `docs/XDD/README.md` to mark spec 013 as `Implemented` and link `live-validation-2026-MM-DD.md`.
     - **Backlog**: Mark F-43 done in `docs/XDD/backlog.md`; cross-link F-44/F-45/F-46 (now unblocked).
     - **User-facing help**: Update `tomo-help.md` slash-command listing to include `/moc-propose` with mode summary.
     - **Memory**: Run `/memory-add` to record any non-obvious lessons captured during implementation (e.g., per-mode performance observations, surprises in topic-signature stability, Hashi handoff outcomes).
  4. Validate: All cross-references resolve; `docs/XDD/README.md` index lists 013 with status. `tomo-help.md` displays `/moc-propose` in the in-container help command.
  5. Success: All documentation deliverables present and discoverable `[ref: docs/CLAUDE.md/Critical Documentation Pattern]`.

- [ ] **T6.4 Final Phase Validation & Launch Gate** `[activity: validate]`

  Final go/no-go review:
  - All Phase-1 to Phase-5 unit tests pass: `pytest tests/ -v`.
  - All Phase-6 integration tests pass: `pytest tests/integration/ -v -m integration` — including the new perf-timing assertions (`test_perf_cache_warm_under_45s`, `test_perf_pass2_apply_under_25s`, `test_perf_multi_cluster_render_under_8s`).
  - Lint: `ruff check tomo/scripts/`.
  - **Hashi receipt-confirmation gate** (T1.1 protocol): verify ONE of (a) `status: received` + `target_version:` in `_outbox/for-hashi/2026-05-07-create-moc-collision-guard.md`, OR (b) a reply file `_inbox/from-hashi/2026-MM-DD-create-moc-collision-guard-ACK.md` with `target_version:` field, AND that the named Hashi version has actually been released and is installed in the test environment.
  - Hashi destination-collision guard: shipped + verified end-to-end (see T6.1 `test_collision_guard_e2e`).
  - Performance targets met — automated assertions in T6.1 + manual wall-clock recording in T6.2 live-vault validation.
  - All PRD AC mapped via `Phase-to-AC Coverage Map` in plan/README.md → all checkboxes ticked across phase files.
  - **Constitution sweep**: re-read MiYo Constitution L1 Privacy/Performance/Operations; confirm no regression introduced (audit log metadata-only, no telemetry, additive hot-path).
  - **Branch hygiene**: feature branch `feat/013-moc-creation-skill` ready for merge to `main`; PR description references PRD + SDD.
  - User sign-off on live-vault validation findings.

  On all-pass: F-43 is launched. Mark spec 013 as `Implemented` in README.
