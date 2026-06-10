# Phase 7 — Design Notes (WIP, pre-spec)

> Working scratchpad while we discuss. NOT the spec yet. Captures decided items
> + open questions so nothing is lost. Promote to Feature 8 / ADR-13 / phase-7.md
> once the open questions (esp. the proposal-doc overlap) are settled.

## Status: DISCUSSION — do not implement the orphan-apply path until the
## proposal-doc problems (section C) are resolved. MOC exclude-tag work (section B)
## is approved-in-principle.

## A. Decided (2026-06-07)

- **Scope:** Phase 7 inside spec 021, spec-first, BEFORE finalize. (021 stays open
  — Feature 3 / ADR-7 orphan link-or-create is e2e non-functional, see C.)
- **create_new naming:** the moc-architect **agent** proposes the new MOC's name +
  topic (like `phase4_title` for clusters), rendered into the doc. (NOT deterministic.)
- **`MiYo/Tomo/exclude/moc` = audit-only:** a MOC carrying this tag is NOT flagged
  as an orphan MOC in `check:moc-uplinks`, but STAYS in the cache as a link target.
  → filter lives in the **orphan pass** (`emit_orphan_suggestions`), NOT in
  `moc_scan` discovery (which would remove it from the cache/link-pool entirely).
- **Root-MOCs** (`000 Index` etc.): excluded from the audit via the **`exclude/moc`
  tag** (user tags them explicitly) — NO root-path heuristic.
- **`MiYo/Tomo/exclude/note`:** a note carrying this tag is NEVER flagged as an
  orphan (covers notes that legitimately have no `up::`, e.g. Dataview-collected).
- **Tag namespace:** `MiYo/Tomo/exclude/moc` + `MiYo/Tomo/exclude/note` (hardwired,
  not user-configurable).
- Dependency: cache entries must carry `tags` for the exclude filters to work —
  verify the builder populates `tags` (cache dump showed `tags: []`).

## B. MOC exclude-tag work (approved to implement)

- `MiYo/Tomo/exclude/moc` → skip in `emit_orphan_suggestions(kinds=("moc",))` (audit
  only; keep in cache + link-candidate pool).
- `MiYo/Tomo/exclude/note` → skip in the note orphan source (`_handle_scan` +
  `emit_orphan_suggestions(kinds=("note",))`).
- Both read the entry's `tags` from the cache → builder must populate `tags`.
- TDD; hardwired tag constants.

## C. Proposal-doc problems found in 2026-06-07_0850 doc (OPEN — discuss)

Observations (user, on review):
1. **MOC01: many notes listed DOUBLED** within the same cluster section. Why?
2. **MOC02: a note (e.g. "Affection") appears in the cluster AND later as an Orphan.**
   Many notes do this.
3. **Not all notes linked in the new MOCs appear in the Orphan list** (and vice
   versa) — inconsistent membership between the cluster sections and the orphan
   section.

CONFIRMED against doc `2026-06-07_0850_moc-proposal-quote-moc.md` (5 clusters, 50 orphans):

- **P1 — within-cluster duplicates (a real bug).** MOC01 "(Quote) (MOC)" `#### Children (71)`
  lists 71 links but only **62 unique → 9 notes listed twice** (other clusters have 0 dupes).
  The header count (71) matches the inflated list, so the cluster's `candidate_stems`
  itself carries duplicates → `candidate_stems`/cluster-item collection is not deduped
  on this path (likely a quote note matching the topic via two facets). Bug to fix.

- **P2 — cluster ∩ orphan overlap (architectural).** **22 notes appear in BOTH a
  proposed cluster AND the `### Oxx` orphan section** (Affection, Empathy, Commitment,
  Financial Stability, …). Both the cluster path (`### MOCxx`) and the case-(a) orphan
  path (`### Oxx`) consume the SAME orphan set (notes with `up_state==absent`) with NO
  dedup between them. ADR-11 accepted the overlap ("no dedup required") — in practice
  it double-lists notes confusingly.

- **P3 — asymmetry from the cap.** 5 clusters hold ~227 link-slots; the orphan section
  is capped at 50. So most clustered notes never appear in the orphan list, and the 50
  orphans are mostly *un*-clustered singletons + the 22 overlaps. "Not all MOC-linked
  notes show as orphans" = expected given cap + independent selection, but reads as
  inconsistent.

Open design question (PIVOT): the scan currently produces TWO overlapping views of the
same orphan set — cluster→new-MOC (`### MOCxx`) and per-orphan link-or-create
(`### Oxx`). They must be reconciled so each homeless note appears in exactly ONE place.
Candidate resolutions:
- **A. Orphans = un-clustered remainder.** Clusters first; the orphan section lists only
  notes NOT in any proposed cluster (and not auto-linkable). Single placement. (likely best)
