---
title: "F-05 — Topic Weighting in MOC Matching"
status: draft
version: "1.0"
---

# Product Requirements Document

> Spec 029 · Issue #124 · Epic #17 (MOC Intelligence, P0) · Track MVP-Polish
> Source design: `docs/XDD/ideas/2026-07-03-f05-topic-weighting-moc-matching.md`
> Scope note: this PRD states WHAT/WHY only. The weighted-overlap formula, the shared scorer
> module, and the analyst-recipe wording are design decisions — deferred to the SDD.

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (observed live misfire, reported by the owner)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

When Tomo decides which Map of Content a captured note belongs to, it should trust what a note
is *about* (its title/heading themes) over words that merely *appear* in it — so notes land
under the right MOC and duplicate MOCs are not proposed on coincidental overlap.

### Problem Statement

Tomo's /inbox flow compares notes and MOCs by their extracted **topics**, treating every topic
as equally important (flat set overlap). A note that happens to share an incidental **content
keyword** with the wrong MOC can therefore be matched to it — even when the two disagree on
their **title-derived** themes. This misfire has been observed live by the vault owner, in two
places:

- **Proposed-MOC duplicate detection** ("this new cluster looks like an existing MOC") — the
  primary offender.
- **Existing-MOC link selection** ("link this item under MOC X") — also affected.

