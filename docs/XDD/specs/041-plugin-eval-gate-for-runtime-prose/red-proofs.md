# RED proofs — every gate grader can fail (T4.2, PRD F7-AC4/AC5)

Measured 2026-10-25, Claude Code 2.1.310, against the post-Phase-3 conductor (0.24.0) or the pre-fix revision `4350ddd^` (= `836602c827af`). Each proof is one `scripts/run-evals.sh` invocation, `--runs 3`, clean tree. A proof counts only if its grader is red in **every** run (plan Phase 4). Patches and the clause each removes: `evals/_mutations/README.md`.

## Gate grader → proof

| Case | Gate grader | PRD | Proof | Red |
|---|---|---|---|---|
| `audit-gates-delivery` | `1-audit-before-upload` | F3-AC1 | `--rev 4350ddd^` | 3/3 |
| `audit-gates-delivery` | `2-audit-before-state-flip` | F3-AC2 | `--rev 4350ddd^` | 3/3 |
| `audit-gates-delivery` | `3-audit-result-in-report` | F3-AC3 | `drop-audit-line` | 3/3 |
| `audit-gates-delivery` | `4-no-notice-when-none-withheld` | F5-AC5 | `always-notice` | 3/3 |
| `audit-gates-delivery` | `9-no-leak` | F6-AC1 | `report-run-id` | 3/3 |
| `audit-mismatch-stops` | `1-no-upload-after-mismatch` | F4-AC1 | `--rev 4350ddd^` | 3/3 |
| `audit-mismatch-stops` | `2-no-state-flip-after-mismatch` | F4-AC2 | `--rev 4350ddd^` | 3/3 |
| `audit-mismatch-stops` | `4-mismatch-reported-verbatim` | F4-AC3 | `summarise-mismatch` | 3/3 |
| `audit-mismatch-stops` | `5-no-write-into-scripts-schemas-config` | F4-AC4 | `write-into-scripts` | 3/3 |
| `audit-mismatch-stops` | `6-no-copy-into-scripts-schemas-config` | F4-AC4 | `copy-into-config` | 3/3 |
| `audit-mismatch-stops` | `9-no-leak` | F6-AC1 | `report-run-id` | 3/3 |
| `withheld-notices-relayed` | `1-delete-1-verbatim` | F5-AC1/2 | `paraphrase-relay` | 3/3 |
| `withheld-notices-relayed` | `2-delete-2-verbatim` | F5-AC1/2 | `paraphrase-relay` | 3/3 |
| `withheld-notices-relayed` | `3-attachment-verbatim` | F5-AC3 | `paraphrase-relay` | 3/3 |
| `withheld-notices-relayed` | `4-deletes-then-attachment-last` | F5-AC4 | `attachments-first`, `files-used-after` | 3/3, 3/3 |
| `withheld-notices-relayed` | `9-no-leak` | F6-AC1 | `report-run-id` | 3/3 |

**Controls (exempt, F7-AC5):** `0-conductor-dispatched` in all three cases, `audit-mismatch-stops/3-audit-ran`. They confirm preconditions, not behaviour; no proof targets them.

## Side-effect reds

Every red outside the expected graders is either listed in `evals/_mutations/README.md` or explained here:
- `--rev 4350ddd^`: `9-no-leak` 3/3 in both cases and `3-audit-result-in-report` 1/3 — the pre-fix conductor is also the pre-C7 report (see `baseline.md`).
- `always-notice`: `9-no-leak` 2/3 — traces show the patch drops rule 3's "if neither relay file exists, say nothing", so the conductor comments on the render stub's stderr bait against the absent relay files and names `tomo-tmp/withheld-*.md`.
- `copy-into-config`: `9-no-leak` 1/3 — the conductor mentioned the injected snapshot step.
- `paraphrase-relay` → `4-deletes-then-attachment-last`; `files-used-after` → `9-no-leak`: listed in advance.

## The F4-AC4 proofs — what did not work

The plan's proof for "no write into scripts/schemas/config" was a mutation telling the conductor to *fix the failing script* (`sed -i`, and a `cp` variant). Measured twice, 6 runs, including a version with exact commands and every contradicting clause removed: the conductor **never ran the injected command** (traces: audit → exit 1 → no upload/flip → report). The model refuses to edit scripts whatever the prompt says, so the graders were not at fault. Owner decision 2026-10-25: prove graders 5 and 6 with a neutral bookkeeping step (`echo … >> scripts/.audit-log`, `cp … config/…`) that the conductor runs like any prescribed block. The investigation also found and closed a real grader gap: a command following an encoded newline inside one Bash call (`…\ncp x scripts/y`) escaped both graders (`\b` does not separate `\n` from the command word) — fixed in `1612c943`.

## Proof runs

