---
title: "Phase 2: Cases, shared graders and offline validation"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Cases, shared graders and offline validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples]`: the pipeline grader table (01–15), the relay grader table (01–04) and the report-only grader.
- `[ref: SDD/Complex Logic]`: the ordered trace regexes and the offline validation table.
- `[ref: SDD/Implementation Gotchas]`: JSON-encoded `input_match`, `min: 0` with `max: 0`, anchoring on the event shape, anchored report lines.
- `[ref: SDD/ADR-3, ADR-4, ADR-5]`
- `[ref: PRD/Features 1, 2, 4]`

**Key Decisions**:
- Every regex pattern on `target: trace` is validated offline before any paid run. The checks run on the spike traces plus hand-edited variants, and they are committed as fixtures so they can be re-run without paying.
- The offline check uses Python `re`; the harness runs JS regex. Patterns stay inside the common subset: no lookbehind beyond what 041 already used, no possessive quantifiers. Backreferences (`\1`) and lookaheads are allowed.

**Dependencies**:
- Phase 1. The cases source `pass1-stubs.sh` and rely on the stand-in swap.

---

## Tasks

This phase delivers all gate cases and graders, each proven offline against real traces.

- [ ] **T2.1 Offline grader-pattern harness and trace fixtures** `[activity: testing]`

  1. Prime: spike traces `e-t7N3jn` (Pass 1) and `e-O6bppm` (Pass 2), and the grader YAML frontmatter format `[ref: SDD/Complex Logic; offline validation table]`
  2. Test: `tests/test_043_grader_patterns.py` loads each `regex` grader's frontmatter from `evals/*/graders/*.md` (and `evals/_lib/*.md`) and evaluates `pattern`, `match` and `count` against the fixtures. Each fixture declares its expected pass/fail per grader.
  3. Implement:
     - Fixtures under `docs/XDD/specs/043-pass1-conductor-eval-gate/fixtures/`:
       - the spike Pass 1 trace;
       - the Pass 2 trace;
       - hand-edited variants: WARN relayed before the first dispatch, WARN relayed after it, reducer moved before a dispatch, two writes with the same stem, a status sentence before the report, a duplicated hand-back frame.
     - Keep the fixtures trimmed to the lines that matter, and replace absolute paths with a neutral placeholder.
     - The loader is shared with T2.2–T2.4.
  4. Validate: the harness passes on the patterns already validated in the SDD.
  5. Success: the offline validation table in the SDD is reproducible by one pytest command `[ref: SDD/ADR-5; Quality Requirements/Reliability]`

- [ ] **T2.2 Case `pass1-suggest-pipeline`** `[activity: testing]` `[parallel: true]`

  1. Prime: the pipeline grader table `[ref: SDD/Implementation Examples; PRD/F1]`
  2. Test: add expectations to T2.1.
     - On the fixtures, every trace grader gives its expected verdict.
     - `tool_used` / `tool_order` graders are checked with a small evaluator over the fixture's tool_use events, using the JSON-encoded input exactly as the harness sees it.
  3. Implement:
     - `evals/pass1-suggest-pipeline/`:
       - `case.yaml`: prompt `/tomo:inbox`, `allowed_tools: [Agent, Bash, Read, Skill]`, `max_turns: 60`, `timeout_seconds: 900`, `runs: 3`.
       - `scaffold.sh`: `SHARED_CTX_WARN=0 DUPLICATES=0`, then `stage_pass1_instance`.
       - graders 01–15 and a byte copy of `9-no-leak.md`.
  4. Validate: the pattern tests pass, and `run-evals.sh` preflight accepts the case (a dry run with a fake `CLAUDE_BIN` under pytest).
  5. Success: every PRD F1 criterion has a grader `[ref: PRD/F1-AC1…AC10]`

- [ ] **T2.3 Case `pass1-warn-and-duplicates-relayed`** `[activity: testing]` `[parallel: true]`

  1. Prime: the relay grader table and the WARN-before-dispatch walkthrough `[ref: SDD/Complex Logic; PRD/F2]`
  2. Test: expectations in T2.1.
     - On the spike trace, relay 02 (WARN before the first dispatch) is red and relay 01 (WARN in the reply) is green.
     - On the "relayed before" fixture both are green; on the "relayed after" fixture 02 is red.
  3. Implement: `evals/pass1-warn-and-duplicates-relayed/` with `SHARED_CTX_WARN=1 DUPLICATES=1`, relay graders 01–04 and the leak guard.
  4. Validate: the pattern tests and the preflight dry run pass.
  5. Success: every PRD F2 criterion has a grader `[ref: PRD/F2-AC1…AC4]`

- [ ] **T2.4 Report-only grader and canary in the Pass 2 cases** `[activity: testing]` `[parallel: true]`

  1. Prime: spike pattern B and canary c (`spike/report-only-probe/graders/`), and the `audit-mismatch-stops` report shape `[ref: SDD/Implementation Examples/Report-only; ADR-4; PRD/F4]`
  2. Test:
     - T2.1 expectations:
       - The report-only grader is green on `e-O6bppm`, red on the status-sentence fixture, and red when the frame is missing.
       - The canary counts exactly 1 on `e-O6bppm` and is red on the duplicated-frame fixture and on the missing-frame fixture.
       - The mismatch pattern is green on a mismatch-report fixture.
     - `tests/test_eval_gate_docs.py`: `7-report-only.md` and `8-handback-canary.md` are byte-identical to `evals/_lib/` in the 4 standard cases, and `audit-mismatch-stops` carries its own `7-report-only-mismatch.md` plus the shared canary.
  3. Implement:
     - `evals/_lib/report-only.md` and `evals/_lib/handback-canary.md`.
     - Copies of both into the 4 standard cases.
     - The mismatch variant in `audit-mismatch-stops`.
  4. Validate: the docs and pattern tests pass.
  5. Success:
     - The report-only grader is in all 5 Pass 2 cases `[ref: PRD/F4-AC1, F4-AC4]`
     - The canary guards the frame `[ref: PRD/F4-AC3]`

- [ ] **T2.5 Mutations** `[activity: testing]`

  1. Prime: `evals/_mutations/README.md` (naming, the neutral-step rule for "never" graders), and the mutation column of the SDD grader tables.
  2. Test: a test in `tests/test_run_evals.py` (or an extension of an existing one) asserts that every new patch applies cleanly to a freshly assembled copy (`patch --dry-run`) and touches only the file it names.
  3. Implement:
     - The Pass 1 patches: `dispatch-conductor`, `analyst-name-not-type`, `path-from-stem`, `setup-in-conductor`, `dispatch-before-setup`, `render-before-reduce`, `reduce-before-batch-2`, `publish-md-with-write-tool`, `mark-before-write`, `inline-python-read`, `reword-report-line`, `always-duplicate-line`, `warn-is-diagnostic`, `warn-in-report-only`, `drop-duplicate-line`.
     - The Pass 2 patch: `status-sentence-first`.
     - Each patch gets a row in `evals/_mutations/README.md` naming the grader(s) it must turn red.
     - "Never" graders (11, 13, 15) use neutral steps.
  4. Validate: the apply test passes.
  5. Success: every non-control grader has a named mutation `[ref: PRD/F5-AC1, F5-AC2, F5-AC3]`

- [ ] **T2.6 Phase Validation** `[activity: validate]`

  - Run the full pytest suite and shellcheck.
  - Confirm that every grader in both Pass 1 cases appears in the offline expectations, and that none is a false positive on the spike trace. Exceptions: graders the spike never reached (the second write, mark-captured, duplicate) are only checked on fixtures.
  - The phase hands to the owner with an exact smoke command for Phase 3.
