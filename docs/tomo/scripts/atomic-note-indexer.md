# WHY: atomic-note-indexer.py (script)

> Rationale for decisions in `tomo/scripts/atomic-note-indexer.py`.

## Separate Scanner Script, Not Folded into Existing Scripts (ADR-1)

WHY: The accumulation indexer is a new cold-path producer that lives in its own script rather than extending `moc-tree-builder.py` or `shared-ctx-builder.py`. `moc-tree-builder.py` was already near the Constitution L2 size guideline (~300-500 LOC) at 722 LOC when F-34 was designed; extending it would push it further over and muddy the separation between MOC-tree concerns (tree shape, section hierarchy) and accumulation concerns (unclassified note clustering). The cold-path producer / cache-persist / shared-ctx-surface / subagent-consume pipeline mirrors F-35's `placeholder_mocs` shape exactly — a separate script at the produce stage makes every pipeline stage individually replaceable.

## Cold-Path Pre-Compute, Not Per-Item kado-search in the Subagent (Option b over option a)

WHY: The architecture decision table for F-34 identified two viable options: (a) add `kado-search` to `inbox-analyst`'s tool list and perform per-item vault searches at Pass-1 subagent time; (b) pre-compute the accumulation index once per `/explore-vault` run and pass it through the shared-ctx envelope. Option (b) was chosen. The XDD-009 and XDD-012 designs established a "no kado-search in subagent" invariant: inbox-analyst subagents do not issue vault searches directly, because Pass-1 subagent cost is already the primary token cost centre and per-item searches amplify it with every inbox batch. Pre-computing on the cold path keeps the Pass-1/subagent cost profile unchanged — the index is built once, budget-trimmed into shared-ctx, and consumed via a dict lookup with no additional Kado calls.

## `up::` Detection via Per-Candidate dataview-inline-field (ADR-5)

WHY: Classifying whether a note already has a MOC parent (an `up::` link) requires reading that note's Dataview inline fields. The ADR-5 decision chose per-candidate `kado-read dataview-inline-field` calls over any bulk projection approach because Kado's architecture places Dataview inline-field parsing outside the core metadata cache — a bulk "return all inline fields for all notes" operation is not available. The reads are bounded to candidate-group members only (notes in topic groups that already reached `min_cluster_size` in raw count), so the number of reads scales with cluster concentration, not vault size. Risk caveat recorded in the SDD (§Risks): if `dataview-inline-field` does NOT return `up::` values that are embedded inside callout blocks (e.g. `> up:: [[MOC]]`), ADR-5 needs a fallback — verify against a real fixture with callout-embedded `up::` before locking A5 in live validation (T5.2).

## Graceful Degradation: Emit `{}` and Exit Non-Zero on Kado/listNotes Error

WHY: When the scanner cannot reach Kado or `listNotes` fails, it emits an empty JSON object `{}` to stdout and exits with a non-zero code. This is the correct failure boundary: an empty accumulation index degrades gracefully (inbox-analyst sees no `accumulation_index` field in shared-ctx and applies today's unchanged behaviour per A6/CON-1), whereas a missing `discovery-cache.yaml` or a partial cache write would silently break MOC matching and classification downstream. The non-zero exit lets the caller (`vault-explorer` Step 9) detect the failure, surface the stderr to the user, and continue cache generation without the `--accumulation` argument — so the cache is always produced, just without the accumulation field. This is where the rationale for Step 9's degrade block lives; the block itself is in `vault-explorer.md` but the reasoning belongs here, not in the agent prompt (memory `feedback_docs_in_script_not_agent`).

## Kado Release Dependency and Live-Validation Gate

WHY: The scanner depends on Kado's `listNotes` search operation (branch `feat/listnotes-search-op` at the time of F-34 development), which was not yet merged to the Kado release reaching the Tomo instance when Phases 1-4 were implemented. All implementation, schema, and unit-test work was completed against fixtures. Live validation (Phase 5, task T5.2) is explicitly gated on the Kado release shipping `listNotes` to the instance. The `dataview-inline-field` path was already available. This is a planned gate, not a defect — the script and the tests are correct; the live-run against Marcus's vault waits on an external dependency.
