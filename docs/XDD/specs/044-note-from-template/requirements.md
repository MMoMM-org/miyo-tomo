---
title: "/note: notes from a template, with follow-up questions"
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

The user hands Tomo rough material for a kind of note, and Tomo turns it into a finished note in the shape of the user's own template, asking only for what is missing.

### Problem Statement

Some notes have a fixed shape: Meeting Notes, Problem Solving, Travel Reflections. The user keeps a template for each in the vault. Filling one today takes manual work, and Tomo does not help with it (#169):

- **`/inbox` does not ask.** Pass 1 and Pass 2 classify and file what is already written. They never check a note against a template or ask for a missing section, so a meeting note without its decisions stays without them.
- **`inbox-author` fills without asking.** Its unknown-type branch finds a vault template by name and fills it in one go (`tomo/dot_claude/skills/inbox-author/SKILL.md:44-48`). What the material did not cover stays empty, unmentioned, and the note stays in the inbox with no instruction set to file it.
- **Every new kind would cost us work.** Pass 2 renders only known tokens, so a new note kind through that path would need template changes in a Tomo-specific format. A user should be able to add a kind by adding a template, with no change from us.

### Value Proposition

- A note of a known kind is complete the first time: Tomo names each section it could not fill, asks for it, and says which ones stay empty.
- Any normal template works. Templater blocks are read as hints, never executed, and no Tomo token is required.
- The note reaches its destination the way every other Tomo note does: an instruction set the user applies in Hashi. Nothing outside the inbox is written before the user approves it there.
- Optional process files remember what the user wants per template (destination, required points, order), and Tomo creates them in a dialogue. The user never edits one by hand.

## User Personas

### Primary Persona: The capturer

- **Demographics:** The owner of a personal Obsidian vault who runs Tomo in its container. Comfortable in a console session. Does not read frontmatter or use a tag pane; filenames, checkboxes and Tomo's own reports are the signals.
- **Goals:** Turn rough material into a finished note of a known kind with as little typing as possible. The material is either text typed into the call or a note already in the inbox (a raw capture, a transcript, a Tsukai note).
- **Pain Points:** Sections get forgotten. Filling a template by hand is repetitive. A raw capture in the inbox and a finished note side by side is a duplicate to clean up.

### Secondary Personas

**The template keeper.** The same owner in another role: decides which vault templates count as note kinds, and what each kind should always ask for and where it should go. Wants this set once, through Tomo, without learning a file format. Pain point: naming schemes differ (`t_` templates, `i_` inserts, `a_` actions in this vault, something else in others), so any fixed rule would be wrong for someone.

**The applier.** The same owner later in Obsidian, reviewing and applying the instruction set in Hashi, or discarding the result. Needs the delivery report to say exactly what was written and what applying it will do, including whether the raw source will be deleted.

## User Journey Maps

### Primary User Journey: Material to filed note

1. **Awareness:** The user has notes from a meeting, typed or captured in the inbox, and wants a proper meeting note.
2. **Consideration:** The alternatives are filling the template by hand or letting `/inbox` file the raw capture as it is. Both lose the missing sections.
3. **Adoption:** `/note meeting with the design team` or `/note` on the inbox capture.
4. **Usage:** Tomo picks the template, shows which points the material covers, asks for the open ones in at most two rounds, prints the full draft with its target name and destination, and delivers after approval. The user applies the instruction set in Hashi.
5. **Retention:** The next meeting note goes faster: a process file, saved after the first run, sets the destination and makes the decisions section required.

### Secondary User Journeys

1. **First run (template keeper).** No template selection is configured yet. Tomo lists the template folder, proposes which filename patterns count as note templates, shows what matches and what does not, and saves the confirmed patterns. The note request then continues in the same session.
2. **No template fits (template keeper).** Tomo says no listed template fits, offers to adjust the patterns or to hand the request to `inbox-author`, and says that an empty folder may also mean the key cannot read it.
3. **Saving or declining a process (template keeper).** After a delivery that showed a preference, Tomo asks once: save, not now, or never for this template. "Never" is remembered. `/note --process <template>` creates or changes one on purpose.
4. **Interrupted delivery or dialogue (capturer).** A delivery fails midway, or the session ends while a draft is still in the dialogue or waiting for approval. The next `/note` offers to resume or drop a started delivery, and to continue or discard an unfinished draft, before anything else; a resume finishes without duplicating what already landed, and a continued printed draft returns to the approval question.
5. **Abort (capturer).** The user aborts during the dialogue. Nothing reaches the vault and the draft is removed.
6. **Discard after delivery (applier).** The user decides against the result, deletes the note and the instruction set in Obsidian, and runs `/inbox --recover` to get the source back as fresh.

## Feature Requirements

### Must Have Features

#### Feature 1: Template selection setup

- **User Story:** As the template keeper, I want Tomo to propose which templates count as note kinds the first time I use `/note`, so that I never configure it up front and my naming scheme is respected.
- **Acceptance Criteria:**
  - [ ] Given no template selection is configured, When the user runs `/note`, Then before choosing a template Tomo prints the proposed filename patterns, the templates they match and the templates they leave out, and only then asks to confirm or correct
  - [ ] Given the user corrects the patterns, When Tomo has applied the correction, Then it prints the new match list again before asking, and nothing is saved until the user confirms
  - [ ] Given the user confirms, When the patterns are saved, Then every other template setting is unchanged and the original request continues in the same session
  - [ ] Given the user aborts the setup, When the session ends, Then no setting is saved and nothing is written to the vault
  - [ ] Given a saved selection, When the user never runs `/note`, Then `/tomo-setup` and every other command behave exactly as before
  - [ ] Given the template mapped as the daily note, When any pattern matches it, Then it is still never offered as a note kind

#### Feature 2: Choosing the template

- **User Story:** As the capturer, I want Tomo to pick the matching template from my material, so that I do not have to name it.
- **Acceptance Criteria:**
  - [ ] Given exactly one selected template fits the request and material, When `/note` runs, Then Tomo names it and continues without asking
  - [ ] Given several templates fit, When `/note` runs, Then Tomo prints the candidates and asks the user to choose
  - [ ] Given the folder lists templates but none fits, When `/note` runs, Then Tomo says that no selected template fits and offers to adjust the patterns, to use `inbox-author`, or to abort
  - [ ] Given the template folder returns no files at all, When `/note` runs, Then Tomo says the folder is empty or not readable by the Kado key, tells the user to either grant the key read access to the template folder or not use `/note`, and never says that no template exists; the same remedy is given when a listed template cannot be read

#### Feature 3: Checklist and questions

- **User Story:** As the capturer, I want Tomo to ask only for what my material does not cover, so that the note is complete without retyping what I already gave.
- **Acceptance Criteria:**
  - [ ] Given a template, When Tomo prepares the questions, Then every heading, frontmatter field and fill-in token of the template is a point, and each point is either filled from the material or open
  - [ ] Given open points, When Tomo asks, Then it asks only open points, at most four per round and at most two rounds, before showing the draft
  - [ ] Given the material covers every point, When `/note` runs, Then Tomo asks no question and shows the draft
  - [ ] Given a point the user skips, When the draft is shown, Then the point stays empty in the note and is named in one line above the draft
  - [ ] Given a point marked required, When the user skips it or two rounds have passed, Then Tomo asks for it again with no skip option, and the user can only answer or abort
  - [ ] Given a required point, When the user gives any non-empty answer, including "none", Then the point counts as answered
  - [ ] Given Templater blocks in the template, When the note is drafted, Then they are read as hints only, never executed, and none remains in the delivered note
  - [ ] Given the user writes in one language, When Tomo asks, Then the questions use that language and the note keeps the template's headings

#### Feature 4: Draft and revision

- **User Story:** As the capturer, I want to see the whole note before anything is written, so that I can change it in the conversation.
- **Acceptance Criteria:**
  - [ ] Given the questions are done, When Tomo shows the draft, Then it prints the full note as text, preceded by the template, the target filename, the destination folder, the skipped points and, for an inbox-note source, that the source will be deleted when the instruction set is applied
  - [ ] Given the draft, When the user asks for a change, Then Tomo prints the full revised draft again before asking for approval
  - [ ] Given the draft, When the user changes the destination, the filename or keeps the source, Then the next draft shows the change and the delivery follows it
  - [ ] Given the draft, When the user approves, Then delivery starts; When the user aborts, Then Feature 6's abort criteria apply

#### Feature 5: Delivery

- **User Story:** As the applier, I want the note and an instruction set in the inbox, so that I file the note in Hashi like every other Tomo note.
- **Acceptance Criteria:**
  - [ ] Given an approved draft, When Tomo delivers, Then the note lands in the inbox marked as waiting to be moved, followed by an instruction set that moves it to the destination
  - [ ] Given an inbox-note source the user did not keep, When Tomo delivers, Then the instruction set also deletes the source, and the delete applies only after the move has applied
  - [ ] Given the delivered instruction set, When it is checked against Hashi's instruction schema, Then it is valid, and it is found by Hashi in the inbox like a Pass 2 set
  - [ ] Given delivery, When it runs, Then the order is note, instruction set, source mark, and a failed step stops every later step
  - [ ] Given both uploads succeeded and the source is an inbox note, When the source is marked, Then the next `/inbox` counts neither the source nor the note as new
  - [ ] Given the target name is taken in the inbox or at the destination, When Tomo delivers, Then nothing is overwritten and Tomo offers to rename or abort
  - [ ] Given delivery succeeded, When Tomo reports, Then it names the note's path, the instruction set's path, whether the source was marked, and that the next step is to review and apply the set in Hashi
  - [ ] Given any delivery, When scripts run, Then no note text, source text or answer appears in script logs or error output, and script output carries only paths, states and the few fields the user needs to see (the note's title, a saved process's settings, the template's point names)

#### Feature 6: Interruption and abort

- **User Story:** As the capturer, I want a failed or aborted run to leave nothing half done, so that I never clean up after Tomo.
- **Acceptance Criteria:**
  - [ ] Given a delivery failed, When it stops, Then the draft is kept, the source is not marked, and Tomo says which step failed
  - [ ] Given a kept draft, When the user next runs `/note`, Then before anything else Tomo shows each kept draft by title, template and time, and offers to resume or drop it
  - [ ] Given a resume, When a target already holds identical content, Then that step counts as done; When it holds different content, Then Feature 5's name-taken criteria apply
  - [ ] Given a drop, When it completes, Then the draft is removed and nothing is written to the vault
  - [ ] Given the user aborts during setup, questions or draft, When the session ends, Then nothing is written to the vault, the draft is removed and the source is untouched; a template selection the user had already confirmed stays saved
  - [ ] Given a successful delivery, When it completes, Then no draft remains
  - [ ] Given an unfinished draft that was never delivered, When the user next runs `/note`, Then before anything else Tomo shows it by title, template and time and offers to continue or discard it; continue returns to the approval question for a printed draft and to the questions otherwise

#### Feature 7: Process files

- **User Story:** As the template keeper, I want Tomo to remember per template where notes go and what must always be asked, without me writing a file.
- **Acceptance Criteria:**
  - [ ] Given a process file with a destination, When the draft is shown, Then it names that destination; Given none, Then it names the default atomic-note folder
  - [ ] Given a process file with required points, When Tomo asks, Then those points follow Feature 3's required rules
  - [ ] Given a process file with free guidance, When Tomo asks, Then the order and emphasis of the questions follow it
  - [ ] Given a process file that cannot be read, When `/note` runs, Then Tomo says so in one line and continues with the template alone
  - [ ] Given a required point the template no longer has, When `/note` runs, Then Tomo says so and continues without it
  - [ ] Given a delivered note whose template has no process file, and the session showed a changed destination, a point skipped in the question rounds that was filled through Change something before delivery, or a requested question order, When the delivery report is printed, Then Tomo asks once whether to save that: save, not now, or never for this template
  - [ ] Given the session showed none of these, or the template already has a process file, When delivery ends, Then Tomo does not ask
  - [ ] Given "save", When it completes, Then the process file exists and every required point in it exists in the template; Given "not now", Then nothing is written
  - [ ] Given "never", When the user later runs `/note` with that template, Then Tomo treats it as having no process and does not ask again
  - [ ] Given `/note --process <template>`, When it runs, Then Tomo shows the current values if a file exists, asks for destination, required points (offered from the template) and guidance, and saves the result, replacing a "never" answer
  - [ ] Given `/note --process` with an unknown template, When it runs, Then Tomo says so and writes nothing
  - [ ] Given backup, restore or an update of the instance, When they run, Then all process files survive unchanged

#### Feature 8: One path per request

- **User Story:** As the capturer, I want a request for a note of a template kind to have exactly one path, so that I do not get a half-filled note from the wrong command.
- **Acceptance Criteria:**
  - [ ] Given `/note` is installed, When `inbox-author` gets a request for a type that is not mapped, Then it points the user to `/note` instead of filling a vault template itself
  - [ ] Given a request for an overview, list, comparison, `.base` or `.canvas`, When `inbox-author` runs, Then it behaves as before, including its built-in default and the mapped `default` template

### Should Have Features

#### Feature 9: Documented discard

- **User Story:** As the applier, I want to know how to undo a delivered result, so that a wrong note costs me two deletions and one command.
- **Acceptance Criteria:**
  - [ ] Given the user documentation for `/note`, When a user reads it, Then it names the two files to delete in Obsidian and the `/inbox --recover` step
  - [ ] Given a source marked by `/note`, When the user runs `/inbox --recover`, Then the source is treated as fresh again

### Could Have Features

- An informational handoff to Hashi that a second producer emits the existing move-and-delete shape. No change on Hashi's side is needed.

### Won't Have (This Phase)

- Tags and MOC links in `/note` notes; `/inbox` handles classification.
- Overwriting an existing note.
- Executing Templater code.
- Process files in the vault (they would need instructions and Hashi).
- Branching logic in process files.
- Questions through the suggestions document.
- `/note --discard`.
- A setup step for `/note` in `/tomo-setup`.

## Detailed Feature Specifications

### Feature: Checklist and questions (Feature 3)

**Description:** Tomo reads the chosen template, lists its points and decides, for each, whether the material already fills it. It asks only for the open ones, within a fixed budget, and keeps required points apart from the budget.

**User Flow:**
1. User runs `/note` with material.
2. System lists the template's points and marks each as filled or open; it prints which points the material covers.
3. System asks up to four open points; the user answers or skips each.
4. System asks a second round if open points remain, again up to four.
5. System asks each still unanswered required point again, without a skip option.
6. System shows the draft with the skipped points named above it.

**Business Rules:**
- Rule 1: A point is a heading, a frontmatter field or a fill-in token of the template. Which token syntaxes count is set in the SDD.
- Rule 2: Filled or open is the model's judgement. Scripts list the points; they do not judge content.
- Rule 3: Two rounds is a hard cap for optional points. Required points are outside the cap.
- Rule 4: A skipped optional point keeps its heading with an empty body.
- Rule 5: Any non-empty answer satisfies a required point.
- Rule 6: Guidance in a process file changes order and emphasis, never the set of points.

**Edge Cases:**
- The template has more than eight optional open points → Expected: two rounds of four, the rest named as skipped.
- A required point is already covered by the material → Expected: not asked.
- The template starts with a Templater include instead of frontmatter → Expected: treated as a hint; the delivered note still has valid frontmatter.
- The user's answer opens a new gap → Expected: asked in the second round if budget remains, otherwise named as skipped.

## Success Metrics

### Key Performance Indicators

- **Adoption:** The owner uses `/note` for at least one note kind on the live vault in the first month after release.
- **Engagement:** Most runs with typical meeting material need one question round; no run exceeds two rounds of optional questions.
- **Quality:**
  - 100 % of delivered notes pass the filled-note check and 100 % of instruction sets pass Hashi's schema, in tests and in the eval case.
  - 0 duplicates: after a delivery, the next `/inbox` proposes nothing for the source or the note.
  - 0 overwrites across the name-taken and resume tests.
  - 0 delivered notes with an empty required point.
  - 0 vault writes and 0 kept drafts after an abort.
  - 0 process offers after "never".
- **Business Impact:** A new note kind costs a template, and no change to Tomo.

### Tracking Requirements

MiYo has no telemetry (constitution L1), so every metric is measured by a test, an eval case or the session transcript of a live run on `tomo-instance`.

| Event | Properties | Purpose |
|-------|------------|---------|
| Question round asked | round number, open points asked, required re-asks | Engagement: rounds per run; eval and transcript |
| Draft approved | skipped point count | Quality: completeness of notes |
| Delivery step done or failed | step name, exit status, paths | Quality: delivery order and failure handling; tests |
| Name taken | target path | Quality: no overwrite; tests |
| Process offer | answer (save, not now, never) | Offer discipline; tests and transcript |
| `/inbox` after delivery | new items counted for source and note | Quality: zero duplicates; live run |

---

## Constraints and Assumptions

### Constraints

- Tomo writes only to the inbox and to its own instance config. The note reaches its destination only through Hashi.
- All vault access goes through Kado. The key needs read access to the template folder; listing and reading need no write permission.
- An empty Kado result cannot tell absence from denial, so messages never claim that a template does not exist.
- Constitution L2: logs and script output carry metadata only, never note content.
- The user decides through `AskUserQuestion`, which allows at most four options per question and four questions per call.
- Runtime files hold imperatives only; rationale goes to `docs/tomo/`.
- No eval-gated file changes. If one has to change, the full eval suite must be GREEN before merge.

### Assumptions

- The owner's Kado key can read the template folder. This is unverified and is the first item of the plan.
- Hashi applies a move with a dependent delete of another inbox note, as it does for Pass 2 today (`tomo/scripts/lib/render_source_actions.py:53-99`).
- Users keep note templates in one folder, `templates.base_path`.
- One `/note` run produces one note.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The Kado key cannot read the template folder | High | Medium | Check first with the existing `inbox-author` branch on `tomo-instance`; document the required read access |
| The model asks too much or too long | Medium | Medium | Two-round cap; one paid eval case for question behaviour |
| The model writes a broken note | Medium | Low | Scripts check the filled note's structure before delivery |
| A source is deleted that the user wanted to keep | High | Low | The draft says the source will be deleted; the user can keep it; deletion only happens when the user applies the set in Hashi, through Obsidian's trash |
| Triage warns about a source marked by `/note` that has no downstream document | Low | Medium | Verify in the SDD; adjust or document |
| A setting write damages the rest of the template settings | High | Low | Byte-identity test on the other template settings |

## Open Questions

- [ ] Does the owner's Kado key read the template folder? Answered by the first plan task.
- [ ] Does triage warn about a source marked by `/note`? Answered in the SDD.

---

## Supporting Research

### Competitive Analysis

Obsidian's own templates and the Templater plugin insert a template and leave filling to the user; neither checks what is missing or asks for it. QuickAdd can prompt for variables, but only for prompts written into the template in its own syntax, which is the kind of tool-specific format this feature avoids. `/note` works from a plain template and decides what to ask from the material.

### User Research

The owner's brainstorm on 2026-11-02 and the decisions logged in this spec's README are the user research: a separate command, the template alone as the definition, a console draft, delivery through Hashi, include patterns proposed by Tomo, process files created only in dialogue, a remembered "never", at most two question rounds, rename or abort on a taken name, and deleting an inbox source by default. The three research reports are summarised with evidence in `research.md`.

### Market Data

Not applicable: Tomo is a personal tool with one owner.
