---
title: "Phase 2: Cases and the baseline on main"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Cases and the baseline on main

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Application Data Models; "The three cases and their graders"]`
- `[ref: SDD/Implementation Examples; The canonical leak guard]`
- `[ref: SDD/Implementation Gotchas]` — JS-regex escaping, `$` without `m`, namespaced agent, identical dispatch prompt
- `[ref: SDD/ADR-4, ADR-5, ADR-9]`
- `tomo/dot_claude/commands/inbox.md:64-71` — the dispatch prompt, verbatim

**Key Decisions**:
- This is the first phase that spends money. Every paid run happens outside the Claude Code Bash sandbox (ADR-9) and after the user approved the sandbox bypass for that command.
- The baseline runs on the conductor **exactly as on `main`** (0.23.0). It is expected to be RED on the relay case and on the leak guard; that red is the evidence Phase 3's STRICT block rests on. Do not touch the conductor in this phase.

**Carried over from the Phase 1 drift check (2026-10-25)** — T2.1's shape tests (`tests/test_eval_suite_shape.py` part 2) must also assert:
- every `case.yaml` has `runs: 3` — the T1.1 cost-cap capture passed `--runs 2` and got `runsPerCase: 1` from a `runs: 1` case.yaml, so case.yaml may override the runner's `--runs 3`; the verdict does not check the per-case run count;
- `case.yaml` `name` equals the case directory name — the runner's `--case` preflight matches directory names, the CLI matches `name:`;
- every non-underscore subdirectory of `evals/` is a recognised case (holds `case.yaml`) — the runner silently skips others, so they would escape the leak-guard identity check;
- the first paid run confirms the CLI's case loader tolerates `evals/_mutations/` (only `_lib/` was verified in the spike); if `_mutations/` does not exist yet, confirm it in Phase 4's first mutation run instead.

**Dependencies**: Phase 1.

---

## Tasks

Delivers the three cases and the recorded "before": what today's conductor does under the gate.

- [ ] **T2.1 The three cases** `[activity: backend-api]` `[component: C4]`

  1. Prime: seeds `spike/2-conductor-cases/evals/*` and `spike/3-sdd-verification/evals/withheld-notices-relayed/`; T1.2's kit; the SDD case table `[ref: SDD/Application Data Models]`
  2. Test: `tests/test_eval_suite_shape.py` part 3 (RED — no cases yet): exactly `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed` exist; each `case.yaml` has `schema_version "1.1"`, `runs: 3`, `allowed_tools: [Agent, Bash]`, the dispatch prompt text identical to `inbox.md:64-71` apart from the `tomo:` namespace; each scaffold sources `../_lib/stubs.sh`; each has `graders/0-conductor-dispatched.md` and a byte-identical `graders/9-no-leak.md`; every literal-line `regex` grader, once JS-unescaped and stripped of its `(?:^|\n)…(?:\n|$)` anchors, equals the line the kit writes (no hand-retyped notice text); the anchored grader does **not** match the same line inside a table row (`| - ⚠️ … |`) or after a count heading on the same line (test with Python `re` on synthetic messages); then one partial paid run per case (`--case <name> --runs 1`) loads and grades without a harness error
  3. Implement: `evals/audit-gates-delivery/` (graders for F3-AC1/2/3, F5-AC5, no-leak) `[ref: PRD/F3-AC1, F3-AC2, F3-AC3, F5-AC5]`; `evals/audit-mismatch-stops/` (F4-AC1/2/3/4, controls: dispatched, audit ran) `[ref: PRD/F4-AC1…AC4]`; `evals/withheld-notices-relayed/` (one anchored verbatim grader per line; one grader for delete 1 → delete 2 → attachment consecutively and nothing after) `[ref: PRD/F5-AC1…AC4]`; grader file names `<n>-<behaviour>.md`, controls named so the close-out can mark them
  4. Validate: shape test green; the three partial runs graded (any verdict but NOT GRADED/REFUSED)
  5. Success: every PRD F3–F6 criterion has exactly one grader `[ref: SDD/Acceptance Criteria; F3–F6]`

- [ ] **T2.2 Baseline: full suite on `main`'s conductor** `[activity: validate]`

  1. Prime: T2.1; `spike/3-sdd-verification/write-up.md` (what to expect) `[ref: SDD/Risks; Known Technical Issues]`
  2. Test: n/a (measurement). Expected: `audit-gates-delivery` and `audit-mismatch-stops` green apart from no-leak; `withheld-notices-relayed` RED on no-leak (run id now in real hex format) and possibly on the adjacency-and-end grader
  3. Implement: `scripts/run-evals.sh` (full suite, runs 3, sandbox bypass approved by the user); write `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/baseline.md`: the verdict line, per (case, grader) pass counts over 3 runs, cost, duration, and the conductor's offending report lines **quoted only as far as they contain no vault content** (stub output only — there is none)
  4. Validate: the verdict line is RED, not NOT GRADED; if it is GREEN, stop and report — Phase 3's premise (ADR-10) would no longer hold and needs the owner's decision
  5. Success: the before-picture for ADR-10 is recorded `[ref: SDD/ADR-10]`

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  - Shape test green; full pytest green; ruff clean; `baseline.md` committed; total spend for the phase noted in `baseline.md`.
