---
title: "Every editable decision reaches the wire"
status: draft
version: "1.0"
---

# Product Requirements Document

> **Scope note.** This spec exists because spec 037 shipped an editable decision
> that reaches no wire, and because the same mistake had already been made once
> before on a different field without anyone noticing. It therefore fixes two
> concrete decisions *and* builds the artefact that makes the third instance
> visible at design time instead of on merge day.

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
| specId | 038-every-editable-decision-reaches-the-wire |
| title | Every editable decision reaches the wire |
| status | `IN_REVIEW` |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 38 |
| openQuestions | 0 — both were answered by the consumer 2026-09-29 |

### SectionStatus

| Section | Status | Detail |
|---------|--------|--------|
| Product Overview | `COMPLETE` | |
| User Personas | `COMPLETE` | Five, three of them machines |
| User Journey Maps | `COMPLETE` | One primary, three secondary (one error path, one build-time) |
| Feature Requirements | `COMPLETE` | F1–F4 Must, S1 Should, C1–C2 Could |
| Detailed Feature Specifications | `COMPLETE` | F2, the most complex |
| Success Metrics | `COMPLETE` | |
| Constraints and Assumptions | `COMPLETE` | |
| Risks and Mitigations | `COMPLETE` | |
| Open Questions | `COMPLETE` | Both answered; their answers are now requirements in F1 and F4 |

---

## Product Overview

### Vision

A decision the owner can make in the suggestions document survives to Pass 2 no
matter which surface they made it on, or which surface they touched afterwards.

### Problem Statement

**The measured defect.** Spec 037 added an editable decision — what to do when
an attachment's destination name is already taken — to the suggestions markdown
and to no wire. The suggestions wire's own top-level description states the
invariant this violates: *"every editable decision the markdown offers is
carried here."*

The consequence is silent data loss, reproduced against Tomo's own code in
`tests/test_037_remedy_lost_on_the_wire_path.py`:

1. The owner ticks **Rename** — the safe remedy, and the pre-ticked default.
2. Anything edits the wire. Saving in Hashi's editor is one way; the rule is an
   `emit_digest` mismatch, and Tomo's own ADR-026 then makes Pass 2 rebuild
   entirely from the wire and never re-read the markdown.
3. The wire has no field for the remedy, so the rebuild produces an empty list.
4. **An empty list is not "no decision".** Downstream, an absent source is
   byte-identical to an explicit **Ignore** — the move goes out against the
   occupied destination, the executor refuses it, and the owning note is filed
   and its source deleted regardless.

So the owner picks the safe option, takes an unrelated action, and silently gets
the unsafe one. Nothing reports a problem on either side of the boundary,
because the failed move is an expected class and Pass 2 sees a well-formed
document.

**The second, unprompted instance.** While auditing the consumer for this defect
we found `delete_source` — the third leg of the Approve / Skip / Delete
tri-state — has a wire field and still loses a markdown tick, because the
consumer's load path reads the JSON only and the body it regenerates on save
carries no per-item checkboxes. Same five-step chain, same silence, and it
predates spec 037 entirely. One instance is an incident; two in one week is a
property of the process.

**Why neither was caught.** The wire path *was* tested — for conflict-free runs,
against a byte-identical golden. A conflict run through that wire is not
expressible, because the field does not exist, so the one case that loses data
is the one case no fixture could build. There is also no artefact either side
can check a new decision against: every feature has reached the consumer through
a handoff somebody remembered to write.

**A third defect of the same shape, found in passing.** The markdown renders the
computed rename target inside a checkbox label, so it looks editable. It is not
— the name is read from a structured JSON snapshot and the rendered text is
never consulted for it. An owner who overtypes it gets the computed name, with
nothing anywhere reporting the substitution
(`tests/test_037_typed_rename_target_is_ignored.py`).

### Value Proposition

Three defects of one shape — a surface offering something it does not honour —
close together, and the artefact that would have exposed all three at design
time gets built. Without it the next editable decision has exactly the same
chance of reaching the consumer through no channel at all.

### The scoping principle (inherited, unchanged)

