---
title: "Phase 3: Consumer Cut-over — Unified byFrontmatter Discovery (F-47.P2)"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Consumer Cut-over — Unified byFrontmatter Discovery (F-47.P2)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Detailed Feature Specifications/State-Promoter + Unified Discovery; lines: 312-364]` — Phase A2.5 step-by-step
- `[ref: SDD/Runtime View/Primary Flow; lines: 762-822]` — orchestrator + discovery + state-promoter sequence diagram
- `[ref: SDD/Complex Logic; lines: 834-883]` — ALGORITHM block for Phase A2.5
- `[ref: SDD/Application Data Models — inbox-discovery.py module; lines: 576-592]`
- `[ref: SDD/Implementation Examples — discover_pending + flip_state; lines: 624-707]`
- `[ref: SDD/Architecture Decisions/ADR-3]` — state-promoter is orchestrator-embedded, NOT a subagent
- `[ref: SDD/Architecture Decisions/ADR-6]` — P2 is the "big bang" that removes legacy paths; Privat-Test inbox wipe at P2 start
- `[ref: PRD/Feature 2, Feature 3]` — unified byFrontmatter discovery + state-promoter
- `[ref: PRD/AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5]`
- `[ref: feedback_orchestrator_impersonate_vs_dispatch]` — STRICT wording in orchestrator prompts

**Key Decisions**:
- **ADR-3**: State-promoter is **orchestrator-embedded** logic (Bash dispatch of a small `state-promoter.py` helper + the existing `instruction-builder` subagent for dispatch). NOT a new subagent — control flow doesn't need LLM reasoning.
- **ADR-6 (P2 atomicity)**: Clean cut-over. `state-init.py` body-read logic + SKIP_SUFFIXES are **deleted**, not shimmed. Privat-Test gets wiped before merge. Per locked OQ4 — no backward-compat tolerated.
- **Sequential promotion** (PRD §5 Business Rules): pending docs processed **one at a time**, sorted by `tomo.updated_at` ASC. No Agent fan-out at the state-promotion layer.
- **Body-read budget** (PRD §5 Business Rules): state-promoter body-reads ONLY the docs it is actively about to promote (≤ pending count, typically 0–3). Non-pending docs are NEVER body-read.

**Dependencies**:
- **Hard**: Phase 2 must be merged. Every producer must emit `tomo:` block before consumers can rely on it.
- T3.1 (inbox-discovery.py) blocks T3.3 (orchestrator wires it in).
- T3.2 (state-promoter.py) blocks T3.3.
- T3.5 (Privat-Test reset) is a runtime prerequisite for live validation — schedule before any live `/inbox` run on Privat-Test.

---

## Tasks

This is the load-bearing phase. After Phase 3 merges, `/inbox` Phase A discovery is **byFrontmatter-first**: one search call returns paths + frontmatter inline for all pending docs, one listDir enumerates fresh sources, and the state-promoter sequentially flips state on user-ticked pending docs. Legacy state-init body-read paths are deleted. **No legacy fallback** per OQ4.

- [ ] **T3.1 `inbox-discovery.py` — unified discovery + bucketing + drift detection** `[activity: backend-implementation]`

  1. Prime: Read SDD inbox-discovery.py module pseudocode `[ref: SDD/Application Data Models; lines: 576-592]`. Read SDD Implementation Examples `discover_pending()` for the byFrontmatter call shape `[ref: SDD/Implementation Examples; lines: 624-650]`. Read PRD §5 Business Rules for bucket definitions + drift detection threshold. Read existing `tomo/scripts/state-init.py` for the listDir + extension-filter pattern being replaced (you're inheriting its job, not its code).
  2. Test: `tests/test_inbox_discovery.py::test_bucketing_with_mixed_pending` (fixture: 1 suggestions/pending-approval + 1 moc-proposal/pending-accept + 1 instructions/pending-apply + 2 captured sources + 1 untagged → buckets contain exactly those splits, newSources excludes captured); `test_empty_inbox_returns_empty_buckets_no_drift`; `test_drift_triggers_when_captured_and_no_pending` (3 captured, 0 pending → drift=True); `test_no_drift_when_any_pending_present` (captured present + 1 pending* → drift=False); `test_non_md_files_excluded_from_newSources` (`.mp3`, `.json` files in inbox don't leak into newSources — those are handled by transcription + tomo-tmp/); `test_filter_path_passed_to_kado_client` (mock KadoClient, assert `path_prefix=inbox_path` was passed); `test_unknown_doc_type_in_hit_logged_and_skipped` (hit with `tomo.doc_type=mystery` → log + skip, don't crash). All tests use mocked `KadoClient`.
  3. Implement: Create `tomo/scripts/inbox-discovery.py` with `# version: 0.1.0`. CLI: `python3 inbox-discovery.py <inbox_path> [--json]` outputs a single JSON object on stdout: `{"buckets": {"pendingApproval": [...], "pendingAccept": [...], "pendingApply": [...], "captured": [...], "newSources": [...]}, "drift": <bool>}`. Implementation calls `KadoClient.search_by_frontmatter("tomo.state=pending-*", path_prefix=inbox_path)` (one call), then `KadoClient.search_by_frontmatter("tomo.state=captured", path_prefix=inbox_path)` (second call — captured discovery), then `KadoClient.list_dir(inbox_path)` for fresh-source set-diff. Bucket client-side by `tomo.doc_type`. Drift = `captured.count > 0 AND (pendingApproval ∪ pendingAccept ∪ pendingApply).count == 0`. NO body-reads in this script — that's state-promoter's job. Stderr logs the `lifecycle.discovery` event with property dict per PRD §7 tracking. Never `2>&1` redirect on the JSON output (per `feedback_never_redirect_stderr_into_json`).
  4. Validate: `pytest tests/test_inbox_discovery.py -v`; `python3 tomo/scripts/inbox-discovery.py /tmp/empty-inbox --json | jq` returns well-formed JSON; `ruff check tomo/scripts/inbox-discovery.py`.
  5. Success: Single point of truth for inbox bucketing `[ref: PRD/AC-2.1, AC-2.2, AC-2.3, AC-5a.1]` `[ref: SDD/Components/InboxOrch + Disc]`. Filter.path narrows server-side (AC-2.4) — no client-side path-filter needed.

