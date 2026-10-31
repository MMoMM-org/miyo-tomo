# RED proofs — Pass 1 conductor eval gate, Blocks A to D and S, merge evidence (T4.1, T4.3, PRD F7)

Measured 2026-10-31, Claude Code 2.1.316, against the runtime files at these versions: `suggest-handling` 0.14.1, `force-atomic-handling` 0.15.0, `synthesis-conductor` 0.24.2 (`# version:` lines in `tomo/dot_claude`). Each proof is one invocation of

```
scripts/run-evals.sh --keep-temp --mutation <name> --case <case>
```

with 3 runs and a clean tree. A proof counts only if every expected grader is red in **every** run. Patches and the clauses each removes: `evals/_mutations/README.md`. Raw log: `tomo-tmp/evals/red-proofs-043.log` (gitignored); each verdict below was copied from it and matches the `verdict.txt` in its results directory. `PARTIAL SUITE` is printed because `--case` is given.

Block A: 15 invocations, 11 proven, 4 not proven, total cost $10.10.
Re-proofs (Block D, strengthened patches, commit fcb8c7e4): 4 invocations, 4 proven, $2.99.
Block B (`status-sentence-first`, five Pass 2 cases): 3 invocations, proven, $1.03.
Block C (spec 041 patches rebased onto `synthesis-conductor` 0.24.2): 7 invocations, 5 patches re-proven, $2.00.
**T4.1 total: 29 invocations, $16.12. T4.1 complete: every non-control grader red 3/3.**

Blocks B to D were run with `--keep-temp` after Block A, from commit fcb8c7e4. Every verdict line below was copied from the log and compared byte for byte with the `verdict.txt` in its results directory: all 14 match. Per-grader counts come from the `FAIL (...)` lines in the log; their number equals the number of `(run N)` entries in each verdict line, and they agree entry by entry, so the verdict line is the evidence for every count.

## Summary

| Proof | Class | Expected grader(s) | Result |
|---|---|---|---|
| `dispatch-conductor` | PROVEN | `01-conductor-not-dispatched` | 3/3 |
| `dispatch-before-setup` | PROVEN | `07-setup-before-dispatch` | 3/3 |
| `reduce-before-batch-2` | PROVEN | `09-reduce-after-last-dispatch` | 3/3 |
| `publish-md-with-write-tool` | PROVEN | `10-two-script-writes-same-stem`, `11-no-inline-vault-write` | 3/3, 3/3 |
| `mark-before-write` | PROVEN | `12a-mark-captured-once`, `12b-mark-captured-after-json-write` | 3/3, 3/3 |
| `inline-python-read` | PROVEN | `13-no-inline-python` | 3/3 |
| `always-duplicate-line` | PROVEN | `15-no-duplicate-line` | 3/3 |
| `reword-report-line` | PROVEN | `pass1-suggest-pipeline/14-report-line-anchored`, `pass1-warn-and-duplicates-relayed/04-report-line-anchored` | 3/3, 3/3 |
| `warn-is-diagnostic` | PROVEN | `01-warn-in-reply` | 3/3 |
| `warn-in-report-only` | PROVEN | `02-warn-before-first-dispatch` | 3/3 |
| `drop-duplicate-line` | PROVEN | `03-duplicate-line` | 3/3 |
| `analyst-name-not-type` | NOT PROVEN (first attempt) | see below | GREEN; re-proven in Re-proofs |
| `path-from-stem` | NOT PROVEN (first attempt) | see below | GREEN; re-proven in Re-proofs |
| `render-before-reduce` | NOT PROVEN (first attempt) | see below | GREEN; re-proven in Re-proofs |
| `setup-in-conductor` | NOT PROVEN (first attempt) | see below | red 3/3 + 1/3; re-proven in Re-proofs |

## Proven

### `dispatch-conductor` — $0.64

- Case: `pass1-suggest-pipeline`
- Expected red: `01-conductor-not-dispatched` 3/3
- Side-effect reds: `07-setup-before-dispatch` 3/3 (structural: setup runs inside the dispatched subagent, so it is never in the main session before a dispatch), `14-report-line-anchored` 1/3.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 01-conductor-not-dispatched (run 0), pass1-suggest-pipeline: 07-setup-before-dispatch (run 0), pass1-suggest-pipeline: 01-conductor-not-dispatched (run 1), pass1-suggest-pipeline: 07-setup-before-dispatch (run 1), pass1-suggest-pipeline: 01-conductor-not-dispatched (run 2), pass1-suggest-pipeline: 07-setup-before-dispatch (run 2), pass1-suggest-pipeline: 14-report-line-anchored (run 2) · runs 3 · $0.64 · 97 s · claude 2.1.316 · tree clean · mutation dispatch-conductor · tomo-tmp/evals/2026-10-31T12-37-49Z
```

### `dispatch-before-setup` — $0.61

- Case: `pass1-suggest-pipeline`
- Expected red: `07-setup-before-dispatch` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 07-setup-before-dispatch (run 0), pass1-suggest-pipeline: 07-setup-before-dispatch (run 1), pass1-suggest-pipeline: 07-setup-before-dispatch (run 2) · runs 3 · $0.61 · 80 s · claude 2.1.316 · tree clean · mutation dispatch-before-setup · tomo-tmp/evals/2026-10-31T12-44-07Z
```

