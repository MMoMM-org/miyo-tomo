---
title: "Phase 8: Baseline e2e on the new flow"
status: pending
version: "1.2"
phase: 8
---

# Phase 8: Baseline e2e on the new flow

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-11; lines: 1222-1225]` — the new flow with fixture agents, the named differences, the byte comparison of the instruction set
- `[ref: SDD/Architecture Decisions; ADR-9; lines: 1212-1215]` — a carried item delivered through `deliver`
- `[ref: SDD/Test Examples; lines: 888-894]` — `test_rereview_replaces_block_with_carried_items`
- `[ref: SDD/Complex Logic (a)–(d); lines: 966-1049]` — quarter end to end, W14 edge, resume, carry failure
- `[ref: SDD/Quality Requirements/Reliability; lines: 1238]`
- `[ref: PRD/Feature 2, Feature 5, Feature 6]`

**Key Decisions**:
- The same fake vault and setup as T1.3; fixture agents (test helpers that write digests, carryover and proposals derived from the fixture's day and previous-note data, as the agents would) stand in for the models. The fingerprint must equal the T1.3 golden file except the named differences: previous-note lines, not-condensed lines, carried items and their marks (F2-AC1).
- The instruction set per kind is compared byte for byte with the T1.3 golden file except ids, timestamps and the carried item lines (F2-AC2).
- No golden file of T1.3 is re-recorded; a difference outside the named set is a bug to fix with a RED test, or a deviation brought to the owner.

**Dependencies**: Phase 7. T8.1 → T8.2.

---

## Tasks

Proves on the fake vault that the new flow produces the same review and the same Pass 2 as the old one, plus exactly what this spec adds.

- [ ] **T8.1 Baseline comparison for week, month and quarter** `[activity: testing]`

  1. Prime: `tests/test_047_baseline_e2e.py` and its golden files (T1.3), `tests/review_doc_fingerprint.py` (`diff`), `tests/review_e2e_walk.py` (condense step from T4.4), `tests/review_privacy_fixture.py` `[ref: SDD/ADR-11]` `[ref: SDD/Complex Logic (a)]`
  2. Test: `tests/test_047_baseline_e2e.py` runs W13, 2026-03 and 2026-Q1 on the new flow (read → plan → fixture digests and carryover → check → fixture proposer → write → approve → Pass 2 deliver) and asserts `diff(old, new)` names only the allowed keys — `tests/review_doc_fingerprint.py` `diff()` emits a dotted subkey (e.g. `marks.s1`) only when both values are dicts and the bare parent (`marks`) when a key exists on one side only, so the allowed set holds the parent key where a part gains its first carried item (and the dotted subkey where one already had marks), and the test asserts which form appeared; the W13 and 2026-03 documents show the previous-note lines (W12 and 2026-02 found, 2025-Q4 "no note found") and carried items with their marks, the quarter shows "no note found for 2025-Q4" and no carried item; a quarter day reaches the proposer inputs with the same material as the same day in a week read (F1-AC2); one carried item ticked, one edited, one unticked: Pass 2 keeps, keeps as edited and omits them, and the instruction set otherwise equals the golden file byte for byte (F2-AC2, F5-AC4, F5-AC5); habits, reading report, the "Vault growth" group (now built from per-unit growth candidates) and child marks unchanged (F2-AC1); RED proofs: a fixture proposer that drops one unit's items, and a renderer that puts the carried mark after the child mark, each fail the test.
  3. Implement: the new-flow parametrisation and the allowed-difference list in the test; the fixture-agent helpers (tests only).
  4. Validate: GREEN; full suite green; ruff clean.
  5. Success: the review and Pass 2 stay as they were, for every kind, apart from what this spec adds `[ref: PRD/F2-AC1, F2-AC2]`

- [ ] **T8.2 Failure, resume and re-review end to end** `[activity: testing]`

  1. Prime: T8.1; `tests/test_review_e2e_failures.py`, `tests/test_review_e2e_edges.py`; walkthroughs (b), (c), (d); `lib/review_section_plan.py` (unchanged) `[ref: SDD/Complex Logic (b), (c), (d)]` `[ref: SDD/Test Examples; lines: 888-894]` `[ref: SDD/Error Handling; lines: 939-962]`
  2. Test, all on the fake vault through the walk:
     - `test_rereview_replaces_block_with_carried_items` (2026-03: deliver, apply with the reference applier, start over, deliver again: one block per section, carried text present, one instruction set; F5-AC6); a broken section checkbox line still stops delivery (spec 046 F3-AC6);
     - resume: run 1 writes four digests and the carryover, then stops; run 2 continues (no fake-Kado call, the stored `read_at`), dispatches only W13 and W14, and writes a document whose fingerprint equals an uninterrupted run's (F6-AC4); a changed mapping between the runs reads anew and dispatches all units (F6-AC5); a Kado stop leaves nothing to continue;
     - one unit fails twice: its days named at the top and in the report as not condensed, never sources, the rest reviewed (F6-AC1); every unit fails: stopped, every week named, no document (F6-AC8);
     - carryover fails whole: no carried mark anywhere, the previous-note lines still shown, the one top line (F6-AC2); one of two notes fails: the other's items carried, the failed note named;
     - proposals invalid twice (fixture proposer writing a carried error both times): no document, the errors shown (F6-AC3 script side);
     - Pass 1 abort after the read: `replace --abort` leaves only `meta.json` and `payloads.json` and the next run reads anew (F6-AC6 script side);
     - start over after delivery: the previous notes are read anew, nothing is carried from the period's own note or Tomo's earlier blocks in it (F6-AC7); an item removed from the previous note is not carried (F4-AC9);
     - 2026-W14 crossing the month edge reads 2026-W13 and 2026-02 (F3-AC1 end to end).
  3. Implement: tests only; any production fix it needs comes with its RED test first.
  4. Validate: GREEN; full suite green; ruff clean.
  5. Success: every failure is named, a resumed run equals an uninterrupted one, and a re-review leaves one block `[ref: PRD/F5-AC6, F6-AC1, F6-AC2, F6-AC4, F6-AC5, F6-AC6, F6-AC7, F6-AC8]`

  - **Carry-over from the T3.2 review (2026-11-23):** add a test where a previous note's folder listing is rate-limited past the retries and only recovered by the end pass, so `resolve` reads the note after `finish()` (verified by hand in the review, not yet committed).
  - **Carry-over from the T5.6 trace (2026-11-24, orchestrator):** assert the `written.previous` row of a found note that carried nothing (`state found, carried 0`, F3-AC11) end to end; today only the rendered line is pinned.

  - **Carry-over from the T7.5 trace (2026-11-24, orchestrator):** F7-AC2 behaviour end to end — a run Kado stops after the discard leaves no stage content; an interrupted stage survives until that period's next `/review`, which continues on it or reads anew.

- [ ] **T8.3 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN; ruff clean; wire gate and manifests green and unchanged. Trace F2-AC1, F2-AC2, F5-AC6 and the e2e halves of F5-AC4, F5-AC5, F6-AC1 … F6-AC8 to node ids. Drift check spec vs code: every SDD interface shape (`review-read.py` ok/continued, `plan`, `check`, `write` refusals and `written` keys) compared with the scripts' docstrings and actual output; differences fixed or recorded as deviations in the SDD. Confirm no eval-gated file changed across the branch (`git diff --stat main...`).
