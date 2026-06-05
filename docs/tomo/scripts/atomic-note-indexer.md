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

WHY: The scanner depends on Kado's `listNotes` search operation (branch `feat/listnotes-search-op` at the time of F-34 development), which was not yet merged to the Kado release reaching the Tomo instance when Phases 1-4 were implemented. All implementation, schema, and unit-test work was completed against fixtures. Live validation (Phase 5, task T5.2) is explicitly gated on the Kado release shipping `listNotes` to the instance. The `dataview-inline-field` path was already available.

NOTE (live validation 2026-06-05): the `listNotes` capability is available on the Kado dev branch and was exercised against the real ~281-note vault. The first live run surfaced two classes of defect that fixtures could not — topic-extraction quality and Kado rate-limiting — both fixed below.

## Topic-Extraction Quality: Tags-by-prefix, No Heading or Title-Word Noise

WHY: The first live scan produced 166 "clusters" for ~281 notes, dominated by structural noise, not themes. Measurement against the real vault settled the topic-source policy that fixtures had not stressed:

- **Level-2 headings contribute nothing useful and are excluded.** 168 of 216 distinct level-2 headings occur in exactly one note (genuine, but a cluster needs ≥ `min_cluster_size`, so a freq-1 heading can never form one), while every heading frequent enough to cluster is a template section (`Definition`, `Resources`, `Code`, `Problem Statement`, …). Headings therefore only ever inject template noise into accumulation clusters. `extract_topics_from_fields` drops Method 2 (level-2 headings); the note's H1/title still feeds Method 1.
- **Only `topic/`-prefixed tags are themes; the prefix list is configurable.** The vault's tag taxonomy splits into `type/` (note types: `note/code`, `note/quote`, …), `stage/`, and `topic/` (the thematic axis). Surfacing all tags made `code`/`content`/`plugin`/`knowledge` (the `note/*` type leaves) into giant false clusters. Method 4 now keeps only tags whose path starts with a configured prefix (`vault-config.tomo.accumulation.topic_tag_prefixes`, default `["topic/"]`) and emits the leaf after the prefix. It is an array + config-driven because other vaults use different thematic prefixes.
- **Title segments are not split into single words.** Method 1 previously exploded "Personal Need" → `personal`, `need`; multi-word title segments now stay whole, so generic single words stop forming clusters.
- **Date-shaped link targets are filtered.** Daily-note links (`[[2022-09-06]]`) were producing ~90 date "topics" via Method 3; link targets matching `^\d{4}-\d{2}-\d{2}$` are now dropped.

Net live effect: 166 → ~118 reliable, thematic clusters (LYT/PKM concepts, value/need categories, Japan), zero heading/bracket/date noise. The detailed measurement lives in spec 015 `solution.md` (Post-Live-Validation Refinements).

## Rate-Limiting on Per-Candidate `up::` Reads

WHY: The per-candidate `dataview-inline-field` reads (ADR-5) issue one Kado call per cluster candidate; on a real vault this burst tripped Kado's rate limiter (HTTP 429). Each 429 was raised immediately, and the scanner's conservative error path (treat-as-classified) then dropped those notes from clusters — making membership silently unreliable (44 notes wrongly dropped in one run). The fix lives in the shared HTTP layer, not here: `lib/kado_client.py` `_call_tool` now retries 429/503 with exponential backoff (honoring `Retry-After`, capped, then surfacing `KadoError` after exhaustion). With retries, the same run dropped 0 notes. The retry belongs in `kado_client` because every Kado caller benefits and the scanner's treat-as-classified path remains the correct final fallback once retries are exhausted.
