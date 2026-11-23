---
title: "Phase 1: Behaviour baseline and early smoke checks"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Behaviour baseline and early smoke checks

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-11; lines: 1222-1225]` — the baseline, the fingerprint fields, the named differences
- `[ref: SDD/Directory Map/Tests; lines: 485-505]` — `review_doc_fingerprint.py`, `test_047_baseline_e2e.py`, the fixture and walk changes
- `[ref: SDD/Implementation Gotchas; lines: 1298-1309]` — `test_review_sdd_map.py` accepts only mapped files; the nested-write smoke; Kado's per-path denial shape
- `[ref: SDD/Architecture Decisions; ADR-2, ADR-7; lines: 1168-1173, 1201-1204]` — the numbers set before measurement; agent writes under the current `settings.json`
- `[ref: PRD/Feature 2; F2-AC1, F2-AC2]`; `[ref: PRD/Notes for the SDD]` (the baseline is an e2e on the fake vault, green before and after)

**Key Decisions**:
- No production change in this phase. The baseline is recorded on the old flow first, so Phase 8 compares like with like (ADR-11).
- The fingerprint records structure only — part order, section keys and checkbox states, group headings, item counts per part, mark suffix keys, habit items, callout fields, link kinds per item (daily / weekly / monthly / previous) — never wording.
- The fixture gains the quarter and the previous notes now (2026-W12, 2026-02; no 2025-Q4), so the same vault serves both runs; the old flow ignores the previous notes.
- The smoke checks and the measurement run only on the owner's go, in the test instance, never in `tomo-privat`.

**Dependencies**: none. T1.1 ∥ T1.2 → T1.3. T1.4 and T1.5 are owner-gated and independent of T1.1–T1.3; their results are recorded in this file before Phase 2 starts.

---

## Tasks

Pins what the review document and Pass 2 look like today for a week, a month and a quarter, and settles the two platform unknowns and the size numbers before the rebuild.

- [x] **T1.1 Structural fingerprint of a review document** `[activity: testing]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/review_doc_parse.py` (how a document's parts, items, ids and links are read), `tomo/scripts/lib/review_doc.py` (`_LABELS`, `_callout`, the part order), `tests/test_review_sdd_map.py` (how it reads the 045 and 046 Directory Maps, lines 1-60) `[ref: SDD/ADR-11; lines: 1222-1225]` `[ref: SDD/Directory Map; lines: 485-505]`
  2. Test: `tests/test_review_doc_fingerprint.py` — two documents differing only in item wording give equal fingerprints; a moved part, an unticked section checkbox, a missing group, one item more, a changed mark suffix, a changed link kind (daily → weekly) and a changed callout field each give unequal fingerprints (each RED-proven by mutating the fingerprint to ignore that field); the fingerprint holds no item text (asserted on a fixture whose items carry a sentinel string); `test_review_sdd_map.py` accepts a review file named in spec 047's Directory Map (fixture: `tests/review_doc_fingerprint.py`), keeps refusing an unmapped file, and keeps reading spec 045's and 046's maps.
  3. Implement: `tests/review_doc_fingerprint.py` (`fingerprint(document_text) -> dict` of structure only; a `diff(a, b)` naming the differing keys); teach `tests/test_review_sdd_map.py` to read spec 047's Directory Map blocks (Tomo runtime and scripts, Documentation, Tests); add `tests/test_review_doc_fingerprint.py` to the Tests block of spec 047's `solution.md` Directory Map in the same commit.
  4. Validate: new tests green; `test_review_sdd_map.py` green with `test_review_doc_fingerprint.py` named in spec 047's map; ruff clean.
  5. Success: a document's structure can be compared without its wording `[ref: PRD/F2-AC1]` `[ref: SDD/ADR-11]`

- [ ] **T1.2 Fixture and walk for the quarter and the previous notes** `[activity: testing]` `[parallel: true]`

  1. Prime: `tests/review_privacy_fixture.py` (folders `DAILY`, `WEEKLY`, `MONTHLY`, `CONFIG`, `build_vault`, `proposals`), `tests/review_e2e_walk.py` (`Walk`, `WEEK`/`MONTH` constants lines 52-66, `pass1`, `deliver`, `stage`), `tests/test_review_e2e.py`; spec 046 quarter config shape (`review.quarterly`, `GRANULARITY[QUARTER]`) `[ref: SDD/Directory Map/Tests; lines: 490-491]` `[ref: SDD/Complex Logic (a); lines: 966-989]`
  2. Test: a quarterly folder and a quarter setup in the fixture config; `build_vault` writes weekly notes for 2026-W12 and W13, monthly notes for 2026-02 (and 2026-01), no 2025-Q4 note, dailies spanning 2026-01-01 … 2026-03-31 with at least one day per ISO week of 2026-Q1 holding content (structure only, synthetic text, no journal text); quarterly fixture proposals valid against today's `review-proposals.schema.json`; `Walk` gains `QUARTER` / `2026-Q1` constants and runs Pass 1 and Pass 2 for the quarter on the old flow; every existing e2e test (`test_review_e2e*.py`, `test_review_privacy.py`) stays green with the extended fixture.
  3. Implement: the fixture extension and the walk's quarter constants and paths; no production file changes.
  4. Validate: `test_review_e2e*.py`, `test_review_privacy*.py` green; the week and month outputs of the walk (documents, instruction sets, reports) and every existing e2e expectation are unchanged by the fixture extension — no existing assertion or expected value edited to make it pass; ruff clean.
  5. Success: the fake vault holds a quarter and the previous notes the new flow will read `[ref: PRD/Assumptions]` `[ref: SDD/ADR-11]`

- [ ] **T1.3 Baseline e2e on the old flow (`tests/test_047_baseline_e2e.py`)** `[activity: testing]`

  1. Prime: T1.1 and T1.2 outputs; `tests/review_e2e_walk.py` (`pass1`, `parse`, `preview`, `deliver`); `tomo/scripts/review-instructions.py` output (the instruction set and the readable instructions) `[ref: SDD/ADR-11; lines: 1222-1225]` `[ref: SDD/Quality Requirements/Reliability; lines: 1238]`
  2. Test: for week 2026-W13, month 2026-03 and quarter 2026-Q1: Pass 1 → document → approve → Pass 2 `deliver`; the fingerprint of each document and the instruction set of each kind (ids and timestamps masked) are written once as golden files under `tests/fixtures/047-baseline/` and asserted equal on every run; the test names which golden file failed and which keys differ; a RED proof: a renderer mutation (one part dropped, one mark suffix removed) and an instruction-set mutation each fail it, recorded in the commit message.
  3. Implement: `tests/test_047_baseline_e2e.py` with a `baseline` parametrisation over the three kinds and a helper that later (T8.1) takes the named differences; the golden files.
  4. Validate: GREEN on the old flow; full suite green; ruff clean.
  5. Success: the before-state of the document and of Pass 2 is pinned for all three kinds `[ref: PRD/F2-AC1, F2-AC2]`

- [ ] **T1.4 Smoke checks in the test instance (owner go)** `[activity: validate]`

  1. Prime: `tomo/dot_claude/agents/inbox-analyst.md:1-12` (frontmatter pattern), `tomo/dot_claude/settings.json:33` (`Edit(tomo-tmp/*)`, read only — never edited); `_inbox/from-kado/` (check first for the per-path denial shape), `tomo/scripts/lib/kado_client.py:51-52, 761` `[ref: SDD/Implementation Gotchas; lines: 1302-1303]` `[ref: SDD/ADR-7; lines: 1201]`
  2. Test, as explicit owner-gated steps (announce, wait for the go, report at once):
     1. Nested write: in a `tomo-instance` session, a throwaway agent with `tools: Read, Write`, `permissionMode: acceptEdits`, `model: haiku` writes `tomo-tmp/review/smoke/digests/x.json`; record whether the file exists and whether a permission prompt appeared; then repeat with `digests/` pre-created. Remove the throwaway agent and the smoke folder afterwards.
     2. Read of a line-broken 40 KB file: a synthetic, content-free JSON file of 40,960 bytes written with `indent=1` and text as line arrays (no line over 2,000 characters) is read by one Read call in the same session; record whether it returns whole in one call (no truncation, no offset needed).
     3. Kado per-path denial: from `_inbox/from-kado/` and Kado's docs only (no live call), record whether a denied path answers 403 (`KadoAuthError`) or a tool error.
  3. Implement: record the three outcomes as notes under this task. If (1) fails without pre-creation, T4.3 makes `review-digest.py plan` pre-create `digests/`; if it fails in both forms, stop and bring it to the owner (a `settings.json` change needs the full eval suite, CON-6). If (2) fails, lower `FILE_CEILING` in T2.2 to the largest size that passed, as a recorded deviation.
  4. Validate: outcomes recorded; nothing under `tomo/` changed; `tomo-privat` untouched.
  5. Success: the agents' file writes and one-call reads are proven before the agents are built `[ref: SDD/ADR-2, ADR-7; SDD/Implementation Gotchas]`

- [ ] **T1.5 Size measurement of 2026-Q1 on the old flow (owner go)** `[activity: validate]`

  1. Prime: `tomo/scripts/review-read.py` `--measure` (docstring lines 21-55, `_measure` 200-209); spec 046 close-out (717 KB, `read-index.json` ≈ 82.5k tokens); research §2 `[ref: SDD/ADR-2; lines: 1168-1173]` `[ref: SDD/Project Commands; lines: 317-330]`
  2. Test, owner-gated: announce, wait for the go, then run `python3 tomo/scripts/review-read.py --kind quarter --period 2026-Q1 --stem 2026-Q1_review --measure` against the test instance's config and key (never `tomo-privat`); report at once.
  3. Implement: record counts only — calls, retries, waited seconds, bytes per read file, and from the per-month parts the per-day average and maximum bytes — as notes under this task; derive the expected indented size per day and per 7-day week (≈ 15 % over compact) and compare with ADR-2's 40,960 / 81,920 / 8,192 numbers. A number that does not hold is brought to the owner as a deviation before T2.2.
  4. Validate: the measure wrote no file; no journal text in the notes.
  5. Success: the ADR-2 limits are checked against the real quarter before they are coded `[ref: SDD/ADR-2; PRD/Constraints]`

- [ ] **T1.6 Phase Validation** `[activity: validate]`

  - Run the full suite in ONE invocation (`./venv/bin/python -m pytest tests/ -q`) — GREEN; `./venv/bin/ruff check tomo/scripts scripts tests` clean. Trace F2-AC1 and F2-AC2 (old-flow half) to the node ids of `tests/test_047_baseline_e2e.py`. Confirm no file under `tomo/` changed in this phase and no eval-gated file changed. T1.4 and T1.5 outcomes recorded (or explicitly deferred by the owner).
