---
title: "/review: every day read, and the previous reviews taken into account"
status: draft
version: "1.2"
date: "2026-11-22"
---

# Product Requirements Document

> v1.1 (2026-11-22): validation fixes; owner decision on continuing an unfinished read; open questions settled; mechanism moved to "Notes for the SDD".

> v1.2 (2026-11-23): owner — a previous note's folder listing answered with nothing is "no note found" (missing), not "Kado returned none" with the key hint. Amended: F3-AC9 and its edge case.

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
| specId | 047-review-chunked-read |
| title | /review: every day read, and the previous reviews taken into account |
| status | COMPLETE |
| sections | see below |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 56 |
| openQuestions | none |

### SectionStatus

| Name | Status | Detail |
|------|--------|--------|
| Product Overview | COMPLETE | Includes the terms used |
| User Personas | COMPLETE | Personas of spec 046, unchanged |
| User Journey Maps | COMPLETE | |
| Feature Requirements | COMPLETE | F1–F7 Must, F8 Should; amendments to specs 045 and 046 |
| Detailed Feature Specifications | COMPLETE | Previous reviews (F3–F5) |
| Success Metrics | COMPLETE | Cost and time are guidance, not gates |
| Constraints and Assumptions | COMPLETE | |
| Risks and Mitigations | COMPLETE | |
| Open Questions | COMPLETE | All settled by the owner on 2026-11-22 |
| Supporting Research | COMPLETE | Ends with notes for the SDD |

---

## Product Overview

### Vision

`/review` helps the user write a weekly, monthly or quarterly review from everything the period holds. Every day of the period reaches Tomo's proposals, however long the period is. The review also looks back one step: it follows up what the previous reviews left open, checks the intentions and goals written there, and shows how their themes went on. The user sees, item by item, what was done since, what is still open and what was not mentioned again.

Terms used in this PRD:

- **Pass 1** writes the review document to the inbox. **Pass 2** is the second `/review` run that turns the approved document into an instruction set the user applies (specs 045 and 046).
- **Child marks** are the marks of specs 045 and 046 for what only a weekly or monthly review holds and what no weekly or monthly review mentions.
- **Previous note** is the periodic note of the period before (Feature 3). A **carried item** is an item Tomo takes from a previous note and follows up (Feature 4); its **carried mark** says what became of it (Feature 5).
- **Condensing** is Tomo's step of taking in a week of the period at a time before the proposals are built.
- **The read** is Tomo reading the period's notes and the previous notes from the vault through Kado.

### Problem Statement

