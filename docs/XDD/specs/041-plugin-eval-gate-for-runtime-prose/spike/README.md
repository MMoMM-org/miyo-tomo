# Spike artifacts for #174

Archived from the session scratchpad on 2026-10-25 so they outlive `/tmp`. Run results (`evals/results/`, `result.json`) are not kept; the outcomes are recorded in the #174 comments and in each `write-up.md`.

These are reference material and seeds for spec 041, not the suite. The permanent suite lives in top-level `evals/`.

| Directory | Question it answered | Outcome |
|---|---|---|
| `1-subagent-visibility/` | Can an eval run reach a plugin subagent and observe its Bash calls? | Yes. `tool_used` and `tool_order` count calls made inside a subagent (`parent_tool_use_id`). The negative control (`probe-runner.negative-control.md`) turns the graders red. |
| `2-conductor-cases/` | Do stubbed-script cases catch the `4350ddd` ordering defect and observe the STRICT stop? | Yes. Green on `main`, red on `4350ddd^`. `build.sh` assembles both plugins; `scaffold.sh` is the template (`__AUDIT_EXIT__` placeholder) that `build.sh` instantiates per case. |

| `3-sdd-verification/` | Does `--model` override an agent's model? Can a scaffold reach its siblings? Is `match: contains` valid? Is `main` green 3/3? | `--model` sets the main session only; yes; yes; ordering and STRICT stop 6/6 green, relay **not** green (a trailing `Files used:` block once in three runs, and a run id in the report). See its `write-up.md`. |

Known gaps in the spike-2 seed, deliberately not fixed here:

- The scaffold's `routing-plan.json` has no `timestamp`, so it does not validate against `tomo/schemas/routing-plan.schema.json`. The conductor never validates the plan, so the spike was unaffected.
- `runs: 1` throughout. A gate needs `runs: 3` or more.
- `4-diff-reported-verbatim.md` uses `match: contains`. The documented default is "found" when `match` is omitted; check whether `contains` is an accepted value before reusing it.

The one edit made on archiving: `build.sh` derives `REPO` from `git rev-parse --show-toplevel` instead of a hardcoded absolute path.

Sanitised before the branch was published (this repository is public): in `results/*.json` the local absolute paths (`suite.root`, `plugins[].path`, every `tracePath`) were replaced by the placeholders `/tmp/eval/tomo` and `/tmp/eval/out/` (same method as `tests/fixtures/eval_results/`; the files still parse as JSON, nothing else changed). The line that dumped the shell environment (`env` piped to `sort`) was removed from the probe scaffold in `3-sdd-verification/` (`build.sh` and `evals/scaffold-probe/scaffold.sh`), which dumped the whole environment into the model output. `tests/test_eval_gate_docs.py` keeps both out.
