# Specification: 007-pipeline-tokens-and-config-batch

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-19 |
| **Current Phase** | PLAN |
| **Last Updated** | 2026-04-19 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | skipped | Requirements defined in conversation (2026-04-19) |
| solution.md | skipped | Design decisions in conversation (2026-04-19) |
| plan/ | in_progress | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-19 | Skip PRD/SDD | Small feature, requirements + design already clear from conversation |
| 2026-04-19 | Position tokens: after_last_line, at_time:HH:MM, before_first_line | Clear semantics for both human (MVP) and machine (Seigyo) |
| 2026-04-19 | Extend read-config-field.py (not new script) | Reuse existing tool, add --fields + --format json |

## Context

Two improvements from live-run observations:
1. Log entries in instructions need structured position tokens instead of free-text time fields ("end of day" is a position, not a time)
2. Config loading via multiple read-config-field.py calls is wasteful — batch loading saves tool calls and tokens

---
*This file is managed by the xdd-meta skill.*
