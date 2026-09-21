---
title: "An occupied asset destination is a Pass-1 decision"
status: draft
version: "2.0"
---

# Product Requirements Document

> **v2.0 supersedes v1.0.** The first draft treated the defect as "a note must
> never be separated from its attachment" and proposed holding notes back, a
> fail-closed vault check, and a four-way remedy set. The owner scoped it down:
> the defect is that the collision reaches Hashi with no chance for the owner to
> have settled it, and the fix is to offer that chance with a working default.
> What happens between Pass 1, Pass 2 and apply is explicitly not modelled — see
> "The scoping principle" below.

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
| specId | 037-asset-destination-collision-is-a-pass1-decision |
| title | An occupied asset destination is a Pass-1 decision |
| status | COMPLETE |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 22 (15 Must · 4 Should · 3 Could) |
| openQuestions | 2 (neither blocking) |

### SectionStatus

| Section | Status |
|---------|--------|
| Product Overview | COMPLETE |
| User Personas | COMPLETE |
| User Journey Maps | COMPLETE |
| Feature Requirements | COMPLETE — 3 Must, 2 Should, 2 Could, 5 Won't |
| Detailed Feature Specifications | COMPLETE — F2, the decision surface |
| Success Metrics | COMPLETE |
| Constraints and Assumptions | COMPLETE |
| Risks and Mitigations | COMPLETE |
| Open Questions | COMPLETE |

---

## Product Overview

### Vision

When the name an attachment wants is already taken, the owner is told while they
are still reviewing — and the obvious fix is already ticked.

### Problem Statement

Tomo computes an attachment's destination from the configured asset folder and
the file's basename, and never asks the vault whether that name is free.

On the 2026-09-15 live run this produced an unappliable action.
`100 Inbox/Scans/karte.png` was to be filed at
`Atlas/290 Assets/295 Attachments/karte.png`, where a **different** 69-byte PNG
of that name already sat. Hashi refused it — *"Inconsistent state — both source
and destination present"* — which is correct and is why nothing was overwritten.

The defect is not the refusal. Hashi behaving as the last line of defence is the
design working. The defect is that the collision travelled all the way there
**with no point at which the owner could have settled it**. Nothing in Pass 1 or
Pass 2 mentioned it; the first signal was a red row in an executor's run log.

Measurable today: **1 of 1** colliding attachments reached apply time as a
failed action, and **0 of 1** were offered to the owner as a decision.

### Value Proposition

A name collision is the owner's call — only they know whether the incoming file
is the better copy, a redundant one, or a different picture that happens to
share a name. Today they are never asked.

Offering the choice in the suggestions document costs one tick and, because
renaming is the default, usually costs nothing at all: the common case resolves
itself and the run proceeds. The owner who wants a different outcome unticks it.

### The scoping principle

**We do not know what happens between Pass 1, Pass 2 and the moment Hashi
applies.** The owner may edit the vault, another tool may write, a second run
may claim the name. This spec therefore does not try to be airtight, and
deliberately declines to model the gap.

What it guarantees is narrower and sufficient: *no component overwrites data*.
Tomo never emits an action that would overwrite; Hashi refuses what it cannot
apply. Everything between those two facts is the owner's to resolve, with
enough information to do it.

This principle is why several defensive behaviours considered in v1.0 are now
explicit non-goals — a failed check, a stale conflict, and a conflict appearing
after review all resolve the same way: Hashi reports, the owner fixes.

## User Personas

### Primary Persona: The vault owner triaging their inbox

- **Demographics:** Single practitioner running Tomo against their own Obsidian
  vault; reviews a suggestions document by ticking checkboxes and does not read
  JSON.
- **Goals:** File inbox material without acquiring surprise duplicates or
  overwriting anything. Have the ordinary case need no attention. Be told when
  something needs attention.
- **Pain Points:** Learning about a conflict from an executor's error table
  after the fact. Being asked to decide things that have an obvious answer.

### Secondary Persona: Hashi, the instruction-set executor

Not a human, but a distinct consumer with its own contract, which the MiYo
constitution treats as documented interface.

- **Role:** Applies the instruction set deterministically, checking each
  action's preconditions first.
- **Goals:** Keep its precondition checks as the final authority. Report clearly
  what it refused and why, so the owner can fix it.
- **Pain Points:** None introduced by this spec — **Hashi is unchanged.** Its
  current behaviour on a collision is already correct and is relied upon here.

