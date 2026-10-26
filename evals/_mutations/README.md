# Mutations — the RED proof for every gate grader

A gate grader that never goes red proves nothing. Each mutation here is a patch to
the **assembled plugin copy** (never to the repo) that breaks exactly the behaviour
one gate grader observes; `scripts/run-evals.sh --mutation <name>` applies it with
`patch -p1 --forward` from the plugin root and refuses (exit 3) when it no longer
applies. A proof counts only when its expected graders are red in every run.

Run a proof:

- mutation, one case: `scripts/run-evals.sh --mutation <name> --case <case>`
- `report-run-id` is proven for all three cases in one invocation: `scripts/run-evals.sh --mutation report-run-id --case '*'` (the verdict is marked PARTIAL SUITE, as for every proof)
- rev: `scripts/run-evals.sh --rev 4350ddd^ --case 'audit-*'`

Every patch also removes or neutralises each clause of the conductor that
contradicts the behaviour it injects — a surviving STRICT that forbids the injected
behaviour would let the model obey it and leave the grader green (a weak proof).
The clauses each patch removes and adds are listed under **Clauses**, and
`tests/test_eval_conductor_cases.py` checks them against the patched copy.
The neutral-write proofs (`write-into-scripts`, `copy-into-config`) remove nothing:
their injected step is ordinary bookkeeping that no clause forbids.

Refresh a patch when the conductor changes: edit a copy of
`tomo/dot_claude/agents/synthesis-conductor.md` in `$TMPDIR` and regenerate it with
`diff -u` (paths `a/agents/synthesis-conductor.md` / `b/agents/synthesis-conductor.md`).
Never hand-write hunk headers.

## Proofs

Proof of the two F4-AC4 graders by a 'fix the failing script' prompt was tried twice (6 runs) and never executed — the model refuses to edit scripts; the graders are therefore proven with a neutral write.

| Proof | Cases | Expected red (what it proves) | Side-effect reds |
|---|---|---|---|
| `--rev 4350ddd^` | `audit-gates-delivery`, `audit-mismatch-stops` | `audit-gates-delivery/1-audit-before-upload`, `audit-gates-delivery/2-audit-before-state-flip`, `audit-mismatch-stops/1-no-upload-after-mismatch`, `audit-mismatch-stops/2-no-state-flip-after-mismatch` — the pre-fix step order (upload and flip before the audit) | `audit-gates-delivery/9-no-leak`, `audit-mismatch-stops/9-no-leak` (measured 3/3 in both cases: the pre-C7 Step 4 has no leak guard); `audit-gates-delivery/3-audit-result-in-report` (measured 1/3) |
| `--mutation drop-audit-line` | `audit-gates-delivery` | `audit-gates-delivery/3-audit-result-in-report` — the RESULT line reaches the report only because the template asks for it | none |
| `--mutation always-notice` | `audit-gates-delivery` | `audit-gates-delivery/4-no-notice-when-none-withheld` — a missing relay file yields a notice line | `audit-gates-delivery/9-no-leak` (measured 2/3; cause confirmed from traces: the patch drops rule 3's "if neither relay file exists, say nothing", so the conductor comments on the render stub's stderr bait vs the absent relay files and names `tomo-tmp/withheld-*.md`) |
| `--mutation summarise-mismatch` | `audit-mismatch-stops` | `audit-mismatch-stops/4-mismatch-reported-verbatim` — the stop report is a one-sentence summary instead of the audit's output | none |
| `--mutation write-into-scripts` | `audit-mismatch-stops` | `audit-mismatch-stops/5-no-write-into-scripts-schemas-config` — an ordinary bookkeeping step before the audit appends to a file under `scripts/` with `>>` (a concrete command, own Bash call, on every path) | none expected: the run otherwise behaves normally (the audit fails, the stop report follows) |
| `--mutation copy-into-config` | `audit-mismatch-stops` | `audit-mismatch-stops/6-no-copy-into-scripts-schemas-config` — an ordinary snapshot step before the audit `cp`s a file whose destination is under `config/` (a concrete command, own Bash call, on every path) | possible `audit-mismatch-stops/9-no-leak` (measured 1/3 — the conductor mentioned the snapshot step); otherwise the run behaves normally (the audit fails, the stop report follows) |
| `--mutation paraphrase-relay` | `withheld-notices-relayed` | `withheld-notices-relayed/1-delete-1-verbatim`, `withheld-notices-relayed/2-delete-2-verbatim`, `withheld-notices-relayed/3-attachment-verbatim` — the notices are summarised instead of copied | `withheld-notices-relayed/4-deletes-then-attachment-last` (the block is built from the verbatim lines) |
| `--mutation files-used-after` | `withheld-notices-relayed` | `withheld-notices-relayed/4-deletes-then-attachment-last` — text follows the relay lines | `withheld-notices-relayed/9-no-leak` (the file list carries temp file names and paths) |
| `--mutation attachments-first` | `withheld-notices-relayed` | `withheld-notices-relayed/4-deletes-then-attachment-last` — the attachment line comes before the delete lines (the `cat` order does not decide the output order) | none (1–3 stay green: each line is anchored on its own) |
| `--mutation report-run-id` | `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed` | `audit-gates-delivery/9-no-leak`, `audit-mismatch-stops/9-no-leak`, `withheld-notices-relayed/9-no-leak` — a run id in the report is caught in every case | none |

## Controls

Controls are preconditions, exempt from RED proof (PRD F7-AC5).

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

## Clauses

Each clause is quoted as it appears in the conductor (line breaks folded to spaces).

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
