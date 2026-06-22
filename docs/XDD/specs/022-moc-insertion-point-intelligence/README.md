# Specification: 022-moc-insertion-point-intelligence

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-14 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-06-20 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 16 ACs, 0 clarification markers; approved 2026-06-15 |
| solution.md | completed | 7 ADRs confirmed; constitution-compliant; approved 2026-06-15 |
| plan/ | completed | 7 phases, 22 tasks; alignment-verified (zero drift); approved 2026-06-15 |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-14 | Spec created on branch `feat/moc-insertion-llm-resolution` | Merges #28 (F-36) + #29 (F-30) + F-05 under epic #17; P0 MOC Intelligence |
| 2026-06-14 | LLM heading-fit decision lives in Pass-1, not Pass-2 render | 2-pass model requires placement to surface in suggestions doc for user review/change before confirmation |
| 2026-06-14 | New resolution order; editable callout demoted to fallback | Editable callouts are scaffolding/instructions (verified vs live "Systems Thinking (MOC)"); real content lives under H2/H3 |
| 2026-06-15 | Step-4 last-resort = anchor on H1 title, `placement:after` | Hashi `type:heading` matches any level incl. H1 (`anchorResolver.ts`, schema `:99`); `type:line` covers deeper fallback. No new Hashi shape / handoff needed |
| 2026-06-15 | F-05 (topic weighting) fenced OUT of 022 | 022 = insertion-point (WHERE inside MOC) only; MOC-selection scoring (WHICH MOC) untouched, F-05 tracked separately |
| 2026-06-15 | New-section name derived from note topic; retire hardcoded "Key Concepts" | `DEFAULT_NEW_SECTION_TITLE` retired; matches user's semantic-MOC model; renamable in suggestions doc |
| 2026-06-15 | Anchor carrier = `create_atomic_note.candidate_mocs[]` (SDD detail) | Pass-1 `link_to_moc.section_name` is dead (consumed nowhere); live synth path is candidate_mocs[] → `_build_link_to_moc_actions`. Final mechanism decided in SDD |
| 2026-06-15 | Heading inventory parsed in moc-tree-builder (no new Kado calls) | Builder already reads MOC bodies; parse H2/H3 + editable callouts there → avoids 429 read-storm. Cost-trim approach decided in SDD |
| 2026-06-15 | SDD ADR-2 = A-trimmed cost strategy | Eager headings-only inventory, cap ~8/MOC, skip Dewey, enforce_budget drops inventory first; per-item regression deferred to #45 |
| 2026-06-15 | SDD ADR-3 = explicit new_section field on instructions link_to_moc | Cleaner than line_to_add string mutation; render builds line_to_add at serialize; no Hashi change |
| 2026-06-15 | SDD complete — all 7 ADRs confirmed | New shared lib `lib/moc_structure.py`; honor via existing anchor.value guard; no new Kado/Hashi surface |
| 2026-06-15 | Spec quality validation passed (4 perspectives) | Alignment 22/22 (zero code drift); ambiguity ~6%. 9 findings fixed: stale SDD status table + ADR-3 PENDING leftovers; EC-3 defined; no-H1 `type:line` test added; KPI baseline reframed to AC-14/15 walk; AC-2 acceptance basis; AC-16 trigger disambiguated; hard byte bound; partial-inventory note |
| 2026-06-15 | Phase 4 (Pass-1 four-tier) implemented | inbox-analyst emits `candidate_mocs[].anchor` via four-tier order; 26 contract fixtures (AC-1,2,4,5,7,9,10,EC-5); both reviews PASS |
| 2026-06-15 | Phase 5 (render honor path) implemented | `_emit` stamps Pass-1 anchor (heuristic auto-suppresses via `anchor.value` guard); independent `_serialize_new_sections`; render fallback unified on `lib/moc_structure` (ADR-4) |
| 2026-06-15 | Honor-path anchor decomposed at `_emit` to satisfy instructions.schema.json | Pass-1 anchor `{type,value,placement,new_section}` was stamped whole into the action `anchor` (allows only `{type,value}`, additionalProperties:false). Decompose: `anchor`={type,value}, lift `placement`/`new_section` to top-level action fields. Added end-to-end schema-validation test as the contract guard |
| 2026-06-15 | Phase 6 (suggestions surfacing) implemented | `**Placement:**` line per candidate MOC (4 UX-locked formats + `←` hint, never bare `[[Target#]]`); dead `section_name` removed from `render_link_to_moc`; both reviews PASS |
| 2026-06-15 | T6.2 expanded to full vertical slice (user decision) | AC-16 needed Pass-1 runner-up flagging that Phase 4 never built. User chose to implement fully (cost: zero new Kado reads/LLM calls, small fixed prompt bump). Added optional `alt_headings` to anchor schema → inbox-analyst TIER-1 emits runner-ups when ≥2 fit → reducer renders "Other sections in this MOC:" advisory. Schema-before-consumer ordering |

## Context

Redesign the `/inbox` MOC link-insertion resolution.

**Problem:** Today the insertion point inside a target MOC is resolved by a deterministic 3-tier heuristic at Pass-2 render time (`instruction-render.py:resolve_section_names`): editable callout → first content heading → new-section-before-footer (#28). This is wrong on three counts: (a) editable callouts (e.g. `[!blocks] Key Concepts`) are scaffolding/instructions, not insert targets — real content links live under the H2/H3 headings below them; (b) the first-heading pick has no relevance scoring, so #28 (new-section) only fires for an artificial footer-only MOC and is unreachable in real vaults; (c) the decision happens after the user confirmed suggestions, so the placement is never user-reviewable.

**Target design (user-confirmed):** New resolution order —
1. LLM picks the thematically fitting H2/H3 heading.
2. Headings exist but none fits → propose a NEW H2 section (#28).
3. No headings at all → insert UNDER the editable callout (config-driven via `callouts.editable`, the old tier-1 demoted to fallback).
4. No editable callout → insert into the note (last-resort).

The LLM heading-fit decision lives in Pass-1 (`inbox-analyst`) so it surfaces in the suggestions document for user review. Requires enriching `shared-ctx` with per-MOC H2/H3 heading inventory + editable callouts (Pass-1 is currently blind to MOC internal structure).

**Cross-repo:** downstream `needs-hashi` — hashi#42 (new-section apply), hashi#43 (insertion-point apply).

**Known concerns:** per-item context cost (#45) from heading inventory — manage separately. Live validation walk: `100 Inbox/First Principles Thinking.md` → a MOC where no H2 fits → #28 fires.

---
*This file is managed by the xdd-meta skill.*
