# WHY: tomo/scripts/moc-discovery.py

> Rationale for decisions in `tomo/scripts/moc-discovery.py`.
> The script drives the `/moc-propose` skill (F-43, spec 013/021).
> This file documents the WHY behind every significant design choice;
> the HOW lives in the script itself and its inline docstrings.

## Scan Mode: Cache-Sourced Orphans (T5.1, ADR-11)

WHY: The original `_handle_scan` enumerated atomic-note candidates via a live
`list_dir` Kado call over each atomic-note subdirectory. This had two problems:

1. **Candidate cap abuse** — every atomic note (including already-MOC-linked
   notes with a valid `up::` link) was counted toward the 200-candidate cap.
   A vault with 276 notes and 206 orphans would always abort with
   `candidate-cap-exceeded`, making whole-vault `/moc-propose` unusable.

2. **Redundant live call** — the MOC-structure cache (`entries[kind=="note"]`)
   already contains the full in-scope note set with `up_state` annotations,
   populated by `moc_scan.in_scope_note_paths`. Scanning live re-does work
   the cache already captured.

Fix (spec 021 T5.1): `_handle_scan` now reads `cache["entries"]` filtered to
`kind=="note" AND up_state=="absent"`. These are the true orphans — atomic notes
with no `up::` parent link. No Kado call is made. Candidates carry `topics`
directly from the cache entry, eliminating the Phase 2 LLM-miss path for
scan-mode candidates.

## Scoped Modes: All Notes, No Orphan Filter

WHY: Scoped modes (`folder`, `tag`, `class`, `title`, `free-text`) operate on a
user-specified target and must return every matching note regardless of `up_state`.
A user asking "find MOC candidates in folder X" expects to see ALL notes in X —
including already-parented ones — so they can decide whether to add them to an
existing MOC or propose a new one. The orphan-filter is **scan-ONLY** because
scan's purpose is to find unparented notes across the whole vault, while scoped
modes are user-directed exploration.

## Candidate Cap: 500 (was 200) (T5.1, ADR-11)

