# Spike 043: Pass 1 eval feasibility and cost

Run once, from a terminal (the eval harness cannot start in Claude Code's sandbox):

```bash
docs/XDD/specs/043-pass1-conductor-eval-gate/spike/run-spike.sh
```

The cost cap is $1, with 2 cases × 1 run. Results land in `tomo-tmp/spike043/results/`. Because of `--keep-temp`, the traces stay under `/private/tmp/e-*/` (sealed mode 000; `chmod -R u+rwX /private/tmp/e-*` to read them).

## What it answers

| Question | Evidence |
|---|---|
| Q1. Does the eval session expand `/tomo:inbox` and impersonate the conductor? | `pass1-suggest-probe` graders 01 (no Agent call for the conductor), 13 (Pass 1 report) and 14 (skill name in trace) |
| Q2. Does the bare `subagent_type: "inbox-analyst"` in the skill prose resolve to the plugin agent, so the stub can replace it? | 02 (3 Agent calls), 03 (the stub's `analyst-stub.py` ran 3×), 04 (`"agentType":"tomo:inbox-analyst"` in the trace) |
| Q3. Is the skill loaded under impersonation? | 14, plus reading the trace for a `Skill` or `Read` call on `suggest-handling` |
| Q4. Which Pass 1 behaviours are gradeable today, and which are RED on the current prose? | 05–12. A red result here is a finding, not a spike failure |
| Q5. Does a `regex` grader on `target: trace` see the conductor's own return (`tool_use_result`, hand-back frame)? | `report-only-probe` graders a, b and c-canary. `report-only-probe` is a copy of `upload-failure-reported`; its existing graders stay in it |
| Q6. What does one Pass 1 case cost? | `aggregate-result.json`, cost per case |

## Parts

- `run-spike.sh` assembles the plugin from the working tree into `tomo-tmp/spike043/plugin`, swaps in the analyst stub, copies the two cases and runs the eval.
- `evals/_lib/inbox-analyst.stub.md` (moved out of the spike by T1.1) is the stand-in analyst: haiku, Bash only. It logs the item path through `scripts/analyst-stub.py` and replies `done <path>`.
- `pass1-suggest-probe/` stages an `action: suggest` instance with 3 fresh sources, one of them in a subfolder (`Places/Dresden.md`). It sets `BATCH_SIZE=2`, so there are 2 batches. Every Pass 1 script is stubbed, with output copied from the real scripts: a tracker `WARN:` line from shared-ctx-builder, and `duplicate_proposals_converted=1` from the reducer.
- `report-only-probe/graders/` holds the three trace graders. They were validated offline against the kept #205 traces: red on `e-zGLuXk` (the status-sentence run), green on `e-FKMwKu`, `e-BffdUn` and `e-qc5JkS`. The canary matched exactly once in each.
