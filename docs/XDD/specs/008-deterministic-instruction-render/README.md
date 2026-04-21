# Specification: 008-deterministic-instruction-render

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-19 |
| **Current Phase** | COMPLETE — all phases shipped and live-validated 2026-04-21 |
| **Last Updated** | 2026-04-21 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | skipped | Requirements clear from conversation |
| solution.md | skipped | Design decisions in conversation |
| plan/ | complete | Phases 1, 2, 3 shipped and live-validated |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-19 | Skip PRD/SDD | Well-understood refactoring, all decisions made in conversation |
| 2026-04-19 | instruction-render.py produces both JSON + MD | JSON is source of truth for Tomo Hashi, MD is human-readable view |
| 2026-04-19 | Use parsed-suggestions.json as canonical input | Same JSON the builder already uses — ensures 100% consistency |
| 2026-04-19 | instruction-builder becomes pure orchestrator | No more LLM-assembled markdown — script renders everything |
| 2026-04-19 | Tomo Hashi runs as Obsidian plugin, not in Tomo | Full Obsidian API access (incl. Templater), reads instructions.json directly from vault |

## Context

Currently the instruction-builder (LLM agent) assembles the instruction markdown
by hand from two sources (manifest.json + parsed-suggestions.json). This is fragile
and prevents machine execution.

After this refactoring:
- `instruction-render.py` produces a canonical `instructions.json` containing ALL actions
- `instruction-render.py` also renders `instructions.md` deterministically from that JSON
- The instruction-builder agent only orchestrates (parse → render → kado-write)
- Tomo Hashi (Obsidian plugin) reads `instructions.json` directly — no markdown parsing. Consumer contract documented at [`docs/instructions-json.md`](../../../instructions-json.md).

## Implementation Status (2026-04-20 status sync)

**Already shipped (precursor work, NOT this spec)**:
- `scripts/instruction-render.py` exists and renders **note files** from
  templates (commit `c928206 feat(pipeline): deterministic note rendering via instruction-render.py`,
  pre-dating this spec by several days). Captured in memory `project_pass2_pipeline_2026-04-17.md`.

**Shipped 2026-04-21 (commits 8c61983, …):**
- T1.1 — Unified `actions[]` list (8 action kinds, monotonic I01..INN)
- T1.2 — `tomo/schemas/instructions.schema.json` with per-kind required fields,
  `additionalProperties:false`
- T1.3 — `instructions.json` now written to output-dir (and vault via the agent)
- T1.4 — `render_instructions_md()` produces the human view deterministically
  from the JSON; section order: New Files → MOC Links → Daily Updates →
  Source Deletions → Skips
- T1.5 — `load_config()` batch-loads every field the pipeline needs once at
  startup (replaces inline yaml reads scattered through the script)
- T1.6 — `tests/test-008-phase1.py` covers all three function surfaces
  (action building, structural schema conformance, MD rendering)
- Phase 2 — `instruction-builder.md` slimmed to 90 lines (from 188), pure
  orchestrator, model downgraded opus→sonnet
- T3.2 — `scripts/instructions-dryrun.py` validates any instructions.json is
  machine-consumable (every action type parseable with required fields present)
- T3.3 — backlog F-01, roadmap Horizon 4, and `tomo/dot_claude/commands/inbox.md`
  all cross-reference XDD 008

**Live-validated 2026-04-21 against the Privat-Test vault:**
- T3.1 — Full Pass-2 cycle ran end-to-end through the Tomo Docker container +
  Kado against 12 source items. 25 actions reconciled 25/25 via
  `instructions-diff.py`; zero observations after the supporting_items
  expansion landed. `instructions.json` (new schema) and `instructions.md`
  both written to the vault via `kado-write` (markdown via `operation=note`,
  JSON via `operation=file` + `scripts/kado-write-file.py`).

## Follow-ups (out of scope for this spec)

Surfaced during live validation — captured for separate work:

- The vault-explorer agent's remaining free-composed sections
  (`relationships:`, `callouts:`, `trackers:`) carry the same LLM-drift
  risk that was fixed for `tags:` via `scripts/vault-config-writer.py`
  in this spec. Pattern is ready to apply; see memory note
  `project_vault_explorer_writer_refactor.md`.
- `vault-reset.sh archive` treats the Pass-1 suggestions doc as an
  artifact; preserving a still-approved suggestions doc while cleaning
  up Pass-2 output requires a finer pattern (or a `--keep-suggestions`
  flag). Non-blocking; documented for future enhancement.

---
*This file is managed by the xdd-meta skill.*