What happens between Pass 1, Pass 2 and application in the vault is explicitly
not modelled. The only guarantee is that no component overwrites data; a failed
check, a stale conflict and a late conflict all resolve the same way — the
executor reports, the owner fixes. The executor keeps its own final destination
check regardless of anything decided here: defence in depth, not a replacement.

This spec adds one deliberate corollary. Where validation is new — a name the
owner typed — Tomo **checks, surfaces, and records; nothing more.** No repair,
no substitution, no blocking.

---

## User Personas

Three of the five are machines. They are listed as personas because each has a
distinct success condition, and two of the three defects above were invisible
precisely because only the human ones were considered.

### Primary Persona: The vault owner, in Tomo's rendered markdown

- **Demographics:** Single owner of a personal Obsidian vault; comfortable in
  plain text and checkboxes; never reads JSON, never sees frontmatter.
- **Goals:** Settle a name collision in the same document where every other
  decision is made, with the sensible answer pre-set — and, when the computed
  name is wrong, supply a better one.
- **Pain Points:** Today the name looks editable and is not. The document takes
  their keystrokes and files something else without saying so.

### Secondary Persona: The vault owner, in the consumer's structured editor

- **Demographics:** Same person, different surface — a rendered card UI over the
  same run.
- **Goals:** See the collision at all, choose a remedy, and type a name, with
  immediate feedback while typing.
- **Pain Points:** The collision is invisible here — there is no field for it, so
  no control can exist. Worse, reviewing this run in the editor and saving is the
  very act that destroys a remedy chosen in the markdown.

### Secondary Persona: The consumer's editor, as a transport

- **Demographics:** Machine. Loads the wire, renders controls for what it knows,
  writes the whole document back.
- **Goals:** Round-trip fidelity — every field it does not render survives
  byte-for-byte.
- **Pain Points:** It can satisfy the human persona above completely and still
  fail this one, by preserving a JSON value while the markdown tick that should
  have changed it never arrives. That is exactly what happened to
  `delete_source`.

### Secondary Persona: Tomo's own rebuild path

- **Demographics:** Machine. `build_from_wire`, reached when `emit_digest` no
  longer matches.
- **Goals:** Produce output indistinguishable from the markdown path for the
  same underlying decisions.
- **Pain Points:** It is the mechanism that converts a missing field into the
  destructive outcome — not the consumer. Its correctness condition is
  *"rebuild-from-wire-alone agrees with the markdown path"*, and nothing asserts
  that for a conflict today.

### Secondary Persona: The consumer's build pipeline

- **Demographics:** Machine, build-time only. Joins a vendored inventory against
  its own coverage map.
- **Goals:** Fail the build when Tomo publishes an editable decision the editor
  does not cover.
- **Pain Points:** No such artefact exists, so there is nothing to join and
  nothing to fail on. Drift is discovered by a person reading source.

---

## User Journey Maps

### Primary User Journey: The owner names the file themselves

1. **Awareness:** Pass 1 reports a collision in the suggestions document and
   pre-ticks Rename with a computed name.
2. **Consideration:** The computed name (`karte (2).png`) is safe but
   meaningless; the owner wants `karte-dresden-1938.png`.
3. **Adoption:** They type it over the computed one, leaving the tick alone.
4. **Usage:** Pass 2 reads the typed name, checks it, and files the attachment
   under it, rewriting the embed in every note that referenced it.
5. **Retention:** The vault ends with the name the owner chose — the first time
   the document's apparent offer and its actual behaviour agree.

### Secondary User Journey: The owner reviews in the editor first

1. The owner opens the run in the structured editor, sees the collision as a
   card, picks a remedy and types a name there instead.
2. They save. The editor writes the whole document back, preserving the
   fields it does not render; the wire changes and `emit_digest` no longer
   matches.
3. Pass 2 rebuilds from the wire alone.
4. **The remedy and the name are both on the wire, so they survive.** Today step
   4 is where the choice becomes Ignore.

### Secondary User Journey (error path): The typed name cannot be used

