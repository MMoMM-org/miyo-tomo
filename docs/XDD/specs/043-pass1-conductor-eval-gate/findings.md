# Spec 043 — Phase 3 findings

Every red grader from a paid run, with its cause and the trace line that shows it.

Causes:

- **(a) prose finding.** The model deviated from the runtime prose. The fix goes in the prose.
- **(b) stand-in fidelity.** The eval stand-in behaves differently from production.
- **(c) pattern defect.** The grader is wrong.

## Smoke 1 — 2026-10-31

Command: `scripts/run-evals.sh --case 'pass1-*' --runs 1 --keep-temp`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · pass1-suggest-pipeline: 14-report-line-anchored (run 0), pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 0), pass1-warn-and-duplicates-relayed: 03-duplicate-line (run 0), pass1-warn-and-duplicates-relayed: 04-report-line-anchored (run 0) · runs 2 · $0.47 · 44 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T09-36-30Z
```

Kept traces:

- `pass1-suggest-pipeline`: `/private/tmp/e-lJ52Dv/out/trace.jsonl` (94 lines).
- `pass1-warn-and-duplicates-relayed`: `/private/tmp/e-jFOZJj/out/trace.jsonl` (111 lines).

Both runs completed the whole pipeline:

- setup;
- 2 batches with 3 analyst dispatches;
- reduce, render, both writes with the same stem `2026-10-30_0000`, and mark-captured;
- the report.

All other graders were green, including:

- relay 01 (`WARN:` verbatim in the reply);
- the conductor-not-dispatched, setup, order, write and mark graders;
- the leak guard in both cases.

### Red graders

| # | Case / grader | Cause | Evidence (trace line) | Fix |
|---|---|---|---|---|
| F1 | pipeline `14-report-line-anchored` | (a) | e-lJ52Dv:90, the final text begins `Pass 1 is complete. The analysts processed 3 items (Alpha, Dresden, Gamma) with no failures, and the suggestions are written to [[2026-10-30_0000_suggestions]].` The step 7 template is `Pass 1 complete: {N} items analysed, suggestions written to [[<date>_suggestions]].` | Make the step 7 lines a verbatim template in `suggest-handling` |
| F2 | relay `04-report-line-anchored` | (a) | e-jFOZJj:106, `Pass 1 complete: 3 items analysed (Alpha, Dresden, Gamma). Suggestions are written to [[2026-10-30_0000_suggestions]].` The item list is inserted and the clause reworded. | Same fix as F1 |
| F3 | relay `03-duplicate-line` | (a) | e-jFOZJj:106, `1 proposed MOC already existed in the vault and is offered as an unticked link instead.` The template is `{n} proposed MOC(s) already existed in the vault and are offered as unticked links instead.`, so the model singularised it. | Same fix as F1 (the duplicate line is part of the step 7 template) |
| F4 | relay `02-warn-before-first-dispatch` | (a), the expected finding (Decisions Log 2026-10-30) | e-jFOZJj:23 is the `WARN:` line in the shared-ctx-builder tool_result. The only reaction before the first dispatch (e-jFOZJj:51) is a **thinking** block at e-jFOZJj:42, which the user never sees. The verbatim relay first appears in the final report, e-jFOZJj:106 ("Earlier warning from setup, repeated verbatim"). The STRICT under step 2 ("before dispatching anything") was read as "somewhere in the reply". | Require a visible assistant message carrying the `WARN:` lines before step 3's first `Agent` call |

### Observations (not red; recorded for follow-up)

| # | Observation | Evidence | Disposition |
|---|---|---|---|
| O1 | (b) The first dispatch used the bare `subagent_type: "inbox-analyst"` that the skill shows. The eval registers only the plugin agent `tomo:inbox-analyst`, so the call failed (`Agent type 'inbox-analyst' not found`) and the model retried with the namespaced name. In production the instance carries a project-level `inbox-analyst`, so the bare name resolves. | e-lJ52Dv:34–39 (2 failed calls, then 3 good ones). The relay run used `tomo:` directly (e-jFOZJj:51). | No grader is affected: 02 counts only `tomo:inbox-analyst` and was 3/3. It costs one extra turn. Not fixed in the prose, because the bare name is correct for production. |
| O2 | The report carries extra notes after the template: the agent-name retry and a "filename date is a day behind" remark (e-lJ52Dv:90), and the stem-date remark (e-jFOZJj:106). | e-lJ52Dv:90, e-jFOZJj:106 | Not graded for Pass 1 (F1-AC9 asks that the reply *begins* with the line). The leak guard stayed green. The verbatim-template fix may reduce it. |
| O3 | HHMM source. Both runs took `0000` from the run timestamp (`2026-10-30T00:00:00Z`), not from the wall clock. | e-lJ52Dv:84, e-jFOZJj:100 | Known issue (SDD). Grader 10 checks only that the two writes share a stem. |
| O4 | Harness facts confirmed on `claude` 2.1.316: `--case 'pass1-*'` works as a glob, `tomo:inbox-analyst` resolves to the stand-in (`analyst-stub.py` ran 3× per case), and the final text was graded by `last_message` (relay 01 green on the last text). | the verdict line; e-lJ52Dv:47,56,72 | The memory note on `last_message` is consistent with this run. Both readings agree here, so the run does not discriminate between them. |
| O5 | The spike's `9-no-leak` red did not reproduce. The leak guard is green in both complete runs. | the verdict line | Confirms the drift review: the spike result was an artefact of its early stop. |

## Smoke 2 — 2026-10-31

Command: `scripts/run-evals.sh --case 'pass1-*' --runs 1 --keep-temp`, on
`suggest-handling` 0.13.0 (the F1–F4 fixes).

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 1/2 cases · pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 0) · runs 2 · $0.38 · 38 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T10-19-30Z
```