### `reduce-before-batch-2` — $0.62

- Case: `pass1-suggest-pipeline`
- Expected red: `09-reduce-after-last-dispatch` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 09-reduce-after-last-dispatch (run 0), pass1-suggest-pipeline: 09-reduce-after-last-dispatch (run 1), pass1-suggest-pipeline: 09-reduce-after-last-dispatch (run 2) · runs 3 · $0.62 · 86 s · claude 2.1.316 · tree clean · mutation reduce-before-batch-2 · tomo-tmp/evals/2026-10-31T12-46-54Z
```

### `publish-md-with-write-tool` — $0.69

- Case: `pass1-suggest-pipeline`
- Expected red: `10-two-script-writes-same-stem` 3/3, `11-no-inline-vault-write` 3/3
- Side-effect reds: `12a-mark-captured-once`, `14-report-line-anchored`, `9-no-leak`, each 3/3. Cascade: the Write tool is unavailable in the eval session ("No such tool available: Write. Write is disabled for this session") even though `case.yaml` lists it, so the note is never published and the later steps drift. 10 and 11 count the attempted call, so they are red for the intended reason.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 10-two-script-writes-same-stem (run 0), pass1-suggest-pipeline: 11-no-inline-vault-write (run 0), pass1-suggest-pipeline: 12a-mark-captured-once (run 0), pass1-suggest-pipeline: 14-report-line-anchored (run 0), pass1-suggest-pipeline: 9-no-leak (run 0), pass1-suggest-pipeline: 10-two-script-writes-same-stem (run 1), pass1-suggest-pipeline: 11-no-inline-vault-write (run 1), pass1-suggest-pipeline: 12a-mark-captured-once (run 1), pass1-suggest-pipeline: 14-report-line-anchored (run 1), pass1-suggest-pipeline: 9-no-leak (run 1), pass1-suggest-pipeline: 10-two-script-writes-same-stem (run 2), pass1-suggest-pipeline: 11-no-inline-vault-write (run 2), pass1-suggest-pipeline: 12a-mark-captured-once (run 2), pass1-suggest-pipeline: 14-report-line-anchored (run 2), pass1-suggest-pipeline: 9-no-leak (run 2) · runs 3 · $0.69 · 102 s · claude 2.1.316 · tree clean · mutation publish-md-with-write-tool · tomo-tmp/evals/2026-10-31T12-48-22Z
```

### `mark-before-write` — $0.68

- Case: `pass1-suggest-pipeline`
- Expected red: `12a-mark-captured-once` 3/3, `12b-mark-captured-after-json-write` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 12a-mark-captured-once (run 0), pass1-suggest-pipeline: 12b-mark-captured-after-json-write (run 0), pass1-suggest-pipeline: 12a-mark-captured-once (run 1), pass1-suggest-pipeline: 12b-mark-captured-after-json-write (run 1), pass1-suggest-pipeline: 12a-mark-captured-once (run 2), pass1-suggest-pipeline: 12b-mark-captured-after-json-write (run 2) · runs 3 · $0.68 · 106 s · claude 2.1.316 · tree clean · mutation mark-before-write · tomo-tmp/evals/2026-10-31T12-50-06Z
```

### `inline-python-read` — $0.64

- Case: `pass1-suggest-pipeline`
- Expected red: `13-no-inline-python` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 13-no-inline-python (run 0), pass1-suggest-pipeline: 13-no-inline-python (run 1), pass1-suggest-pipeline: 13-no-inline-python (run 2) · runs 3 · $0.64 · 77 s · claude 2.1.316 · tree clean · mutation inline-python-read · tomo-tmp/evals/2026-10-31T12-51-53Z
```

### `always-duplicate-line` — $0.63

- Case: `pass1-suggest-pipeline`
- Expected red: `15-no-duplicate-line` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 15-no-duplicate-line (run 0), pass1-suggest-pipeline: 15-no-duplicate-line (run 1), pass1-suggest-pipeline: 15-no-duplicate-line (run 2) · runs 3 · $0.63 · 77 s · claude 2.1.316 · tree clean · mutation always-duplicate-line · tomo-tmp/evals/2026-10-31T12-53-12Z
```

### `reword-report-line` — $1.25

- Case: `pass1-suggest-pipeline`, `pass1-warn-and-duplicates-relayed`
- Expected red: `pass1-suggest-pipeline/14-report-line-anchored` 3/3, `pass1-warn-and-duplicates-relayed/04-report-line-anchored` 3/3
- Side-effect red: `pass1-warn-and-duplicates-relayed/02-warn-before-first-dispatch` 1/3 (run 2). It is a grader defect on batched calls, being fixed (F6), not an effect of the patch.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · pass1-suggest-pipeline: 14-report-line-anchored (run 0), pass1-suggest-pipeline: 14-report-line-anchored (run 1), pass1-suggest-pipeline: 14-report-line-anchored (run 2), pass1-warn-and-duplicates-relayed: 04-report-line-anchored (run 0), pass1-warn-and-duplicates-relayed: 04-report-line-anchored (run 1), pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 2), pass1-warn-and-duplicates-relayed: 04-report-line-anchored (run 2) · runs 6 · $1.25 · 138 s · claude 2.1.316 · tree clean · mutation reword-report-line · tomo-tmp/evals/2026-10-31T12-54-30Z
```