1. The owner types a name that is unusable — it contains a path separator or a
   character the vault forbids, it is blank, or it is itself already taken.
2. Pass 2 checks it and refuses it. It does **not** repair it, and it does **not**
   fall back to the computed name.
3. The attachment is not filed. The instruction document records that the typed
   name could not be used, in the same register as every other Pass-2 problem.
4. The owner corrects the name and runs again, or picks a different remedy.

### Secondary User Journey (build-time): A new editable decision is added

1. **Awareness:** Someone adds a new editable decision to the suggestions
   markdown — a tick, a field, a choice.
2. **Consideration:** They add its row to the inventory at the same time, naming
   its wire field, or recording that it has none yet.
3. **Adoption:** The inventory ships; the consumer vendors it as they vendor the
   wire schema.
4. **Usage:** The consumer's build joins the inventory against its own coverage
   map. A row nothing in their editor covers **fails their build**.
5. **Retention:** Neither side audits the other. The gap that produced this spec
   becomes a build failure at design time instead of a defect report on merge
   day.

---

## Feature Requirements

> Every criterion below names **which wire** and **which path** it constrains.
> Spec 037's central claim was true of the instructions wire and needed to be
> true of the suggestions wire; naming it is the cheapest guard against
> repeating that.

### Must Have Features

#### F1: The chosen remedy survives the JSON-only path

- **User Story:** As the vault owner, I want the remedy I chose to be the remedy
  Pass 2 applies, regardless of what else touched the run, so that a safe choice
  cannot silently become the destructive one.
- **Acceptance Criteria:**
  - [ ] Given a run with an attachment conflict, When the suggestions wire is published, Then it carries the remedy for that conflict
  - [ ] Given the same run, When the wire is published, Then the remedy's default value is the one the markdown pre-ticks for that conflict
  - [ ] Given an attachment embedded by several notes, When the wire is published, Then the conflict appears once and one value settles it for all of them, consistent with 037's F2
  - [ ] Given an edited wire, When Pass 2 rebuilds from it alone, Then the remedies it produces are identical to those the markdown path produces for the same decisions
  - [ ] Given a run with no conflicts, When the wire is published, Then the output is unchanged from today apart from the version stamp
  - [ ] Given the suggestions wire schema changes, When the change is classified, Then the wire's version is moved and a handoff is owed, because the affected nodes are closed
  - [ ] Given a conflict on the wire, When it is published, Then it carries the occupied destination and whether the two files are byte-identical — the consumer cannot derive either
  - [ ] Given a conflict on the wire, When it is published, Then the notes that embed the attachment are **not** carried, because the consumer derives them from the run
  - [ ] Given the instructions wire, When this spec ships, Then it is untouched — no criterion here constrains it

#### F2: The rename target is owner-editable, on both surfaces

- **User Story:** As the vault owner, I want to name the file myself rather than
  accept a mechanical suffix, so that the vault ends up with a name that means
  something.
- **Acceptance Criteria:**
  - [ ] Given the owner types a name over the computed one in the markdown, When Pass 2 reads the document, Then the typed name is what Pass 2 proposes
  - [ ] Given the owner leaves the computed name untouched, When Pass 2 reads the document, Then behaviour is byte-identical to today
  - [ ] Given the owner types a name in the editor, When Pass 2 rebuilds from the wire, Then the typed name is what Pass 2 proposes
  - [ ] Given a typed name arrives by either surface, When it is validated, Then the same rules apply to both — not two implementations that can diverge
  - [ ] Given Pass 1 found no free name and rendered the "no free name available" line, When the owner supplies a name there, Then it is read and used like any other typed name
  - [ ] Given that line with no name supplied, When Pass 2 reads the document, Then the behaviour is unchanged from today — the remedy degrades as it does now
  - [ ] Given a typed name that is accepted, When the attachment is filed, Then the embed is rewritten in every owning note, as 037 already does for a computed name

#### F3: An unusable typed name is refused and recorded, never substituted

- **User Story:** As the vault owner, I want to be told when the name I typed
  could not be used, so that I am never quietly given a different one.
