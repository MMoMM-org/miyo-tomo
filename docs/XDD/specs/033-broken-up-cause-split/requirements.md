---
title: "Say why a parent link is broken, and stop offering to delete the ones that work"
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

## Product Overview

### Vision

A garden audit earns its name by being trustworthy: everything it flags is worth acting on, and
every fix it offers is safe to accept. A finding the user must second-guess is worse than no
finding, because it spends the one thing the audit is asking for — their attention — and then
punishes them for giving it.

### Problem Statement

The audit calls a parent link **broken** whenever its target is not the name of a map-of-content
inside the folders being scanned. That single label is standing in for three different situations:

| what is actually true | is *"repoint it, or leave empty to remove"* the right advice? |
|---|---|
| The target note does not exist | **yes** — the link is dangling |
| The target exists, it just is not marked as a map | **no** — the link works; the *target* is what is untagged |
| The target exists outside the scanned folders | **no** — the scanner cannot see it; the vault is fine |

All three are presented identically: same wording, same checkbox, same offer to delete the link.

**Measured on the live vault, 2026-09-03** (359 scanned notes, 42 flagged):

- **20** point at a note that is present and readable — it simply carries no map tag.
- **22** point at something the scan cannot see. Of those, seven name one target by its short name,
  and an eighth records that same target by a **full path in a folder that is not being scanned**.
  So the target demonstrably exists; it is simply out of view.

That leaves **at most a handful** of the 42 where "this link is dangling" is a true statement. For
the large majority, accepting the offered fix **deletes a working parent link** — and does so
silently, because from the audit's point of view the user approved exactly what was proposed.

The damage is quiet and cumulative. Someone working down the list in good faith flattens hierarchy
they built on purpose: notes parented to notes, or parented across a folder boundary. Nothing errors.
Nothing warns. The structure is just gone, one approved checkbox at a time.

The cost of the current wording is not only the deletions it invites. It is also the findings it
buries: a genuinely dangling link sits in a list of 42, indistinguishable from 41 false alarms.

### Value Proposition

The audit stops guessing and starts saying which of the three it is. Two of the three stop offering
a destructive fix at all — and one of them turns into a genuinely useful suggestion, because the
fix for *"the parent is not marked as a map"* is to **mark the parent**, not to sever the link.
That inversion also scales in the user's favour: one tag can resolve several findings at once,
where the current advice would have required several deletions.

Everything the split needs is already in the audit's own data. This costs no additional vault
access, and the check stays as cheap as it is today.

---

## User Personas

### Primary Persona: The vault owner working through an audit report

- **Role:** Reads a garden-audit report and ticks the fixes they want applied.
- **Goals:** Leave the vault tidier than they found it; spend attention only where it pays.
- **Pain Points:** Cannot tell, from the report alone, whether a flagged link is really broken.
  Checking each one by hand defeats the purpose of the audit; not checking risks deleting good
  structure.
- **Technical Level:** Comfortable in their own vault; not expected to know how the scan decides
  what counts as a map.

### Secondary Personas

- **The vault owner whose hierarchy uses plain notes as parents.** Never intended their parent notes
  to be maps. Today every one of those links is reported as broken. They need the audit to stop
  calling a deliberate choice a defect — or, if it wants to argue the point, to argue it as advice
  rather than as a repair.
- **The vault owner with folders outside the audited scope.** Their links across that boundary are
  fine. They need the report to name the boundary rather than blame the link.

---

## User Journey Maps

### Primary User Journey: Deciding what to do about a flagged parent

1. Opens the audit report and reaches the broken-parent section.
2. Reads a finding and immediately sees **which of the three situations it is**.
3. For a dangling link: ticks the fix, as today.
4. For an untagged parent: reads the suggestion to tag the *target*, and notices it would settle
   several findings at once. No checkbox invites them to delete anything.
5. For an out-of-scope target: reads that the target is outside the audited area, and decides
   whether to widen the scope — a settings decision, not a note edit.
