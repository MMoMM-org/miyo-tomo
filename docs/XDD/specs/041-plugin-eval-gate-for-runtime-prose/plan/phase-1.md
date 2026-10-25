---
title: "Phase 1: Runner, verdict and stub kit"
status: pending
version: "1.1"
phase: 1
---

# Phase 1: Runner, verdict and stub kit

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View; Components, responsibility matrix]`
- `[ref: SDD/Internal API Changes; C1, C2, C3]`
- `[ref: SDD/Implementation Examples; "Verdict derivation (C2)", "The canonical leak guard", "A case scaffold"]`
- `[ref: SDD/Runtime View; Primary Flow, Error Handling, Complex Logic "Assemble plugin copy"]`
- `[ref: SDD/ADR-1, ADR-2, ADR-3, ADR-4, ADR-5, ADR-6, ADR-8]`
- `[ref: SDD/Implementation Gotchas]`

**Key Decisions**:
- **Fixtures are real results, never invented** (memory: fixtures mirror live output). `spike/results/` holds five real `aggregate-result.json` files: all green (`conductor-cases-green-3x.json`), one red run among three (`relay-red-one-run.json`, case score 0.944), a red pre-fix arm (`pre-4350ddd-red.json`), a run that could not start (`eperm-in-sandbox.json`), and a model-override run. The two shapes never observed — a cost-cap partial and a missing result file — are covered by T1.1's one capture run and by a deleted-file test.
- **Exactly one paid call in this phase**: T1.1's cap-hit capture (`--max-cost-usd 0.01`, one probe case, expected ≤ $0.10), outside the Claude Code Bash sandbox, with the user's approval for that command. Nothing else in Phase 1 reaches the real binary.
- **Tests never touch the real repo, `tomo-instance/`, `tomo-privat` or `~/.tomo`.** The runner reads its repo root from `TOMO_EVALS_REPO_ROOT` (default: the repo holding the script); runner tests point it at a `tmp_path` `git init` copy carrying fixture cases. An autouse fixture sets `CLAUDE_BIN` to a fake and `HOME` to `tmp_path`; the runner itself refuses (exit 3) when `PYTEST_CURRENT_TEST` is set and `CLAUDE_BIN` is not.

**Dependencies**: none.

---

## Tasks

Delivers everything the gate needs except the cases themselves: a verdict reader whose GREEN cannot be faked by a partial, errored or missing result; a runner that assembles the plugin and can never write into the repo or reach the paid binary from a test; a stub kit that stages a realistic workspace; and the canonical leak guard.

- [ ] **T1.1 Verdict reader** `[activity: backend-api]` `[parallel: true]` `[component: C2]`

  1. Prime: SDD C2 interface, the verdict example and its traced walkthrough `[ref: SDD/Internal API Changes; C2]` `[ref: SDD/Implementation Examples; Verdict derivation]`; the five files in `spike/results/`
  2. Capture (paid, once): run the `scaffold-probe` case from `spike/3-sdd-verification/evals/` with `--max-cost-usd 0.01 --runs 2` outside the sandbox; commit the result as `tests/fixtures/eval_results/cost-cap-partial.json` and note in the fixture README which keys it actually carries (`partial`, `partialReason`?). If the CLI does not produce a partial at that cap, record that and keep C2's `partial`-only rule.
  3. Test (RED — `scripts/lib/eval_verdict.py` does not exist), `tests/test_eval_verdict.py`, fixtures copied from `spike/results/` into `tests/fixtures/eval_results/`: green-3x → `GREEN`, exit 0, line carries cases passed/total, runs, cost, duration, Claude version, tree state, results path `[ref: PRD/F2-AC1]`; relay-red-one-run → `RED`, exit 1, stderr names `(withheld-notices-relayed, 4-…, run 0)` although the CLI's score was 0.944 `[ref: PRD/F2-AC2]`; pre-4350ddd-red → `RED` naming both ordering graders; cost-cap-partial → `NOT GRADED`, exit 2, even though every graded run passed `[ref: PRD/F2-AC3]`; eperm-in-sandbox → `NOT GRADED`, exit 2, with the sandbox hint `[ref: PRD/F2-AC5]`; a copy of green-3x with one run's `error` set to a rate-limit text → `NOT GRADED`; a missing file, an empty file, invalid JSON, `schemaVersion: 2` → `NOT GRADED`, exit 2, no traceback; `--partial-suite` prefixes `PARTIAL SUITE — does not satisfy the merge rule` `[ref: PRD/F8-AC1]`; `--mutation`/`--rev` echoed in the line; `--compare green-3x relay-red` lists exactly the differing (case, grader) pairs and nothing else `[ref: PRD/F9-AC1]`; `verdict.txt` written beside the result
  4. Implement: `scripts/lib/eval_verdict.py`, stdlib only, file-level WHY docstring, `# version: 0.1.0`
  5. Validate: RED → GREEN; ruff clean; every RED proven by reverting the branch that makes it pass (memory: prove RED by reverting)
  6. Success: no input — real, partial, errored, missing or malformed — produces GREEN unless every grader of every run passed `[ref: SDD/ADR-8]`

