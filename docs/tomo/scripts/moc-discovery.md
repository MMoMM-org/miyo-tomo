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

## Inter-Cluster Member-Overlap Dedup (ADR-13 D3, T7.4)

WHY: `phase6_dedupe` only compares each proposed cluster's TOPIC set against
existing MOCs (Jaccard ≥ 0.80 or exact-title match). It has no awareness of how
proposed clusters relate to EACH OTHER. In practice, smaller clusters that are
entirely or mostly subsets of larger ones (e.g. MOC05 ⊆ MOC02 at 100% overlap,
MOC04 ⊆ MOC03 at 97%) survive `phase6_dedupe` because nothing in that pass
compares proposals to proposals.

The fix (`_dedupe_overlapping_clusters`) is a NEW post-`phase6_dedupe` pass that
compares proposed clusters against each other on their `candidate_stems` membership:

- Denominator is the SMALLER cluster's member count: `|small ∩ large| / |small|`.
- Threshold: `>= 0.80` (exactly 0.80 drops; 0.79 and below keeps both).
- Sort order: size DESC, then `cluster_id` ASC — so on a size tie the lower id
  wins (MOC01 survives, MOC02 dropped), giving a deterministic outcome independent
  of input order.
- A cluster already dropped is not re-evaluated as the "larger" reference against
  remaining clusters.
- Drop records appended to `duplicates_skipped` use `reason="member-overlap"` and
  `existing_moc` points to the surviving cluster's `cluster_id`. This matches the
  existing `duplicates_skipped` shape so downstream consumers (report renderer,
  agent surfacing) need no changes.

This pass is ADDITIVE: it does not change `phase6_dedupe`'s topics-vs-existing-MOC
logic, and it runs after `phase6_dedupe` so a cluster already dropped by an
existing-MOC match is never re-evaluated here.

## Note-Orphan Pass Removed from Cluster Path (ADR-13 D1, T7.5)

WHY: The `_run_pipeline` (cluster path) formerly called
`emit_orphan_suggestions(kinds=("note",))` after Phase 6.5 and populated
`orphan_suggestions` / `orphan_total` / `orphan_overflow` in the DiscoveryReport.
This produced a `## Orphan Notes & MOCs / ### Oxx` per-note section in the
proposal-doc, which contradicts ADR-13 D1: `/moc-propose` is cluster→new-MOC
only. The orphan section mixed two concerns (cluster proposal + vault health audit)
into one document, making the proposal-doc harder to act on.

The note-orphan pass is removed from `_run_pipeline`. The cluster path now emits
`orphan_suggestions=[]` / `orphan_total=0` / `orphan_overflow=0` unconditionally.

The emit helper (`emit_orphan_suggestions`), the cap helper (`_cap_orphans`), and
the renderer (`_render_orphan_section`) are RETAINED — they are still used by
`_run_moc_uplink_check` (the `--check-moc-uplinks` path), which produces MOC-orphan
suggestions for the dedicated MOC-parentage audit doc. Removing them would break
check mode.

Interactive note-orphan handling (pick a parent, create a new MOC for an orphan
note) is deferred to Garden-Audit (#30) where it belongs — a separate workflow,
not a sidebar in a cluster proposal.


## Link Members: Augmenting the Rendered Slice (spec 042 ADR-2, T2.1)

WHY: Topic clustering only finds notes that share a normalised topic. Notes the
user linked to several members of a proposed MOC belong there too, but carry
different topics. `_run_pipeline` therefore asks `kado-graph neighbors` for each
member of a cluster and adds every eligible non-member that appears in at least
two members' neighbour lists (`lib/link_members.augment_clusters`; rules and
budget in `docs/tomo/scripts/lib/link_members.md`).

**Insertion point — after D3 and the confidence sort, before Phase 6.5.** The
lookups cost Kado calls under a per-run attempt budget (120, ADR-4 v1.2, shared fairly across the rendered clusters). Running
them before Phase 6 / D3 would spend budget on clusters that are then dropped
as duplicates, squelched or absorbed. The confidence sort moved up from after
Phase 6.5 to directly after D3 so the slice is known before the lookups; Phase
6.5 decorates clusters in place and keeps their order, so the emitted order is
unchanged.

**Only the rendered slice — `clusters[:max_results]`.** The reducer renders at
most `max_results` cluster sections; a lookup for a cluster nobody sees is
wasted budget. Clusters beyond the slice get `link_lookup_status:
not_rendered`, `link_members: []` and cause no call. The slice is cut in
confidence order so the budget goes to the proposals the user reads first.

