# Mutations — the RED proof for every gate grader

A gate grader that never goes red proves nothing. Each mutation here is a patch to
the **assembled plugin copy** (never to the repo) that breaks exactly the behaviour
one gate grader observes; `scripts/run-evals.sh --mutation <name>` applies it with
`patch -p1 --forward` from the plugin root and refuses (exit 3) when it no longer
applies. A proof counts only when its expected graders are red in every run.

Run a proof:

- mutation, one case: `scripts/run-evals.sh --mutation <name> --case <case>`
- `report-run-id` is proven for all five cases in one invocation: `scripts/run-evals.sh --mutation report-run-id --case '*'` (the verdict is marked PARTIAL SUITE, as for every proof)
- the #205 proofs run both failed-delivery cases in one invocation: `scripts/run-evals.sh --mutation <name> --case '*-failure-reported'`
- rev: `scripts/run-evals.sh --rev 4350ddd^ --case 'audit-*'`

Every patch also removes or neutralises each clause of the runtime files that
contradicts the behaviour it injects — a surviving STRICT that forbids the injected
behaviour would let the model obey it and leave the grader green (a weak proof).
The clauses each patch removes and adds are listed under **Clauses**, and
`tests/test_eval_conductor_cases.py` checks them against the patched copy.
The neutral-write proofs (`write-into-scripts`, `copy-into-config`) remove nothing:
their injected step is ordinary bookkeeping that no clause forbids.

Refresh a patch when a file it patches changes: edit a copy of the assembled plugin
(`tomo/dot_claude/{agents,skills,commands}` plus the analyst stand-in) in `$TMPDIR` and
regenerate it with `diff -u`, paths relative to the plugin root
(`a/agents/synthesis-conductor.md` / `b/agents/synthesis-conductor.md`,
`a/skills/suggest-handling/SKILL.md`, `a/commands/inbox.md`). A patch that changes
several files is the concatenation of one `diff -u` per file. Never hand-write hunk
headers.

## Proofs

**#205 (recorded 2026-10-26, conductor 0.24.1):** the `failed-step-path`, `flip-after-failed-upload` and `explain-failure` rows, and the two failed-delivery cases added to `drop-audit-line` and `report-run-id`, were each red in 3/3; side-effect reds below are measured. Verdicts: `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/red-proofs.md`, section #205.

Proof of the two F4-AC4 graders by a 'fix the failing script' prompt was tried twice (6 runs) and never executed — the model refuses to edit scripts; the graders are therefore proven with a neutral write.

