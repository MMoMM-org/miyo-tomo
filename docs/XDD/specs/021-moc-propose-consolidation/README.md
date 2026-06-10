# Specification: 021-moc-propose-consolidation

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-05 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-06-09 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Gherkin ACs across 8 Must-Have features + 2 Privacy EARS; F6/F7/F8 added post-live-validation 2026-06-06/07 |
| solution.md | completed | ADR-1…13; schema Option A; lib/ extraction; per-item shaping → issue #45 (epic #24) |
| plan/ | completed | 7 phases all done; T4.3/T4.4 + T7.6 live-validated 2026-06-09 |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-05 | Supersede F-34 inbox-path Condition B (spec 015); consolidate vault-wide MOC discovery into `/moc-propose` | Live validation proved Condition B never fires: the accumulation_index is trimmed to 0 by the 15KB shared-ctx budget. Vault-wide MOC discovery already exists in `/moc-propose` (scan mode + Phase 6.5); F-34 duplicated it on the inbox hot path. |
| 2026-06-05 | Rebuild `moc-tree-builder.py` into the builder of a NEW scoped, timed (TTL 1 day) `moc-structure-cache` | Avoids a full live Kado pull per `/moc-propose` run; `cache-builder` already has a `last_scan` ISO timestamp to base TTL on. Discovery becomes tag-primary (`#type/others/moc`), fixing the 224 false-positive placeholders (notes-area MOCs missed by path-only discovery). |
| 2026-06-05 | Retire Condition B (accumulation) from inbox; KEEP Condition A and KEEP Condition C (placeholder nudge) fully in `/inbox` | Marcus: the placeholder nudge is the value — offer not-yet-existing MOC links for new inbox items, then create the MOC. Condition C now fed by the corrected lean placeholder list. |
| 2026-06-05 | `/moc-propose` keeps Phase 1–6 logic; changes are data-source + up-detection + case (a) | Logic works and serves its purpose. Fix Phase 6.5 to read frontmatter `up:` AND inline `up::` (vault uses both); add orphan→suggest-link-to-existing-MOC for notes AND MOCs; incorporate newer Kado features (operation='tags'/'frontmatter', listDir depth/type/childCount). |
| 2026-06-05 | Add standalone Must-Have Feature 5: inbox Condition A scores against the complete tag-discovered MOC set | User caught that the path-primary discovery (older than F-34) also starved `/inbox`: Condition A only ever matched new items against the ~89 MOC-folder maps, never notes-area MOCs, since `shared_ctx.mocs` derives from the same `map_notes`. Tag-primary discovery (Feature 1) fixes it automatically, but it gets its own ACs + metric M8 so the inbox gain is verified, not incidental. |
| 2026-06-05 | ADR-1 cache schema = Option A (entries[]+kind+loader shim); ADR-2 inline `up::` wins; ADR-3 explore force-rebuild / propose rebuild-if-stale; ADR-4 raise budget to 40KB | SDD-phase user confirmations. Schema A minimises blast radius on the 1929-LOC moc-discovery; inline-wins is the user's precedence call; explore pre-warms while propose stays fast; budget raise unblocks essential placeholder. |
| 2026-06-05 | Per-item context shaping deferred to follow-up spec (issue #45 (epic #24)); 021 = budget-raise only | Shaping is the real per-subagent cost lever but is correctness-sensitive (inclusive pre-filter must not drop true matches); folding it into a 5-feature consolidation spec risks scope-bloat. 021 raises the budget (prompt-cache-softened) as the interim. |
| 2026-06-06 | Add Feature 6 + ADR-11 after live validation: whole-vault `scan` = cache-sourced **orphans** (`up_state==absent`), scoped runs see ALL notes, `candidate_cap` 200→500, Phase-2 topic-index over note entries | Live `/moc-propose` aborted `candidate-cap-exceeded` (209 atomic notes > 200) because Phase 1 counted every note incl. the 70 already MOC-linked — the cap measured vault size, not "notes needing a MOC", so any mature vault tripped it. Cache already carries `kind==note` entries with `up_state`+`topics` (verified: 206 orphans on the real vault), so the fix is cache-sourced + free of live pull / LLM topic extraction. Folded into 021 rather than shipping a restricted feature. User-confirmed: scan=orphans default, all-notes for scoped, cap raised (Option 2). |
| 2026-06-07 | Add Feature 8 + ADR-13 after proposal-doc review: proposal coherence — drop the per-note orphan section from `/moc-propose` (cluster→new-MOC only), inter-cluster member-overlap dedup (≥80% → drop smaller), dedup `candidate_stems`, `MiYo/Tomo/exclude/{moc,note}` tags | Live doc showed within-cluster dupes (P1), 22 notes double-listed in cluster+orphan sections (P2, two paths over the same orphan set), and near-identical clusters surviving (P4: MOC05⊆MOC02, MOC04 97%⊆MOC03 — dedup was topics-vs-existing only). A no-`up::` note doesn't warrant a MOC → interactive note-orphan handling deferred to Garden-Audit #30 (reuses 021 cache + up_parse + orphan_link). exclude/moc = audit-only (stays link target); exclude/note filters scan candidates. User-confirmed: drop orphan section, ≥80% dedup, exclude tags, orphan flow → #30. |
| 2026-06-06 | Add Feature 7 + ADR-12 after live validation: scan output-quality cleanup — default orphan pass = `kind=="note"` only, bounded link-first output (`orphan_display_cap` default 50 + overflow footer), `/moc-propose check:moc-uplinks` for on-demand MOC-parentage audit, `X/` template-vault excluded via config | Live scan emitted 251 orphan suggestions (206 notes + 45 MOCs). Investigation (Kado 50-note sample) proved the 206 notes are REAL orphans (empty `up::` placeholders + notes with no `up`); `lib/up_parse` is correct → NOT changed. The noise was the 45 MOCs (17 `X/` template-vault, 17 Efforts, 6 root maps that correctly have no parent), all from the uncapped notes-AND-MOCs orphan pass. Fix = output shaping: kind-filter default + cap + on-demand `check:` mode; `X/` exclusion via `exclude_paths` (exclude-wins-over-tag mechanism already exists — config not script). User-confirmed: hard cap link-first, `check:` prefix, X/ in config, keep tag-discovery broad (root/Dewey MOCs stay as link targets). |
| 2026-06-09 | Implementation complete | Branch `feat/f-34-msp-condition-b-accumulation`. Condition B (accumulation) retired; A+C kept with corrected placeholder list. Placeholder links 397→196 detection / 38 MOC-named Condition C feed (date-shaped + 224 false positives removed); shared-ctx envelope 54.5KB→35.7KB; whole-vault `/moc-propose` scan from cache (no abort); F8 `exclude/moc`+`exclude/note` live-validated (28→27 / 206→205); `placeholder.build`/`moc-cache.build` telemetry added. Version bumps: placeholder_detect 0.2.0, moc-tree-builder 0.5.0, shared-ctx-builder 1.4.0, inbox-triage 0.8.0, moc_tags 1.0.1. Full suite 924 passed (8 pre-existing ide_bridge/spec-019 failures only). Follow-ups: #45 (per-item shaping, deferred), #50 (inline exclude tags). (#49 MOC-naming was filed then closed not-a-bug 2026-06-10 — created names use the normalized `name` field which applies the convention.) |
| 2026-06-05 | Spec revised after a 5-agent spec-review (REQUEST CHANGES → all findings fixed) | Caught 2 Critical + 7 High design holes at the seams: (C1) dual-up parser changed to `parse_up_from_content(raw)` — splits frontmatter locally from the single read_note (no extra Kado call); (C2) CacheEntry carries classification/linked_notes so cache-builder's classifications don't silently empty; (H1) accumulation retirement scope expanded to vault-summary/vault-explorer/shared-ctx.schema.json/tomo.accumulation config/help+skill prose/test_shared_ctx_accumulation; (H2/H3) case-(a) reframed as a separate orphan pass over cache entries[up_state==absent], NOT a Phase-6 edit and NOT relaxing restrict_to_atomic_note_paths; (H4) added Kado-denial RED test task; (H5) fixed lib component names; (H6) added F4#2 Condition-C-casing test. Plus MEDIUM/LOW: up_state vocab (parse returns target/source only, caller sets state), cache-source wiring, placeholder math reconciled (224 false-positive / 173 genuine → ~171), edge cases (concurrency, placeholder+orphan, exclude-vs-scope), frontmatter-up premise noted, atomic_note scalar/dict, golden-baseline task T3.0, AC count 26→22, kado_client v0.8.0. |

## Context

Supersedes the open threads in `015-msp-condition-b-accumulation/analysis-2026-06-05_msp-viability.md`.
That analysis' central hypothesis ("placeholder over-detection from block-ref anchors is the highest-leverage fix")
was disproven by live data on the real vault (Kado reports 5393 notes, mostly daily):

- Of 397 `placeholder_mocs`: 37 anchored block-refs, **224 false positives** (target note exists but isn't a
  discovered MOC), 173 genuinely missing. Root cause: `moc-tree-builder.detect_placeholders` builds
  `all_vault_paths` from **only the 89 discovered MOC paths**, never the real vault.
- Fixing detection alone is insufficient to revive Condition B (54KB → ~36KB envelope, still > 15KB budget).
- `up` exists in TWO forms: frontmatter `up:` YAML list AND inline `up::`; Phase 6.5 only checks inline.
- `#type/others/moc` verified reliable on real MOCs (5/5 Atlas/Efforts) → enables tag-primary discovery.

Interim work already on branch `feat/f-34-msp-condition-b-accumulation` (keep): `moc-tree-builder.py` v0.3.0
(anchor-strip + per-note dedup in `detect_placeholders`) + `tests/test_moc_tree_placeholders.py` (10 tests).

Open sub-question for SDD: with accumulation gone + placeholder corrected, the inbox shared-ctx is ~36KB
(still > 15KB A4 budget). Decide raise-budget vs per-item context shaping for placeholder + mocs.

---
*This file is managed by the xdd-meta skill.*
