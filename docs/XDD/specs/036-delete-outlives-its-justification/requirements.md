---
title: "A delete must not outlive the action that justified it"
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

A destructive instruction is never emitted, never pre-approved, and never executed unless the
thing that justifies it is still standing.

### Problem Statement

Tomo emits `delete_source` instructions that remove a user's original inbox note. Three of the
four emission sites make that delete **conditional** on another action succeeding — the note is
only safe to remove because its content is going somewhere else. Nothing enforces the condition.

Three paths have been measured to termination, all reaching a real vault:

| # | Path | Needs Hashi to fail? | Measured |
|---|---|---|---|
| P1 | `create_moc` and `move_note` claim the same destination. Hashi writes the MOC, the move then fails on "both source and destination present", and the paired `delete_source` runs anyway. | Yes | 2026-09-09, real `build_actions` + both guards; `destination_clashes: 0` |
| P2 | `filter_missing_daily_notes` drops the daily partner because the target daily note does not exist, keeps every other action, and ships the delete whose stated reason is "Content fully captured in daily note." | **No — Tomo only** | 2026-09-09, real `build_actions` + real `filter_missing_daily_notes` |
| P3 | A tag-handler group with an unresolved `target_path` emits zero `insert_under_marker` and one `delete_source` per source note. | **No — Tomo only** | 2026-09-09, end-to-end through real reducer render + real parser + real `build_actions` |

Two of the three never involve Hashi at all. P2 and P3 are Tomo shipping an instruction set that
is internally contradictory at the moment it is written: Tomo has already established the
justification is false and emits the delete regardless.

P3 compounds the harm at the consent step. `annotate_tag_handler_group_guards` returns early on a
null target before it can set a guard, so the guards that would suppress the Approve box never get
set and the box renders **pre-checked**. The user is shown a group whose own target line reads
*"(unresolved — check handler config)"*, already approved, which will delete every source note and
insert nothing. One insert covers a whole group; one delete is emitted per source. A single
unresolved target loses every note in the group.

**Severity ceiling:** the executor deletes via `vault.trash`. Where the user has configured
permanent deletion, none of this is recoverable.

**Why the existing machinery does not cover it.** Tomo already holds this exact idea twice — the
OQ6 completion gate defers a delete until every expected atomic exists, and T5.3 withdraws a
paired delete when it drops a move. Both are correct. Both are reachable only from the `move_note`
claimant, and both are evaluated at **build** time over actions Tomo *intends* to emit, never at
**apply** time over actions that actually succeeded.

**What build-time checking structurally cannot reach.** A user who creates a note at the
destination path between instruction generation and application produces a clash that does not
exist when Tomo looks. No amount of Tomo-side guarding sees it. Only the executor can.

### Value Proposition

The user's inbox note is the only copy. Every other artifact in a Tomo run is derived and can be
regenerated; the source note cannot. This spec makes the irreversible operation the one that is
hardest to trigger by accident — refused at emission where Tomo can see the problem, refused at
approval where the user would otherwise consent blind, and refused at execution where only the
executor can see the problem.

## User Personas

### Primary Persona: Vault owner applying through Hashi

- **Demographics:** Single-vault Obsidian user, technical, runs `/inbox` on their own machine and
  applies the resulting instruction set with the Hashi plugin. The system's only current user.
- **Goals:** Empty the inbox without reading every instruction. Trust that approving a run cannot
  destroy something that was not filed.
- **Pain Points:** The instruction set is long and the checkboxes are uniform — a `delete_source`
  renders as an ordinary `- [ ] Applied` line, visually identical to a harmless action. Nothing in
  the document connects a delete to the action that justifies it, so a wrong one is invisible on
  review. When execution goes wrong the failure is silent: the run reports 10 of 11 applied and the
  eleventh is a note that no longer exists.

### Secondary Persona: Vault owner applying manually from the markdown