Kept traces:

- `pass1-suggest-pipeline`: `/private/tmp/e-zxesgn/out/trace.jsonl` (92 lines).
- `pass1-warn-and-duplicates-relayed`: `/private/tmp/e-XygOSA/out/trace.jsonl` (107 lines).

Trace line numbers count from 0, as in smoke 1.

Both runs completed the whole pipeline, setup through the report, with 3
analyst dispatches each and no failed `Agent` call (O1 did not recur).

### Closed

| # | Evidence |
|---|---|
| F1 | e-zxesgn:88, the reply begins `Pass 1 complete: 3 items analysed, suggestions written to [[2026-10-31_1120_suggestions]]. Review in Obsidian, check the **Approved** box, then re-run `/inbox`.` |
| F2 | e-XygOSA:105, the same line exactly. |
| F3 | e-XygOSA:105, `1 proposed MOC(s) already existed in the vault and are offered as unticked links instead.` (not singularised). |

### Red graders

| # | Case / grader | Cause | Evidence (trace line) | Fix |
|---|---|---|---|---|
| F4 (persists) | relay `02-warn-before-first-dispatch` | (a) | e-XygOSA:23 is the `WARN:` line in the shared-ctx-builder tool_result. After the two `read-config-field.py` calls, the only reaction before the first dispatch (e-XygOSA:53) is a non-empty **thinking** block at e-XygOSA:47 ("The shared-ctx builder flagged two active trackers, mood and sleep, missing keywords … I'll run /tomo-setup trackers …"), followed directly by the batch-count `Bash` call at e-XygOSA:48. There is no assistant text block. The final report repeats the `WARN:` line verbatim (e-XygOSA:105; relay 01 green). Same pattern as smoke 1 (thinking at e-jFOZJj:42). The 0.13.0 wording ("send them to the user now … as a text message of your own (not a thought)") was read at the right place and answered in thinking. | `suggest-handling` 0.13.1: a `STRICT` block at the top of step 3 whose output is a fixed `text` reply (`Setup warnings:` + the `WARN:` lines), required before the batch-count command; thinking named as not counting |

### Observations (not red; recorded for follow-up)

| # | Observation | Evidence | Disposition |
|---|---|---|---|
| O3 (changed) | HHMM source. Both runs now ran `date +%Y-%m-%d_%H%M` and used the wall clock (`2026-10-31_1120`), not the run timestamp. | e-zxesgn:79, e-XygOSA:96 | Grader 10 still checks only that the two writes share a stem. |
| O6 | The thinking block that reacted to the `WARN:` line (e-XygOSA:47) has a signature whose base64 decodes to bytes containing the marker `narration`; the empty thinking blocks of the same run (e-XygOSA:53, :65) decode to `thinking` instead. | the `signature` fields at those lines | Observation only. The non-empty block may be summarised thinking rather than the raw thought, and the signature format is not a documented contract. Nothing is built on it. |

