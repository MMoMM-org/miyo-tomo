# Runtime-prose eval suite

`claude plugin eval` runs Tomo's LLM-read runtime prose against stubbed scripts and grades what the model does. Run it with `scripts/run-evals.sh`; it prints one verdict line.

## Coverage

One list: which runtime files the suite covers and which cases cover them. A change to a file in this table needs a full-suite GREEN before merge (root `CLAUDE.md` Rules). A change to any other file needs nothing from this suite.

| Runtime file | Cases |
|---|---|
| `tomo/dot_claude/agents/synthesis-conductor.md` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` |
| `tomo/dot_claude/commands/inbox.md` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` |
| `tomo/dot_claude/settings.json` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` |

- The conductor is the subject. Every case dispatches it with the prompt from `inbox.md`'s Pass 2 dispatch, reproduced verbatim (agent name namespaced as `tomo:synthesis-conductor`).
- `inbox.md` is listed because the cases reproduce its dispatch prompt: if that prompt changes, the cases must change with it.
- `settings.json` is listed because the runner pins the eval's main model to its `model` field.

## Running

```bash
scripts/run-evals.sh                      # full suite, 3 runs per case: the only run that satisfies the merge rule
scripts/run-evals.sh --case <glob>        # one case: PARTIAL SUITE, never satisfies the merge rule
scripts/run-evals.sh --help               # all options
```

The eval harness cannot start inside Claude Code's Bash sandbox (runs fail with EPERM and end NOT GRADED). Run it from a terminal, or from a coding session with the sandbox bypassed for that one command (`!scripts/run-evals.sh` in the prompt).

Exit codes:

| Code | Verdict | Meaning |
|---|---|---|
| 0 | GREEN | every grader passed in every run of every case |
| 1 | RED | at least one grader failed; stderr names case, grader and run |
| 2 | NOT GRADED | cost cap, API or rate-limit error, scaffold failure, harness error, interrupt, or the repo changed during the run. Not a pass. |
| 3 | REFUSED | preflight failed before anything was spent (old `claude`, no cases, missing leak guard, unknown `--case`/`--mutation`/`--rev`, unreadable settings, bad options) |

Results land in `tomo-tmp/evals/<TS>/` (gitignored): `aggregate-result.json`, `report.html`, `verdict.txt`.

Cost: about $0.20 per case at 3 runs (measured on the first three cases: $0.60 for 3 cases x 3 runs), so about $1.00 for the five cases (not yet measured). The default cap is $5 (`--max-cost-usd` or `EVAL_MAX_COST_USD`); hitting it gives NOT GRADED.

## Reading a failure

1. The RED stderr names the case, grader and run.
2. Re-run with `--keep-temp`. The CLI seals the kept workspaces mode 000: `chmod -R u+rwX /private/tmp/e-*` before opening them.
3. In the trace, the Agent tool_result is the conductor's own report. The final message is the main session relaying it. A grader on `last_message` sees the relay, not the report: check which of the two deviated.

## Adding a case

1. Create `evals/<name>/` with `case.yaml`, `scaffold.sh` and `graders/`.
2. `scaffold.sh` sets the kit variables, then sources the kit and stages the instance:
   - `AUDIT_RESULT=ok|fail`
   - `WITHHELD_DELETES=0|1|2`
   - `WITHHELD_ATTACH=0|1`
   - optional, `ok` when unset: `UPLOAD_RESULT=ok|fail` (upload exits 1 with its partial-failure block), `FLIP_RESULT=ok|fail` (state flip exits 1, transition rejected)
   - `. "$(dirname "$0")/../_lib/stubs.sh"` then `stage_instance`
3. Every case carries the leak guard: copy `evals/_lib/no-leak.md` to `graders/9-no-leak.md` byte for byte. The runner refuses a case without it (exit 3). When a new internal name (script, filter, file, run-id format) can reach the user-facing report, add it to the guard's `pattern` in `evals/_lib/no-leak.md` and re-copy it into every case.
4. A grader that only confirms a precondition (for example `3-audit-ran`) is a control. Every other grader needs a mutation that turns it red: see `evals/_mutations/README.md` for the mutations and the RED proofs.
5. Add the case to the coverage table above. If it covers a new runtime file, add that file too. `tests/test_eval_gate_docs.py` fails when a case or a path is missing from the table.

## Known limits

Residual limits of the F4-AC4 graders (`5-no-write-into-scripts-schemas-config`, `6-no-copy-into-scripts-schemas-config`), the pattern-based checks that nothing was written into `scripts/`, `schemas/` or `config/`:

- Writes that still escape: `python -c "open(...,'w')"`, heredoc python, `patch`, `git checkout`/`git apply`, `dd of=`, `truncate`, `chmod`, `cp -t scripts/ x`, a cp/ln/install split by a backslash continuation, `sed -e '…' -i`, a double-quoted sed expression with an escaped `\"`.
- Over-firing: any path merely ending in `scripts/`, `schemas/` or `config/`; a `description` containing such a command.
- The interpreter graders count `echo python3 scripts/<stem>.py` and a description naming it as a run, and miss `python3 -u scripts/…`.

Known gaps:

- `upload-failure-reported` and `state-flip-failure-reported` (#205) measure the conductor's `<step> exited <code> for "<note>".` line, but their gate graders have no RED proof in `evals/_mutations/README.md` yet.
- Subagent tool calls appearing in traces is observed (spike), not documented by Anthropic. The `3-audit-ran` control is the canary: if it goes red with no prose change, suspect the trace first.