| Proof | Cases | Expected red (what it proves) | Side-effect reds |
|---|---|---|---|
| `--rev 4350ddd^` | `audit-gates-delivery`, `audit-mismatch-stops` | `audit-gates-delivery/1-audit-before-upload`, `audit-gates-delivery/2-audit-before-state-flip`, `audit-mismatch-stops/1-no-upload-after-mismatch`, `audit-mismatch-stops/2-no-state-flip-after-mismatch` — the pre-fix step order (upload and flip before the audit) | `audit-gates-delivery/9-no-leak`, `audit-mismatch-stops/9-no-leak` (measured 3/3 in both cases: the pre-C7 Step 4 has no leak guard); `audit-gates-delivery/3-audit-result-in-report` (measured 1/3) |
| `--mutation drop-audit-line` | `audit-gates-delivery`, `upload-failure-reported`, `state-flip-failure-reported` | `audit-gates-delivery/3-audit-result-in-report`, `upload-failure-reported/4-audit-result-in-report`, `state-flip-failure-reported/3-audit-result-in-report` — the RESULT line reaches the report only because the template asks for it, also when a later step fails | none |
| `--mutation always-notice` | `audit-gates-delivery` | `audit-gates-delivery/4-no-notice-when-none-withheld` — a missing relay file yields a notice line | `audit-gates-delivery/9-no-leak` (measured 2/3; cause confirmed from traces: the patch drops rule 3's "if neither relay file exists, say nothing", so the conductor comments on the render stub's stderr bait vs the absent relay files and names `tomo-tmp/withheld-*.md`) |
| `--mutation summarise-mismatch` | `audit-mismatch-stops` | `audit-mismatch-stops/4-mismatch-reported-verbatim` — the stop report is a one-sentence summary instead of the audit's output | none |
| `--mutation write-into-scripts` | `audit-mismatch-stops` | `audit-mismatch-stops/5-no-write-into-scripts-schemas-config` — an ordinary bookkeeping step before the audit appends to a file under `scripts/` with `>>` (a concrete command, own Bash call, on every path) | none expected: the run otherwise behaves normally (the audit fails, the stop report follows) |
| `--mutation copy-into-config` | `audit-mismatch-stops` | `audit-mismatch-stops/6-no-copy-into-scripts-schemas-config` — an ordinary snapshot step before the audit `cp`s a file whose destination is under `config/` (a concrete command, own Bash call, on every path) | possible `audit-mismatch-stops/9-no-leak` (measured 1/3 — the conductor mentioned the snapshot step); otherwise the run behaves normally (the audit fails, the stop report follows) |
| `--mutation paraphrase-relay` | `withheld-notices-relayed` | `withheld-notices-relayed/1-delete-1-verbatim`, `withheld-notices-relayed/2-delete-2-verbatim`, `withheld-notices-relayed/3-attachment-verbatim` — the notices are summarised instead of copied | `withheld-notices-relayed/4-deletes-then-attachment-last` (the block is built from the verbatim lines) |
| `--mutation files-used-after` | `withheld-notices-relayed` | `withheld-notices-relayed/4-deletes-then-attachment-last` — text follows the relay lines | `withheld-notices-relayed/9-no-leak` (the file list carries temp file names and paths) |
| `--mutation attachments-first` | `withheld-notices-relayed` | `withheld-notices-relayed/4-deletes-then-attachment-last` — the attachment line comes before the delete lines (the `cat` order does not decide the output order) | none (1–3 stay green: each line is anchored on its own) |
| `--mutation report-run-id` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` | `audit-gates-delivery/9-no-leak`, `audit-mismatch-stops/9-no-leak`, `withheld-notices-relayed/9-no-leak`, `upload-failure-reported/9-no-leak`, `state-flip-failure-reported/9-no-leak` — a run id in the report is caught in every case | none |
| `--mutation failed-step-path` | `upload-failure-reported`, `state-flip-failure-reported` | `upload-failure-reported/1-upload-failure-line-in-report`, `state-flip-failure-reported/1-state-flip-failure-line-in-report` — the failed-step line names the doc by its vault path instead of its note name | `upload-failure-reported/5-no-failure-detail-in-report`, `state-flip-failure-reported/4-no-failure-detail-in-report` (the vault path carries `100 Inbox/`, which the detail guard bans) |
| `--mutation flip-after-failed-upload` | `upload-failure-reported` | `upload-failure-reported/2-no-state-flip-after-failed-upload` — 3d still runs 3e after a non-zero upload exit | none (the flip stub succeeds, so the report is unchanged) |
| `--mutation explain-failure` | `upload-failure-reported`, `state-flip-failure-reported` | `upload-failure-reported/5-no-failure-detail-in-report`, `state-flip-failure-reported/4-no-failure-detail-in-report` — a `Detail:` line copies the failing script's last stderr line into the report | none (`9-no-leak` stayed green in all six runs) |

## Proofs — spec 043 (to be recorded in Phase 4)

Named, not yet run. Each row names the mutation that must turn its graders red; none of
them counts as a RED proof until Phase 4 has run it (3 runs), recorded the verdicts and
the results path in `docs/XDD/specs/043-pass1-conductor-eval-gate/red-proofs.md`, and
moved the row into `## Proofs` with its measured side-effect reds. "Offline model" names
the fixture in `docs/XDD/specs/043-pass1-conductor-eval-gate/fixtures/` whose trace the
expected red looks like; `tests/test_043_grader_patterns.py` shows the grader red on it.

