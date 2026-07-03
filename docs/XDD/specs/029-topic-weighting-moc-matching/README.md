# Specification: 029-topic-weighting-moc-matching

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-07-03 |
| **Current Phase** | Ready |
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
