---
title: "Phase 6: Integration, Live Validation & Docs"
status: in_progress
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

- [x] **T6.0 Backfill `moc-discovery.py main()` orchestration** `[activity: backend-cli]` ✅ DONE 2026-05-09: `tomo/scripts/moc-discovery.py` v0.9.0 with `_run_pipeline` orchestration calling phase1 → phase65 in order; `tests/test_moc_discovery_main.py` (5 tests: title-mode, tag-mode w/Kado-fake, zero-candidates abort, squelched cluster, dry-run regression). Spec compliance + code quality both PASS. Full suite 190 passed / 1 skipped. Commits: `3bec663` (RED) + `cd88f74` (GREEN) + `a014c4b` (test naming) + `5482897` (cleanup).

  Surfaced during T6.1 spec-compliance review (2026-05-09): Phase 2's phase-functions (`phase4_title`, `phase5_resolve_parents`, `phase6_dedupe`, `phase65_validate_existing_up`) exist as units but `main()` raises `NotImplementedError` after the squelch-decrement step. Phase 3's T3.4 "Live producer smoke" was never executed (no done-note). Production `/moc-propose tag:X` would crash today. T6.1's perf assertions (`test_perf_cache_warm_under_45s`) cannot exercise the real cache-warm path without this wiring.

  1. Prime: Read SDD `Runtime View/Primary Flow` + `Building Block View/moc-discovery.py`. Re-read each phase function's signature in `tomo/scripts/moc-discovery.py` (phase1_filter through phase65_validate_existing_up). Re-read the `DiscoveryReport` schema (per `application data models` SDD section).
  2. Test: `tests/test_moc_discovery_main.py` — new unit test exercising `main()` end-to-end on a small in-memory cache:
     - `test_main_tag_mode_produces_discovery_report` — argparse → phases run in order → JSON DiscoveryReport on stdout.
     - `test_main_zero_candidates_emits_abort_reason` — empty cache → JSON with `abort_reason: 'zero_candidates'`, exit 0.
     - `test_main_handles_squelched_cluster` — squelch state with active topic-signature → cluster filtered before render, surfaced in `squelched_count`.
     - `test_main_dry_run_path_unchanged` — confirm `--dry-run` still exits cleanly (regression guard for T2.1).
  3. Implement: Replace the `NotImplementedError` block at `moc-discovery.py:1493-1497` with the orchestration:
     - Load cache (existing helper).
     - Run phases in order: `phase1_filter` → `phase2_score` → `phase3_threshold` → `phase4_title` → `phase5_resolve_parents` → `phase6_dedupe` (consumes `squelch_registry` already loaded above) → `phase65_validate_existing_up`.
     - Assemble `DiscoveryReport` per SDD shape (clusters, abort_reason, run metadata, squelched_count, duplicates_skipped_count).
     - `json.dump` to stdout. Exit 0 on success, 1 on partial-failure, 2 on fatal (per existing exit-code spec).
     - Preserve all existing logging conventions (stderr, structured `_log` calls).
  4. Validate: `pytest tests/test_moc_discovery_main.py -v` plus full regression `pytest tests/ -v`. Manual smoke: `python3 tomo/scripts/moc-discovery.py --tag <real-Privat-Test-tag> --config <fixture-config> --cache <fixture-cache>` produces valid DiscoveryReport JSON on stdout.
  5. Success: `/moc-propose tag:X` end-to-end through the agent invocation path (per `tomo/dot_claude/agents/moc-architect.md` Step 4) returns a real proposal-doc with no NotImplementedError. Phase 3 T3.4 "Live producer smoke" can finally be executed `[ref: SDD/Runtime View/Primary Flow]` `[ref: PRD/AC-1.x]` `[ref: phase-2.md/T2.8]`.