## User Journey Maps

### Primary User Journey: The collision that settles itself

1. **Awareness:** The owner opens the suggestions document. Among the decisions
   is an attachment-conflict entry naming the file and the occupied destination,
   with **rename already ticked**.
2. **Consideration:** For most collisions there is nothing to consider — the
   default is what they would have chosen.
3. **Adoption:** They leave it as it is.
4. **Usage:** Pass 2 emits a move to a free name and every embed names it.
5. **Retention:** Nothing failed, nothing was overwritten, and the run log shows
   what happened.

### Secondary User Journey: The collision the owner wants to handle themselves

1. **Awareness:** Same entry, but the owner recognises the occupying file and
   wants to sort it out by hand.
2. **Consideration:** They untick rename and tick either *keep in inbox* (leave
   the attachment where it is, no move attempted) or *ignore* (send the move
   anyway and let Hashi refuse it, so the report lands in the run log).
3. **Adoption:** The document warns that the conflict remains unresolved.
4. **Usage:** Pass 2 honours the choice. With *ignore*, Hashi's run log carries
   the refusal.
5. **Retention:** The owner resolves it in Obsidian and, if they wish, re-runs.

## Feature Requirements

### Must Have Features

#### F1: Tomo learns whether the destination is already taken

- **User Story:** As the vault owner, I want Tomo to notice that an
  attachment's destination name is occupied, so that the collision can be put in
  front of me instead of travelling to the executor unmentioned.
- **Acceptance Criteria:**
  - [ ] Given an attachment whose destination name is free, When Pass 1 runs, Then no conflict is raised and the run behaves exactly as it does today
  - [ ] Given an attachment whose destination name is occupied, When Pass 1 runs, Then a conflict is recorded naming the incoming file and the occupied destination
  - [ ] Given several attachments in one run, When Pass 1 runs, Then the vault is consulted once for the asset folder rather than once per attachment
  - [ ] Given a destination occupied by a name differing only in case, When Pass 1 runs, Then it counts as occupied, consistent with CON-6
  - [ ] Given the vault cannot be consulted, When Pass 1 runs, Then no conflict is raised and the run proceeds — the check degrades, it does not block

#### F2: The conflict is a decision in the suggestions document, with rename as the default

- **User Story:** As the vault owner, I want the conflict shown where I make
  every other decision and pre-set to the sensible answer, so that the ordinary
  case needs nothing from me and the unusual case is one untick away.
- **Acceptance Criteria:**
  - [ ] Given a run with at least one conflict, When the suggestions document is rendered, Then it contains an entry naming the incoming file, the occupied destination, and every note that embeds the file
  - [ ] Given any conflict entry, When it is rendered, Then exactly three remedies are offered — rename, keep in inbox, ignore — with **rename ticked**
  - [ ] Given an attachment embedded by several notes, When the document is rendered, Then the conflict appears once and one tick settles it for all of them
  - [ ] Given a run with no conflicts, When the document is rendered, Then no conflict section appears at all
  - [ ] Given the owner unticks rename without ticking another remedy, When the document is read back, Then the entry is treated as *ignore*

#### F3: Pass 2 honours the chosen remedy

- **User Story:** As the vault owner, I want my tick to be what happens, so that
  the document is a decision and not a notice.
- **Acceptance Criteria:**
  - [ ] Given rename is ticked, When Pass 2 renders, Then a move to a name free in the vault is emitted and every owning note's embed names that file
  - [ ] Given keep-in-inbox is ticked, When Pass 2 renders, Then no move action is emitted for that attachment and no action fails at apply time because of it
  - [ ] Given ignore is ticked, When Pass 2 renders, Then the move is emitted unchanged against the occupied destination, so Hashi refuses it and reports it
  - [ ] Given any remedy, When Pass 2 renders, Then no action is emitted that would overwrite the occupying file
  - [ ] Given the coverage audit runs on a run containing conflicts, Then expected and actual action counts agree and the audit passes

### Should Have Features

#### S1: The document says whether it is the same file

- **User Story:** As the vault owner, I want to know whether the file already
  there is the same picture, so that I do not accept a rename that gives me two
  copies of one image.
- **Acceptance Criteria:**
  - [ ] Given the occupying file is byte-identical to the incoming one, When the entry is rendered, Then it says so and notes that renaming will create a second copy of the same file
  - [ ] Given the occupying file differs, When the entry is rendered, Then it says a different file holds the name
  - [ ] Given the comparison cannot be made, When the entry is rendered, Then it says the files could not be compared, and the remedies are unchanged