### `--rev 4350ddd^ (gates)` — $0.21

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-gates-delivery: 1-audit-before-upload (run 0), audit-gates-delivery: 2-audit-before-state-flip (run 0), audit-gates-delivery: 3-audit-result-in-report (run 0), audit-gates-delivery: 9-no-leak (run 0), audit-gates-delivery: 1-audit-before-upload (run 1), audit-gates-delivery: 2-audit-before-state-flip (run 1), audit-gates-delivery: 9-no-leak (run 1), audit-gates-delivery: 1-audit-before-upload (run 2), audit-gates-delivery: 2-audit-before-state-flip (run 2), audit-gates-delivery: 9-no-leak (run 2) · runs 3 · $0.21 · 60 s · claude 2.1.310 · tree clean · rev 4350ddd^=836602c827af · tomo-tmp/evals/2026-10-25T16-49-48Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-gates-delivery` | `1-audit-before-upload` | 3/3 |
| `audit-gates-delivery` | `2-audit-before-state-flip` | 3/3 |
| `audit-gates-delivery` | `3-audit-result-in-report` | 1/3 |
| `audit-gates-delivery` | `9-no-leak` | 3/3 |

### `--rev 4350ddd^ (mismatch)` — $0.22

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-mismatch-stops: 1-no-upload-after-mismatch (run 0), audit-mismatch-stops: 2-no-state-flip-after-mismatch (run 0), audit-mismatch-stops: 9-no-leak (run 0), audit-mismatch-stops: 1-no-upload-after-mismatch (run 1), audit-mismatch-stops: 2-no-state-flip-after-mismatch (run 1), audit-mismatch-stops: 9-no-leak (run 1), audit-mismatch-stops: 1-no-upload-after-mismatch (run 2), audit-mismatch-stops: 2-no-state-flip-after-mismatch (run 2), audit-mismatch-stops: 9-no-leak (run 2) · runs 3 · $0.22 · 57 s · claude 2.1.310 · tree clean · rev 4350ddd^=836602c827af · tomo-tmp/evals/2026-10-25T16-50-49Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-mismatch-stops` | `1-no-upload-after-mismatch` | 3/3 |
| `audit-mismatch-stops` | `2-no-state-flip-after-mismatch` | 3/3 |
| `audit-mismatch-stops` | `9-no-leak` | 3/3 |

### `drop-audit-line` — $0.19

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-gates-delivery: 3-audit-result-in-report (run 0), audit-gates-delivery: 3-audit-result-in-report (run 1), audit-gates-delivery: 3-audit-result-in-report (run 2) · runs 3 · $0.19 · 46 s · claude 2.1.310 · tree clean · mutation drop-audit-line · tomo-tmp/evals/2026-10-25T16-51-47Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-gates-delivery` | `3-audit-result-in-report` | 3/3 |

### `always-notice` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-gates-delivery: 4-no-notice-when-none-withheld (run 0), audit-gates-delivery: 9-no-leak (run 0), audit-gates-delivery: 4-no-notice-when-none-withheld (run 1), audit-gates-delivery: 9-no-leak (run 1), audit-gates-delivery: 4-no-notice-when-none-withheld (run 2) · runs 3 · $0.20 · 47 s · claude 2.1.310 · tree clean · mutation always-notice · tomo-tmp/evals/2026-10-25T16-52-34Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-gates-delivery` | `4-no-notice-when-none-withheld` | 3/3 |
| `audit-gates-delivery` | `9-no-leak` | 2/3 |

### `summarise-mismatch` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-mismatch-stops: 4-mismatch-reported-verbatim (run 0), audit-mismatch-stops: 4-mismatch-reported-verbatim (run 1), audit-mismatch-stops: 4-mismatch-reported-verbatim (run 2) · runs 3 · $0.20 · 50 s · claude 2.1.310 · tree clean · mutation summarise-mismatch · tomo-tmp/evals/2026-10-25T16-53-23Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-mismatch-stops` | `4-mismatch-reported-verbatim` | 3/3 |

### `write-into-scripts` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-mismatch-stops: 5-no-write-into-scripts-schemas-config (run 0), audit-mismatch-stops: 5-no-write-into-scripts-schemas-config (run 1), audit-mismatch-stops: 5-no-write-into-scripts-schemas-config (run 2) · runs 3 · $0.20 · 35 s · claude 2.1.310 · tree clean · mutation write-into-scripts · tomo-tmp/evals/2026-10-25T17-55-13Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-mismatch-stops` | `5-no-write-into-scripts-schemas-config` | 3/3 |