- **Acceptance Criteria:**
  - [ ] Given a typed name containing a path separator, When Pass 2 validates it, Then it is refused — not truncated to its last segment
  - [ ] Given a typed name containing a character the vault forbids, When Pass 2 validates it, Then it is refused — not rewritten with substitutes
  - [ ] Given a typed name that is empty or only whitespace, When Pass 2 validates it, Then it is refused
  - [ ] Given a typed name that is itself already taken at the destination, When Pass 2 validates it, Then it is refused — **run-local**: taken by another action in the same run. Measured 2026-10-01: Pass 2 has no vault listing (`path_exists` appears nowhere in `render_actions.py` or `render_md.py`, and the wire carries only `destination`, `same_file`, `proposed_name` per ADR-3), so the vault-side reading of this criterion is **not decidable in Pass 2** by any module. Pass 1 owns occupancy and hands forward one `proposed_name`. The run-local reading is satisfied by the existing claimed check at `render_actions.py:927`, which a typed destination already passes through by design (`:922-926`). The markdown already tells the owner as much on the `Ignore` line — "if the name is still taken when you apply, the move fails" — reworded after an owner catch on 2026-09-28 for claiming knowledge Pass 2 does not have.
  - [ ] Given any refused name, When Pass 2 emits its output, Then no move is emitted for that attachment and the attachment stays where it is
  - [ ] Given any refused name, When the instruction document is rendered, Then it records that the typed name could not be used, naming the attachment. **Scope, ruled by the owner 2026-10-02: "refused name" here means the three string classes T3.1 decides** — `separator_present`, `forbidden_character`, `blank` — **not the run-local collision of the fourth criterion.** A typed name that is usable as a string but collides is refused by the pre-existing claimed check (`render_actions.py:927`) and reported with the pre-existing shared sentence, *"destination collision: it also resolves to `<dest>`, already claimed by `<claimant>`"* (`render_actions.py:935`), which names no provenance because the skipped entry carries none. Two alternatives were measured and declined: forking that sentence when the name was typed, and plumbing `name_is_owner_supplied` onto the skipped entry so the renderer could add the framing. Both were rejected as buying little — the owner already knows they typed the name, since the document is rendered from the run in which they typed it — at the cost of forking a sentence the owner reviewed on 2026-09-28 or adding a second reader-less field one week after `kind`'s own reader-less field had to be argued for. The collision path's obligation is the fourth criterion's, and it is met.
  - [ ] Given any refused name, When the instruction document is rendered, Then the text states only what was verified — never a predicted future outcome and never an inferred intent
  - [ ] Given any refused name, When Pass 2 emits its output, Then the computed name is **not** used as a fallback
  - [ ] Given a name Tomo computed rather than the owner typing it, When Pass 2 processes it, Then behaviour is unchanged from today — this feature constrains typed names only

#### F4: The inventory of editable decisions exists, as a file the consumer can vendor

- **User Story:** As the consumer's build pipeline, I want a machine-readable
  list of every editable decision the markdown offers, so that a decision my
  editor does not cover fails my build instead of reaching a user.
- **Acceptance Criteria:**
  - [ ] Given the inventory, When it is read, Then it carries one row per editable decision the suggestions markdown offers
  - [ ] Given a decision with no wire field, When its row is written, Then the row records that absence explicitly rather than omitting the decision
  - [ ] Given any row, When it is written, Then it carries a stable opaque `id` that does not change when the markdown's wording changes
  - [ ] Given a control's label is reworded, When the inventory is regenerated, Then the row's `id` is unchanged, so the consumer's join sees an edit rather than a delete plus an add
  - [ ] Given a decision that is read-only, When the inventory is built, Then it does not appear
  - [ ] Given a control that has been retired, When the inventory is written, Then its row remains with `editable: false`, so the consumer is told to remove their control rather than left writing a field no longer honoured
  - [ ] Given the inventory, When a row is added or changed, Then the change is visible as a diff to a file, not as prose in a handoff
  - [ ] Given a malformed row, When Tomo's own tests run, Then they fail — the consumer never receives a malformed inventory
  - [ ] Given this spec ships, When the inventory is published, Then its rows agree with the suggestions wire as this spec leaves it, including the remedy's new field

