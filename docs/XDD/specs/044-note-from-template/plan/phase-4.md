---
title: "Phase 4: Eval, live walk and close-out"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Eval, live walk and close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-8]`
- `[ref: SDD/Known Technical Issues]`: `AskUserQuestion` cannot be answered in an eval; the dialogue criteria are proven by prose tests plus a live walk.
- `evals/README.md`: case layout, `9-no-leak.md`, coverage table, RED-proof rule.
- Spec 043 `close-out.md`: the close-out format.

**Key Decisions**:
- The eval case is not added to the CLAUDE.md gate (ADR-8).
- Paid runs and the instance sync happen only on the owner's explicit instruction; the tree is never edited during a paid run.

**Dependencies**:
- Phase 3 complete.

---

## Tasks

This phase proves the model behaviour once, walks the feature live and closes the spec.

- [ ] **T4.1 Stub kit and eval case** `[activity: test]`

  1. Prime: `evals/README.md`; `evals/_lib/pass1-stubs.sh`; `tests/test_stub_contract.py`; `tests/test_eval_gate_docs.py` `[ref: SDD/ADR-8]`
  2. Test: `evals/_lib/note-stubs.sh` stubs the `/note` scripts with output copied from the real ones and cited by file and line, and fails loudly on unexpected argv; the stubs include `stage` writing `note.md` and the `deliver` exit codes 0, 1 and 3 with the `EXISTS:` first line; `tests/test_stub_contract.py` covers it. Case `evals/note-draft-before-approval/` with material that fills every point: graders check the draft and header are printed before the approval question, the printed text is `note.md`, not `draft.md`, no question round runs, `deliver` is never called before approval, and `9-no-leak.md` is a byte copy. Each non-control grader has a mutation in `evals/_mutations/` that turns it red.
  3. Implement: kit, case, mutations; coverage table row in `evals/README.md` marked "not gated".
  4. Validate: pytest passes (including the gate-docs test); the paid run (`scripts/run-evals.sh --keep-temp`, owner's instruction) is GREEN and each mutation run is RED; verdict line, cost and results path recorded.
  5. Success: the model prints before it asks and delivers only after approval `[ref: PRD/F4; SDD/F4-AC1, F4-AC4]`

- [ ] **T4.2 Live walk on tomo-instance** `[activity: validate]`

  1. Prime: PRD journeys; SDD criteria marked as model behaviour; memory: sync before any live walk, restart Claude after the sync, never `tomo-privat` `[ref: PRD/User Journey Maps]`
  2. Test: a written checklist in `docs/XDD/specs/044-note-from-template/live-walk.md` with one line per criterion: first run with pattern setup; one-template and several-template choice; an inbox-note source with open and required points; skip and the skipped line; a revision; delivery and the report; Hashi applies the set (move, then the source to trash); the next `/inbox` proposes nothing for either file; a name-taken rename; an interrupted delivery and resume; abort; the process offer with "never" and a second run without the offer; `/note --process`; `inbox-author` with an overview (unchanged) and with a template kind (points to `/note`); title starting with a dot refused; `--source` outside the inbox refused; vanished source before the mark (note and set delivered, source not marked); killed delivery between steps offered as resume; a process file with an empty `destination:` or `offer:` key still used.
  3. Implement: the owner syncs `tomo-instance` (`./scripts/update-tomo.sh --instance tomo-instance --yolo`) from the branch or `main` as the owner decides, restarts the session and walks the checklist; Claude reads the transcripts and fills in each line with the session id.
  4. Validate: every line has an outcome and evidence; failures become fixes before merge or are recorded with the owner's decision.
  5. Success: the dialogue criteria hold on a real vault `[ref: PRD/Success Metrics]`

- [ ] **T4.3 Close-out** `[activity: validate]` `[model: routine]`

  1. Prime: spec 043 `close-out.md`; `docs/ai/memory/memory.md` Critical Documentation `[ref: PRD/Success Metrics]`
  2. Test: trace all 52 criteria to node ids that run in ONE pytest invocation, to the eval verdict or to a live-walk line; for any criterion no test could fail, write a RED-proven test. The `tests/test_note_privacy.py` allowlist is the evidence for F5-AC8 under the amended CON-3.
  3. Implement: `docs/XDD/specs/044-note-from-template/close-out.md`; a Critical Documentation entry in `docs/ai/memory/memory.md`; spec README to Implemented through `xdd-meta finalize`.
  4. Validate: the single pytest invocation is green and its node ids are quoted verbatim.
  5. Success: every criterion is traced to evidence that could fail `[ref: PRD; SDD/Acceptance Criteria]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Full pytest and ruff; link check; `git status` clean; PR body carries the spec id, #169 and the eval verdict (as evidence, not as a gate).