**Squelch, D3 and confidence stay topic-only.** Augmentation runs after all
three and only adds the `link_members` / `link_lookup_status` fields; it never
touches `items`, `candidate_stems` or `confidence`. A squelch signature
(`compute_topic_signature`, topics + top-5 stems) must stay stable across runs
so a rejected proposal stays muted — if link members fed the signature, a new
link in the vault would un-mute a proposal the user already rejected.
Confidence is "topic members / candidates"; counting link members would rank a
cluster by how linked it is, not by how well its topic covers the scope. D3
compares topic memberships; link members are allowed to appear in several
clusters (F1-AC4) and must not trigger an inter-cluster drop.

**Members are re-checked by `NodeEligibility` before lookups.** Pass 2
(`--phase1-input`) trusts the candidate list the agent hands back without
re-filtering, so a periodic note, MOC or inbox note can arrive as a topic
member. Such a member is not looked up and cannot act as a bridge. A member
that is merely missing from the cache (`uncached`) is still looked up:
folder/tag/class candidates come from live Kado and may be newer than the
cache build; that is no reason to lose their links.

**The lookup map is built by path, rendered by stem.** Phase 6.5 builds
`stem → path` with last-wins on a stem collision. Reused for lookups, two
candidates sharing a stem would lose one path: it would never be looked up and
could reappear as a link member of its own cluster under the member's stem.
The augmentation expands each cluster stem to every candidate path with that
stem, looks up each path, and maps `linked_with` back to stems for rendering.

**Colliding stems count by path (owner decision O4, 2026-10-28).** The
2-member threshold counts distinct member PATHS. Two notes that share a stem
(`Atlas/202 Notes/alpha.md`, `Atlas/202 Notes/2021 Thoughts/alpha.md`) are two
different notes, so a note linked from both qualifies, and the rendered reason
shows the shared name once (`linked with [[alpha]]`). Collapsing by stem would
make the reason line honest about the name but drop a real second link; the
owner chose to keep path counting and pin it with a test.

**Test fakes carry the graph surface.** The Kado client is not duck-typed
around the graph: any stand-in handed to the pipeline must expose `graph`,
`attempt_count`, `attempt_gate` and `min_interval`, the way `_NullKadoClient`
does (a `graph()` that raises `KadoError` degrades every rendered cluster to
`failed`). A branch that silently tolerated a missing surface would hide a
wiring mistake instead of failing it.

**`--emit-phase1` makes no graph call.** Pass 1 exits before the pipeline; the
two-pass flow counts as one run, and Pass 2 does the lookups once.

**`_NullKadoClient.graph` raises.** Without Kado the run still emits
proposals: every rendered cluster gets `failed` with no link members, and the
exit code is the one the run would have without link members.

**Report fields are additive.** `topic_clusters[i].link_members`,
`topic_clusters[i].link_lookup_status` and the top-level `link_stats` are new
keys; nothing existing changes. `link_stats` is part of `empty_report` (all
zeros) so abort and dry-run reports keep one shape for the reducer's
`Discovery:` line.


## `--around`: One Proposal From a Seed's Links (spec 042 F2, T3.1)

WHY: A note that grew links to several others is a MOC in waiting, but it
shares no topic with its neighbours, so no topic mode finds it. `--around
NAME_OR_PATH` builds one proposal from the seed's links alone: the seed is the
ticked member, every eligible neighbour (`NodeEligibility`) is an unticked link
member with `linked_with: [seed]`.

**Resolution reads the cache only.** The argument is matched against the
MOC-structure cache entries; there is no Kado name search (owner decision,
2026-10-28). A name search would turn a typo into a silent pick of some other
note; an uncached seed is reported as not found with the remedy ("rebuild the
cache or give a path"). Accepted forms: `stem`, `[[stem]]` (an `|alias` is
dropped), `stem.md`, and a vault path (anything containing `/`, `.md`
optional). A path is matched against entry paths, a name against entry stems.
Both comparisons ignore case: Obsidian resolves links case-insensitively, and
the resolved seed always carries the cache's own spelling, so Kado is never
sent the user's casing. Several matches are never guessed between — the run
stops and lists every matching path, whether the duplicates are two notes or a
note and a MOC, so the user can repeat the run with a path.

**Refusals, in order:** ambiguous → not found → periodic → MOC. A path
argument is checked for periodic before the cache lookup, because periodic
folders are usually outside the cache: without that, a daily note given by
path would read "not found" instead of the real reason. A periodic note links
everything of its day; a MOC around it is a day log, not a topic, so it is
refused ("periodic notes cannot be a MOC seed"). A MOC seed is a different
proposal type (extend the existing MOC, F3) and is routed to its own builder.

**The seed follows member eligibility (owner decision A, 2026-10-28).** A note seed that is not eligible as a link member (`NodeEligibility.check`: not Markdown, still in the inbox, outside the atomic-note folders, tagged `exclude/note`) is refused with `abort_reason: around-ineligible` and a message naming the reason in user terms, before any Kado call. Without this, a note the user excluded would end up as the ticked member of a new MOC, while the same note would have been withheld as a link member. The check runs after the periodic and MOC routing, so those keep their own messages.

