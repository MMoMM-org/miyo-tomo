---
title: "Phase 6: Wire v4, integration, live walk and close-out"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Wire v4, integration, live walk and close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Deployment View/Multi-Component Coordination]` — order (1)–(7)
- `[ref: SDD/Technical Debt]` — the ~14 tests with `"schema_version": "3"`, `test_review_sdd_map.py`
- `[ref: SDD/Quality Requirements]`; `[ref: PRD/Success Metrics]`
- `[ref: SDD/Architecture Decisions; ADR-5]`
- Spec 045 `close-out.md` and `live-walk.md` (precedent)

**Key Decisions**:
- All instruction-schema changes happen here, together, after Hashi's release: producer schema, `schema_version` "4", the shape manifest, and the vendored copy (byte-identical, never edited) (ADR-5, owner 2026-11-14).
- The PR merges only after Tomo and Hashi work together in the test vault: week, month, quarter; first delivery and re-run (PRD Constraints).
- Paid evals and live runs only on the owner's instruction; sync with `--instance tomo-instance` only.

**Dependencies**: Phase 5. T6.1 waits for Hashi's reply to `_outbox/for-hashi/2026-11-14_tomo-to-hashi_replace-between-markers.md` and its release.

---

## Tasks

Ships the wire bump with Hashi, proves the whole flow end to end and in the test vault, and closes the spec.

- [ ] **T6.1 Wire v4 after Hashi's release** `[activity: integration]`

  1. Prime: Hashi's reply in `_inbox/from-hashi/` and its released `src/schema/instructions.schema.json`; spec 039 `test_039_t3_1_wire_v4` precedent (live schema, version and manifest moved together; only the vendored copy lagged); `tomo/schemas/instructions.schema.json`, `tomo/schemas/shapes/instructions.shape.json`; the form-agnostic search `rg -n "schema_version.{0,8}['\"]3['\"]" tests tomo/scripts` (never truncated; each hit checked per wire — e.g. `tests/test_review_instructions.py:729`); `docs/instructions-json.md` `[ref: SDD/Cross-Component Boundaries; ADR-5]`
  2. Test: diff the released `replace_between_markers` `$def` against the handoff fragment — any difference becomes a fix task with a RED test before anything else; the vendored copy is byte-identical to Hashi's released file (sha256 recorded); the producer schema gains the action and `schema_version` "4" in the same commit as the manifest regeneration; `/inbox`, `/note` and `/review` producers emit "4" through `wire_schema_version`; every instructions-wire hit of the search moves to "4" (list recorded in this task); the 038 wire baselines regenerated; the T5.3 test-only schema and its helper switch removed, Phase 5 tests now validating against the committed schemas; a few vectors from Hashi's own `replaceBetweenMarkers` / `insertUnderMarker` tests re-run through Tomo's reference splice (T5.1); `test_tomo_schema_parity`, wire gate and manifests green; Hashi's answer on v3 sets reflected in the release notes text.
  3. Implement: producer schema, version, manifest, vendored copy, the listed tests, removal of the test-only schema; `docs/instructions-json.md` (version and the new action); WHY docs first; version bumps.
  4. Validate: the full suite GREEN with no named exception.
  5. Success: Tomo and Hashi share wire v4 `[ref: SDD/ADR-5; PRD/Constraints]`

- [ ] **T6.2 End-to-end tests and documentation** `[activity: testing]`

  1. Prime: `tests/test_review_e2e*.py`, `tests/review_e2e_walk.py`, `tests/test_review_sdd_map.py:35-50`, `tests/test_review_why_docs.py`; README, `docs/tomo/`, PRIVACY.md `[ref: SDD/Directory Map; PRD/F6-AC6]`
  2. Test: e2e on fake Kado for week, month and quarter: setup with a mapping → Pass 1 document → edits (untick one section, add a user item, edit an item) → Pass 2 → set; then a re-run producing `replace_between_markers` for kept sections and nothing for an unticked one; a reference applier implementing Hashi's documented semantics shows the user's text unchanged and one block per section; the unmapped e2e paths unchanged; `test_review_sdd_map.py` repointed to spec 046's Directory Map (or both maps); WHY-doc mirror test covers the new libs.
  3. Implement: e2e fixtures; README feature text (#263, #256, #267 parts), `docs/tomo` mirrors complete, PRIVACY.md (rows file, read parts), `commands/review.md`, `vault-example.yaml`; version bumps.
  4. Validate: the full suite GREEN; ruff clean.
  5. Success: week, month and quarter run end to end as a month does `[ref: PRD/F6-AC6]`

- [ ] **T6.3 Live walk with Hashi in the test vault (owner-run)** `[activity: validate]`

  1. Prime: spec 045 `live-walk.md` format; reference memories on test-vault plugins (update-time-on-edit, Templater on create)
  2. Test, as explicit owner-gated steps:
     1. Sync on the owner's instruction: `scripts/update-tomo.sh --instance tomo-instance --yolo`.
     2. Restart the Tomo session so the synced skill loads.
     3. The owner walks, with the released Hashi:
        - setup for week, month and quarter (mapping, one off-limits mark, one analysis row) and the review continuing in the same session after the save;
        - week 2026-W13, month 2026-03 and quarter 2026-Q1, Pass 1 and Pass 2, then apply;
        - a re-run with one section unticked and one block edited.
     4. Walk rows record the section fit:
        - a section whose description no group covers received sourced items;
        - items read as reminders, not finished review text;
        - costs and durations per pass from `tomo-session-stats.py`.
     Writes reach the test vault only through Hashi's apply; nothing edits it directly.
  3. Implement: record every run in `live-walk.md` (counts only, no journal text); file walk-found fixes as tasks with RED tests. Notes from Phase 4: record the context use (tokens) and cost of the quarter's Pass 1 beside the ≤ $5 / ≤ 20 min KPI; the mapped callout's target stem and not-read / partly-read paths are still raw (path-derived, low risk) — check them in the walk or note them in the close-out.
  4. Validate: KPIs — weekly Pass 1 ≤ $0.50, monthly Pass 1 ≤ $2.00 and ≤ 7 min, Pass 2 ≤ $0.75, quarterly Pass 1 ≤ $5.00 and ≤ 20 min; 0 changed characters of user text outside markers; 0 sections with two blocks; 0 writes to off-limits.
  5. Success: Tomo and Hashi work together on all three kinds, first delivery and re-run `[ref: PRD/Success Metrics; PRD/Constraints]`

- [ ] **T6.4 Close-out** `[activity: validate]`

  1. Prime: spec 045 `close-out.md` and spec 044's (method)
  2. Test: every one of the 49 PRD criteria traced to node ids run in ONE pytest invocation, or to a recorded live-walk row for model behaviour; criteria parts no test can fail closed by RED-proven tests in `tests/test_046_close_out_gaps.py`; inbox cost log updated. Known prose-pin-only parts to trace to live-walk rows (Phase 2 drift check): F2-AC10 "the request continues in the same session", F2-AC3 "one line per left-out heading with its reason", F2-AC2/F2-AC6 (the table and suggestion descriptions as the model words them).
  3. Implement: `close-out.md`; spec README Finalize after merge; memory index entry (Critical Documentation).
  4. Validate: drift check spec vs code; the Kokoro FYI (`_outbox/for-kokoro/2026-11-14_…`) status checked and, if the contract changed at T6.1, a follow-up FYI; the PR carries the spec ID, the issues (#263, #256, #267) and the Hashi release.
  5. Success: the spec closes with its evidence `[ref: PRD all criteria]`
