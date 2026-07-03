# Specification: 029-topic-weighting-moc-matching

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-07-03 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-07-03 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 4 Must features, Gherkin criteria, MoSCoW complete |
| solution.md | completed | 7 ADRs, interface spec, traced walkthrough, EARS criteria |
| plan/ | completed | 3 phases, TDD tasks; alignment verified (no drift) |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-03 | Spec 029 scaffolded from brainstorm `docs/XDD/ideas/2026-07-03-f05-topic-weighting-moc-matching.md` | F-05, issue #124, epic #17 (P0 MOC Intelligence) |
| 2026-07-03 | Approach B (title-derived weight at match time) | No cache/schema/squelch-signature change; smallest blast radius near MVP. Approaches A (typed topics) and C (config weights) fenced to parking lot. |
| 2026-07-03 | Both match sites in scope: dedupe (Python `_find_jaccard_match`) + item→MOC link (inbox-analyst recipe) | One weighting rule, two substrates. |
| 2026-07-03 | Keep `JACCARD_DUP_THRESHOLD = 0.80`; validate via `analyze-placement-confidence.py` as an in-scope done-criterion | Weighting re-scores; confirm 0.80 still separates before deferring re-tune. |
| 2026-07-03 | PRD approved; continue to SDD | requirements.md completed; 5 parking-lot items tracked (issues #125/#126 + backlog F-05a/b/c). |
| 2026-07-03 | SDD written; 7 ADRs (all confirmed in brainstorm) | New `lib/topic_match.py`; `_find_jaccard_match(+cluster_title)`; analyst Step 4 recipe via agent-author; squelch signature frozen; threshold validated in-scope. No repo CONSTITUTION.md — MiYo constitution aligned inline. |
| 2026-07-03 | PLAN written; spec Ready | 3 phases (core scorer → both-site integration [parallel] → validation & tuning). Alignment check: all code refs match current source, no drift. |
| 2026-07-03 | /validate pass (4 perspectives); HIGH+MED+LOW fixes applied | Fixed non-discriminating tests (now assert flat≥0.80 ∧ weighted<0.80 so a flat no-op fails); added threshold-crossing worked example; reworked T3.1 (analyze-placement-confidence.py measures tier-1 heading fit, NOT dedupe — measure dedupe pairs directly, quantified criterion); fixed dangling ref; unified title-derived terminology; +5 LOW cleanups. Alignment confirmed Site 2 feasible (per-MOC title in shared_ctx.mocs). |
| 2026-07-03 | **T3.1: KEEP `JACCARD_DUP_THRESHOLD = 0.80`** — separation confirmed on real vault, no re-tune | Measured `weighted_overlap` over all 1953 pairs of the 63 existing MOCs in the discovery cache (all legitimately distinct → incidental class). **max incidental weighted = 0.286** (max flat = 0.400); zero pairs reach 0.80. True-dup floor ≥ 0.80 is unit-test-proven (`test_true_dup_title_agreement_survives` = 0.833; identical = 1.0). Criterion `max(incidental) 0.286 < 0.80 ≤ min(true-dup)` holds with wide margin. Caveat: this cache has no MOC×MOC flat-misfire pair (max flat 0.40), so the misfire *fix* is demonstrated by unit tests (traced walkthrough 2) + the live run, not this sample. |
| 2026-07-03 | **T3.2: live `/inbox` Pass-1 confirms the fix** — misfire fixed, no regression, no dedupe/squelch churn | Two targeted notes placed in `100 Inbox/`. **"Idea Emergence Reflections"** (content overlaps Systems (MOC) heavily, but title theme = Idea Emergence) ranked **Idea Emergence (MOC) 0.50 selected** over **Systems (MOC) 0.27** — under old flat scoring Systems would have led (0.263 vs 0.188), so the weighting flipped the ranking correctly. Control note ranked My PKM (MOC) (title "Best practices" hit, fit 1.0) — sensible, no regression. Proposed MOCs: 0; no duplicate/squelch signals in run artifacts. Cost impact negligible by design (O(\|topics\|) substring test) — no cost-log delta measured. |
| 2026-07-03 | Implementation complete | F-05 topic weighting shipped on feature/f05-moc-topic-weighting. New lib/topic_match.py (weighted_overlap, Ruzicka Σmin/Σmax, title-derived ×2); Site 1 moc-discovery._find_jaccard_match wired (v0.20.0); Site 2 inbox-analyst.md Option A recipe (v0.21.0) + WHY-doc. 3 new test files (~648 LOC); full suite 2026 passing, ruff clean. Threshold 0.80 kept (T3.1: max incidental 0.286 ≪ 0.80). Live /inbox Pass-1 confirmed misfire fix (Idea Emergence MOC ranked 0.50 over Systems MOC 0.27); no dedupe/squelch churn. Squelch signature byte-identical. Commits 0898032..HEAD. Issue #124, epic #17. |

## Context

Source brainstorm: `docs/XDD/ideas/2026-07-03-f05-topic-weighting-moc-matching.md` (fully validated + spec-reviewed).

GitHub issue #124 (P0-must, area:moc), native sub-issue of epic #17 "MOC Intelligence".

**Goal:** weight title-derived topics above content keywords in MOC matching so title agreement
wins over incidental content overlap. Approach B: `title_derived(t,N) := normalize(t)` is a
substring of `normalize(title_N)`; weighted-overlap scorer (`W_TITLE=2`/`W_BASE=1`). No cache,
schema, or squelch-signature change.

**Parking lot (out of scope):** H3-heading topics; archived-inbox replay fixture; config-driven
weights; standalone threshold re-derivation; typed-topics-at-extraction.

---
*This file is managed by the xdd-meta skill.*