- **Demographics:** The same person on a different path — no Hashi in the loop, working the
  `_instructions.md` by hand.
- **Goals:** Understand and perform each action themselves; keep the option of not installing a
  plugin.
- **Pain Points:** Exposed to P2 and P3 exactly as the primary persona is, because both are
  produced entirely by Tomo before any executor is involved. Better placed on P1: a human doing the
  move notices that the destination is occupied and stops. This persona is why no requirement here
  may depend on execution results — a solution that assumes Hashi abandons this path silently.

## User Journey Maps

### Primary User Journey: Approve a run, apply it, keep everything

1. **Awareness:** The user runs `/inbox` and receives a suggestions document; they discover the
   need for this feature only by losing a note, which is the failure mode this spec removes.
2. **Consideration:** They review suggestions and tick approvals. Their alternative is reading every
   emitted instruction line by line before applying — which the uniform checkbox rendering makes
   impractical.
3. **Adoption:** They approve the run and apply it.
4. **Usage:** Every action either succeeds, or fails and takes its dependent deletes down with it.
   A delete whose justification is gone is never presented for approval, never emitted, or never
   executed.
5. **Retention:** The inbox empties and nothing disappears that was not filed. Trust survives the
   run.

### Secondary User Journey: Apply manually from the markdown

1. **Awareness:** Same trigger — a `/inbox` run.
2. **Consideration:** They prefer to perform the actions themselves rather than install or trust an
   executor.
3. **Adoption:** They open `_instructions.md` and work down it.
4. **Usage:** The document never asks them to delete a note whose partner action Tomo already knows
   cannot be performed. Where Tomo withheld an action, the delete that depended on it is absent
   rather than sitting one line below it.
5. **Retention:** The markdown path stays viable without a plugin.

### Error / Recovery Journey: The destination was taken after the set was generated

1. **Awareness:** The user generates an instruction set, then — before applying — creates or renames
   a note that occupies a destination the set claims.
2. **Consideration:** Nothing signals the collision; the set was valid when written.
3. **Adoption:** They apply the set as normal.
4. **Usage:** The move fails at execution. The delete that depended on it is skipped rather than
   applied, and the run reports it as skipped-because-dependency-failed rather than as done.
5. **Retention:** The original note survives. The user fixes the collision and re-runs.

## Feature Requirements

### Must Have Features

#### Feature 1: A contested destination withdraws both claimants and their deletes

- **User Story:** As a vault owner, I want two actions that claim the same destination to both be
  refused, so that neither can half-succeed and strand the delete that depended on it.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F1-AC1** — Given a run in which a `create_moc` and a `move_note` resolve to the same destination path, When the instruction set is built, Then neither action is emitted, And the `delete_source` paired with that move is not emitted, And the clash is reported with both claimants named
  - [ ] **F1-AC2** — Given a run in which the destination differs only by letter case between the two claimants, When the instruction set is built, Then the two are still treated as one contested destination
  - [ ] **F1-AC3** — Given a run in which a `create_moc` claims a destination no other action claims, When the instruction set is built, Then it is emitted unchanged and no delete is withdrawn
  - [ ] **F1-AC4** — Given a contested destination whose move carries an audio peer, When both claimants are dropped, Then the audio peer's `delete_source` is withdrawn as well as the origin's
  - [ ] **F1-AC5** — Given a contested destination, When both claimants are dropped, Then any staging note that only the dropped move would have filed is not uploaded to the vault

#### Feature 2: A withheld daily action withdraws the delete it justified

