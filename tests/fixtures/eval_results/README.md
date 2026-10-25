# eval_results fixtures

Real `claude plugin eval` aggregate results (schemaVersion 1), used by `tests/test_eval_verdict.py`.
Tests copy them to `tmp_path` before running the reader so `verdict.txt` never lands here.

| Fixture | Source | Represents | Keys of note |
|---|---|---|---|
| `green-3x.json` | spike/results/conductor-cases-green-3x.json | Every grader of every run passed (3 cases, `audit-*`) | `partial: false`, per-run `error: null` |
| `relay-red.json` | spike/results/relay-red-one-run.json | One of three runs failed one grader; the CLI case score is 0.944 | run 0 grader `4-deletes-before-attachments-and-last` failed; CLI `passed` is not trusted |
| `pre-4350ddd-red.json` | spike/results/pre-4350ddd-red.json | Two cases, both ordering graders failing, before the fix commit | `tool_order` graders failed in both cases |
| `eperm-in-sandbox.json` | spike/results/eperm-in-sandbox.json | Run could not start inside the Bash sandbox | run `error` = "run could not start (EPERM) ...", `graders: []`, `score: 0` |
| `model-override-green.json` | spike/results/model-override-green.json | Single-case green with `modelOverride` | `suite.modelOverride` set |
| `cost-cap-partial.json` | captured 2026-10-25, claude 2.1.310, `--max-cost-usd 0.01 --runs 2 --ablation none --model sonnet`, cost $0.064, CLI exit 2 | Run stopped by the cost ceiling | `partial: true`, `partialReason: "cost_ceiling"`; no `aborted` key anywhere; the one run that executed passed (`error: null`, score 1); `runsPerCase: 1` although `--runs 2` was passed (case.yaml says `runs: 1`; whether case.yaml won or the cap stopped scheduling is unclear, recorded as observed) |

Deviation from the plan: the `scaffold-probe` scaffold was sanitised before the capture (the spike
version dumped `env | sort` into the model output); the captured run writes only `dollar0=probe` and the
sibling marker, so no environment values are in a committed fixture.