### `warn-is-diagnostic` — $0.63

- Case: `pass1-warn-and-duplicates-relayed`
- Expected red: `01-warn-in-reply` 3/3
- Side-effect red: `02-warn-before-first-dispatch` 3/3. Expected: the patch removes the `cat tomo-tmp/setup-warnings.txt` that grader 02 looks for.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-warn-and-duplicates-relayed: 01-warn-in-reply (run 0), pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 0), pass1-warn-and-duplicates-relayed: 01-warn-in-reply (run 1), pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 1), pass1-warn-and-duplicates-relayed: 01-warn-in-reply (run 2), pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 2) · runs 3 · $0.63 · 106 s · claude 2.1.316 · tree clean · mutation warn-is-diagnostic · tomo-tmp/evals/2026-10-31T12-56-50Z
```

### `warn-in-report-only` — $0.60

- Case: `pass1-warn-and-duplicates-relayed`
- Expected red: `02-warn-before-first-dispatch` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 0), pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 1), pass1-warn-and-duplicates-relayed: 02-warn-before-first-dispatch (run 2) · runs 3 · $0.60 · 79 s · claude 2.1.316 · tree clean · mutation warn-in-report-only · tomo-tmp/evals/2026-10-31T12-58-37Z
```

### `drop-duplicate-line` — $0.61

- Case: `pass1-warn-and-duplicates-relayed`
- Expected red: `03-duplicate-line` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-warn-and-duplicates-relayed: 03-duplicate-line (run 0), pass1-warn-and-duplicates-relayed: 03-duplicate-line (run 1), pass1-warn-and-duplicates-relayed: 03-duplicate-line (run 2) · runs 3 · $0.61 · 82 s · claude 2.1.316 · tree clean · mutation drop-duplicate-line · tomo-tmp/evals/2026-10-31T12-59-58Z
```

## Not proven (Block A first attempts, kept as history)

Owner decision 2026-10-31: these four were re-run after the patch or the case was strengthened. The first attempts are not counted; the re-proofs below are.

### `analyst-name-not-type` — $0.61

- Case: `pass1-suggest-pipeline`
- Diagnosed cause: GREEN. The model kept `subagent_type` from the Agent tool's own description, whatever the patched dispatch template said.

```
GREEN (PARTIAL SUITE — does not satisfy the merge rule) 1/1 cases · runs 3 · $0.61 · 92 s · claude 2.1.316 · tree clean · mutation analyst-name-not-type · tomo-tmp/evals/2026-10-31T12-39-27Z
```

### `path-from-stem` — $0.64

- Case: `pass1-suggest-pipeline`
- Diagnosed cause: GREEN. The `--sources` output contradicted the patch's premise (each line is already the real path), and the model passed the real path.

```
GREEN (PARTIAL SUITE — does not satisfy the merge rule) 1/1 cases · runs 3 · $0.64 · 98 s · claude 2.1.316 · tree clean · mutation path-from-stem · tomo-tmp/evals/2026-10-31T12-41-01Z
```

### `render-before-reduce` — $0.60

- Case: `pass1-suggest-pipeline`
- Diagnosed cause: GREEN. The model reordered the steps because render's `--input` is the reducer's `--output`.

```
GREEN (PARTIAL SUITE — does not satisfy the merge rule) 1/1 cases · runs 3 · $0.60 · 84 s · claude 2.1.316 · tree clean · mutation render-before-reduce · tomo-tmp/evals/2026-10-31T12-45-28Z
```

### `setup-in-conductor` — $0.65

- Case: `pass1-suggest-pipeline`
- Diagnosed cause: `06-run-id-once` red 3/3, `05-shared-ctx-once` red 1/3 (run 1). The patched shared-ctx command lacked `--warnings-out`, and the skill's own setup superseded the injected step 1b.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 06-run-id-once (run 0), pass1-suggest-pipeline: 05-shared-ctx-once (run 1), pass1-suggest-pipeline: 06-run-id-once (run 1), pass1-suggest-pipeline: 06-run-id-once (run 2) · runs 3 · $0.65 · 85 s · claude 2.1.316 · tree clean · mutation setup-in-conductor · tomo-tmp/evals/2026-10-31T12-42-40Z
```

## Side-effect reds

Measured counts, from the verdict lines above:

- `dispatch-conductor` → `07-setup-before-dispatch` 3/3 (structural: setup runs inside the dispatched subagent), `14-report-line-anchored` 1/3.
- `publish-md-with-write-tool` → `12a-mark-captured-once`, `14-report-line-anchored`, `9-no-leak` 3/3 each. Cascade: the Write tool is unavailable in the eval session ("No such tool available: Write. Write is disabled for this session") even though `case.yaml` lists it. `10` and `11` count the attempted call.
- `reword-report-line` → `pass1-warn-and-duplicates-relayed/02-warn-before-first-dispatch` 1/3 (run 2). **Void:** a grader defect on batched calls, not an effect of the patch; fixed in c2602d6b (F6, grader 02 binds the WARN result to the `cat` call by tool id). Not counted as a side-effect red.
- `warn-is-diagnostic` → `02-warn-before-first-dispatch` 3/3 (the patch removes the `cat` that grader looks for).
- `setup-in-conductor` (first attempt, not proven): `05-shared-ctx-once` 1/3 only. Superseded: see the re-proof.

