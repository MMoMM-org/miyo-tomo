---
title: "Inbox attachment filing — embedded attachments follow their note out of the inbox"
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

An attachment embedded in an inbox note leaves the inbox **with** its note, filed to the vault's
asset folder — so that processing an inbox item finishes the job instead of half of it.

### Problem Statement

When an inbox note embeds an attachment (`![[karte.jpg]]`), `/inbox` files the note and abandons the
attachment.

The note is moved to `Atlas/202 Notes/`. The image stays in the inbox. **Nothing reports an error**,
because Obsidian resolves `![[karte.jpg]]` by name across the whole vault — the embed keeps
rendering, the note looks perfect, and the only symptom is that the inbox never reaches zero.

Three consequences, in increasing order of cost:

1. **The inbox never empties.** Tomo's core promise is that a processed item leaves the inbox. For
   any note with an attachment, that promise is silently broken. Residue accumulates run over run.
2. **Assets are never filed.** `concepts.asset` (`Atlas/290 Assets/295 Attachments/`) is declared in
   the vault config and, for this path, never used. The vault's asset folder does not reflect the
   vault's assets.
3. **The failure is invisible, so it compounds.** A loud failure gets fixed on the first run. This
   one is discoverable only by noticing that the inbox has a growing tail of images nobody moved.

**Evidence — this is observed, not hypothetical.** A cross-vault import of travel notes
(`tomo-instance/tomo-tmp/rendered-hashi/instructions.json`, 2026-09-01) required 8 attachment moves
alongside 13 note moves. The deterministic `/inbox` pipeline cannot produce a single one of them, so
the instruction set had to be composed by hand in a session. That workaround is what surfaced the
gap.

**Measurable statement:** for an inbox note embedding N attachments, `/inbox` currently emits 0
actions for those N files; the correct number is N (deduplicated).

### Value Proposition

Users choose Tomo because it proposes a *complete* filing decision they can approve in one pass. An
incomplete proposal is worse than no proposal: it looks finished, so the residue is never noticed
until it is large.

This feature closes the last gap between "the note is filed" and "the inbox item is done" — and it
does so with no new user-facing configuration, because the destination is already declared.

## User Personas

### Primary Persona: The vault owner processing an inbox

- **Demographics:** Single practitioner running Tomo against a personal Obsidian vault; high
  technical expertise; reviews and approves every proposal rather than delegating execution.
- **Goals:** Empty the inbox. Have every artifact — note and attachment alike — land where the vault
  structure says it belongs. Approve once, with confidence that approval covers the whole item.
- **Pain Points:** Must manually notice, hunt down, and drag attachments after `/inbox` has run.
  There is no signal telling them an attachment was left behind, so the work is remembered rather
  than prompted. Doing it by hand also risks breaking embeds if the file is moved without Obsidian's
  link updating.

### Secondary Personas

**The vault importer** — the same person performing a bulk one-off migration from another vault,
where notes arrive with attachment folders. Same needs, different volume: dozens of attachments in a
single run rather than one or two. This persona is what produced the evidence above; the feature must
not degrade at that volume.

## User Journey Maps

### Primary User Journey: Filing a note that carries an image

1. **Awareness:** The user drops (or imports) a note containing `![[karte.jpg]]` into the inbox,
   together with the image file. They expect both to be handled.
2. **Consideration:** They run `/inbox` and read the suggestions document. Today the document says
   nothing about the image, so they have no reason to think it will be left behind. The alternative
   is doing the whole filing by hand in Obsidian.
3. **Adoption:** The suggestions document names the attachments that will move and where to. The
   user sees the complete consequence of approving, before approving.
4. **Usage:** They approve the item as usual. The note and its attachments move together. The embed
   continues to render, now pointing at the filed location.
5. **Retention:** The inbox reaches zero. That is the signal that keeps them trusting the pipeline
   enough to approve without checking manually afterwards.

### Secondary User Journeys

**Bulk import.** The user imports a folder of notes plus a sibling `Images/` folder. They approve a
batch; every referenced attachment is filed once, including attachments referenced by more than one
note. The run does not become materially slower or more expensive than a note-only run.

**Attachment not found.** The user approves a note whose embed points at a file that is not in the
inbox (already filed, stored elsewhere, or a typo). The note files normally, no attachment action is
proposed, and the user is told which embeds were not resolved rather than silently ignored.

## Feature Requirements

### Must Have Features

#### Feature 1: Detect attachments embedded in inbox notes

- **User Story:** As a vault owner, I want Tomo to notice the attachments my inbox notes embed, so
  that filing decisions cover the whole item and not just the note.
