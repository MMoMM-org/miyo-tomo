# XDD 015 — Requirements (PRD)

> **Status:** draft (2026-05-07)
> **Spec ID:** 015
> **Title:** Mental Squeeze Point — Condition B: Accumulation Detection
> **Backlog ref:** F-34 (Must)
> **Related:** F-35 (Condition C, code-complete 2026-05-07, commit `5b3a031`); F-43 (MOC-creation skill — complementary, can land independently)
> **Architecture decision:** option (b) accumulation index pre-computed in shared-ctx pipeline; index shape = `topic → list of stems` (locked 2026-05-07).

## 1. User story

> As a Tomo user processing inbox items, when an inbox item's topics
> match **two or more existing atomic notes in my vault that have no
> `up::` link** (i.e. they sit unclassified outside any MOC), I expect
> Tomo to recognise the accumulation and propose creating a thematic
> MOC to organise them — alongside the new inbox item.
> Today this trigger is silent: the cluster keeps growing, the new item
> goes in next to its siblings, and the user has to notice the pattern
> manually.

## 2. Problem today

- **Spec lives, code does not.** Tier-3 New MOC Proposal §2 defines four
  triggers (Conditions A–D). Today only **A** (Batch Cluster, ≥3 items
  in a single /inbox run) fires end-to-end via
  `tomo/scripts/suggestions-reducer.py`. **B** (vault-side accumulation)
  is unimplemented.
- **Accidental clusters compound.** Without B, related notes accumulate
  silently in the atomic-notes folder. The user discovers them
  retroactively (annual cleanup) instead of at the moment Tomo could
  surface them.
- **C alone is not enough.** F-35 ships Condition C (placeholder MOC
  trigger — wikilinks to non-existent MOCs). C is a *deliberate* signal
  the user already wrote; B is a *latent* signal Tomo discovers. Both
  are needed for the MSP feature to be MVP-complete.
- **Architecture risk.** A naive implementation that calls `kado-search`
  per inbox item (option a, considered and rejected 2026-05-07) would
  amplify Pass-1 cost. Pass-1 already costs ~$26 on Opus main thread per
  /inbox batch (F-32); per-item searches against the vault would compound
  this on every run.

## 3. Goals

- **G1 — Fire Condition B when 2+ unclassified notes share a topic.**
  When the inbox item's topics match a topic-cluster in the vault of
  size ≥ 2 with no `up::` link, the analyst MUST emit
  `needs_new_moc: true` with `proposed_moc_topic = <cluster topic>`.
- **G2 — Pre-compute, don't search per-item.** The accumulation index
  is built once per `/explore-vault` run (cache layer), surfaced once
  per `/inbox` run (shared-ctx layer), and consumed as a dict lookup
  per item (subagent layer). No per-item Kado searches.
- **G3 — Additive on hot paths.** Existing /inbox runs without an
  accumulation index (older caches, missing field) MUST behave
  byte-identically to today's runs. The shared-ctx schema treats
  the new field as optional.
- **G4 — Stay within the 15 KB shared-ctx budget.** The serialised
  accumulation index plus existing fields MUST fit. Strategy: rank
  clusters by size (largest first), drop tail when over budget.
- **G5 — Reuse existing infrastructure where possible.** Topic
  extraction is already deterministic (`tomo/scripts/topic-extract.py`).
  The new scanner reuses it, the way `moc-tree-builder.py` does for MOCs.
- **G6 — Surface cluster identity in suggestions doc.** When Condition B
  fires, the user can tell *which* notes drove the proposal (so they can
  judge whether the proposed MOC matches their mental model). Implementation
  detail (label "accumulation cluster" vs uniform "Proposed MOC") is open.

## 4. Non-goals

- **N1 — Real-time index refresh.** The index is rebuilt at
  `/explore-vault` time, not after every `/inbox` run. Notes added in
  the last batch are not retroactively in the index until the next
  scan. This is a deliberate cost trade.