WHY: With scan sourcing only orphans, the realistic candidate set is smaller
(orphans only, not all notes), but 200 was still too low even for that. A vault
with 200+ orphans (e.g. 206 out of 276 notes in Marcus's vault) would abort.
The cap was raised to 500 in `MocProposalConfig.candidate_cap` (shared-ctx-builder)
and the `getattr(config, "candidate_cap", 500)` fallback in Phase 1.

The cap exists to prevent accidentally dispatching thousands of LLM calls when
the cache is complete and `cache_miss_max_batches` would catch that — the cap is
a fast-fail gate, not the primary quality control. 500 is a reasonable ceiling
for a dense personal vault.

## `_build_topics_index`: Indexing Both MOC and Note Entries (T5.1)

WHY: Before T5.1, `_build_topics_index` only indexed `cache["map_notes"]` (the
shim layer, kind==moc entries). Scan-mode candidates have paths that are
`kind=="note"` entries — they never appeared in `map_notes`. This meant every
scan candidate was a Phase 2 cache miss, requiring an LLM batch call even though
the cache already had their topics.

Fix: `_build_topics_index` now indexes `cache["entries"]` (all kinds) in a first
pass, then overlays `cache["map_notes"]` in a second pass so MOC shim entries
are never shadowed. This makes scan candidates Phase 2 cache hits — no LLM call
needed.

The `map_notes` overlay is kept because `title`/`free-text` mode constructs
candidates from `map_notes` entries directly, and those must still resolve as
hits in the index. The two passes are additive and commutative for any path that
appears in both (last-writer-wins, which the cache-builder prevents by deduping).

## Phase 2 LLM Path Still Active for Non-Cached Candidates

WHY: Scoped modes (folder/tag/class) source candidates from live Kado calls.
These paths may not be in the cache (e.g. a folder query on a rarely-scanned
subfolder). For those candidates, Phase 2's LLM batch-extract path is still
needed. `_build_topics_index` returns an empty slot for them, they land in
`misses`, and `_batch_llm_extract` handles them. This path was not changed by
T5.1.

## Orphan Output Shaping: Notes-Only Default, Cap in the Pipeline (ADR-12, T6.3)

WHY: The case-(a) orphan pass (`emit_orphan_suggestions`) was called with the
full cache entries (notes AND MOCs) and no bound, so a whole-vault scan emitted
251 suggestions — 45 of them noise MOCs (template-vault, root maps) and a
206-note flood. The default scan now calls the pass with `kinds=("note",)` (MOC
orphans are surfaced on demand via `--check-moc-uplinks`, not on the
notes-discovery path) and truncates the link-first-ordered result to
`orphan_display_cap` (default 50) via `_cap_orphans`, recording `orphan_total` +
`orphan_overflow` in the report for the reducer's overflow footer.

The cap lives HERE, not in `lib/orphan_link`: the cap is config-driven
(`tomo.moc_proposal.orphan_display_cap`) and the lib stays pure/config-free for
testability. Ordering in the lib + capping in the pipeline means truncation
always keeps the most-actionable suggestions.

## `--check-moc-uplinks`: Focused Audit, Clustering Skipped (ADR-12, T6.3)

WHY: A user who wants to audit MOC parentage shouldn't have to wade through the
clustering pipeline or note orphans. `_run_moc_uplink_check` runs ONLY the orphan
pass over `kinds=("moc",)` and emits a `check-moc-uplinks` report. main()
short-circuits to it right after the cache load — before squelch decrement (no
clustering run to squelch) and before `--emit-phase1` (the agent never combines
the two). No Kado is built in this branch: the pass reads cache entries only, so
a fresh cache needs no rebuild. Keeping tag-discovery broad (root/Dewey MOCs stay
in the cache as link targets) is what makes this audit useful — it can offer an
existing parent MOC for an orphan MOC.

## `exclude/note` Tag: Filter at Scan Candidate Source (ADR-13 B-note, T7.2)

WHY: A note tagged `MiYo/Tomo/exclude/note` should never be proposed as a
clustering candidate in `/moc-propose`'s whole-vault scan. The user has explicitly
opted this note out of MOC-proposal discovery — e.g. a daily-log note or
administrative note that doesn't belong in a thematic MOC.

The filter lives at the scan candidate source (`_handle_scan`) rather than
downstream (in `emit_orphan_suggestions` or `phase3_cluster`) for two reasons:

1. **Early rejection is cheaper** — a note excluded at Phase 1 consumes no topic
   lookup, no LLM batch slot, no cluster slot. Filtering downstream would still
   touch Phase 1–2 resources for notes that should be invisible to the pipeline.

2. **Consistent with scan's purpose** — `_handle_scan` is already the single
   cache-based candidate source for scan mode (ADR-11, T5.1). Adding the tag
   guard here keeps all scan-specific selection logic in one place.

The filter checks `EXCLUDE_NOTE_TAG in (entry.get("tags") or [])` — exact string
match on the full tag `"MiYo/Tomo/exclude/note"` (imported from `lib/moc_tags.py`,
the single home for both exclude-tag constants). The `tags` field is populated by
`moc-tree-builder.py:extract_tags` (T7.1), which reads frontmatter and inline
tags from the cache entry.

Scoped modes (`folder`, `tag`, `class`, `title`, `free-text`) are NOT affected —
they are user-directed, path-specific queries where the user has already said "look
here"; the exclude tag is respected only for the whole-vault passive scan.

## `candidate_stems` / Cluster `items` Are Deduped (ADR-13 D4, T7.3)

WHY: `phase3_cluster` explodes each `Candidate` into one `ClusterCandidate` per
topic in `candidate.topics`. If a candidate carries two topic phrases that
normalise to the same key (e.g. `["shell", "shells"]`), both rows land in the
same cluster's `hits` list, causing the same `section_id` to appear twice in
`"items"`. The downstream `_enrich_cluster` copies `items` directly to
`candidate_stems` (`list(cluster.get("items") or [])`), so the duplicate
propagates to the rendered `#### Children (N)` count — which then disagrees with
the number of unique links in the section body.

The fix is an order-preserving dedup of `items` at assembly time inside
`lib/topic_clusters.build_topic_clusters` (first occurrence wins). This keeps
the fix colocated with the only location that knows which section_ids are
duplicates, while leaving the threshold check (`len(hits) < threshold`) on the
raw hit count — so a cluster that only reaches threshold due to duplicate rows is
still correctly dropped.

Dedup is NOT applied to cross-cluster membership: a candidate whose topics span
two distinct normalised keys correctly appears in both the `shell` cluster and the
`system` cluster. The dedup only removes a note from the SAME cluster appearing
twice.