**A MOC seed goes to the extension builder** (`_run_around_extension`, see
`around:<MOC>` below); the routing in front of it is the same resolver.

**Exactly one lookup, from the same budget.** The seed's `neighbors` call runs
inside `with LinkLookup(client)`, so it is paced and counted against the 120
attempt budget like any other lookup, and `link_stats` reports it. The lookup
reuses `augment_clusters` with a one-member cluster and threshold 1: the
eligibility rules, the uncached count and the failure statuses are the same
code as for topic clusters.

**A failed seed lookup is its own abort.** If the lookup fails (Kado error or
budget refusal), the run stops with "seed lookup failed" — never "fewer than 3
notes". The second message would tell the user the hub has no links when we
simply could not ask, and they would stop looking (F5-AC5). This is the only
place a Kado failure ends a run without a document: without the lookup there
is nothing to propose.

**Three notes minimum.** Fewer than 2 eligible neighbours → no proposal, reason
"fewer than 3 notes" (owner decision 2026-10-27: same floor as `min_notes`).

**Title, parents, confidence.** The title is the seed stem plus the profile MOC
suffix (`profile_conventions.moc_suffix`, applied once) — the seed names the
hub, a Title-Cased topic would rename the user's note. Parent options come
from Phase 5 run on the seed's cached topics; the seed stem is not a keyword,
or a note called "Energy" would score against a Dewey "energy" category by
its name alone. Confidence follows the topic formula (topic members /
candidates), which is 1.0 for the single seed; nothing ranks it against other
proposals.

The report keeps `confidence: 1.0`; the reducer does not render it for `around:`
sections (owner decision B, see suggestions-reducer.md).

**Single pass, no squelch, no Phase 2/3/6/D3.** There is no topic extraction
to hand to the agent, so `--emit-phase1` / `--phase1-input` have nothing to
carry; combining either (or `--check-moc-uplinks`) with `--around` is a fatal
usage error (exit 2) rather than silently running the other flow — the agent
would otherwise wait for a Pass 1 file that never names the seed. The squelch
registry is neither read nor decremented: an `around:` run is an explicit
request for one note, so a past rejection of a topic proposal must not hide
it, and an `around:` run must not age other rejections (owner decision,
2026-10-28). Phase 6 and D3 compare proposals with existing MOCs and with each
other by topic; with one proposal and no topic they have nothing to compare.
Phase 6.5 does run on the seed so its `(up)` annotation is the same as in any
other proposal.

**Report shape.** `around: {kind, path, stem}` is a top-level field, `None` in
`empty_report`, so every report has one shape. Every `around:` abort report
still carries `around` (when resolved) and `link_stats`, so the `Discovery:`
line can show the one attempt.

**The stderr `links:` line is the report's `link_stats`, logged once at the end.**
WHY: the agent reads stderr to write the `Discovery:` line. `around:<MOC>` rewrites
`members_total` to the number of MISSING members after the lookup, so a stat line
logged straight from the lookup said 17 members while the report said 7 (T5.3 live
run). `_around_lookup` therefore logs only status and neighbour count; `_run_around`
logs `links: ` plus every `link_stats` value from the finished report, on success,
`no-missing-members`, `fewer-than-3-notes` and seed-lookup aborts alike. Stderr and
report cannot diverge. Resolve aborts (`around-not-found`, `around-ambiguous`,
`around-periodic`, `around-ineligible`) return before any lookup: they log no
`links:` line and their report carries the zeroed `link_stats` of `empty_report`.

## `around:<MOC>`: The MOC's Missing Members (spec 042 F3, T4.1)

WHY: Notes drift into a topic without ever getting `up::` to its MOC: the
user links them from the MOC body, or they link the MOC, and the parent is
never set. `--around <MOC>` lists those notes so the user can tick them in.

