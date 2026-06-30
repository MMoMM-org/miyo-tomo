---
title: "Suggestions document source-model unification (#33 / F-42 Phase 1)"
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

- [x] Problem is validated by evidence (live code + issue #33 decision log)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included (deferred to SDD)
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

The `/inbox` review surface speaks one word — **source** — for the input a note was
derived from, and lets the user keep or remove that source with a single, unambiguous
decision, even when the source is an audio + transcript pair.

### Problem Statement

The Pass-1 suggestions document presents an **ambiguous source-disposition decision**.
For each atomic-note item, `suggestions-reducer.py` renders four checkboxes:

```
- [x] Approve
- [ ] Keep origin (skip the implicit delete of the inbox source after move_note)
- [ ] Skip (keep in inbox)
- [ ] Delete source
```

Two of these — **"Keep origin"** and **"Delete source"** — both govern the disposition of
the same input file, under two different words (`origin` vs `source`). The internal fields
mirror the split: `keep_origin` / `origin_inbox_item` (origin) coexist with
`source_path` / `delete_source` (source). One concept, two names.

This is actively harmful for **voice items**, where the "source" is really **two files**:
the audio (`.m4a`) and the transcript (`.md`) the voice pipeline produced from it. Today a
confirmed voice item deletes only the transcript `.md`; the `.m4a` is silently left behind.
The consequence is measurable: **orphaned audio accumulates in the inbox** after every voice
capture, and the user cannot tell from the review document which file a checkbox governs.

### Value Proposition

One concept, one word, one decision. The user reviews a single **"Keep source"** control per
item and trusts that confirming the item removes *everything* that fed it — transcript and
audio together — while keeping the source is equally all-or-nothing. No orphaned audio, no
guessing which checkbox owns which file.

## User Personas

### Primary Persona: The vault owner (Marcus / MiYo pre-launch user)

- **Demographics:** Single power user of an Obsidian PKM; high technical expertise; reviews
  the Pass-1 suggestions document in Obsidian and signals decisions via checkboxes +
  frontmatter state (no tag pane, frontmatter hidden — state-machine-only UX).
- **Goals:** Triage the inbox quickly; trust that confirming an item cleans up its inputs
  without leaving residue; never have Tomo delete anything without explicit approval.
- **Pain Points:** Two words for one concept makes the review document harder to read;
  orphaned `.m4a` files pile up after voice captures and must be hand-deleted later.

### Secondary Personas

None. This is internal tooling for a single pre-launch user. The downstream **executor**
(Hashi / the user applying instructions) is a *consumer of the wire contract*, not a review
persona — captured under Constraints and the migration requirement, not as a review journey.

## User Journey Maps

### Primary User Journey: Confirm a voice capture and clean up its inputs

1. **Awareness:** A voice memo dropped into the inbox was transcribed by the voice pipeline
   (`.m4a` → sibling transcript `.md`); both sit in the inbox.
2. **Consideration:** During `/inbox`, the user opens the suggestions document and reads the
   item's single decision block — one Approve, one **Keep source** control, with the source
   shown as the `{transcript + audio}` set.
3. **Adoption:** The user leaves Approve checked and **Keep source unchecked** (the default —
   remove the inputs once the note exists).
4. **Usage:** On confirm, Pass-2 emits `delete_source` instructions for **both** the
   transcript and the audio. Tomo proposes; the user/Hashi applies. The inbox is left clean.
5. **Retention:** No orphaned audio is left behind; the user trusts the single decision and
   stops manually hunting for stray `.m4a` files.

### Secondary User Journeys

- **Keep the source:** User checks **Keep source** → neither the transcript nor the audio is
  proposed for deletion; both stay in the inbox.
- **Plain (non-voice) note:** Item has no audio peer → the single source decision governs just
  the one transcript/origin file, exactly as a normal note behaves today.

## Feature Requirements

### Must Have Features

#### Feature 1: Unified "source" terminology

- **User Story:** As the vault owner, I want one word — *source* — for the input a note came
  from, so that the review document is unambiguous.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a rendered suggestions document, When I read any item's decision block, Then no
    user-facing label contains the word "origin" (the keep control reads **"Keep source"**).
  - [ ] Given the parsed review state and the rendered instruction set, When I inspect the
    internal decision field, Then it is named with the `source` concept (no `keep_origin`
    field remains in the codebase outside backward-compat shims).
  - [ ] Given the consolidation/tag-handler blocks, When they render a keep control, Then they
    also read "Keep source" (consistent across all render sites, not just per-item atomics).

#### Feature 2: Single keep/delete decision per source

- **User Story:** As the vault owner, I want one keep/delete decision per item, so that I am
  never asked to reason about two checkboxes that mean the same thing.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an atomic-note item in the suggestions document, When I read its decision block,
    Then there is exactly **one** source-disposition control (no separate "Keep origin" *and*
    "Delete source" pair on the same item).
  - [ ] Given the default (Keep source unchecked), When the item is confirmed, Then the source
    is proposed for deletion (preserving today's default-delete-after-move behavior).
  - [ ] Given Keep source checked, When the item is confirmed, Then no `delete_source` is
    emitted for that item's source.

#### Feature 3: Voice source = {audio + transcript} set

- **User Story:** As the vault owner, I want a voice item's source to mean *both* the audio
  and its transcript, so that confirming the item removes both and leaves no orphaned audio.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a confirmed voice item whose transcript declares an audio peer, When Keep source
    is unchecked, Then Pass-2 emits `delete_source` for **both** the transcript `.md` and the
    audio file.
  - [ ] Given a confirmed voice item, When Keep source is **checked**, Then **neither** the
    transcript nor the audio is proposed for deletion.
  - [ ] Given a confirmed item with **no** audio peer, When Keep source is unchecked, Then
    exactly one `delete_source` (the transcript/origin) is emitted — identical to today.
  - [ ] Given a voice item, When Tomo renders the source, Then the source is displayed as the
    file *set* (transcript + audio), not a single ambiguous path.

#### Feature 4: Wire-field rename with a lockstep migration path

> **Decision (2026-06-30, ADR-3):** hard cutover, not a backward-compat shim. The single
> operator deploys Tomo + Hashi together ("Hashi will be in sync"). The documented migration
> path is **apply pending instruction sets, then upgrade both repos together** — there is no
> dual-accept window.

- **User Story:** As the operator, I want the rename to be clean (no alias debt) given that I
  deploy Tomo and Hashi together, with a documented procedure so no in-flight work is stranded.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an instruction document generated *after* this change, When it is validated
    against the schema, Then it uses `source_inbox_item` and passes; `origin_inbox_item` is no
    longer an accepted property.
  - [ ] Given the wire contract change, When the migration is documented, Then a Kokoro ADR
    records the breaking rename + the "apply-pending-then-upgrade-both" procedure, and a handoff
    is recorded to `miyo-tomo-hashi` (Hashi#41, apply side) to land in the same deploy.
  - [ ] Given Tomo emits `source_inbox_item` and Hashi accepts only `source_inbox_item`, When
    both are deployed together, Then move_note cleanup applies end-to-end.

#### Feature 5: Propose-only invariant preserved

- **User Story:** As the vault owner, I want Tomo to never delete anything itself, so that I
  retain final control over my vault.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given any source-deletion decision, When Pass-2 runs, Then Tomo emits `delete_source`
    *instructions* only and performs no filesystem deletion itself.

### Should Have Features

- Display the audio peer's filename/extension in the source set so the user sees exactly which
  audio file the decision governs (improves trust; not required for correctness).

### Could Have Features

- A batch-level summary line ("N source files proposed for deletion this run") in the
  instruction set's human-readable preview.

### Won't Have (This Phase)

- Broader Pass-2 checkbox-hierarchy redesign (Accept vs per-action vs FAN vs MOC toggles),
  per-item visual breaks, and related-item clustering — these are **#33 Phase 2** (UX pass),
  deferred to its own design-first effort.
- The Hashi **apply-side** implementation of the unified `{m4a + transcript}` deletion — lives
  in `miyo-tomo-hashi#41` (separate repo; coordinated via handoff).

## Detailed Feature Specifications

### Feature: Voice source = {audio + transcript} set

**Description:** When a confirmed item is a voice capture, the "source" it consumes is the pair
of files the voice pipeline produced: the original audio and its transcript. A single keep/
delete decision governs the pair. Unchecked (default) proposes deletion of both; checked keeps
both.

**User Flow:**
1. User reviews a voice item showing its source as `{transcript.md + audio.m4a}`.
2. System renders one **Keep source** control (unchecked by default).
3. User confirms the item (leaves Keep source unchecked).
4. System (Pass-2) emits `delete_source` for the transcript and the audio.

**Business Rules:**
- Rule 1: A source is a *set* of one or more files; the keep/delete decision applies to the
  whole set atomically (all kept or all proposed for deletion).
- Rule 2: An item's audio peer is included only when the item's transcript actually declares
  one; absent a declared peer, the set is the single transcript/origin file.
- Rule 3: Default (Keep source unchecked) preserves today's behavior: the move's source is
  proposed for deletion once all expected atomics for that source are represented.
- Rule 4: Tomo emits instructions only — never deletes.

**Edge Cases:**
- Scenario: Keep source checked on a voice item → Expected: neither file proposed for deletion.
- Scenario: Voice item with no declared audio peer → Expected: single-file source; behaves like
  a plain note.
- Scenario: Multiple atomics derived from one transcript → Expected: still one source-set
  decision; the existing completion gate (delete only after all expected atomics rendered)
  continues to hold, now covering the audio peer too.
- Scenario: Old-format instruction doc applied mid-migration → Expected: old field name still
  honored; no apply failure.

## Success Metrics

### Key Performance Indicators

- **Quality (primary):** Zero orphaned audio files in the inbox after a confirmed-and-applied
  voice item with Keep source unchecked (target: 0 strays; today: 1 stray per voice capture).
- **Clarity:** Zero occurrences of the word "origin" in user-facing review text and zero
  `keep_origin`/`origin_*`-named live fields (excluding the documented compat shim).
- **Safety:** 100% of source deletions emitted as instructions (no Tomo-side filesystem
  deletes) — invariant, not a trend.
- **Compatibility:** 100% of pre-change instruction documents continue to apply during the
  migration window.

### Tracking Requirements

This is a deterministic local tool; "tracking" = test assertions + the existing metadata-only
instruction-render telemetry (no analytics, per constitution).

| Event | Properties | Purpose |
|-------|------------|---------|
| `delete_source` emitted for voice item | count of files in the set (metadata only — paths/counts, no content) | Verify the audio peer joins the set |
| Suggestions doc rendered | presence/absence of "origin" tokens (test-time) | Verify terminology unification |
| Instruction set validated | schema pass/fail under old vs new field name | Verify migration compatibility |

---

## Constraints and Assumptions

### Constraints

- **Constitution L2 (Architecture):** The wire-field rename (`origin_inbox_item`) is a breaking
  change to a public inter-component contract (Tomo ↔ Hashi). It requires a documented
  migration path in Kokoro and a Hashi handoff; backward compatibility during the window is
  mandatory.
- **Constitution L1 (Testing):** Every filesystem/vault-mutation path and every keep/delete
  decision must be covered by tests proving *both* the delete and the keep (reject) outcome.
- **Tomo near-MVP:** Hot paths take additive changes where possible; avoid gratuitous breakage.
- **Deterministic rendering:** All document/instruction assembly stays script-driven, not
  LLM-assembled.
- **Propose-only:** Tomo never deletes; it emits `delete_source` instructions.

### Assumptions

- The transcript's audio peer is discoverable from data the pipeline already captures (the
  transcript's `source:` frontmatter, written by the voice pipeline and read during analysis);
  no new audio re-scan is required. *(Mechanism is an SDD concern; the PRD assumes the linkage
  exists.)*
- A bounded migration window is acceptable: both old and new field names are honored on apply
  for a defined period, after which the old name is retired in a follow-up.
- The single-user pre-launch scope means no large back-catalog of in-flight instruction docs —
  the compat window can be short.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Breaking wire rename strands in-flight instruction docs | High | Medium | Accept BOTH old and new field names on apply during a defined window; document migration in Kokoro; coordinate Hashi via handoff |
| Audio peer not actually available to the renderer | High | Medium | Confirmed in research that the link exists in the transcript's `source:` frontmatter; SDD defines the plumbing analyst→confirmed-item→renderer; fail safe = behave as single-file source if peer absent |
| Over-deletion (audio removed when user wanted to keep) | High | Low | Keep source = atomic opt-out for the whole set; tests prove the keep path suppresses BOTH files |
| Rename sweep misses a consumer → silent drift | Medium | Medium | Repo-wide `rg` sweep of every `origin`/`keep_origin`/`origin_inbox_item` consumer; schema `additionalProperties:false` surfaces stragglers |
| Scope creep into the Phase-2 UX redesign | Medium | Medium | Phase-2 items explicitly fenced into Won't-Have |

## Open Questions

- [x] ~~Migration window policy~~ — RESOLVED (ADR-3): hard cutover, no window; lockstep deploy +
  "apply pending first" procedure.
- [x] ~~Final new field name~~ — RESOLVED: `source_inbox_item`.
- [ ] Minor: remove the per-atomic "Delete source" box (junk delete-only stays in the
  skipped-items flow)? — confirm during SDD finalize.

---

## Supporting Research

### Competitive Analysis

N/A — internal PKM tooling for a single pre-launch user; no competitive surface.

### User Research

Evidence base is the live codebase (verified this session) and the issue #33 decision log
(2026-06-03), not external user studies:
- 4-checkbox ambiguity confirmed in `suggestions-reducer.py` (per-item decision block).
- Dual naming confirmed: `keep_origin`/`origin_inbox_item` vs `source_path`/`delete_source`.
- Audio peer exclusion confirmed in `_build_delete_source_actions` (the comment explicitly
  excludes audio + transcript peer pairs); the audio→transcript link is captured in the
  transcript's `source:` frontmatter by the voice pipeline.

### Market Data

N/A — see Competitive Analysis.