## Re-proofs (strengthened patches, commit fcb8c7e4)

The four Block A patches that were not proven, re-run after fcb8c7e4 (`test(evals): strengthen four spec 043 mutation patches with neutral steps`). Each: `scripts/run-evals.sh --keep-temp --mutation <name> --case pass1-suggest-pipeline`, 3 runs, clean tree. Block D: $2.99.

| Proof | Expected grader(s) | Red counts | Result |
|---|---|---|---|
| `analyst-name-not-type` | `02-analyst-dispatched-3x`, `03-no-general-purpose` | 3/3, 3/3 | PROVEN |
| `path-from-stem` | `04-subfolder-path-and-key` | 3/3 | PROVEN |
| `render-before-reduce` | `08-reducer-before-render` | 3/3 | PROVEN |
| `setup-in-conductor` | `05-shared-ctx-once`, `06-run-id-once` | 3/3, 3/3 | PROVEN |

### `analyst-name-not-type` — $1.12

- Case: `pass1-suggest-pipeline`
- Expected red: `02-analyst-dispatched-3x` 3/3, `03-no-general-purpose` 3/3
- Side-effect reds (all in run 1 only): `10-two-script-writes-same-stem` 1/3, `12a-mark-captured-once` 1/3, `14-report-line-anchored` 1/3, `9-no-leak` 1/3. Run 1 drifted after the analysts were typed `general-purpose`; the same four graders went red together in Block A's `publish-md-with-write-tool` cascade.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 02-analyst-dispatched-3x (run 0), pass1-suggest-pipeline: 03-no-general-purpose (run 0), pass1-suggest-pipeline: 02-analyst-dispatched-3x (run 1), pass1-suggest-pipeline: 03-no-general-purpose (run 1), pass1-suggest-pipeline: 10-two-script-writes-same-stem (run 1), pass1-suggest-pipeline: 12a-mark-captured-once (run 1), pass1-suggest-pipeline: 14-report-line-anchored (run 1), pass1-suggest-pipeline: 9-no-leak (run 1), pass1-suggest-pipeline: 02-analyst-dispatched-3x (run 2), pass1-suggest-pipeline: 03-no-general-purpose (run 2) · runs 3 · $1.12 · 140 s · claude 2.1.316 · tree clean · mutation analyst-name-not-type · tomo-tmp/evals/2026-10-31T13-39-49Z
```

### `path-from-stem` — $0.61

- Case: `pass1-suggest-pipeline`
- Expected red: `04-subfolder-path-and-key` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 04-subfolder-path-and-key (run 0), pass1-suggest-pipeline: 04-subfolder-path-and-key (run 1), pass1-suggest-pipeline: 04-subfolder-path-and-key (run 2) · runs 3 · $0.61 · 115 s · claude 2.1.316 · tree clean · mutation path-from-stem · tomo-tmp/evals/2026-10-31T13-42-11Z
```

### `render-before-reduce` — $0.64

- Case: `pass1-suggest-pipeline`
- Expected red: `08-reducer-before-render` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 08-reducer-before-render (run 0), pass1-suggest-pipeline: 08-reducer-before-render (run 1), pass1-suggest-pipeline: 08-reducer-before-render (run 2) · runs 3 · $0.64 · 100 s · claude 2.1.316 · tree clean · mutation render-before-reduce · tomo-tmp/evals/2026-10-31T13-44-07Z
```

### `setup-in-conductor` — $0.62

- Case: `pass1-suggest-pipeline`
- Expected red: `05-shared-ctx-once` 3/3, `06-run-id-once` 3/3
- No side-effect reds.

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · pass1-suggest-pipeline: 05-shared-ctx-once (run 0), pass1-suggest-pipeline: 06-run-id-once (run 0), pass1-suggest-pipeline: 05-shared-ctx-once (run 1), pass1-suggest-pipeline: 06-run-id-once (run 1), pass1-suggest-pipeline: 05-shared-ctx-once (run 2), pass1-suggest-pipeline: 06-run-id-once (run 2) · runs 3 · $0.62 · 112 s · claude 2.1.316 · tree clean · mutation setup-in-conductor · tomo-tmp/evals/2026-10-31T13-45-49Z
```

## Block B — `status-sentence-first` ($1.03)

Expected graders (`evals/_mutations/README.md`, spec 043 section): `audit-gates-delivery/7-report-only`, `audit-mismatch-stops/7-report-only-mismatch`, `withheld-notices-relayed/7-report-only`, `upload-failure-reported/7-report-only`, `state-flip-failure-reported/7-report-only`. The canary `8-handback-canary` must stay green: it was not red in any of the five cases. Three invocations cover the five cases. **PROVEN**: every expected grader red 3/3. No side-effect reds.

| Case | Expected grader | Red |
|---|---|---|
| `audit-gates-delivery` | `7-report-only` | 3/3 |
| `audit-mismatch-stops` | `7-report-only-mismatch` | 3/3 |
| `withheld-notices-relayed` | `7-report-only` | 3/3 |
| `upload-failure-reported` | `7-report-only` | 3/3 |
| `state-flip-failure-reported` | `7-report-only` | 3/3 |