- [x] **T6.1 Privat-Test integration suite** `[activity: integration-test]` ✅ DONE 2026-05-09: `tests/integration/test_moc_propose_e2e.py` (14 integration-tagged tests covering 6 input modes + 2 abort paths + Override + collision-guard + squelch lifecycle + 3 perf assertions; 3 plain non-tagged helper tests for additional pipeline coverage); `tests/integration/conftest.py` (privat_test_clone, seeded_discovery_cache, isolated_tomo_state fixtures + builder helpers); `tests/integration/README.md` (env requirements, producer-side scope, 1.5× CI tolerance rationale); `pyproject.toml` registers `integration` + `perf` markers. Spec compliance + code quality both PASS. 14 integration tests + full suite 190 passed / 1 skipped. Range: `8bb0ddb..e5519be` (T6.1 footprint = `fa4d3c3`, `e179db2`, `e5519be`).

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

- [ ] **T6.3 Documentation, release notes & memory updates** `[activity: documentation]` 🔶 STREAM A DONE 2026-05-09: README `/moc-propose` row, evolution log `2026-05-09_F-43-moc-creation-skill.md`, Kokoro reflection handoff `_outbox/for-kokoro/2026-05-09_tomo-to-kokoro_F-43-create-moc-collision-protocol.md`, backlog F-43 done + F-44/F-45/F-46 unblock notes, XDD index spec 013 → Implemented, tomo-help `/moc-propose` listing v0.2.3. Both reviews PASS. Range `e5519be..da86f71`. Stream B (live-validation link in XDD index + `/memory-add` for non-obvious lessons) awaits T6.2.

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

- [x] **T6.5 Production LLM client gap — agent-side topic extraction** `[activity: backend-cli + agent]` ✅ DONE 2026-05-20: Surfaced during T6.2 live-vault validation — `/moc-propose tag:topic/knowledge/lyt` crashed with `phase2_extract_topics: llm_client is required when there are cache misses`. Root cause: T2.8 was validation-only (tests passed using a `RecordingLLMClient` fake), and T6.0's `_run_pipeline` left `llm_client=None` with a `T2.8 will inject real client` TODO. Cache only populates topics for `map_notes` (MOCs), so every atomic-note candidate is a guaranteed cache miss → guaranteed RuntimeError on any real input. Integration tests `test_moc_propose_e2e.py` exercise phase 2 with pre-populated fixtures and never traversed `main()` against a real-world miss path.

  **Fix (Option B — agent-side extraction)**: `moc-discovery.py` v0.10.0 grew two mutually-exclusive flags — `--emit-phase1 <path>` runs Phase 1 only and writes candidate paths + cache-resolved topics (null for misses) + `body_excerpt` (first 800 chars via kado-read) for misses; `--phase1-input <path>` reads the agent-enriched JSON, skips Phase 1, and runs Phases 2-6.5 with `phase2_extract_topics` short-circuiting on pre-populated `c.topics`. `moc-architect.md` v0.2.0 now runs a 2-pass flow: Step 4a invokes `--emit-phase1`, Step 4b extracts 3-5 topics per cache-miss candidate from `body_excerpt` (in-context LLM work — no nested subagent dispatch, no MCP Kado access from agent), Step 4c invokes `--phase1-input`. Agent's `tools` grew `Write` for rewriting the phase1 JSON cleanly. CON-6 cache-miss cap (5 × 10) is now enforced in `_write_phase1_emit` since phase 2's enforcement is bypassed on the resume path.

  **Tests added** (`tests/test_moc_discovery_main.py` v0.2.0): `test_emit_phase1_writes_candidates_json`, `test_emit_phase1_marks_misses_as_null` (with `body_excerpt` assertion), `test_phase1_input_skips_phase1_no_llm_needed`. Full unit suite 175 passed / 1 skipped (was 175 before — 3 new tests net of any cleanup).

  **Lesson** (worth a `/memory-add` once T6.2 is complete): integration tests that mock a key dependency by injecting it into a sub-helper rather than exercising the orchestration's wiring will silently pass while the production path crashes. The right guard would have been an `end_to_end_main_with_real_cache_misses` smoke test that calls `main()` against a cache where atomic notes have no topic entries — exactly the production shape. T2.8's "manual smoke" instruction asked for this but was either skipped or only executed with `--dry-run`.

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