- [ ] **T3.2 `state-promoter.py` — flip_state + tick detection helper** `[activity: backend-implementation]`

  1. Prime: Read SDD Implementation Examples `flip_state()` walkthrough `[ref: SDD/Implementation Examples; lines: 656-707]`. Read SDD Complex Logic algorithm step 5 (sequential state-promotion) `[ref: SDD/Complex Logic; lines: 866-875]`. Read PRD §5 Business Rules (sequential, body-read budget, transition rejections, idempotency). Confirm `validate_transition` from `tomo_lifecycle` and `KadoConcurrencyError` from `kado_client` (Phase 1 deliverables).
  2. Test: `tests/test_state_promoter.py::test_check_tick_suggestions_finds_header_approved` (body string contains `- [x] Approved` at header → returns True); `test_check_tick_suggestions_unchecked_returns_false`; `test_check_tick_moc_proposal_finds_any_accept` (body has at least one `- [x] Accept` line within a `### MOC` block → True); `test_check_tick_malformed_body_returns_false_and_logs` (corrupt UTF-8 / unreadable → False + stderr warning, no exception); `test_flip_state_calls_write_frontmatter_with_correct_payload` (mock KadoClient, assert `{"tomo":{"state":"approved","updated_at":...}}` and `mode="merge"` and `expected_modified` passed through); `test_flip_state_rejects_invalid_transition_no_kado_call` (e.g. `suggestions pending-approval → applied` → no write call, logs `lifecycle.transition_rejected`); `test_flip_state_retries_once_on_concurrency_error` (first `write_frontmatter` raises `KadoConcurrencyError`; mock `read_frontmatter` returns target state; flip returns idempotent no-op without raising); `test_flip_state_raises_on_persistent_conflict` (retry's latest state ≠ target → re-raise).
  3. Implement: Create `tomo/scripts/state-promoter.py` with `# version: 0.1.0`. Two callable surfaces: `check_tick(body: str, doc_type: str) -> bool` (regex/substring on body for header `[x] Approved` (suggestions / suggestions-fan) or any `[x] Accept` (moc-proposal)); `flip_state(client, path, doc_type, from_state, to_state, run_id, expected_modified) -> None` (validates transition, calls `write_frontmatter` with merge-mode payload `{"tomo": {"state": to_state, "updated_at": iso8601}}`, retry-once on `KadoConcurrencyError`, idempotent no-op on race-with-target). Imports `validate_transition` from `lib.tomo_lifecycle`. CLI mode: `python3 state-promoter.py check-tick <path> <doc_type>` exits 0 if ticked, 10 if not, 11 if malformed. CLI mode: `python3 state-promoter.py flip <path> <doc_type> <from> <to> <run_id> <expected_modified>` for shell-invocation from orchestrator.
  4. Validate: `pytest tests/test_state_promoter.py -v`; `ruff check tomo/scripts/state-promoter.py`; manual CLI smoke test with a fixture file.
  5. Success: All sequential-promotion semantics covered including rejection + retry-once + idempotent race `[ref: PRD/AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5]` `[ref: SDD/Implementation Examples; lines: 690-697]`. No body-read on non-pending docs (caller-enforced).

- [ ] **T3.3 `inbox-orchestrator.md` Phase A rewrite (A2.5b/c/d/e) + A4 removal** `[activity: agent-prompt-update]`

  1. Prime: Read current `tomo/dot_claude/agents/inbox-orchestrator.md` end-to-end. Identify Phase A0–A5 current structure. Read SDD User Flow Steps 1-5 `[ref: SDD/Detailed Feature Specifications/User Flow; lines: 316-347]`. Read PRD §5 Business Rules. Read SDD ADR-3 (orchestrator embeds the state-promoter loop — no new subagent). Read `feedback_orchestrator_impersonate_vs_dispatch.md` for STRICT wording requirements. Read SDD Sequence Diagram `[ref: SDD/Runtime View; lines: 783-822]`.
  2. Test: N/A (agent prompt). Done = orchestrator prompt now describes A2.5b (run `inbox-discovery.py`), A2.5c (read buckets from JSON), A2.5d (drift handling — pure surfacing, no auto-action when `--recover` absent), A2.5e (sequential loop: for each pendingApproval/pendingAccept doc, kado-read body → state-promoter.py check-tick → if ticked, Task-tool dispatch instruction-builder → on success, state-promoter.py flip), and that legacy step A4 is removed.
  3. Implement: Rewrite Phase A in `inbox-orchestrator.md`:
     - A0–A2 unchanged.
     - A2.5a: media-file check (text deferred to Phase 4 task T4.3; for now just a placeholder "see Feature 5b — implemented in F-47.P3").
     - A2.5b: `python3 scripts/inbox-discovery.py "$INBOX_PATH" --json > tomo-tmp/discovery.json` (STRICT: never `2>&1` per `feedback_never_redirect_stderr_into_json`).
     - A2.5c: parse `tomo-tmp/discovery.json` into shell vars / subsequent step inputs.
     - A2.5d: drift-hint surfacing (placeholder; full UX text in Phase 4 T4.2).
     - A2.5e: sequential loop. For each doc in pendingApproval then pendingAccept, sorted by `tomo.updated_at` ASC: kado-read body → `python3 scripts/state-promoter.py check-tick <path> <doc_type>` (exit code branches: 0 = ticked → dispatch instruction-builder; 10 = no tick → skip; 11 = malformed → log + skip); on dispatch success, `python3 scripts/state-promoter.py flip <path> ...`.
     - **Remove Step A4** entirely (state-init listDir + tag-state filter).
     - Phase A5 branch decision now reads counters from `tomo-tmp/discovery.json` (newSources, captured, pendingApply).
     - STRICT/MUST: "State-promoter is orchestrator logic; do NOT spawn a new subagent for it. Pending docs are processed SEQUENTIALLY, one at a time. NEVER body-read non-pending docs." Bump `# version:`.
  4. Validate: Run `./scripts/update-tomo.sh`; restart Claude (per `feedback_restart_after_agent_sync`); in tomo-instance, run `/inbox` with one fresh source + one pre-existing `<ts>_suggestions.md` that has `[x] Approved` ticked → orchestrator should run discovery, find the pending suggestions, dispatch Pass-2, flip state, and Pass-1 the new source. Inspect stderr trace for the discovery JSON + sequential promotion log lines.
  5. Success: `/inbox` Phase A makes exactly one `byFrontmatter pending-*` call + one `byFrontmatter captured` call + one `listDir` call regardless of inbox backlog `[ref: PRD/AC-2.1]`. State transitions happen sequentially with body-read only on actively-promoted docs `[ref: PRD §5 Business Rules]`. Legacy A4 step is gone `[ref: SDD/User Flow Step 4]`.

- [ ] **T3.4 Remove `state-init.py` legacy paths (or shrink to listDir helper)** `[activity: refactor]`

  1. Prime: Read current `tomo/scripts/state-init.py` end-to-end. Identify the body-read logic, SKIP_SUFFIXES list, and any consumers (`rg state-init tomo/ scripts/`). Read SDD Implementation Boundaries `[ref: SDD/Implementation Boundaries; lines: 143-159]` — explicit option: delete vs shrink to thin listDir-helper. Read SDD ADR-6 — P2 is clean cut-over.
  2. Test: Existing tests touching state-init must either (a) be deleted along with the legacy logic or (b) updated to exercise the new listDir-helper shape. Snapshot the old test list before editing.
  3. Implement: **Decision point** (record as deviation if option B chosen): Option A — delete `state-init.py` entirely. Option B — shrink to a 30-line listDir wrapper used by `inbox-discovery.py`. Recommend **Option A**: `inbox-discovery.py` already calls `KadoClient.list_dir` directly; an extra wrapper script adds no value. `git rm tomo/scripts/state-init.py`. Delete obsoleted tests in `tests/test_state_init*.py`. Sweep callers via `rg state-init tomo/ scripts/ tests/ install-tomo.sh` and remove references. If any agent prompt mentions `state-init.py`, replace with `inbox-discovery.py`.
  4. Validate: `rg state-init tomo/ scripts/` returns zero hits outside `_archive/` / historical evolution notes; `pytest tests/ -v` passes with the old tests removed; `ruff check tomo/scripts/`. Run `./scripts/update-tomo.sh` and verify `tomo-instance/scripts/state-init.py` is gone.
  5. Success: Single discovery path through `inbox-discovery.py`; no legacy SKIP_SUFFIXES anywhere `[ref: SDD/Implementation Boundaries — Can Modify list]` `[ref: SDD/ADR-6 P2 clean cut-over]`.

- [ ] **T3.5 Privat-Test inbox reset + smoke run** `[activity: runtime-validation]`

  1. Prime: Read OQ4 lock + PRD §8 Assumptions ("Privat-Test vault reset is acceptable") `[ref: PRD/§8 Assumptions]`. Confirm Privat-Test path from `reference_test_vault_path` memory. Read SDD ADR-6 — Privat-Test inbox wipe is a P2-start prerequisite.
  2. Test: N/A (runtime). Smoke = `/inbox` exits 0 against a freshly-wiped inbox containing only 2-3 manually-dropped fresh source items; produces `<ts>_suggestions.md` with valid `tomo:` block; source items end with `tomo.state=captured`.
  3. Implement: Document the reset procedure as a checklist commit in `evolution/2026-05/` per `~/Kouzou/standards/general.md` ("Significant setup steps get an entry in `evolution/YYYY-MM/`"): (1) backup Privat-Test inbox to `~/tmp/F-47-prereset-<timestamp>/`; (2) trash all `.md` files in Privat-Test `100 Inbox/` via Obsidian (NOT git, NOT rm — must go through Obsidian to flush metadata cache); (3) drop 2-3 fresh markdown notes manually; (4) run `/inbox` and capture stderr trace. Commit the evolution entry to `feat/017-tomo-lifecycle-tags`.
  4. Validate: Smoke `/inbox` run produces expected files; no leftover `tomo.state=*` from before the reset visible in byFrontmatter discovery; stderr trace shows discovery → no pending hits → listDir → 2 newSources → Pass-1 fan-out → suggestions doc with `tomo.state=pending-approval`.
  5. Success: Privat-Test is the F-47 reference vault going forward `[ref: PRD/§8 Assumptions]` `[ref: SDD/ADR-6]`. Smoke run confirms Phase 3 end-to-end.

- [ ] **T3.6 Phase 3 Validation** `[activity: validate]`

  Run `pytest tests/test_inbox_discovery.py tests/test_state_promoter.py -v`. Run full `pytest tests/ -v` — expect deletions in test_state_init*.py only. Run `ruff check tomo/scripts/`. Live smoke per T3.5 must pass. Repeat live smoke with the **mixed-state** scenario PRD §6.3: prepare an inbox with 1 captured source + 1 pending-approval suggestions doc (manually placed) + 1 pending-accept proposal-doc + 1 untagged fresh source. Run `/inbox`. Expected: discovery returns 2 pending hits + 1 captured + 1 newSource; state-promoter dispatches Pass-2 for both pending docs (sequential); Pass-1 runs for the fresh source. Final inbox = 1 captured source (old) + 1 approved suggestions + 1 accepted proposal + 2 new instructions docs + 1 pending-approval new-suggestions + 1 captured new-source. Inspect stderr `lifecycle.discovery` event — token_estimate ≤ PRD §7 heavy target (6,000). Verify AC-2.4 by manually setting `tomo.state=pending-approval` on a doc OUTSIDE the inbox folder — confirm `/inbox` does NOT see it (server-side filter narrow). Verify AC-3.4 by manually corrupting a `tomo.state` to an illegal value on a fixture doc — `/inbox` skips it with logged rejection event.
