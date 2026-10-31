# RED proofs — Pass 1 conductor eval gate, Block A (T4.1, PRD F7)

Measured 2026-10-31, Claude Code 2.1.316, against the runtime files at these versions: `suggest-handling` 0.14.1, `force-atomic-handling` 0.15.0, `synthesis-conductor` 0.24.2 (`# version:` lines in `tomo/dot_claude`). Each proof is one invocation of

```
scripts/run-evals.sh --keep-temp --mutation <name> --case <case>
```

with 3 runs and a clean tree. A proof counts only if every expected grader is red in **every** run. Patches and the clauses each removes: `evals/_mutations/README.md`. Raw log: `tomo-tmp/evals/red-proofs-043.log` (gitignored); each verdict below was copied from it and matches the `verdict.txt` in its results directory. `PARTIAL SUITE` is printed because `--case` is given.

Block A: 15 invocations, 11 proven, 4 not proven, total cost $10.10.

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
| `analyst-name-not-type` | NOT PROVEN | see below | GREEN |
| `path-from-stem` | NOT PROVEN | see below | GREEN |
| `render-before-reduce` | NOT PROVEN | see below | GREEN |
| `setup-in-conductor` | NOT PROVEN | see below | red 3/3 + 1/3 |

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

## Not proven

Owner decision 2026-10-31: these four are re-run after the patch or the case is strengthened. They are not counted.

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
- `reword-report-line` → `pass1-warn-and-duplicates-relayed/02-warn-before-first-dispatch` 1/3. Grader defect on batched calls, being fixed (F6).
- `warn-is-diagnostic` → `02-warn-before-first-dispatch` 3/3 (the patch removes the `cat` that grader looks for).
- `setup-in-conductor` (not proven): `05-shared-ctx-once` 1/3 only.

## Open

Not yet run:

- Block B: `status-sentence-first` on all five Pass 2 cases (`audit-gates-delivery`, `audit-mismatch-stops`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported`).
- Block C: the five spec 041 patches rebased onto conductor 0.24.2: `summarise-mismatch`, `files-used-after`, `paraphrase-relay`, `explain-failure`, `report-run-id`.
- Re-proofs after strengthening: `analyst-name-not-type`, `path-from-stem`, `render-before-reduce`, `setup-in-conductor`.
