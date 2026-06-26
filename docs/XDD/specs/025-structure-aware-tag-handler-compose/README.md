# Specification: 025-structure-aware-tag-handler-compose

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-25 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-06-25 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 24 Gherkin ACs, FR-15…FR-20; 4 open questions deferred to SDD |
| solution.md | completed | 11 ADRs confirmed; helper contract + traced walkthrough + EARS ACs |
| plan/ | completed | 7 phases, 23 tasks, TDD; schema-first hard gate (Phase 1 → 3-6) |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-25 | Spec scaffolded from brainstorm | Source: `docs/XDD/ideas/2026-06-25-structure-aware-tag-handler-compose.md`; extends spec 024-tag-handler-framework (miyo-tomo#47) |
| 2026-06-25 | Hashi dependency treated as AVAILABLE | Hashi `block` anchor + `replace_section` shipped/merged (1238 tests green) before PRD — no in-flight cross-repo blocker; `replace_section` parked Tomo-side (no consumer this spec) |
| 2026-06-25 | v1 scope = all four matrix cells | Hashi shipped → table/list × append/newest-first all unblocked |
| 2026-06-25 | merged granularity reuses cell synthesize directives at batch scope | No separate merge-directive field — smaller schema/test surface |
| 2026-06-25 | Cell→column mapping is positional + count check | Named-column mapping parked; reorder-misfill an accepted, documented v1 limitation |
| 2026-06-25 | PRD completed | 24 Gherkin ACs (FR-15…FR-20); research surfaced producer-chain propagation gap + 3-way-drift + raw-bytes-anchor risks |
| 2026-06-25 | SDD completed; ADR-9/10/11 confirmed | Parse: first matching structure wins; mixed bullets: first-item authoritative (no warn); preview: verbatim rows + mode line |
| 2026-06-25 | PLAN completed; spec Ready | 7 phases / 23 tasks, TDD; Phase 1 (schema) is a hard gate for Phases 3-6 (CON-1 drift); Phase 2 helper parallelizable |
| 2026-06-25 | Implementation complete | Shipped on feat/structure-aware-tag-handler-compose (20 commits, 7 phases, all spec-compliance + code-quality gates passed). Delivers: output_format object + 4 coordinated schemas (block anchor + replace_section mirror); target_structure.py pure helper; tag-handler-compose.py orchestration script (skill→script→lib for ADR-3); producer-chain propagation; interpreter SKILL.md compose; instruction-render block-anchor emission (byte-exact); reducer mode-descriptor + fallback ⚠️; tsukai.json migrated. 1704 tests green, parity + ruff clean. T7.3 host-side validated on real Dev Log bytes; full /inbox live apply deferred with two preconditions (## Captures heading; verify Tsukai emits `created` frontmatter). |

## Context

Structure-aware tag-handler compose: a tag handler can opt in (per handler, via a new `output_format`
object) to making its composed capture conform to the target section's existing structure — emit a
Markdown table row or list item instead of a prose block. Motivating case: Tsukai captures routed to a
`## Captures` table in `Efforts/Tomo Dev Log.md`, newest on top.

Settled brainstorm forks: tables + lists scope; Hybrid mechanism (config intent + mandatory target read);
newest-first ordering (tables use Hashi `block` anchor, lists need no Hashi change); typed-cell config
shape; per-handler granularity flag (`per_item | merged`); warn + prose-fallback on structure mismatch.

Cross-repo: the sole Hashi dependency (multi-line `block` anchor + `replace_section`) is **done/merged**.
Companion Kokoro contract note: `_outbox/for-kokoro/2026-06-25_tomo-to-kokoro_block-anchor-and-replace-section-contract.md`.

---
*This file is managed by the xdd-meta skill.*
