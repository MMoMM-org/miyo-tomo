---
title: "Phase 4: RED proofs and gate documentation"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: RED proofs and gate documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Application Data Models; Mutation table]`
- `[ref: SDD/ADR-7]`
- `[ref: SDD/Building Block View; C5, C6]`
- `[ref: PRD/F7]`
- memory: "Apply the mutation the docstring NAMES", "Prove a test is RED by reverting the fix", "Which test catches what is a measurable claim"

**Key Decisions**:
- Mutations patch the assembled copy of the **post-Phase-3** prose; a rev-based proof (`4350ddd^`) stays rev-based.
- A mutation counts only if its grader is red in **every** run of the proof (runs 3). A grader that goes red in 1–2 of 3 is recorded as a weak proof and its mutation strengthened, never accepted as is.
- Control graders are exempt and marked as such.

**Carried over from T2.1 review (2026-10-25):**
- `audit-mismatch-stops` has **two** F4-AC4 gate graders (`5-no-write-into-scripts-schemas-config`, `6-no-copy-into-scripts-schemas-config`); each needs its own RED proof in `_mutations/README.md` (`fix-on-mismatch` may prove only one — add a cp-based variant if so). **Outcome:** the "fix the script" mutations never executed (the model refuses to edit scripts); graders 5 and 6 are proven by `write-into-scripts` and `copy-into-config` instead (owner decision 2026-10-25, `red-proofs.md`). The T4.1 patch list below is the original plan.
- T4.3's `evals/README.md` documents the F4-AC4 graders' residual limits: writes that still escape (`python -c "open(...,'w')"`, heredoc python, `patch`, `git checkout`/`git apply`, `dd of=`, `truncate`, `chmod`, `cp -t scripts/ x`, a cp/ln/install split by a backslash continuation, `sed -e '…' -i`, a double-quoted sed expression with an escaped `\"`); over-firing (any path merely ending in `scripts/`/`schemas/`/`config/`, a `description` containing such a command); interpreter graders count `echo python3 scripts/<stem>.py` and a description naming it as a run, and miss `python3 -u scripts/…`.
- The first `--mutation` run confirms the CLI's case loader tolerates `evals/_mutations/` (carried from Phase 1).

**Dependencies**: Phase 3. T4.3 depends only on Phase 2 (case names) and may run in parallel with T4.1/T4.2.

---

## Tasks

Delivers the proof that every gate grader can fail, and the documentation that says when the gate must run.

- [ ] **T4.1 Mutation patches and index** `[activity: backend-api]` `[component: C5]`

  1. Prime: SDD Mutation table; post-Phase-3 `synthesis-conductor.md` `[ref: SDD/Application Data Models; Mutation table]`
  2. Test: `tests/test_eval_conductor_cases.py` (RED — no `_mutations/` yet): every patch in `evals/_mutations/` applies cleanly (`patch --dry-run -p1`) to a fresh assembly of the working tree; every gate grader of every case is named in `_mutations/README.md` by at least one mutation or rev; every grader not named is listed as a control; every mutation named in the README has a patch file and vice versa `[ref: PRD/F7-AC4, F7-AC5]`
  3. Implement: `evals/_mutations/{drop-audit-line,always-notice,summarise-mismatch,fix-on-mismatch,paraphrase-relay,files-used-after,attachments-first,report-run-id}.patch`; `evals/_mutations/README.md` table: mutation or rev → cases → expected red graders (what it proves) → side-effect reds (other gate graders it is expected to turn red, e.g. `files-used-after` also turns `9-no-leak` red); `report-run-id` lists all three cases; `attachments-first` rewrites the "followed by" sentence in Step 4 (the `cat` order does not decide output order); controls listed
  4. Validate: shape test green; each patch reviewed against the grader it claims (the patch changes what the grader observes, not a neighbouring behaviour)
  5. Success: every gate grader has a named, reproducible proof `[ref: SDD/ADR-7]`

- [ ] **T4.2 Run every proof** `[activity: validate]` `[component: C5]`

  1. Prime: T4.1 `[ref: PRD/F7-AC4]`
  2. Test: each proof run (`scripts/run-evals.sh --rev 4350ddd^ --case <c>` / `--mutation <m> --case <c>`, `--runs 3`) is RED on its expected graders in 3/3 runs, and on no gate grader outside expected ∪ side-effect (an unexpected red is investigated, not ignored); `report-run-id` is run once per case
  3. Implement: record each proof's verdict line and per-grader pass counts in `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/red-proofs.md`
  4. Validate: every gate grader red in 3/3 under its proof; cost total noted
  5. Success: no gate grader is unproven `[ref: PRD/F7-AC4]`

- [ ] **T4.3 Gate documentation** `[activity: documentation]` `[parallel: true]` `[component: C6]`

  1. Prime: `CLAUDE.md` Rules; `docs/ai/memory/tools.md`; `README.md`; memory "CLI change → grep dot_claude/skills" `[ref: SDD/Building Block View; C6]`
  2. Test: `tests/test_eval_conductor_cases.py` (RED — docs absent): every path in the `evals/README.md` coverage table exists; every case directory appears in it; root `CLAUDE.md` Rules contains the gate rule naming `evals/README.md`. Plus the checklist — `evals/README.md` lists every covered runtime file (`tomo/dot_claude/agents/synthesis-conductor.md`; `tomo/dot_claude/commands/inbox.md`, whose dispatch prompt the cases reproduce; `tomo/dot_claude/settings.json`, whose `model` the gate pins) with the cases covering it `[ref: PRD/F7-AC1]`; explains how to run (sandbox bypass or `!`), what each exit code means, how to add a case (kit variables, the leak-guard copy, adding new guard names to the pattern, a mutation per gate grader); root `CLAUDE.md` Rules: a change to a file in that list needs a full-suite GREEN before merge, verdict line in the PR `[ref: PRD/F7-AC2]`, and nothing for other files `[ref: PRD/F7-AC3]`; `docs/ai/memory/tools.md` entry; one `README.md` pointer; `docs/ai/memory/memory.md` Critical Documentation line (docs/CLAUDE.md rule)
  3. Implement: the five edits above
  4. Validate: every path named in the docs exists (`rg` each); the coverage list matches the cases' actual targets
  5. Success: a coding session can tell from the repo alone whether its change needs the gate `[ref: PRD/F7-AC2, F7-AC3]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Shape test green incl. mutations; full pytest green; ruff clean; `red-proofs.md` complete; docs paths verified.
