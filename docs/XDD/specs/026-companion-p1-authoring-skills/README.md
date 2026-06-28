# Specification: 026-companion-p1-authoring-skills

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-28 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-06-28 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 19 Gherkin ACs; 5 Must-have features; MoSCoW + edge cases + risks. Standard-mode research (Requirements/Technical/Integration). |
| solution.md | completed | 9 ADRs (all confirmed); directory map, runtime flow, EARS ACs, Test Strategy. kado-write-patterns (1 write-side skill), staging tomo-tmp/staged-artifact.<ext>. Constitution L1/L2 fixes folded in. |
| plan/ | completed | 5 phases / 18 tasks, TDD. Phase 1 (deterministic scripts) hard-gates skill work. Parallel: 3 format skills (Phase 2). |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-28 | Spec scaffolded from brainstorm | Source: `docs/XDD/ideas/2026-06-28-companion-p1-authoring-skills.md`; design approved in 2026-06-28 brainstorm (gap-review + spec-reviewer passed). Tracks #91/#92/#93, part of epic #16. |
| 2026-06-28 | Kado `.base`/`.canvas` acceptance VERIFIED | Integration research confirmed against Kado source (`request-mapper.ts` Rule 3 accepts non-`.md` via `operation=file`; `kado-write-file.py` already extension-agnostic). The charter §5 verify-first item is resolved — NO Kado handoff needed. |
| 2026-06-28 | Template mapping uses real schema keys | Technical research: charter's `note`/`moc` were wrong; real `templates.mapping` keys are `atomic_note`, `map_note`, `daily`, `weekly`, `monthly`, `yearly`, `project`, `source` (+ `default-doc-writer`'s `default` convention, not in schema). |
| 2026-06-28 | `.base`/`.canvas` JSON: minimal parse-check in P1 | `json.loads()` gate in inbox-author blocks malformed JSON; structural/semantic validation (Canvas 8-point checklist, Bases cross-refs) deferred to #92 (boundary commented on #92). |
| 2026-06-28 | Inbox collision → warn + ask | Same stem+extension already present: warn the user and ask before overwrite (default-doc-writer overwrote silently — data-loss risk). |
| 2026-06-28 | Unknown type, no vault template → default + note | inbox-author writes with the default/inbox template and tells the user no type-specific template was found (never silently mislabel or refuse). |
| 2026-06-28 | PRD completed | 19 Gherkin ACs; deferred OQ-1/4 (kado-toolkit name+packaging), OQ-3 (.base/.canvas staging path), #91 (templater/dataview need) to SDD. |
| 2026-06-28 | ADR-1: kado-write-patterns (one write-side skill) | Symmetric to read-side kado-discovery-patterns; clean read/write split; research advised against multiple sub-skills. Resolves OQ-1/4. |
| 2026-06-28 | ADR-2: staging tomo-tmp/staged-artifact.<ext> | Consistent with existing tomo-tmp/default-doc.md pattern; deterministic single artifact per run. Resolves OQ-3. |
| 2026-06-28 | SDD completed | 8 ADRs confirmed (ADR-1..8); directory map, runtime sequence, EARS ACs traced from PRD. |
| 2026-06-28 | Constitution validate → Needs Attention | 1 L1 FAIL (no test plan for write paths) + 1 L1 WARN (safety logic in AI glue) + 4 L2. Privacy/Architecture/Dependencies all PASS. |
| 2026-06-28 | ADR-9 + fixes folded in | Extract parse-gate → `validate-json.py`; collision → `kado-write-file.py --no-overwrite` (deterministic + unit-tested); Test Strategy added; inbox-author drops format-skill pre-load (auto-load, L2 Perf); PRD/README name `kado-toolkit`→`kado-write-patterns`; PLAN to add evolution-log + PRIVACY.md + Kokoro design-note handoff (L2). |
| 2026-06-28 | PLAN completed | 5 phases / 18 tasks (TDD). Phase 1 deterministic scripts hard-gate Phases 3-4; Phase 2 format skills parallel; Phase 5 docs/ops/integration incl. L2 tasks (evolution, PRIVACY, Kokoro handoff) + live walk. |
| 2026-06-28 | Alignment validate → READY TO IMPLEMENT | AC→task + component→task coverage complete; zero drift (all pre-impl file states match SDD). Hygiene fixes folded: `--no-overwrite` exit-3 contract, version-bump checklist (T4.4), AC count corrected to 19. Spec phase → Ready. |

## Context

Tomo Companion Mode **Phase 1** — framework authoring skills. The companion is the existing
conversational Tomo session (no new agent/persona/command); P1 ships **skills** that encode
framework knowledge the LLM lacks, plus wiring of the existing inbox-authoring path.

**Reframe (supersedes the 2026-06-24 charter §6.2/§7):** inbox-only, no direct-write, Kado key stays
read-broad + write-inbox-only — no broader ACL, no cross-repo Kado change, no Kokoro ADR.

**Five deliverables:** (1) obsidian-markdown upgrade, (2) obsidian-bases (new), (3) obsidian-canvas
(new), (4) inbox-author (rename of default-doc-writer + extend: format wiring, #46 template mapping,
`.base`/`.canvas` write path), (5) kado-write-patterns (new, write-side Kado helper invocations).
Supporting deterministic scripts (Constitution L1): `validate-json.py` (parse-gate) +
`kado-write-file.py --no-overwrite` (collision guard), both unit-tested.

**Skill test (design guard):** a capability earns a skill only if it encodes knowledge the LLM does
not already have; user-specific markers/reports live in the user's instance config, not the framework.

Full brainstorm charter: `docs/XDD/ideas/2026-06-28-companion-p1-authoring-skills.md`.

---
*This file is managed by the xdd-meta skill.*
