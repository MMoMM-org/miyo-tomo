# Specification: 023-moc-placement-fit-confidence

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-15 |
| **Current Phase** | SDD complete — PLAN deferred |
| **Last Updated** | 2026-06-16 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 12 ACs, 0 clarification markers; approved 2026-06-16 |
| solution.md | completed | 4 ADRs confirmed; threshold 0.6; no-footer→line; reject→alt_headings; approved 2026-06-16 |
| plan/ | pending | Deferred by user — plan when ready to implement |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-15 | Spec created from spec 022 live-walk findings | Two problems surfaced: (1) tier-1 fits content to STRUCTURAL/template headings (Beppu→Japan "## Content"); (2) #28 tier-2 new-section never triggers because the analyst always finds a weak tier-1 fit. No placement confidence exists to distinguish strong fits (FPT→"Thinking Frameworks") from weak ones (Sapporo→"Content") — both carried MOC-match 0.80. |
| 2026-06-15 | Builds on spec 022 (extends `candidate_mocs[].anchor` + four-tier order) | Confidence is the missing signal that gates tier-1 vs tier-2; cleaner than a hardcoded structural-heading blocklist (generalizes). |
| 2026-06-16 | PRD approved (12 ACs); SDD approved (ADR-1..4 confirmed) | Scope locked: hardcoded threshold 0.6, confidence surfaced as %, no-footer tier-2 fix included, gate-rejected heading → alt_headings. Non-goals: no MOC-selection change, no config threshold, no new Hashi shape, no structural-heading blocklist. |
| 2026-06-16 | PLAN deferred by user | PRD + SDD banked; implementation planning + build to resume later. Spec 022 Phase 7 (T7.3 live walk / T7.4) remains the active in-flight work. |

## Context

Emerged from spec 022's Phase 7 live-validation walk (2026-06-15). Spec 022 relocated the MOC insertion-point decision to Pass-1 (four-tier: semantic heading-fit → new-section → editable-callout → H1). The live walk validated tier-1 (FPT → `## Thinking Frameworks`) and AC-16, but exposed:

1. **Structural-heading scaffolding fit** — tier-1 fit content notes (Japanese cities) to Japan (MOC)'s generic LYT-template heading `## Content` (its only headings are scaffolding: Link MOC · Structure · Content · Primer Questions · Processes). This is the heading-level version of the scaffolding-insertion anti-pattern that 022 only addressed for editable callouts.
2. **#28 never triggers** — because the analyst always finds *some* weak tier-1 fit, the tier-2 new-section path (022 #28 / AC-14/AC-15) does not fire in real vaults.

**Evidence:** FPT→Concepts `Thinking Frameworks` (strong) and Sapporo→Japan `Content` (weak scaffolding) both carried MOC-match score `0.80` and no placement confidence to tell them apart. `alt_headings` is not a usable proxy (present for the strong fit, absent for the weak one).

**Proposed mechanism:** Pass-1 emits a `fit_confidence` on `candidate_mocs[].anchor`; a threshold gates tier-1 (confident semantic heading fit) vs tier-2 (no confident fit → new section). Surface: schema field + analyst emission + threshold in the four-tier order + optionally surface confidence in the suggestions-doc Placement line.

See `docs/XDD/specs/022-moc-insertion-point-intelligence/` and the auto-memory `project_spec022_live_walk_targets`.

---
*This file is managed by the xdd-meta skill.*