#### S2: An unresolved conflict is called out

- **User Story:** As the vault owner, I want to be reminded that a conflict I
  did not rename away is still a conflict, so that I am not surprised by it
  later.
- **Acceptance Criteria:**
  - [ ] Given a conflict where rename is not ticked, When the document is rendered, Then the entry states that the conflict remains and names what will happen — the attachment stays in the inbox, or Hashi will refuse the move

### Could Have Features

#### C1: The proposed name is shown

- [ ] Given a conflict, When the entry is rendered, Then the rename remedy names the destination it would use
- [ ] Given the proposed name is itself occupied, When Pass 2 renders, Then the next free variant is used

#### C2: Pass 2's summary lists unresolved conflicts

- [ ] Given a run with conflicts not resolved by rename, When Pass 2 completes, Then its summary names each one rather than counting them

### Won't Have (This Phase)

- **Any change to Hashi.** Its refusal on a collision is already the correct
  behaviour and is what remedy *ignore* deliberately relies on.
- **Any change to the instructions document.** It stays exactly as it is; an
  owner who chose *ignore* resolves the conflict themselves afterwards.
- **Holding notes back because an attachment is unresolved.** Considered in
  v1.0 and rejected: it would hold a ready note over one picture, and the
  scoping principle says a note filed with an embed still pointing at the inbox
  is a state the owner can see and fix, not one worth blocking a run for.
- **A fail-closed vault check.** A failed check raises no conflict and the run
  proceeds. Hashi remains the guard.
- **Overwriting the occupying file.** Not offered, not reachable, not a default.
  The one guarantee this spec makes is that no component overwrites data.

## Detailed Feature Specifications

### Feature: F2 — The conflict as a decision

**Description:** The suggestions document gains a section that appears only when
a run has at least one attachment conflict. Each entry names one incoming file,
the destination it wants, the notes that embed it, and three remedies with
rename pre-ticked.

**User Flow:**

1. Owner opens the suggestions document after Pass 1.
2. System presents the conflict entry with rename ticked.
3. Owner leaves it, or unticks rename and ticks another remedy.
4. Pass 2 renders the consequence.

**Business Rules:**

- Rule 1: An attachment is deduplicated globally across the run, so one entry
  covers every note embedding that file and one tick settles all of them.
- Rule 2: Rename is ticked by default. This reverses v1.0's rule that nothing is
  pre-ticked: for this decision an obvious safe answer exists, and requiring a
  tick for it would make the common case cost attention it does not deserve.
- Rule 3: No remedy ticked, or rename unticked with nothing else ticked, means
  *ignore* — the move goes out unchanged and Hashi reports it. An owner who
  actively cleared the default gets the loudest of the three outcomes, not the
  quietest.
- Rule 4: More than one remedy ticked is an unsettled entry and is treated as
  *ignore*, with the same reasoning as Rule 3.
- Rule 5: A rename never targets an occupied name, in the vault or among the
  destinations this run already claims.
- Rule 6: Nothing in this section can delete or overwrite a file. The strongest
  outcome it produces is a move to a free name.

**Edge Cases:**

- Scenario 1: Two notes embed the same conflicted attachment → Expected: one
  entry, one tick, both notes treated alike.
- Scenario 2: The occupying file is byte-identical and rename stays ticked →
  Expected: the move proceeds to a free name; the document warned that this
  creates a second copy. That is a legitimate choice, not an error.
- Scenario 3: The destination folder does not exist → Expected: not a conflict.
- Scenario 4: The occupied name differs only in case → Expected: conflict.
- Scenario 5: The conflict is gone by Pass 2 → Expected: the plain move is
  emitted; a stale conflict changes nothing.
- Scenario 6: No conflict at Pass 1, one at apply → Expected: Hashi refuses and
  reports. Not modelled, by the scoping principle.
- Scenario 7: The destination is occupied by a folder → Expected: conflict,
  rename remains the sensible default.

## Success Metrics

### Key Performance Indicators

- **Owner agency:** Every collision that exists at Pass 1 appears as a decision
  in the suggestions document. Baseline: 0 of 1 on 2026-09-15.
- **Common-case silence:** A collision resolved by the default produces no
  failed action at apply time. Baseline: 1 failed action on 2026-09-15.
