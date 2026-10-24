# Specification: 040-relevant-mocs-per-item

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-23 |
| **Current Phase** | Implemented |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-10-24 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.2; 6 Must, 2 Should, 1 Could; 30 acceptance criteria |
| solution.md | completed | v1.1; ADR-1…ADR-10 confirmed 2026-10-24; 30 EARS criteria, 1:1 with the PRD |
| plan/ | completed | 6 phases, 20 tasks (7 parallel) |

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
| 2026-10-23 | Quality bar: before/after live run on the same inbox in tomo-instance, comparing candidate sets and Phase-B cost | Owner decision. Measures agreement with today's LLM picks, not ground-truth correctness. |
| 2026-10-23 | PRD approved; transition to SDD | Owner approval. |
| 2026-10-24 | SDD ADR-1…ADR-10 confirmed | Scoring by meaning (confidence 0-1, thresholds kept); duplicate key = proposal-grouping cluster key; an index hit is an ordinary candidate; colliding titles → all paths offered unticked; freshness = delete-before-build + `--run-id` check (context still rebuilt per run from the local discovery cache). |
| 2026-10-24 | Spec validation (completeness/consistency/coverage/constitution/alignment): 6 FAIL, ~30 WARN, all fixed in PRD v1.2, SDD v1.1, plan v1.1 | Key fixes: names file named via `to_filename` (item_key is a path); `placeholder_targets` always written; ≤20 nominations in thread order; any reader failure fails the item via Step 11; old-shape context fails the item; mutator moved to `lib/duplicate_proposals.py` (reducer is 2835 LOC); new transcript scanner (T1.1) for the no-preview KPI; agreement bar = min(90%, before-run variance); guards vs RED assertions separated. |
| 2026-10-24 | Classification MOCs may be nominated and become unticked candidates, as today | Owner decision. Keeps the Classification Guard unchanged. |
| 2026-10-24 | Baseline details (MOC paths/titles) stay out of git; only counts and figures are committed | Owner decision (public repo). Details go to `tomo-instance/spec-040-baseline/` (gitignored). |
| 2026-10-24 | Decomposition tier: Incremental | Classifier recommended Incremental (feature_count=6, rule 1; 30 ACs; at classification time 1 new component lib/moc_folders.py — the validation round later added lib/duplicate_proposals.py and scripts/measure-shared-ctx-reads.py, which only strengthens the recommendation; no parallel markers in the SDD; the plan tags 7 tasks parallel). Accepted. |
| 2026-10-24 | PRD v1.1 amended per ADR-10 | F2-AC5 and the renamed-MOC edge case: an unresolved name is dropped and logged; F4-AC1 and Rule 5 name the cluster key. |

## Context

GitHub issue #173: `shared-ctx.json` carries a 40 KB budget. `enforce_budget` in `tomo/scripts/shared-ctx-builder.py` sheds MOC inventory when it is exceeded — all `headings` are gone at ~96 MOCs, and at ~216 MOCs the file is emitted over budget. `mocs[]` is ~77% of the payload and is read by every Phase-B subagent, so its bytes are paid once per inbox item. This spec gives every item the names of all eligible MOCs and the full placement detail only for the MOCs the analyst nominates, so the inventory is never cut and never read whole.

---
*This file is managed by the xdd-meta skill.*
| 2026-10-24 | After-run agreement KPI missed (67%/60%); a second after-run instead of accepting or re-tuning | Owner decision. The second run missed too (67%/50%), and the after-runs agree with each other less than the before-runs did. |
| 2026-10-24 | Document the agreement miss in the close-out; candidate stability follows up in #200 | Owner decision. Every other KPI met: cache-write −18%, $ −9%, 0 previews, 0 duplicate proposals, seeded item linked. |
| 2026-10-24 | Implementation complete | PR #198, branch `spec/173-relevant-mocs-per-item`. Close-out: 28 criteria traced to 64 node ids run in one invocation (90 passed), 2 by document review; three gaps closed by tests (3db1de3c). Found and filed: #199, #200. |
