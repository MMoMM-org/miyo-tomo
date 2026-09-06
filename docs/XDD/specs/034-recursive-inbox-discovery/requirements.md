---
title: "Recursive inbox discovery"
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
| specId | 034-recursive-inbox-discovery |
| title | Recursive inbox discovery |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 24 |

---

## Product Overview

### Vision

A note is in the inbox if it is anywhere under the inbox folder — not only if it happens
to sit at the top level.

### Problem Statement

Notes filed into inbox subfolders are silently invisible to Tomo. `discover_files`
(`tomo/scripts/inbox-triage.py:172`) lists the inbox at `depth=1`, so a note at
`100 Inbox/Places/Dresden.md` is never partitioned, never analysed, and never appears in a
suggestions document. Nothing reports this. The note simply never shows up, and the user
has no way to tell "Tomo considered it and declined" from "Tomo never saw it".

The problem is measurable and was measured. Spec 031's T6.5 live validation (2026-09-05)
placed four test notes in `100 Inbox/Places/` and produced **zero** attachment output. The
resolution layer had done its work correctly for all of them — `resolved-attachments.json`
was right — but not one note had been discovered, so nothing downstream could use it.

Two consequences follow:

- **Wasted work every run.** The attachment resolver added by spec 031 uses
  `list_notes(inbox_path, fields=["links"])`, which *is* recursive. So Tomo already resolves
  attachments for notes it will never triage, every pass (#164).
- **The specification describes something impossible.** Spec 031's acceptance criterion
  AC-F2.1 and its SDD walkthrough both use `100 Inbox/Places/Dresden.md` as a source note
  (#163). The documents were written against the behaviour a reader would reasonably expect.

Marcus confirmed on 2026-09-05 that he does organise the inbox into subfolders. The
documents are right; the pipeline is too narrow.

### Value Proposition

The user gets to organise their inbox the way they already think about it, instead of
flattening it to accommodate a tool. Nothing else in the workflow changes: the same
review document, the same two-pass approval, the same apply step. The feature is
invisible when it works — notes simply stop disappearing.

## User Personas

### Primary Persona: The vault owner

- **Demographics:** Single user, owns the Obsidian vault Tomo operates on. High technical
  expertise — writes the specs, reads the code, runs the pipeline by hand. Uses Tomo daily
  through `/inbox`, not through an API.
- **Goals:** Capture into the inbox freely, in whatever structure suits the material, and
  have Tomo triage all of it. Trust that "not in the suggestions document" means "Tomo
  decided against it", never "Tomo could not see it".
- **Pain Points:** Notes filed into a subfolder vanish from the workflow with no signal.
  The failure is silent, so it is discovered late — in this case only when a deliberate
  test placed fixtures in a subfolder and produced nothing.

### Secondary Persona: The maintainer

The same person in a different role — not a second user, but a second set of needs, and the
reason one decision in this spec deliberately took the more expensive route.

- **Demographics:** The vault owner reading their own code months later, or an AI agent
  reading it in a fresh session with no memory of why anything is as it is. High expertise,
  zero context.
- **Goals:** Understand what a field holds by reading its name, and trust that a name which
  once described its content still does.
- **Pain Points:** A name that has quietly outlived its meaning. This cost real time twice
  in the week this spec was written — a renderer that no longer rendered anything, and a
  parser branch that could not be reached. Both were found late, and both by reading rather
  than by any test.

## User Journey Maps

### Primary User Journey: Capturing into a structured inbox

1. **Awareness:** The user files a captured note into `100 Inbox/Places/` because it
   belongs with other place notes. They expect the next `/inbox` run to pick it up.
2. **Consideration:** No alternative is evaluated — the user is not choosing a tool, they
   are using the one they built. The only alternative available today is to flatten the
   inbox, which is what the current behaviour silently forces.
3. **Adoption:** No adoption step. The feature ships and the note is discovered on the next
   run; there is nothing to enable or configure.
4. **Usage:** `/inbox` → the subfolder note appears in the suggestions document alongside
   root-level notes, indistinguishable in treatment → the user reviews and approves →
   `/inbox` for Pass 2 → apply. Attachments file to the asset folder as they already do
   for root-level notes.
5. **Retention:** The user stops thinking about inbox structure at all, which is the
   point. Success here is the absence of a workaround.

### Secondary User Journey: Two notes that share a name

The user has `100 Inbox/Places/Dresden.md` and `100 Inbox/Reise/Dresden.md`. Both are
distinct notes about different things. They expect both to be triaged independently and
both to survive the run — and, critically, they expect never to find that one of them
overwrote the other's result, or that the wrong one was marked as captured in the vault.

### Secondary User Journey: Reading the code later

1. **Awareness:** The maintainer opens a file they have not seen in months, or an agent
   opens it with no prior context, and needs to know what identifies an inbox item.
2. **Consideration:** They read the field name and the schema. There is no other source —
   the WHY documentation explains decisions, not field semantics.
3. **Adoption:** Not applicable; they are not choosing anything.
4. **Usage:** They rely on the name. If it says "stem", they will assume a bare filename and
   write code on that assumption.
5. **Retention:** Success is that they never discover, through a defect, that the name was
   lying.

## Feature Requirements

### Must Have Features

#### Feature 1: Notes in inbox subfolders are discovered and triaged

- **User Story:** As the vault owner, I want a note anywhere under the inbox folder to be
  triaged, so that I can organise my inbox without notes silently disappearing.
- **Acceptance Criteria:**
  - [ ] Given a note at `100 Inbox/Places/Dresden.md` with no `tomo` frontmatter, When
        `/inbox` runs Pass 1, Then it appears in the suggestions document as a source item
  - [ ] Given notes at both `100 Inbox/Root.md` and `100 Inbox/Sub/Nested.md`, When
        `/inbox` runs Pass 1, Then both appear and receive the same kind of treatment —
        depth is not visible in the output
  - [ ] Given a note nested two levels deep at `100 Inbox/A/B/Deep.md`, When `/inbox` runs
        Pass 1, Then it is discovered — the recursion has no depth limit
  - [ ] Given an inbox with only root-level notes, When `/inbox` runs Pass 1, Then the
        resulting suggestions document is unchanged from before this feature — no
        regression for the flat case
  - [ ] Given a non-note file in a subfolder such as `100 Inbox/Images/karte.png`, When
        `/inbox` runs Pass 1, Then it is not partitioned as a source item, exactly as a
        root-level image is not today

#### Feature 2: Two notes sharing a filename are handled independently

- **User Story:** As the vault owner, I want two same-named notes in different subfolders
  to be triaged independently, so that neither silently destroys the other's result.
- **Acceptance Criteria:**
  - [ ] Given `100 Inbox/Places/Dresden.md` and `100 Inbox/Reise/Dresden.md` both new,
        When Pass 1 runs, Then two distinct suggestions appear, one per note
  - [ ] Given the same two notes, When the per-item analysis completes, Then each note's
        result is preserved — neither overwrites the other
  - [ ] Given the same two notes, When one is approved and the other is not, Then only the
        approved one is acted on and only its source note is marked in the vault
  - [ ] Given the same two notes, When the run completes, Then the run state records a
        distinct outcome for each — one note's status never masks the other's
  - [ ] Given the same two notes both approved, When the coverage audit runs, Then it
        accounts for two items, not one — it must not report full coverage by collapsing
        them
  - [ ] Given a note at `100 Inbox/Places/Dresden.md` with no explicit title, When the
        suggestions document is rendered, Then its suggested name reads `Dresden` — never a
        path-derived string
  - [ ] Given the same note, When the suggestions document is rendered, Then its source
        link reads `[[Dresden]]` — never a path-derived string
  - [ ] Given the same note, When it is approved and applied, Then the note created in the
        vault is titled from the filename or its own frontmatter, never from the internal
        identifier

  *Business context: today the per-item result file, the append-only run state, and the
  coverage audit are all addressed by bare filename. The last criterion is deliberately
  phrased as a counting requirement because the current failure mode is a false pass, not
  an error.*

#### Feature 3: Marking a source note as captured targets the right note

- **User Story:** As the vault owner, I want the "captured" mark written to the note it
  belongs to, so that a name clash never corrupts my vault.
- **Acceptance Criteria:**
  - [ ] Given two same-named notes in different subfolders and only one approved, When the
        run marks sources as captured, Then the frontmatter is written to the approved
        note only and the other note is untouched
  - [ ] Given a name clash of any kind, When the pipeline cannot address a source note
        unambiguously, Then it declines to write rather than guessing

  *This is the only requirement in this spec whose failure mutates user data. A wrong write
  here is worse than no write, and the second criterion states that preference explicitly.*

#### Feature 4: Force Atomic works for a note in a subfolder

- **User Story:** As the vault owner, I want **Force Atomic Note** to work on a subfolder
  note, so that the escape hatch is available everywhere the note is.
- **Acceptance Criteria:**
  - [ ] Given a suppressed suggestion for `100 Inbox/Places/Dresden.md`, When the user
        ticks **Force Atomic Note** and re-runs, Then the atomic proposal is built from
        that note's actual content
  - [ ] Given the same, When the proposal is approved and applied, Then the resulting note
        reflects the subfolder note, not some other document

  *Business context: this fails today for a single subfolder note with no name clash at
  all — a second, independent defect from the one Feature 2 addresses.*

#### Feature 5: Audio files match their transcript by note, not by name alone

- **User Story:** As the vault owner, I want an audio file paired with its own transcript,
  so that an unrelated same-named note elsewhere does not make Tomo think the audio is
  already handled.
- **Acceptance Criteria:**
  - [ ] Given `100 Inbox/memo.m4a` with no transcript, and an unrelated
        `100 Inbox/Archive/memo.md`, When Pass 1 runs, Then the audio is still treated as
        needing transcription
  - [ ] Given `100 Inbox/Voice/memo.m4a` and its transcript `100 Inbox/Voice/memo.md`,
        When Pass 1 runs, Then the pair is recognised and the audio is not re-transcribed

#### Feature 6: Every run records how much it cost

- **User Story:** As the vault owner, I want each run to report its item count and cost, so
  that a future decision about limits can be made from data rather than a guess.
- **Acceptance Criteria:**
  - [ ] Given any `/inbox` Pass 1, When it completes, Then the item count and the Kado call
        count are reported in the run output
  - [ ] Given a run notably larger than previous ones, When it completes, Then its figures
        are recorded in `docs/evolution/inbox-cost-log.md` alongside existing entries in
        the same format

  *No volume cap is specified — see Won't Have. This feature exists so that the absence of
  a cap is an observed choice rather than an unexamined one.*

### Should Have Features

#### Feature 7: Discovery does not cost an extra vault listing

- **User Story:** As the vault owner, I want recursion not to make my runs more expensive.
- **Acceptance Criteria:**
  - [ ] Given any Pass 1, When it completes, Then the number of directory listings of the
        inbox is no greater than before this feature
  - [ ] Given the measured baseline of 3 base Kado calls per run, When Pass 1 completes
        after this change, Then the base call count is 3 or fewer and the actual figure is
        recorded

  *A recursive listing of the inbox already happens every run for attachment resolution.
  Whether it can serve discovery as well is a design question for the SDD; the requirement
  here is only that the user's cost does not rise.*

### Could Have Features

#### Feature 8: The two file-type checks agree

Two places decide "is this entry a file" using different comparisons, one tolerant of
casing and one not. No live divergence exists — the vault gateway emits a fixed lowercase
value — so this is robustness, not a fix. Worth doing only if the two checks end up
sharing input.

- [ ] Given a directory listing entry whose type differs only in letter case, When both
      checks run, Then they agree on whether it is a file

### Won't Have (This Phase)

- **A cap on items per run.** No limit exists today, and the unbounded behaviour already
  applies to a flat inbox with many untriaged notes — recursion reveals a backlog rather
  than creating one. The largest clean run on record is 21 items; there is no measurement
  above that to set a limit from. Feature 6 gathers the data instead. *(Decision:
  2026-09-06.)*
- **A subfolder exclusion mechanism.** None exists for the inbox today, and attachment
  folders contain no notes, so it would be new surface for a problem that has not occurred.
  *(Decision: 2026-09-06.)*
- **Changes to how the sibling component resolves a source note.** Two same-named notes
  still produce indistinguishable source references, which affects that component's linking
  and its matching between a suggestion and a daily-log entry. Handed off rather than solved
  here. Note that the component's own code already records bare-name ambiguity as an
  accepted limitation of its current version — the handoff tells its owner that the
  limitation got wider, it does not report a new defect. *(Decision: 2026-09-06.)*
- **Bounding the in-memory size of a directory listing.** The vault gateway pages its
  responses correctly; the client merges all pages eagerly. That is a pre-existing
  consumer-side memory characteristic, not introduced by this feature.

## Detailed Feature Specifications

### Feature: Two notes sharing a filename are handled independently

**Description:** Every stage of the pipeline that needs to refer to "which inbox note is
this" currently does so by bare filename. That is unambiguous only because a flat folder
cannot hold two files with the same name. Once notes can live in subfolders, the assumption
fails, and it fails silently at every stage: results overwrite each other, run state
records one outcome for two notes, the coverage audit counts one where there are two, and
the vault gets a mark written to the wrong note.

This feature requires that an inbox note is addressed by something that is unique across
the whole inbox subtree, and that the name of that thing says what it is.

**User Flow:**

1. User files two notes with the same filename into different inbox subfolders.
2. System discovers both and treats them as two separate items throughout.
3. User sees two suggestions and decides on each independently.
4. System applies only what was approved, to the note it belongs to.

**Business Rules:**

- Rule 1: Two distinct inbox notes must never be addressed by the same identifier, at any
  stage of a run.
- Rule 2: An identifier must be derivable from the note's location alone, without
  consulting run state — the same note yields the same identifier in Pass 1 and Pass 2.
- Rule 3: Where the pipeline stores per-item output as a file, the filename must be safe on
  the filesystem and must not collide for two distinct notes.
- Rule 4: The identifier that makes items distinct and the text shown to the user must be
  two separate things. Today one field does both jobs, and they look like one job only
  because a flat folder makes a filename unique. They must be split: a distinct identifier
  for addressing, and a plain filename for anything a person reads.
- Rule 5: No user-visible text may be derived from the addressing identifier. Note titles
  and the source links in the review document must continue to read as plain filenames.
  *(Decision: 2026-09-06 — the field is renamed rather than repurposed, accepted with its
  versioning cost. Splitting is the form that decision has to take, because the existing
  field feeds both a machine join and a rendered title.)*
- Rule 6: Where an identifier is passed to another component that expects a bare filename,
  it must still be a bare filename at that boundary. This spec does not change what other
  components receive.
- Rule 7: When the pipeline cannot address a source note unambiguously, it must decline the
  operation rather than choose. Silence is preferable to a wrong write.
- Rule 8: Every stage that derives the addressing identifier must derive it the same way.
  Two stages computing it differently would reintroduce, in a harder-to-see form, the exact
  defect fixed in #165 — a proposal that parses correctly into a lookup nothing then reads.

**Edge Cases:**

- Two notes with the same name in different subfolders → Expected: two independent items,
  both surviving the full run.
- Three or more notes with the same name → Expected: the same, with no special-casing of
  the two-note situation.
- A note whose path contains characters awkward in a filename → Expected: the derived
  identifier is still filesystem-safe, and still unique.
- A run interrupted between Pass 1 and Pass 2, with per-item output from an older run still
  present → Expected: stale output from a previous run is not mistaken for this run's, and
  a missing item is reported rather than skipped in silence.
- The identifier's format changes between Pass 1 and a later Pass 2 within the same session
  → Expected: the affected item is reported as missing. Today this path skips silently, so
  an item would simply vanish from the run with no message — this must become a report, not
  a gap.
- A subfolder note and a root note with the same name → Expected: treated as two items, no
  precedence given to the root one.
- The same note discovered twice within one run → Expected: one item, not two.

## Success Metrics

### Key Performance Indicators

*Deviation from the standard checklist, stated rather than papered over: adoption,
engagement, and business-impact KPIs do not apply. Tomo has one user, who is also its
author — there is no acquisition funnel, no usage-frequency target, no revenue. Inventing
numbers for those categories would make this document less trustworthy, not more complete.
What follows is correctness and cost, which is what actually decides whether this feature
succeeded.*


- **Correctness (primary):** A note placed in an inbox subfolder appears in the suggestions
  document. Target: 100%. This is the whole feature; anything less is a failure, not a
  degraded success.
- **No silent loss:** Number of items whose per-item output is overwritten, or whose run
  state is masked by another item. Target: zero, verified by a run containing a deliberate
  name clash.
- **No wrong vault writes:** Number of "captured" marks written to a note that was not the
  approved source. Target: zero. Measured by inspecting frontmatter after an apply in a
  clash scenario.
- **Cost does not rise:** Base vault calls per Pass 1. Target: no greater than the current
  3, measured against the 2026-09-05 baseline of `kado_calls=20` for a 4-item run.
- **No regression for flat inboxes:** A run over a root-only inbox produces the same
  suggestions document as before. Target: identical output.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Pass 1 completes | item count, base call count, total Kado call count | Feeds the cost log; establishes whether recursion changed cost, and gathers the data a future limit would need |
| Item discovered | note path, depth relative to inbox root | Distinguishes "declined" from "never seen" — the exact ambiguity this feature removes |
| Identifier collision avoided | the two note paths involved | Proves the clash case actually occurred in a validation run rather than being assumed |
| Source note marked captured | note path written to | Verifies the write landed on the intended note |
| Per-item output missing at read time | expected identifier | Surfaces the stale-run and interrupted-run edge cases, which currently pass in silence |

Cost figures are recorded in `docs/evolution/inbox-cost-log.md`, in the format the existing
entries use.

---

## Constraints and Assumptions

### Constraints

- **Single-user, local-first.** No multi-user coordination, no network surface. Vault access
  goes through the existing gateway; this spec adds no new one.
- **The two-pass approval model is unchanged.** Tomo proposes, the user approves, and only
  then is anything applied. Recursion widens what is proposed, never what is applied
  without consent.
- **The boundary to sibling components stays as it is.** Whatever identifier this spec
  introduces internally, other components continue to receive what they receive today.
- **Renaming the identifier field is a versioned change** across the artefacts that carry
  it, and the analyst's written contract changes with it. Accepted deliberately rather than
  taking the cheaper value-only change.
- **Live validation is the user's to run**, against their own vault, as with every prior
  spec. Implementation cannot self-certify this feature.

### Assumptions

- Inbox subfolders hold notes the user wants triaged. Verified by asking, 2026-09-05 — not
  inferred from the folder layout.
- Attachment-only subfolders contain no notes today. If that changes, the absence of an
  exclusion mechanism becomes visible, and the decision to omit one gets revisited.
- The inbox is small enough that a recursive listing is not itself a problem. Unverified
  for very large vaults; Feature 6 exists to notice if that assumption breaks.
- No note relies on being invisible to Tomo by virtue of sitting in a subfolder. If the
  user has been using subfolders as a hiding place, this feature ends that, and the first
  run will show it.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A stage that addresses notes by bare filename is missed, and fails silently | High — silent data loss, or a wrong vault write | Medium — the sites are spread across many files and several are not obvious | Enumerate every one during design and cover each with a test that fails on collision; treat a missed site as the defect this spec exists to prevent |
| A first run over a long-hidden backlog produces an overwhelming review document | Medium — the user faces an unreviewable list | Medium — depends entirely on the user's actual inbox, which is unmeasured | Accepted deliberately, no cap. Feature 6 measures it; a limit can follow from data |
| The identifier rename is applied to some artefacts and not others | High — a partial rollout fails silently rather than loudly, because nothing validates the shape | Medium | Change every carrier together in one step; a validation gate should reject the old field name rather than tolerating both |
| Recursion widens name-based matching elsewhere in ways not yet found | Medium | Low — the known cases are enumerated, but the enumeration may be incomplete | Search for name-based matching as a class during design, not just the known instances |
| The sibling component's own matching becomes ambiguous for clashing names | Low — display and linking, not data loss | Medium | Handed off so the owning component can decide; documented as a known limitation here |
| An item silently vanishes when per-item output written before a change is looked up after it | Medium — a note disappears from a run with no message | Medium — the window exists whenever the format changes mid-session, and the lookup already skips missing files without warning | Make the missing-file case report rather than skip; cover it with a test that exercises the window directly |
| Live validation is skipped and the feature ships unproven | High — this exact failure produced spec 031's fixture error | Low — the recent precedent is fresh | The spec is not complete until a live run over a real subfolder note passes |

## Open Questions

- [ ] Does the user's real inbox already contain subfolder notes, and how many? This
      determines whether the first run is uneventful or is a large backlog. Not measurable
      from here — the real vault is not accessible to this session.
- [ ] Should a note that becomes visible for the first time be marked in any way, so the
      user can tell "newly discovered because of this change" from "newly captured"? Not
      required by any criterion above; raised because the first run is a one-off event.
- [ ] Is there a subfolder the user would want excluded after all, once they see the first
      recursive run? The decision was to build no mechanism; this question exists so the
      decision is revisited on evidence rather than forgotten.

---

## Supporting Research

### Competitive Analysis

Not applicable. Tomo is a single-user tool built by its own user; there is no competing
product and no market to position against. Recording this rather than inventing an
analysis.

### User Research

The research for this spec was code archaeology across four perspectives — requirements,
technical, performance, and contracts — with every claim re-verified against source before
being accepted. The full findings, including two claims that were corrected during
research, are in this spec's `README.md` under "Research findings".

The one piece of genuine user research is a direct question, asked and answered on
2026-09-05: does the user put notes in inbox subfolders? Yes. That answer is what makes
this a pipeline defect rather than a documentation error, and it was asked precisely
because assuming either way would have produced a materially different spec.

### Market Data

Not applicable — see Competitive Analysis.
