# Runtime-prose eval suite

`claude plugin eval` runs Tomo's LLM-read runtime prose against stubbed scripts and grades what the model does. Run it with `scripts/run-evals.sh`; it prints one verdict line.

## Coverage

One list: which runtime files the suite covers and which cases cover them. A change to a file in this table needs a full-suite GREEN before merge (root `CLAUDE.md` Rules), except in a row marked "not gated". A change to any other file needs nothing from this suite.

| Runtime file | Cases |
|---|---|
| `tomo/dot_claude/agents/suggestion-conductor.md` | `pass1-suggest-pipeline`, `pass1-warn-and-duplicates-relayed` |
| `tomo/dot_claude/skills/suggest-handling/SKILL.md` | `pass1-suggest-pipeline`, `pass1-warn-and-duplicates-relayed` |
| `tomo/dot_claude/agents/synthesis-conductor.md` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` |
| `tomo/dot_claude/commands/inbox.md` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported`, `pass1-suggest-pipeline`, `pass1-warn-and-duplicates-relayed` |
| `tomo/dot_claude/settings.json` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported`, `pass1-suggest-pipeline`, `pass1-warn-and-duplicates-relayed` |
| `tomo/dot_claude/skills/note-from-template/SKILL.md` | `note-draft-before-approval` (not gated) |
| `tomo/dot_claude/commands/note.md` | `note-draft-before-approval` (not gated) |

- Pass 2 cases (the five without the `pass1-` prefix): the synthesis conductor is the subject. Each case dispatches it with the prompt from `inbox.md`'s Pass 2 dispatch, reproduced verbatim (agent name namespaced as `tomo:synthesis-conductor`).
- Pass 1 cases (`pass1-*`): the prompt is `/tomo:inbox`. As in production, the main session impersonates the suggestion conductor (it is not dispatched) and loads the `suggest-handling` skill, so the session's final reply is the conductor's own report.
- `inbox.md` is listed because the Pass 2 cases reproduce its dispatch prompt and the Pass 1 cases enter through it: if it changes, the cases must be re-run or changed with it.
- `settings.json` is listed because the runner pins the eval's main model to its `model` field.
- `/note` case (`note-draft-before-approval`, spec 044 ADR-8): the prompt is `/tomo:note` with material that fills every point of the one candidate template, so no question round runs. `AskUserQuestion` cannot be offered in an eval, so the case grades the end of the run: the last message is the approval question, the header and `note.md` are printed before it, `note.md` was read, no question came before the draft, and `deliver` never runs. Its rows are marked "not gated": one recorded run is the evidence, and a later change to the skill or the command needs no eval run. The case holds an `evals/note-draft-before-approval/NOT_GATED` file, so the full suite skips it (stderr prints `skipped (not gated): note-draft-before-approval`) and its verdict and cost cover only the gated cases; it runs only with `--case note-draft-before-approval`.
- Not in the table, so not gated: `force-atomic-handling` (no case covers it), `inbox-analyst` (replaced by a stand-in, see Adding a case), and every script (all stubbed, see Known limits).

## Running

```bash
scripts/run-evals.sh                      # full suite, 3 runs per case: the only run that satisfies the merge rule
scripts/run-evals.sh --case <glob>        # one case: PARTIAL SUITE, never satisfies the merge rule
scripts/run-evals.sh --case note-draft-before-approval   # a not-gated case: runs only when named
scripts/run-evals.sh --help               # all options
```

A case is not gated when its directory holds a `NOT_GATED` file. The default run (no `--case`, also with `--mutation` or `--rev`) leaves it out of the assembled copy and prints one `skipped (not gated): <case>` line per skipped case on stderr; the verdict is still the full-suite verdict, because the merge rule covers only gated cases. Name the case with `--case` to run it (PARTIAL SUITE, as any `--case` run). Mark a case only when its coverage rows say "not gated" (`tests/test_eval_gate_docs.py` checks both agree).

A not-gated case may also hold an `ALLOW_TOOLS` file: tool names separated by spaces or lines (letters, digits and `_` only). A case's `allowed_tools` in `case.yaml` cannot grant a tool; only the CLI's `--allow-tools` can, and the runner passes `--allow-tools Bash` for every case. When `--case` selects a case with `ALLOW_TOOLS`, its tools join that list (`--allow-tools Bash Write AskUserQuestion`) and stderr prints `granted (not gated): <case> <tools>`. The grant applies to the whole eval call, so the runner refuses an `ALLOW_TOOLS` file in a case without `NOT_GATED` and a `--case` glob that matches a case with the file and a gated case. The default run skips not-gated cases and keeps exactly `--allow-tools Bash`; gated cases depend on that (`pass1-suggest-pipeline/11-no-inline-vault-write` relies on Write being absent). A one-run probe: `scripts/run-evals.sh --case note-draft-before-approval --runs 1 --keep-temp`.

The eval harness cannot start inside Claude Code's Bash sandbox (runs fail with EPERM and end NOT GRADED). Run it from a terminal, or from a coding session with the sandbox bypassed for that one command (`!scripts/run-evals.sh` in the prompt).

Exit codes:

| Code | Verdict | Meaning |
|---|---|---|
| 0 | GREEN | every grader passed in every run of every case |
| 1 | RED | at least one grader failed; stderr names case, grader and run |
| 2 | NOT GRADED | cost cap, API or rate-limit error, scaffold failure, harness error, interrupt, or the repo changed during the run. Not a pass. |
| 3 | REFUSED | preflight failed before anything was spent (old `claude`, no cases, missing leak guard, unknown `--case`/`--mutation`/`--rev`, unreadable settings, bad options) |

Results land in `tomo-tmp/evals/<TS>/` (gitignored): `aggregate-result.json`, `report.html`, `verdict.txt`.

Cost and duration, measured on `claude` 2.1.316 (the spec 043 merge evidence, `synthesis-conductor` 0.25.0 on sonnet):

- Full suite (7 cases x 3 runs): $2.74–2.76, 271–310 s wall clock. With the conductor on haiku it was $2.20–2.33 and 298–416 s, and the duration varies with API latency.
- One Pass 1 run: $0.19–0.23 and 38–65 s. One Pass 2 run: $0.09–0.12 and 14–29 s.
- A RED proof (one mutation, one Pass 1 case, 3 runs): about $0.62; one Pass 2 case, 3 runs: about $0.30. Spec 043's RED proofs cost $22.37 in all.

The default cap is $5 (`--max-cost-usd` or `EVAL_MAX_COST_USD`); hitting it gives NOT GRADED.

## Reading a failure

1. The RED stderr names the case, grader and run.
2. Re-run with `--keep-temp`. The CLI seals the kept workspaces mode 000: `chmod -R u+rwX /private/tmp/e-*` before opening them.
3. Pass 2 cases: in the trace, the Agent tool_result is the conductor's hand-back (`The report follows:` … `agentId:`), which the report-only graders read. The final message is the main session relaying it. A grader on `last_message` sees the relay, not the report: check which of the two deviated.
4. Pass 1 cases: the main session is the conductor, so `last_message` is its own report. The analyst dispatches and their results are in the main trace; the analysts' own turns are not.

## Adding a case

1. Create `evals/<name>/` with `case.yaml`, `scaffold.sh` and `graders/`.
2. `scaffold.sh` sets the kit variables, then sources the kit and stages the instance.
   - Pass 2 kit (`evals/_lib/stubs.sh`):
     - `AUDIT_RESULT=ok|fail`
     - `WITHHELD_DELETES=0|1|2`
     - `WITHHELD_ATTACH=0|1`
     - optional, `ok` when unset: `UPLOAD_RESULT=ok|fail` (upload exits 1 with its partial-failure block), `FLIP_RESULT=ok|fail` (state flip exits 1, transition rejected)
     - `. "$(dirname "$0")/../_lib/stubs.sh"` then `stage_instance`
   - Pass 1 kit (`evals/_lib/pass1-stubs.sh`), prompt `/tomo:inbox`:
     - `SHARED_CTX_WARN=0|1` (the shared-context builder prints a `WARN:` line and saves it for the relay)
     - `DUPLICATES=0|1` (the reducer converts one proposed MOC that already exists)
     - `. "$(dirname "$0")/../_lib/pass1-stubs.sh"` then `stage_pass1_instance`
     - The kit's header lists which Tomo script each stub's output is copied from. When one of those scripts changes its output, `tests/test_stub_contract.py` fails; update the stub to follow it.
   - `/note` kit (`evals/_lib/note-stubs.sh`), prompt `/tomo:note <request>`:
     - `NOTE_DRAFTS=none|kept|interrupted|unfrozen|unfinished|unstaged|stale` (a stage directory from an earlier session; the kit header says what each holds)
     - `NOTE_DELIVER=delivered|source_gone|failed_kado_config|failed_<step>|withdrawn|exists_note|exists_instructions_json|exists_destination` (what `deliver` meets; the kit header lists every value)
     - `. "$(dirname "$0")/../_lib/note-stubs.sh"` then `stage_note_instance`
     - The fixture vault (templates, the inbox source note) is written into the eval workspace as `note-fixture.json` next to the stubs. `tests/test_stub_contract.py` runs each stub and its real script on the same argv, the real one against a fake Kado filled from that file (`tests/note_stub_kit.py`), and compares exit code, stdout, stderr and the stage files.
   - The analyst is a stand-in: the runner copies `evals/_lib/inbox-analyst.stub.md` over `agents/inbox-analyst.md` in the assembled plugin (also under `--rev`). It runs one stub script that writes the item's result file and state line, then replies `done`. The eval registers it only as `tomo:inbox-analyst`.
3. Every case carries the leak guard: copy `evals/_lib/no-leak.md` to `graders/9-no-leak.md` byte for byte. The runner refuses a case without it (exit 3). When a new internal name (script, filter, file, run-id format) can reach the user-facing report, add it to the guard's `pattern` in `evals/_lib/no-leak.md` and re-copy it into every case.
4. A grader that only confirms a precondition (for example `3-audit-ran`) is a control. Every other grader needs a mutation that turns it red: see `evals/_mutations/README.md` for the mutations and the RED proofs.
5. Anchor every trace regex on the event shape of a real call (for example `"name":"Bash","input":{…"command":"…`), never on a bare command or phrase. The trace also carries the skill and agent prose, which quotes the same commands, so an unanchored pattern matches the prose and goes green on a run that never made the call. Check a new pattern offline against a kept trace and against the fixtures in `docs/XDD/specs/043-pass1-conductor-eval-gate/fixtures/`.
6. Add the case to the coverage table above. If it covers a new runtime file, add that file too. `tests/test_eval_gate_docs.py` fails when a case or a path is missing from the table.

## Known limits

Residual limits of the F4-AC4 graders (`5-no-write-into-scripts-schemas-config`, `6-no-copy-into-scripts-schemas-config`), the pattern-based checks that nothing was written into `scripts/`, `schemas/` or `config/`:

- Writes that still escape: `python -c "open(...,'w')"`, heredoc python, `patch`, `git checkout`/`git apply`, `dd of=`, `truncate`, `chmod`, `cp -t scripts/ x`, a cp/ln/install split by a backslash continuation, `sed -e '…' -i`, a double-quoted sed expression with an escaped `\"`.
- Over-firing: any path merely ending in `scripts/`, `schemas/` or `config/`; a `description` containing such a command.
- The interpreter graders count `echo python3 scripts/<stem>.py` and a description naming it as a run, and miss `python3 -u scripts/…`.

Limits of the spec 043 graders (the Pass 1 cases and the report-only graders):

- The analysts run in the background. The main session ends its turn while it waits and is woken by a task notification, so one case produces several result frames. `last_message` is the text of the last assistant event that has text (read from the 2.1.316 bundle, consistent with every run so far), not the last frame. Dispatch graders read the dispatch, not the completed result.
- The trace format is a dependency. The report-only graders read the hand-back frame (`[Subagent hand-back] … The report follows:`), validated on `claude` 2.1.314 (spike) and 2.1.316 (every gate run since). The format already changed once, between 2.1.310 and 2.1.314. `8-handback-canary` goes red when the frame moves or repeats, so a format change shows up as red and not as a silent pass.
- The Pass 2 dispatch must stay in the foreground. `claude` 2.1.316 sometimes starts an Agent call in the background although the call does not ask for it (3 of 307 Pass 2 traces up to 2026-11-01); the report then arrives as a task notification, the hand-back frame never appears, and `7-report-only` and `8-handback-canary` go red although the conductor answered correctly. The case prompts and `inbox.md` Step 3b therefore pass `run_in_background: false`. A red `8-handback-canary` with `"is_backgrounded": true` in the conductor's `task_started` event means this happened, not that the conductor deviated.
- The analyst's own behaviour is not covered: the cases run the stand-in. A bare `inbox-analyst` dispatch fails once in the eval and is retried as `tomo:inbox-analyst`; in production the bare name resolves.
- `pass1-suggest-pipeline/14-report-line-anchored` reads the trace, not `last_message`: every content block is its own assistant event in the trace (blocks of one API message share `message.id`), and `last_message` reads only the last event with text, so a preface written as its own text block before the report was invisible to it. The grader requires the completion line as the first content block of the first assistant event after a `tool_result` event that is not a thinking event (system, rate-limit and tool-progress events may sit in between). It depends on the compact JSON key order the trace has today (`"type"` first in each event, `"content":[` then the first block's `"type"`); `pass1-warn-and-duplicates-relayed/04-report-line-anchored` keeps the `last_message` form.
- The wait between batches is not graded. `pass1-suggest-pipeline/09-reduce-after-last-dispatch` checks only that the reducer runs after the last dispatch.
- The source of the HHMM part of the suggestions stem is not graded. `pass1-suggest-pipeline/10-two-script-writes-same-stem` checks only that both writes use the same stem.
- The `WARN:` relay before the first dispatch (`pass1-warn-and-duplicates-relayed/02-warn-before-first-dispatch`) is graded as the `cat tomo-tmp/setup-warnings.txt` call whose result (bound by `tool_use_id`) carries the `WARN:` line, both before the first `Agent` call. A text reply before dispatch is not required: the model answered the warning only in thinking in 4 of 4 runs.
- The Write tool is unavailable in the eval session even though both Pass 1 cases list it in `allowed_tools` ("Write is disabled for this session"). `pass1-suggest-pipeline/11-no-inline-vault-write` still goes red on the attempted call, but a run that tries Write then drifts.
- Every script is a stub. A script's own behaviour (for example the shared-context builder's `--warnings-out` file) is exercised only through its stub, so no script is in the coverage table.
- `tests/test_stub_contract.py` runs most stubs and their real scripts on the same input with Kado faked, and fails when exit code, stream, status line or written keys diverge. It needs no paid run. Not covered: `suggestion-parser.py`, the shared-context reconcile line (the test passes `--skip-reconcile`) and the values of the reducer's and triage's output, where only keys are compared.
- `force-atomic-handling` has no case and is not gated.

Limits of the `/note` case (`note-draft-before-approval`):

- `AskUserQuestion` cannot be offered. `claude plugin eval` leaves it out of the session's tools even with the `ALLOW_TOOLS` grant (probe `tomo-tmp/evals/2026-11-06T07-16-55Z`, recorded with paths redacted in `tests/fixtures/044-note-probe/trace.jsonl` by `redact.py` next to it): the model's ToolSearch for it found nothing, and it asked the approval question as plain text in its final message. The case therefore grades the end of the run, not a question call. Deliver, Change something and Abort, and every dialogue branch, are covered by `tests/test_note_skill_prose.py` and the spec 044 live walk.
- `0-approval-asked` is the control: the last message names Deliver and Abort, so the run ended on the approval question. When it is red, the run stopped elsewhere (silently, on another question, or after a delivery) and the ordering graders tell nothing.
- The ordering graders read the trace and anchor on the first approval attempt: an assistant text event that names Deliver and then Abort, or an `AskUserQuestion` call whose input names Deliver. `1-header-before-approval` and `2-note-printed-before-approval` need the header or the resolved `note.md` body (`Related:` with nothing after it) in an assistant text event at or before that approval, followed by an approval in text; a header inside an `AskUserQuestion` input does not count. `3-note-md-read-before-approval` needs a Read or Bash call naming the staged `note.md` before it; a `cat` counts as a read.
- A grader is one regex with no includes, so two fragments are copied into several graders, and `tests/test_note_eval_case.py` defines each once and fails when a copy differs. The approval fragment `APPROVAL_IN_TEXT` (`[Dd]eliver(?![a-z])` then `[Aa]bort` inside one JSON text value), behind the assistant text event prefix as `APPROVAL_EVENT`, ends graders 1, 2, 3, 5 and 6 (the control `0-approval-asked` uses its `last_message` form). The before-approval guard `BEFORE_APPROVAL` (lines that are neither an `APPROVAL_EVENT` nor an `AskUserQuestion` call naming Deliver) opens graders 1, 2 and 3. Change a fragment in the test and in every grader together.
- `5-no-question-before-approval` counts any question attempt before `stage`: an `AskUserQuestion` call, a ToolSearch whose input names `AskUserQuestion`, or an assistant text event holding a `?`. A sentence ending in `?` before the draft turns it red although nothing was asked.
- `4-draft-md-never-printed` reads every assistant text event for `Related:` followed by `{{source_link}}`; a sentence that only quotes the token passes.
- No grader passes on an empty or truncated run: 4, 5 and 6 each also need a printed note or the approval question. `9-no-leak` (a byte copy) passes on an empty last message and is paired with the control.
- The case's `ALLOW_TOOLS` file grants Write and `AskUserQuestion` when it runs with `--case`. Write is offered with it; `AskUserQuestion` is not (above).

Known gaps:

- `upload-failure-reported` and `state-flip-failure-reported` (#205) measure the conductor's `<step> exited <code> for "<note>".` line. Every one of their gate graders was red in 3/3 under its mutation (`evals/_mutations/README.md`; verdicts in `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/red-proofs.md`, section #205).
- The eval's outer session sometimes adds its own sentence when it repeats the Pass 2 conductor's report (seen in 2 of 6 runs). That is why the report-only graders read the hand-back frame in the trace and not `last_message`; the outer session's relay itself is not graded for shape.
- Subagent tool calls appearing in traces is observed (spike), not documented by Anthropic. The `3-audit-ran` control is the canary: if it goes red with no prose change, suspect the trace first.
