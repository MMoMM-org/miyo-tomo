# Specification: 024-tag-handler-framework

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-23 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-06-23 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | PRD — design locked in #47 brainstorm |
| solution.md | completed | SDD — 3-layer design, action registry, cross-repo finding |
| plan/ | completed | 6 phases; Hashi handoff ships first (T1.1, parallel) |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-23 | Generalize "Tsukai support" into a tag-handler framework | Per-feature declarative handlers (Tsukai = #1); user-extensible. Recorded on #47. |
| 2026-06-23 | Handler = pure data, not a skill | skill-author isn't installed in Tomo; matches Tomo's "logic in skills, config in data" principle. Authored via a wizard. |
| 2026-06-23 | Aggregation: merge per (handler, target note) | LLM composes one logical status update with full batch context, not a per-capture dump. |
| 2026-06-23 | Additive-only on hot paths | Tomo near-MVP; a /inbox run with no registered handlers must be byte-identical to today. |
| 2026-06-23 | SDD OQ-2: ship `insert_under_marker` only; other 3 actions declared-but-deferred | Registry extensible; one flagship action proves the model without overbuild. |
| 2026-06-23 | SDD OQ-3: append a new dated status block, never replace under the marker | Preserves history; user review is the idempotency gate. |
| 2026-06-23 | SDD finding: `insert_under_marker` needs a NEW Hashi action (cross-repo) | Existing vocab can't insert a multi-line block into an arbitrary note at a marker. |
| 2026-06-23 | Phasing: Phase-1 Tomo-only + manual apply; Phase-2 Hashi action via handoff | Ships v1 end-to-end with no cross-repo dependency (MVP boundary already manual). |
| 2026-06-23 | PLAN: Hashi handoff is T1 (ships first, parallel) | A well-explained Hashi ask early lets the executor land before Tomo's side is done — no manual-apply interim. Only insert_under_marker needs a new Hashi action; route_to_folder/link_to_moc reuse move_note/link_to_moc. |
| 2026-06-23 | /validate 024 → fixes applied | 3-perspective validation (all SDD code-claims held). Fixed: HIGH phasing contradiction (SDD §6 reconciled to Hashi-first), MED routing-plan.schema.json must be extended + omit `handled` when empty (AC-5), MED Kokoro reflection now first-class (T1.1b, `_outbox/for-kokoro/`), + parity polish (placement/enabled/marker-transform/compose-oneOf). |
| 2026-06-23 | Hashi `insert_under_marker` executor SHIPPED (user-confirmed) | Cross-repo dependency cleared: T6.2 automated apply moves from deferred-fallback to buildable; no manual-apply interim. Verify rendered instruction matches shipped Hashi contract at P4 (T4.1). |
| 2026-06-23 | SDD §10 OQ resolved: interpreter compose = **lean in-skill** | The suggestion-conductor composes each group via its own inference (no separate analyst/subagent dispatch). Lightest; fits the conductor-does-work pattern. Deterministic grouping stays a testable helper. |
| 2026-06-23 | Phase 3 producer→consumer contract = new `tag-handler-group.schema.json` | A merged group spans multiple captures, so it does NOT fit per-item `item-result.schema.json`. A dedicated group-result artifact (handler/target/marker/composed_block/source_paths) is the skill→reducer interface — additive, avoids touching the hot item-result path. Schema defined BEFORE producer/consumer (anti-drift). |
| 2026-06-23 | Phase 4 expanded: approved groups need explicit approval→render linkage | Explore map found approved tag-handler groups are NOT wired from suggestions-doc → suggestion-parser → instruction-render. P4 = T4.0 hashi-instructions `insert_under_marker` $def + T4.1 linkage+render + T4.2 guards + T4.3 validation. Run SEQUENTIALLY (same files). |
| 2026-06-23 | Approval linkage = **deterministic group id** from (handler, target_path) | `group_id()` lives in tag-handler-group.py; reducer renders it as the suggestion id, parser extracts approved ids, instruction-render recomputes + matches, reading the group-result JSONs as the data source-of-truth. No new schema field, no skill re-touch, no fragile markdown re-parse of the multi-line composed block. |

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
