# Specification: 008-deterministic-instruction-render

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-19 |
| **Current Phase** | PLAN |
| **Last Updated** | 2026-04-19 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | skipped | Requirements clear from conversation |
| solution.md | skipped | Design decisions in conversation |
| plan/ | in_progress | |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-19 | Skip PRD/SDD | Well-understood refactoring, all decisions made in conversation |
| 2026-04-19 | instruction-render.py produces both JSON + MD | JSON is source of truth for Seigyo, MD is human-readable view |
| 2026-04-19 | Use parsed-suggestions.json as canonical input | Same JSON the builder already uses — ensures 100% consistency |
| 2026-04-19 | instruction-builder becomes pure orchestrator | No more LLM-assembled markdown — script renders everything |
| 2026-04-19 | Seigyo runs as Obsidian plugin, not in Tomo | Full Obsidian API access (incl. Templater), reads instructions.json directly from vault |

## Context

Currently the instruction-builder (LLM agent) assembles the instruction markdown
by hand from two sources (manifest.json + parsed-suggestions.json). This is fragile
and prevents machine execution.

After this refactoring:
- `instruction-render.py` produces a canonical `instructions.json` containing ALL actions
- `instruction-render.py` also renders `instructions.md` deterministically from that JSON
- The instruction-builder agent only orchestrates (parse → render → kado-write)
- Seigyo (Obsidian plugin) reads `instructions.json` directly — no markdown parsing

---
*This file is managed by the xdd-meta skill.*