- **Acceptance Criteria:**
  - [ ] Given an inbox note containing `![[karte.jpg]]`, When `/inbox` analyses it, Then `karte.jpg`
        is recorded as an attachment of that item.
  - [ ] Given an inbox note containing a note-to-note embed `![[Some Note]]`, When `/inbox` analyses
        it, Then it is **not** recorded as an attachment.
  - [ ] Given an inbox note containing a plain link `[[karte.jpg]]` rather than an embed, When
        `/inbox` analyses it, Then it is **not** recorded as an attachment.
  - [ ] Given an inbox note embedding the same attachment twice, When `/inbox` analyses it, Then the
        attachment is recorded once.
  - [ ] Given an inbox note with no embeds, When `/inbox` analyses it, Then the item carries an empty
        attachment list and behaves exactly as it does today.

#### Feature 2: Resolve each embed to a real file in the inbox

- **User Story:** As a vault owner, I want Tomo to find the actual file an embed refers to, so that
  the proposed move points at something real.
- **Acceptance Criteria:**
  - [ ] Given a note at `100 Inbox/Places/Dresden.md` embedding `![[karte.jpg]]` and a file at
        `100 Inbox/Images/karte.jpg`, When `/inbox` resolves the embed, Then it resolves to
        `100 Inbox/Images/karte.jpg` — a subfolder, not a sibling.
  - [ ] Given an embed written with an explicit path `![[Images/karte.jpg]]`, When `/inbox` resolves
        it, Then the given path is used without a lookup.
  - [ ] Given an embed whose target does not exist anywhere in the inbox, When `/inbox` resolves it,
        Then no attachment action is proposed for it and the unresolved embed is reported to the user.
  - [ ] Given an embed whose basename matches files in two different inbox subfolders, When `/inbox`
        resolves it, Then the ambiguity is reported rather than guessed, and no action is proposed.
  - [ ] Given a run over an inbox of any size, When `/inbox` resolves embeds, Then the number of
        additional vault queries does not grow with the number of notes or embeds.

#### Feature 3: Propose the attachment move for approval

- **User Story:** As a vault owner, I want the suggestions document to tell me which attachments will
  move and where, so that I see the full consequence before I approve.
- **Acceptance Criteria:**
  - [ ] Given an item with resolved attachments, When the suggestions document is rendered, Then it
        names each attachment and its destination folder.
  - [ ] Given an item with no attachments, When the suggestions document is rendered, Then no
        attachment section appears for that item.
  - [ ] Given the user edits the suggestions document, When it is parsed back, Then the attachment
        list survives the round trip unchanged.
  - [ ] Given the item is reviewed through the structured (editor) channel rather than the markdown,
        When it is parsed back, Then the attachment list is identical to the markdown channel's.

#### Feature 4: Emit the attachment move as an executable action

- **User Story:** As a vault owner, I want approving an item to move its attachments, so that the
  inbox item is genuinely finished.
- **Acceptance Criteria:**
  - [ ] Given an approved item with attachment `100 Inbox/Images/karte.jpg`, When instructions are
        rendered, Then one attachment-move action is emitted with that source and a destination under
        the configured asset folder, preserving the original filename and extension.
  - [ ] Given two approved notes embedding the same attachment, When instructions are rendered, Then
        exactly one attachment-move action is emitted for it.
  - [ ] Given an approved item with attachments, When instructions are rendered, Then **no deletion
        action** is emitted for any attachment.
  - [ ] Given an instruction set containing attachment moves, When it is validated, Then it conforms
        to the instruction schema and the schema version is unchanged.
  - [ ] Given an item is skipped or not approved, When instructions are rendered, Then no attachment
        action is emitted for it.

#### Feature 5: Account for attachment moves in the coverage audit

- **User Story:** As a vault owner, I want the pipeline's self-check to cover attachment moves, so
  that a missing or spurious move is caught rather than passing silently.
- **Acceptance Criteria:**
  - [ ] Given an approved item with N unique resolvable attachments, When the coverage audit runs,
        Then it expects exactly N attachment-move actions.
  - [ ] Given the renderer emits fewer attachment moves than expected, When the coverage audit runs,
        Then it reports a mismatch and fails.
  - [ ] Given an instruction set containing attachment moves, When the coverage audit reports totals,
        Then attachment moves are included in the total, not omitted from it.
  - [ ] Given a dry run of an instruction set containing attachment moves, When it is executed, Then
        it describes them rather than rejecting the set as containing an unknown action.

#### Feature 6: The human-readable instruction document describes attachment moves

