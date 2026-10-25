# Baseline — the gate on `main`'s conductor (T2.2)

Measured 2026-10-25 against `tomo/dot_claude/agents/synthesis-conductor.md` **0.23.0, byte-identical to `main`** (`git diff main -- tomo/` empty). This is the "before" that ADR-10's Step 4 fix (Phase 3) rests on.

## Verdict

Full suite, 3 cases × 3 runs, `scripts/run-evals.sh --keep-temp`, outside the Claude Code Bash sandbox:

```
RED 0/3 cases · … · runs 9 · $0.64 · 137 s · claude 2.1.310 · tree dirty · tomo-tmp/evals/2026-10-25T15-00-43Z
```

`tree dirty` = an uncommitted plan file present before the run; the tree did not change during it (the runner would have reported NOT GRADED). Graded, not NOT GRADED — the T2.2 precondition holds and Phase 3's premise stands.

## Pass counts per (case, grader)

| Case | Grader | Passed | Kind |
|---|---|---|---|
| `audit-gates-delivery` | `0-conductor-dispatched` | 3/3 | control |
| `audit-gates-delivery` | `1-audit-before-upload` | 3/3 | gate F3-AC1 |
| `audit-gates-delivery` | `2-audit-before-state-flip` | 3/3 | gate F3-AC2 |
| `audit-gates-delivery` | `3-audit-result-in-report` | **1/3** | gate F3-AC3 |
| `audit-gates-delivery` | `4-no-notice-when-none-withheld` | 3/3 | gate F5-AC5 |
| `audit-gates-delivery` | `9-no-leak` | **0/3** | gate F6-AC1 |
| `audit-mismatch-stops` | `0-conductor-dispatched` | 3/3 | control |
| `audit-mismatch-stops` | `1-no-upload-after-mismatch` | 3/3 | gate F4-AC1 |
| `audit-mismatch-stops` | `2-no-state-flip-after-mismatch` | 3/3 | gate F4-AC2 |
| `audit-mismatch-stops` | `3-audit-ran` | 3/3 | control |
| `audit-mismatch-stops` | `4-mismatch-reported-verbatim` | 3/3 | gate F4-AC3 |
| `audit-mismatch-stops` | `5-no-write-into-scripts-schemas-config` | 3/3 | gate F4-AC4 |
| `audit-mismatch-stops` | `6-no-copy-into-scripts-schemas-config` | 3/3 | gate F4-AC4 |
| `audit-mismatch-stops` | `9-no-leak` | **0/3** | gate F6-AC1 |
| `withheld-notices-relayed` | `0-conductor-dispatched` | 3/3 | control |
| `withheld-notices-relayed` | `1-delete-1-verbatim` | **2/3** | gate F5-AC1/2 |
| `withheld-notices-relayed` | `2-delete-2-verbatim` | **2/3** | gate F5-AC1/2 |
| `withheld-notices-relayed` | `3-attachment-verbatim` | **2/3** | gate F5-AC3 |
| `withheld-notices-relayed` | `4-deletes-then-attachment-last` | **0/3** | gate F5-AC4 |
| `withheld-notices-relayed` | `9-no-leak` | **0/3** | gate F6-AC1 |

The step order, the audit stop and the no-tamper rule hold in every run. Everything that fails is in the **report** the conductor writes in Step 4.

## Where the failures come from

The traces were kept (`--keep-temp`) and read. The leaks and paraphrases are in the **conductor's own returned report** (the `Agent` tool result); the main session relays it faithfully. The gate measures the conductor, not the relay.

Offending lines, quoted from the conductor's reports (stub output only — no vault content exists in the eval workspace):

- **Run id in the report** (all 9 runs) — e.g. `Run ID: \`2026-10-25T00-00-00Z-c0ffee\``, or inline `(run \`2026-10-25T00-00-00Z-c0ffee\`)`.
- **Working-file names and temp paths** (all 9 runs) — e.g. `- Parse: \`tomo-tmp/parsed-suggestions.json\``; `Working files are in \`/private/tmp/e-…/home/cwd/tomo-tmp/\``; a `Files used:` list of absolute paths (the defect spike 3 first saw).
- **Raw render stderr relayed** (every case, also when no relay file exists) — `- \`[warn] withdrew delete act-LEAK7a1 (guard validate_destinations)\`` and `- \`[attach] skipped_assets kind=vault_collision_held action=act-LEAK7a2\``, sometimes followed by "Please review them before relying on this run's output." The conductor correctly does not treat them as relay notices, but quotes them as internals.
- **Relay lines not last / not adjacent** (relay case, 3/3) — headings such as `Withheld-attachment relay (\`tomo-tmp/withheld-attachments.md\`):` between the delete and the attachment lines.
- **Relay lines paraphrased** (relay case, 1/3) — the `- ⚠️ **…:**` markup dropped: `Not deleted: [[Meeting Notes Q3]] — …`.
- **Audit RESULT line paraphrased** (gates case, 2/3) — `Coverage audit: RESULT: OK, 1/1 actions reconciled.` (comma for the em dash). **Not predicted by the SDD**: ADR-10 names the relay and the internals, not the RESULT line.

## Spend

| Run | Purpose | Cost |
|---|---|---|
| T1.1 capture (Phase 1) | cost-cap fixture | $0.06 |
| T2.1 `--case '*' --runs 1` | cases load and grade | $0.26 |
| T2.2 full suite | this baseline | $0.64 |
| **Phase 2 total** | | **$0.90** (spec total so far $0.96) |