The Pass 1 patches target the file that carries the rule they break — `commands/inbox.md`,
`agents/suggestion-conductor.md` or `skills/suggest-handling/SKILL.md` — and neutralise
the clause in every one of them that repeats it. The "never" graders (pipeline 11, 13, 15)
are proven with a neutral step: an ordinary-looking instruction that happens to do the
forbidden thing (a Write publish, a `python3 -c` read, a count line that is always
reported), never a request to misbehave.

| Proof | Cases | Expected red (what it proves) | Side-effect reds |
|---|---|---|---|
| `--mutation dispatch-conductor` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/01-conductor-not-dispatched` — `/inbox` dispatches the suggestion conductor as a subagent instead of running it itself; offline model: `pass1-conductor-dispatched.jsonl` | not yet measured |
| `--mutation analyst-name-not-type` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/02-analyst-dispatched-3x`, `pass1-suggest-pipeline/03-no-general-purpose` — the dispatch template keys the analyst by `name`, so no dispatch carries `subagent_type`; offline model: `pass1-analyst-name-not-type.jsonl` | not yet measured |
| `--mutation path-from-stem` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/04-subfolder-path-and-key` — each item's path is rebuilt as `<INBOX_PATH>/<stem>.md`, which flattens `Places/Dresden.md`; offline model: `pass1-dresden-path-flattened.jsonl`, `pass1-dresden-key-flattened.jsonl` | not yet measured |
| `--mutation setup-in-conductor` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/05-shared-ctx-once`, `pass1-suggest-pipeline/06-run-id-once` — the conductor runs `run-id.py` and `shared-ctx-builder.py` before the skill runs them again; offline model: `pass1-setup-twice.jsonl` | not yet measured |
| `--mutation dispatch-before-setup` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/07-setup-before-dispatch` — the shared context is built after the last batch, right before Reduce; offline model: `pass1-dispatch-before-setup.jsonl` | not yet measured |
| `--mutation render-before-reduce` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/08-reducer-before-render` — Render is step 4 and Reduce step 5; offline model: `pass1-render-before-reduce.jsonl` | not yet measured |
| `--mutation reduce-before-batch-2` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/09-reduce-after-last-dispatch` — the reducer runs after every batch, so it runs before the second batch is dispatched; offline model: `pass1-reducer-between-dispatches.jsonl` | not yet measured |
| `--mutation publish-md-with-write-tool` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/10-two-script-writes-same-stem`, `pass1-suggest-pipeline/11-no-inline-vault-write` — neutral step: the note is published with the Write tool into the inbox folder, only the wire file goes through `kado-write-file.py`; offline model: `pass1-write-tool-publish.jsonl` | not yet measured |
| `--mutation mark-before-write` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/12a-mark-captured-once`, `pass1-suggest-pipeline/12b-mark-captured-after-json-write` — mark-captured runs after the `.md` write and once more after the `.json` write; offline model: `pass1-mark-before-json-write.jsonl` (12b), `pass1-mark-twice.jsonl` (12a) | not yet measured |
| `--mutation inline-python-read` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/13-no-inline-python` — neutral step: step 1 reads `inbox_path` with a `python3 -c` one-liner instead of `read-routing-plan.py`; offline model: `pass1-inline-python.jsonl` | not yet measured |
| `--mutation reword-report-line` | `pass1-suggest-pipeline`, `pass1-warn-and-duplicates-relayed` | `pass1-suggest-pipeline/14-report-line-anchored`, `pass1-warn-and-duplicates-relayed/04-report-line-anchored` — the report template no longer starts with `Pass 1 complete:`; offline model: `pass1-report-quoted.jsonl` | not yet measured |
| `--mutation always-duplicate-line` | `pass1-suggest-pipeline` | `pass1-suggest-pipeline/15-no-duplicate-line` — neutral step: the duplicate-count line is reported whatever the count, so `DUPLICATES=0` yields `0 proposed MOC(s) already existed …`; offline model: `pass1-complete-relayed.jsonl` | not yet measured |
| `--mutation warn-is-diagnostic` | `pass1-warn-and-duplicates-relayed` | `pass1-warn-and-duplicates-relayed/01-warn-in-reply` — the `WARN:` line is a maintainer diagnostic that needs no action, so it is not relayed; offline model: `pass1-complete.jsonl` | not yet measured |
| `--mutation warn-in-report-only` | `pass1-warn-and-duplicates-relayed` | `pass1-warn-and-duplicates-relayed/02-warn-before-first-dispatch` — the `WARN:` line is relayed verbatim, but only in the step 7 report, after every dispatch; offline model: `pass1-warn-after-dispatch.jsonl` | not yet measured |
| `--mutation drop-duplicate-line` | `pass1-warn-and-duplicates-relayed` | `pass1-warn-and-duplicates-relayed/03-duplicate-line` — the reducer's summary line is for the log, so the duplicate line is not reported; offline model: `pass1-complete.jsonl` | not yet measured |
| `--mutation status-sentence-first` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` | `audit-gates-delivery/7-report-only`, `audit-mismatch-stops/7-report-only-mismatch`, `withheld-notices-relayed/7-report-only`, `upload-failure-reported/7-report-only`, `state-flip-failure-reported/7-report-only` — the synthesis conductor begins its reply with one status sentence before the report (the canary `8-handback-canary` must stay green); offline model: `pass2-status-sentence.jsonl`, `pass2-mismatch-status-sentence.jsonl` | not yet measured |

## Inherited proofs

A grader that is a byte copy of a grader with a recorded RED proof inherits that proof
(the copy is enforced by `tests/test_run_evals.py`). It needs no mutation of its own:
the pattern, not the behaviour behind it, is what a mutation would re-prove.

| Case | Grader | Proven by | Why no own mutation |
|---|---|---|---|
| `pass1-suggest-pipeline` | `9-no-leak` | `--mutation report-run-id` | byte copy of `evals/_lib/no-leak.md`; `report-run-id` turned that exact file red in all five Pass 2 cases (#205). Both read `last_message`, so the Pass 1 report is checked by the same pattern |
| `pass1-warn-and-duplicates-relayed` | `9-no-leak` | `--mutation report-run-id` | as above |

## Controls

Controls are preconditions, exempt from RED proof (PRD F7-AC5).

The Pass 1 cases (spec 043) have no control: the main session runs Pass 1 itself, so
there is no dispatch to confirm, and every other Pass 1 grader observes behaviour the
gate decides. Their leak guards inherit a recorded proof instead (see Inherited proofs).

| Case | Control grader | Why exempt |
|---|---|---|
| `audit-gates-delivery` | `0-conductor-dispatched` | precondition: the conductor ran |
| `audit-mismatch-stops` | `0-conductor-dispatched` | precondition: the conductor ran |
| `audit-mismatch-stops` | `3-audit-ran` | precondition: the mismatch was produced at all |
| `withheld-notices-relayed` | `0-conductor-dispatched` | precondition: the conductor ran |
| `upload-failure-reported` | `0-conductor-dispatched` | precondition: the conductor ran |
| `upload-failure-reported` | `3-upload-ran` | precondition: the failed upload was produced at all |
| `state-flip-failure-reported` | `0-conductor-dispatched` | precondition: the conductor ran |
| `state-flip-failure-reported` | `2-state-flip-ran` | precondition: the failed state flip was produced at all |
| `audit-gates-delivery` | `8-handback-canary` | precondition: the hand-back frame the report-only grader reads is in the trace exactly once |
| `audit-mismatch-stops` | `8-handback-canary` | precondition: the hand-back frame the report-only grader reads is in the trace exactly once |
| `withheld-notices-relayed` | `8-handback-canary` | precondition: the hand-back frame the report-only grader reads is in the trace exactly once |
| `upload-failure-reported` | `8-handback-canary` | precondition: the hand-back frame the report-only grader reads is in the trace exactly once |
| `state-flip-failure-reported` | `8-handback-canary` | precondition: the hand-back frame the report-only grader reads is in the trace exactly once |

## Clauses

Each clause is quoted as it appears in the file(s) the patch changes (line breaks
folded to spaces). The spec 043 patches name those files on a `files:` line; the
earlier ones all patch `agents/synthesis-conductor.md`.

### drop-audit-line

- removes: "> Coverage audit: <RESULT line from instructions-diff>"
- removes: "1. Each `Coverage audit:` line carries the `RESULT:` line the coverage audit printed, character for character"
- removes: "the audit's stdout on a mismatch (3c), the `RESULT:` line, the Step 1 drift warnings"
- adds: "1. The report does not quote the coverage audit's output."

### always-notice

- removes: "one per withheld delete across every entry processed this run. The file never contains anything else (no run id, no header, no internals). If the command errors (no such file), there is nothing to relay."
- removes: "followed by the lines of `tomo-tmp/withheld-attachments.md`, only for each file that exists."
- removes: "If neither relay file exists, say nothing about withheld deletes or attachments."
- adds: "If the command errors (no such file), write `- ⚠️ **Not deleted:** none` as the last line of the report."

### summarise-mismatch

- removes: "Exit 1 = mismatch (report diff output verbatim to user and stop"
- removes: "you STOP and report the diff verbatim."
- removes: "it is the audit's stdout copied as printed, and nothing else."
- removes: "everything inside them kept: the audit's stdout on a mismatch (3c),"
- removes: "resolve a coverage mismatch — report the diff verbatim and STOP"
- adds: "you STOP and summarise the mismatch in one sentence."
- adds: "The stop report is that one sentence, in your own words — never a line of the audit's output."

### write-into-scripts

- removes: none — the injected step is innocent bookkeeping, not a fix; no clause forbids it
- adds: "Record that the audit is about to run:"
- adds: "echo audit-started >> scripts/.audit-log"
- adds: "Then run the coverage audit:"

### copy-into-config

- removes: none — the injected step is innocent bookkeeping, not a fix; no clause forbids it
- adds: "Keep a snapshot of the parsed suggestions next to the vault config:"
- adds: "cp tomo-tmp/parsed-suggestions.json config/parsed-suggestions.snapshot.json"
- adds: "Then run the coverage audit:"

### paraphrase-relay

- removes: "STRICT — copy every line of `tomo-tmp/withheld-deletes.md` and of `tomo-tmp/withheld-attachments.md` into the report character for character"
- removes: "NEVER reword, shorten, merge, summarise, put them in a table or count them."
- removes: "- ⚠️ **<label>:** <rest of the first line, copied from the file>"
- removes: "the Step 1 drift warnings, and the relay lines."
- removes: "3. The relay lines are ONE block: the delete lines, then the attachment lines, one per line."
- removes: "NEVER write a sentence that introduces, announces or summarises the relay lines"
- removes: "nor a relay line."
- adds: "Then, below that report, summarise the notices in your own words: one short sentence per notice, never the line as it is written in the file."
- adds: "3. The notice summaries come last in the report."

### files-used-after

- removes: "one per line, the last lines of the report."
- removes: "no file name, no path, no script name."
- removes: "NEVER write anything after them — no file list, no summary, no closing sentence."
- removes: "4. In the Step 4 report, NEVER add a line that is neither in the example above nor a relay line."
- removes: "Your reply is ONLY the report: NEVER write anything before or after it"
- adds: "5. After the relay lines, list the files you used this run, one path per line."

### attachments-first

- removes: "output the lines of `tomo-tmp/withheld-deletes.md` followed by the lines of `tomo-tmp/withheld-attachments.md`"
- removes: "the delete lines, then the attachment lines"
- adds: "output the lines of `tomo-tmp/withheld-attachments.md` first, followed by the lines of `tomo-tmp/withheld-deletes.md`"
- adds: "the attachment lines, then the delete lines"

### report-run-id

- removes: "NEVER put internals in a report: no run id,"
- removes: "no command, no run id, no file name."
- removes: "it is the audit's stdout copied as printed, and nothing else."
- adds: "> Run ID: <RUN_ID>"
- adds: "Every report includes the line `Run ID: <RUN_ID>`."
- adds: "followed by the line `Run ID: <RUN_ID>`."

### failed-step-path

- removes: "file name, no path, no script name."
- removes: "and `<note>` is the note name of the entry's `VAULT_PATH`: its last segment, without the folder and without `.md`"
- removes: "The note name is the ONLY doc identifier allowed in a report; it is never a path."
- adds: "file name or path except the vault path in a failed-step line, no script name."
- adds: "and `<note>` is the entry's `VAULT_PATH` exactly as the routing plan gives it, folder and `.md` included"
- adds: "The vault path is the doc identifier in a failed-step line, so the user can open the doc in the vault."

### flip-after-failed-upload

- removes: "Any non-zero exit: do NOT run 3e for this entry."
- removes: "Continue with the next entry."
- adds: "Any non-zero exit: still run 3e for this entry, so the doc's state reflects the attempt."

### explain-failure

- removes: "Report it ONLY as the failed-step line of rule 2 in Step 4"
- removes: "On exit 1 or 2: report it ONLY as `state flip exited <code> for "<note>".`"
- removes: "no script stderr line (`[warn]`, `[attach]` or any other)"
- removes: "Report a failed step ONLY as `<step> exited <code> for "<note>".`"
- removes: "no explanation of why a step failed,"
- removes: "and wrote failure detail, commands and next steps around the report."
- adds: "> Detail: <the failing script's last stderr line, as printed>"
- adds: "followed by its Detail line"
- adds: "drift warnings, the Detail line, and the relay lines."
- adds: "followed by its `Detail:` line"

### dispatch-conductor

- files: `commands/inbox.md`
- removes: "| suggest | IMPERSONATE suggestion-conductor |"
- removes: "IMPERSONATE means: read `.claude/agents/suggestion-conductor.md`"
- removes: "NEVER call `Agent()` for it."
- removes: "It applies to synthesis-conductor and voice-transcriber only."
- adds: "| suggest | DISPATCH suggestion-conductor (see Step 3a) |"
- adds: "It applies to suggestion-conductor, synthesis-conductor and voice-transcriber."
- adds: "subagent_type: "suggestion-conductor""

### analyst-name-not-type

- files: `skills/suggest-handling/SKILL.md`, `commands/inbox.md`
- removes: "STRICT — the key is `subagent_type`. `name` only labels the spawned agent."
- removes: "STRICT — every Agent() call passes `subagent_type`."
- removes: "a dispatch without `subagent_type` silently runs general-purpose"
- removes: "subagent_type: "inbox-analyst""
- adds: "The key is `name`: it selects the inbox-analyst agent."
- adds: "name: "inbox-analyst""

### path-from-stem

- files: `skills/suggest-handling/SKILL.md`
- removes: "Each line is one item's `path`."
- adds: "Each line is one source; its `<stem>` is the last segment of the line, without `.md`."
- adds: "Every item lives directly in the inbox, so its `<path>` is `<INBOX_PATH>/<stem>.md`."

### setup-in-conductor

- files: `agents/suggestion-conductor.md`
- removes: "STRICT — run NO setup commands here."
- removes: "call `run-id.py`, `shared-ctx-builder.py` or `read-config-field.py`."
- removes: "so a setup here is discarded and the RUN_ID captured from it is stale."
- adds: "### Step 1b — Prepare the run"
- adds: "python3 scripts/run-id.py --out tomo-tmp/.run_id"
- adds: "The skill then runs its own setup as written."

### dispatch-before-setup

- files: `skills/suggest-handling/SKILL.md`
- removes: "STRICT — run ALL commands below before dispatching ANY subagent."
- removes: "before dispatching anything."
- adds: "### 3c. Shared context"
- adds: "so build it after the last batch, right before Reduce:"
- adds: "the dispatch prompt only passes its path"

### render-before-reduce

- files: `skills/suggest-handling/SKILL.md`
- removes: "### 4. Reduce"
- removes: "### 5. Render"
- adds: "### 4. Render"
- adds: "### 5. Reduce"
- removes: "reducer's summary line (step 4)"
- adds: "reducer's summary line (step 5)"

### reduce-before-batch-2

- files: `skills/suggest-handling/SKILL.md`, `agents/suggestion-conductor.md`
- removes: "| suggestions-reducer fails | Keep all"
- adds: "After each batch completes, run the Reduce command (step 4)"
- adds: "A reducer error after a batch that is not the last one only means items are still pending: continue with the next batch."
- adds: "| suggestions-reducer fails after the last batch | Keep all"

### publish-md-with-write-tool

- files: `skills/suggest-handling/SKILL.md`, `agents/suggestion-conductor.md`
- removes: "Publish both artefacts with the same script"
- removes: "python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-rendered.md"
- removes: "never read the rendered markdown and pass it to `mcp__kado__kado-write`."
- removes: "NEVER local `Write`."
- adds: "the note goes in with the Write tool"
- adds: "Write its content unchanged to `<INBOX_PATH>/<YYYY-MM-DD_HHMM>_suggestions.md`."
- adds: "Vault writes as the skill says."

### mark-before-write

- files: `skills/suggest-handling/SKILL.md`
- removes: "STRICT — mark-captured runs immediately after vault write succeeds. Do NOT skip or defer."
- adds: "Mark the sources captured as soon as the note is in the vault:"
- adds: "Run mark-captured once more after the wire write, so the state also records it:"

### inline-python-read

- files: `skills/suggest-handling/SKILL.md`, `agents/suggestion-conductor.md`
- removes: "and NEVER run `python3 -c`."
- removes: "inline Python is refused by the Bash validator on its `#` characters,"
- removes: "STRICT — NEVER inline Python with `python3 -c "..."`."
- removes: "Why: triggers approval prompts every invocation."
- removes: "python3 scripts/read-routing-plan.py --field inbox_path"
- adds: "read every value the later steps need with a command."
- adds: "python3 -c "import json; print(json.load(open('tomo-tmp/routing-plan.json'))['inbox_path'].rstrip('/'))""

