---
title: "Phase 1: Stand-ins and runner swap"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Stand-ins and runner swap

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Internal API Changes]`: `stage_pass1_instance` variables and the runner swap.
- `[ref: SDD/Application Data Models]`: the workspace files and the strict-stub rules.
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2, ADR-6]`
- `[ref: PRD/Feature 3]`
- `evals/_lib/stubs.sh` header: the convention for citing source formats.

**Key Decisions**:
- The stand-in analyst comes from the working tree even under `--rev`, exactly like `evals/`.
- Each stub's output format is copied from the real script, and the kit header cites the script and line for every format.
- Stubs fail loudly on argv that `suggest-handling` never passes.

**Dependencies**:
- None. This phase costs nothing: pytest, shellcheck, no `claude` call.

---

## Tasks

This phase makes Pass 1 runnable in a throwaway workspace, end to end, with no Kado and no real analyst.

- [x] **T1.1 The runner swaps in the analyst stand-in** `[activity: backend]` `[parallel: true]`

  1. Prime: `scripts/run-evals.sh` assembly block and preflight; `tests/test_run_evals.py` fake-`CLAUDE_BIN` pattern `[ref: SDD/Internal API Changes; ADR-1]`
  2. Test:
     - The assembled copy's `agents/inbox-analyst.md` is byte-identical to `evals/_lib/inbox-analyst.stub.md`, also under `--rev`.
     - A `--mutation` patch targeting the stand-in still applies after the swap.
     - The repo's `tomo/dot_claude/agents/inbox-analyst.md` hash is unchanged.
     - A missing stub file gives REFUSED (3) and makes no `claude` call.
  3. Implement:
     - The swap and the preflight check go into `scripts/run-evals.sh`. Bump `# version:` 0.1.4 → 0.2.0.
     - Move the spike's `inbox-analyst.stub.md` to `evals/_lib/`. It runs the stand-in script with `path`, `item_key` and `run_id` from its inputs, and replies `done <path>`.
     - Help text: the cost line now covers 7 cases.
  4. Validate: the runner tests pass and shellcheck is clean.
  5. Success:
     - The stand-in is in every assembled copy `[ref: PRD/F3; SDD/ADR-1]`.
     - The missing-stub refusal spends nothing `[ref: SDD/Error Handling]`.

- [x] **T1.2 Pass 1 stub kit** `[activity: backend]` `[parallel: true]`

  1. Prime:
     - `suggest-handling/SKILL.md` steps 1–7: every script call with its exact flags.
     - The real scripts' output lines: `read-routing-plan.py`, `read-config-field.py`, `run-id.py`, `shared-ctx-builder.py` (the WARN line), `suggestions-reducer.py` (the summary line), `suggestions-render.py`, `kado-write-file.py`, `mark-captured.py`, `inbox-triage.py`.
     - `tomo/scripts/lib/item_key.py` `to_filename`.
     - The spike scaffold `[ref: SDD/Application Data Models]`
  2. Test: new `tests/test_pass1_stub_kit.py` runs `stage_pass1_instance` in a tmp dir and then calls the stubs with the argv the skill uses.
     - Each variable combination (0/0, 1/1) produces the expected files and stderr lines.
     - An invalid variable value gives `return 1`.
     - The stand-in script writes `items/<to_filename(key)>` and one state line per item.
     - The reducer stub fails with exit 2 when there are fewer results than state lines. Otherwise it writes 3 sections and `proposed_mocs` of length `DUPLICATES + 1`, consistent with its summary line.
     - The render stub output is over 1 KB and has 3 `## ` sections.
     - Every stub exits 2 with `stub <name>: unexpected argv` on an unknown flag.
     - The conductor file is staged from `$(dirname "$0")/../../agents/` (ADR-6).
     - Nothing is written outside the tmp dir: the test snapshots `$HOME/.tomo` and the repo tree before and after.
  3. Implement:
     - `evals/_lib/pass1-stubs.sh`, bash 3.2, with a header that cites the source format of every stub.
     - The stand-in script `scripts/analyst-stub.py`, written by the kit into the workspace.
  4. Validate: the kit tests pass, shellcheck is clean, ruff is clean.
  5. Success:
     - Plausible, consistent stand-ins `[ref: PRD/F3-AC1, F3-AC2]`
     - Loud failure on unknown calls `[ref: PRD/F3-AC3]`
     - No writes outside the workspace `[ref: PRD/F3-AC4]`

- [x] **T1.3 Phase Validation** `[activity: validate]`

  - Run the full pytest suite (`./venv/bin/python -m pytest -q`): Phase 1 must not break the existing 041 runner or docs tests.
  - Check shellcheck on the runner and the kit.
  - Confirm `git status` shows only the Phase 1 files.