### Should Have Features

#### S1: The owner is told which surface wins

- **User Story:** As the vault owner editing on two surfaces, I want to know the
  rule for which one counts, so that I am not surprised by a value I thought I
  had changed.
- **Acceptance Criteria:**
  - [ ] Given the user documentation, When it describes the two surfaces, Then it states plainly that once the run has been saved in the editor, the editor's values are the ones Pass 2 uses
  - [ ] Given the documentation on attachment name collisions, When it is read after this spec ships, Then it says the name is editable and describes what happens when a typed name is refused

### Could Have Features

#### C1: Pass 2's summary counts refused names

- **User Story:** As the vault owner skimming the run summary, I want refused
  names counted alongside the other skip reasons, so that I see at a glance that
  something needs me.
- **Acceptance Criteria:**
  - [ ] Given a run with at least one refused typed name, When the summary is rendered, Then the count appears alongside the existing skip counts

#### C2: An inventory row can carry a short note

- **User Story:** As the consumer reading a row whose wire field is absent, I
  want one line saying why, so that I can tell a deliberate gap from an
  oversight.
- **Acceptance Criteria:**
  - [ ] Given a row with no wire field, When it carries a note, Then the note is a single short string and is optional on every other row

### Won't Have (This Phase)

- **Detecting or reporting divergence between the markdown and the wire.** The
  rebuild path does not read the markdown by design; comparing them would
  contradict the precedence rule rather than document it. Owner decision: the
  rule is documented, not changed.
- **Repairing, sanitising or substituting an unusable typed name.** Explicitly
  ruled out — it is the defect this spec closes, wearing a different hat.
- **Blocking a run because a typed name is unusable.** Pass 2 surfaces and
  records; it does not refuse to produce a run.
- **Re-checking at apply time whether a name is still free.** The gap between
  Pass 1, Pass 2 and apply is not modelled; the executor's own final check
  covers it.
- **Adding controls to the consumer's editor.** Theirs to build; tracked in their
  issues, unblocked by this spec's wire field.
- **Closing the `delete_source` control gap.** Same boundary — the field already
  exists and the flag semantics have been measured and sent; the missing control
  is consumer-side.
- **Sanitising destinations that Tomo computed.** No behaviour change for names
  the owner did not type; the existing path stays as it is.

---

## Detailed Feature Specifications

### Feature: F2 — The rename target is owner-editable

**Description:** The suggestions document already renders the computed rename
target inside the remedy's checkbox label. The owner may replace that text with
a name of their own. The document keeps its checkbox idiom — the tick still
chooses the remedy — and the name beside it becomes a value the reader trusts
rather than decoration.

**User Flow:**

1. Owner reads the conflict entry and sees Rename pre-ticked with a computed
   name.
2. Owner replaces the name, leaving the tick alone.
3. Pass 2 reads the remedy from the tick and the name from the text.
4. Pass 2 validates the name (F3) and, if it is usable, files the attachment
   under it and rewrites the owning notes' embeds.

**Business Rules:**

- The name is read from wherever the owner can edit it. On an untouched document
  that value is the computed name, so an untouched document behaves exactly as
  it does today.
- A decision and its parameter travel together: the remedy and the name are one
  decision about one attachment, and one attachment has one decision no matter
  how many notes embed it.
- The same validation applies to both surfaces. Two implementations of one rule
  is the divergence this whole spec is about.
- Nothing silently replaces the owner's text. If it cannot be used, it is
  refused and said so.

**Edge Cases:**

- The owner ticks Rename but deletes the name entirely → refused as blank (F3);
  the attachment is not filed and the document says why.
- The owner half-edits the line so the name cannot be read at all → treated as a
  refused name, never as a different remedy and never as a parse failure.
- The owner types the name that is already occupying the destination → refused as
  taken (F3).
- The owner types a name in the editor and a different one in the markdown, then
  saves the editor → the editor's value is used, per the precedence rule (S1).