- **User Story:** As a vault owner, I want a delete justified by a daily-note write to disappear
  when Tomo withholds that write, so that content is never removed from the inbox before it has
  been recorded anywhere.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F2-AC1** — Given an accepted daily entry whose origin has no confirmed item, And the target daily note does not exist so the daily action is withheld, When the instruction set is built, Then the `delete_source` for that origin is not emitted
  - [ ] **F2-AC2** — Given an origin with accepted daily entries across several buckets or several days, When any one of those daily actions is withheld, Then the origin's `delete_source` is not emitted
  - [ ] **F2-AC3** — Given an origin whose daily actions are all emitted, When the instruction set is built, Then its `delete_source` is emitted unchanged
  - [ ] **F2-AC4** — Given a run in which a daily action is withheld, When the user reads the instruction document, Then the withheld action and the withdrawn delete are reported together rather than in unrelated sections

#### Feature 3: A tag-handler group with no resolvable target emits no delete

- **User Story:** As a vault owner, I want a consolidation that cannot be performed to delete
  nothing, so that an unresolved handler configuration costs me a no-op instead of every note in
  the group.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F3-AC1** — Given an approved tag-handler group whose `target_path` is absent, When the instruction set is built, Then no `delete_source` is emitted for any source in that group, And no `insert_under_marker` is emitted
  - [ ] **F3-AC2** — Given an approved tag-handler group with a resolvable target, When the instruction set is built, Then one `insert_under_marker` and one `delete_source` per source are emitted as today
  - [ ] **F3-AC3** — Given a group of three sources whose target is absent, When the instruction set is built, Then the count of emitted `delete_source` actions attributable to that group is zero, not one or two

#### Feature 4: An unresolvable group is never presented as pre-approved

- **User Story:** As a vault owner, I want a group whose target could not be resolved to arrive
  unticked and marked, so that my approval is never collected for something the system already
  knows it cannot do.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F4-AC1** — Given a tag-handler group whose target cannot be resolved, When the suggestions document is rendered, Then the group carries a guard marking the reason, And its Approve control is not pre-selected
  - [ ] **F4-AC2** — Given a tag-handler group whose target resolves and whose marker is present, When the suggestions document is rendered, Then its Approve control renders exactly as it does today
  - [ ] **F4-AC3** — Given a group with an unresolved target, When the user reads the group, Then the stated reason for it being unapprovable is visible in the group itself

#### Feature 5: Every delete names the actions that justify it, and the executor honours that

- **User Story:** As a vault owner, I want a delete to carry the identity of the actions it depends
  on, so that a failure the system could not predict still cannot cost me the original.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F5-AC1** — Given any emitted `delete_source`, When the instruction set is inspected, Then it carries a dependency field naming the ids of the actions that justify it
  - [ ] **F5-AC2** — Given a delete that no other action justifies — the user asked for the deletion itself — When the instruction set is inspected, Then its dependency field is present and explicitly empty rather than absent
  - [ ] **F5-AC3** — Given an origin consumed by three atomics, When the delete is emitted, Then its dependency field names all three move ids, not one
  - [ ] **F5-AC4** — Given an emitted instruction set, When every id in every dependency field is checked, Then each one is present in the same set's action list
  - [ ] **F5-AC5** — Given an applied run in which a named dependency failed, When execution reaches the dependent delete, Then the delete is not performed and is recorded as skipped due to that dependency
  - [ ] **F5-AC6** — Given an applied run in which a destination was occupied after generation but before application, When the move fails, Then the paired delete is skipped and the original note still exists afterwards

### Should Have Features

#### Feature 6: The instruction document explains a withheld delete where the user reads it

- **User Story:** As a vault owner reviewing a run, I want a withdrawn delete explained next to the
  action that caused the withdrawal, so that I can tell a deliberate omission from a bug.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F6-AC1** — Given a run in which any guard withdrew a delete, When the instruction document is rendered, Then the withdrawal and its cause appear together
  - [ ] **F6-AC2** — Given a run in which no delete was withdrawn, When the instruction document is rendered, Then no withdrawal reporting appears

### Could Have Features

#### Feature 7: A destructive action reads as destructive in the document

