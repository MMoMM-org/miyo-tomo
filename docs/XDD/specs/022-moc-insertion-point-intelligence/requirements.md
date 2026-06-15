---
title: "MOC insertion-point intelligence"
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

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Output Schema

### PRD Status Report

| Field | Value |
|-------|-------|
| specId | 022-moc-insertion-point-intelligence |
| title | MOC insertion-point intelligence |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 16 |

---

## Product Overview

### Vision

When `/inbox` links a captured note into a Map-of-Content, it places the link under the
*thematically correct* section — and shows that placement to the user for review before anything
is written.

### Problem Statement

The `/inbox` flow already decides **where inside a target MOC** a note-link goes, but it does so
wrongly on three counts (all verified against live vault + code):

1. **Wrong target.** The current resolver inserts into the first matching *editable callout*
   (e.g. `[!blocks] Key Concepts`). But in real MOCs those callouts are **scaffolding / template
   instructions** — the actual content links live under the **H2/H3 headings below them**
   (confirmed against `Atlas/200 Maps/Systems Thinking (MOC).md`). Links land in the instruction
   block instead of the content section.
2. **No semantic fit.** When it does reach headings, it picks the *first* heading (or one literally
   named "Key Concepts"), with no judgment of whether the heading fits the note. Consequently the
   "propose a new section when nothing fits" path (#28) only fires for an artificial heading-less
   MOC and is **unreachable in real vaults**.
3. **Not reviewable.** The placement is resolved at Pass-2 render time — **after** the user has
   already confirmed the suggestions. The user never sees or controls where their note lands,
   which violates MiYo's 2-pass, proposal-first contract.

Consequence: in a "chaos" personal vault, captured notes accrete under arbitrary or scaffold
sections, and the user cannot correct placement without manual post-editing of the vault.

### Value Proposition

The note-link lands where it *belongs* — under the section whose meaning matches the note — and
the user can verify or override that decision in the suggestions document with a single edit,
before any vault change. MOCs grow coherent sections instead of a junk drawer, and the user stays
in control, consistent with how the rest of MiYo works.

## User Personas

### Primary Persona: Marcus (vault owner / sole operator)

- **Demographics:** Single power user; owns the Obsidian PKM; high technical expertise; runs
  Tomo `/inbox` against his own vault. Vault is large and structurally inconsistent ("chaos").
- **Goals:** Capture notes quickly and have them filed into the right MOC section with minimal
  manual cleanup; retain final say over placement; keep MOCs semantically organized.
- **Pain Points:** Links dumped into scaffold callouts or arbitrary first-headings; no visibility
  into placement until after applying; correcting a misplacement means editing the vault by hand.

### Secondary Personas

None. Tomo is single-operator by design (memory: `user_marcus_tomo_ux_model`).

## User Journey Maps

### Primary User Journey: Reviewing and confirming a note's MOC placement

1. **Awareness:** User captures a note (e.g. "First Principles Thinking") into the inbox and runs
   `/inbox`.
2. **Consideration:** Pass-1 proposes the target MOC(s) and, for each, the **section** the link
   will go under — surfaced as a `**Placement:**` line in the suggestions document.
3. **Adoption:** User skims the placement line, sees it is correct (or edits the heading / renames
   a proposed new section), then checks the doc-level `Approved` box.
4. **Usage:** User re-runs `/inbox` for Pass-2; the confirmed placement is rendered into the
   instruction set and applied (via Hashi or manually).
5. **Retention:** Because placement is right-by-default and one edit away when wrong, the user
   trusts `/inbox` to file notes and keeps using it.

### Secondary User Journeys

None.

## Feature Requirements

### Must Have Features

The MUST set is the four-step resolution order, its relocation to Pass-1, and its surfacing for
review.

#### Feature 1: Semantic heading-fit placement (Pass-1)

- **User Story:** As Marcus, I want each proposed MOC link placed under the existing H2/H3 heading
  that thematically fits my note, so that related notes cluster under the right section even when
  they share no literal keywords.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-1** Given a target MOC with ≥1 H2/H3 heading and a note that thematically fits one of
    them, When Pass-1 resolves placement, Then the link is placed under that heading and the
    suggestions document shows `**Placement:** under \`## <heading>\``.
  - [ ] **AC-2** Given a note whose fitting heading shares **zero literal token overlap** with the
    note (e.g. a "First Principles Thinking" note vs a "Reasoning Techniques" heading), When
    Pass-1 resolves placement, Then the semantically correct heading is still chosen (fit is by
    meaning, not keyword overlap).
  - [ ] **AC-3** Given any target MOC, When placement is resolved, Then exactly one of the four
    tiers (fitting heading → new section → editable callout → note title) fires, evaluated in that
    order, and the chosen tier is recorded so the suggestions doc and the instruction set name the
    same placement.

#### Feature 2: New-section proposal when nothing fits (#28)

- **User Story:** As Marcus, when no existing heading in the target MOC fits my note, I want Tomo
  to propose a **new** H2 section named after my note's topic, so that my MOCs grow coherent
  sections instead of dumping the link under an arbitrary heading.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-4** Given a MOC that has H2/H3 headings but none fits the note, When Pass-1 resolves
    placement, Then a new H2 section is proposed and the suggestions doc shows
    `**Placement:** new section \`## <Topic>\` (created before the footer)`.
  - [ ] **AC-5** Given a new-section proposal, When the section name is generated, Then it is
    derived from the note's dominant topic (NOT the hardcoded literal "Key Concepts").
  - [ ] **AC-6** Given a confirmed new-section placement, When Pass-2 renders and the change is
    applied, Then the new H2 section is inserted before the MOC footer with the trailing-newline
    spacing contract preserved (no flush-against-footer regression).

#### Feature 3: Editable-callout fallback (demoted)

- **User Story:** As Marcus, when a MOC has no headings at all, I want the link placed under its
  editable callout (the section where I normally put my H2/H3), so that headingless MOCs still
  receive the link in a sensible spot.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-7** Given a MOC with no H2/H3 headings but a configured editable callout
    (`callouts.editable`), When placement is resolved, Then the link is placed under that callout
    and the suggestions doc shows `**Placement:** inside the \`> [!<callout>]\` callout`.
  - [ ] **AC-8** Given multiple editable callouts, When the fallback fires, Then selection follows
    the existing config priority — and this tier is only reached when no fitting/any heading
    exists.

#### Feature 4: Note-title last-resort

- **User Story:** As Marcus, when a MOC has neither a fitting heading nor an editable callout, I
  want the link placed under the MOC's title rather than dropped, so that every note is filed
  somewhere legible and no action silently fails.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-9** Given a MOC with no headings and no editable callout, When placement is resolved,
    Then the link is placed under the MOC's H1 title and the suggestions doc shows
    `**Placement:** under the note title (no matching section or callout found)`.
  - [ ] **AC-10** Given any resolvable MOC, When placement is resolved, Then the action is never
    left unresolved/dropped — one of the four tiers always produces a concrete placement.

#### Feature 5: Reviewable, overridable placement in the suggestions document

- **User Story:** As Marcus, I want the chosen placement shown in the suggestions document with an
  edit hint, so that I can verify it and correct a wrong guess with one edit before confirming —
  not discover the placement after applying.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-11** Given any proposed MOC link, When the suggestions document is rendered, Then it
    shows exactly one `**Placement:**` line for that link with a leading qualifier word
    (under / new section / inside / under the note title) and an `←` edit hint — never a bare
    `[[Target#]]` with an empty anchor.
  - [ ] **AC-12** Given the user edits the placement heading in the suggestions document before
    confirming, When Pass-2 renders, Then the user's chosen heading is honored.
  - [ ] **AC-13** Given the placement decision is made in Pass-1, When the user reviews suggestions,
    Then the decision is visible *before* the confirm gate (no placement is decided only at Pass-2
    render).

#### Feature 6: Live-validation walk (acceptance gate for the spec)

- **User Story:** As Marcus, I want a real end-to-end run proving the new-section path fires and is
  reviewable, so that #28 is validated against a real vault rather than only a unit fixture.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **AC-14** Given the note `100 Inbox/First Principles Thinking.md` and a target MOC in which
    no existing H2 thematically fits it, When `/inbox` Pass-1 runs, Then a new H2 section is
    proposed, the proposed section name appears in the suggestions document, and the user can
    rename it there.
  - [ ] **AC-15** Given the user confirms that suggestion, When Pass-2 renders and the change is
    applied through Hashi, Then the new section lands before the MOC footer with correct spacing
    and the link appears under it.

### Should Have Features

- [ ] **AC-16** When two or more existing headings are plausible for a note, the suggestions
  document surfaces the runner-up heading(s) as an advisory line so the user can retarget without a
  re-run (ambiguous-fit affordance, EC-3).

### Could Have Features

- Surfacing a short rationale ("matched on: systems / feedback") next to the placement line.
  Deferred unless it falls out cheaply from the Pass-1 decision.

### Won't Have (This Phase)

- **F-05 topic weighting** (title/heading > content in MOC *selection*) — 022 is insertion-point
  only (WHERE inside a MOC), not which MOC is selected.
- **Per-item context-cost shaping (#45)** — enriching context with heading inventory adds to the
  Pass-1 envelope; trimming/shaping that envelope is #45's job. 022 acknowledges the regression and
  defers the mitigation.
- **Profile-configurable footer callouts (#35 / F-55)** — the footer-callout set stays as-is; 022
  consumes footer detection but does not make it profile-driven.
- **New Hashi wire shapes / apply-side changes** — the landed Hashi insert primitive (PR #65)
  already applies every shape 022 emits (heading/callout/line anchors; inside/before/after). No new
  Hashi capability is required.

## Detailed Feature Specifications

### Feature: Four-step insertion-point resolution

**Description:** For each (note, target-MOC) pair, Pass-1 chooses *where inside the MOC* the link
goes, evaluating four tiers in order and stopping at the first that succeeds. The decision is
carried into the suggestions document for review, then honored at Pass-2 render.

**User Flow:**
1. User runs `/inbox`; Pass-1 analyzes each inbox item and identifies candidate MOCs.
2. For each pre-checked candidate MOC, Pass-1 resolves placement using the four-step order.
3. The suggestions document shows the resolved `**Placement:**` line per link.
4. User reviews, optionally edits the heading / renames a proposed section, and approves.
5. User re-runs `/inbox` (Pass-2); the confirmed placement is rendered and applied.

**Business Rules:**
- **R1 (order):** Resolution evaluates tiers strictly in order — (1) fitting existing H2/H3 →
  (2) new H2 section → (3) under editable callout → (4) under H1 title. First success wins.
- **R2 (semantic fit):** Tier-1 fit is judged by meaning, not literal keyword overlap.
- **R3 (new-section naming):** A new section is named from the note's dominant topic; the legacy
  hardcoded default name is retired.
- **R4 (review-before-confirm):** The placement is decided in Pass-1 and shown in the suggestions
  document before the confirm gate; Pass-2 honors it rather than re-deciding.
- **R5 (no drop):** Every resolvable (note, MOC) pair produces a concrete placement; tier-4 is the
  guaranteed catch-all.
- **R6 (classification exclusion):** Classification-layer MOCs are never insertion targets and are
  excluded before tier-1.

**Edge Cases:**
- **EC-2 (in-run new MOC):** A MOC proposed in the same run does not yet exist → heading-fit is
  judged against the create-MOC **template body**; the suggestions doc notes the MOC will be
  created. → Expected: placement resolves against template structure, no failure.
- **EC-5 (classification MOC):** Target is a classification-layer MOC → Expected: excluded as an
  insertion target before resolution (never receives a link).
- **EC-6 (user overrides to a non-existent heading):** User edits the placement to a heading the
  MOC doesn't contain → Expected: treated as a new-section request — the named H2 is created
  (rather than silently appended elsewhere or failing).
- **EC-1 (headingless + callout-less MOC):** No heading, no editable callout → Expected: tier-4
  (under H1 title) fires; if a MOC even lacks an H1, the placement degrades to a literal first-body
  line anchor (still applied, never dropped).
- **EC-4 (note → multiple MOCs):** A note links to several MOCs → Expected: placement is resolved
  **per (note, MOC) pair** independently (a note may land under a heading in one MOC and create a
  new section in another).

## Success Metrics

### Key Performance Indicators

- **Correct placement (Quality):** On the validation set, ≥ the current baseline of note-links land
  under a semantically appropriate section (not a scaffold callout or arbitrary first-heading),
  judged by the owner on review.
- **Reviewability (Adoption):** 100% of proposed MOC links display a `**Placement:**` line — zero
  bare `[[Target#]]` anchors in the suggestions document.
- **New-section reachability (Quality):** The #28 new-section path fires on at least one real-vault
  run (the AC-14/AC-15 walk) — proving it is reachable outside unit fixtures.
- **No silent drops (Quality):** Zero resolvable MOC links left unresolved/unanchored after Pass-2.
- **Cost (Business Impact / guardrail):** Per-run `/inbox` token cost stays within the documented
  envelope; any regression from heading-inventory enrichment is recorded against the cost log and
  attributed to the #45 follow-up.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Placement resolved (Pass-1) | tier fired (1–4), MOC path, has-fitting-heading | Verify the order and how often each tier fires |
| Placement overridden (user) | edited heading vs proposed | Measure how often the default guess is wrong |
| New-section proposed (#28) | MOC path, generated name | Confirm #28 reachability and naming quality |
| Pass-2 render of placement | anchor type/placement honored vs re-resolved | Prove Pass-1 decision is honored, not recomputed |
| Run token cost | tokens, MOC count, heading bytes | Track the #45 cost regression against baseline |

---

## Constraints and Assumptions

### Constraints

- **2-pass model:** The placement decision must surface in the suggestions document for review
  before the confirm gate — this is the reason it lives in Pass-1, not Pass-2 render.
- **No new Hashi shape:** All emitted placements must use anchor/placement combinations the landed
  Hashi insert primitive (PR #65) already applies (heading/callout/line anchors; inside/before/
  after). Last-resort uses an H1-title heading anchor specifically to avoid a new shape.
- **Kado is the only vault surface:** Any MOC-structure read routes through Kado, never the
  filesystem (Constitution L1).
- **Constitution L2:** Relocating the insertion decision from Pass-2 to Pass-1 changes the
  Tomo↔Hashi interaction model and the suggestions/instructions contract → a Kokoro ADR /
  design-note must accompany the implementation.
- **Additive / near-MVP:** Hot-path pipeline scripts take additive changes; no breaking changes to
  existing inbox behavior (memory: `feedback_near_mvp_no_breakage`).
- **Single-user scope:** Validation targets Marcus's real vault and use case, not exhaustive
  synthetic coverage.

### Assumptions

- Candidate MOCs and their heading structure can be read/derived without a prohibitive Kado read
  storm (heading inventory is parsed where MOC bodies are already read — no new read calls).
- The note's dominant topic is available to Pass-1 to name a new section.
- The Hashi insert primitive (PR #65) remains the apply mechanism and its shapes are stable.
- Classification-layer MOCs are already identifiable (`is_classification`) and excluded upstream.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Heading-inventory enrichment inflates per-item Pass-1 token cost | Medium | High | Parse inventory at the existing MOC body-read site (no new Kado calls); cap/trim inventory; record regression and hand the shaping fence to #45 |
| Kado 429 from reading MOC bodies for inventory | Medium | Low | Reuse the existing body reads in the structure cache; no extra live reads on the hot path |
| Semantic heading-fit is wrong for a given note | Medium | Medium | Placement is shown and overridable in the suggestions doc with one edit (AC-11/AC-12); ambiguous-fit advisory (AC-16) |
| Tomo↔Hashi drift on a new emission shape | High | Low | 022 emits only already-applied shapes; close with a real Tomo→Hashi walk (AC-14/AC-15), per the standing "real walks > fixtures" rule |
| New-section path still unreachable in practice | High | Low | AC-14/AC-15 walk on a real MOC where no H2 fits is a hard acceptance gate |

## Open Questions

None blocking. All prior forks resolved and recorded in the spec README Decisions Log
(last-resort = H1 anchor; F-05 fenced; new-section named from topic; carrier = candidate_mocs[];
heading inventory parsed in the structure builder). Remaining technical mechanics (exact schema
field shapes, cost-trim option) are deliberately deferred to the SDD.

---

## Supporting Research

### Competitive Analysis

N/A — internal pipeline component of a single-user PKM system; no competitive product surface.

### User Research

Grounded in the owner's live vault and direct dialogue: verified that editable callouts
(`[!blocks] Key Concepts`) are scaffolding with content living under H2/H3 below them
(`Atlas/200 Maps/Systems Thinking (MOC).md`); confirmed the placement must be reviewable in the
2-pass model. Full agent-team findings (Requirements / Technical / Integration / UX, all file:line
grounded) are persisted in `research-synthesis.md` alongside this PRD.

### Market Data

N/A — internal tooling.