Spec 046 (PR #271) added quarterly reviews and the user's own template sections. Its live walk showed two gaps (#270, owner request 2026-11-22):

- **A quarter cannot be read in full.** The material Tomo reads for 2026-Q1 of the test vault is about 717 KB, about 390,000 tokens. A model's working context holds about 200,000 tokens, and one read by a model returns at most about 25,000 tokens; the quarter's index alone is about 82,500 tokens. Both 2026-Q1 runs of the spec 046 walk fell back to searching a few fields per day and reported a partial read. The quarter's review was built on part of its days. One run cost $4.26, of which $2.83 went to four helpers the session started on its own.
- **A month is over the limit too.** A month's material is about 190 KB, about 100,000 tokens, four times what one read returns. The week fits today.
- **Trimming alone does not help.** Leaving out repeated text saves about 220 KB of the quarter and still leaves about 270,000 tokens, more than a context holds.
- **No review looks back.** A review reads only the notes inside its period: a month reads its weekly notes, a quarter its monthly notes. No review reads the previous week, month or quarter. So Tomo cannot say what the last review left open, whether its intentions held, or how its themes moved. The owner does this by hand, going back to last week's and last month's note.

### Value Proposition

- Every day of a week, month or quarter reaches the proposals. There is no partial read and no silent sample.
- Week, month and quarter are built the same way, so a quarter is as complete as a week.
- The review follows up the previous reviews: open items and intentions come back with "done", "still open" or "not mentioned again", in the section where they fit, each once.
- The user sees at the top of the review document which previous notes were read and which were not found, empty or not set up.
- Nothing else changes for the user: the review document, Pass 2, the delivery into the user's sections and the privacy contract stay as specs 045 and 046 define them.
- Quality comes first. The cost and time limits stay as guidance; the owner accepts a higher weekly cost for one flow and a complete read.

## User Personas

### Primary Persona: The reviewer

- **Demographics:** As in specs 045 and 046: the owner of a personal Obsidian vault who runs Tomo in its container, keeps daily notes and writes weekly, monthly and quarterly reviews. Comfortable in a console session. Does not read frontmatter or use a tag pane; filenames, checkboxes and Tomo's own reports are the signals. Writes mostly in German.
- **Goals:** Get reminders from every day of the period, also for a quarter. See what last week's or last month's review left open and whether it got done, whether the intentions held, and which themes go on, without opening the earlier notes.
- **Pain Points:** The quarterly review of spec 046 was built on part of the quarter and said so. Following up the previous review means opening it and comparing by hand. An item that shows up twice, once from the days and once from the previous review, would be noise.

### Secondary Personas

**The vault keeper.** The owner in the setup role, as in spec 046. Has set up some period kinds and maybe not others (for example weeks and months but no quarters).
- **Goal:** A review works with what is set up and says plainly what it could not look at.
- **Pain point:** A setup question in the middle of a review, or a silent gap where a kind is not set up.

**The applier.** The owner later in Obsidian, applying the instruction set in Hashi, or a user without Hashi applying it by hand.
- **Goal:** The delivery works exactly as before; a carried item is a line of text like any other.
- **Pain point:** Any change in what Pass 2 delivers or how it is applied.

**The plain-template user.** A Tomo user without a section mapping, as in spec 046.
- **Goal:** Carried items land in the "Tomo Review" groups and the review works as before.
- **Pain point:** Features that assume a mapping and leave a plain template with less.

## User Journey Maps

### Primary User Journey: A finished month that looks back

1. **Awareness:** March has ended. The user wants to write the monthly review and remembers that February's review named goals and a few open points.
2. **Consideration:** The alternative is opening February's monthly note and the last quarterly note and comparing them with the month by hand.
3. **Adoption:** The user runs `/review month` as before. Nothing new to set up.
4. **Usage:** Tomo reads March's days, its weekly notes, February's monthly note and the previous quarter's note. The review document says at its top that February's note was read and the quarterly note of 2025-Q4 was not found. February's goal "start running again" shows up in "Things I did well this month" as "· done (previous review)", linked to February's note and the days it happened. An open point from February that March never mentions shows up in the "open" group as "· not mentioned again (previous review)". The user unticks one, rewrites another, approves and runs `/review` again; Pass 2 works as before.
5. **Retention:** Each review starts where the last one ended. The user stops opening last month's note to compare.

### Secondary User Journeys

1. **A full quarter (reviewer).** The user runs `/review quarter` for 2026-Q1. Tomo reads all 90 days and writes the document. The reading report names no day as not read because of size. Carried items come from the previous quarter's note, or the top line says it was not found.
2. **First review ever (reviewer, plain-template user).** No previous note exists yet. The document's top says in one line per kind that no previous note was found. The review is otherwise complete and nothing is treated as an error.
3. **A previous kind that is not set up (vault keeper).** A weekly review would read the previous month, but months are not set up. The document's top says monthly notes are not set up. No setup question interrupts the review; the vault keeper runs `/review setup` later if they want it.
4. **No mapping (plain-template user).** The carried items go into the "done", "open" and "themes" groups of the "Tomo Review" part, with their marks.
5. **An interrupted Pass 1 (reviewer).** The session ends while Tomo is condensing a quarter. The user runs `/review 2026-Q1` again. Tomo says it continues the read made earlier and names when it was made, and condenses only what is left.
6. **Applying (applier).** The applier delivers and applies the review as before. A carried item lands as its text, with its mark as the user left it.

## Feature Requirements

### Must Have Features

#### Feature 1: Every day of the period reaches the proposals

- **User Story:** As the reviewer, I want every day of my week, month or quarter to reach Tomo's proposals, so that a long period is reviewed as completely as a short one.
- **Acceptance Criteria:**
  - [ ] F1-AC1: Given a week, a month or a quarter, When Tomo builds the proposals, Then every day it read takes part in them with everything it read of that day; no day is left out, cut short, sampled, or read only through some of its fields or a search over them because of the size of the period, and the reading report names 0 days as not read because of size; a day that cannot take part is named at the top of the document (F6-AC1)
  - [ ] F1-AC2: Given a week, a month and a quarter of the same vault, When Tomo builds each review, Then each is equally complete: a day of a quarter reaches the proposals with the same material as the same day in a weekly review; a week that crosses the edge of the period takes part only with its days inside the period, under the configured first day of the week and week rule
  - [ ] F1-AC3: Given a matter found on two days that lie in different weeks of the period, When Tomo proposes themes, Then it counts as a recurring theme; the "at least two days of the period" rule of spec 045 is applied over the whole period, not per week
  - [ ] F1-AC4: Given an item that is open on an earlier day and done on a later day of the period, also in a later week, When Tomo proposes it, Then it is proposed as done and not as open; open is judged against the whole period
  - [ ] F1-AC5: Given a finding that appears in more than one week of the period, When Tomo writes the proposals, Then it is one item with the source links of all those days, in one section or group (spec 046 Rule 5 across weeks)
  - [ ] F1-AC6: Given a period, When Tomo condenses it, Then only the days of the period are condensed; from the day after the period it takes only the fields that name the day before, as today, and nothing else
  - [ ] F1-AC7: Given a day larger than the per-day reading limit, When Tomo reads it, Then it reads the day up to the limit at a section boundary and names it as partly read, as today

F1-AC3, F1-AC4 and F2-AC3 apply one principle — judge over the whole period, never per week — to three different things: themes, open items and child marks.

#### Feature 2: The review stays the same for the user

- **User Story:** As the reviewer and the applier, I want the review document and Pass 2 to stay as they are, so that the new reading changes nothing I rely on except what this spec adds.
- **Acceptance Criteria:**
  - [ ] F2-AC1: Given the same vault, setup and period for a week (2026-W13), a month (2026-03) and a quarter (2026-Q1), When the review document is written before and after this spec, Then both have the same parts in the same order, the same sections and groups with their checkboxes, the same child marks, habit items and reading report, and items with source links of the same kinds; they differ only in the carried items and their marks (F4, F5), the previous-note lines (F3-AC6), and parts named as not condensed (F6-AC1); the wording of the model-written items is not compared
  - [ ] F2-AC2: Given an approved review document written by the new flow, When the user runs Pass 2, Then the preview, the Deliver or Abort step, the instruction set, the readable instructions and the replacement of Tomo's earlier blocks work as specs 045 and 046 define them, and the instruction-set format is unchanged
  - [ ] F2-AC3: Given a month or a quarter, When Tomo sets the child marks, Then it compares over the whole period, never per week (spec 045 F3-AC5, spec 046 F6-AC4, F1-AC9)
  - [ ] F2-AC4: Given tracker fields in the setup, When the habits are built, Then they count or average every day of the period that carries a value, as spec 045 Feature 8 defines, whatever the number of weeks
  - [ ] F2-AC5: Given a period, When Tomo reports what it read, Then the per-day report, the stop when no day holds content, and the stop when Kado is unreachable work as spec 045 F3-AC8 to F3-AC10 define them; a month whose weeks have no weekly notes, or a quarter whose months or weeks have no monthly or weekly notes, is built from what exists, and the report names the missing weekly and monthly notes (spec 045 F3-AC6, spec 046 F6-AC5)
  - [ ] F2-AC6: Given a read, When Tomo reads the period's notes and its previous notes, Then all of that one read stays within Kado's rate limit in one pass, with the retries of spec 045 F3-AC11, and one report of retries and waiting time covers it (spec 045 F3-AC12)

#### Feature 3: Finding the previous reviews

- **User Story:** As the reviewer, I want Tomo to read the review notes of the period before, so that my review can follow up on them.
- **Acceptance Criteria:**
  - [ ] F3-AC1: Given a weekly review, When Tomo reads the period, Then it also reads the previous week's note and the note of the month before the month in which the week starts (2026-W14, starting Monday 2026-03-30: 2026-W13 and February 2026; 2026-W01, starting 2025-12-29: 2025-W52 and November 2025)
  - [ ] F3-AC2: Given a monthly review, When Tomo reads the period, Then it also reads the previous month's note and the note of the quarter before the month's quarter (March 2026: February 2026 and 2025-Q4; January 2026: December 2025 and 2025-Q4)
  - [ ] F3-AC3: Given a quarterly review, When Tomo reads the period, Then it also reads the previous quarter's note (2026-Q1: 2025-Q4)
  - [ ] F3-AC4: Given a previous period, When Tomo looks for its note, Then it finds it only through the setup's folder and name format for that kind, in the folder itself or in its year subfolder, as it finds weekly and monthly notes today; a note under another name, for example after a change of the name format, is not found
  - [ ] F3-AC5: Given each previous note, When Tomo reads it, Then it is in exactly one state: found, empty, missing, not set up, or not read; the review continues in every state
  - [ ] F3-AC6: Given the previous notes of a review, When the document is written, Then its top names each previous note in one line with its state, and the run report says the same; the line for missing says no note was found for that period, without an error tone, also for a user's first review
  - [ ] F3-AC7: Given a previous note that holds nothing beyond its template's skeleton, When Tomo reads it, Then its state is empty; a note with any text of the user's, with or without a Tomo block, is found
  - [ ] F3-AC8: Given a previous period whose kind has no folder or name format in the setup, When Tomo reads the period, Then that note's state is not set up, and no setup question is asked during the review
  - [ ] F3-AC9: Given a previous note that Kado refuses or fails to return, When Tomo reads, Then its state is not read and the line names the cause; given a listing of its folder that Kado answers with nothing, Then its state is missing ("no note found")
    - Amended 2026-11-23 (owner): an empty listing is missing — spec 045 Rule 6 gives the key hint only when Kado answered nothing at all, and the period's dailies were read; a key denial that lists as empty also reads "no note found" (accepted).
  - [ ] F3-AC10: Given a previous note larger than the per-day reading limit, When Tomo reads it, Then it reads it up to that limit at a heading boundary, and its line says it was read in part
  - [ ] F3-AC11: Given a found previous note from which Tomo carries no item, When the document is written, Then its state line says found and that nothing was carried from it

#### Feature 4: Carrying items forward

- **User Story:** As the reviewer, I want the open items, intentions and themes of the previous reviews followed up in my review, each once and in the section where it fits, so that I see what happened to them without opening the earlier notes.
- **Acceptance Criteria:**
  - [ ] F4-AC1: Given a found previous note that holds an open item, an intention or goal, and a theme — in the user's own text or in a Tomo block — When the document is written, Then each of the three appears as a carried item with its carried mark; no setup value marks what counts as open or as an intention
  - [ ] F4-AC2: Given a carried open item or intention, When Tomo checks it against the period's days, Then it is marked done when a day shows it done, still open when a day shows it still open or only partly done, and not mentioned again when no day of the period mentions it
  - [ ] F4-AC3: Given a carried theme, When Tomo checks it against the period's days, Then it is marked still open when at least one day of the period shows it again, and not mentioned again when no day does; a theme is never marked done
  - [ ] F4-AC4: Given a carried item, When Tomo places it, Then it goes into the mapped section whose description it fits best, otherwise into the group of its mark: done into "done"; still open and not mentioned again into "open"; a theme into "themes"
  - [ ] F4-AC5: Given a section the user marked off-limits, When Tomo places carried items, Then none goes there; text in an off-limits section of a previous note may still be read as a source (spec 046 F2-AC11)
  - [ ] F4-AC6: Given a carried item that the period's days also hold, When Tomo writes it, Then it is one item with its carried mark, whose sources are the previous note and those days; it appears nowhere else in the document
  - [ ] F4-AC7: Given the same matter in both previous notes of a review (for example the previous week and the previous month), When Tomo writes it, Then it is one item with one carried mark and both previous notes among its sources
  - [ ] F4-AC8: Given an item the previous note itself carried as still open, When it is still open in this period, Then it is carried again with the same mark; Tomo counts no age and adds no text about how long it has been open
  - [ ] F4-AC9: Given an item the user unticked or deleted in the previous review document, or removed from the previous note after applying, When Tomo reads the previous note, Then the item is not carried; only what the note holds now is carried
  - [ ] F4-AC10: Given a mapped section whose item cap is reached, When a carried item fits it best, Then the carried item goes into the group of its mark (F4-AC4) instead; it is never dropped and never merged with an item of another mark; carried items of the same mark merge under spec 046 F1-AC5, keeping every source link
  - [ ] F4-AC11: Given a previous note written in another language than the current review language, When the document is written, Then the text of every carried item is in the current review language

#### Feature 5: The marks of carried items

- **User Story:** As the reviewer, I want a carried item to say in a few words what became of it and where it came from, so that I tell it apart from what the period alone shows.
- **Acceptance Criteria:**
  - [ ] F5-AC1: Given a carried item in a weekly, monthly or quarterly review, When the document is written, Then the item's text is followed by " · " and its mark: in English "done (previous review)", "still open (previous review)" or "not mentioned again (previous review)"; in German "erledigt (letzter Rückblick)", "noch offen (letzter Rückblick)" or "nicht mehr erwähnt (letzter Rückblick)"; in any other review language the English mark
  - [ ] F5-AC2: Given an item that carries both a carried mark and a child mark, When it is written, Then both show, the carried mark first, each after its own " · "
  - [ ] F5-AC3: Given a carried item, When it is written, Then one of its source links is the link to the previous note it came from, named by that note's name (for example `2026-W12`)
  - [ ] F5-AC4: Given a ticked carried item in an approved document, When Pass 2 delivers it, Then the mark is part of the item's text: the user may edit or delete it, the line lands as the user left it, like the child marks, and the mark is never read as an item edit or as a done tick
  - [ ] F5-AC5: Given a carried item the user unticked or deleted, When Pass 2 builds the delivery, Then it is absent, as spec 045 F5-AC6 defines for any item
  - [ ] F5-AC6: Given a delivered review whose period is reviewed again, When Pass 2 delivers, Then Tomo's earlier block, carried items included, is replaced and no second block or instruction set appears (spec 045 F6-AC2, F6-AC3, spec 046 Feature 5); a broken section checkbox line stops delivery as spec 046 F3-AC6 defines

#### Feature 6: When a step fails, and running again

- **User Story:** As the reviewer, I want a failure in one part of the work to be named and the rest of the review to go on, and an interrupted review to continue where it stopped, so that I never get a silent gap or pay twice.
- **Acceptance Criteria:**
  - [ ] F6-AC1: Given a week of the period whose material Tomo could not condense, also after one more try, When the document is written, Then the document's top and the run report name that week and its days as not read, like days Kado did not return (spec 045 F3-AC13), and the review is built from the rest
  - [ ] F6-AC2: Given that taking the previous reviews into account fails as a whole, When the document is written, Then the review continues without it, the document's top says in one line that the previous reviews could not be taken into account, and no item carries a carried mark; the lines of F3-AC6 still show; given that only one of two previous notes fails, Then the other's items are carried and the top names the failed note
  - [ ] F6-AC3: Given proposals that fail the document's checks, When Tomo builds them, Then it corrects them once; if they fail again, it shows what failed and writes no document, as today
  - [ ] F6-AC4: Given a Pass 1 interrupted by the end of the session or a failed step before the document was written, When the user runs `/review` for the same period again, Then Tomo continues on the stored read without reading Kado again, says in one line that it continues and when the read was made, condenses only what is not yet done, and writes a document like an uninterrupted run would; after a stop because Kado was unreachable (F2-AC5) nothing is stored and there is nothing to continue; starting over, or a changed section mapping, reads anew (F6-AC5)
  - [ ] F6-AC5: Given a first run for a period, a start over, or a section mapping changed since the stored read, When Tomo runs Pass 1, Then it makes a new read and discards all earlier material of that period; material from an earlier read or condensed under an earlier mapping is never used
  - [ ] F6-AC6: Given the user aborts during Pass 1 (not the Deliver or Abort step of Pass 2), When the abort is answered, Then no further step runs, no document is written, the material is deleted at once (F7-AC1), and the run cannot be continued
  - [ ] F6-AC7: Given a period reviewed again (start over, spec 045 F6-AC1), When Tomo reads it, Then it reads the previous notes anew as they stand now, and never carries anything from the target note of the period itself or from Tomo's earlier blocks in it
  - [ ] F6-AC8: Given that no week of the period can be condensed, When Tomo reports, Then it stops like a period with no content (F2-AC5), names every week, and writes no document

#### Feature 7: Privacy

- **User Story:** As the reviewer, I want the extra material this review produces to be kept as briefly and as visibly as before, so that I can protect it like my vault.
- **Acceptance Criteria:**
  - [ ] F7-AC1: Given a review run, When the review document is written, the user aborts Pass 1 (F6-AC6), or the user drops the review, Then everything Tomo took from notes for the review outside the document — the material per day, the condensed weeks, the material from previous notes, the carried items and the proposals — is deleted, as today
  - [ ] F7-AC2: Given a Pass 1 interrupted by the end of the session or a failed step, When the run ends, Then its material stays only until the document is written, the user drops the review or starts over, or that period's next `/review` replaces it, and the privacy documentation says so; a Kado stop leaves no material
  - [ ] F7-AC3: Given the privacy and setup documentation, When a user reads it, Then it names the new places where content from notes rests during a review, the previous notes as a new source that is read, that the models doing the condensing, the carrying and the proposals see note content and which models they are, and that each of them writes its own session transcript in the container home
  - [ ] F7-AC4: Given any review run, When a step reports, logs or records cost, Then no note text, previous-note text, carried item or proposal text appears in Tomo's records (logs, error output, cost records), also from the new steps; they carry only paths, dates, counts and states (spec 045 F7-AC1)
  - [ ] F7-AC5: Given a review run, When any step other than the read runs, Then it has no access to Kado or the vault of its own and sees only what the read took from the vault; nothing but the document write writes to the inbox, and nothing writes to the vault

### Should Have Features

#### Feature 8: Measuring cost and time

- **User Story:** As the owner, I want each live run to show where cost and time go, so that I can judge the guidance limits with real numbers.
- **Acceptance Criteria:**
  - [ ] F8-AC1: Given a live review run, When its cost is recorded, Then the record lists cost, time and peak size per step, with counts only
  - [ ] F8-AC2: Given a run above a cost or time limit of the Success Metrics, When it runs, Then it completes like any other run; the overrun is reported in the spec's close-out and blocks nothing

### Could Have Features

- A line at the top of the document counting the carried items per mark.
- A short "what the marks mean" passage in the usage documentation.
- Offering to drop an unfinished read of another period when the user starts a new review.
- Longer mark wording ("done since the previous review"), if the short form proves unclear.

### Won't Have (This Phase)

- **Trimming the review skill and polishing the setup answers (#259).** It builds on this redesign afterwards.
- **A setup marker for intention sections.** Tomo decides from the text; revisit if the live walk shows poor detection.
- **An age counter for carried items** ("open for three weeks").
- **Reading reviews further back** than the previous notes of F3-AC1 to F3-AC3, or a yearly review.
- **Writing into previous notes.** They are read only.
- **"Avoid repeating last time's items"** as a goal. Previous reviews serve follow-up, intentions and themes.
- **A further condensing level** (weeks into months before the proposals). Only if condensed weeks prove too large.
- **Changes to Hashi or Kado, a handoff to them, or a new instruction-set format.** A carried mark is item text. At most an FYI to Kokoro.
- **Leaving non-note embeds out of the "not in a weekly or monthly review" lists.** Parked from the spec 046 walk.

### Amendments to specs 045 and 046

Everything of spec 045's PRD (v1.8) and spec 046's PRD (v1.3) stays in force. Nothing is removed. References to spec 045 criteria use the numbering of the spec 045 close-out (`docs/XDD/specs/045-weekly-monthly-review/close-out.md`, lines 610–634), because spec 045's requirements.md does not number its criteria. The amendments below restate a criterion for the new reading or narrow a rule for carried items:

- **Spec 045 Rule 3 and F4-AC3, spec 046 F1-AC3 and its Rule 1 (a source inside the period):** amended for carried items. A carried item marked done or still open links its previous note and at least one day of the period. A carried item marked not mentioned again links only its previous note or notes; that is its source. Every other Tomo proposal keeps the rule unchanged. The quality KPI "0 Tomo proposals without a source link in the period" counts the previous note as the source of a not-mentioned-again item.
- **Spec 045 F4-AC2 (a theme is found on at least two days of the period):** restated by F1-AC3 over the whole period. Amended for carried themes: a theme of a previous review that one day of the period shows again is proposed as still open (F4-AC3).
- **Spec 045 F4-AC2 and spec 046 F1-AC7 (the groups):** carried items with no fitting section go into the existing "done", "open" and "themes" groups (F4-AC4). No group is added.
- **Spec 046 F1-AC6 and Rule 5 (one place per finding):** restated for findings across weeks (F1-AC5) and for carried items (F4-AC6, F4-AC7).
- **Spec 046 F1-AC5 (the item cap):** carried items count toward it; a full section sends a carried item to its group instead of dropping it (F4-AC10).
- **Spec 045 F3-AC1, spec 046 F1-AC1 and F6-AC4 (what is read):** restated by F1-AC1 with the hard condition that no day is left out because of size; extended by Feature 3 to the previous notes.
- **Spec 045 F3-AC5, spec 046 F6-AC4 and F1-AC9 (the child marks):** restated by F2-AC3 over the whole period.
- **Spec 045 F3-AC10 (stop when Kado refuses access):** narrowed for previous notes. A previous note Kado refuses or fails to return is named as not read and the review continues (F3-AC9). For the period's own notes the stop stays.
- **Spec 045 F3-AC13 (missing days named at the top):** extended to weeks not condensed (F6-AC1), the previous-note lines (F3-AC6) and a failed carry (F6-AC2).
- **Spec 045 F2-AC8 (a period kind not set up runs the setup first):** does not apply to the kinds of previous notes (F3-AC8). It still applies to the kind the user asks to review.
- **Spec 045 F5-AC6, F6-AC2, F6-AC3 and spec 046 F3-AC6:** restated for carried items by F5-AC5 and F5-AC6.
- **Spec 045 F7-AC1 and F7-AC2 (privacy):** extended by F7-AC3 and F7-AC4 to the new material and the models that see it.
- **Spec 045 F6 and spec 046 F5 (open reviews and reviewing a delivered period again):** unchanged. Continuing an interrupted Pass 1 (F6-AC4) is a different thing: it concerns a Pass 1 that wrote no document yet, so no open review exists for it.
- **Week's previous month:** a weekly review's previous month is the month before the month in which the week starts (F3-AC1), also when the week ends in the next month.
- **Spec 046 cost and time KPIs:** kept as numbers, now explicitly guidance (Success Metrics). The quarterly limit, "to confirm" in spec 046, is measured on a full read for the first time.

## Detailed Feature Specifications

### Feature: Taking the previous reviews into account (Features 3, 4 and 5)

**Description:** While Tomo reads the period, it also reads the review notes of the period before: for a week the previous week and the previous month, for a month the previous month and the previous quarter, for a quarter the previous quarter. It finds them by the setup's folder and name format only. From each found note, Tomo takes what was left open, the intentions and goals, and the themes. It checks each against the period's days and gives it one of three marks: done, still open, or not mentioned again. Each carried item lands once, in the section it fits best or in the group of its mark, with a link to the previous note. The document's top says which previous notes were read and which were empty, missing, not set up or not read. If carrying fails, the review goes on without it and says so.

**User Flow:**
1. User runs `/review` for a week, month or quarter.
2. System reads the period's notes and the previous notes in one read, within Kado's rate limit.
3. System condenses the period week by week and takes the items of the previous notes.
4. System builds the proposals over the whole period, checks each carried item against the days, gives it its mark and places it once.
5. System writes the review document. Its top names the previous notes with their states, any week not condensed, and any failure to carry. It deletes the material it used for the document.
6. User unticks, edits, deletes or adds items, including carried ones, ticks Approved and runs `/review` again.
7. System delivers as specs 045 and 046 define; a carried item lands as its text.

**Business Rules:**
- Rule 1: Spec 045 Rules 1, 2, 4 (as amended by spec 046), 5, 6 and 7 and spec 046 Rules 2 to 9 apply unchanged. Spec 045 Rule 3 applies as amended by Rule 4 below.
- Rule 2: A day counts as read only when its material reached the proposals. There is no partial read and no fallback to a sample.
- Rule 3: Previous notes are found only through the setup's folder and name format. A week's previous month is the month before the month the week starts in. A month's previous quarter is the quarter before the month's quarter.
- Rule 4: A carried item marked done or still open links its previous note and at least one day of the period. A carried item marked not mentioned again links only its previous note or notes.
- Rule 5: A carried item appears once, with exactly one carried mark.
- Rule 6: Previous notes are read, never written. The target note of the period is never a previous note.
- Rule 7: A failure to carry never stops the review. A failure to condense never leads to a partial read; it is named.
- Rule 8: All material taken from notes for a review, except the review document, rests only until the document is written, the user aborts or drops the review, or a new read replaces it.
- Rule 9: A new read happens only on the first run for a period, on start over, or when the section mapping changed since the stored read; otherwise an interrupted Pass 1 continues on the stored read.

**Edge Cases:**
- First review ever: no previous note exists → Expected: one missing line per kind at the top, no error tone, the review is complete otherwise.
- The previous note holds only the template's skeleton → Expected: state empty, named at the top, nothing carried.
- The user wrote the previous note by hand, without any Tomo block → Expected: state found; its text is carried from like any other.
- A found previous note holds nothing to follow up → Expected: its line says found, nothing carried (F3-AC11).
- The previous note uses another template or language → Expected: it is read; carried items are written in the current review language (F4-AC11).
- The name format changed since the previous note was written → Expected: the previous note is not found under the new format; state missing.
- A week crosses a month or quarter edge → Expected: its previous month is the month before the month it starts in (2026-W14 from 2026-03-30 reads February 2026).
- The week of New Year → Expected: the previous week is the last week of the year before under the week rule (2026-W01 → 2025-W52); a week rule other than ISO is followed.
- January → Expected: previous month December of the year before; previous quarter Q4 of the year before.
- Previous notes in year subfolders → Expected: found as weekly and monthly notes are found today.
- Months are set up, quarters are not → Expected: a monthly review names the previous quarter as not set up; no setup question.
- Kado refuses the previous note's path, or answers the folder listing with nothing → Expected: not read with the cause, or no note found for an empty listing (F3-AC9, amended 2026-11-23); the review continues.
- A very long previous note → Expected: read up to the limit at a heading boundary, named as read in part (F3-AC10).
- The same open item in the previous week and the previous month → Expected: one item, both notes as sources, one mark (F4-AC7).
- An item still open for the third review in a row → Expected: still open again, no age (F4-AC8).
- An intention partly done → Expected: still open (F4-AC2).
- A carried item that also carries a child mark → Expected: both marks, carried first (F5-AC2).
- The best-fitting section is off-limits in this period's note → Expected: the item goes to the next fitting section or its group (F4-AC5).
- The best-fitting section is full → Expected: the item goes to the group of its mark (F4-AC10).
- The user removed an item from the previous note after applying → Expected: not carried (F4-AC9).
- A period reviewed again after delivery → Expected: previous notes read anew; nothing carried from the period's own note (F6-AC7).
- One week cannot be condensed → Expected: its days named as not read at the top; the rest reviewed; no sample of those days (F6-AC1, F1-AC1).
- No week can be condensed → Expected: Tomo stops, names every week, writes no document (F6-AC8).
- The session ends while condensing → Expected: the next `/review` of the period continues on the stored read and says when it was made; the material stays on disk until then, a drop or a start over, and the privacy documentation says so (F6-AC4, F7-AC2).
- The section mapping changes between the interruption and the rerun → Expected: a new read; the earlier material is discarded (F6-AC5).
- A day larger than the per-day reading limit → Expected: read up to the limit at a section boundary and named as partly read, as today (F1-AC7).

## Success Metrics

### Key Performance Indicators

- **Adoption:** The owner runs 4 consecutive weekly reviews, 1 monthly review and 1 quarterly review on the new flow in the live vault after release (measured after the spec closes).
- **Engagement:** At most 40 % of Tomo's proposals are unticked or deleted over a delivered review (spec 045 KPI, unchanged). The same count is reported separately for carried items, per mark, with the same 40 % target as guidance; habit items are not counted.
- **Quality:** On the test vault's 2026-W13, 2026-03 and 2026-Q1: 0 days named as not read because of size (hard condition); 0 reads that fall back to a sample or a search. Everywhere: 0 carried items placed twice; 0 carried items without a link to their previous note; 0 note text in Tomo's records; 0 material from notes left on disk after a written document, an abort or a drop. The owner compares the three live-walk documents with those of the spec 046 walk and records whether they are at least as useful.
- **Business Impact:** Not applicable: a personal tool without revenue or user base targets.
- **Cost and time (guidance, not gates):** On the test vault: weekly Pass 1 at most $0.80 (spec 046 limit; the estimate for the new flow is $0.90 to $1.10, accepted by the owner for one flow and a complete read); monthly Pass 1 at most $2.00 and 7 minutes; quarterly Pass 1 at most $5.00 and 20 minutes; Pass 2 at most $0.85. The $0.50 weekly limit in the brainstorm is spec 045's number and is stale since spec 046.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Review read | as specs 045 and 046, plus per previous note its kind and state, the number of weeks in the period, and whether the read is new or continued | Coverage, previous-note states, continue rate |
| Week condensed | period, week, days in it, passed or failed | Hard condition, failure rate |
| Previous reviews carried | period, per previous note the number of items taken, passed or failed | Carry coverage |
| Review document written | as spec 046, plus carried items per mark, how many landed in a section or a group, carried items placed more than once, carried items without a previous-note link, weeks not condensed, days not read by cause | Hard condition, quality KPI, engagement baseline |
| Review delivered | as spec 046, plus carried items kept / unticked / deleted per mark | Engagement KPI for carried items, adoption |
| Run cost | period, kind, pass, cost, time and peak size per step | Cost and time guidance (F8) |

All events carry counts and states only, never text (spec 045 Feature 7, unchanged). Adoption is counted by the owner from "Review delivered" events per kind after release.

---

## Constraints and Assumptions

### Constraints

- One read by a model returns at most about 25,000 tokens, and a model's context holds about 200,000 tokens. A quarter's material is about 390,000 tokens, a month's about 100,000, a seven-day week's about 22,000.
- All vault access goes through Kado and its key. Kado's rate limit is shared with everything Tomo runs at the time.
- Tomo writes only to the inbox; the 2-pass model of specs 045 and 046 is unchanged.
- No change to Hashi or Kado and no handoff to them. The instruction-set format stays as spec 046 left it. At most an FYI to Kokoro.
- The privacy contract of spec 045 stays: material from notes is deleted when the document is written, on abort and on drop.
- The privacy documentation names the models that see note content (F7-AC3).
- The document and Pass 2 must stay as they are for every period kind (F2); the owner accepted the larger risk of changing how every kind is read.
- No change to the files under the eval gate is planned. If one becomes necessary, it needs the full-suite run before merge.

### Assumptions

- Condensing a week keeps what the proposals need. The owner's quality comparison (KPI) checks this.
- A model can tell open items and intentions in a previous note without a marker.
- Users name their periodic notes consistently with the setup's name format.
- The test vault holds notes for 2026-W12 and February 2026, so 2026-W13 and 2026-03 find their previous notes; it likely holds no note for 2025-Q4, so the quarter walk covers the missing state. The walk checks this first.
- The cost estimate uses list prices and the spec 046 measurements.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Condensing loses detail the user needed | High | Medium | Condensing by week only, no further level; the owner compares with the spec 046 documents (KPI) |
| The new reading changes the document or Pass 2 unnoticed | High | Medium | Before-and-after comparison for week, month and quarter (F2-AC1, F2-AC2) |
| A failed week silently shrinks the review | High | Low | Named at the top like not-read days; no fallback (F6-AC1, F1-AC1) |
| A theme spread over two weeks is lost, or an item done later stays open | Medium | Medium | Themes and open items judged over the whole period (F1-AC3, F1-AC4) |
| Carried items duplicate what the days show | Medium | Medium | One item with both sources (F4-AC6, F4-AC7) |
| The model misreads what was open or intended | Medium | Medium | Marks are visible and editable; engagement per mark tracked; a setup marker is the fallback (Won't Have, revisit) |
| A missing or not-set-up previous note looks like an error | Low | Medium | One plain line per note; the review continues (F3-AC6, F3-AC8) |
| A continued read misses notes changed since it was made | Low | Medium | The line names when the read was made; start over reads anew (F6-AC4, F6-AC5) |
| More material rests on disk, and more models see note content | Medium | Medium | Deleted at write, abort and drop; interrupted runs and the models named in the privacy documentation (F7) |
| The weekly cost rises above its limit | Low | High | Accepted by the owner; guidance only; measured per step (F8) |

## Open Questions

None remain. Settled by the owner on 2026-11-22:

- [x] Approach, models, one flow for all kinds, the new read layout, the hard condition, the previous-note states, the mark labels, the week's previous month, the day after the period, deletion at write (spec README, Decisions Log).
- [x] A carried theme uses the same three labels: still open when one day of the period shows it again, not mentioned again otherwise, never done (F4-AC3).
- [x] A carried item marked not mentioned again with no fitting section goes into "open"; no group is added (F4-AC4).
- [x] A rerun of an interrupted Pass 1 continues on the stored read without a new Kado read, says so in one line with the time of the read, and condenses only what is not yet done; start over or a changed section mapping reads anew and discards the earlier material (F6-AC4, F6-AC5).
- [x] Engagement for carried items: the same 40 % as spec 045, reported per mark, as guidance (Success Metrics).
- [x] An interrupted read's material rests until the document is written, a drop, a start over or that period's next `/review`, and the privacy documentation names it; offering to drop it stays a Could Have (F7-AC2).

---

## Supporting Research

### Competitive Analysis

Periodic Notes, Templater and Dataview build periodic notes and roll up fields, and a user can embed last week's note in this week's. None follows up what the previous review left open against the new days, and none marks each item as done, still open or not mentioned again for the user to accept item by item. AI summaries of a period typically read one period in isolation and cut long periods silently.

### User Research

- Owner decisions 2026-11-22 (brainstorm and spec README): use the previous reviews to follow up open items, check intentions and goals, and follow themes, not to avoid repeats; the previous periodic note as it stands in the vault is the source; the model decides what is open or an intention; carried items go once into the best-fitting section or group with a mark; one flow for week, month and quarter; quality before cost; the new read layout replaces the old one, with a behaviour baseline first; deletion at write as today; the state not set up; short generic labels with the link naming the previous note; a week's previous month is the month before the month it starts in; only the period's days are condensed; an interrupted Pass 1 continues on the stored read.
- Spec 046 close-out and live walk: both 2026-Q1 runs read in part; quarter Pass 1 costs $1.41, $4.26, $1.46 and $1.31 on partial reads (up to 16.8 minutes); weekly Pass 1 cold $0.75 and $0.69; monthly Pass 1 cold $1.04 in 5.5 minutes.
- Research for this spec (research.md, 2026-11-22): a day of the test vault averages about 6 KB; review material is about 1.85 characters per token; the material outside the days is about 184 KB for the quarter; estimated cost per run for the new flow: week $0.90 to $1.10, month $1.60 to $2.00, quarter $2.50 to $3.50; the carried marks reach Hashi only as item text, so no handoff is needed.
- Test vault: weekly notes up to 2026-W13, monthly notes up to 2026-02, dailies up to 2026-03-31, then a deliberate gap.

### Market Data

Not applicable: a personal-vault feature for the existing Tomo user base.

### Notes for the SDD

Moved here from the PRD body in v1.1 so nothing is lost; they are mechanism, not requirements:

- Only the read step calls Kado; the other steps add no Kado calls. The previous notes add 2 to 4 calls to the read.
- A helper agent cannot start another helper (platform constraint); the review's main session starts all of them.
- Owner's model choice: a small model condenses each week, a mid-size model carries the previous items, the largest model builds the proposals (README Decisions Log).
- A quarter needs 14 to 16 week helpers started at once; this is unproven, so plan a fallback in two rounds and pin foreground dispatch.
- The before-and-after comparison of F2-AC1 is an end-to-end run for week, month and quarter on the fake vault, green before the rebuild and after it.
- "Continue on the stored read" needs a way to tell which read each stored file came from, and which mapping the condensed weeks were built under.
