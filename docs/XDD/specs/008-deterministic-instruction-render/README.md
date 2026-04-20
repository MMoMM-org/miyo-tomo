# Specification: 008-deterministic-instruction-render

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-19 |
| **Current Phase** | PLAN — implementation pending |
| **Last Updated** | 2026-04-20 |

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

## Implementation Status (2026-04-20 status sync)

**Already shipped (precursor work, NOT this spec)**:
- `scripts/instruction-render.py` exists and renders **note files** from
  templates (commit `c928206 feat(pipeline): deterministic note rendering via instruction-render.py`,
  pre-dating this spec by several days). Captured in memory `project_pass2_pipeline_2026-04-17.md`.

**Pending — the actual XDD 008 deliverables**:
- T1.1 — Build unified `actions[]` list from manifest + parsed-suggestions sources
- T1.2 — Define `tomo/schemas/instructions.schema.json` (does NOT yet exist)
- T1.3 — Write `instructions.json` (NOT yet emitted by `instruction-render.py`)
- T1.4 — Render `instructions.md` from JSON (currently the LLM agent assembles it)
- T1.5 — Config loading via batch `--fields` (XDD 007 shipped the `--fields` flag;
  consumption in `instruction-render.py` may be partial)
- Phase 2 — Simplify instruction-builder agent (still LLM-assembled today)
- Phase 3 — Validation

So: "Pass 2 is partly script-driven" (true) ≠ "XDD 008 is done" (false). The
spec expanded the scope after the precursor; the JSON-as-source-of-truth + MD-from-JSON
parts are the open work.

---
*This file is managed by the xdd-meta skill.*