- **N2 — Topic similarity / fuzzy matching.** First cut uses normalised
  string equality on lowercased, whitespace-collapsed topic strings. Any
  smarter matching (lemmatisation, embedding similarity) is post-MVP.
- **N3 — Cluster annotation by user.** No mechanism to mark a cluster
  as "intentional, do not propose MOC". User declines via the standard
  Approve/Skip suggestion checkbox; persistence of the decline across
  runs is post-MVP.
- **N4 — Walking arbitrary folder paths.** First cut walks atomic notes
  only (configured via `vault-config.concepts.atomic_note.base_path`).
  Other folders (`source`, `area`, `project`) are out of scope; if those
  notes need MOC organisation, they get their own future condition.
- **N5 — Surface the trigger source in instructions.json.** The
  generated `create_atomic_note` action with `needs_new_moc=true` is
  shape-identical regardless of which condition fired. Suggestions doc
  may label it; downstream pipeline does not branch on it.

## 5. Acceptance criteria

**A1 — Index ships in the cache.** After `/explore-vault` runs against
a vault with at least one accumulation cluster (≥2 unclassified atomic
notes sharing a topic), `discovery-cache.yaml` MUST contain a
`unclassified_topic_clusters` field shaped
`{<topic>: [<stem1>, <stem2>, ...]}` with all clusters of size ≥ 2.
Vaults with zero clusters have an empty dict.

**A2 — Shared-ctx surfaces the index.** When the cache contains a
non-empty `unclassified_topic_clusters`, `shared-ctx-builder.py` MUST
emit a top-level `accumulation_index` field in `shared-ctx.json`
matching the cache shape (after size-budget trimming, see A4). When
absent or empty, the field MUST be omitted (additive guarantee).

**A3 — Subagent fires Condition B.** `inbox-analyst` Step 4 MUST scan
`shared_ctx.accumulation_index` (when present). For each item topic
matching an index key (case-insensitive, whitespace-normalised), the
subagent MUST set `needs_new_moc: true` and
`proposed_moc_topic = <index_key>`. Top-scoring thematic candidate
MOCs (if any) remain in `candidate_mocs[]`.

**A4 — Size budget enforced.** `shared-ctx-builder.py` MUST keep the
serialised shared-ctx ≤ `--max-bytes` (default 15 KB). When the
accumulation index pushes the envelope over budget, clusters MUST be
dropped tail-first (smallest clusters first, then alphabetical tiebreak)
until the envelope fits. The stderr log line MUST report
`accumulation_clusters_total=N accumulation_clusters_kept=K`.

**A5 — `up::` detection is reliable.** A note counts as
"unclassified" iff it has no `up::` marker in body, callout body, or
frontmatter (the same three locations `moc-tree-builder.py` scans for
parent links). The scanner MUST honour `vault-config.relationships`
(F-16 marker config) when defined; otherwise fall back to the hardcoded
`up::` literal that `moc-tree-builder.py` already uses.

**A6 — Empty / new vaults degrade gracefully.** A vault with zero
atomic notes, zero unclassified atomic notes, or zero shared-topic
clusters MUST produce an empty index in cache and no
`accumulation_index` field in shared-ctx. /inbox runs against such
vaults MUST be byte-identical to today's pre-F-34 behaviour.

**A7 — Conflict precedence with C.** When both Condition B (this spec)
and Condition C (F-35) fire on the same inbox item, **C wins** —
placeholder name is a deliberate dead link the user already wrote, a
higher-confidence intent signal than a freshly-discovered accumulation.
This is the same precedence already encoded in inbox-analyst Step 4.

**A8 — Tests cover the happy path and the drift guards.** Unit tests
MUST cover: (i) cluster discovery with a mocked atomic-note set,
(ii) `up::` filter, (iii) size-budget trimming when the index would
exceed 15 KB, (iv) per-item lookup hit / miss in the subagent flow
(via shared-ctx fixture). End-to-end smoke test against `Privat-Test/`
MUST produce a Proposed MOC suggestion when a known cluster exists.