- **No overwrites:** Zero actions emitted whose destination holds a different
  file, except where the owner chose *ignore*. Baseline: 1 such action, not
  chosen.
- **Audit health:** The Pass-2 coverage audit passes on runs containing
  conflicts.
- **Cost:** One additional folder listing per run; content reads bounded by
  actual collisions.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Conflict detected | incoming path, destination, owning notes | Numerator for owner agency — proves detection ran |
| Remedy applied | destination, remedy, whether default or chosen | Separates "the default worked" from "the owner intervened"; feeds common-case silence |
| Move emitted against an occupied destination | destination | Must be zero unless the owner chose *ignore*; the no-overwrites KPI |
| Coverage audit outcome | expected, actual, conflict count | A run where these diverge is the Pass-2 abort this spec must not cause |
| Vault calls for conflict checking | listing calls, content reads | Cost KPI; catches a per-attachment probe creeping in |

## Constraints and Assumptions

### Constraints

- **Kado is the only vault surface** (MiYo Constitution, Privacy & Security L1).
- **The two-pass model is the approval mechanism** — but a pre-ticked default is
  still an approval mechanism: the owner reviews the document and can untick.
- **`instructions-diff` is a paired consumer** — an unaccounted action source
  aborts Pass 2 on a count mismatch. Not theoretical; it happened on 2026-09-15.
- **Hashi modifies, never creates** — a renamed attachment is a move of a staged
  file.
- **Near-MVP, additive only** — a run with no conflicts behaves identically.
- **The gap between passes is not modelled** — see the scoping principle.

### Assumptions

- Renaming is the right default for most collisions. If it turns out not to be,
  the cost is an untick, which is why the default is safe to assume rather than
  research.
- `path_exists` and `read_file_bytes` remain available on binary files through
  Kado. Verified live against a PNG on 2026-09-15.
- Hashi keeps refusing a move whose destination is occupied. Stated by the
  owner as a requirement of the design, not a guess about Hashi's roadmap.
- The asset folder is a single configured destination, so one listing suffices.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The pre-ticked default files a rename the owner did not want | Medium | Medium | The entry names the file and the destination, and S1 warns when renaming duplicates an identical file; the owner reviews the document before Pass 2 either way |
| An owner unticks rename and forgets the conflict exists | Low | Medium | S2 states in the entry what will happen instead; with *ignore*, Hashi's run log repeats it |
| Renaming leaves an embed pointing at the old name | High | Low | F3 puts the embed rewrite in the same criterion as the move — a rename that does not rewrite fails the criterion |
| Adding an action source breaks the coverage audit | High | Medium | F3's last criterion makes the audit's agreement an acceptance criterion |
| Collisions turn out to be frequent and the folder listing grows costly | Low | Low | One listing per run regardless of attachment count; content reads only on collision |

## Open Questions

- [ ] The rename scheme — numeric suffix (`karte-1.png`), run date, or owning
      note's stem. Affects C1 only.
- [ ] Whether *keep in inbox* should also suppress the owning note's filing, so
      note and file stay together. The owner has ruled that it need not, on the
      scoping principle; recorded here because it is the question most likely to
      come back after living with it.

---

## Supporting Research

### Competitive Analysis

Not applicable — a single-user tool. The relevant comparison is with how the
surrounding system already handles the same class of problem:

- **In-run collisions** (`_build_move_asset_actions`): detected, skipped,
  reported, never renamed automatically, never aborting the run.
- **Note destination clashes** (spec 034 T5.2): checked against the vault in the
  reducer and **renamed before the owner reads the document**. This spec's
  default is the same posture applied to attachments — the precedent already
  exists for the other file class.
- **Withheld MOC links** (`instruction-render`): an action whose target cannot
  be confirmed is not emitted, and the document says so.

### User Research

One observed run, 2026-09-15, executed by Hashi against the Privat-Test vault:
26 of 28 actions applied, `I05 move_asset` failed on the occupied destination.

The owner's scoping of the fix, recorded verbatim in intent: show the conflict in
the suggestions document with rename as the default, keep-in-inbox and ignore as
the alternatives; leave Hashi and the instructions document alone, since Hashi
already throws the right error and the owner can fix it from there; accept that
with the two non-rename remedies the attachment stays in the inbox, and say so in
the document. And the principle that bounds all of it — what happens between the
passes and the apply is unknown, so it need not be accounted for, as long as
neither the owner nor Hashi overwrites data.

### Market Data

Not applicable.