- [ ] **T1.2 Stub kit and canonical leak guard** `[activity: backend-api]` `[parallel: true]` `[component: C3]`

  1. Prime: `spike/2-conductor-cases/scaffold.sh` (seed) and `spike/3-sdd-verification/add_relay_case.py` (bait, relay lines); real formats at `tomo/scripts/instructions-diff.py:762-765,1276-1282`, `tomo/scripts/run-id.py:5`, `tomo/scripts/lib/render_md.py:838-890`; `tomo/scripts/instruction-render.py:274-328` (relay file unlinked when empty); `tomo/schemas/routing-plan.schema.json`; `spike/3-sdd-verification/real_lines.py` to regenerate the notice text `[ref: SDD/Internal API Changes; C3]` `[ref: SDD/ADR-3, ADR-4, ADR-5]`
  2. Test (RED — kit does not exist), `tests/test_eval_suite_shape.py` part 1: sourcing the kit in `tmp_path` with each parameter combination stages the documented files; every stub appends its name + argv to `tomo-tmp/calls.log`; the audit stub prints exactly `RESULT: OK — 1/1 actions reconciled.` (exit 0) or the mismatch line + `RESULT: FAIL — count or coverage mismatch above.` (exit 1); the `run-id.py` stub output matches `^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-[0-9a-f]{6}$`; relay files are absent after staging, present after the `instruction-render.py` stub ran with `WITHHELD_DELETES`/`WITHHELD_ATTACH` > 0, and **absent** after it ran with 0; the staged routing plan validates against `tomo/schemas/routing-plan.schema.json`; the render stub's stderr carries the bait; `evals/_lib/no-leak.md`'s pattern (Python `re` accepts this pattern's syntax) matches the **observed** leaks — `Run ID: \`2026-10-24T00-00-00Z-eval01\`` is *not* matched by the hex alternative (that is why the kit prints hex) but `/private/tmp/e-uWtF9E/home/cwd/tomo-tmp/routing-plan.json` is — and the **synthetic** ones, labelled as such: a hex run id, `/var/folders/…`, `/Volumes/…`, each guard name, `act-LEAK7a1`; it does **not** match any notice line (including `/inbox --pass2 --force` in the attachment remedy), the suggestions-doc name, or `RESULT: OK — 1/1 actions reconciled.` `[ref: PRD/F6-AC1]`
  3. Implement: `evals/_lib/stubs.sh` (`stage_instance`; header comment naming each copied string's source file and line), `evals/_lib/no-leak.md`
  4. Validate: RED → GREEN; `bash -n`; bash 3.2 compatible (no `declare -A`, no `mapfile`)
  5. Success: a case scaffold is three variables and one `source` `[ref: SDD/Implementation Examples; A case scaffold]`

- [ ] **T1.3 Runner** `[activity: backend-api]` `[component: C1]`

  1. Prime: T1.1, T1.2; `scripts/update-tomo.sh:1-60` (header, `print_help`, `SCRIPT_DIR`/`REPO_ROOT` pattern); `scripts/cleanup-tomo.sh` (rm guard pattern); `tests/test_update_tomo_sync_gaps.py` (subprocess pattern) `[ref: SDD/Internal API Changes; C1]` `[ref: SDD/Runtime View]` `[ref: SDD/ADR-1, ADR-6, ADR-8, ADR-9]`
  2. Test (RED — `scripts/run-evals.sh` does not exist), `tests/test_run_evals.py`. Fixture: a `tmp_path` git repo with `tomo/dot_claude/{agents,skills,commands,settings.json}` and `evals/` holding one fixture case (kit-based, with `9-no-leak.md`), `TOMO_EVALS_REPO_ROOT` pointing at it, `HOME=tmp_path/home`, and a fake `claude` on `CLAUDE_BIN` that records argv, snapshots the plugin dir it was given, and writes a chosen fixture result into `--output-dir`. Tests: no-argument run passes `--ablation none --threshold 1.0 --runs 3 -j 2 --no-publish --trust-plugin --scaffold --allow-tools Bash --model sonnet --max-cost-usd 5` and the three `tomo-tmp/evals/<TS>/` outputs `[ref: PRD/F1-AC1, F1-AC3]`; `--model` follows the fixture's `settings.json` (`haiku` there → `haiku` passed); the snapshot's `agents/` is byte-identical to the source (no frontmatter rewritten) `[ref: PRD/F2-AC6]`; the snapshot holds `.claude-plugin/plugin.json` `{"name": "tomo"}`, `agents/`, `skills/`, `commands/`, `evals/` without `results/`; the temp dir is gone after exit 0, after the fake exits 1, 2 and 130 `[ref: SDD/Complex Logic]`; fake exits 1 or 2 **with** a result → C2's verdict decides (RED / NOT GRADED), the runner does not abort under `set -e`; fake exits 2 with **no** result → NOT GRADED exit 2 `[ref: PRD/F2-AC5]`; `--rev <sha>` takes the runtime dirs from that commit while `evals/` stays the working tree's; `--mutation <name>` patches the snapshot, never the fixture repo; a non-applying patch → exit 3, fake never invoked; the fixture repo's `git status --porcelain` + tracked-file hash, and `HOME/.tomo`, identical before/after every test `[ref: PRD/F1-AC2]`; a fake that writes into the fixture repo during the run → NOT GRADED exit 2 naming the path; fake `--version` below 2.1.269 → exit 3 before eval is invoked `[ref: PRD/F1-AC5]`; `--max-cost-usd 9` and `EVAL_MAX_COST_USD=9` reach the CLI, the default stays 5 on the next call `[ref: PRD/F2-AC4]`; `--case` unknown → exit 3 listing cases `[ref: PRD/F8-AC2]`, known → verdict PARTIAL SUITE `[ref: PRD/F8-AC1]`; `evals/` with no case → exit 3; a case without a byte-identical `graders/9-no-leak.md` → exit 3 `[ref: PRD/F6-AC2]`; `--runs` without `--case`/`--mutation`/`--rev` → exit 3; `CLAUDE_BIN` unset under pytest → exit 3; `--help` documents runs, cost, results path, exit codes 0–3 and the sandbox requirement `[ref: PRD/F1-AC6]`
  3. Implement: `scripts/run-evals.sh` (bash 3.2, `# version: 0.1.0`, `print_help`, `CLAUDE_BIN`, `TOMO_EVALS_REPO_ROOT`, `mktemp -d "$TMPDIR/tomo-evals.XXXXXX"` + trap; `rm -rf` only on that path; the CLI call guarded so its exit code is captured, not fatal)
  4. Validate: RED → GREEN; `bash -n`; shellcheck if installed; every RED proven by reverting the guarding branch
  5. Success: the runner cannot spend money on a malformed invocation or from a test, and cannot change the repo `[ref: SDD/Quality Requirements; Security]`

- [ ] **T1.4 install/update never deliver `evals/`** `[activity: validate]` `[parallel: true]` `[component: C8]`

  1. Prime: `scripts/install-tomo.sh:12` (`TOMO_SOURCE`), `:1195-1260`; `scripts/update-tomo.sh:370-465`; `tests/test_update_tomo_sync_gaps.py:26-60` (how it resolves `REPO_ROOT`, `_make_minimal_instance`) `[ref: SDD/Constraints CON-2]`
  2. Test, `tests/test_eval_suite_not_synced.py` (its own file — T1.2 owns `test_eval_suite_shape.py`): (a) static — every copy source path in both scripts resolves under `$TOMO_SOURCE` (`$REPO_ROOT/tomo`), so nothing outside it, `evals/` included, can be a source; red if a copy line with a source outside `$TOMO_SOURCE` is added (apply locally, revert); (b) dynamic — copy `scripts/` and `tomo/` into a `tmp_path` tree, add a sentinel `evals/_lib/sentinel.txt` **there**, run the update into a minimal instance in the same `tmp_path`, assert no instance file carries the sentinel name or content. Neither part writes into the real repo `[ref: PRD/F1-AC4]`
  3. Implement: `tests/test_eval_suite_not_synced.py`
  4. Validate: passes; (a) red under its stated local mutation, then reverted
  5. Success: placement of `evals/` is proven safe, not assumed `[ref: PRD/F1-AC4]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - `./venv/bin/python -m pytest tests/test_eval_verdict.py tests/test_run_evals.py tests/test_eval_suite_shape.py tests/test_eval_suite_not_synced.py` green; full `./venv/bin/python -m pytest tests/` green (memory: diff-scoped review misses full-suite failures); `./venv/bin/ruff check scripts/lib tests`; `git status` in the real repo shows only the new files; the only paid call was T1.1's capture.