`--case audit-*` — $0.44

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · audit-gates-delivery: 7-report-only (run 0), audit-gates-delivery: 7-report-only (run 1), audit-gates-delivery: 7-report-only (run 2), audit-mismatch-stops: 7-report-only-mismatch (run 0), audit-mismatch-stops: 7-report-only-mismatch (run 1), audit-mismatch-stops: 7-report-only-mismatch (run 2) · runs 6 · $0.44 · 78 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T13-47-43Z
```

`--case *-failure-reported` — $0.39

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · state-flip-failure-reported: 7-report-only (run 0), state-flip-failure-reported: 7-report-only (run 1), state-flip-failure-reported: 7-report-only (run 2), upload-failure-reported: 7-report-only (run 0), upload-failure-reported: 7-report-only (run 1), upload-failure-reported: 7-report-only (run 2) · runs 6 · $0.39 · 67 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T13-49-02Z
```

`--case withheld-notices-relayed` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 7-report-only (run 2) · runs 3 · $0.20 · 46 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T13-50-11Z
```

## Block C — spec 041 patches on `synthesis-conductor` 0.24.2 ($2.00)

Expected graders are the rows of the recorded `## Proofs` table in `evals/_mutations/README.md`. All five patches are re-proven: every expected grader red 3/3 in every case.

| Proof | Expected grader(s) | Red counts | Result | Side-effect reds (measured) |
|---|---|---|---|---|
| `summarise-mismatch` | `audit-mismatch-stops/4-mismatch-reported-verbatim` | 3/3 | PROVEN | `audit-mismatch-stops/7-report-only-mismatch` 3/3 |
| `files-used-after` | `withheld-notices-relayed/4-deletes-then-attachment-last` | 3/3 | PROVEN | `9-no-leak` 3/3 (recorded in the table), `7-report-only` 3/3 |
| `paraphrase-relay` | `withheld-notices-relayed/1-delete-1-verbatim`, `2-delete-2-verbatim`, `3-attachment-verbatim` | 3/3, 3/3, 3/3 | PROVEN | `4-deletes-then-attachment-last` 3/3 (recorded in the table), `7-report-only` 3/3 |
| `explain-failure` | `upload-failure-reported/5-no-failure-detail-in-report`, `state-flip-failure-reported/4-no-failure-detail-in-report` | 3/3, 3/3 | PROVEN | `upload-failure-reported/7-report-only` 3/3, `state-flip-failure-reported/7-report-only` 3/3 |
| `report-run-id` | `9-no-leak` in `audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` | 3/3 in each of the five cases | PROVEN | `7-report-only` (`7-report-only-mismatch` in `audit-mismatch-stops`) 3/3 in each of the five cases; `audit-mismatch-stops/8-handback-canary` 1/3 (run 0); `upload-failure-reported/5-no-failure-detail-in-report` 1/3 (run 2) |

The recorded table lists no side-effect reds for `summarise-mismatch`, `explain-failure` and `report-run-id`. The `7-report-only` reds are new with the spec 043 grader `7-report-only`: each of these patches puts text into the report that the grader forbids, so they are expected, not defects. The 1/3 canary and `5-no-failure-detail` reds under `report-run-id` are run-specific drift (a run id in the report pulled further text in).

### `summarise-mismatch` — $0.19

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-mismatch-stops: 4-mismatch-reported-verbatim (run 0), audit-mismatch-stops: 7-report-only-mismatch (run 0), audit-mismatch-stops: 4-mismatch-reported-verbatim (run 1), audit-mismatch-stops: 7-report-only-mismatch (run 1), audit-mismatch-stops: 4-mismatch-reported-verbatim (run 2), audit-mismatch-stops: 7-report-only-mismatch (run 2) · runs 3 · $0.19 · 41 s · claude 2.1.316 · tree clean · mutation summarise-mismatch · tomo-tmp/evals/2026-10-31T13-50-58Z
```

### `files-used-after` — $0.22

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 4-deletes-then-attachment-last (run 0), withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 9-no-leak (run 0), withheld-notices-relayed: 4-deletes-then-attachment-last (run 1), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 9-no-leak (run 1), withheld-notices-relayed: 4-deletes-then-attachment-last (run 2), withheld-notices-relayed: 7-report-only (run 2), withheld-notices-relayed: 9-no-leak (run 2) · runs 3 · $0.22 · 54 s · claude 2.1.316 · tree clean · mutation files-used-after · tomo-tmp/evals/2026-10-31T13-51-40Z
```