- **User Story:** As a vault owner, I want the readable instructions to describe attachment moves in
  plain language, so that I can audit what will happen without reading JSON.
- **Acceptance Criteria:**
  - [ ] Given an instruction set containing an attachment move, When the readable document is
        rendered, Then it states the attachment's name, source and destination.
  - [ ] Given an instruction set containing an attachment move, When the readable document is
        rendered, Then it never prints an "unknown action" placeholder.

### Should Have Features

- **Unresolved-embed reporting.** When an embed cannot be resolved or is ambiguous, say so in the
  suggestions document next to the item, rather than only in stderr. Elevates a silent skip into a
  visible, actionable note. *(Should, not Must: the Must-level requirement is only that Tomo does not
  guess.)*
- **Destination collision handling.** Two different attachments sharing a basename (`karte.jpg` from
  two source folders) both target the same destination filename. Disambiguate rather than letting one
  overwrite or fail.

### Could Have Features

- **Attachment count in the run summary.** Report "N attachments filed" alongside the existing
  per-run counts, so the effect is visible without opening the vault.
- **Attachments on non-atomic item types.** This phase targets the item types that produce a note
  move. Extending to other item types is deferred until one needs it.
- **Reusing the vault's own link resolution.** Obsidian already knows what every embed resolves to.
  Consuming that directly would be correct by construction rather than by matching, at the cost of a
  new cross-repo capability and per-note queries. Worth revisiting if basename matching proves
  insufficient.

### Won't Have (This Phase)

