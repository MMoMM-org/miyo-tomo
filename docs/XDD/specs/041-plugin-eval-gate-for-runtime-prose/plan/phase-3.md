---
title: "Phase 3: Conductor Step 4 fix"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Conductor Step 4 fix

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-10]`
- `[ref: SDD/Implementation Boundaries]` — the only runtime file this spec may change
- `[ref: SDD/Deployment View; Multi-Component Coordination]` — WHY → runtime → sync → verify
- `CLAUDE.md` Rules — runtime files carry imperatives only; WHY lives in `docs/tomo/<mirrored-path>.md`; STRICT only after an observed deviation, one-line `Why:`
- `tomo/dot_claude/agents/synthesis-conductor.md:199-237` (Step 4), `docs/tomo/dot_claude/agents/synthesis-conductor.md`
- `tests/test_039_t5_1_reporting.py:412-425` — Step 4 may hold exactly one STRICT paragraph naming `withheld-deletes.md`, and its `Why:` must mention "remedy"
- `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/baseline.md` (T2.2)

**Key Decisions**:
- The WHY is written to the docs mirror **before** the runtime edit (CLAUDE.md: strip-first destroys institutional knowledge; here: write-first keeps the runtime file imperative-only).
- Step headers do not move — `tests/test_synthesis_conductor_step_order.py` pins their positions.
- The new STRICT block governs the whole report and does **not** name `withheld-deletes.md` (so `test_039_t5_1_reporting.py` keeps finding exactly one relay STRICT block). The existing relay block already says "the last lines of the report" and was broken anyway — the new block is a report-level rule, not a rewording.
- Sync targets `tomo-instance` only, never `tomo-privat` (memory: tomo-privat is live).

**Dependencies**: Phase 2 (T2.2 baseline RED recorded).

---

## Tasks

Makes the conductor's report end at the relay lines and carry no internals, proven by the gate rather than by reading the prose.

- [ ] **T3.1 WHY for the new Step 4 rules** `[activity: documentation]`

  1. Prime: `baseline.md`; the existing Step 4 section of `docs/tomo/dot_claude/agents/synthesis-conductor.md` `[ref: SDD/ADR-10]`
  2. Test: n/a (documentation). Checklist: the observed deviations with the baseline's pass counts — trailing `Files used:` block with absolute paths; run id in the report; raw render stderr quoted with action ids and guard names (`9-no-leak` 0/3 in every case); headings between the relay lines (`4-deletes-then-attachment-last` 0/3); relay markup dropped (2/3); `RESULT:` line paraphrased (`3-audit-result-in-report` 1/3); why the `Coverage audit:` line is the RESULT line verbatim (the owner and the gate read the audit's own words); why the relay lines are consecutive and last (the owner reads the shell, the lines are the last thing seen); why no internals — run id, action id, guard/function name, raw stderr, file, path, script name (ADR-11, Constitution L2); why one STRICT carries all three rules (owner decision, ADR-10 widened 2026-10-25); that the three cases + the leak guard are what keep this true
  3. Implement: edit `docs/tomo/dot_claude/agents/synthesis-conductor.md`
  4. Validate: every claim cites `baseline.md` or a file:line
  5. Success: the rationale exists before the runtime imperative does `[ref: CLAUDE.md Rules]`

- [ ] **T3.2 Conductor Step 4 imperatives + version bump** `[activity: backend-api]`

  1. Prime: T3.1; `synthesis-conductor.md:199-237` (Step 4) and `:239-247` ("What you never do") `[ref: SDD/ADR-10]`
  2. Test (RED — recorded in T2.2): `scripts/run-evals.sh --case withheld-notices-relayed` and the full no-leak graders are RED on 0.23.0; after the edit the full suite is GREEN; `tests/test_synthesis_conductor_step_order.py` and `tests/test_039_t5_1_reporting.py` stay green unmodified
  3. Implement: Step 4 report template and rules, as **one report-level STRICT block** (ADR-10 as widened): the `Coverage audit:` line carries the `RESULT:` line from `instructions-diff.py` character for character; no internals anywhere in the report — run id, action id, guard or function name, raw script stderr line, file name, path, script name; the relay lines consecutive with nothing between them and nothing after them. The block must not name `withheld-deletes.md`. `Why:` "the model paraphrased the RESULT line, quoted run ids, action ids, guard names and temp paths, and put headings between and text after the relay lines."; `# version: 0.23.0` → `0.24.0`
  4. Validate: full suite `scripts/run-evals.sh` GREEN once; if not GREEN, iterate on the imperative wording only (each iteration a partial `--case` run first), record each attempt's verdict line in `baseline.md` under "after"
  5. Success: `main`-candidate conductor passes every gate grader in 3/3 runs `[ref: PRD/F3-AC3, F5-AC1…AC4, F6-AC1]`

- [ ] **T3.3 Instance sync** `[activity: validate]`

  1. Prime: memory "update-tomo is version-gated AND needs --yolo", "sync before any live walk"; `scripts/update-tomo.sh --help` `[ref: SDD/Deployment View]`
  2. Test: n/a. Checklist: dry run first (`-n`) shows `↑ update` for `synthesis-conductor.md` and nothing unexpected
  3. Implement: `scripts/update-tomo.sh --instance tomo-instance --yolo`
  4. Validate: `rg '^# version' tomo-instance/.claude/agents/synthesis-conductor.md` shows 0.24.0
  5. Success: the test instance runs the fixed prose `[ref: SDD/Deployment View]`

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Full pytest green (incl. the step-order test); ruff clean; full eval suite GREEN with the verdict line recorded in `baseline.md`; no runtime file other than `synthesis-conductor.md` changed (`git diff --stat main -- tomo/`).
