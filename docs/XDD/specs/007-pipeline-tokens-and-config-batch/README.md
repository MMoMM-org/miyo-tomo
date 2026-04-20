# Specification: 007-pipeline-tokens-and-config-batch

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-19 |
| **Current Phase** | Completed |
| **Last Updated** | 2026-04-20 |
| **Shipped** | 2026-04-19 (commit `90526f8 merge: feat/pipeline-tokens-and-config-batch (XDD 007)`) |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | skipped | Requirements defined in conversation (2026-04-19) |
| solution.md | skipped | Design decisions in conversation (2026-04-19) |
| plan/ | skipped | Implementation went direct conversation → code; no formal phase plan written. See Completion Summary below. |

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

## Completion Summary (2026-04-20 status sync)

Shipped via `feat/pipeline-tokens-and-config-batch` branch, merged 2026-04-19 (`90526f8`).

**What landed**:
- `scripts/read-config-field.py` v0.2.0:
  - `--fields <a,b,c>` for batch reads (one tool call instead of N)
  - `--format json` output mode for structured consumers
  - Backward-compatible `--field` still works
- Position tokens introduced for log entries: `after_last_line`, `at_time:HH:MM`, `before_first_line`
  — used in `instruction-render.py` and `suggestions-render.py` outputs
- Agents updated to consume batched config (fewer tool calls per Pass)

**Plan formalism skipped**: Feature was small enough to go from conversation
to code directly. No `plan/phase-N.md` files were ever written. Recorded
here in retrospect to avoid future "is this done?" confusion.

---
*This file is managed by the xdd-meta skill.*
