# Spike 043: results

The run was on 2026-10-30 with `claude` 2.1.314 and sonnet as the main session. Both cases ran once (`--runs 1`). The total cost was **$0.296** and the run took 58 s.

| Case | Score | Turns | Cost | Duration |
|---|---|---|---|---|
| `pass1-suggest-probe` | 10/14 | 8 (the last of 3 result frames) | $0.207 (sonnet $0.204, haiku stubs $0.003) | 58 s |
| `report-only-probe` | 9/10 | 2 | $0.089 | 30 s |

The traces were kept as `/private/tmp/e-t7N3jn` (Pass 1) and `/private/tmp/e-O6bppm` (report-only). Every number below comes from those traces and from `tomo-tmp/spike043/results/aggregate-result.json`.

## Q1. Is the conductor impersonated? Yes

- The main session made no `Agent` call for `suggestion-conductor` (grader 01 green).
- Following `inbox.md`, the main session read `.claude/agents/suggestion-conductor.md` itself (trace frame 6) and then ran the pipeline in its own context.
- A Pass 1 case therefore enters through `/tomo:inbox`.
- `last_message` is the conductor's own report: the final `result` frame carries the conductor's text.

## Q2. Does the analyst stub replace the real agent? Yes

- The conductor dispatched with `subagent_type: "tomo:inbox-analyst"`. It added the plugin namespace itself; the skill text says only `inbox-analyst`.
- The stub agent ran: `analyst-stub.py` was called 3× (grader 03). `subagent_stats.by_type` shows `{"tomo:inbox-analyst": 3}`.
- The haiku stub costs $0.003 for all three items.
- Grader 04 (`"agentType":"tomo:inbox-analyst"`) was red, but that is a defect in the grader, not in the routing. The analysts were launched **in the background** (`started_in_background: 3`), so their `tool_use_result` says only "Async agent launched", and the `agentType` field never appears. The signal to use is `"subagent_type":"tomo:inbox-analyst"` (found 27×).

**New finding: background dispatch.** The main session ends its turn while it waits, and the harness wakes it with a `task_notification` frame. One case therefore produces several `result` frames: 3 here. The batch discipline held: batch 2 was dispatched only after both batch 1 notifications (frames 73 and 78, then frame 84). The grader must still read the *last* frame, and it did.

## Q3. Is the skill loaded under impersonation? Yes

The main session called `Skill("tomo:suggest-handling")` (frame 9) and then followed the skill's steps literally. Grader 14 is green.

## Q4. What can be graded today?

Green, and the behaviour was really observed:

- 06: setup runs before the first dispatch.
- 05: the subfolder path `100 Inbox/Places/Dresden.md` reaches the analyst unchanged as both `path` and `item_key`.
- 02: there are 3 dispatches with batch size 2.
- 07: the reducer runs before the renderer.
- 10: no `python3 -c`.
- 11: the `WARN:` line is relayed verbatim.

Not reached (08, 09, 12):

- **The stubs were too thin.** The analyst stub wrote no `items/*.result.json`, the reducer stub wrote `{}`, and the renderer stub wrote `# Suggestions` (14 bytes).
- The conductor noticed this *after* the first vault write. It then stopped before the JSON write and before `mark-captured`, and reported the inconsistency in detail. That is correct behaviour on inconsistent input, but it means a case never reaches the end of the pipeline.
- **Consequence for the SDD:** the stubs must produce plausible artifacts:
  - the analyst stub writes a result file,
  - the reducer writes a document with 3 sections and 1 proposed MOC,
  - the renderer writes a markdown file with 3 sections.

**Grader 13 was a false positive.** `Pass 1 complete` matched inside "I did not report "Pass 1 complete", because it isn't." Report graders need an anchor at the start of a line, matching the template in `suggest-handling` line 171 (`Pass 1 complete: {N} items analysed`).

No RED was observed on the current text up to the point where the run stopped.

## Q5. Can a trace grader see the conductor's own return? Yes, through the hand-back frame

| Grader | Result | Cause |
|---|---|---|
| a. `tool_use_result` (pattern A) | ❌ red | In 2.1.314, `tool_use_result.content` begins with an extra `{"type":"text","text":"<tools-used-before-summary>Bash</tools-used-before-summary>\n"}` element, and every report line is quoted with `> `. The format changed after the offline validation against the #205 traces. |
| b. hand-back frame (pattern B) | ✅ green | `[Subagent hand-back] … The report follows:` then the indented `> ` lines |
| c. canary `count: 1` | ✅ green | Exactly one hand-back frame |

**Consequence:** use pattern B together with the canary. The harness format is a dependency of the grader, and it has already changed once. The canary has to fail when the frame disappears, so that a format change shows up red and does not silently turn into "pattern absent".

## Q6. What does a case cost?

- One Pass 1 run is **$0.21**, measured on a run that stopped before its last 3 steps. A complete run is estimated at **$0.23–0.27**: three more tool calls at a stable cache-read cost.
- That is well below the research estimate of $0.45–0.90.
- At the gate standard of `runs: 3`, one Pass 1 case costs about **$0.70–0.80 per gate run**.

| Pass 1 cases | Extra per gate run | Within +$0.60–0.80? | Within the $5 cap? |
|---|---|---|---|
| 1 | ~$0.75 | yes | yes |
| 2 | ~$1.50 | no | yes |
| 3 | ~$2.25 | no | yes |

The report-only grader is free: it adds three regex graders to the existing `upload-failure-reported` case, so the spec needs no new case for it.

## What changes for the PRD and SDD

1. The analyst stub agent works. Keep it, and point it at plausible result files.
2. The script stubs have to write plausible artifacts, not just print plausible stdout.
3. Report graders are anchored at the start of a line.
4. The report-only grader uses pattern B plus the canary, and the grader documents its version dependency.
5. Dispatch graders use `subagent_type`, not `agentType`.
6. The PRD has to address the background dispatch (several `result` frames per case). The gate already handles it.
7. The case count is an owner decision: the budget allows 1 Pass 1 case, and the cap allows 3.