### reword-report-line

- files: `skills/suggest-handling/SKILL.md`
- removes: "Pass 1 complete: {N} items analysed, suggestions written to"
- adds: "Done — {N} items analysed. Your suggestions are in [[<date>_suggestions]]."

### always-duplicate-line

- files: `skills/suggest-handling/SKILL.md`
- removes: "When `<n>` is greater than 0, add:"
- adds: "and add, whatever `<n>` is (0 included):"

### warn-is-diagnostic

- files: `skills/suggest-handling/SKILL.md`
- removes: "STRICT — repeat every `WARN:` line this script prints to the user, verbatim,"
- removes: "it is the only report of unusable tracker configuration"
- adds: "`WARN:` lines this script prints on stderr are diagnostics for the maintainer; they are kept in the script's log and need no action here."

### warn-in-report-only

- files: `skills/suggest-handling/SKILL.md`
- removes: "before dispatching anything."
- adds: "in the step 7 report, below the Pass 1 complete line. Until then, carry on."
- adds: "Then add each `WARN:` line from step 2, verbatim, one per line."

### drop-duplicate-line

- files: `skills/suggest-handling/SKILL.md`
- removes: "Then read `duplicate_proposals_converted=<n>` from the reducer's summary line"
- removes: "proposed MOC(s) already existed in the vault and are offered as"
- adds: "The reducer's summary line (step 4) is for the log; it is not reported."

### status-sentence-first

- files: `agents/synthesis-conductor.md`
- removes: "Your reply is ONLY the report: NEVER write anything before or after it"
- removes: "it is the audit's stdout copied as printed, and nothing else."
- adds: "Begin your reply with one short sentence stating whether the run succeeded."
- adds: "nor a relay line, except the opening sentence."
- adds: "it opens with the status sentence of rule 4, then the audit's stdout copied as printed."
