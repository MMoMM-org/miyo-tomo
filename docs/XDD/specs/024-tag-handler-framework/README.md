# Specification: 024-tag-handler-framework

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-23 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-06-23 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | in_progress | PRD — design locked in #47 brainstorm |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-23 | Generalize "Tsukai support" into a tag-handler framework | Per-feature declarative handlers (Tsukai = #1); user-extensible. Recorded on #47. |
| 2026-06-23 | Handler = pure data, not a skill | skill-author isn't installed in Tomo; matches Tomo's "logic in skills, config in data" principle. Authored via a wizard. |
| 2026-06-23 | Aggregation: merge per (handler, target note) | LLM composes one logical status update with full batch context, not a per-capture dump. |
| 2026-06-23 | Additive-only on hot paths | Tomo near-MVP; a /inbox run with no registered handlers must be byte-identical to today. |

## Context

Tomo handling for `MiYo/<Feature>`-tagged inbox notes (GitHub issue **#47**, P1-should). A declarative,
user-authored handler framework; **Tsukai** (`MiYo/Tsukai/<repo>`) is handler #1. Full locked design is
recorded as a comment on #47 (2026-06-23 brainstorm) and is the source of truth for PRD/SDD.

Key elements:
- **Handler** = `config/tag-handlers/<feature>.json` (pure data), authored via `tomo-tag-handler-wizard`.
- **Match** = `{tag_prefix, capture_segments[], read_fields[]}`.
- **Actions** (v1, registry-extensible): `insert_under_marker`, `route_to_folder`, `link_to_moc`,
  `enrich_frontmatter` — each = compose (mechanical OR LLM directive) + place.
- **Pipeline hooks**: triage detect → Pass-1 group-by-target + LLM-merge → Pass-2 Hashi insert.
- **Guards**: target missing → "create it first" checkbox; marker missing → error.

---
*This file is managed by the xdd-meta skill.*