- **B. Scan = orphans only.** Drop cluster→new-MOC from scan; new-MOC proposals come only
  from scoped runs. Scan becomes pure "link homeless notes / flag the rest".
- **C. Scan = clusters only.** Drop the per-orphan section in scan (pre-ADR-7 behaviour);
  lose link-to-existing in scan.
Plus P1 (dedup candidate_stems) is a straight bug fix regardless of A/B/C.

## D. REVISED DIRECTION (decided 2026-06-07)

Resolution of the C pivot — NOT option A. The user's call:

- **D1. Drop the `### Oxx` orphan section from `/moc-propose` entirely** (Option C).
  `/moc-propose` = cluster→new-MOC ONLY. The note-orphan link-or-create section is
  removed from the cluster proposal-doc. (The orphan-section renderer stays, but is
  used ONLY by `check:moc-uplinks` for MOC orphans.)
- **D2. Note-orphan handling → a FUTURE separate "Orphan Scan"** (framing TBD —
  housekeeping / gardening). Rationale: a note without `up::` does NOT automatically
  warrant a MOC — worst case one MOC per note just to silence moc-propose. MOCs are
  for groups of notes sharing a topic. So per-orphan `create_new` is dropped;
  the future Orphan Scan is primarily link-to-existing + flag, designed separately.
  → orphan-apply wiring (parser reads `### Oxx`) and create_new agent-naming are
  DEFERRED to that future feature (create_new-for-orphans effectively deprecated).
- **D3. Inter-cluster member-overlap dedup (NEW, this phase).** When two proposed
  clusters share members beyond a threshold, DROP the smaller (keep the larger).
  Confirmed need: MOC05⊆MOC02 (100%), MOC04 97%⊆MOC03. Current `phase6_dedupe` only
  compares cluster TOPICS vs EXISTING MOCs — add a members-based pass over the
  PROPOSED clusters. Threshold: OPEN (pure subset only vs ≥X% of the smaller's
  members; MOC04 is 97% not 100%, so a ≥~80–90% overlap rule beats exact-subset).
- **D4. P1 within-cluster dedup (bug).** Dedup `candidate_stems` per cluster (MOC01
  had 9 dupes). Straight fix.

## Phase 7 scope (this iteration) — LOCKED 2026-06-07
1. **D1** — drop the `### Oxx` orphan section from the cluster proposal-doc; the
   orphan-section renderer is used ONLY by `check:moc-uplinks`.
2. **D3** — inter-cluster member-overlap dedup: drop the smaller proposed cluster
   when **≥80% of its members** are also in a larger proposed cluster. (Catches
   MOC05⊆MOC02 100% + MOC04 97%⊆MOC03.) New members-based pass over the proposed
   clusters (current phase6_dedupe = topics-vs-existing only).
3. **D4** — dedup `candidate_stems` within a cluster (MOC01 had 9 dupes).
4. **B (moc)** — `MiYo/Tomo/exclude/moc` = audit-only: skip in
   `emit_orphan_suggestions(kinds=("moc",))` (check:moc-uplinks); MOC stays in cache +
   link-pool. Root-MOCs (`000 Index` etc.) get the tag (user-applied), no heuristic.
5. **B (note)** — `MiYo/Tomo/exclude/note` IMPLEMENT NOW: filter at the scan candidate
   source (`_handle_scan`, cache-based where tags are available) so an excluded note
   is NOT clustered into a proposed MOC (and, later, not orphan-flagged). Real effect
   in Phase 7: keeps Dataview-collected / deliberately-parentless notes out of MOC
   proposals. (Scoped live runs: tag-filter deferred — user scoped deliberately.)
6. **Dependency** — builder must populate entry `tags` in the cache (dump showed
   `tags: []`); both exclude filters read `tags`.

`check:moc-uplinks` STAYS (it was always MOC-only, not notes); exclude/moc + root-MOC
tagging target it.

DEFERRED → **GH #30 (F-44) Knowledge-garden audit skill** (the "Orphan Scan" is
garden-audit, roadmap-obsidian-power.md Track 2 — interactive housekeeping/gardening:
detect orphans → propose review + filing). Deferred items documented as a comment on
#30 (2026-06-07): note-orphan link-or-create + apply-wiring, create_new agent-naming
(deprecated — a no-up note doesn't warrant a MOC), `exclude/note` honoring, reuse of
the 021 cache + `lib/up_parse` + `lib/orphan_link`. NOT a new feature — folds into #30.

## ALL OPEN ITEMS RESOLVED → ready to write Feature 8 / ADR-13 / phase-7.md.
