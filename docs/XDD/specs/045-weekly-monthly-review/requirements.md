---
title: "/review: weekly and monthly reviews the user edits before they land"
status: approved
version: "1.1"
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

At the end of a week or a month, Tomo reads every daily note of that period and proposes a review — what happened, what stayed open, what kept coming back, how the habits went, where the vault grew — that the user edits item by item before it lands in their weekly or monthly note.

### Problem Statement

The user writes a daily note every day and a weekly and a monthly note to look back. Tomo does not help with the looking back today (#31, backlog F-45):

- **The roll-up is manual or mechanical.** The owner's weekly notes (`Calendar/302 Weekly/2026-W13.md`) pull each day's Daily Log in with Quoth embeds and the habits with Dataview queries. That lists the days; it does not say what the week was about. Themes, threads that ran across several days and things left undone are found only by reading every day again. A user without Dataview or Quoth has not even the list.
- **The daily note holds more than the log.** A day's record is spread over the habit fields (sport, sleep, energy), the Dayplanner note, the 5 Year Journal note, the Obsidian ToDos, the Daily Log, and the user's own end-of-day fields (highlights, disappointments, to improve). No current Tomo command reads them together.
- **Weekly and monthly notes are invisible to Tomo.** Their folders, name format and template are not configured anywhere Tomo reads (backlog F-02: "config present, rendering open"); the installed vault configuration carries the daily folder only, and the example name format for weeks does not produce ISO week names like `2026-W13`, which the owner's vault uses.
- **A generated review the user cannot change is wrong.** A review is the user's reflection. Text Tomo writes straight into it, without the user accepting and editing each part, would be someone else's review (owner decision 2026-11-08).

### Value Proposition

- One command turns a finished week or month into a proposed review grounded in the user's own daily notes, with every proposal linked to the days it came from.
- The user stays the author: every proposed item is accepted, changed or dropped in Obsidian, in one review document, and the user may add items of their own, before anything reaches the weekly or monthly note.
- It works with plain daily notes, and fully with the owner's setup (inline fields, Dayplanner, 5 Year Journal, ToDos), without running Dataview or Quoth.
- The result lands where the user already reviews: as a section of the existing weekly or monthly note, or as a new note when there is none, applied through Hashi like every other Tomo change.

## User Personas

### Primary Persona: The reviewer

- **Demographics:** The owner of a personal Obsidian vault who runs Tomo in its container and keeps daily notes. Comfortable in a console session. Does not read frontmatter or use a tag pane; filenames, checkboxes and Tomo's own reports are the signals. Writes the dailies mostly in German.
- **Goals:** Look back on a week or a month in a few minutes: what got done, what stayed open, what recurred, how the habits went, where the vault grew. Keep the review in their own words.
- **Pain Points:** Rereading seven or thirty dailies takes too long, so weekly reviews lapse (the test vault's weeklies stop at 2026-W13 while its dailies go on). Mechanical roll-ups list days instead of themes. Anything an AI writes straight into the review feels foreign.

### Secondary Personas

**The plain-vault user.** Another Tomo user whose daily notes are plain text: a log, maybe some tasks and fields, no Dataview, no Quoth, possibly no weekly notes and no weekly template yet. Needs the review to work from what is written in the dailies and to create the periodic note when it does not exist.

**The vault keeper.** The owner in the setup role: tells Tomo once where weekly and monthly notes live, how they are named, which template they use, where in them a review goes, which parts of a daily note count, and in which language reviews are written. Wants this proposed by Tomo from what is in the vault and confirmed in a dialogue, never a file to edit.

**The applier.** The owner later in Obsidian, applying the instruction set in Hashi — or a user without Hashi, applying it by hand from the readable instructions. Needs the report to say exactly which note gets which section, or which new note is created where.

## User Journey Maps

### Primary User Journey: Finished week to edited review

1. **Awareness:** A week has ended; the user wants to look back before planning the next one.
2. **Consideration:** The alternatives are rereading the dailies or relying on the weekly note's embeds and queries; both leave the synthesis to the user.
3. **Adoption:** `/review` (the last finished week), `/review W13`, `/review 2026-W13`, or `/review @Calendar/302 Weekly/2026-W13.md` (the weekly note picked with `@`).
4. **Usage:** Tomo reads the period's dailies and their linked notes, reports per day what it read, and writes a review document to the inbox. The user opens it in Obsidian, unticks what is wrong, rewrites what is close, adds what is missing, ticks Approved, and runs `/review` again. Tomo shows the section as it will land and where, delivers the instruction set after approval, and the user applies it in Hashi or by hand. The weekly note now holds the review section.
5. **Retention:** The next week starts from the same setup; the review takes one command, a few minutes of editing, one more command and one apply.

### Secondary User Journeys

1. **First run (vault keeper).** No weekly or monthly setup exists. Tomo proposes the setup from the calendar folders, the existing periodic notes and the template folder, shows what the proposal matches, and saves only what the user confirms. The review request then continues.
2. **Changing the setup (vault keeper).** `/review setup` shows the current setup and runs the same proposal-and-confirm dialogue, for example to change the first day of the week or the review place.
3. **No periodic note yet (plain-vault user).** The period's note does not exist. The review document says the review will create it; after Pass 2 the new note, with the review section in it, waits in the inbox with an instruction set that moves it to the periodic folder.
4. **Monthly review (reviewer).** `/review month` (the last finished month), `/review 2026-03` or `/review @…/2026-03.md` reviews a month over its dailies and the weekly reviews written for its weeks. Tomo marks what appears only in a weekly review — a link or a theme the user added in hindsight — and offers what the dailies held but the weekly reviews left out.
5. **Coming back to an open review (reviewer).** The user runs `/review` while an earlier review is still open — a document not yet delivered, or a delivered instruction set not yet applied. Tomo offers that review first, whatever period the command would otherwise pick.
6. **Empty or sparse period (reviewer, plain-vault user).** Few or no dailies exist for the period, or they hold nothing. Tomo reports what it found and writes nothing when there is nothing to review.
7. **Abort and discard (reviewer, applier).** The user decides against the review: before Pass 2 by deleting the review document or answering Abort, after Pass 2 by not applying the instruction set and deleting it. Nothing in the vault outside the inbox has changed in either case.

## Feature Requirements

### Must Have Features

#### Feature 1: Periodic note setup

- **User Story:** As the vault keeper, I want Tomo to propose where my weekly and monthly notes live, how they are named, the first day of my week, which template they use, where a review goes in them, which parts of a daily note count and the review language, so that I confirm it once, change it when I want, and never edit a file.
- **Acceptance Criteria:**
  - [ ] Given no setup for the requested period kind, When the user runs `/review`, Then before reading any daily note Tomo proposes, for that period kind, the folder, the name format, the first day of the week (weekly only), the template, the review heading and the place it goes, the daily sections to read and the review language, shows the existing notes the name format matches and those it does not, and asks to confirm or correct in plain text
  - [ ] Given an existing setup, When the user runs `/review setup`, Then Tomo shows the current values, runs the same proposal-and-confirm dialogue, and saves only what the user confirms
  - [ ] Given existing periodic notes named by ISO week (for example `2026-W13`), When Tomo proposes a name format and first day of the week, Then the proposal produces exactly those names and proposes Monday
  - [ ] Given no existing periodic notes, When Tomo proposes a name format, Then it proposes ISO weeks (`2026-W13`, starting Monday) and calendar months (`2026-03`) and says it found no notes to compare with
  - [ ] Given the user sets a first day of the week other than Monday, When Tomo shows the matches, Then week numbers and the week's year follow that first day, and the existing notes the name format no longer matches are shown before the user confirms
  - [ ] Given no template for the period kind, or a template Kado cannot read, When Tomo proposes the setup, Then it says so and proposes a plain note (title and review section) instead, and says an unreadable template may mean the Kado key has no access
  - [ ] Given the user corrects a proposal, When Tomo has applied it, Then it shows the new matches again before asking, and nothing is saved until the user confirms
  - [ ] Given the user confirms, When the setup is saved, Then no other setting changes except a correction the user confirmed in the same dialogue (for example a daily folder path with a stray trailing space), and the review request continues in the same session
  - [ ] Given the user aborts the setup, When the session ends, Then nothing is saved and nothing is written to the vault

#### Feature 2: Choosing the review

- **User Story:** As the reviewer, I want `/review` to pick up an open review or the last finished week or month, so that the common case needs no argument and I never lose an edited review.
- **Acceptance Criteria:**
  - [ ] Given an open review exists (a review document not yet delivered, or a delivered instruction set not yet applied), When the user runs `/review` with or without a period, Then before anything else Tomo shows each open review by period and state and offers to continue it
  - [ ] Given no open review and no period argument, When the user runs `/review`, Then the period is the last finished week, from the configured first day of the week to the day before the next one; `/review month` takes the last finished calendar month
  - [ ] Given a period named by itself — a week (`2026-W13`), a month (`2026-03`), or an existing weekly or monthly note picked with `@` — When the user runs `/review` with it, Then that period is reviewed, without a `week` or `month` word
  - [ ] Given a week or month without a year (for example `W13`, `M03`), When the user runs `/review` with it, Then the period is the most recent finished one of that number, and Tomo names the year it chose before reading
  - [ ] Given a note picked with `@` whose name does not fit the configured name format of either period kind, When the user runs `/review` with it, Then Tomo says the note is not a weekly or monthly note under the setup, shows the name format, and writes nothing
  - [ ] Given a period that has not ended yet or lies in the future, When the user names it, Then Tomo says it can only review finished periods, names the last finished one, and writes nothing
  - [ ] Given an argument that is not a valid week or month (for example `2026-W54`, `2026-13`, `month 2026-W13`), When the user runs `/review`, Then Tomo says what it expected, shows one valid example, and writes nothing
  - [ ] Given a period kind that is not set up, When the user asks for it, Then Feature 1 runs first
  - [ ] Given week 53 or a week that spans two years, When it is reviewed, Then its days, its number and its note name follow the configured first day of the week (the ISO calendar when it is Monday)
#### Feature 3: Reading the period

- **User Story:** As the reviewer, I want Tomo to read everything my days hold — not only the log — so that the review reflects the whole period.
- **Acceptance Criteria:**
  - [ ] Given a period, When Tomo reads it, Then it reads every daily note dated in the period and, from each, the sections the setup names: free text (for example the Daily Log and the end-of-day fields), tracker fields, tasks with their done state, and the notes those sections link or embed for that same day (in the owner's vault the Dayplanner note and the 5 Year Journal entry of that year)
  - [ ] Given an embed or query in a daily note, When Tomo reads the day, Then the content comes from the embedded note itself, never from a plugin's rendering; content that belongs to another day or year (for example "On This Day", earlier years in the 5 Year Journal) is not used
  - [ ] Given a living task note shared by all days (for example `Next Todos`), When Tomo reads the period, Then only tasks whose done date lies in the period count as done in the period, and open tasks are labelled as open today, never as open on a past day
  - [ ] Given a daily note with only plain text, When Tomo reads it, Then the review is still built from that text
  - [ ] Given a monthly review, When Tomo reads the month, Then it also reads the weekly notes of the weeks that overlap the month, leaves out weekly content tied to a day outside the month, and marks what appears only in a weekly note (a link or theme found in no daily of the month) and what the dailies held but no weekly note mentions
  - [ ] Given a month whose weeks have no weekly notes, When Tomo reads it, Then the review is built from the dailies alone and the report says no weekly notes were found
  - [ ] Given the period, When Tomo reads it, Then it also lists the notes created in the period, the MOCs changed in the period and the MOCs those new notes link to, and calls this vault growth, not a history of edits
  - [ ] Given Tomo has read the period, When it reports, Then it shows per day whether a daily note was found, whether it held content, and which linked notes were missing or not readable
  - [ ] Given no daily note in the period holds content, When Tomo reports, Then it says so, says an empty result may also mean the Kado key cannot read the folder, and writes nothing
  - [ ] Given Kado is unreachable or refuses access, When Tomo reads, Then it stops, shows the error, and writes nothing
  - [ ] Given Kado's rate limit (shared with everything else Tomo runs at the time), When Tomo reads a period, Then it paces its calls and retries a call Kado turned away for the rate limit, waiting as long as Kado asks, so that a period is read completely rather than cut short
  - [ ] Given a run in which Kado turned calls away for the rate limit, When Tomo reports, Then it says how many calls were retried and how long it waited, and suggests raising Kado's rate limit; when the retries do not stop, it slows down further, and only when a call still fails after its retries does it name what it could not read
  - [ ] Given a run that could not read some notes, When the review document is written, Then the document says at its top which days or notes are missing from the review
#### Feature 4: The review document (Pass 1)

- **User Story:** As the reviewer, I want a review document I can edit item by item, so that only what I accept and how I phrase it lands in my note.
- **Acceptance Criteria:**
  - [ ] Given the period was read, When Tomo writes the review document, Then it lands in the inbox under a name that shows the period (for example `2026-W13 Review`), states the target note and whether it exists or will be created, carries an unticked Approved checkbox, and nothing else in the vault is written
  - [ ] Given the document, When the user opens it, Then the proposals are grouped — what happened and got done, what stayed open, recurring themes, where the vault grew, and the habits of Feature 8; for a month also what only the weekly reviews hold and what the dailies held that the weekly reviews left out — and every proposal is one ticked item with editable text
  - [ ] Given a proposal from Tomo, When it is written, Then it carries at least one link to a daily note inside the period, or, for what only a weekly review holds, to that weekly note
  - [ ] Given a group with no proposal, When the document is written, Then the group shows one line saying nothing was found for it; that line never lands in the periodic note
  - [ ] Given the review language from the setup, When Tomo writes the proposals, Then they are in that language
  - [ ] Given the review document in the inbox, When the user runs `/inbox`, Then it is neither classified as a new item nor applied as another kind of document
  - [ ] Given the sections of the periodic note the setup names as the user's own (for example reflections, "in my own words"), When Tomo proposes the review, Then it proposes only its own section and never text for those sections

#### Feature 5: Applying the review (Pass 2)

- **User Story:** As the applier, I want `/review` to turn my edited document into an instruction set, so that I apply the review in Hashi like every other Tomo change.
- **Acceptance Criteria:**
  - [ ] Given an open review document whose Approved box is not ticked, When the user continues it, Then Tomo says the document is not approved yet and names the box, and delivers nothing
  - [ ] Given an approved review document, When the user continues it, Then Tomo shows in plain text the review section as it will land — the ticked items with the user's text and the items the user added — with the target note and place, and asks Deliver or Abort; a change is made by editing the document and continuing again
  - [ ] Given approval and an existing target note, When Tomo delivers, Then the instruction set adds the review section, under its own heading, at the configured place of that note and changes nothing else in it
  - [ ] Given approval and no target note, When Tomo delivers, Then the new note — from the template when there is one, with the review section in place — waits in the inbox and the instruction set moves it to the periodic folder
  - [ ] Given an unticked or deleted item, or a group with nothing ticked, When the section is built, Then it is absent, and an empty group leaves no heading
  - [ ] Given the configured place does not exist in the target note, When Tomo prepares delivery, Then it says so before delivering and offers the headings the note has, or Abort
  - [ ] Given the delivered instruction set, When Hashi lists the inbox, Then it finds and validates it like a Pass 2 set
  - [ ] Given delivery, When Tomo writes the instruction set, Then it also writes readable instructions in the inbox, as `/inbox` and `/note` do, that let a user without Hashi apply the review by hand: the section text ready to copy, the target note and the exact place, or the new note and the folder to move it to
  - [ ] Given a delivery that fails midway, When the user next runs `/review`, Then Tomo offers to resume or drop it, and a resume finishes without duplicating what already landed
  - [ ] Given delivery succeeded, When Tomo reports, Then it names the target note, the place, the instruction set and the readable instructions, and that the next step is to apply it in Hashi or by hand, and the review document shows in its name or its first line that it was delivered

#### Feature 6: One review per period

- **User Story:** As the reviewer, I want reruns of the same period to continue what exists, so that I never get two reviews in one note or lose my edits.
- **Acceptance Criteria:**
  - [ ] Given an open review for a period, When the user asks to start over, Then Tomo names the document that will be replaced and asks again before replacing it
  - [ ] Given a delivered instruction set for the period that is not yet applied, When the user continues the review, Then Tomo delivers no second set and says the existing one waits for Hashi
  - [ ] Given the target note already holds a Tomo review section, When the user reviews that period again, Then Tomo says so, and Pass 2 replaces that section instead of adding a second one
  - [ ] Given the target note was created by the user between Pass 1 and applying in Hashi, When Tomo delivers or the user applies, Then nothing is overwritten: Tomo targets the existing note at delivery, or the apply refuses the move and Tomo's report on the next `/review` says so

#### Feature 7: Privacy

- **User Story:** As the reviewer, I want the content of my days to stay in my vault, so that a review leaves no copy of my journal anywhere else.
- **Acceptance Criteria:**
  - [ ] Given any review run, When it reports or logs, Then no daily-note text, journal answer, tracker value or proposal text appears in logs, error output or cost records; they carry only paths, dates, counts and states
  - [ ] Given a run ends by delivery, abort or drop, When it ends, Then Tomo's own working copies of daily-note content are removed, and the content exists only in the vault (including the inbox review document and the delivered note)

#### Feature 8: Habits as numbers

- **User Story:** As the reviewer, I want the tracker fields summed up for the period (for example sport days, average sleep, energy), so that I see the trend without a Dataview chart.
- **Acceptance Criteria:**
  - [ ] Given tracker fields named in the setup, When the period is read, Then the habits group proposes one item per tracker: a count of days for yes/no trackers, an average for number trackers, over the days that carry a value
  - [ ] Given days without a value, or with a value that does not fit the tracker's type (for example "ja" for a number), When the item is built, Then those days are named as missing or unreadable, never counted as zero
  - [ ] Given a vault without tracker fields, or a tracker with no value on any day, When the period is read, Then that item or the whole habits group is absent

### Should Have Features

None. Everything the owner asked for is Must Have; the remaining ideas are Could Have.

### Could Have Features

- Quarterly and yearly reviews over the same setup.
- A review of the running week or month "so far".
- The draft side pane of `/note` for the Pass 2 approval.

### Won't Have (This Phase)

- **Editing the review in a Hashi view.** v1 is edited as markdown in Obsidian; a Hashi editor tab is a later spec with a Hashi handoff (owner decision 2026-11-08). The markdown document covers the common case (80/20, owner decision 2026-11-11); edits it cannot carry safely — for example item text with `#`, `*`, `"` or `[[` that would break the document's own structure — are named in the design and left to that Hashi editor rather than solved in markdown at any cost.
- **Running the review through `/inbox`.** Pass 2 is `/review` itself (owner decision 2026-11-08).
- **Writing into daily notes,** or into the user's own sections of the periodic note.
- **Tasks from Todoist** or any source outside the vault.
- **Executing Dataview, Quoth or Templater.** Their blocks are followed to the notes they read, or skipped.
- **Changing MOCs** from the review. The review reports where the vault grew; MOC work stays with `/moc-propose`.
- **Unattended or scheduled reviews.** The user starts every review.

## Detailed Feature Specifications

### Feature: The review document and its Pass 2 (Features 4 and 5)

**Description:** The review document is the single place where the user turns Tomo's proposals into their review. It carries the period, what was read and what was missing, the target note, an Approved checkbox, and the proposals grouped by kind, each a ticked item with its text and its source-day links. The user edits it in Obsidian with the same means as the Pass 1 suggestions document: tick or untick, retype the text, delete an item, add an item in the same form. Pass 2 reads exactly what the user left.

**User Flow:**
1. User runs `/review` (or names a period).
2. System offers any open review first; otherwise it checks the setup, reads the period, reports per day what it read, and writes the review document to the inbox.
3. User opens the document in Obsidian, unticks, rewrites, deletes or adds items, ticks Approved, saves.
4. User runs `/review` again.
5. System offers the open review, shows the section as it will land and its target, and asks Deliver or Abort.
6. User approves; System delivers the instruction set and names the next step.
7. User applies the instruction set in Hashi.

**Business Rules:**
- Rule 1: Every proposal from Tomo starts ticked; the user's edits are the only thing that changes what lands.
- Rule 2: The text that lands is the text the user left, unchanged; an item the user added lands like Tomo's.
- Rule 3: Tomo never makes a proposal without a source link inside the period (a daily note, or for a month a weekly note); items the user adds need none.
- Rule 4: The document never contains text for the user's own sections of the periodic note.
- Rule 5: At most one open review and one Tomo review section per period and kind.
- Rule 6: An empty Kado result is reported as "Kado returned none", never as "nothing happened".
- Rule 7: Nothing is delivered from a document whose Approved box is not ticked.

**Edge Cases:**
- The user unticks or deletes every item → Expected: Pass 2 says there is nothing to deliver and offers Abort or start over.
- The user edits or removes a source-day link of an item → Expected: the item lands with the user's text; links are not required for the user's version.
- The user renames or moves the review document → Expected: Tomo finds it by its period, or says it cannot find it and offers to start over.
- The periodic note appears between Pass 1 and Pass 2 → Expected: Pass 2 targets the existing note and adds the section instead of creating a note.
- A daily note links a Dayplanner or journal note that does not exist or cannot be read → Expected: that day is read without it, and the per-day report names it.
- Two daily notes carry the same date → Expected: both are read and the report names the duplicate.

## Success Metrics

### Key Performance Indicators

- **Adoption:** The owner runs a weekly review for 4 consecutive finished weeks in the live vault after release (measured after the spec closes).
- **Engagement:** In a delivered review, at most 40 % of Tomo's proposals are unticked or deleted; above that the proposals are noise. Counted per group from item counts at Pass 1 and Pass 2, without storing any text.
- **Quality:** 0 writes to the vault outside the inbox before the user applies in Hashi; 0 delivered proposals from Tomo without a source-day link in the period; 0 periodic notes with two Tomo review sections.
- **Cost and time:** On the test vault's March 2026, a weekly Pass 1 costs at most $0.50, a monthly Pass 1 at most $2.00, a Pass 2 at most $0.20; a monthly Pass 1 finishes within 5 minutes.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Review read | period, kind, days in period, days with content, linked notes read / missing, weekly notes read (month), calls made, calls retried, time waited, parts not read | Coverage and rate-limit pressure |
| Review document written | period, number of proposals per group | Baseline for the engagement KPI |
| Review delivered | period, Tomo proposals kept / unticked / deleted, user items added, target existed or created | Engagement KPI, duplicate check |
| Run cost | period, kind, pass, cost, duration | Cost and time KPI (cost log after every live run) |

All events carry counts and states only, never text (Feature 7).

---

## Constraints and Assumptions

### Constraints

- Tomo writes only to the inbox; everything else reaches the vault as an instruction set the user applies in Hashi. Hashi changes existing notes and creates a note only by moving it from the inbox.
- All vault access goes through Kado and its key's permissions; Kado limits how fast Tomo may call it, and that limit is shared with everything else Tomo does at the time.
- No change to the files that need a full eval run before merge.
- No change to Hashi or Kado is required for v1.

### Assumptions

- The owner's March 2026 dailies (2026-03-20..29) are representative of their daily template; their sections, fields and embeds are the reference for full support.
- The owner's weekly and monthly notes follow ISO weeks and calendar months, as `2026-W13` (starting on a Monday) and `2026-02` show; other users may start their week on another day.
- The owner's weekly notes hold content the dailies do not (links and themes added in hindsight), which is why a monthly review reads them too.
- The owner's weekly and monthly notes have a heading near which a review section can go (`## Review of the Week`, `## Review of the month`, `### In my own words`).

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A wrong week name format targets a note that does not exist and creates a duplicate weekly note | High | Medium | The setup proposes the format from existing notes and shows the matches before saving (F1); the document and the delivery name the target and whether it exists (F4, F5) |
| Proposals read as generic summary and the user unticks most of them | High | Medium | Every proposal links its source days (F4); engagement KPI tracked from the first delivered review |
| A month needs many reads and Kado's shared rate limit turns calls away, so the review silently covers less | Medium | High | Paced calls with retries until Kado accepts, a report of retries and waiting with the advice to raise Kado's limit, and an explicit "not read" report in the run and the document for what still failed (F3) |
| A month that reads dailies and weekly reviews takes too long | Medium | Medium | Pacing is reported with its waiting time; the 5-minute KPI is measured on the test vault's March 2026 |
| Journal content leaks into logs or cost records | High | Low | Feature 7, tested over every output |
| The test vault's recent dailies are near-empty skeletons and the gap after 2026-09-12 must stay broken | Medium | High | Live walk on March 2026 (earlier periods are allowed, F2); no fixture writes into the daily folder |
| The review place does not exist in some periodic notes (older layouts) | Medium | Medium | Delivery checks the place first and offers the note's actual headings (F5) |
| Two reviews of one period land when a set is delivered twice | High | Low | Open reviews are offered first and a second set is refused (F2, F6) |

## Open Questions

None blocking. The questions of the first draft and the owner's notes on it (2026-11-11) were answered as follows, pending the owner's approval of this PRD:

- [x] Monthly source: the month's dailies and the weekly notes of its weeks, marking what only the weekly reviews hold and what they left out (owner decision 2026-11-11; was Could Have in v1.0).
- [x] Calling the review: `/review` and `/review month` for the last finished period; any argument that names a period by itself (`W13`, `2026-W13`, `2026-03`, an `@`-picked note) needs no `week` or `month` word.
- [x] First day of the week is a setup value; `/review setup` changes the setup at any time.
- [x] Rate limit: pace and retry rather than stop; report retries and suggest raising Kado's limit (owner decision 2026-11-11).
- [x] Without Hashi: readable instructions next to the instruction set, as `/inbox` and `/note` write.
- [x] The user may add own items; the source-day rule applies to Tomo's proposals only (Rule 3).
- [x] The review place is a setup value; for the owner's notes the setup proposes "before `### In my own words`", so the user reads the review and then writes.
- [x] A stray trailing space in the configured daily folder is corrected in the setup when the user confirms it (F1).

---

## Supporting Research

### Competitive Analysis

Obsidian's own ecosystem covers the mechanical half: Periodic Notes creates the weekly note, Dataview and Quoth roll up fields and logs, Templater fills dates. None of them reads the days and proposes what they mean, and none works for a vault without those plugins. AI note tools that summarise a week write the summary directly; none hands the user an item-by-item document to accept before it lands.

### User Research

- Owner decisions 2026-11-08 (Decisions Log): the review must use the whole daily note; it must not be a black box; it must work for users without Dataview/Quoth while supporting the owner's setup fully; edit in Obsidian; Pass 2 via `/review`; finished and earlier periods only.
- Test vault reading (2026-11-08): 471 dailies at the top of `Calendar/301 Daily/` (real run 2025-05 to 2026-03-31, then the deliberate gap, then near-empty 2026-09-01..12); weeklies to 2026-W13, monthlies to 2026-02; templates `t_week*.md`, `t_month*.md` in `X/900 Support/930 Templater/`. A March daily holds habit fields, a Daily Log and end-of-day review fields, and links or embeds `Efforts/300 Planner/DP-<date>.md` (Dayplanner), `Calendar/305 5 Year Journal/5J-<date>.md` and `Efforts/500 OnGoing/Next Todos.md`.
- The owner's weekly note already rolls up each day's log with Quoth and the habits with Dataview, and holds hand-written reflection sections.
- Two review passes of the first draft (technical and user side, 2026-11-08) found the open-review default, the double delivery, the missing Approved signal, untestable MOC-history and keep-ratio criteria and several missing error cases; all are worked into this version.

### Market Data

Not applicable: a personal-vault feature for the existing Tomo user base.