Consequences: wrong link suggestions the user must catch and reject, and suppressed or
mis-merged MOC proposals — both erode trust in Tomo's placement intelligence, which is the core
value of the MOC Intelligence epic (#17). The original inbox that produced the misfire is
archived and not trivially reproducible, so the fix is validated against the failure *pattern*
rather than the exact historical case.

### Value Proposition

Placement is the heart of Tomo's promised value: "Claude proposes, the user approves." Every
mis-placed suggestion is friction the user pays for. Weighting title themes above incidental
content keywords removes a class of confident-but-wrong matches at negligible cost — no new data
store, no schema change, no user-visible configuration. It is a precision upgrade to an existing
behavior, not a new surface.

## User Personas

### Primary Persona: The Vault Owner (Marcus, pre-launch)

- **Demographics:** Single power-user of a personal Obsidian vault; high technical expertise;
  runs Tomo's /inbox triage regularly; hides frontmatter and tag panes, so placement quality is
  judged through filenames, checkboxes, and the /inbox summary.
- **Goals:** Trust Tomo's MOC placement enough to approve suggestions quickly; avoid manually
  correcting wrong-MOC links; not have duplicate MOCs proposed for topics already covered.
- **Pain Points:** A confident wrong match is worse than no match — it costs attention to spot
  and undo. Incidental keyword overlap producing the wrong MOC is exactly this failure.

### Secondary Personas

The **/inbox pipeline itself** is a non-human consumer of matching: the deterministic
duplicate-detection scorer and the inbox-analyst agent both make placement decisions using topic
overlap. Both must apply the same weighting rule so the system is internally consistent.

## User Journey Maps

### Primary User Journey: /inbox triage placement

1. **Awareness:** The user captures notes into the vault inbox and runs /inbox.
2. **Consideration:** Tomo analyzes each item, extracts topics, and compares them against
   existing MOCs (to link) and against each other (to propose/merge MOCs).
3. **Adoption:** Tomo presents Pass-1 suggestions — which MOC each item links under, and whether
   a proposed new MOC duplicates an existing one.
4. **Usage:** The user reviews suggestions. With weighting, matches driven by title-theme
   agreement rank first; matches driven only by incidental content keywords no longer win.
5. **Retention:** Fewer wrong suggestions to reject → higher trust → faster approval loops.

### Secondary User Journeys

None. F-05 changes an existing step in one journey; it introduces no new entry point.

## Feature Requirements

### Must Have Features

The minimum for F-05 to be valuable: title-theme weighting applied consistently at **both**
match sites, with no regression to real duplicates and no disturbance to existing suppression
state.

#### Feature 1: Title-weighted duplicate detection (proposed MOCs)

- **User Story:** As the vault owner, I want proposed MOCs judged as duplicates only when they
  agree on their title themes, so incidental keyword overlap stops flagging unrelated MOCs as
  the same.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a proposed MOC and an existing MOC that overlap only on an incidental content
        keyword while their title themes differ, When duplicate detection runs, Then they are
        NOT flagged as duplicates.
  - [ ] Given a proposed MOC and an existing MOC that share their title themes, When duplicate
        detection runs, Then they ARE flagged as duplicates (no regression on real dups).
  - [ ] Given two notes where no topic on either side derives from a title, When duplicate
        detection runs, Then the match outcome is identical to the pre-F-05 (flat) behavior.
  - [ ] Given a note with an empty or missing title, When duplicate detection runs, Then it is
        scored without error using only base-weight topics.

#### Feature 2: Title-weighted MOC link selection (existing MOCs)

- **User Story:** As the vault owner, I want an item linked under the MOC whose title themes it
  shares, not a MOC it merely shares a stray keyword with, so link suggestions are right more
  often.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an inbox item whose title theme matches MOC-A and whose incidental content keyword
        matches MOC-B, When the analyst ranks candidate MOCs, Then MOC-A ranks above MOC-B.
  - [ ] Given the analyst's existing keep-behavior, When weighting is applied, Then the
        already-defined keep-threshold and top-N cap on candidates are preserved (weighting
        re-ranks, it does not change how many candidates are kept).
  - [ ] Given the analyst's non-thematic scoring adjustments (e.g. the depth bonus), When
        weighting is applied, Then those adjustments are preserved unchanged.

#### Feature 3: Zero-disturbance guarantee

- **User Story:** As the vault owner, I want the weighting change to not disturb anything I have
  already suppressed or any stored state, so I don't get a wave of re-surfaced or re-suppressed
  items after the upgrade.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an existing suppression (squelch) registry, When F-05 ships, Then the keys used to
        match suppressions are byte-identical to before (no re-suppression churn).
  - [ ] Given the discovery cache, When F-05 ships, Then no cache rebuild, schema change, or
        version bump is required.

#### Feature 4: Threshold validated, not assumed

- **User Story:** As the vault owner, I want confidence that the duplicate-detection threshold
  still separates true duplicates from incidental overlap under the new weighting, so the fix
  does not silently over- or under-merge.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the weighting change, When placement-confidence analysis is run against the
        personal vault, Then the current duplicate-detection threshold (0.80) is confirmed to
        still separate true duplicates from incidental overlap.
  - [ ] Given that analysis shows the threshold no longer separates correctly, When F-05 is
        finalized, Then the threshold is re-tuned to a value the data supports (rather than
        deferred).

### Should Have Features

- A synthetic regression fixture that encodes the observed misfire pattern (incidental overlap
  winning) so the guarantee in Feature 1 is locked against future regressions.

### Could Have Features

- Recovering the archived original inbox to replay the exact historical misfire as a
  higher-fidelity fixture (nice-to-have; the synthetic fixture is sufficient for launch).

### Won't Have (This Phase)

- **H3-heading topics** as an additional weighting signal (H1 ≈ title, H2 is structural
  boilerplate; H3 unmeasured) — separate investigation.
- **Config-driven weights** (weights sourced from vault-config) — deferred; values are fixed
  constants this phase.
- **Typed-topic provenance stored in the cache** (full extraction-time provenance) — heavier
  alternative, only if the title-derivation approach proves insufficient.
- **Standalone threshold re-derivation** beyond the in-scope validation in Feature 4.

## Detailed Feature Specifications

### Feature: Title-weighted matching (behavioral)

**Description:** Wherever Tomo compares two topic sets to make a placement decision, a topic that
reflects a note's **title theme** carries more weight than a topic that is merely an incidental
content keyword. The comparison still produces a single overlap score in the same 0–1 range and
is still compared against the same thresholds; only the relative influence of title-themed topics
increases.

**User Flow:**
1. User runs /inbox.
2. System extracts topics for each item/cluster and for candidate MOCs (unchanged).
3. System scores overlap, now giving title-themed topics greater influence than content
   keywords, at both the duplicate-detection site and the link-selection site.
4. System presents suggestions in which title-theme agreement outranks incidental overlap.

**Business Rules:**
- Rule 1: A topic counts as title-themed for a note when it corresponds to that note's title;
  otherwise it is a content keyword. (The exact correspondence test is an SDD decision.)
- Rule 2: When neither note contributes any title-themed topic, the score equals the pre-F-05
  flat-overlap score exactly (safe reduction).
- Rule 3: Both match sites apply the same weighting rule; they may differ in numeric precision
  (the deterministic site is exact; the analyst recipe is a simplified but directionally
  equivalent form) but must agree on the placement *decision* direction.
- Rule 4: Suppression keys and the discovery cache are unaffected by weighting.

**Edge Cases:**
- Empty/missing title on either side → that note contributes only content-keyword weight; scored
  without error. → Expected: graceful reduction toward flat behavior.
- Very long title (many title-themed topics on one side) → Expected: score stays bounded and
  sensible; no single note dominates purely by title length.
- Empty topic set on either side → Expected: no match (unchanged from today).
- Both sides have *different* title themes but share a content keyword → Expected: score is
  lower than flat overlap (this is the intended discrimination that fixes the misfire).

## Success Metrics

> This is a single-user, pre-launch tool; metrics are correctness-oriented, not adoption-oriented.

### Key Performance Indicators

- **Quality (primary):** Zero known wrong-MOC matches caused by incidental content-keyword
  overlap in a live /inbox run on the personal vault, with no new mis-merged or mis-linked true
  matches introduced (no regression).
- **Correctness of guarantees:** Squelch keys unchanged (0 re-suppression events attributable to
  F-05); no cache rebuild required.
- **Separation:** The duplicate-detection threshold demonstrably separates true duplicates from
  incidental overlap under weighting (Feature 4 validation).

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Duplicate-detection outcome (live /inbox run) | proposed MOC, matched MOC (if any), whether title themes agreed | Confirm incidental-overlap dups are rejected and real dups still caught |
| Link-selection ranking (live /inbox run) | item, ranked candidate MOCs | Confirm title-theme MOC outranks incidental-keyword MOC |
| Squelch-key comparison (pre/post F-05) | key set before vs after | Prove zero suppression churn |
| Placement-confidence analysis | score distribution vs threshold | Validate threshold separation (Feature 4) |

---

## Constraints and Assumptions

### Constraints

- **No cache/schema/signature change** — F-05 must not require a discovery-cache rebuild, a
  schema version bump, or any change to how suppression keys are computed.
- **Near-MVP, additive only** — this is a "Could"-tier refinement on a hot path close to MVP;
  changes must be additive and low-blast-radius, with no breakage of existing placement behavior.
- **Constitution L1 testing** — any code path affecting placement must cover both the correct
  (happy) and the rejection path with automated tests.
- **Single-user validation scope** — validation is against the owner's personal vault
  (pre-launch), not a broad user base.

### Assumptions

- A note's title reliably reflects its dominant theme (true for the owner's vault, where H1 ≈
  note title).