6. Applies the ticked fixes with confidence that nothing approved was a false alarm.

### Secondary User Journeys

- **Scanning for real problems only.** The user wants the handful of genuinely dangling links. They
  read the counts per situation and go straight to the one that matters, instead of triaging 42
  identical-looking entries.
- **Running an audit on a cache built before this change.** The report does not invent a cause it
  cannot know. It says so plainly and tells the user how to get the better answer.

---

## Feature Requirements

### Must Have Features

#### Feature 1: Each flagged parent carries which of the three situations it is

- **User Story:** As a vault owner, I want each flagged parent link to record *why* it was flagged,
  so that the report can tell me what is actually wrong.
- **Acceptance Criteria:**
  - [ ] Given a flagged link whose target is a known note inside the audited folders, When the audit
        runs, Then the finding records that the target exists but is not marked as a map.
  - [ ] Given a flagged link whose target is not present in the audited folders at all, When the
        audit runs, Then the finding records that the target was not found in the audited area.
  - [ ] Given a link whose target is a map, When the audit runs, Then it is not flagged — unchanged
        from today.
  - [ ] Given the audit runs, Then it performs no additional vault queries to reach these
        conclusions.

#### Feature 2: An untagged parent is advice, not a repair

- **User Story:** As a vault owner whose parent notes are ordinary notes, I want the audit to tell
  me the target is unmarked rather than offer to delete my link, so that following its advice
  cannot destroy structure I built on purpose.
- **Acceptance Criteria:**
  - [ ] Given a finding whose target exists but is not marked as a map, When the report is written,
        Then the finding appears as advice and not as an integrity defect.
  - [ ] Given such a finding, When the report is written, Then it offers **no** apply checkbox and
        **no** repoint field, so nothing destructive can be approved.
  - [ ] Given such a finding, When the report is written, Then the suggestion names the **target**
        as the thing to change — mark it as a map — and not the link.
  - [ ] Given several findings share one unmarked target, When the report is written, Then the
        suggestion makes clear that one change settles all of them.
  - [ ] Given such a finding is approved along with the rest of the report, When fixes are applied,
        Then no instruction touching that note is produced.

#### Feature 3: An out-of-scope target is described as out of scope

- **User Story:** As a vault owner with notes outside the audited folders, I want the report to say
  the target was not found in the audited area, so that I do not read a scanning limit as a broken
  link.
- **Acceptance Criteria:**
  - [ ] Given a finding whose target is not present in the audited folders, When the report is
        written, Then it states the target was not found **in the audited area** rather than
        asserting the note does not exist.
  - [ ] Given such a finding, When the report is written, Then it points at the audited scope as
        something the user can widen.
  - [ ] Given such a finding, When the report is written, Then the remove and repoint fix remains
        available, because a genuinely dangling link is inside this group.

#### Feature 4: Today's behaviour survives for everything else

- **User Story:** As a vault owner who already relies on the audit, I want the rest of the report
  to behave exactly as before, so that this change costs me no relearning.
- **Acceptance Criteria:**
  - [ ] Given a finding in the out-of-scope group, When a fix is approved and applied, Then the
        instruction produced is the same one today's audit would have produced.
  - [ ] Given any other audit check, When the audit runs, Then its findings, counts and wording are
        unchanged.
  - [ ] Given a run with no flagged parents at all, When the report is written, Then it is
        unchanged from today.

#### Feature 5: A report says how many of each, so the user can triage

- **User Story:** As a vault owner, I want to see at a glance how the flagged parents divide across
  the three situations, so that I can go to the ones that matter.
- **Acceptance Criteria:**
  - [ ] Given flagged parents in more than one situation, When the report is written, Then it
        states the count per situation.
  - [ ] Given flagged parents in exactly one situation, When the report is written, Then the
        breakdown does not claim a division that does not exist.
  - [ ] Given no flagged parents, When the report is written, Then no breakdown line appears.

#### Feature 6: An older audit cache degrades instead of guessing