- Pass 1 found no free name, and the owner supplies one → accepted and validated
  like any other typed name.
- Pass 1 found no free name, and the owner supplies nothing → unchanged from
  today's degraded behaviour.

---

## Success Metrics

### Key Performance Indicators

This is an internal correctness spec; the metrics are measured conditions, not
adoption numbers.

- **Correctness:** A conflict decision produces the same Pass-2 outcome on the
  markdown path and the rebuild path — zero divergence, for every remedy.
- **Quality:** The three strict `xfail` markers standing in the suite today
  (`test_037_remedy_lost_on_the_wire_path.py`,
  `test_037_typed_rename_target_is_ignored.py`) flip to passing, and the tests
  that record today's wrong answers are deleted with them rather than left green.
- **Adoption (consumer):** The consumer's two open issues become unblocked —
  neither waits on Tomo after this ships.
- **Engagement:** Deliberately not measured. The checklist asks for a usage-
  frequency target; for a single-owner correctness fix there is no honest one —
  a conflict happens when it happens, and a spec that succeeded would not make
  the owner *use* anything more often. Stating this beats inventing a number.
- **Business impact:** Zero silent substitutions. Every case where Pass 2 does
  not do what the document appeared to offer is stated in the instruction
  document.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Conflict decided on either path | remedy, whether a name was typed | Prove the two paths agree — the F1 condition |
| Typed name refused | reason class (separator / forbidden character / blank / taken) | Prove each refusal class is reachable and reported, per Constitution L1's both-paths rule |
| Attachment filed under a typed name | — | Prove the happy path end to end, including the embed rewrite |
| Live run against the test vault | remedy exercised | The repeat of 037's live validation, now with a typed name |
| Inventory row count vs. editable decisions in the renderer | — | Catch an editable decision shipped without a row |

---

## Constraints and Assumptions

### Constraints

- **CON-1 — The release is coordinated and cannot be split.** The consumer's
  vendored schema rejects unknown properties and pins the current version, and
  treats a validation failure as fatal for the whole document. Shipping the field
  before they vendor the change would take their editor out of service on exactly
  the runs this spec serves — worse than today's silent loss.
- **CON-2 — The version move is load-bearing, not ceremonial.** Tomo's own
  consumer gate rejects a wire whose version does not match and falls back to the
  markdown without failing. A half-completed version move therefore produces no
  error, just a wire path that quietly stops being used.
- **CON-3 — Additive only.** The project is near MVP; no existing behaviour may
  break, including every conflict-free run's byte-identical output.
- **CON-4 — This is the first owner-typed string to become a vault write
  destination anywhere in the codebase.** The helper that builds these
  destinations deliberately does not sanitise, which was correct while the value
  could only be machine-computed.
- **CON-5 — Constitution L1 (Testing):** the path performs vault mutation, so it
  owes tests for the happy path and at least one failure/denial case; and
  validation behaviour owes tests proving both acceptance and refusal.
- **CON-6 — Constitution L2 (Architecture):** a change to a public interface
  between MiYo components requires a documented migration path and explicit
  review.
- **CON-7 — User-facing text states only what the renderer verified** (ADR-11:
  no executor internals in rendered text). Spec 037 shipped four sentences that
  asserted more than the code knew, and the owner caught two of them in shipped
  output.

### Assumptions

- The owner is the only editor of both surfaces, and the same person orchestrates
  both deployments — so a coordinated release is achievable rather than
  theoretical.
- The consumer preserves fields it does not render when it writes the document
  back. Stated by them and verified in their source; if it were false, the wire
  field alone would not be sufficient.
- The existing per-run vault listing is a good enough freeness check for a typed
  name. It inherits the same staleness window already accepted project-wide, and
  no new one.