**A9 — Documentation.** Tier-3 New MOC Proposal spec MUST be updated to
mark Condition B as implemented and to point at `XDD 015`. Inbox-analyst
agent MUST bump version with a Condition-B note (analogous to F-35's
v0.10.0 bump).

## 6. Out of scope (noted for future work)

- **Cross-condition labelling in suggestions doc.** Whether the user
  sees "Proposed MOC — accumulation cluster" vs uniform "Proposed MOC"
  is left to the SDD/implementation phase. Today they look identical.
- **Cluster-driven section proposals (F-36 link).** When a freshly-
  proposed B-MOC has no sections yet, the user manually creates them on
  first use. F-36 (new section proposal logic) is the natural follow-up.
- **Incremental cache refresh (F-09 link).** Today the index is rebuilt
  on every `/explore-vault`. Delta refresh is post-MVP.
- **Profile-aware exclusions.** Some Dewey ranges (e.g. 2070 Links,
  2820 Quotes) probably should not surface clusters — quotes don't need
  MOCs. First cut treats all atomic notes equally; profile-driven
  exclusions are post-MVP.
- **Pre-Pass-1 user warning.** "Cache is N days stale, X new atomic
  notes since last scan — clusters may be incomplete." Useful, but ties
  to F-21 (cache staleness warning) which has its own backlog entry.

## 7. Success signals

