# Specification: 023-moc-placement-fit-confidence

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-15 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-06-16 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 12 ACs, 0 clarification markers; approved 2026-06-16 |
| solution.md | completed | 4 ADRs confirmed; threshold 0.6; no-footer→line; reject→alt_headings; approved 2026-06-16 |
| plan/ | completed | 5 phases all shipped (schema → footer-inventory → gate → surfacing+resolution → live walk), 11 tasks, 2 parallel; created 2026-06-16, revised for the Pass-1/Pass-2 split |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-15 | Spec created from spec 022 live-walk findings | Two problems surfaced: (1) tier-1 fits content to STRUCTURAL/template headings (Beppu→Japan "## Content"); (2) #28 tier-2 new-section never triggers because the analyst always finds a weak tier-1 fit. No placement confidence exists to distinguish strong fits (FPT→"Thinking Frameworks") from weak ones (Sapporo→"Content") — both carried MOC-match 0.80. |
| 2026-06-15 | Builds on spec 022 (extends `candidate_mocs[].anchor` + four-tier order) | Confidence is the missing signal that gates tier-1 vs tier-2; cleaner than a hardcoded structural-heading blocklist (generalizes). |
| 2026-06-16 | PRD approved (12 ACs); SDD approved (ADR-1..4 confirmed) | Scope locked: hardcoded threshold 0.6, confidence surfaced as %, no-footer tier-2 fix included, gate-rejected heading → alt_headings. Non-goals: no MOC-selection change, no config threshold, no new Hashi shape, no structural-heading blocklist. |
| 2026-06-16 | PLAN deferred by user | PRD + SDD banked; implementation planning + build to resume later. Spec 022 Phase 7 (T7.3 live walk / T7.4) remains the active in-flight work. |
| 2026-06-16 | PLAN created; resume 023 ahead of 022 Phase 7 | 023 is the gap 022's live walk exposed — scaffolding-heading fits + tier-2 never firing. Implemented on the same `feat/moc-insertion-llm-resolution` branch (023 extends 022's anchor/four-tier machinery; not a separate concern). No cross-repo Kokoro ADR / Hashi handoff needed — 023 changes no component interaction or wire shape (Tomo-internal). 022 T7.3/T7.4 deferred behind 023. |
| 2026-06-16 | Phase 1 shipped (schema `fit_confidence`); commit 1a01faf | RED→GREEN, 31/31 tests, spec-compliance + code-quality PASS. |
| 2026-06-16 | DEVIATION: AC-9 resolves at Pass-2, not Pass-1; + `has_footer` inventory (ADR-2 corrected, ADR-5 added) | Tracing the code revealed the Pass-1 analyst inventory has NO MOC body — so the SDD's "analyst emits `<last body line>`" is unimplementable. Corrected: analyst emits a truthful null-value anchor (`callout/before` vs `line/after`, chosen via a new cheap `has_footer` flag), the render resolver fills the exact line/footer-text at Pass-2. User also added a transparency requirement (AC-13): the suggestions doc must show WHERE a tier-2 section lands (`(before the footer)` / `(at the end of the MOC)`) — which forces footer-awareness at Pass-1 (the doc is a Pass-1 artifact). PRD +AC-9a/AC-13 (14 ACs); SDD ADR-2/ADR-5 + directory map (+moc-tree-builder, +shared-ctx-builder); PLAN 4→5 phases. User confirmed design + conceptual-wording 2026-06-16. |
| 2026-06-16 | Implementation complete | Branch feat/moc-insertion-llm-resolution (not yet merged), commits e6c95d6..1724e9b. Shipped: fit_confidence on item-result anchor + 0.6 Pass-1 gate (inbox-analyst v0.18.0), has_footer cache flag (moc-tree-builder v0.6.1, shared-ctx-builder v1.5.1), confidence-% + tier-2 destination on placement line (suggestions-reducer v1.10.8), no-footer line resolution + confidence telemetry (instruction-render v0.24.10). Full suite 1256 passed; live walk validated tier-1 confidence % + the 022 Japan/Content regression fix; AC-9 no-footer on unit coverage. Deferred: #64 (per-value telemetry), #65 (callout title in tier-3 placement line). |

## Context

Emerged from spec 022's Phase 7 live-validation walk (2026-06-15). Spec 022 relocated the MOC insertion-point decision to Pass-1 (four-tier: semantic heading-fit → new-section → editable-callout → H1). The live walk validated tier-1 (FPT → `## Thinking Frameworks`) and AC-16, but exposed:

1. **Structural-heading scaffolding fit** — tier-1 fit content notes (Japanese cities) to Japan (MOC)'s generic LYT-template heading `## Content` (its only headings are scaffolding: Link MOC · Structure · Content · Primer Questions · Processes). This is the heading-level version of the scaffolding-insertion anti-pattern that 022 only addressed for editable callouts.
2. **#28 never triggers** — because the analyst always finds *some* weak tier-1 fit, the tier-2 new-section path (022 #28 / AC-14/AC-15) does not fire in real vaults.

**Evidence:** FPT→Concepts `Thinking Frameworks` (strong) and Sapporo→Japan `Content` (weak scaffolding) both carried MOC-match score `0.80` and no placement confidence to tell them apart. `alt_headings` is not a usable proxy (present for the strong fit, absent for the weak one).

**Proposed mechanism:** Pass-1 emits a `fit_confidence` on `candidate_mocs[].anchor`; a threshold gates tier-1 (confident semantic heading fit) vs tier-2 (no confident fit → new section). Surface: schema field + analyst emission + threshold in the four-tier order + optionally surface confidence in the suggestions-doc Placement line.

See `docs/XDD/specs/022-moc-insertion-point-intelligence/` and the auto-memory `project_spec022_live_walk_targets`.

---
*This file is managed by the xdd-meta skill.*