### `paraphrase-relay` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 1-delete-1-verbatim (run 0), withheld-notices-relayed: 2-delete-2-verbatim (run 0), withheld-notices-relayed: 3-attachment-verbatim (run 0), withheld-notices-relayed: 4-deletes-then-attachment-last (run 0), withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 1-delete-1-verbatim (run 1), withheld-notices-relayed: 2-delete-2-verbatim (run 1), withheld-notices-relayed: 3-attachment-verbatim (run 1), withheld-notices-relayed: 4-deletes-then-attachment-last (run 1), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 1-delete-1-verbatim (run 2), withheld-notices-relayed: 2-delete-2-verbatim (run 2), withheld-notices-relayed: 3-attachment-verbatim (run 2), withheld-notices-relayed: 4-deletes-then-attachment-last (run 2), withheld-notices-relayed: 7-report-only (run 2) · runs 3 · $0.20 · 48 s · claude 2.1.316 · tree clean · mutation paraphrase-relay · tomo-tmp/evals/2026-10-31T13-52-36Z
```

### `explain-failure` — $0.40

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · state-flip-failure-reported: 4-no-failure-detail-in-report (run 0), state-flip-failure-reported: 7-report-only (run 0), state-flip-failure-reported: 4-no-failure-detail-in-report (run 1), state-flip-failure-reported: 7-report-only (run 1), state-flip-failure-reported: 4-no-failure-detail-in-report (run 2), state-flip-failure-reported: 7-report-only (run 2), upload-failure-reported: 5-no-failure-detail-in-report (run 0), upload-failure-reported: 7-report-only (run 0), upload-failure-reported: 5-no-failure-detail-in-report (run 1), upload-failure-reported: 7-report-only (run 1), upload-failure-reported: 5-no-failure-detail-in-report (run 2), upload-failure-reported: 7-report-only (run 2) · runs 6 · $0.40 · 73 s · claude 2.1.316 · tree clean · mutation explain-failure · tomo-tmp/evals/2026-10-31T13-53-25Z
```

### `report-run-id` — $0.39 + $0.39 + $0.21 = $0.99

`--case audit-*` — $0.39

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · audit-gates-delivery: 7-report-only (run 0), audit-gates-delivery: 9-no-leak (run 0), audit-gates-delivery: 7-report-only (run 1), audit-gates-delivery: 9-no-leak (run 1), audit-gates-delivery: 7-report-only (run 2), audit-gates-delivery: 9-no-leak (run 2), audit-mismatch-stops: 7-report-only-mismatch (run 0), audit-mismatch-stops: 8-handback-canary (run 0), audit-mismatch-stops: 9-no-leak (run 0), audit-mismatch-stops: 7-report-only-mismatch (run 1), audit-mismatch-stops: 9-no-leak (run 1), audit-mismatch-stops: 7-report-only-mismatch (run 2), audit-mismatch-stops: 9-no-leak (run 2) · runs 6 · $0.39 · 68 s · claude 2.1.316 · tree clean · mutation report-run-id · tomo-tmp/evals/2026-10-31T13-54-39Z
```

`--case *-failure-reported` — $0.39

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · state-flip-failure-reported: 7-report-only (run 0), state-flip-failure-reported: 9-no-leak (run 0), state-flip-failure-reported: 7-report-only (run 1), state-flip-failure-reported: 9-no-leak (run 1), state-flip-failure-reported: 7-report-only (run 2), state-flip-failure-reported: 9-no-leak (run 2), upload-failure-reported: 7-report-only (run 0), upload-failure-reported: 9-no-leak (run 0), upload-failure-reported: 7-report-only (run 1), upload-failure-reported: 9-no-leak (run 1), upload-failure-reported: 5-no-failure-detail-in-report (run 2), upload-failure-reported: 7-report-only (run 2), upload-failure-reported: 9-no-leak (run 2) · runs 6 · $0.39 · 73 s · claude 2.1.316 · tree clean · mutation report-run-id · tomo-tmp/evals/2026-10-31T13-55-48Z
```

`--case withheld-notices-relayed` — $0.21

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 9-no-leak (run 0), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 9-no-leak (run 1), withheld-notices-relayed: 7-report-only (run 2), withheld-notices-relayed: 9-no-leak (run 2) · runs 3 · $0.21 · 51 s · claude 2.1.316 · tree clean · mutation report-run-id · tomo-tmp/evals/2026-10-31T13-57-03Z
```

## Totals

| Block | Invocations | Cost |
|---|---|---|
| A | 15 | $10.10 |
| D (re-proofs) | 4 | $2.99 |
| B | 3 | $1.03 |
| C | 7 | $2.00 |
| **T4.1** | **29** | **$16.12** |

T4.1 complete: every non-control grader red 3/3. Every expected grader of the 15 spec 043 proofs (Block A's 11 plus the 4 re-proofs), of `status-sentence-first` (five cases), and of the 5 re-proven spec 041 patches was red in every run of every listed case. The controls are exempt (PRD F7-AC5).

## Block S — re-proofs on the sonnet conductor (`synthesis-conductor` 0.25.0)

After the first merge evidence went RED (see T4.3 below), the owner moved the conductor from haiku to sonnet (0.25.0, commit d1cb8903). Every conductor proof measured on haiku was repeated on sonnet: `status-sentence-first` in the five Pass 2 cases and the five spec 041 patches. Each verdict below matches the `verdict.txt` in its results directory byte for byte.

### First run, from commit d1cb8903 ($4.67)

All five spec 041 patches: every expected grader red 3/3 in every case, as on haiku. `status-sentence-first` was red 3/3 in four cases but only 2/3 in `withheld-notices-relayed`: in run 2 sonnet ignored the vague instruction to "begin your reply with one short sentence stating whether the run succeeded" and handed back a clean report, so the grader was right to stay green. The patch was made a neutral literal line (`Status: run finished.`, commit 99a6f50c) and re-proven below.

`--mutation status-sentence-first --case audit-*`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · audit-gates-delivery: 7-report-only (run 0), audit-gates-delivery: 7-report-only (run 1), audit-gates-delivery: 7-report-only (run 2), audit-mismatch-stops: 7-report-only-mismatch (run 0), audit-mismatch-stops: 7-report-only-mismatch (run 1), audit-mismatch-stops: 7-report-only-mismatch (run 2) · runs 6 · $0.61 · 87 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T15-27-48Z
```

