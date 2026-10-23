# Specification: 040-relevant-mocs-per-item

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-23 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-10-23 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 6 Must, 2 Should, 1 Could; 30 acceptance criteria |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-23 | Structural fix (issue #173 option 3) chosen over raising the budget or graded trimming | Owner decision. The shared-ctx budget is multiplied by item count because every Phase-B subagent reads every MOC; only per-item MOC selection removes the scaling limit instead of moving it. |
| 2026-10-23 | Research mode: Agent Team (technical, matching, performance, integration) | Owner choice. |
| 2026-10-23 | Shape: slim all-MOC index for every item + full inventory fetched only for the MOCs the analyst nominates; no Phase-A lexical pre-filter | Research replay over 105 analyst transcripts: 25 of 52 thematic picks had zero lexical overlap; top-K recall flat at 0.50 for K=3..30. The picks are explained by MOC titles. kado-graph rejected as the basis (single-note link walk, no content/tag query, fresh items carry no links). |
| 2026-10-23 | Index entry = title only; when titles collide, the entries outside the configured MOC folder carry their path | Owner decision. In LYT/MiYo vaults ~99% of MOCs live in one folder, so titles are almost always unique; the fallback keeps identity unambiguous at ~18 B/MOC instead of ~74 B. |
| 2026-10-23 | Duplicate-MOC guard: analyst imperative (check proposed topic against the index before needs_new_moc) + deterministic reducer backstop (normalised proposed topic vs existing titles) | Owner decision. Today nothing downstream checks proposed MOCs against existing ones; a missed match becomes a duplicate "Proposed MOC". |
| 2026-10-23 | In scope: slim `placeholder_links` (unique targets only); MOCs tagged `MiYo/Tomo/exclude/moc` leave the inbox link-candidate pool. Out of scope: Hashi picker handoff, kado-graph signal (stays in #82) | Owner decision. The exclude filter **supersedes spec 021 ADR-13 B-moc** ("the MOC STAYS in the cache + link-candidate pool") for inbox link candidates; the audit-only skip in /moc-propose is unchanged. |
| 2026-10-23 | PRD approved; transition to SDD | Owner approval. |
| 2026-10-23 | Quality bar: before/after live run on the same inbox in tomo-instance, comparing candidate sets and Phase-B cost | Owner decision. Measures agreement with today's LLM picks, not ground-truth correctness. |

## Context

GitHub issue #173: `shared-ctx.json` carries a 40 KB budget. `enforce_budget` in `tomo/scripts/shared-ctx-builder.py` sheds MOC inventory when it is exceeded — all `headings` are gone at ~96 MOCs, and at ~216 MOCs the file is emitted over budget. `mocs[]` is ~77% of the payload and is read by every Phase-B subagent, so its bytes are paid once per inbox item. This spec makes the conductor select the relevant MOCs per item so Phase-B subagents no longer receive the full MOC inventory.

---
*This file is managed by the xdd-meta skill.*
