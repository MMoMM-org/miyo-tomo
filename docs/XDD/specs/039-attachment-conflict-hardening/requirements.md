---
title: "Attachment conflict hardening"
status: draft
version: "1.0"
---

# Product Requirements Document

> **Scope note.** Four inputs share one subject — what happens to an attachment
> between the owner's decision and the vault — and each one, alone, leaves the
> others' failure open. The consumer asked for an editable target folder; a
> folder makes "same name, different place" the normal case, which makes the
> bare embed ambiguous; an owner-typed target is never checked against the vault
> in Pass 2; and when an attachment move fails, its origin note is deleted
> anyway (#186). Two link-breaking input classes (#185) pass the typed-name
> guard on the same path. They ship together because fixing any one of them
> while the others stay open moves the data loss rather than removing it.

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
| specId | 039-attachment-conflict-hardening |
| title | Attachment conflict hardening |
| status | `IN_REVIEW` |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 53 |
| openQuestions | 0 — the owner question was ruled 2026-10-11; A1 and A3 measured by the consumer in Obsidian 2026-10-12 |

### SectionStatus

| Section | Status | Detail |
|---------|--------|--------|
| Product Overview | `COMPLETE` | |
| User Personas | `COMPLETE` | Four, two of them machines |
| User Journey Maps | `COMPLETE` | One primary, five secondary (three error paths) |
| Feature Requirements | `COMPLETE` | F1–F6 Must, S1 Should, C1 Could |
| Detailed Feature Specifications | `COMPLETE` | F3 + F4 together — the vault check and the embed decision share one picture of the vault |
| Success Metrics | `COMPLETE` | |
| Constraints and Assumptions | `COMPLETE` | Names the four prior criteria this spec supersedes |
| Risks and Mitigations | `COMPLETE` | |
| Open Questions | `COMPLETE` | One owner question ruled 2026-10-11; A1 measured by the consumer 2026-10-12 |

---

## Product Overview

### Vision

Whatever the owner decides about an attachment — keep its name, rename it, move
it somewhere else — the note that embeds it points at that file after apply, and
nothing in the inbox is deleted unless what it carried actually arrived.

### Problem Statement

**1. The owner cannot choose where a conflicting attachment goes.** When an
attachment's destination name is taken, the suggestions document offers Rename,
Keep in inbox or Ignore. Rename can only change the *name*: the folder is shown
inside the rename line but any folder the owner types there is refused
(owner ruling 2026-10-02). The consumer's editor cannot offer a folder either —
the wire has no field for one. Picking a free folder is often the natural fix,
and it is the one fix neither surface can express. The consumer's owner asked
for exactly this on 2026-10-11 while building the conflict control (Hashi #141).

**2. A name that is unique where it lands is not unique where Obsidian looks.**
Tomo writes every attachment embed as a bare basename — `![[karte.png]]` —
(owner ruling 2026-09-27). Obsidian resolves a bare basename across the whole
vault. Tomo only ever checks the destination folder: Pass 1's free-name search
reads that one folder's listing, and nothing reads any other. So today, any
attachment whose basename also exists elsewhere in the vault is filed with an
ambiguous embed — measured in code, not in a run: three paths reach it
(a conflict-free attachment, a computed rename, a qualified embed made bare by a
rename). Problem 1's fix turns this from an accident into the default outcome of
"move it without renaming it".

**3. Pass 2 never checks an attachment target against the vault.** Pass 2's
vault guard covers note moves and new MOCs and skips attachment moves entirely.
A name the owner typed onto a file that already exists reaches the executor
unchecked, which refuses it at apply time. A typed folder would have the same
exposure in every folder the owner can name.

**4. When an attachment move fails, its origin is deleted anyway (#186).** An
origin note's delete waits only for the note's own move. If the attachment's
move fails, the delete still runs: the filed note embeds a file that was never
created, the attachment sits in the inbox under its old name, and the inbox no
longer holds the item a re-run would need. Two independent runs on 2026-10-11 —
ours and the consumer's — emitted exactly this shape and survived only because
both destinations happened to be free. Kokoro's ADR-029 records it as an open
item Tomo owes a proposal on.

**5. Two link-breaking inputs pass the typed-name guard (#185).** A typed name
with leading or trailing whitespace is accepted and filed with its padding. A
typed name containing `#`, `^`, `[` or `]` is accepted, filed, and its embed
rewritten into a form Obsidian reads as a heading, a block reference or broken
brackets — and which Tomo's own embed reader then cannot see, so a later run
reports that note as attachment-free. The damage is a dead link the tooling has
been made blind to.

### Value Proposition

One release closes the attachment path end to end: the owner can say where a
file goes, Pass 2 checks every target it is about to hand over, the link it
writes resolves to that file, a typed name that would break the link is refused,
and an origin is only deleted once its attachments have arrived. The consumer
gets the field it asked for, and Kokoro gets the proposal ADR-029 is waiting on.

### The scoping principle (inherited, unchanged)

What happens between Pass 1, Pass 2 and application is not modelled; the
executor keeps its own final destination check. Where validation is new, Tomo
**checks, surfaces and records — it never repairs.** This spec extends that
principle to one new input (a folder) and one new kind of check (the vault, in
Pass 2), and does not relax it anywhere.

---

## User Personas

### Primary Persona: The vault owner, in Tomo's rendered markdown

- **Demographics:** Single owner of a personal Obsidian vault; works in plain
  text and checkboxes; never reads JSON, never sees frontmatter.
- **Goals:** Settle an attachment conflict in the same document as every other
  decision — including "put it in that folder instead" — and trust that the note
  will show the right file afterwards.
- **Pain Points:** The folder is visible but untouchable. A file filed under a
  name that exists elsewhere may silently display a different image. An inbox
  note can disappear while its attachment is still sitting in the inbox.

### Secondary Persona: The vault owner, in the consumer's structured editor

- **Demographics:** Same person, a card UI over the same run, with immediate
  feedback while typing.
- **Goals:** Pick a folder from the vault, not type one; see a usable name
  before saving.
- **Pain Points:** The editor cannot offer a folder because the wire cannot
  carry one. The editor sanitises a name visibly; the markdown refuses the same
  keystrokes — the owner has to know the two surfaces differ.

### Secondary Persona: The consumer's executor

- **Demographics:** Machine. Applies the instruction set in dependency order,
  skips any action whose dependency failed.
- **Goals:** Never delete something whose replacement did not arrive; never
  overwrite.
- **Pain Points:** It can only skip what it is told depends on something. Today
  it is never told that a delete depends on an attachment move, so its own
  correct cascade cannot protect the origin.

### Secondary Persona: Tomo's own rebuild path

- **Demographics:** Machine. Rebuilds Pass 2's input from an edited wire alone.
- **Goals:** Agree with the markdown path for the same decisions.
- **Pain Points:** A new editable field that only one path reads is the exact
  defect spec 038 closed; the folder must not reopen it.

---

## User Journey Maps

### Primary User Journey: The owner moves an attachment to a different folder

1. **Awareness:** Pass 1 reports that `karte.png` collides in the asset folder
   and pre-ticks Rename with a computed name.
2. **Consideration:** The owner does not want `karte (2).png`; the map belongs in
   a maps folder, where nothing is called `karte.png`.
3. **Adoption:** They leave Rename ticked, type the maps folder on the folder
   line, and type `karte.png` back as the name.
4. **Usage:** Pass 2 checks the folder, checks the target against the vault,
   files the attachment there, and — because `karte.png` now exists twice in the
   vault — writes the embed with its path in every note that embeds it.
5. **Retention:** The note shows the map they meant, in the folder they chose,
   under the name they kept.

### Secondary User Journey: The owner decides in the editor

1. The owner opens the run in the editor and picks the folder from the vault.
2. They save; Pass 2 rebuilds from the wire alone.
3. The folder survives the rebuild and produces the same outcome the markdown
   path would.

### Secondary User Journey (error path): The typed folder cannot be used

1. The owner types a folder that climbs out of the vault, is blank, contains a
   forbidden character, ends in a slash, or lies inside the inbox.
2. Pass 2 refuses it — it does not normalise it and does not fall back to the
   default folder.
3. Nothing of that item is filed; the instruction document names the attachment
   and the reason.
4. The owner corrects the folder and runs Pass 2 again.

### Secondary User Journey (error path): The target turns out to be taken

1. The owner's target — typed or computed, any folder — already holds a file
   when Pass 2 runs.
2. Pass 2 withholds the move and holds the notes that embed the attachment;
   nothing of that item is filed or deleted.
3. The instruction document says the target is occupied, by what, and that the
   item stayed in the inbox.

### Secondary User Journey (error path): The move fails at apply anyway

1. Something Pass 2 could not see — a file created after Pass 2, a check Kado
   could not answer, or an `Ignore` the owner chose on purpose — makes the
   attachment move fail at apply.
2. The executor skips the origin's delete because it depends on that move.
3. The inbox still holds the origin note and the attachment; a re-run can repair
   the item.

### Secondary User Journey: A name the owner typed would break the link

1. The owner types ` karte.png` with a stray space, or `karte#1938.png`.
2. Pass 2 refuses it, saying that the name would break the link — not that the
   vault forbids the filename.
3. The owner retypes it; the attachment is filed and its embed resolves.

---

## Feature Requirements

> Every criterion names the **channel** it constrains, in Kokoro ADR-029's terms:
> **C1** the instructions wire, **C3** the suggestions wire (consumer-editable),
> **C4** the suggestions markdown, **C10** the executor's apply-time behaviour.
> A criterion tagged **(C1)** changes what the consumer receives; one tagged
> **(internal)** changes only what Tomo decides.

### Must Have Features

#### Feature 1: The target folder is editable on both surfaces

- **User Story:** As the vault owner, I want to choose the folder a renamed
  attachment goes to, so that I can resolve a conflict by placing the file
  where it belongs instead of inventing a name.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F1-AC1 (C3)** — Given a run with an attachment conflict, When the suggestions wire is published, Then every conflict carries a target-folder field that is always present and empty by default, And the wire's version moves to 4
  - [ ] **F1-AC2 (C4)** — Given a conflict in the suggestions markdown, When it is rendered, Then it has its own folder line under the remedy choice, pre-filled with the destination's current folder, separate from the rename line
  - [ ] **F1-AC3 (C4)** — Given the owner changes the folder line and leaves Rename ticked, When Pass 2 reads the document, Then the attachment's target is that folder plus the rename line's name
  - [ ] **F1-AC4 (C3)** — Given the owner sets the folder in the editor, When Pass 2 rebuilds from the wire alone, Then the outcome is identical to the markdown path for the same decision
  - [ ] **F1-AC5 (C3, C4)** — Given an empty folder field, or a folder equal to the destination's own folder, When Pass 2 renders, Then the target is exactly what it is today
  - [ ] **F1-AC6 (C3, C4)** — Given a folder is set while the remedy is Keep in inbox or Ignore, When Pass 2 renders, Then the folder is ignored, And Ignore still sends the move to the original destination unchanged
  - [ ] **F1-AC7 (C3, C4)** — Given an untouched suggestions document, When Pass 2 reads it on either path, Then its output is byte-identical to today's apart from the wire's version stamp — provided every basename it files is unique in the vault, every target is free, and Kado answers; F3 and F4 deliberately change the output when any of those does not hold
  - [ ] **F1-AC8 (C4)** — Given a folder typed inside the rename line's backticks, When Pass 2 reads the document, Then it is still refused as a path separator — the 2026-10-02 ruling is unchanged by the new folder line
  - [ ] **F1-AC9 (C3)** — Given the inventory of editable decisions, When it is published, Then it carries one new row for the folder, And the count of editable wire fields moves from 25 to 26 with both directions of the join agreeing
  - [ ] **F1-AC10 (C3)** — Given the owner keeps the original basename and changes only the folder, When Pass 2 renders, Then the attachment is filed under its original name in the new folder — a changed folder alone is a valid rename
  - [ ] **F1-AC11 (C3, C4)** — Given Pass 1 found no free name and the owner sets a folder but leaves the name empty, When Pass 2 validates it, Then the name is refused as blank — the original basename is never filled in for the owner (owner ruling 2026-10-11)

#### Feature 2: An unusable folder is refused, never repaired

- **User Story:** As the vault owner, I want a folder I mistyped to be refused
  and named, so that I am never given a different folder than the one I chose.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F2-AC1 (internal)** — Given a typed folder that climbs out of the vault (`..`), starts at the filesystem root (`/`, `~`), starts with `./`, uses a backslash, or contains an empty or a `.` segment, When Pass 2 validates it, Then it is refused — not normalised
  - [ ] **F2-AC2 (internal)** — Given a typed folder that is blank, ends in a slash, has whitespace at either end of any segment, contains a character the vault forbids in a name, or contains `#`, `^`, `[` or `]`, which would break a path-qualified embed (owner ruling 2026-10-12), When Pass 2 validates it, Then it is refused
  - [ ] **F2-AC3 (internal)** — Given a typed folder that is the inbox or lies inside it, When Pass 2 validates it, Then it is refused, because a file filed there would be read as new inbox material by the next run
  - [ ] **F2-AC4 (C1)** — Given any refused folder, When Pass 2 emits its output, Then no move is emitted for that attachment, And the notes that embed it are held, as for a refused name
  - [ ] **F2-AC5 (internal)** — Given any refused folder, When the instruction document and the run's shell report are rendered, Then each names the attachment and states which rule the folder broke, using only what was verified
  - [ ] **F2-AC6 (internal)** — Given any refused folder, When Pass 2 emits its output, Then the default folder is **not** used as a fallback
  - [ ] **F2-AC7 (internal)** — Given a bad folder in one conflict, When Pass 2 runs, Then only that item is refused and the rest of the run is produced — a single bad folder never aborts the run
  - [ ] **F2-AC8 (internal)** — Given a usable typed folder that does not exist yet, When Pass 2 renders, Then the move is emitted, And the instruction document states that the folder will be created on apply
  - [ ] **F2-AC9 (internal)** — Given a typed folder containing `{{`, `<%` or a control character, When Pass 2 validates it, Then it is refused with the same reason F5-AC7 uses, And the rest of the run is produced (owner ruling 2026-10-12)

#### Feature 3: Pass 2 checks every attachment target against the vault

- **User Story:** As the vault owner, I want Pass 2 to refuse a target that is
  already taken, so that a conflict is caught while I can still change my
  decision rather than when the executor refuses it.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F3-AC1 (C1)** — Given a Rename target — computed or typed, in any folder — that already holds a file in the vault, ignoring case, When Pass 2 renders, Then no move is emitted, And the notes that embed the attachment are held
  - [ ] **F3-AC2 (C1)** — Given an attachment with no conflict whose ordinary destination has become occupied since Pass 1, When Pass 2 renders, Then it is treated exactly as F3-AC1
  - [ ] **F3-AC3 (C1)** — Given a free target, When Pass 2 renders, Then the move is emitted exactly as today
  - [ ] **F3-AC4 (C1)** — Given the owner chose Ignore, When Pass 2 renders, Then the move is still sent unchanged to the occupied destination — Ignore is the owner's explicit instruction and is exempt from this check
  - [ ] **F3-AC5 (internal)** — Given a withheld target, When the instruction document is rendered, Then it names the attachment, the occupied target and what occupies it, in wording written for an attachment rather than for a note
  - [ ] **F3-AC6 (internal)** — Given Kado cannot answer for a target's folder, When Pass 2 renders, Then the move is still emitted, And the instruction document reports that target as not checked — an unanswered check is never reported as a free target
  - [ ] **F3-AC7 (internal)** — Given a run, When the check runs, Then the vault is listed at most once per distinct target folder and searched by name at most once per distinct filed basename, a name search that would exceed a fixed page budget is treated as unanswered, And a run that files no attachment makes no additional vault calls

#### Feature 4: The embed carries a path only when the basename would be ambiguous

- **User Story:** As the vault owner, I want the note to show the file that was
  filed for it, so that a same-named file elsewhere in the vault can never be
  displayed in its place.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F4-AC1 (C1)** — Given an attachment the run files whose basename will be unique in the vault after the run, When its owning notes are rendered, Then every embed of it is the bare basename, exactly as today
  - [ ] **F4-AC2 (C1)** — Given an attachment the run files whose basename will also exist elsewhere after the run — an existing file, the file occupying its original destination, or another attachment this run files — When its owning notes are rendered, Then every embed of it carries the full vault path
  - [ ] **F4-AC3 (C1)** — Given an attachment the run files under its original name and in its default folder, When its basename is ambiguous, Then its embed is qualified too — the rule applies to every attachment the run files, not only to renamed ones
  - [ ] **F4-AC4 (internal)** — Given the attachment's own inbox copy, and any other inbox file this run moves away, When uniqueness is decided, Then neither is counted — uniqueness is judged on the vault as it will be after the run
  - [ ] **F4-AC5 (C1)** — Given a qualified embed, When it is written, Then it keeps the file's extension and any display size, alias or anchor the owner wrote
  - [ ] **F4-AC6 (C1)** — Given Kado cannot answer whether a basename is unique, When the owning notes are rendered, Then the embed is qualified — the form that resolves whatever else is in the vault
  - [ ] **F4-AC7 (internal)** — Given a note this run filed with a qualified embed, When a later run reads that note, Then Tomo still recognises the embed as an attachment
  - [ ] **F4-AC8 (internal)** — Given an attachment whose move is withheld for any reason, When its owning notes are rendered, Then no embed is rewritten for it

#### Feature 5: A typed name that would break the link is refused (#185)

- **User Story:** As the vault owner, I want a name I typed that would break its
  own embed to be refused, so that I never get a link that neither Obsidian nor
  Tomo can follow.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F5-AC1 (internal)** — Given a typed name with leading or trailing whitespace, When Pass 2 validates it, Then it is refused — not trimmed
  - [ ] **F5-AC2 (internal)** — Given a typed name containing `#`, `^`, `[` or `]`, When Pass 2 validates it, Then it is refused
  - [ ] **F5-AC3 (internal)** — Given either refusal, When the instruction document is rendered, Then both share one reason, And its sentence says the name would break the link — never that the vault forbids the filename, which is false for these characters
  - [ ] **F5-AC4 (internal)** — Given a note *title* containing `#` (e.g. `C# Notizen`), When Tomo derives its filename, Then the result is unchanged from today — the new rule constrains typed attachment names only
  - [ ] **F5-AC5 (internal)** — Given a refusal reason the renderer does not recognise, When the instruction document is rendered, Then it is never reported as a blank name
  - [ ] **F5-AC6 (internal)** — Given a conflict whose source basename Tomo can discover as an attachment and which contains no character the vault forbids, When Pass 1 computes a name for it and the typed-name rules check that name, Then it is accepted — Tomo never proposes such a name and then refuses it if typed back. (Sources carrying `#`, `^`, `[` or `]` are never discovered as attachments; sources carrying a forbidden character are pinned as a known divergence by spec 038.)
  - [ ] **F5-AC7 (internal)** — Given a typed name containing `{{`, `<%` or a control character, When Pass 2 validates it, Then it is refused with one shared reason, And the rest of the run is produced — today such a name aborts the whole of Pass 2 (owner ruling 2026-10-12)

#### Feature 6: An origin is deleted only after its attachments have arrived (#186)

- **User Story:** As the vault owner, I want an inbox note kept until everything
  it carried has been filed, so that a failed attachment move leaves me
  something to repair instead of a dangling link.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F6-AC1 (C1)** — Given an origin whose filed notes embed attachments that the run moves, When the instruction set is produced, Then the origin's delete — and its audio peer's — waits for every such attachment move as well as for every note move
  - [ ] **F6-AC2 (C1, C10)** — Given an attachment move fails at apply, When the executor reaches the origin's delete, Then it skips the delete as a failed dependency, And the origin and the attachment both stay in the inbox
  - [ ] **F6-AC3 (C1)** — Given an attachment embedded by notes from two origins, When the instruction set is produced, Then both origins' deletes wait for its single move
  - [ ] **F6-AC4 (C1)** — Given an attachment move withheld at build time, When the instruction set is produced, Then no surviving delete names it as a dependency
  - [ ] **F6-AC5 (C1)** — Given an attachment kept in the inbox by the owner's choice, When the instruction set is produced, Then the origin's delete is unchanged from today — no move exists to wait for, and the embed still resolves to the file in the inbox
  - [ ] **F6-AC6 (C1)** — Given the instructions contract's description of what a delete may depend on, When this spec ships, Then it names attachment moves, in Tomo's copy and in the vendored consumer copy
  - [ ] **F6-AC7 (C10)** — Given the consumer's executor as it is today, When it applies an instruction set produced by this spec, Then it needs no change — asserted against its dependency cascade, not assumed
  - [ ] **F6-AC8 (internal)** — Given the owner chose Ignore, When the instruction document is rendered, Then its disclosure states that the origin is kept if the move fails, replacing the sentence that says the note is filed either way

### Should Have Features

#### S1: The owner is told how the two surfaces differ, and what Pass 2 now checks

- **User Story:** As the vault owner using both the editor and the markdown, I
  want to know where the two behave differently, so that a refusal in one place
  does not surprise me after a clean save in the other.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **S1-AC1** — Given the user documentation on attachment conflicts, When it is read after this spec ships, Then it describes the folder line, the refusal rules for folders and names, and that the editor sanitises a name the markdown refuses
  - [ ] **S1-AC2** — Given the troubleshooting documentation, When it is read after this spec ships, Then it no longer says the destination is checked only in Pass 1, And it explains a target reported as occupied or as not checked

### Could Have Features

#### C1: The run reports how many vault lookups the new checks cost

- **User Story:** As the maintainer watching Kado's rate limit, I want the run
  to report the lookups F3 and F4 made, so that a regression in their cost is
  visible without a live trace.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **C1-AC1** — Given a Pass 2 run, When it finishes, Then the number of vault lookups made for attachment targets and basename uniqueness is recorded alongside the run's existing call counts

### Won't Have (This Phase)

- **Sanitising, trimming or otherwise repairing anything the owner typed** in
  Tomo. The editor's sanitiser is the consumer's surface; Tomo's guard refuses.
- **Creating folders.** Tomo reports that a folder will be created; the
  executor creates it, as its contract already says.
- **Re-checking at apply time.** Unchanged: the executor's own check covers the
  gap between Pass 2 and apply.
- **Repairing notes filed in earlier runs** whose embeds a rename or move now
  breaks. Unchanged and not claimed (`backlog.md` "A renamed attachment breaks
  the embed in any note that was filed earlier").
- **An empty typed name escaping the refusal contract** — backlogged
  (`backlog.md:1839`).
- **The fan wire dropping attachment conflicts** when wires are combined —
  pre-existing, backlogged.
- **Schema-validating an edited wire as a whole** in Pass 2 — per-field checks
  only; backlogged.
- **Force Atomic bypassing conflict detection** — Pass 1 is unchanged; F3 now
  catches the occupied target in Pass 2, which is the measurable improvement.
- **Carrying the refusal verdict on the wire** so it is decided once
  (`backlog.md:1917`) — not pulled into v4.

---

## Detailed Feature Specifications

### Feature: F3 + F4 — one picture of the vault, two decisions

**Description:** Both features ask the same question of the vault at the same
moment — "what will be at this name once the run is applied?" — and answer two
different things with it: whether a target may be used (F3) and whether a link
to it needs a path (F4). They are specified together so that the two answers
can never disagree about the vault they are based on.

**User Flow:**

1. Owner settles every conflict, possibly typing names and folders.
2. Pass 2 resolves each attachment's final target: folder (typed, or the
   default) plus name (typed, computed, or original).
3. Pass 2 refuses unusable folders and names (F2, F5) before anything asks the
   vault.
4. Pass 2 asks the vault what occupies each remaining target and how many files
   share each final basename.
5. Occupied targets are withheld with their notes held (F3); every other target
   is moved.
6. Every embed of a moved attachment is written bare or qualified according to
   the after-the-run count (F4).

**Business Rules:**

- **Rule 1:** A target is judged against the vault and against this run's other
  targets together; neither alone decides.
- **Rule 2:** Names are compared ignoring case, for occupancy and for
  uniqueness — a false "taken" is recoverable, a silent overwrite is not.
- **Rule 3:** Uniqueness is decided for the vault after the run: files this run
  moves out of the inbox do not count, files this run moves in do.
- **Rule 4:** Ignore is exempt from the **vault** half of Rule 1 — a target this
  run already gave to another attachment still withholds it. It is never exempt
  from Rule 3. Under Ignore the target is occupied by design, so a qualified
  embed names the occupier's path: when the files are identical that is the
  right file, and when the move fails the origin is kept (F6).
- **Rule 5:** An unanswered question is never read as a favourable answer: a
  target Kado could not check is reported as unchecked, and a basename whose
  uniqueness could not be established is written with its path.
- **Rule 6:** The embed decision and the move decision are made once, from the
  same data, for every note that embeds the attachment.
- **Rule 7:** A withheld move rewrites no embed (F4-AC8).

**Edge Cases:**

- The owner moves `karte.png` to a free folder without renaming → filed;
  embed qualified, because the occupier still holds `karte.png`.
- Two conflicts resolve to the same folder and name → the second is withheld as
  a run collision and its notes are held; its embed is not rewritten.
- Two different files are filed into different folders under one basename → both
  are filed; both embeds are qualified.
- The occupier differs from the target only in case → occupied.
- The target folder does not exist → nothing occupies it; filed, reported as
  "will be created"; embed decided by the vault-wide count as usual.
- Kado answers for one folder and fails for another → each target is judged by
  its own answer; only the unanswered ones are reported as unchecked.
- Kado's key cannot see part of the vault → a same-named file there is not
  counted; recorded as an assumption, not handled.

---

## Success Metrics

### Key Performance Indicators

- **Adoption:** Every PRD criterion is traced to a test executed in one run of
  the suite before close-out (the 036–038 close-out rule).
- **Engagement:** n/a — the owner's behaviour does not change; their options do.
- **Quality:** Zero instruction sets in which an origin's delete can apply after
  one of its attachment moves failed — asserted for every delete Tomo emits, not
  sampled. Zero embeds written bare for a basename the run knew to be
  non-unique.
- **Business Impact (cost):** Additional vault calls per Pass 2 bounded by the
  number of distinct target folders plus the number of distinct filed basenames;
  zero for a run that files no attachment.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Attachment target withheld in Pass 2 | attachment, target, occupier, reason kind | F3 — visible in the instruction document and the shell report |
| Target not checked | attachment, target | F3-AC6 — distinguishes "free" from "unanswered" |
| Typed folder or name refused | attachment, refusal reason | F2, F5 |
| Embed qualified | attachment, final path, reason (ambiguous / unanswered) | F4 — makes the new embed form auditable |
| Vault lookups for attachments | count per run | C1 and the cost KPI |

---

## Constraints and Assumptions

### Constraints

- **CON-1 — Coordinated release.** The suggestions wire moves to version 4; the
  consumer's validator rejects the new field until it vendors the schema. Tomo
  and the consumer release together. The vendored copy of the consumer's
  suggestions schema is refreshed to version 3 first, because spec 038 left it at
  version 2 — so this spec's schema diff measures only 3 → 4.
- **CON-2 — Design-time handoff to Kokoro.** F6 changes what a delete depends
  on in the instructions wire (C1). Per ADR-029's cadence it goes to Kokoro as a
  proposal, naming C1, C3, C4 and C10, the suggestions wire's v3 → v4 migration
  path, and the two near-miss runs. **Gate (owner ruling 2026-10-12):** sent in
  Phase 1; no C1 work starts before it is sent; nothing merges to `main` before
  Kokoro has answered. If Kokoro rejects option 1, the C1 change is reverted on
  the branch before merge.
- **CON-3 — Handoff to the consumer.** Answers its three asks (accept the folder
  field and name the release vehicle; the ambiguous-embed finding; the remedy
  rule for names) and delivers the #185 ruling, which was promised before it
  ships #141.
- **CON-4 — Runtime file discipline.** Explanatory content goes to
  `docs/tomo/<mirrored-path>.md`, not into runtime agent or skill files.
- **CON-5 — Prior criteria this spec supersedes, named so no reader treats the
  change as a regression:**
  - **038 F3-AC4** — "taken" was run-local only, because Pass 2 had no vault
    listing. F3 extends it to the vault.
  - **038 F1-AC9** — "the instructions wire is untouched". F6 changes C1's
    `depends_on` values and its description.
  - **037 F1-AC3** — "the vault is consulted once per run for the asset
    folder". F3/F4 add bounded calls; the new bound is F3-AC7 and the cost KPI.
  - **037 F1-AC5** — "when the vault cannot be consulted, the check degrades
    without blocking". Still never blocks, but no longer silent: F3-AC6 reports
    the target as unchecked and F4-AC6 qualifies the embed.
- **CON-6 — Unchanged rulings this spec builds on:** bare embed by default
  (2026-09-27); Keep in inbox files the note and holds only the attachment
  (2026-09-27); only Tomo's own printed folder is stripped from the rename line
  (2026-10-02); typed input is refused, never sanitised (038 ADR-5); a refused
  attachment holds its owning notes (038 ADR-6).

### Assumptions

- **A1 — Obsidian resolves a bare basename across the whole vault**, so two
  files with one basename make a bare embed ambiguous. **Measured by the
  consumer in Obsidian on 2026-10-12** (`getFirstLinkpathDest`, two
  `karte.png`): a copy in the embedding note's own folder wins; otherwise one
  copy wins from everywhere — not the nearest (a note in `Atlas/202 Notes/` got
  `100 Inbox/Scans/karte.png` over `Atlas/290 Assets/295 Attachments/karte.png`).
  The tie-break between two candidates (shorter path or alphabetical) is not
  pinned down. A bare ambiguous embed is therefore actively wrong, not merely
  ambiguous; F4's qualified embed is required for correctness.
- **A2 — Kado's name search covers every file type and the whole vault within
  the key's scope.** Read from Kado's source (v1.3.0), not measured live. A key
  restricted to part of the vault under-counts (Risk R3).
- **A3 — The consumer's executor creates a missing parent folder** for an
  attachment move, as its documented contract states. **Measured by the
  consumer 2026-10-12:** one `app.vault.createFolder` call creates several
  missing levels (`a/b/c` from nothing), so any depth holds.
- **A4 — The consumer's executor skips any action whose dependency failed,
  whatever the kinds involved.** Confirmed live for note moves on 2026-09-21 and
  read in its planner for all kinds; F6-AC7 asserts it.

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| R1 — The new vault lookups push a run into Kado's rate limit | Medium | Low | Bounded per distinct folder and basename (F3-AC7); retries already back off; C1 makes the cost visible |
| R2 — Holding notes on an occupied target (F3) surprises an owner who previously got the note filed and the move refused at apply | Medium | Medium | Same treatment as a refused name, already shipped in 038; the instruction document names the target and its occupier |
| R3 — A restricted Kado key hides a same-named file, so an embed is written bare though ambiguous | Medium | Low | Recorded as assumption A2; no worse than today; a qualified embed is always written when Kado does not answer |
| R4 — The consumer cannot ship version 4 in step | High | Low | CON-1; their editor ships #141 without the folder picker meanwhile, as they proposed |
| R5 — Moving the embed decision changes the bytes of notes that previously rendered identically | Medium | Medium | F4-AC1 pins today's output for every unique basename; F1-AC7 pins an untouched document |
| R6 — The new refusal reason is misreported by a renderer that only knows the old three | High | High without F5-AC5 | F5-AC5 is a prerequisite, not a follow-up |

## Open Questions

- [x] **Owner (ruled 2026-10-11):** On the "no free name available" line, a
  folder supplied with an empty name is **refused as blank** — the attachment is
  not filed under its original basename. 038's contract that nothing is ever
  substituted for the owner wins over the consumer's "a folder alone resolves
  it"; a folder change with the original name typed back in remains valid
  (F1-AC10). Now criterion F1-AC11.
- [x] **Answered 2026-10-12:** whether Obsidian resolves an ambiguous bare
  basename to a file the owner did not intend. The ask had been withdrawn from
  the reply on the belief that the consumer cannot measure in Obsidian; the
  consumer measured it anyway in its dev console — yes, it can (A1). F4's rule
  is required, not just safe.

---

## Supporting Research

### Competitive Analysis

Not applicable — the comparison that matters is Obsidian's own link format
setting "Shortest path when possible", which writes a path exactly when a
basename is not unique. F4 adopts the same rule for the links Tomo writes.

### User Research

- The consumer's owner reviewed the conflict-control mockup and asked for a
  folder (handoff 2026-10-11).
- Two independent live runs on 2026-10-11 emitted the #186 shape; both were
  safe only because their destinations were free.
- Four research passes on 2026-10-11 are kept in full in `research.md`; their
  open questions were settled by the owner and are in the README's decisions
  log.

### Market Data

Not applicable.