- **Standalone attachments sitting in the inbox** (an image dropped in with no note referencing it).
  Deliberately excluded: such files carry no lifecycle frontmatter and cannot enter the two-pass
  state machine. This is a standing, documented decision (#93, 2026-07-18) and this spec does **not**
  reopen it. An embedded attachment is different in kind — it inherits its note's lifecycle and needs
  no state of its own.
- **Attachments referenced from outside the inbox.** If an inbox note embeds a file already filed
  elsewhere in the vault, nothing moves. It is already where it belongs.
- **Rewriting embed references.** Embeds are not rewritten to point at the new location; they
  continue to resolve by name, and the vault updates links itself when a file moves.
- **Deleting attachments.** Attachments are moved, never deleted. Contrast the existing audio-peer
  behaviour, which deletes — that is a different intent and must not be generalised to this one.
- **New user configuration.** The destination is the already-declared asset concept. No new setting,
  no wizard change.

## Detailed Feature Specifications

### Feature: Resolve each embed to a real file in the inbox

**Description:** An Obsidian embed names its target the way a human would — usually a bare filename,
occasionally a path. The vault resolves that by name across the whole vault, which is why a stranded
attachment stays invisible. Tomo must do the opposite of Obsidian here: it must find the *specific*
file in the inbox that the embed refers to, because only files in the inbox are candidates for
filing. An embed that resolves to something already filed is correctly left alone.

**User Flow:**

1. User runs `/inbox` on an inbox containing notes and an attachment subfolder.
2. System collects, per note, the list of embed targets that name a file rather than another note.
3. System builds a picture of the files actually present in the inbox, including subfolders.
4. System matches each embed target against that picture.
5. System records the resolved paths on the item, and reports any target it could not resolve or
   could not resolve uniquely.
6. User reads the suggestions document, which names the attachments and their destination.

**Business Rules:**

- Rule 1: An embed is an attachment only if its target names a file with an extension that is not a
  note. A target with no extension, or a note extension, is a note embed and is ignored.
- Rule 2: An embed target that already contains a path is taken as given; no matching is performed.
- Rule 3: Only files inside the inbox are candidates. A target matching a file outside the inbox
  resolves to nothing and produces no action.
- Rule 4: Resolution must be unique. A target matching more than one inbox file is reported, not
  guessed — a wrong move is worse than no move.
- Rule 5: The set of attachments is deduplicated by resolved path across the entire run, not per
  item. Two notes embedding one image produce one move.
- Rule 6: An attachment moves only if at least one item embedding it is approved. Attachments of
  skipped items do not move.
- Rule 7: Attachments are moved to the configured asset folder, keeping their original filename and
  extension.
- Rule 8: An attachment move never implies a deletion. The moved file is the same file.
- Rule 9: The cost of resolution must not scale with the number of notes or embeds. A per-embed or
  per-note lookup is not acceptable — this constraint has bitten the project before and is a stated
  reason for an existing accepted design decision.
- Rule 10: Failure to resolve is non-fatal. The note files normally; only the attachment action is
  withheld.

**Edge Cases:**

- Embed target lives in a subfolder, not beside the note → Expected: resolved correctly. This is the
  observed real case and the reason a sibling assumption is insufficient.
- Same attachment embedded by two notes, both approved → Expected: one move action.
- Same attachment embedded by two notes, only one approved → Expected: one move action, driven by the
  approved note. The unapproved note's embed continues to resolve by name.
- Two different attachments with the same basename in different inbox subfolders → Expected:
  ambiguity reported; no action proposed. (Disambiguating the *destination* for two genuinely
  different files is a separate Should-have.)
- Embed target absent from the inbox → Expected: no action, reported as unresolved, note files
  normally.
- Attachment already present at the destination → Expected: the move is a no-op rather than an error;
  the executor's existing idempotency behaviour covers this.
- Item has attachments but produces no note move (for example, an instruction-only item) →
  Expected: no attachment action; out of scope this phase.
- Attachment with an unusual or uppercase extension → Expected: treated as an attachment as long as
  it is not a note extension; the extension is preserved exactly on the destination.
- An embed inside a code fence → Expected: acceptable to treat as an embed this phase; a false
  positive costs one unnecessary move proposal that the user can decline, and no data is lost.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Not applicable in the usual sense — this is a correctness fix on an existing path,
  active for every run. The meaningful measure is coverage, below.
- **Coverage:** 100% of resolvable embedded attachments on approved items produce a move action.
  Baseline today: 0%.
- **Quality — residue:** the number of attachment files left in the inbox after a run whose notes
  were all approved reaches **zero**. This is the headline metric; it is directly observable.
- **Quality — no regressions:** runs on notes without attachments produce a byte-identical
  instruction set to today's.
- **Quality — correctness of skips:** zero move actions proposed for files that do not exist. An
  unresolved embed must produce no action rather than a fabricated one.
- **Cost:** additional vault queries per run is a small constant, independent of note and embed
  count. A measurable increase proportional to inbox size is a failure of this requirement.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Attachments detected | count per item, count per run | Confirms detection fires at all; distinguishes "no attachments" from "detection broken" |
| Embed unresolved | target name, source note | The visible signal for Rule 10; a rising count indicates a resolution strategy that is too narrow |
| Embed ambiguous | target name, candidate count | Validates Rule 4; if this is common, basename matching is the wrong strategy |
| Attachment moves emitted | count per run, count deduplicated | Reconciles against the coverage audit's expectation |
| Vault queries per run | existing per-run call count | Guards Rule 9. Note: the existing per-run counter is known to under-report; it must be corrected before it can be used as a baseline for this metric |
| Inbox residue after run | count of non-note files remaining | The headline metric — measured against the vault, not self-reported |

## Constraints and Assumptions

### Constraints

- **The executor's action contract is fixed and already shipped.** The attachment-move action accepts
  only an id, the action name, a source, a destination and an applied flag. Carrying any additional
  per-item context on it is rejected outright. Provenance must therefore live on Tomo's side, not on
  the wire.
- **The document format version must not change.** The executor pins it exactly; changing it would
  make every instruction set fail, not only those containing attachment moves.
- **Note moves and attachment moves are now a strict partition.** The executor hard-rejects a note
  move whose endpoints are not note files. Routing by file type is mandatory, not defensive.
- **Cost sensitivity.** `/inbox` has a tracked per-run cost budget and a documented history of
  rate-limiting under read-heavy designs. Any resolution strategy that queries per note or per embed
  is constrained by that history.
- **Two review channels must stay in sync.** The item is reviewed either as markdown or through the
  structured editor channel. A field added to one and not the other is silently invisible on the
  other path.
- **Approval semantics are unchanged.** This feature adds nothing the user must approve separately;
  attachments ride the existing per-item approval.

### Assumptions

- Attachments referenced by an inbox note are themselves in the inbox — in its root or a subfolder.
  Validated by the observed import. If an attachment lives outside, no action is correct anyway.
- The vault owner wants attachments in one configured folder rather than mirrored per-topic. The
  existing asset concept is a single flat destination and no request for per-topic asset folders
  exists.
- Embeds are the right signal. A file merely *linked* (not embedded) is a deliberate reference, not a
  dependency of the note, and should not be swept along.
- The asset destination is declared in every profile in use. It is present in the shipped profile; a
  profile omitting it must be handled rather than assumed.
- Basename matching within the inbox is sufficiently unambiguous in practice. If ambiguity turns out
  to be common, the Could-have alternative becomes the answer.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A new action kind is emitted but omitted from the coverage audit's reconciliation list, so the audit passes green while the actions go entirely unchecked | High | **High** — this is the default outcome of adding a kind without touching the audit | Treat audit registration as part of the definition of done, not a follow-up. An acceptance criterion covers it explicitly (Feature 5). The symptom is subtle: the header's action total exceeds the printed total |
| Existing path helpers assume note files and corrupt attachment paths (appending a note extension, or forcing a note extension on the destination) | High | High | Attachment paths must not travel through the note-oriented path helpers. Covered by a Feature 4 criterion requiring the original filename and extension to survive |
| A new per-item field is added to the markdown channel but not the structured channel (or is dropped by the parser's explicit projection step) | Medium | High | Both channels and the projection are named as acceptance criteria (Feature 3). The projection is a known silent-drop point in this pipeline |
| Resolution strategy quietly fabricates a path that does not exist | High | Medium | Rule 10 plus a Feature 2 criterion: an unresolved embed produces no action. Fabrication is worse than omission because the coverage audit would count it as covered |
| Per-embed or per-note lookups reintroduce rate limiting on large inboxes | Medium | Medium | Rule 9 makes constant query cost a requirement, and a metric tracks it. An equivalent decision was already taken and documented for the audio-peer path |
| Inserting a new action kind into the emission sequence shifts every subsequent action identifier, breaking fixtures | Low | High | Expected and benign, but it will surface as broad test churn; anticipate it rather than treating it as a regression |
| Feature creeps into filing standalone inbox attachments | Medium | Low | Explicitly in Won't Have, with the standing decision cited. Scope boundary is stated in three places |

## Open Questions

- [ ] **Which embed-resolution strategy is adopted?** Research compared three: matching against a
      picture of the inbox subtree (one additional query, independent of volume, correct for the
      observed case); querying the vault per embed (correct but scales with embed count, and carries
      a substring-matching hazard that can silently select a wrong file); and assuming the attachment
      sits beside the note (no queries, but wrong for the observed case and fails silently). Research
      recommends the first, and notes that the second was already evaluated and rejected for a
      comparable purpose. **This is the central design decision and belongs in the SDD as an ADR.**
- [ ] **Where is the attachment list produced — during analysis, or deterministically?** The list can
      be derived without judgement, which argues for a deterministic step; but the analysis step
      already reads each note's body, which argues for reusing that read. This has cost and
      testability consequences and should be decided explicitly.
- [ ] **Should the destination disambiguate colliding basenames now or later?** Listed as a
      Should-have. If deferred, the behaviour on collision must still be defined rather than left to
      chance.
- [ ] **Should the per-run query counter be corrected as part of this work?** It is known to
      under-report, and this spec's cost metric depends on it. Fixing it here keeps the metric
      honest; deferring it means the metric cannot be trusted at first.

---

## Supporting Research

### Competitive Analysis

Not applicable in the conventional sense — this is an internal pipeline correctness gap, not a
market-facing capability. The meaningful comparison is against the vault application's own
behaviour: Obsidian moves a file and updates every reference to it automatically. The relevant
lesson is that reference integrity is *not* this feature's problem — moving the file is sufficient,
and rewriting embeds would be redundant work with its own failure modes. That directly informed the
"Won't Have" decision on rewriting references.

The second comparison worth naming is Tomo's own existing handling of a non-note companion file: the
audio peer attached to a voice transcript. It travels the same pipeline and proves the shape works.
It differs in exactly two ways that must not be copied by accident — its location is known by
convention rather than discovered, and its end state is deletion rather than filing.

### User Research

Single-practitioner tool; research is direct observation rather than interviews.

- **Observed workaround (2026-09-01):** filing travel notes with map images from another vault could
  not be done through `/inbox`. The instruction set was composed by hand and contained 8 attachment
  moves against 13 note moves — attachments were 38% of the file operations in a realistic import.
- **Observed layout:** attachments were not beside their notes. Notes lived in one inbox subfolder,
  images in a sibling one, and embeds referenced them by bare filename. Any design assuming
  co-location would have failed on the first real case.
- **Observed destination:** the hand-composed set targeted exactly the folder already declared as the
  asset concept, confirming the configured destination matches actual intent with no new setting
  needed.
- **Inferred pain:** the gap went unnoticed until a bulk import made it large enough to see. For
  single-attachment notes the residue is one file per run, which is precisely the size that never
  gets reported and never gets fixed.

### Market Data

Not applicable. This is a single-vault internal tool with no market sizing. The volume figure that
matters for design is the observed import: order-of-ten attachments in one run, with repeat
references plausible — enough that deduplication is a real requirement rather than a theoretical one,
and few enough that no batching or streaming design is warranted.