- Title information for both items and candidate MOCs is already available to both match sites
  (no new data needs to be gathered).
- The observed misfire is representative of the class of failures F-05 targets; a synthetic
  fixture modeling incidental-overlap-wins is a valid stand-in for the archived case.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Weighting lowers scores enough to drop a *true* duplicate below threshold | Medium | Low | Feature 4 threshold validation on real vault data before finalizing; true dups share title themes and are protected by Rule 2/3 |
| The two match sites diverge in behavior (deterministic vs analyst recipe) | Medium | Medium | Same rule and constants at both; acceptance criteria assert decision-direction agreement; analyst recipe audited |
| Title-theme correspondence test misclassifies a content keyword that also appears in the title | Low | Medium | Acceptable/desirable (a keyword that is also in the title is plausibly thematic); bounded by fixed max weight |
| Suppression churn if weighting accidentally touches key computation | High | Low | Feature 3 byte-identical squelch-key test; keys remain decoupled from weighting |

## Open Questions

- [ ] None blocking. The threshold decision is resolved (keep 0.80, validate in-scope per Feature
      4). Remaining items (H3 topics, archived-inbox replay, config-driven weights) are
      explicitly deferred in "Won't Have (This Phase)".

---

## Supporting Research

### Competitive Analysis

Not applicable — F-05 is an internal precision refinement to a personal PKM pipeline, not a
market-facing feature. The relevant prior art is Tomo's own MOC Intelligence epic (#17): spec
022 established insertion-point intelligence (WHERE inside a MOC); F-05 is the complementary
selection-scoring refinement (WHICH MOC), which 022 explicitly fenced out.

### User Research

Direct owner report: the misfire was observed live, "mainly on the proposed MOCs" (duplicate
detection) "but also with the normal MOCs" (link selection). This single high-signal report from
the sole user is the evidence base for the problem statement. Domain input also confirmed H1 ≈
note title and H2 = structural boilerplate in the owner's vault, informing the "Won't Have" scope.

### Market Data

Not applicable (single-user, pre-launch). The design alternatives, gap review, and spec review
are captured in the source brainstorm document (`docs/XDD/ideas/2026-07-03-f05-topic-weighting-moc-matching.md`).