- **User Story:** As a vault owner skimming a long instruction set, I want deletions to be
  distinguishable from ordinary actions at a glance, so that review effort lands where the risk is.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F7-AC1** — Given an instruction document containing at least one `delete_source`, When it is rendered, Then those entries are visually distinguishable from non-destructive entries
  - [ ] **F7-AC2** — Given an instruction document containing no `delete_source`, When it is rendered, Then its appearance is unchanged from today

### Won't Have (This Phase)

- **Detection of staging notes stranded by a failed action.** Considered and rejected on
  architecture: the only reliable signal is the executor's applied flags, and consuming those makes
  Tomo depend on Hashi, abandoning the manual-markdown persona. Once Feature 5 lands the residue is
  clutter rather than loss — the original survives. Recorded so a future session does not
  re-propose reading execution results back.
- **The `## Section` landing above a note's H1.** A real Tomo defect, measured in the same live run:
  an anchor rewrite replaces type and value but inherits the placement chosen for the anchor it
  replaced. It is one field outliving its anchor inside a single action, not an action outliving
  another action — adjacent shape, different mechanism, no wire involvement. Its own spec.
- **`instructions` never reaching `tomo.state: applied`.** Tomo's lifecycle table assigns the
  transition to Hashi; Hashi treats the block as Tomo-owned and never writes it; Tomo's promoter has
  no branch for the doc type. A phantom contract with no functional effect. Backlog.
- **Changes inside the executor beyond consuming the dependency field.** The executor's skip
  mechanism already exists and is complete. Anything further is that repo's decision.
- **A general transaction or rollback model.** Out of scope by an order of magnitude, and
  unnecessary: refusing to emit and refusing to execute are sufficient for the measured paths.

## Detailed Feature Specifications

### Feature: Every delete names the actions that justify it, and the executor honours that

**Description:** Each emitted `delete_source` carries the identities of the actions whose success
makes the deletion correct. The executor already knows how to skip an action whose dependency
failed and how to report that outcome; it has never been given the dependency. This feature
supplies it, and makes the empty case explicit so that "nothing justifies this" is an assertion
rather than an omission.

**User Flow:**
1. User approves a run containing a note that will be filed as an atomic and its origin deleted.
2. System emits the move and the delete, the delete naming the move.
3. User applies the run.
4. System attempts the move; the destination is occupied by a note created since generation.
5. System records the move as failed, reaches the delete, sees its named dependency among the
   failures, skips it, and reports it as skipped-due-to-dependency.
6. User sees a run that did not fully succeed, and an inbox note that still exists.

**Business Rules:**
- Rule 1: Every `delete_source` carries the dependency field. There is no emission path that omits
  it.
- Rule 2: The field is a list. One delete may be justified by several actions — an origin consumed
  by N atomics, or a daily origin with entries across several buckets and days.
- Rule 3: The semantics are AND. If any named action fails, the delete does not happen.
- Rule 4: An empty list means "nothing conditions this delete; perform it" and is only correct
  where the user asked for the deletion itself.
- Rule 5: Every named id must exist in the same instruction set. A guard that drops a partner must
  drop or amend the deletes naming it — Features 1 through 3 are what make this rule holdable.
- Rule 6: The manual-markdown path must remain fully usable. Nothing here may require an executor.

**Edge Cases:**
- Scenario 1: A partner action is withheld by a Tomo guard after the delete was built → Expected:
  the delete is withdrawn, not left naming an id that is no longer present.
- Scenario 2: A delete names an id that is absent from the set → Expected: caught by our audit
  before the set ships. If one ships anyway, the executor skips the delete rather than performing
  it — confirmed by the consumer, who checks the dependency list against the action list at plan
  time. The failure list cannot catch this case, but plan-time validation can and does.
- Scenario 3: An origin consumed by three atomics where one move fails → Expected: the delete is
  skipped; the two successful moves stand.
- Scenario 4: A voice note whose transcript and audio are both deleted → Expected: both deletes
  carry the same dependency and both are skipped together.
