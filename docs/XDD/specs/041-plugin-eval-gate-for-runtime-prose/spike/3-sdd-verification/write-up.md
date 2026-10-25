# SDD verification spike (2026-10-25)

Four questions the SDD could not answer from the documentation, answered by running them. Claude Code 2.1.310, `--ablation none`, total spend about $0.73.

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Does `--model` override an agent's own `model:`? | **No — it sets the main session only.** With `--model claude-sonnet-5-5` the trace shows the main session on sonnet and the conductor on `claude-haiku-5-5`. Without `--model` the main session ran opus, the conductor haiku. | `audit-gates-delivery`, runs 1, $0.05 |
| 2 | Can a scaffold script reach files beside it? | **Yes.** `$0` and `BASH_SOURCE` are the script's original path inside the plugin directory; `pwd` is the empty workspace. The scaffold env carries `HOME`, `TMPDIR`, `PATH` of the run, no `EVAL_*`. A directory under `evals/` with no `case.yaml`/`prompt.md` (`_lib/`) does not break loading. | `evals/scaffold-probe/`, $0.16 |
| 3 | Is `match: contains` accepted? | **Yes**, alongside the documented default. | `scaffold-probe` grader 1 |
| 4 | Is `main` green 3/3? | **Ordering and STRICT stop: yes** (6/6 runs, $0.31, 83 s). **Relay: no** (see below). | spike-2 cases + `evals/withheld-notices-relayed/` |

## The relay probe on `main`

`withheld-notices-relayed`: real notice lines rendered by Tomo's own `render_md` (`real_lines.py`), relay files staged in `tomo-tmp/`, leak bait (`act-LEAK…`, guard names, `run_id:`) on the `instruction-render` stub's stderr. Runs 3, $0.16, score 0.944.

- **Run 0 failed "relay lines are the last lines".** The conductor appended a `Files used:` block of absolute temp paths after the notices. The main session relayed the report faithfully, so the deviation is the conductor's.
- **The conductor wrote `Run ID: \`2026-10-24T00-00-00Z-eval01\`` into its report** in both inspected runs. The report template carries no run id. The probe's leak grader missed it because it matched the bait marker `evalLEAK`, not the run-id format the `run-id.py` stub actually prints — a gap in the probe, not evidence the prose is safe.
- Every notice line itself was copied character for character in all three runs, and none of the stderr bait reached the final message.

## Running these

`build.sh` assembles `tomo/` beside itself from the conductor at `main` plus the spike-2 cases; copy `evals/scaffold-probe` and `evals/withheld-notices-relayed` into `tomo/evals/` (or rerun `add_relay_case.py` from a scratch copy). Every run needs `--scaffold --allow-tools Bash --trust-plugin` and **must run outside Claude Code's Bash sandbox** — inside it the eval harness fails with `run could not start (EPERM)`. `tail_msgs.py <trace.jsonl>` prints the conductor's report and the main session's final message from a kept run (`--keep-temp`).