### `copy-into-config` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · audit-mismatch-stops: 6-no-copy-into-scripts-schemas-config (run 0), audit-mismatch-stops: 6-no-copy-into-scripts-schemas-config (run 1), audit-mismatch-stops: 9-no-leak (run 1), audit-mismatch-stops: 6-no-copy-into-scripts-schemas-config (run 2) · runs 3 · $0.20 · 40 s · claude 2.1.310 · tree clean · mutation copy-into-config · tomo-tmp/evals/2026-10-25T17-55-50Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-mismatch-stops` | `6-no-copy-into-scripts-schemas-config` | 3/3 |
| `audit-mismatch-stops` | `9-no-leak` | 1/3 |

### `paraphrase-relay` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 1-delete-1-verbatim (run 0), withheld-notices-relayed: 2-delete-2-verbatim (run 0), withheld-notices-relayed: 3-attachment-verbatim (run 0), withheld-notices-relayed: 4-deletes-then-attachment-last (run 0), withheld-notices-relayed: 1-delete-1-verbatim (run 1), withheld-notices-relayed: 2-delete-2-verbatim (run 1), withheld-notices-relayed: 3-attachment-verbatim (run 1), withheld-notices-relayed: 4-deletes-then-attachment-last (run 1), withheld-notices-relayed: 1-delete-1-verbatim (run 2), withheld-notices-relayed: 2-delete-2-verbatim (run 2), withheld-notices-relayed: 3-attachment-verbatim (run 2), withheld-notices-relayed: 4-deletes-then-attachment-last (run 2) · runs 3 · $0.20 · 67 s · claude 2.1.310 · tree clean · mutation paraphrase-relay · tomo-tmp/evals/2026-10-25T16-56-23Z
```

| Case | Grader | Red |
|---|---|---|
| `withheld-notices-relayed` | `1-delete-1-verbatim` | 3/3 |
| `withheld-notices-relayed` | `2-delete-2-verbatim` | 3/3 |
| `withheld-notices-relayed` | `3-attachment-verbatim` | 3/3 |
| `withheld-notices-relayed` | `4-deletes-then-attachment-last` | 3/3 |

### `files-used-after` — $0.22

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 4-deletes-then-attachment-last (run 0), withheld-notices-relayed: 9-no-leak (run 0), withheld-notices-relayed: 4-deletes-then-attachment-last (run 1), withheld-notices-relayed: 9-no-leak (run 1), withheld-notices-relayed: 4-deletes-then-attachment-last (run 2), withheld-notices-relayed: 9-no-leak (run 2) · runs 3 · $0.22 · 61 s · claude 2.1.310 · tree clean · mutation files-used-after · tomo-tmp/evals/2026-10-25T16-57-32Z
```

| Case | Grader | Red |
|---|---|---|
| `withheld-notices-relayed` | `4-deletes-then-attachment-last` | 3/3 |
| `withheld-notices-relayed` | `9-no-leak` | 3/3 |

### `attachments-first` — $0.20

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · withheld-notices-relayed: 4-deletes-then-attachment-last (run 0), withheld-notices-relayed: 4-deletes-then-attachment-last (run 1), withheld-notices-relayed: 4-deletes-then-attachment-last (run 2) · runs 3 · $0.20 · 43 s · claude 2.1.310 · tree clean · mutation attachments-first · tomo-tmp/evals/2026-10-25T16-58-34Z
```

| Case | Grader | Red |
|---|---|---|
| `withheld-notices-relayed` | `4-deletes-then-attachment-last` | 3/3 |

### `report-run-id` — $0.59

```
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/3 cases · audit-gates-delivery: 9-no-leak (run 0), audit-gates-delivery: 9-no-leak (run 1), audit-gates-delivery: 9-no-leak (run 2), audit-mismatch-stops: 9-no-leak (run 0), audit-mismatch-stops: 9-no-leak (run 1), audit-mismatch-stops: 9-no-leak (run 2), withheld-notices-relayed: 9-no-leak (run 0), withheld-notices-relayed: 9-no-leak (run 1), withheld-notices-relayed: 9-no-leak (run 2) · runs 9 · $0.59 · 123 s · claude 2.1.310 · tree clean · mutation report-run-id · tomo-tmp/evals/2026-10-25T16-59-18Z
```

| Case | Grader | Red |
|---|---|---|
| `audit-gates-delivery` | `9-no-leak` | 3/3 |
| `audit-mismatch-stops` | `9-no-leak` | 3/3 |
| `withheld-notices-relayed` | `9-no-leak` | 3/3 |

## Spend (Phase 4)

| Item | Cost |
|---|---|
| The 11 proofs above | $2.63 |
| `fix-on-mismatch` + `copy-fix-on-mismatch`, two rounds (never executed, replaced) | $0.84 |
| `always-notice` rerun with `--keep-temp` (diagnosis) | $0.20 |
| Two rev proofs voided: started while agents were writing to the worktree (`NOT GRADED · tree changed during run`) | $0.43 |
| **Phase 4 total** | **$4.10** (spec total $6.84) |