- Scenario 5: A partner already applied in an earlier partial run → Expected: an already-applied
  partner counts as satisfied, not as failed.
- Scenario 6: The user deliberately asked to delete a note outright → Expected: empty dependency
  list, delete proceeds, unaffected by any other action's outcome.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Not applicable in the usual sense — this is a correctness change on a path every run
  already takes. The equivalent is coverage: 100% of `delete_source` emission sites carry a
  dependency field, and 100% of conditional sites have a withdrawal test.
- **Engagement:** Every applied run exercises the mechanism; no user action is required to opt in.
- **Quality:** Zero instruction sets emitted in which a `delete_source` names an id absent from the
  set, or in which a delete survives the withholding of its partner. Measured by the wire-hygiene
  and guard tests, and by the emitted-set audit below.
- **Business Impact:** Zero source notes deleted without their replacement being written. This is
  the metric the spec exists for; the acceptable value is zero, not a rate.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Destination clash withheld | claimant kinds, destination, withdrawn delete count, withdrawn link count | Confirms Feature 1 fires in real runs and shows how often the condition occurs |
| Daily action withheld | reason, withdrawn delete count | Confirms Feature 2; a nonzero count with zero withdrawn deletes is the P2 regression signature |
| Tag-handler group unresolvable | group id, guard reason, suppressed delete count | Confirms Features 3 and 4; the suppressed count is the blast radius that did not happen |
| Delete dependency emitted | delete count, deletes with empty dependency, deletes with non-empty dependency | Establishes that no emission path omits the field, and that empty is rare and deliberate |
| Dangling dependency detected | offending delete id, missing partner id | Must always be zero; any occurrence is Rule 5 broken and the executor cannot catch it |

All counters are metadata only — action kinds, counts, ids and paths. No note content, per the
project's audit-log rule.

---

## Constraints and Assumptions

### Constraints

- The manual-markdown application path must remain fully functional with no executor present. This
  rules out any design that reads execution results back.
- The instruction wire is a contract with a separate repository that vendors its own copy of the
  schema and rejects unknown fields outright. A new field is a coordinated release, not an additive
  change.
- The instruction wire and the suggestions wire carry independent version counters, so the two
  documents version separately even when they ship together.
- The executor deletes via the host's trash, which the user may have configured as permanent. The
  design cannot assume deletions are recoverable.
- Project governance requires every vault-mutating path to carry tests for both the permitted and
  the refused case, and requires implementation to trace to an approved spec.
- The consumer's derived dependency edges and our declared ones **union**; a declared edge never
  retires a derived one. Declaring an edge adds knowledge they cannot derive, and is never evidence
  that an edge they did derive is wrong.
- The system is near MVP; changes should be additive and must not break paths that currently work.

### Assumptions

- **A real triage run can produce the P2 input shape** — an accepted daily entry whose origin has no
  confirmed item and whose daily note is absent at build time. The emission was measured from a
  hand-built input; the upstream reachability was not established. If an upstream invariant forbids
  it, P2 narrows to a race between generation and application, which Feature 5 covers regardless.
- ~~The consuming repository will accept the dependency field as required.~~ **No longer an
  assumption — asked and answered on 2026-09-09.** Required with an explicit empty list, field name
  `depends_on` in snake case, and their edge sets union with ours rather than being overridden by
  them. They will additionally read the field on *any* action kind, not only `delete_source`.
- **The executor's dependency-skip mechanism behaves as its source indicates.** It was read, not
  executed, from this side.
- **Staging residue occurs.** Every link of the chain was measured separately; the combined outcome
  has never been observed, because the live run applied cleanly.
