# Specification: 006-spec-consolidation

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-18 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-04-18 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Full consolidation scope: migrate, reconcile, flesh out placeholders, backlog |
| solution.md | completed | Reference folder structure, inline deviations, standalone backlog |
| plan/ | completed | 4 phases, 21 tasks: migrate → reconcile → flesh out → index+backlog+cleanup |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-18 | Spec 006 created | Consolidate docs/specs/ into docs/XDD/, reconcile with implementation, produce open-items backlog |
| 2026-04-18 | Full consolidation chosen | Migrate tier specs into XDD, reconcile with implementation, flesh out placeholders, produce backlog |
| 2026-04-18 | Kokoro stays authoritative | Tomo documents deviations but doesn't modify Kokoro's architecture docs |
| 2026-04-18 | Flesh out placeholders | Reverse-engineer skeletal specs from working code rather than dropping them |
| 2026-04-18 | PRD completed | 5 Must-Have features, 2 Should-Have, 1 Could-Have defined with Gherkin acceptance criteria |
| 2026-04-18 | ADR-1: Reference docs folder | Preserve tier hierarchy under docs/XDD/reference/ |
| 2026-04-18 | ADR-2: Standalone backlog file | docs/XDD/backlog.md with categorized items |
| 2026-04-18 | ADR-3: Inline deviation annotations | Callout blocks within migrated specs, not separate registry |
| 2026-04-18 | SDD completed | 3 ADRs confirmed, 10-step consolidation flow, file format specs defined |
| 2026-04-18 | PLAN completed | 4 phases, 21 tasks: structure+migration → reconciliation → placeholders → index+backlog+cleanup |

## Context

Merge the legacy `docs/specs/` tier-based architecture docs into `docs/XDD/`, reconcile specs with actual implementation state, and produce an actionable open-items backlog. This addresses spec drift accumulated during phases 1-3 of development.

---
*This file is managed by the xdd-meta skill.*