- An attachment's conflict remains keyed by the attachment, not by the note — the
  invariant 037 established and this spec must not reopen.

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The field ships before the consumer vendors it, taking their editor out of service on conflict runs | High | Low | CON-1 makes it a single coordinated release; the handoff goes out complete, once, after the producer side is finished |
| The version is moved in one place and not another, so the wire path silently stops being used | High | Medium | CON-2 named as a constraint; the closing condition includes a run proving the rebuild path is still taken |
| Validation is implemented twice and the two surfaces diverge | High | Medium | F2 requires one rule for both surfaces; the split is that the consumer validates for feedback while Tomo validates for the record |
| A refused name is quietly replaced by the computed one under some path | High | Low | Explicit Won't-Have, an F3 criterion, and a test asserting the absence rather than the presence |
| A rendered sentence asserts more than the code verified, repeating 037 | Medium | Medium | CON-7; the wording is checked against what the renderer actually knows before it ships |
| The inventory is written once and then drifts | Medium | High | The consumer's build fails on an unmapped row; Tomo's own tests fail on a malformed one. Neither side reviews the other |
| A typed name escapes the attachments folder | High | Low | Refusal rather than truncation (F3); the existing helper already discards everything before the last separator, so refusal closes the reporting gap rather than a traversal hole |

---

## Open Questions

**Both have been answered** (consumer reply, 2026-09-29). Recorded here because
the answers are now requirements, not options.

- [x] **The conflict's context: send the destination and the byte-identity;
      let them derive the owning notes.** The destination is not derivable — the
      wire carries only the profile's *name*, and the editor has no other source
      for where attachments are filed. Byte-identity is firmer than a preference:
      their vault port has **no binary read at all**, and a UTF-8 round trip
      through it corrupts a binary, so computing it would mean adding a binary
      path to a shared abstraction and doing per-conflict I/O in the editor. We
      have already compared the files; a boolean is cheaper than them re-deriving
      it badly. The owning notes they can derive from the run.
- [x] **The inventory needs one column we had not planned: a stable row `id`.**
      Neither planned field can key a row — `markdown_control` is prose, and
      prose gets reworded (our own warning bullet was reworded four times in two
      days), which their join would read as one row deleted and one added,
      silently dropping that row's coverage claim. `wire_field` is `null` for
      exactly the rows that matter most, so it cannot be unique either.
      `editable` stays, with a purpose it did not have before: a retired control
      keeps its row at `editable: false`.

**One thing their answer surfaced that is ours, and is not fixed here.** Deriving
the owning notes from the run is correct because our own list is complete *for
the run* — but a note filed in an earlier run that embeds the same inbox
attachment is invisible to both sides, and a rename breaks its embed. Recorded in
`docs/XDD/backlog.md`; the owner-facing text this spec ships must not imply the
list is exhaustive.

Resolved before this document was written, recorded here so they are not
reopened: what happens to an unusable typed name (refused and recorded); whether
the "no free name" case is typeable (yes); whether divergence between surfaces is
detected (no — documented instead); and what the conflict row is keyed by (the
attachment, not the note).

---

## Supporting Research

### Competitive Analysis

Not applicable in the usual sense — there is no competitor for this boundary. The
closest external comparison is the general pattern the consumer proposed and the
owner accepted: the producer publishes an inventory of what it offers, the
consumer keeps a map of what it covers, and a build joins them. Neither side
reviews the other's changes; each fails on them. This is the same mechanism
already used for the vendored schema mirror, applied to a contract that was prose
until now.

### User Research

Five parallel research perspectives, 2026-09-29 — requirements, technical,
integration, user-surface and safety. Findings are recorded in the spec README;
the ones that changed this document's shape:

- The release cannot be split (CON-1), which was assumed to be a preference and
  turned out to be a hard constraint.
- The version move is a functioning gate, not paperwork (CON-2).
- This is the first owner-typed vault write destination in the codebase (CON-4),
  and the helper it flows through was built on the assumption it could never be
  owner-typed.
- The `item_key` join agreed with the consumer concerns note identity and does
  not apply to an attachment conflict, which is keyed by the attachment. The two
  agreements were never about the same thing.
- A free-text editable field is already precedented on this wire — but it reaches
  its destination through a helper that sanitises, while this one does not.
  Reading the precedent as "no new guard needed" would be the same
  presence-is-not-safety inference that produced this spec's parent defects.

### Market Data

Not applicable — single-user internal tooling.