- A live `/inbox` run against `Privat-Test/` (or Marcus's real vault)
  produces a Proposed MOC suggestion for an item that matches a known
  unclassified topic cluster — without the user having intervened.
- Pass-1 cost on Opus main thread does NOT regress vs the F-32 baseline
  (~$26/run today). The new infrastructure adds /explore-vault cost,
  not /inbox cost.
- The MSP feature (Conditions A + B + C) is end-to-end complete: the
  Tier-3 New MOC Proposal spec has zero "missing" entries when audited
  against shipped code.
- Tomo correctly proposes a new "Boardgames" MOC the next time the user
  drops a boardgames note into the inbox, because three such notes
  already accumulated in `Atlas/202 Notes/` without an `up::`.

## 8. Open questions

> **RESOLVED 2026-06-04** (brainstorm; stakeholder Marcus). Authoritative
> resolutions are tabulated in `README.md` → "Open questions — RESOLVED".
> Summary: OQ1 → separate `atomic-note-indexer.py`; OQ2 → **`listNotes`**
> (was `listDir`; superseded by Kado's purpose-built op); OQ3 →
> always-run; OQ4 → string equality; OQ5 → configurable `min_cluster_size`
> **default 3**; OQ6 → **dissolved** (no body reads — structured signals from
> Kado); OQ7 → additive at `cache_version: 1`. The leans below are retained as
> the original reasoning; where a resolution differs from the lean (OQ2:
> `listNotes`; OQ5: 3 not 2; OQ6: dissolved), the README table wins.
> **UNBLOCKED 2026-06-04:** Kado shipped `kado-search operation="listNotes"`
> (`fields=["links","headings","tags"]`); the SDD (`solution.md`) is written
> against that contract. See README "✅ Unblocked" banner + `solution.md`.

- **OQ1 — Where does the scanner live?** Two viable homes:
  (i) extend `moc-tree-builder.py` (already uses `topic-extract.py`,
  already walks Kado, but its job description is "MOC tree" — adding
  atomic-note walks bloats responsibility);
  (ii) new script `atomic-note-indexer.py` invoked from `/explore-vault`
  alongside `moc-tree-builder.py` (cleaner separation, but more
  install/update plumbing).
  **Lean:** (ii) — separation of concerns wins for a feature this
  distinct.

- **OQ2 — How does the scanner discover atomic notes?**
  (a) `kado-search listDir` on `vault-config.concepts.atomic_note.base_path`
  (recursive); (b) walk `cache.vault_structure.concepts_mapped.atomic_note`
  if cache-builder writes per-note paths there. The cache today only
  stores counts and subdirs, not paths. **Lean:** (a) — explicit Kado
  call for the canonical "what notes exist" question; cache stores the
  *result* of the scan.

- **OQ3 — When does the scanner run?** (i) Always on `/explore-vault`
  (adds cost — ~281 kado-reads × ~50ms = ~14s additional per scan);
  (ii) only when `vault-config.tomo.accumulation_detection: true`
  opt-in flag is set. **Lean:** (i) for MVP — single code path, no
  config branching; benchmark first /explore-vault run and reconsider
  if latency is unacceptable.

- **OQ4 — Topic normalisation aggressiveness.** Backlog open question:
  "string equality on normalised topic? substring? semantic?". For
  MVP, **string equality on lowercase + whitespace-collapsed** matches
  the F-35 placeholder-match logic (consistent across conditions) and
  is implementable without new dependencies.

- **OQ5 — Default minimum cluster size.** Spec says "≥ 2 existing
  notes". User Marcus might prefer 3 (less noise). Should this be
  configurable via `vault-config.tomo.accumulation.min_cluster_size`?
  **Lean:** ship 2 as the default (matches spec literal), no config
  knob in MVP — add knob if the first live run produces too many false
  positives.

- **OQ6 — Does the scanner read every atomic note's body, or only
  frontmatter + first heading?** Topic-extract uses title + H2 + tags
  + wikilinks. Reading full body (~1-5KB per note × 281 notes) =
  ~1MB total over Kado. That's tractable but slow. Reading head-only
  (~500 bytes per kado-read) is faster but loses tag-based topics if
  tags are body-positioned. **Lean:** read full body — topic-extract
  results are only as good as the input it sees.

- **OQ7 — Cache schema bump?** `discovery-cache.yaml` has
  `cache_version: 1`. Adding `unclassified_topic_clusters` — bump to
  `2` and drift-guard, or treat as additive at version 1? Per the F-35
  precedent (placeholder_mocs added without version bump), **lean:**
  additive at version 1, missing field = empty dict.

## 9. Constraints

- **C1 — "Additive only on hot paths"** (memory:
  `feedback_near_mvp_no_breakage.md`). New infrastructure goes through
  `/explore-vault` (cold path). Hot paths (inbox-analyst, instruction-
  render, suggestions-reducer, shared-ctx-builder) accept only additive
  changes — guarded by A6 (empty index = today's behaviour).
- **C2 — Kado MCP is the only vault gateway** (constitution L1). The
  scanner uses `kado-read` (and `kado-search` if needed for listDir);
  no direct filesystem access.
- **C3 — Shared-ctx envelope ≤ 15 KB** (existing budget — see
  `shared-ctx-builder.py:enforce_budget`). The accumulation index
  participates in budget trimming (see A4).
- **C4 — Compatible with F-35.** F-35's `placeholder_mocs[]` field
  ships in shared-ctx (PR `5b3a031`). Both fields coexist; precedence
  rule (A7) defines conflict behaviour.
- **C5 — No new dependencies.** Reuse `topic-extract.py` for topics;
  reuse `kado_client` for vault access; reuse `enforce_budget` for
  size capping.
- **C6 — Branch + commit discipline.** Implementation lands on
  `feat/f-34-msp-condition-b-accumulation`; no direct commits to main.

## 10. Definition of done

- All A1–A9 acceptance criteria pass.
- All OQ1–OQ7 open questions are answered in the SDD (014 doesn't have
  to ship until OQs are resolved).
- Tier-3 New MOC Proposal spec marks Condition B as ✅ shipped.
- Backlog F-34 marked code-complete; live-validation result attached.
- Pass-1 token cost regression test (vs F-32 baseline) shows no
  amplification on /inbox runs.

## 11. Validation hooks (for the SDD/PLAN phases)

- Live test against `Privat-Test/` with a known unclassified cluster.
- Live test against Marcus's real vault (the 281-atomic-notes
  corpus) — measures real /explore-vault latency cost.
- Empty-vault test — confirm shared-ctx omits the field.
- 15 KB budget stress — confirm trimming behaves as A4 specifies.
- Conflict-precedence test — item topics match BOTH a placeholder
  (F-35) AND an accumulation cluster — confirm C wins (A7).
