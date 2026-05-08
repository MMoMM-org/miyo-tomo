---
title: "Phase 5: Squelch Lifecycle Wiring"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Squelch Lifecycle Wiring

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions/ADR-8]` — sidecar registry file design.
- `[ref: SDD/Application Data Models/SquelchEntry]` — registry entry shape.
- `[ref: SDD/Implementation Examples/Example 2]` — topic-signature algorithm.
- `[ref: SDD/Acceptance Criteria/Edge Case Criteria — squelch]` — EARS for squelch behaviour.
- `[ref: PRD/Feature 8]` — squelch behaviour (3-run silence).

**Key Decisions**:
- **ADR-8**: Sidecar registry at `tomo-instance/state/moc-squelch.json`, keyed by topic-signature.
- Squelch decrement happens at the **start** of each `/moc-propose` run; entries with `runs_remaining=0` are removed before proposal generation.
- Rejection detection happens at **archive-time** of a proposal-doc — a doc archived with no Accept ticked enters the registry.

**Dependencies**:
- T1.3 (squelch helper `lib/squelch.py`) — required.
- T2.6 (Phase 6 read-only squelch hookup) — required.
- Phase 4 (parser) — required to recognise an archived-without-accept proposal-doc.

---

## Tasks

This phase wires the squelch lifecycle: read+decrement at run start (T5.1), persist on rejection (T5.2). After this phase, Feature 8 acceptance criteria pass end-to-end.

- [ ] **T5.1 Squelch read + decrement at moc-discovery start** `[activity: state-management]`

  1. Prime: Read `tomo/scripts/lib/squelch.py` from T1.3. Read SDD `Acceptance Criteria/Edge Case Criteria — squelch` for the EARS criteria `[ref: SDD/Acceptance Criteria]`. Read Phase 6 of `moc-discovery.py` from T2.6 (read-only hookup).
  2. Test: `tests/test_squelch_decrement_lifecycle.py::test_decrement_on_run_start` (registry has 2 entries with `runs_remaining=2,1`; after decrement, runs_remaining=1,0; entry-with-0 removed); `test_decrement_persisted_atomically` (file written; corruption simulation rolls back to last-good); `test_active_signature_filters_cluster` (cluster signature in active entries → not in `DiscoveryReport.topic_clusters`); `test_signature_is_stable_across_runs` (per Example 2 — same cluster + same top-K stems → same signature).
  3. Implement: In `moc-discovery.py`, add early-stage call: `registry = load_registry(...)`; `decrement_all(registry)`; `save_registry_atomic(...)`. After Phase 6 dedupe, filter clusters whose signature is `is_active`. Wire signature computation per SDD Example 2.

     **Deviation (recorded 2026-05-08, commit 730ec13):**
     - Threading `squelch_registry` into `phase6_dedupe(...)` is deferred. `main()` currently raises `NotImplementedError` after the squelch save (the Phase 2 individual phase helpers exist but the main-pipeline assembly that invokes them in sequence is not yet wired — Phase 2 T2.1-T2.8 delivered the helpers but no orchestrator). T5.1 ships the load/decrement/save behaviour and the `--squelch-state` CLI arg; the call-site wiring will land when the main pipeline orchestration is added (post-Phase-5 task). Tests for `phase6_dedupe`'s squelch-filtering invoke the function directly (already covered in `test_moc_discovery_phase6.py` from T2.6).
  4. Validate: `pytest tests/test_squelch_decrement_lifecycle.py -v`. Manual: corrupt the JSON; verify warning + reset-to-empty; re-run; verify recovery.
  5. Success: Squelch decrement-on-run + active-filter behaviour `[ref: PRD/AC-8.2]` `[ref: SDD/Acceptance Criteria/Edge Case Criteria]`.

- [ ] **T5.2 Squelch persist on rejection** `[activity: state-management]`

  1. Prime: Read `tomo/scripts/instruction-set-cleanup.py` (or sibling cleanup logic) — find where archived proposal-docs are tagged/moved. Read Phase 4 parser MOC branch (T4.1).
  2. Test: `tests/test_squelch_rejection.py::test_rejected_proposal_writes_squelch_entry` (proposal-doc archived with all clusters' Accept = unticked → registry gains entries for each cluster); `test_partially_accepted_only_rejected_clusters_squelched` (multi-cluster doc: 1 accepted, 2 rejected → 2 squelch entries); `test_runs_remaining_initialised_to_squelch_runs_config` (default 3 from vault-config); `test_first_seen_at_iso_timestamp`.
  3. Implement: In whichever script handles proposal-doc archival (likely `instruction-set-cleanup.py` or a new helper invoked by `/inbox` post-apply): when a `tomo-moc-proposal-*.md` is being archived, parse it once more (reuse T4.1 parser entry point), identify rejected clusters (those without ticked Accept), compute topic signature per cluster, append `SquelchEntry` to registry, persist atomically. Bump `# version:`.
  4. Validate: `pytest tests/test_squelch_rejection.py -v`. **End-to-end smoke**: write a proposal-doc with 2 clusters; tick neither; archive; verify `state/moc-squelch.json` has 2 new entries with `runs_remaining=3`. Re-run `/moc-propose` for the same trigger 3 times; on the 4th run, the previously-rejected clusters are allowed again (per AC-8.2).
  5. Success: Rejection writes entries; expiry after `squelch_runs` runs `[ref: PRD/AC-8.1, AC-8.2]` `[ref: SDD/Acceptance Criteria/Edge Case Criteria]`.

- [ ] **T5.3 Phase 5 Validation** `[activity: validate]`

  Run all squelch tests. Run regression suite over Phase 1-4 to confirm squelch wiring did not regress prior tests. **Lifecycle smoke**: run a 4-iteration scenario manually — propose, reject all, run /moc-propose 3 more times verifying suppression, then run a 4th time and verify clusters re-appear. Inspect `state/moc-squelch.json` after each step.
