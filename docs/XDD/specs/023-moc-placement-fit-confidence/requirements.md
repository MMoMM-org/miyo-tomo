---
title: "MOC placement-fit confidence"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (spec 022 live walk, 2026-06-15)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Output Schema

### PRD Status Report

| Field | Value |
|-------|-------|
| specId | 023-moc-placement-fit-confidence |
| title | MOC placement-fit confidence |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 14 |

---

## Product Overview

### Vision
The `/inbox` pipeline places a note under an existing MOC heading **only when that heading is a genuinely good thematic home** — and otherwise proposes a new, well-named section — so the user never has to undo a link buried under scaffolding.

### Problem Statement
Spec 022 relocated the MOC insertion-point decision to Pass-1's four-tier order (semantic heading-fit → new-section → editable-callout → H1). Its 2026-06-15 live walk validated the happy path (First Principles Thinking → `## Thinking Frameworks`) but exposed two coupled failures:

1. **Scaffolding-heading fits.** Tier-1 fits content notes to *structural/template* headings. Japanese-city notes landed under Japan (MOC)'s generic `## Content` heading — a pure LYT-template scaffolding heading (its only headings are `Link MOC · Structure · Content · Primer Questions · Processes`, none of them a topic section). This is the heading-level version of the "insert into scaffolding" anti-pattern that 022 only fixed for editable *callouts*.
2. **Tier-2 never triggers.** Because the analyst always finds *some* weak tier-1 fit, the new-section path (022 #28 / AC-14/AC-15) does not fire on real vaults — it remained unvalidated end-to-end.

The root cause is measurable: there is **no signal for how good a heading fit is**. In the walk, `First Principles Thinking → Concepts (MOC) "Thinking Frameworks"` (strong) and `Sapporo → Japan (MOC) "Content"` (weak scaffolding) **both carried MOC-match score `0.80`** and no placement confidence to tell them apart. The `alt_headings` advisory is not a usable proxy — it was present for the strong fit and *absent* for the weak one. Consequence: weak fits are indistinguishable from strong ones, so they are silently forced into tier-1.

### Value Proposition
A single Pass-1 signal — heading-fit confidence — lets the four-tier order distinguish "this heading is the right home" from "nothing here really fits." That one signal:
- Stops content being filed under scaffolding headings (the user's links land where they belong).
- Makes the tier-2 new-section path fire *when it should* — naturally, on real vaults.
- Is surfaced in the suggestions doc so the user sees *why* a placement was chosen and can review borderline calls before approving.

It generalizes (no per-profile blocklist of "bad" heading names to maintain) and reuses an established pattern: the pipeline already emits LLM 0-1 confidence scores (`type_confidence`, `candidate_mocs[].score`, `classification.confidence`, `atomic_note_worthiness`) surfaced as percentages in the suggestions-doc "Why" line.

## User Personas

### Primary Persona: The PKM owner (Marcus)
- **Demographics:** Single power user; expert Obsidian/LYT practitioner; runs Tomo over a large personal vault.
- **Goals:** Run `/inbox`, review proposals quickly, approve placements that are *correct* without hand-fixing where each link lands.
- **Pain Points:** Links filed under generic scaffolding headings (`## Content`) that are not real topic homes; having to manually retarget the placement; no visibility into how confident the system was about a placement.

### Secondary Personas
None. Tomo is a single-owner tool; the proposal-review surface (the suggestions doc) is the only consumer of placement decisions.

## User Journey Maps

### Primary User Journey: Reviewing a placement in the suggestions doc
1. **Awareness:** User runs `/inbox`; Pass-1 produces placement decisions for each pre-checked MOC.
2. **Consideration:** User reads the `**Placement:**` line per candidate MOC, now annotated with a confidence percentage.
3. **Adoption:** A strong fit (`under \`## Thinking Frameworks\` (confidence: 89%)`) is approved as-is; a proposed new section (`new section \`## Städte\``) is approved when no existing heading fit well.
4. **Usage:** For a borderline call, the user edits the `**Placement:**` line to retarget — the confidence % flags which placements are worth a second look.
5. **Retention:** Placements consistently land in the right home, so the review step gets faster and trust in `/inbox` increases.

### Secondary User Journeys
None.

## Feature Requirements

### Must Have Features

#### Feature 1: Pass-1 emits a heading-fit confidence
- **User Story:** As the PKM owner, I want Pass-1 to record how strongly the chosen heading fits the note, so the system can tell a real thematic home from a scaffolding heading.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-1** Given a pre-checked MOC with content headings, When Pass-1 selects a tier-1 heading, Then it emits a `fit_confidence` (0.0–1.0) for that heading on `candidate_mocs[].anchor`.
  - [ ] **AC-2** Given the anchor is not a tier-1 heading fit (tier-2/3/4, or no anchor), When Pass-1 emits the anchor, Then `fit_confidence` is null or absent (it qualifies tier-1 heading fits only).
  - [ ] **AC-3** Given a strong thematic fit (note topic clearly matches a content heading), When Pass-1 scores it, Then `fit_confidence` is high; And given a weak fit to a generic/structural heading (e.g. `## Content`), Then `fit_confidence` is low — the two are distinguishable.

#### Feature 2: Threshold-gated tier-1 vs tier-2
- **User Story:** As the PKM owner, I want a note placed under an existing heading only when the fit is confident, otherwise proposed as a new section, so content never lands under scaffolding.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-4** Given a tier-1 candidate heading whose `fit_confidence` ≥ the (hardcoded) threshold, When Pass-1 resolves placement, Then tier-1 wins (anchor on that heading).
  - [ ] **AC-5** Given the best heading's `fit_confidence` < threshold, When Pass-1 resolves placement, Then tier-1 is rejected and the order falls through to tier-2 (new section named from the note topic) — not forced into the low-confidence heading.
  - [ ] **AC-6** Given Japan (MOC) with only structural headings and a Japanese-city note, When Pass-1 resolves placement, Then the city does NOT land under `## Content`; it is proposed as a new section (regression guard for the exact walk failure).
  - [ ] **AC-7** Given a vault where no MOC offers a confident heading fit for a note, When Pass-1 runs, Then the tier-2 new-section path fires (closing the 022 #28 / AC-14/AC-15 gap that never triggered in real vaults).

#### Feature 3: No-footer new-section fallback
- **User Story:** As the PKM owner, I want a proposed new section to land correctly even in MOCs that have no footer callout, so the more-frequent tier-2 path doesn't produce an unanchored or misplaced section.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-8** Given a tier-2 new-section decision for a MOC that HAS a footer callout, When Pass-1 emits the anchor, Then it anchors the new section before the footer (unchanged 022 behavior).
  - [ ] **AC-9** Given a tier-2 new-section decision for a MOC with NO footer callout (e.g. Concepts (MOC)), When Pass-1 emits the anchor, Then it emits a `line`-type anchor with `placement: after` and a null value (signalling "append at the end of the MOC") — and at Pass-2 the render resolver fills that value with the MOC's actual last body line — reusing an existing Hashi shape, no new wire shape. (Pass-1 cannot see the MOC body; the exact line is resolved at render where the live MOC is read — symmetric with how the footer-callout text is resolved for AC-8.)
  - [ ] **AC-10** Given either footer case, When the instruction is rendered/applied, Then the new `## <Topic>` heading and its link are inserted with correct spacing (no flush-against-footer, no dangling section).
  - [ ] **AC-9a** Given Pass-1 must choose between the footer (AC-8) and no-footer (AC-9) branch before the live MOC is read, When the analyst resolves a tier-2 placement, Then it reads a `has_footer` flag on the MOC inventory (`shared_ctx.mocs[].has_footer`, derived cheaply at cache-build time from the MOC body — no new Kado read) to pick the truthful anchor type.

#### Feature 4: Surface confidence in the suggestions doc
- **User Story:** As the PKM owner, I want to see the placement confidence in the suggestions doc, so I can spot and review borderline placements before approving.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-11** Given a tier-1 heading placement with a `fit_confidence`, When the suggestions doc renders the `**Placement:**` line, Then it shows the confidence as a percentage (e.g. `under \`## Thinking Frameworks\` (confidence: 89%)`), consistent with the existing Why-line percentages.
  - [ ] **AC-12** Given an anchor without `fit_confidence` (tier-2/3/4, or a legacy result), When the suggestions doc renders, Then no confidence annotation appears and the line is unchanged from 022 (back-compat).
  - [ ] **AC-13** Given a tier-2 new-section placement, When the suggestions doc renders the `**Placement:**` line, Then it shows WHERE the section will land so the user sees the destination before approving — `new section \`## <Topic>\` (before the footer)` for a footer MOC, or `new section \`## <Topic>\` (at the end of the MOC)` for a footer-less MOC. The conceptual destination is shown (not the literal last-line text, which is resolved at Pass-2).

### Should Have Features
- A confidence indicator on the ambiguous-fit advisory (`**Other sections in this MOC:**`) when the runner-up is close to the chosen heading. *(Deferred unless trivial; AC-16 of 022 already lists runner-ups.)*

### Could Have Features
- A user-configurable confidence threshold (vault-config). *Explicitly not in this phase — see Won't Have.*
- A user-configurable structural-heading list as an extra negative signal. *Not needed; confidence generalizes.*

### Won't Have (This Phase)
- **Config-driven threshold.** The threshold is hardcoded in `inbox-analyst.md` (matching the existing 0.7/0.5/0.15 hardcoded thresholds). Lifting it to config is a future option, not this phase.
- **Structural-heading blocklist.** No machine-readable list of "bad" heading names; confidence scoring replaces the need for one.
- **Changes to MOC-selection scoring (which MOC).** This spec is insertion-point only (like 022). It does not touch `candidate_mocs[].score`, `needs_new_moc`, or the choice of which MOC a note belongs to.
- **New Hashi wire shapes.** The no-footer fallback reuses the existing `line` anchor + `after` placement.

## Detailed Feature Specifications

### Feature: Threshold-gated tier-1 vs tier-2 (the core mechanism)
**Description:** Pass-1 scores the semantic fit of the best candidate heading and only commits to tier-1 when that score clears a hardcoded threshold; otherwise it proposes a new section. The confidence is carried on the anchor and surfaced to the user.

**User Flow:**
1. User runs `/inbox`.
2. Pass-1 (per pre-checked MOC) evaluates content headings for semantic fit and assigns the best one a `fit_confidence`.
3. System: if `fit_confidence ≥ threshold` → tier-1 (anchor on heading, carry `fit_confidence`); else → tier-2 (new section named from topic).
4. System: for tier-2, choose the footer anchor if a footer exists, else a last-line `line` anchor.
5. User reads the `**Placement:**` line (with confidence % on tier-1 fits) and approves or edits.

**Business Rules:**
- Rule 1: `fit_confidence` qualifies tier-1 heading fits only; tiers 2–4 carry no confidence.
- Rule 2: The threshold is a single hardcoded constant in `inbox-analyst.md`; changing it is a prompt edit + version bump (consistent with existing thresholds).
- Rule 3: A new section's name is derived from the note's dominant topic, never the literal "Key Concepts" (inherited from 022 AC-5).
- Rule 4: Back-compat — an anchor lacking `fit_confidence` is valid and renders/behaves exactly as in 022.
- Rule 5: This spec never alters which MOC a note links to.

**Edge Cases:**
- Scenario 1: All candidate headings are structural/generic (Japan (MOC)) → Expected: all score below threshold → tier-2 new section (AC-6).
- Scenario 2: Note fits a heading strongly AND a runner-up plausibly (FPT) → Expected: tier-1 on the best, `fit_confidence` high, runner-up still surfaced via 022's `alt_headings` advisory.
- Scenario 3: Tier-2 fires but the MOC has no footer → Expected: last-line `line` anchor (AC-9), not a null/unanchored section.
- Scenario 4: Exactly at the threshold boundary → Expected: deterministic, documented tie-break (≥ threshold wins tier-1).
- Scenario 5: Empty/degraded inventory (no headings cached) → Expected: no `fit_confidence`, behaves as 022 graceful-degradation (omit anchor / tier-4); the four-tier must not fabricate a confidence for inventory it wasn't given.
- Scenario 6: Legacy result.json without `fit_confidence` → Expected: renders unchanged, no confidence annotation (AC-12).

## Success Metrics

### Key Performance Indicators
- **Quality (primary):** On the spec-022 live-walk corpus, zero content notes are placed under a structural/scaffolding heading (e.g. `## Content`). Target: 0 scaffolding-fits where a new section is warranted.
- **Coverage:** The tier-2 new-section path fires at least once on the real vault walk (closes 022 AC-14/AC-15). Target: ≥1 genuine #28 trigger validated end-to-end.
- **Consistency:** Items of the same kind (e.g. the cluster of Japanese cities) receive the same tier decision in a run. Target: 100% intra-cluster consistency (the walk previously showed 4 different outcomes pre-fix).
- **Transparency:** Tier-1 placements display a confidence %. Target: 100% of tier-1 heading placements annotated.

### Tracking Requirements
Extends the spec-022 metadata-only resolution telemetry (Constitution L2 — no note content / heading text).

| Event | Properties | Purpose |
|-------|------------|---------|
| four-tier resolution (existing 022 telemetry) | per-tier counts + the new `fit_confidence` bucket (e.g. tier-1-confident vs tier-1-rejected→tier-2 counts), MOC path | Verify weak fits are being routed to tier-2 and #28 fires; metadata only |
| placement decision | tier fired, fit_confidence value (number only — not the heading text) | Tune the hardcoded threshold against real runs without logging content |

---

## Constraints and Assumptions

### Constraints
- **No new Kado reads / no new LLM passes.** Confidence is scored within the existing Pass-1 analysis over already-loaded inventory (the 022 cost contract holds).
- **Hardcoded threshold** in `inbox-analyst.md` (per locked decision); no config surface this phase.
- **No new Hashi wire shape** — the no-footer fallback uses the existing `line`/`after` shape.
- **Metadata-only telemetry** (Constitution L2).
- **Builds on spec 022** — requires 022's `candidate_mocs[].anchor`, four-tier order, shared `lib/moc_structure`, and the suggestions-doc Placement line.

### Assumptions
- LLM self-assessed 0-1 confidence is usable here, because the pipeline already relies on the same pattern for `type_confidence`, MOC `score`, classification confidence, and `atomic_note_worthiness` (all surfaced as percentages). Calibration need only be good enough to separate "clear topic home" from "generic/structural heading."
- The MOC heading inventory is fresh (the cache is rebuilt via `/explore-vault`). Stale-cache degradation is a known operational issue, not in scope here.
- A single hardcoded threshold generalizes across the user's MOC styles well enough; if not, the config option (Could-Have) is the escape hatch.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM confidence is poorly calibrated (weak fits score high) | High | Medium | Surface the % in the suggestions doc so the user catches mis-scores; tune the hardcoded threshold against the live-walk corpus; the decision is always editable pre-approval |
| Threshold too high → too many new sections (section sprawl) | Medium | Medium | Tune against the walk corpus; the runner-up advisory (022 AC-16) still surfaces existing headings for one-edit retarget |
| Threshold too low → scaffolding fits persist | Medium | Low | Same tuning; the quality KPI (0 scaffolding-fits) is the acceptance gate |
| No-footer fallback inserts a section in an unexpected spot | Medium | Low | Reuse the validated `line`/`after` Hashi shape; cover with the real-vault walk on a footer-less MOC (Concepts (MOC)) |
| Scope creep into MOC-selection scoring | Medium | Low | Explicit non-goal; reviews reject any change to `score`/`needs_new_moc` |

## Open Questions
- [ ] What is the initial hardcoded threshold value? (Proposed: 0.6 — to be tuned in SDD/implementation against the live-walk corpus.)
- [ ] Should the threshold-rejected runner-up always appear in the `alt_headings` advisory so the user can still one-click retarget to it? (Likely yes — confirm in SDD.)

---

## Supporting Research

### Competitive Analysis
N/A — internal single-user PKM tooling; no competitive surface. The relevant prior art is internal: spec 022's four-tier resolution and the existing LLM-confidence fields in the pipeline.

### User Research
Direct evidence from the spec-022 Phase 7 live walk (2026-06-15) against the owner's real vault: FPT→`Thinking Frameworks` (strong) vs Sapporo/Beppu/Hakodate→`Content` (weak scaffolding), both at MOC-match 0.80; tier-2 never fired; placements were inconsistent under a stale cache and uniformly scaffolding-fits once consistent. Full trace in spec 022 README and `project_spec022_live_walk_targets` memory.

### Market Data
N/A — internal tooling.
