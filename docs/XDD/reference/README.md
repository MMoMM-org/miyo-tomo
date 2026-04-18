# Architecture Reference

These are Tomo's architecture specifications, organized in a 3-tier hierarchy:

- **Tier 1** — Framework: Overarching architecture, principles, and constraints
- **Tier 2** — Components & Workflows: Data structures and process definitions
- **Tier 3** — Details: Implementable units with algorithms and schemas

## Authority Model

**Kokoro** (`~/Kouzou/projects/miyo/`) is the architectural authority. These docs originated from Kokoro's architecture decisions and were migrated to Tomo's `docs/XDD/reference/` during spec consolidation (XDD-006, 2026-04-18).

Where Tomo's implementation deviates from the original architecture, inline deviation callouts are included:

> **Warning Deviation (XDD-NNN)**
> **Original**: what the spec described
> **Actual**: what was implemented
> **Reason**: why the deviation occurred
> **See**: link to the XDD spec

## Key Deviations

- **Inbox Processing** (XDD-004): Fan-out refactor — monolithic agent model replaced with orchestrator + per-item subagents
- **Daily Note** (XDD-005): Tracker extension — 3 classification dimensions, polymorphic updates, sub-wizards

## Migration History

Migrated from `docs/specs/` on 2026-04-18 as part of XDD-006 (Spec Consolidation). All 38 specs moved with `git mv` to preserve history. Status markers updated from "Draft" to "Implemented" (or "Implemented with deviations" where applicable).