- **User Story:** As a vault owner who has not refreshed the audit's index, I want the report to
  admit it cannot tell which situation applies, so that it never states a cause it does not know.
- **Acceptance Criteria:**
  - [ ] Given an index built before this change, When the audit runs, Then no finding claims a
        situation it cannot determine.
  - [ ] Given an index built before this change, When the report is written, Then it says the index
        predates the distinction and how to refresh it.
  - [ ] Given an index built before this change, When the report is written, Then no finding offers
        a fix that would be wrong for two of the three situations.

### Should Have Features

- **A suggestion the user can act on directly.** Where the fix is *"mark the target as a map"*, the
  report could carry the target's name in a form the user can copy, rather than making them find
  the note first.
- **Grouping by shared target.** Several findings pointing at one unmarked parent could be presented
  together rather than repeated, so the single action needed is obvious.

### Could Have Features

- **Counting the saved deletions.** Reporting how many destructive fixes this change withheld would
  make the value visible, but nothing depends on it.

### Won't Have (This Phase)

- **Splitting "not found in the audited area" into *missing* versus *outside the scope*.** Deciding
  which requires looking beyond the audited folders, and this check is deliberately built to answer
  from its own index without reaching into the vault. Under-claiming is the correct behaviour here;
  a confident wrong answer is what this spec exists to remove.
- **Applying the tag automatically.** Marking a note as a map changes how the whole vault is read.
  That is the user's decision, and this phase only surfaces it.
- **Changing which notes count as maps.** The definition is configuration, not a defect, and is out
  of scope.
- **Widening the audited scope.** The report may point at the setting; it does not change it.

---

## Detailed Feature Specifications

### Feature: An untagged parent is advice, not a repair

**Description**

Today, a link whose target exists but is not marked as a map produces an integrity finding with an
apply checkbox and a repoint field. Approving it deletes the link. This is the single largest group
in the measured population (20 of 42), and the fix is wrong for every one of them.

After this change the finding still appears — the user should know their parent is not a map, since
that is what makes the note invisible to map-based navigation — but it appears as **advice**, with
the suggested action pointing at the target.

**User Flow**

1. The user reaches the advisory part of the report.
2. They read that a parent note is not marked as a map, and which notes are affected by it.
3. They decide: mark it, or accept it as-is.
4. If they approve the report as a whole, nothing about these notes is modified.

**Business Rules**

- An advisory finding never carries an apply checkbox or a repoint field.
- The suggested action names the *target*, never the referencing note.
- Approving a report with advisory findings produces no instruction for them.
- Where several findings share one target, the report makes the one-action-settles-many
  relationship explicit.

**Edge Cases**

- **The target is not a map but is also flagged for something else.** Both findings stand; they are
  about different notes and different problems.
- **The target's name is ambiguous** — two notes share it. Out of scope here; the existing
  duplicate-name check owns that.
- **Every flagged parent is advisory.** The integrity part of the report has no broken-parent
  entries at all, and must read correctly rather than showing an empty section.
- **The user marks the target as a map, then re-runs.** The findings disappear on the next index
  refresh, not immediately — the report should not imply otherwise.

---

## Success Metrics

### Key Performance Indicators

- **No destructive fix is offered for a link that works.** On the measured population, the count of
  approvable delete-or-repoint offers drops from 42 to the out-of-scope group alone.
- **The report distinguishes all three situations on real data**, with counts that add up to the
  total flagged.
- **The audit makes no additional vault queries** — measured the same way spec 032 measured it.
- **Everything outside broken parents is byte-identical**, demonstrated by comparison against the
  current output rather than by tests continuing to pass.

### Tracking Requirements

- Record the per-situation counts from the first live run in the audit's own report, so the
  before/after comparison is visible without extra instrumentation.
- Record the cost outcome in the run cost log, as spec 032 did.
- Note in the spec whether the advisory suggestion actually led to a tag being added — the one
  metric that says whether the inversion was useful rather than merely safe.