`--mutation status-sentence-first --case *-failure-reported`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · state-flip-failure-reported: 1-state-flip-failure-line-in-report (run 0), state-flip-failure-reported: 7-report-only (run 0), state-flip-failure-reported: 7-report-only (run 1), state-flip-failure-reported: 7-report-only (run 2), upload-failure-reported: 7-report-only (run 0), upload-failure-reported: 1-upload-failure-line-in-report (run 1), upload-failure-reported: 7-report-only (run 1), upload-failure-reported: 7-report-only (run 2) · runs 6 · $0.59 · 71 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T15-29-17Z
```

`--mutation status-sentence-first --case withheld-notices-relayed`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 7-report-only (run 1) · runs 3 · $0.32 · 61 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T15-30-30Z
```

`--mutation summarise-mismatch --case audit-mismatch-stops`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-mismatch-stops: 4-mismatch-reported-verbatim (run 0), audit-mismatch-stops: 7-report-only-mismatch (run 0), audit-mismatch-stops: 4-mismatch-reported-verbatim (run 1), audit-mismatch-stops: 7-report-only-mismatch (run 1), audit-mismatch-stops: 4-mismatch-reported-verbatim (run 2), audit-mismatch-stops: 7-report-only-mismatch (run 2) · runs 3 · $0.29 · 31 s · claude 2.1.316 · tree clean · mutation summarise-mismatch · tomo-tmp/evals/2026-10-31T15-31-32Z
```

`--mutation files-used-after --case withheld-notices-relayed`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 4-deletes-then-attachment-last (run 0), withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 9-no-leak (run 0), withheld-notices-relayed: 4-deletes-then-attachment-last (run 1), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 9-no-leak (run 1), withheld-notices-relayed: 4-deletes-then-attachment-last (run 2), withheld-notices-relayed: 7-report-only (run 2), withheld-notices-relayed: 8-handback-canary (run 2), withheld-notices-relayed: 9-no-leak (run 2) · runs 3 · $0.38 · 77 s · claude 2.1.316 · tree clean · mutation files-used-after · tomo-tmp/evals/2026-10-31T15-32-05Z
```

`--mutation paraphrase-relay --case withheld-notices-relayed`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 1-delete-1-verbatim (run 0), withheld-notices-relayed: 2-delete-2-verbatim (run 0), withheld-notices-relayed: 3-attachment-verbatim (run 0), withheld-notices-relayed: 4-deletes-then-attachment-last (run 0), withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 1-delete-1-verbatim (run 1), withheld-notices-relayed: 2-delete-2-verbatim (run 1), withheld-notices-relayed: 3-attachment-verbatim (run 1), withheld-notices-relayed: 4-deletes-then-attachment-last (run 1), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 1-delete-1-verbatim (run 2), withheld-notices-relayed: 2-delete-2-verbatim (run 2), withheld-notices-relayed: 3-attachment-verbatim (run 2), withheld-notices-relayed: 4-deletes-then-attachment-last (run 2), withheld-notices-relayed: 7-report-only (run 2) · runs 3 · $0.34 · 73 s · claude 2.1.316 · tree clean · mutation paraphrase-relay · tomo-tmp/evals/2026-10-31T15-33-23Z
```

`--mutation explain-failure --case *-failure-reported`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · state-flip-failure-reported: 4-no-failure-detail-in-report (run 0), state-flip-failure-reported: 7-report-only (run 0), state-flip-failure-reported: 4-no-failure-detail-in-report (run 1), state-flip-failure-reported: 7-report-only (run 1), state-flip-failure-reported: 4-no-failure-detail-in-report (run 2), state-flip-failure-reported: 7-report-only (run 2), upload-failure-reported: 5-no-failure-detail-in-report (run 0), upload-failure-reported: 7-report-only (run 0), upload-failure-reported: 5-no-failure-detail-in-report (run 1), upload-failure-reported: 7-report-only (run 1), upload-failure-reported: 5-no-failure-detail-in-report (run 2), upload-failure-reported: 7-report-only (run 2) · runs 6 · $0.63 · 109 s · claude 2.1.316 · tree clean · mutation explain-failure · tomo-tmp/evals/2026-10-31T15-34-38Z
```

`--mutation report-run-id --case audit-*`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · audit-gates-delivery: 7-report-only (run 0), audit-gates-delivery: 9-no-leak (run 0), audit-gates-delivery: 7-report-only (run 1), audit-gates-delivery: 9-no-leak (run 1), audit-gates-delivery: 7-report-only (run 2), audit-gates-delivery: 9-no-leak (run 2), audit-mismatch-stops: 7-report-only-mismatch (run 0), audit-mismatch-stops: 9-no-leak (run 0), audit-mismatch-stops: 7-report-only-mismatch (run 1), audit-mismatch-stops: 9-no-leak (run 1), audit-mismatch-stops: 7-report-only-mismatch (run 2), audit-mismatch-stops: 9-no-leak (run 2) · runs 6 · $0.59 · 86 s · claude 2.1.316 · tree clean · mutation report-run-id · tomo-tmp/evals/2026-10-31T15-36-28Z
```

`--mutation report-run-id --case *-failure-reported`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · state-flip-failure-reported: 7-report-only (run 0), state-flip-failure-reported: 9-no-leak (run 0), state-flip-failure-reported: 7-report-only (run 1), state-flip-failure-reported: 9-no-leak (run 1), state-flip-failure-reported: 7-report-only (run 2), state-flip-failure-reported: 9-no-leak (run 2), upload-failure-reported: 7-report-only (run 0), upload-failure-reported: 9-no-leak (run 0), upload-failure-reported: 7-report-only (run 1), upload-failure-reported: 9-no-leak (run 1), upload-failure-reported: 7-report-only (run 2), upload-failure-reported: 9-no-leak (run 2) · runs 6 · $0.60 · 92 s · claude 2.1.316 · tree clean · mutation report-run-id · tomo-tmp/evals/2026-10-31T15-37-56Z
```