- **The three measurement runs are not reproducible from the repository.** Flagged 2026-09-10 by
  validation: every mechanism P1, P2 and P3 describe is live in `main` exactly as stated, and each
  was verified independently against source — but no artifact from those runs (the emitted action
  lists, the `destination_clashes: 0` figure) is committed anywhere. A reader cannot re-derive the
  numbers without re-running the probes. The claims are evidence-backed; their provenance is not
  archived. T4.4's end-to-end tests become that archive.
- The single user's vault is the target environment; no multi-user or concurrent-apply case exists.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A delete names a partner id that a later guard removed | Low | Medium | **Corrected 2026-09-09 by the consumer.** The original entry assumed the executor would perform such a delete; it will not. They check at plan time that every named id appears in the action list and **skip** the delete when one is missing — a malformed set fails closed. Our audit remains the thing that stops a dangling id shipping; theirs is what happens on the day one does. Features 1–3 remain prerequisites regardless. |
| The consuming repo declines the field as required, or wants a different shape | Medium | Medium | Ask before implementing rather than after. The question is a handoff, not an announcement. |
| The empty dependency list is treated as "unknown" rather than "unconditional" by a future consumer | High | Low | Make it required with an explicit empty value so absence is never valid, and state the semantics in the contract. |
| Fixing P3's consent step suppresses approval controls that legitimately should render | Medium | Low | Pair every suppression criterion with a criterion asserting the healthy case renders unchanged. |
| The two wire changes shipping together produce a release the consumer cannot vendor in one pass | Medium | Low | One changed-fields list covering both documents, and the schema files themselves shipped rather than described. |
| P2's upstream reachability turns out to be impossible, making Feature 2 unnecessary work | Low | Low | Feature 2 is a guard whose cost is small and whose presence is harmless if the input shape never occurs; the withdrawal it adds is the same one Feature 1 already needs. |

## Open Questions

- [x] ~~Does the consuming repo want the dependency field required or optional?~~ **Answered
      2026-09-09: required, with an explicit empty list.** Their reasoning sharpens ours — for a
      join key, absence degrades a feature; for a delete gate, absence is indistinguishable between
      "nothing justifies this" and "everything does", and those have opposite correct behaviours.
- [x] ~~Should an already-applied partner from a partial re-run count as satisfied?~~ **Answered
      2026-09-09: yes, and the mechanism is better than the filter we found.** Their dependency
      builder reads the *unfiltered* action list, so the edge to an applied action is built; it
      simply never resolves, because only ids that ran and failed enter the failure set. Intended
      behaviour for a partial re-run, and we may rely on it.
- [ ] Can a real triage run produce P2's input shape, or does an upstream invariant forbid it?
- [x] ~~Does the suggestions wire need a corresponding change so the user can see the dependency
      before approving?~~ **Answered 2026-09-10: no.** The SDD scopes the change to the instruction
      wire alone and lists `suggestions-wire.schema.json` under Must Not Touch. The dependency is a
      Pass-2 emission property; at Pass-1 approval time the actions it would name do not exist yet,
      so there is nothing for the user to see. Recorded here rather than left as an open question
      the design had already closed by fiat.

---

## Supporting Research

### Competitive Analysis

Not applicable — this is an internal correctness property of a single-user system with no
competing implementation. The closest external analogue is the standard practice of ordering
destructive operations after their prerequisites and gating them on success, which is the property
this spec adds.

### User Research

The system has one user, who supplied the decisive constraints directly:

- Tomo must not consume the executor's results, because a user not running the executor would be
  abandoned by any design that does. This eliminated the residue-detection feature.
- Tomo cannot guard everything from its own side; a note created between generation and application
  is invisible to build-time checking. This established that the wire dependency is not a
  generalisation of the guards but the only mechanism covering that class.
- Where the executor is involved, the executor must see the relationship.
- Consent and emission are one failure, not two: approval collected under a false premise belongs
  in the same spec as the emission it authorises.

### Market Data

Not applicable. The relevant measurements are the three reproduced failure paths recorded in the
Problem Statement, all from the 2026-09-09 vault run and its artifacts.