**Rule 1 — a missing member** is a neighbour of the MOC (`neighbors`, either
link direction) that passes member eligibility (`NodeEligibility`) and whose
cached parent does not name this MOC — neither the cached `up_target` nor any
element of the cached `up_value`. The lookup reuses the `around:<note>` path
— `augment_clusters` with the MOC as the one-member cluster and threshold 1 —
so pacing, the 120-attempt budget, the uncached count and "seed lookup failed"
on a Kado error or budget refusal are the same code (ADR-4). A neighbour that
is itself a MOC (the MOC's own parent, a sibling hub) fails eligibility and is
never a member (PRD edge case "parent MOC").

**Why the cached `up_target`, not a read.** The MOC-structure cache already
holds each note's parent, resolved by `up_parse` from inline `up::` *and*
frontmatter `up:`. A frontmatter parent therefore counts as present (PRD edge
case), and the run costs one Kado call however many neighbours the MOC has; a
`read_note` per neighbour would cost one per note, outside the graph budget.

**Why `up_value` too.** `up_parse` keeps ONE parent in `up_target` — the
first inline `up::`, else the first element of a frontmatter `up:` list. A
note with `up: ["[[Other]]", "[[MOC]]"]` is cached `up_target: Other`; read
alone, it would be proposed as missing although it already points at the
MOC. The cache entry also stores the frontmatter value as parsed
(`up_value`, list or scalar; `None` for an inline parent), so every element
of it is checked. The member lookup goes by the neighbour's path into the
cache entries, because `LinkMember` carries only `up_target` and the reducer
consumes that shape unchanged.

**The comparison.** Each candidate is reduced to a bare stem — `[[ ]]`, an
`|alias`, a `#heading`, a folder and `.md` stripped — and compared
case-insensitively, because Obsidian resolves `up::` the same way. A
`up_target` that an older cache persisted as the str repr of the whole
frontmatter list (`"['Other', 'MOC']"`, no `up_value`) is unwrapped
(`unwrap_list_repr`) and every element is checked, not just the first.

**Residual limit — inline parents.** The cache keeps no second inline
parent and does not record a frontmatter `up:` once an inline `up::` won
(`up_value` is then `None`). A note with two inline `up::` lines whose
second names the MOC, or with an inline `up::` to another note plus a
frontmatter `up:` to the MOC, is therefore still proposed as missing. The
user sees it unticked (Rule 5) and leaves it so. The apply side is NOT a
backstop for this: `emit_up_preservation_actions` reads only the FIRST
inline `up::` (frontmatter stripped) and compares it exactly. For a ticked
note whose first inline parent is another note it applies Rule 4.2 — adds
`up:: [[MOC]]` and moves the other parent to `related::` — although the
note already named the MOC. A stale cache (a note parented since the last
explore) behaves the same way: the guard only no-ops when the note's FIRST
inline `up::` is exactly the MOC.

**One missing member suffices** (Rule 4) — there is no 3-note floor: the MOC
already exists, one stray note is worth proposing. **None missing** → no
proposal, `abort_reason: no-missing-members`, message naming the MOC
(F3-AC2), so the user knows the MOC was checked rather than that the lookup
failed.

**Report shape.** `report.extension = {moc_stem, moc_path, members}`, each
member a `LinkMember` with `linked_with: [<moc stem>]` and the cached
`up_state` / `up_target` (Rule 2: the reducer shows the existing parent and
the Override applies at render time). Members are all unticked (Rule 5) —
the ticks live in the doc, so the report carries no tick flag. `topic_clusters`
stays empty: an extension is not a new MOC, has no title, parent or template,
and must not run through Phase 6/D3 or the squelch registry. `link_stats`
reports the one lookup, with `members_total` set to the missing members (not
every eligible neighbour), so the `Discovery:` line counts what is proposed.
`extension` is `None` in `empty_report`, like `around`.

## Phase 6.5 Rows and Link Members Say Why an `up::` Is Broken (spec 042 T5.3d)

WHY: render keeps every existing `up::` (Rule 4.3 retired, see
`docs/tomo/scripts/lib/render_actions.md`), so the doc must say what happens
to it — and for a target that does not exist, that it does not exist, because
the user may have meant to create that MOC (owner decision 2026-10-29).
"Broken" alone cannot tell the two cases apart, so the report now carries the
reason next to the state.

- **Topic members (Phase 6.5).** Each `broken` row gains `reason`:
  `not-a-moc` when the target stem is a non-MOC note among the cache
  `entries`, else `unresolved`. `absent` and `valid` rows keep their
  three keys: no reason applies to them, and the row shape every existing
  consumer and test pins stays unchanged. This
  uses the same classification as `moc-tree-builder.py`, which writes the
  same values into the cache as `up_broken_reason`: both call
  `lib/up_state.classify_up_target` (#216). Until then the rule was mirrored
  here because importing the hyphenated builder pulls in the whole cache
  build; a library module removes that cost and the drift risk of two copies.
  `valid` keeps its own
  test (`_moc_stems_from_cache`, stems and titles), so this change only splits
  `broken` and moves no row between states.
- **Link members, around and extension members.** `LinkMember` carries the
  cache entry's `up_broken_reason`; `_augment_rendered_clusters`,
  `_build_around_note` and `_run_around_extension` copy it into a member
  dict as `up_broken_reason` when the member's `up_state` is `broken`, the
  same rule as for topic rows: the reason is present exactly when the state
  is broken. No read is added: the reason is in the cache entry the member
  already came from.
- **Old reports and old caches.** A row or member without a reason still
  renders; the reducer falls back to the `not-a-moc` wording (see
  `docs/tomo/scripts/suggestions-reducer.md`). A cache that predates spec 033
  has no `up_broken_reason`, so its link members carry `None` and get the same
  fallback.
