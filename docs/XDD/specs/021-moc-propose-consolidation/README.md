# Specification: 021-moc-propose-consolidation

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-05 |
| **Current Phase** | SDD |
| **Last Updated** | 2026-06-05 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 26 ACs (5 Must-Have features), 7 OQs resolved 2026-06-05 |
| solution.md | completed | ADR-1…10; schema Option A; lib/ extraction; per-item shaping → GH #24 |
| plan/ | pending | |

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
| 2026-06-05 | Per-item context shaping deferred to follow-up spec (GH #24); 021 = budget-raise only | Shaping is the real per-subagent cost lever but is correctness-sensitive (inclusive pre-filter must not drop true matches); folding it into a 5-feature consolidation spec risks scope-bloat. 021 raises the budget (prompt-cache-softened) as the interim. |

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
