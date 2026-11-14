---
title: "/review: review material for the user's own template sections"
status: approved
version: "1.2"
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

`/review` is a review helper: for a finished week, month or quarter, Tomo reads what each section of the user's own review template asks for — "What Went Well", "Learnings of the Week", "I look forward to", "Things which were hard this month" — searches the period's notes for exactly that, and hands the user short reminders per section of what happened and what will need to happen. The user turns those reminders into their own thoughts. Because the reminders already sit in the section they belong to, the user no longer goes back and forth between the review document, the daily notes and the sections of their note.

### Problem Statement

Spec 045 (`/review`, shipped in PR #257) reads a week's or a month's daily notes and proposes a review in fixed groups — done, open, themes, growth, habits — that lands as one Tomo-owned section, "Tomo Review", in the weekly or monthly note. The user's template is used only to find the place for that section. The owner uses that review as raw material for writing their own review in the sections of their template, and this leaves gaps (#263, #256, owner notes 2026-11-14):

- **The material is gathered by Tomo's groups, not by what the user's sections ask for.** The owner's templates carry the sections a review is written in: the weekly template "In my own words" with "What Went Well", "Start Doing", "Stop Doing", "Continue Doing" and "Learnings of the Week"; the monthly template "Goals and Wishes" (four sub-sections), "I look forward to", "This will be challenging", "Things I did well this month" and "Things which were hard this month". Some match a group closely (done and themes fit "What Went Well", growth fits "Learnings of the Week"); others — "Start Doing", "Stop Doing", "This will be challenging", the goals — have no group, so Tomo never looks for their material.
- **Writing the review means going back and forth.** The owner fills each section by hand every week and month, picking from the review document's groups, rereading days for what no group holds, and copying item by item — the back-and-forth the owner named as the reason for this spec.
- **Spec 045 forbids putting material into the user's sections.** Its PRD (F4-AC7, Rule 4, Won't-Have) rules out any text for the user's own sections. The owner lifted that rule on 2026-11-13: the material is a memory aid the user edits, so it may go into the user's sections, placed by headings only.
- **A whole group can be dropped only item by item.** The spec 045 live walk produced 21 items in 5 groups for 2026-W13 and 35 for March 2026. A user who does not want, say, the vault growth this time unticks every item of it one by one (#256).
- **Quarterly reviews are not supported.** The owner also writes quarterly reviews (the test vault has a `Calendar/304 Quarterly` folder); spec 045 left quarters as a Could Have, so a quarter gets no help at all.
- **Templates differ per variant and repeat their headings.** The private and work variants of the templates use different heading texts and levels; "In my own words" and "Reflections" occur in more than one kind and at different levels. A mapping by heading name alone would target the wrong section.

### Value Proposition

- Each section of the user's template gets the material it asks for, whatever kind of review it is — a look back, a lesson, a plan, a worry — because Tomo searches the period's notes for what the section's description and keywords name.
- The material is a set of reminders with their source days, short enough to read and check, which the user turns into their own review.
- The reminders sit in the section they belong to, so writing the review needs no back-and-forth and no copying by hand.
- What a section receives is the user's own definition — a description and optional keywords — proposed by Tomo from the template and confirmed once, like the trackers of the daily notes.
- Week, month and quarter work the same way.
- Nothing of spec 045 is taken away: everything it reads and proposes is still read and proposed; what no section takes stays in the "Tomo Review" section.
- The user's own text in those sections is never changed; Tomo's lines sit in a block of their own that a later review of the same period replaces.
- One checkbox drops a whole section of the review document.
- Everything still goes through the 2-pass model: Pass 1 writes the review document to the inbox, Pass 2 delivers an instruction set the user applies in Hashi or by hand.

## User Personas

### Primary Persona: The reviewer

- **Demographics:** As in spec 045: the owner of a personal Obsidian vault who runs Tomo in its container and keeps daily notes, and writes weekly, monthly and quarterly reviews. Comfortable in a console session. Does not read frontmatter or use a tag pane; filenames, checkboxes and Tomo's own reports are the signals. Writes mostly in German.
- **Goals:** Find, in each section of their own template, reminders of what the week, month or quarter held for that section, so that writing the review means thinking and writing rather than collecting. Drop a section of the proposal at once when it does not fit this time.
- **Pain Points:** The spec 045 review gives material by Tomo's groups, not by the sections the user writes in, so writing means switching between the review document, the days and the note. Sections with no matching group get nothing. Quarters get no help. Unticking a whole group means unticking every item. Anything that touches their own text in a section feels like losing the authorship of the review.

### Secondary Personas

**The vault keeper.** The owner in the setup role: tells Tomo once, per template, which sections of the weekly, monthly and quarterly note receive review material, what belongs in each, where in the section Tomo's lines go and how many items a section may hold; and, for the quarter, where quarterly notes live, how they are named and which template they use. Wants this proposed by Tomo from the template and confirmed in the existing setup dialogue, never a file to edit.

**The applier.** The owner later in Obsidian, applying the instruction set in Hashi, or a user without Hashi applying it by hand. Needs to know, per section, what lands where, and needs an apply that never changes the user's own text.

**The plain-template user.** A Tomo user whose weekly, monthly or quarterly template has no sections that suit review material (only automatic blocks, or no template at all). Needs `/review` to keep working exactly as in spec 045.

## User Journey Maps

### Primary User Journey: Finished month into the user's own sections

1. **Awareness:** A month has ended; the user wants to write "Things I did well this month" and "Things which were hard this month" and plan the next one.
2. **Consideration:** Spec 045 gives a "Tomo Review" section in fixed groups the user then picks from, section by section; the alternative is rereading the month.
3. **Adoption:** The setup already maps the monthly template's sections; the user runs `/review month` as before.
4. **Usage:** Tomo reads the month, looks for what each mapped section asks for, and writes the review document: one part per mapped section with its reminders and source days, then the "Tomo Review" part for what no mapped section takes. The user unticks the section they do not want this time, rewrites items, adds their own, ticks Approved and runs `/review` again. Tomo shows per section what lands and where, asks Deliver or Abort, and delivers the instruction set. After the apply in Hashi each mapped section of the monthly note holds Tomo's block beside the user's own text, and the user writes their review from it.
5. **Retention:** Each week, month and quarter the reminders arrive in the same sections; the user's review starts from them.

### Secondary User Journeys

1. **First mapping (vault keeper).** The setup for a period kind exists from spec 045 but carries no section mapping, or the setup runs for the first time. Tomo proposes, from the template's headings, which sections receive material, with a description, optional keywords, the placement and the item cap per section, inside the existing confirm step; the user confirms or corrects one row at a time.
2. **Changing the mapping (vault keeper).** `/review setup` shows the current mapping and runs the same proposal-and-confirm dialogue, for example after a template change or to map "This will be challenging".
3. **First quarterly review (vault keeper, reviewer).** A quarter has ended; the user runs `/review quarter`. No quarterly setup exists, so Tomo proposes the quarterly folder, name format, template and section mapping in one confirm step; after confirming, Tomo reads the quarter's daily notes and its weekly and monthly reviews and writes the review document as for a month.
4. **Dropping a section (reviewer).** In the review document the user unticks one section's checkbox; at Pass 2 Tomo warns in one line that the section, with any items the user added there, will not land.
5. **Reviewing a delivered period again (reviewer, applier).** The user reviews a period whose note already holds Tomo's blocks. The new review replaces Tomo's earlier blocks and nothing else; the user's text around them stays.
6. **A mapped heading is missing in the note (reviewer).** The target note lacks a mapped heading (an older layout, a renamed heading). Tomo names it before delivery and lets the user choose what happens to that section's material.
7. **No periodic note yet (plain-template user, reviewer).** The note does not exist; Tomo builds it from the template and fills the mapped sections the template carries as plain headings; the rest goes into the "Tomo Review" section.
8. **Nothing to map (plain-template user).** The template offers no suitable section; the setup says so and `/review` behaves as in spec 045.

## Feature Requirements

### Must Have Features

#### Feature 1: Material per section (Pass 1)

- **User Story:** As the reviewer, I want Tomo to search the period's notes for what each section of my template asks for and give me short reminders with their source days, condensed to the section's item cap, so that I have the material for every kind of review section and can check every item.
- **Acceptance Criteria:**
  - [ ] F1-AC1: Given a confirmed mapping for the period kind's template, When Tomo reads the period, Then it reads everything spec 045 reads (its Feature 3: the daily sections the setup names, their linked notes, the weekly notes of a month, the vault growth; for a quarter also Feature 6), and in those notes it looks for what each mapped section's description and keywords ask for; a mapping adds what Tomo looks for and never narrows what it reads
  - [ ] F1-AC2: Given a mapped section whose description asks for something no spec 045 group covers (for example what to start or stop doing, or what will be challenging next month), When the period's notes hold matching material, Then the section receives items for it; what a section receives follows its description and keywords, not the fixed group set
  - [ ] F1-AC3: Given a proposal for a mapped section, When Tomo writes it, Then it is one item that reminds the user of something the period shows — what happened, or what will need to happen — with at least one link to a daily note inside the period, or, for what only a weekly or monthly review of the period holds, to that note; it leaves judgement and reflection to the user and is not written as the user's finished review text
  - [ ] F1-AC4: Given a forward-looking section, When Tomo proposes items for it, Then each item is a suggestion drawn from something the period shows and links the day it came from; Tomo invents no item without a source
  - [ ] F1-AC5: Given more material for a section than its item cap, When Tomo writes it, Then it merges related findings into fewer items, keeps the source links of every merged finding, and never exceeds the cap
  - [ ] F1-AC6: Given a finding that fits more than one section, When Tomo writes the proposals, Then it proposes it in one section, the one whose description it fits best, and in no other section or group; an item proposed in two places (the same text, or the same sources with the same first line) is refused before the document is written
  - [ ] F1-AC7: Given what no mapped section takes, When Tomo writes the proposals, Then it goes into the spec 045 groups of the "Tomo Review" part, so that every finding a spec 045 group would hold lands either in a mapped section or there; a group with nothing left is absent from that part, and with no group left the "Tomo Review" part is absent
  - [ ] F1-AC8: Given a mapped section for which nothing in the period fits, When the document is written, Then the section shows one line saying nothing was found and its section checkbox starts unticked
  - [ ] F1-AC9: Given a monthly or quarterly review, When Tomo builds the proposals, Then the spec 045 marks for what only a weekly review holds and what the weekly reviews left out (month), and the marks of F6-AC4 (quarter), stay on the items they apply to, in whichever section those items land
  - [ ] F1-AC10: Given no mapping for the period kind, When Tomo builds the proposals, Then they are the spec 045 groups exactly as spec 045 defines them, for a quarter with the groups of F6-AC4

#### Feature 2: Section mapping in the setup

- **User Story:** As the vault keeper, I want Tomo to propose which sections of my weekly, monthly and quarterly template receive review material, what belongs in each, where Tomo's lines go and how many items each may hold, so that I confirm it once per template and never edit a file.
- **Acceptance Criteria:**
  - [ ] F2-AC1: Given a period kind whose template Tomo can read, When the setup proposes its values (`/review` without a mapping, or `/review setup`), Then in the same confirm step it proposes a section mapping: for each suitable heading of the template, the heading with its level and parent heading, a description of what Tomo is to look for in the period's notes for that section, optional keywords, the placement (before the heading, directly under the heading, or at the end of the section) and a maximum number of items; nothing is saved until the user confirms
  - [ ] F2-AC2: Given the proposal, When Tomo shows it, Then it is one table in the existing confirm step — no extra question turn — and the user corrects a row by naming it and the change in plain text, removes a row, or adds a heading the proposal left out
  - [ ] F2-AC3: Given a heading whose text carries Templater code or a link, a heading that repeats under parents that change per period (for example the day headings of a week), a section that holds only automatic content (queries, embeds, buttons, inline fields), or a section the user marked off-limits (F2-AC11), When Tomo builds the proposal, Then it does not offer that heading, and it names the left-out headings with the reason in one line each
  - [ ] F2-AC4: Given the user adds a heading Tomo did not offer, When the heading falls under one of the reasons of F2-AC3, Then Tomo refuses it and says the reason; any other heading of the template is accepted
  - [ ] F2-AC5: Given a heading text that occurs more than once in the template (for example "In my own words" at two levels), When it is mapped, Then the mapping names it by its text, level and parent heading, and the proposal shows these so the user sees which one is meant
  - [ ] F2-AC6: Given a template with forward-looking sections (for example "I look forward to", "This will be challenging", "Goals and Wishes"), When Tomo proposes the mapping, Then it may propose them with a description that asks for suggestions drawn from what the period shows
  - [ ] F2-AC7: Given a mapped section, When Tomo proposes its description, Then it may name one or more of the spec 045 groups (done, open, themes, growth, habits; for a month also only-in-weekly and not-in-weekly; for a quarter also the groups of F6-AC4) as the section's starting point; a group named by no mapped section stays in the "Tomo Review" section
  - [ ] F2-AC8: Given the private and the work variant of a template, or the templates of two period kinds, When each is set up, Then each has its own mapping, and a mapping saved for one never applies to another
  - [ ] F2-AC9: Given a template with no suitable heading, or no template, When the setup runs, Then Tomo says no section can be mapped, saves no mapping, and the review works as in spec 045
  - [ ] F2-AC10: Given the user corrects or confirms the mapping, When it is saved, Then no other setup value changes, the descriptions and keywords are stored as the user confirmed them, and the review request continues in the same session
  - [ ] F2-AC11: Given the mapping proposal, When the user marks a heading of the template off-limits in the same confirm step — either the heading only or the heading with its sub-sections — Then Tomo never writes into that section (or, with its sub-sections, into any of them), whatever the mapping says; nothing is off-limits unless the user marks it, no heading name is off-limits by default, and Tomo may still read the user's own text there as a source, as spec 045 reads the weekly notes' own sections for a month

#### Feature 3: The review document by section (Pass 1)

- **User Story:** As the reviewer, I want the review document laid out by the sections of my note, each with one checkbox, so that I can drop a section at once and edit the rest item by item.
- **Acceptance Criteria:**
  - [ ] F3-AC1: Given a mapping, When Tomo writes the review document, Then it holds one part per mapped section, in the order of the template, headed by the section's name, followed by the "Tomo Review" part when F1-AC7 leaves anything for it; the spec 045 parts of the document (period, what was read and missing, target note, Approved checkbox) stay
  - [ ] F3-AC2: Given a section part, When the user opens the document, Then it carries one section checkbox, ticked by default except as F1-AC8 says, with positive wording in the review language, and below it the section's items, each ticked and editable as in spec 045
  - [ ] F3-AC3: Given a section part, When the document is written, Then the part says where in the note it lands: the heading and the placement
  - [ ] F3-AC4: Given an unticked section checkbox, When the user runs Pass 2, Then the whole section is absent from the delivery, including items the user added to it, and the Pass 2 preview says so in one line naming the section and the number of the user's own items dropped with it
  - [ ] F3-AC5: Given a ticked section checkbox whose items are all unticked or deleted, When Pass 2 builds the delivery, Then that section receives nothing and the preview names it as empty
  - [ ] F3-AC6: Given the user deletes or breaks a section checkbox line, When Pass 2 reads the document, Then it says which section's checkbox is missing and how to restore it, and delivers nothing

#### Feature 4: Delivery into the user's sections (Pass 2)

- **User Story:** As the applier, I want Tomo's lines to land in each mapped section at the chosen place and in a block of their own, so that my own text in the section stays exactly as it was.
- **Acceptance Criteria:**
  - [ ] F4-AC1: Given an approved review document and an existing target note, When Tomo delivers, Then for each kept section the instruction set adds Tomo's block — the ticked items with the user's text and the items the user added — at the section's placement, and the "Tomo Review" section as in spec 045 when anything is left for it; nothing else in the note changes
  - [ ] F4-AC2: Given Tomo's block in a section, When it is written, Then it sits between invisible start and end markers (hidden in Obsidian's reading view) that name the section, and carries no visible prefix or heading of its own
  - [ ] F4-AC3: Given a section that already holds the user's text, When the instruction set is applied, Then every character of the user's text in that section is unchanged; Tomo's block is added, never put in place of the user's text
  - [ ] F4-AC4: Given a mapped heading that is missing in the target note, or occurs there more than once so that the mapped one cannot be targeted unambiguously, When Tomo prepares delivery, Then before delivering it names each such section in the existing Deliver step and offers, per section, to leave it out, to put its items into the "Tomo Review" section, or to Abort the delivery; nothing is written blind
  - [ ] F4-AC5: Given no target note, When Tomo builds the new note, Then mapped sections are filled only where the note has the mapped heading as plain text; for a template that Templater runs on creation the spec 045 rule applies (the template's Tomo variant, or the template as it is); the material of a mapped section whose heading the new note lacks goes into the "Tomo Review" section, and the document says so before delivery
  - [ ] F4-AC6: Given the Pass 2 preview, When Tomo shows it, Then it lists per section the heading, the placement and the lines that land, and the "Tomo Review" section, before asking Deliver or Abort
  - [ ] F4-AC7: Given delivery, When Tomo writes the readable instructions, Then they carry, per section, the block ready to copy, the heading and the exact placement, so that a user without Hashi can apply it by hand

#### Feature 5: Reviewing a delivered period again

- **User Story:** As the reviewer, I want a second review of the same period to replace Tomo's earlier blocks in my sections, so that a section never holds two Tomo blocks and my own text stays.
- **Acceptance Criteria:**
  - [ ] F5-AC1: Given a target note whose mapped sections hold Tomo's blocks from an earlier review of the period, When the user reviews the period again and delivers, Then the instruction set uses Hashi's action that replaces only the text between Tomo's markers: each kept section's earlier block is replaced by the new one, the user's text around it is unchanged, and a section unticked this time keeps its earlier block
  - [ ] F5-AC2: Given a re-run in which a kept section holds no earlier Tomo block (for example a section mapped after the first review), When Tomo delivers, Then that section's block is added as in F4-AC1
  - [ ] F5-AC3: Given an earlier block whose end marker the user removed, When Tomo prepares delivery, Then it names that section, does not replace anything in it, and offers to leave that section out or to Abort the delivery
  - [ ] F5-AC4: Given an earlier block the user edited after the apply, When the preview of a re-run shows the sections whose block will be replaced, Then it says that edits inside Tomo's block are replaced and that text outside the block is kept
  - [ ] F5-AC5: Given a re-run, When the instruction set is applied, Then no section holds more than one Tomo block for the period

#### Feature 6: Quarterly reviews

- **User Story:** As the reviewer, I want `/review` to help with my quarterly review the way it helps with a month, reading the quarter's days and my weekly and monthly reviews, so that the quarter's sections get their material too.
- **Acceptance Criteria:**
  - [ ] F6-AC1: Given no quarterly setup, When the user asks for a quarter, Then the spec 045 setup (its Feature 1) runs for the quarterly note — folder, name format, template, review place, review language — together with the section mapping of Feature 2, in one confirm step; the proposed name format follows existing quarterly notes, or `2026-Q1` when there are none, and nothing is saved until the user confirms
  - [ ] F6-AC2: Given no open review, When the user runs `/review quarter`, `/review 2026-Q1` or `/review` with a quarterly note picked with `@`, Then the period is the last finished calendar quarter, the named quarter, or the picked note's quarter; a quarter without a year (`Q1`) is the most recent finished one of that number, and Tomo names the year it chose before reading; an open review is offered first as in spec 045
  - [ ] F6-AC3: Given an argument that is not a valid quarter (for example `2026-Q5`), or a quarter that has not ended yet, When the user runs `/review` with it, Then Tomo says what it expected or that it can only review finished periods, shows one valid example or names the last finished quarter, and writes nothing
  - [ ] F6-AC4: Given a quarter, When Tomo reads it, Then it reads every daily note of the quarter as spec 045 reads a month's, and also the weekly notes of the weeks that overlap the quarter and the monthly notes of its months, leaving out review content tied to a day outside the quarter; it marks what appears only in the monthly reviews (found in no daily of the quarter) and what the dailies held but no monthly review mentions, as spec 045 does for a month with its weekly reviews; the weekly notes are read as sources, not marked separately
  - [ ] F6-AC5: Given a quarter whose months have no monthly notes, or whose weeks have no weekly notes, When Tomo reads it, Then the review is built from what exists and the report says which monthly and weekly notes were not found
  - [ ] F6-AC6: Given a quarterly review, When it is written, delivered or run again, Then spec 045's review document, Pass 2, one review per period, privacy and habits, and Features 1 to 5 of this spec, apply as for a month, with the quarterly note as the target

### Should Have Features

#### Feature 7: Choosing and correcting the template

- **User Story:** As the vault keeper, I want a mistyped template name to show me the templates Tomo found, and a corrected template to update the place and the mapping, so that a typo never leaves me with a mapping for the wrong template (#267).
- **Acceptance Criteria:**
  - [ ] F7-AC1: Given the user types a template name that Tomo does not find, When the setup answers, Then it says the name was not found and lists the templates it found whose name fits the period kind, and asks again; nothing is saved
  - [ ] F7-AC2: Given the user corrects the template in the setup dialogue, When Tomo shows the proposal again, Then the review place and the section mapping are proposed anew from the corrected template, and no row from the earlier template remains
  - [ ] F7-AC3: Given a template correction that leaves a mapped heading out, When Tomo shows the new proposal, Then it names the headings of the earlier mapping that the corrected template no longer has

### Could Have Features

- The weekly, monthly and quarterly mappings in one confirm turn when several period kinds are set up in the same session.
- Negative keywords per section (what must not go there), as some trackers carry.
- Moving an item from one section to another in the review document.
- Yearly reviews over the same setup (left over from spec 045's Could Have).

### Won't Have (This Phase)

- **Renaming the command or the skill** (for example to "review-helper"). The command stays `/review`; a skill rename is decided at the skill revisit #259.
- **Removing anything spec 045 reads, proposes or delivers.** This spec adds material per section, a third period kind and new places for the material; it takes nothing away.
- **Writing into inline fields** or placing anything other than by headings.
- **Replacing a whole section** of the user's note; Tomo only adds its block or replaces its own block.
- **Writing into sections the user marked off-limits** (F2-AC11), whatever the mapping says.
- **New headings in the user's note** other than the "Tomo Review" heading of spec 045.
- **Executing Templater** to fill a new note's headings; the spec 045 rule for such templates stays.
- **Quarters other than calendar quarters** (for example a business year starting in another month).
- **The bare "stop" answer and the saved week rule** of #267; they stay in #267.
- **Editing the review in a Hashi view** (unchanged from spec 045).

### Amendments to spec 045

Everything of spec 045's PRD (v1.8) stays in force. No spec 045 feature or criterion is removed; the amendments below change where the material goes, extend a criterion to sections or to the quarter, or lift a restriction:

- **F2 (choosing the review)** and **F3-AC5 / F3-AC6 (reading a month with its weekly notes)**: extended by Feature 6 to a third period kind, the quarter, read with its weekly and monthly notes.
- **Could-Have "Quarterly and yearly reviews"**: quarterly moves into this spec as a Must (Feature 6); yearly stays a Could Have.
- **F4-AC2** (the fixed group set): amended. With a mapping, the document is laid out by mapped sections and the spec 045 groups hold what no mapped section takes, so every group's material is still proposed (F1-AC7, F3-AC1). Without a mapping, F4-AC2 applies unchanged (F1-AC10).
- **F4-AC4** (a group with no proposal shows one line): extended to mapped sections, whose checkbox then starts unticked (F1-AC8).
- **F4-AC7** and **Rule 4** (no text for the user's own sections): narrowed to sections the user marked off-limits (F2-AC11). Tomo proposes material for mapped sections; it never proposes text for an off-limits section. Spec 045's list of the user's own sections keeps its other role unchanged: their text in the weekly notes is read as a source for a month, and the "Tomo Review" section is never placed in them.
- **Won't-Have "writing into … the user's own sections of the periodic note"**: lifted for mapped sections; writing into daily notes stays out.
- **F5-AC3** (the instruction set adds the review section under its own heading): extended by F4-AC1. The "Tomo Review" section is added when something is left for it.
- **F5-AC6** (unticked items and empty groups are absent): extended by F3-AC4 and F3-AC5.
- **F6-AC3** and **Rule 5** (one Tomo review section per period, replaced on re-run): extended by Feature 5 to at most one Tomo block per mapped section.
- **Constraint "No change to Hashi or Kado is required for v1"**: Feature 5 depends on a new Hashi action; everything else needs no Hashi or Kado change.

## Detailed Feature Specifications

### Feature: The sectioned review — gathering, document and delivery (Features 1, 3, 4 and 5)

**Description:** With a mapping, Tomo reads the period as spec 045 does and, in addition, looks in the period's notes for what each mapped section's description and keywords ask for. The review document mirrors the user's note: one part per mapped section, each with a section checkbox and short reminders for that section with their source days, then the "Tomo Review" part for the rest. Pass 2 turns every kept section into a block of Tomo's lines at the section's placement, between invisible markers, and leaves the user's own text in the section as it is. A later review of the same period replaces only those blocks. Week, month and quarter follow the same flow.

**User Flow:**
1. User runs `/review` (or names a week, month or quarter).
2. System checks the setup and its mapping, reads the period, gathers per mapped section what its description asks for, and writes the review document with one part per mapped section and the "Tomo Review" part.
3. User unticks a section they do not want, edits, deletes or adds items, ticks Approved, saves.
4. User runs `/review` again.
5. System checks every mapped heading in the target note, names missing or ambiguous sections and sections whose earlier block lost its end marker, with their choices, shows per section what lands where and which earlier blocks are replaced, and asks Deliver or Abort.
6. User approves; System delivers the instruction set and the readable instructions.
7. User applies the instruction set in Hashi or by hand, and writes their review from the reminders.

**Business Rules:**
- Rule 1: Spec 045 Rules 1, 2, 3, 6 and 7 apply unchanged (items start ticked, the user's text lands unchanged, every Tomo proposal has a source link in the period, empty Kado results are reported as such, nothing is delivered without Approved).
- Rule 2: What a mapped section receives follows its description and keywords; a mapping adds what Tomo looks for and never narrows what it reads or proposes.
- Rule 3: Tomo's lines in a user's section stay inside Tomo's markers; the user's text outside them is never changed.
- Rule 4: A section the user marked off-limits never receives anything.
- Rule 5: A finding is proposed in one section or group; no item is proposed in two places.
- Rule 6: A section's items never exceed its cap.
- Rule 7: An unticked section checkbox drops the whole section, including the user's own items in it.
- Rule 8: At most one Tomo block per mapped section and period, and at most one "Tomo Review" section per period.
- Rule 9: A section whose heading cannot be found exactly once in the target note is never written without the user's choice.

**Edge Cases:**
- The user renames a mapped heading in the note → Expected: F4-AC4 names it as missing; the setup's mapping is unchanged until the user runs `/review setup`.
- The user moves Tomo's block to another section → Expected: a re-run finds the block by its markers, names where it is now, and replaces it there only after the user confirms.
- Every section is unticked and nothing is left for the "Tomo Review" section → Expected: Pass 2 says there is nothing to deliver and offers Abort or start over (spec 045 edge case, extended).
- A re-run leaves nothing for the "Tomo Review" section that an earlier review wrote → Expected: Tomo names the earlier section and says it stays as it is; removing it is the user's choice.
- The template changed since the mapping was saved → Expected: F4-AC4 catches missing headings in the note; the setup is not changed by `/review` itself.
- The user adds items to a section whose checkbox is unticked → Expected: F3-AC4's one-line warning names them before delivery.
- A heading of the note sits inside a fenced code block → Expected: it does not count as a heading.
- A week overlaps two quarters → Expected: its weekly note is read for both quarters, each time only with the content tied to that quarter's days (F6-AC4).

## Success Metrics

### Key Performance Indicators

- **Adoption:** The owner runs 4 consecutive weekly reviews, 1 monthly review and 1 quarterly review with a section mapping in the live vault after release (measured after the spec closes).
- **Engagement — section fit:** Over those reviews, at least 70 % of the mapped sections that received items stay ticked at Pass 2. Counted from section counts, without storing any text.
- **Engagement — items:** At most 40 % of Tomo's proposals are unticked or deleted over a delivered review (spec 045 KPI, now also reported per section); habit items are not counted.
- **Quality:** 0 writes to the vault outside the inbox before the user applies; 0 changed characters of the user's own text in a mapped section after an apply; 0 sections with two Tomo blocks for a period; 0 items proposed in two places; 0 writes to an off-limits section; 0 Tomo proposals without a source link in the period.
- **Cost and time:** The spec 045 limits stay on the test vault's March 2026: weekly Pass 1 at most $0.50, monthly Pass 1 at most $2.00, Pass 2 at most $0.75, monthly Pass 1 within 7 minutes. A quarterly Pass 1 on the test vault's first quarter of 2026 costs at most $5.00 and finishes within 20 minutes (to confirm: scaled from the month's $2.00 and 7 minutes for about three times the reads, plus the quarter's weekly and monthly notes). The mapping adds no question turn to the setup.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Mapping proposed | period kind, headings offered, headings left out per reason | Proposal coverage |
| Mapping saved | period kind, sections mapped, rows corrected / removed / added by the user | Proposal quality |
| Review read | as spec 045, plus for a quarter: weekly and monthly notes read / not found | Coverage, quarterly cost baseline |
| Review document written | period, kind, items per section, sections empty, items in the "Tomo Review" part per group, Tomo items without a source link | Baseline for the engagement KPIs, source-link check |
| Review delivered | period, kind, sections kept / unticked / empty, per section Tomo items kept / unticked / deleted and user items added, user items dropped with an unticked section, sections missing or ambiguous in the target and the choice taken, earlier blocks replaced, sections with a broken earlier block and the choice taken | Section fit, item engagement, re-run check |
| Run cost | period, kind (week, month, quarter), pass, cost, duration, setup turns | Cost and time KPI |

All events carry counts and states only, never text (spec 045 Feature 7, unchanged).

---

## Constraints and Assumptions

### Constraints

- No spec 045 feature is removed: everything it reads, proposes and delivers stays available; this spec only adds material per section, the quarter as a period kind, and new places for the material. Every amendment above is checked against this.
- Tomo writes only to the inbox; everything else reaches the vault as an instruction set the user applies in Hashi or by hand.
- Placement is by headings only. Hashi matches a heading by its exact text and, when a text occurs more than once, takes the first; Tomo must therefore detect duplicates before delivery (F4-AC4).
- Replacing Tomo's earlier block (F5-AC1) uses a new Hashi action that replaces only Tomo's marked block. This spec assumes the action exists; there is no fallback and no refusal for a Hashi version without it.
- The handoff to Hashi for that action — including the changes to the instruction-set schema files — goes out through the MiYo handoff protocol as soon as the SDD defines the action; Hashi builds it, orchestrated by the owner.
- The change is merged only after Tomo and Hashi work together in the test vault: first delivery, re-run with block replacement, for a week, a month and a quarter.
- Spec 045 Feature 7 applies unchanged: no note text in Tomo's logs, error output or cost records. The section descriptions and keywords are setup text the user confirms, not note text.
- As in spec 045, no change to the files under the eval gate is planned; if one becomes necessary, it needs the full-suite run before merge.

### Assumptions

- The owner's private and work templates in the test vault are representative of the sections the owner fills by hand.
- The quarterly template's contents are not known yet; the test vault's `Calendar/304 Quarterly` folder exists, and the quarterly mapping is proposed from whatever template the setup finds there or in the templates folder.
- Quarters are calendar quarters (January to March, April to June, July to September, October to December).
- Invisible markers stay invisible in Obsidian's reading view and survive the user's edits around them.
- The spec 045 groups are good starting points for the owner's sections (done and themes for "What Went Well", growth for "Learnings of the Week", done and only-in-weekly for "Things I did well this month", open and not-in-weekly for "Things which were hard this month").
- An item cap set generously (about today's amount per group) leaves enough material to write from.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| An apply changes or removes the user's own text in a section | High | Low | Tomo only adds its block or replaces its own block (Rule 3); whole-section replacement is a Won't-Have; quality KPI 0 changed characters |
| The material lands in the wrong one of two same-named headings | High | Medium | Headings mapped by text, level and parent (F2-AC5); ambiguous targets named before delivery (F4-AC4) |
| The Hashi action for re-runs is late or behaves differently than the SDD defines | Medium | Medium | The handoff goes out as soon as the SDD defines the action; the PR merges only after Tomo and Hashi work together in the test vault (Constraints) |
| A section's description asks for something the notes rarely hold, so the section stays empty | Medium | Medium | One "nothing found" line and an unticked checkbox (F1-AC8); the description is corrected at setup (F2-AC2); section-fit KPI |
| Reminders read like a finished review and crowd out the user's own writing | Medium | Medium | Reminders state what happened or what will need to happen and leave judgement to the user (F1-AC3); cap per section (F1-AC5) |
| Suggestions for forward-looking sections feel foreign | Medium | Medium | Every suggestion cites its source day (F1-AC4); one checkbox drops the section (F3-AC4); section-fit KPI |
| The proposed mapping does not match what the user writes in a section | Medium | Medium | Descriptions confirmed and corrected at setup (F2-AC2); section-fit KPI tracked per section |
| The cap cuts material the user needed | Medium | Low | Merge rather than cut, sources kept (F1-AC5); the cap is a setup value |
| A section mapping loses material spec 045 used to propose | Medium | Low | Every finding lands in a section or in the "Tomo Review" part (F1-AC7); a mapping never narrows what is read (F1-AC1) |
| A quarter needs about three months of reads and runs long or costly under Kado's rate limit | Medium | High | Spec 045's pacing, retries and "not read" report apply (F6-AC6); quarterly cost and time KPI measured on the test vault's first quarter of 2026 |
| Templates that change per variant or over time break the mapping | Medium | Medium | Mapping per template (F2-AC8); missing headings named before delivery (F4-AC4); template correction re-proposes the mapping (F7-AC2) |
| The user's added items vanish with an unticked section unnoticed | Medium | Low | One-line warning with their count before delivery (F3-AC4) |

## Open Questions

Decisions proposed by the coordinator and confirmed by the owner on 2026-11-14:

- [x] #267 split: in this spec the not-found template with candidates (F7-AC1), the re-proposal after a template correction (F7-AC2) and the same-named heading told apart by level and parent (F2-AC5); the bare "stop" answer and the saved week rule stay in #267.
- [x] ~~The setup's list of the user's own sections stays, as the never-write list~~ — superseded in v1.2: the user marks off-limits headings in the confirm step, heading only or with sub-sections, nothing by default (F2-AC11, Rule 4); spec 045's own-sections list keeps its reading role.
- [x] Headings with Templater code or links, headings under parents that change per period, and sections with only automatic content are not offered as targets (F2-AC3).
- [x] New-note mode: mapped sections are filled only where the new note has the heading as plain text; Templater-on-create templates keep the spec 045 rule; the rest goes to the "Tomo Review" section (F4-AC5).
- [x] A missing or ambiguous mapped heading in the target note: leave the section out, put it into the "Tomo Review" section, or Abort, chosen in the existing Deliver step (F4-AC4).
- [x] A section unticked on a re-run keeps its earlier block rather than having it removed (F5-AC1).
- [x] An earlier "Tomo Review" section with nothing left for it on a re-run stays as it is (Edge Cases).
- [x] The default item cap the setup proposes: 8 items per section (spec 045's W13 had about 4 items per group, March about 5; the cap leaves room above that).
- [x] What a re-run does before the Hashi action exists (v1.0 F5-AC2): decided by the owner on 2026-11-14 — the action is assumed to exist; a re-run always replaces only Tomo's block through it (F5-AC1); no fallback and no refusal for an older Hashi; the PR merges only after Tomo and Hashi work together in the test vault (Constraints).
- [x] The core of the spec is gathering material per section; delivery into the sections serves it (owner notes 2026-11-14; Vision, Feature 1).
- [x] Quarterly reviews join this spec as a third period kind (owner 2026-11-14; Feature 6).
- [x] The command stays `/review`, described as a review helper; a skill rename is decided at #259 (Won't Have).

Added by v1.1, to confirm:

- [x] Quarterly cost and time limit (confirmed 2026-11-14): at most $5.00 and 20 minutes for a quarterly Pass 1 on the test vault's first quarter of 2026 (Success Metrics).
- [x] Quarterly marks (decided 2026-11-14): one level up from the month — what only the monthly reviews hold and what no monthly review mentions; the weekly notes are read as sources without a separate mark (F6-AC4).
- [x] Calendar quarters only, confirmed 2026-11-14; yearly reviews stay Could Have for a later spec (Assumptions, Won't Have); a quarter start other than January would be a later setup value.

---

## Supporting Research

### Competitive Analysis

Periodic Notes and Templater create the weekly, monthly or quarterly note with the user's sections; Dataview and Quoth roll fields and logs into them. None gathers material for what a given section asks for, and none lets the user accept that material item by item and section by section before it lands. AI summaries that write into a note typically take over the section rather than adding reminders beside the user's text.

### User Research

- Owner decisions 2026-11-13 and 2026-11-14 (spec README, Decisions Log): Tomo may write into the user's sections, by headings only; descriptions and keywords per section like the trackers; Tomo condenses to a generous cap; forward-looking sections may be mapped with sourced suggestions; one checkbox per section drops it with its user items; Tomo's block between invisible markers, replaced on re-run through a new Hashi action; the "Tomo Review" section stays for unmapped groups.
- Owner notes on the v1.0 draft (2026-11-14): the core is gathering and processing the material each section needs — reminders of what happened and what will need to happen, which the user turns into their own thoughts; the spec 045 review is fine as material but needs a lot of back-and-forth between sections, which is the reason to place it in the right section; Tomo must produce material for every kind of review by reading what the target template requires; no spec 045 feature is removed; the owner also writes quarterly reviews.
- Test vault templates (structure only): the weekly private template carries "Review of the Week" with the day headings, "Learnings of the Week", "Reflections" and "In my own words" with "What Went Well", "Start Doing", "Stop Doing", "Continue Doing"; the monthly private template carries "Outlook" with "Goals and Wishes" (four sub-sections), "I look forward to", "This will be challenging", "ToDos for this month", and "Review of the month" with "In my own words" ("Things I did well this month", "Things which were hard this month"). The work variants use other heading texts and levels. Filled notes show the owner writes the Outlook sections, "In my own words" and the reflections by hand. The test vault has a `Calendar/304 Quarterly` folder; its template has not been read.
- Spec 045 live walk: 21 items in 5 groups for 2026-W13, 35 items for March 2026; the owner found that amount right.
- Hashi today places text before a heading, directly under it, or at the end of its section, and refuses a missing heading; it has no action that replaces only a marked part of a section, and its whole-section replacement would remove the user's text. The new action is requested by this spec (Constraints).

### Market Data

Not applicable: a personal-vault feature for the existing Tomo user base.