## Smoke 3 — 2026-10-31

Command: `scripts/run-evals.sh --case pass1-warn-and-duplicates-relayed --runs 1 --keep-temp` (`suggest-handling` 0.13.1)

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 0) · runs 1 · $0.20 · 41 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T10-50-48Z
```

Kept trace: `/private/tmp/e-QKbc19/out/trace.jsonl`. Line numbers count from 0.

F4 persists for the third time, in the same shape:

- e-QKbc19:23 is the `WARN:` tool_result.
- e-QKbc19:48 is a non-empty thinking block: "Setup check found two active trackers—mood and sleep—missing keywords … I'll need to run /tomo-setup trackers …".
- e-QKbc19:49 is the batch-count `Bash` call. No `Setup warnings:` text block was written.
- e-QKbc19:53 is the first dispatch.

The fixed-text `STRICT` of 0.13.1 was answered in thinking, like the duty wording of 0.13.0. Every other grader in the case stayed green.

## Smoke 4 — 2026-10-31

Command: `scripts/run-evals.sh --case pass1-warn-and-duplicates-relayed --runs 1 --keep-temp` (`suggest-handling` 0.14.0, the Plan B `cat` relay)

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 0) · runs 1 · $0.21 · 50 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T11-11-16Z
```

Kept trace: `/private/tmp/e-GDBsiX/out/trace.jsonl`. Line numbers count from 0.

F4 persists for the fourth time:

- e-GDBsiX:28 is the new `cat tomo-tmp/setup-warnings.txt` call, and e-GDBsiX:29 its result: the `WARN:` line, exactly as saved. The model ran the relay command at the right place.
- e-GDBsiX:47 is a non-empty thinking block that paraphrases the warning ("I noticed the "mood" and "sleep" trackers have no keywords set … I'll run /tomo-setup trackers …").
- e-GDBsiX:48 is the batch-count call. No text block came between them.

In all four runs the reaction is a non-empty thinking block in the same place (O6), and it reads like a message to the user. It never appears as a text block. The relay command itself works: the verbatim `WARN:` line now sits in a tool result before the first dispatch (e-GDBsiX:54).

## F4 disposition — 2026-10-31

**Closed by owner decision (F2-AC2 redefined).** F4 is not fixed in the prose; the criterion is redefined. A tool result counts as showing the warning to the user, because Claude Code displays Bash output. F2-AC2 is now met when the `cat tomo-tmp/setup-warnings.txt` call, whose result carries the `WARN:` line, runs before the first `Agent` call (README Decisions Log 2026-10-31; requirements F2-AC2).

Why:

- **4/4 thinking-only.** Four wordings (0.12.x duty, 0.13.0 named vehicle, 0.13.1 fixed-text `STRICT`, 0.14.0 copy-the-`cat` `STRICT`) all produced the same thing: a non-empty thinking block at the top of step 3 and no text block.
- **The tool result is visible and deterministic.** It needs no reaction from the model after the call: the result carries the saved lines verbatim.

Evidence on smoke 4 (`/private/tmp/e-GDBsiX/out/trace.jsonl`, lines from 0):

- e-GDBsiX:28 is the Bash tool_use `{"command":"cat tomo-tmp/setup-warnings.txt"}`.
- e-GDBsiX:29 is its tool_result: `WARN: 2 active tracker field(s) have no keywords; … mood, sleep. Run /tomo-setup trackers …`, exactly as the builder printed it.
- e-GDBsiX:54 is the first dispatch.

Consequences:

- Relay grader 02 checks the `cat` tool_use and its next tool_result, both before the first Agent call (SDD Complex Logic). Evaluated offline on the four kept traces: red on e-jFOZJj, e-XygOSA and e-QKbc19 (their prose had no `cat`), green on e-GDBsiX.
- Relay grader 01 (the `WARN:` line verbatim in the final reply) is unchanged. It was green in all four smokes.
- `suggest-handling` 0.14.1 keeps `--warnings-out` and the step 3 `cat`, and drops the text-reply `STRICT`.
- The mutation `warn-in-report-only` removes the `cat` and keeps only the step 7 repeat, so the new grader 02 goes red on it.