`--mutation report-run-id --case withheld-notices-relayed`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 9-no-leak (run 0), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 9-no-leak (run 1), withheld-notices-relayed: 7-report-only (run 2), withheld-notices-relayed: 9-no-leak (run 2) · runs 3 · $0.32 · 49 s · claude 2.1.316 · tree clean · mutation report-run-id · tomo-tmp/evals/2026-10-31T15-39-30Z
```

### `status-sentence-first` with the literal status line, from commit 99a6f50c ($1.58)

Red 3/3 in all five cases: `7-report-only` in `audit-gates-delivery`, `upload-failure-reported`, `state-flip-failure-reported` and `withheld-notices-relayed`, `7-report-only-mismatch` in `audit-mismatch-stops`.

`--mutation status-sentence-first --case audit-*`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · audit-gates-delivery: 7-report-only (run 0), audit-gates-delivery: 7-report-only (run 1), audit-gates-delivery: 7-report-only (run 2), audit-mismatch-stops: 7-report-only-mismatch (run 0), audit-mismatch-stops: 7-report-only-mismatch (run 1), audit-mismatch-stops: 7-report-only-mismatch (run 2) · runs 6 · $0.67 · 53 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T16-45-20Z
```

`--mutation status-sentence-first --case *-failure-reported`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/2 cases · state-flip-failure-reported: 7-report-only (run 0), state-flip-failure-reported: 7-report-only (run 1), state-flip-failure-reported: 7-report-only (run 2), upload-failure-reported: 7-report-only (run 0), upload-failure-reported: 7-report-only (run 1), upload-failure-reported: 7-report-only (run 2) · runs 6 · $0.60 · 62 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T16-46-15Z
```

`--mutation status-sentence-first --case withheld-notices-relayed`

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 7-report-only (run 0), withheld-notices-relayed: 7-report-only (run 1), withheld-notices-relayed: 7-report-only (run 2) · runs 3 · $0.31 · 37 s · claude 2.1.316 · tree clean · mutation status-sentence-first · tomo-tmp/evals/2026-10-31T16-47-19Z
```

**Block S total: 13 invocations, $6.25. Every conductor proof holds on sonnet.**

## T4.3 — merge evidence

Three full suites (`scripts/run-evals.sh --keep-temp`, no `--case`), back to back, no edits in between. Log: `tomo-tmp/evals/merge-evidence-043.log` (gitignored).

### First attempt, candidate e91276104f215adbbcce6f1ba0af2deb61bd15c6 (haiku conductor 0.24.2) — RED

`full suite 1`

```
GREEN 7/7 cases · runs 21 · $2.33 · 416 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T15-01-31Z
```

`full suite 2`

```
RED 5/7 cases · state-flip-failure-reported: 7-report-only (run 1), upload-failure-reported: 7-report-only (run 2) · runs 21 · $2.27 · 373 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T15-08-29Z
```

`full suite 3`

```
GREEN 7/7 cases · runs 21 · $2.20 · 378 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T15-14-44Z
```

Suite 2 failed `7-report-only` in `state-flip-failure-reported` (run 1) and `upload-failure-reported` (run 2). In both traces the conductor prefaced the stop report with its own sentence ("Pass 2 did not finish cleanly: …", "Pass 2 synthesis did not complete. The Step 4 report is below."), the F5 deviation that rule 5 of 0.24.2 forbids. All three suites took 373–416 s, over the 6 min KPI. Owner decisions: conductor on sonnet, duration KPI 7 min (spec README Decisions Log).

### Second attempt, candidate 99a6f50cf8cc574e04f402d79f3b7bd8830740f2 (sonnet conductor 0.25.0) — GREEN

`full suite 1`

```
GREEN 7/7 cases · runs 21 · $2.75 · 271 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-47-57Z
```

`full suite 2`

```
GREEN 7/7 cases · runs 21 · $2.76 · 310 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-52-30Z
```

`full suite 3`

```
GREEN 7/7 cases · runs 21 · $2.74 · 286 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-57-42Z
```

All three GREEN 7/7. Median cost $2.75 (≤ $3.10), maximum $2.76 (< $5), maximum duration 310 s (≤ 7 min). T4.3 met.

## Totals after Phase 4 evals

| Item | Cost |
|---|---|
| T4.1 (Blocks A to D, haiku conductor) | $16.12 |
| Block S (sonnet re-proofs) | $6.25 |
| T4.3 first attempt (RED) | $6.80 |
| T4.3 second attempt (GREEN) | $8.25 |
| **Phase 4** | **$37.42** |
