# Specification: 005-Daily Note Workflow Extension

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-16 |
| **Current Phase** | Ready to implement (Phase 1) |
| **Last Updated** | 2026-04-16 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | ready | Daily-note-oriented extension of /inbox Pass 1 |
| solution.md | ready | 7 ADRs — all confirmed in the 2026-04-15 + 2026-04-16 design sessions |
| plan/ | ready | 5 phases: schema+config → shared-ctx+wizard → subagent → reducer → validation |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-15 | Three evaluation dimensions per inbox item: tracker match, log-entry candidate, log-link candidate | Matches Marcus's mental model for /inbox; one subagent call covers all three |
| 2026-04-15 | `log_entry` vs `log_link` driven by `atomic_note_worthiness` | If the item also produces an atomic note → log_link; else log_entry inline |
| 2026-04-15 | Polymorphic `updates[]` inside existing `update_daily` action | Avoids proliferating top-level action kinds; Pass-2 handler stays one |
| 2026-04-16 | Multi-daily targeting only when content reads as log-format (date-prefixed lines) | Avoids misreading date mentions in prose; default single-entry most-recent-date |
| 2026-04-16 | Cutoff default 30 days | Marcus currently has year-old items; cutoff keeps daily-note actions bounded to realistic recency |
| 2026-04-16 | Daily-note-create surfaced as checkbox only; actual create by external plugin | Tomo proposes; user's Obsidian plugin executes. Matches MVP boundary |
| 2026-04-16 | Wizard-managed tracker descriptions + daily-log config via `/tomo-setup` | Sub-wizards when volume grows. Skill naming: `tomo-*` prefix |

## Context

Extends Spec 004 (fan-out refactor). The per-item subagent keeps its single
Kado-read; its classification evaluates three additional dimensions:

1. **Tracker match** — item content updates a tracker field in the relevant
   daily note (e.g. `Sport:: true`).
2. **Log entry** — item content belongs INSIDE the daily note body, under
   `# Daily Log`, as a short inline entry.
3. **Log link** — item remains standalone (atomic note) and the daily note
   gets a wikilink under `# Daily Log`.

Tracker + (log_entry OR log_link) can coexist. log_entry + log_link are
mutually exclusive for the same content.

Two new config concepts live in `vault-config.yaml`:

- **Tracker semantics** — per tracker field: `description`,
  `positive_keywords`, `negative_keywords`.
- **Daily-log config** — `section`, `heading_level`, `time_extraction`
  source priority, `cutoff_days`, `auto_create_if_missing` flags.

Both edited via a `/tomo-setup` sub-wizard rather than hand-YAML.

---
*This file is managed by the xdd-meta skill.*
