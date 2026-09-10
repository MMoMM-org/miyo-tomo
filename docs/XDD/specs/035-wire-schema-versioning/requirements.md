---
title: "A wire shape cannot change without the consumer being told"
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

A wire document cannot change shape without the change being detected, versioned, and handed to the
consumer before it ships.

### Problem Statement

Tomo publishes **three** wire documents that another repository vendors and validates against:
the suggestions wire, the instructions wire, and the garden-audit wire. Each carries its own
`schema_version`. Nothing detects a shape change in any of them.

**This has already happened twice, and the second instance is live today.**

| # | Incident | Detected by | Status |
|---|---|---|---|
| 1 | `attachments` (spec 031) and `item_key` (spec 034) added to the suggestions wire; `schema_version` stayed `"1"` | Nobody, for two specs — found only when every run failed the consumer's validator | Fixed 2026-09-09 |
| 2 | `up_source` and `up_value` added to the garden-audit wire's `findings[].detail` (specs 032/033) | Nobody. Found 2026-09-10 while researching this spec | **Live and unvendored on both sides** |

The second is benign **only by accident**. `findings[].detail` is the one node in that document
declared open; root and `findings[]` are both closed. Had those fields landed one level up, the
garden-audit editor would have stopped opening — the same failure as incident 1, in a different
document, while the spec about incident 1 was being written.

**The check that exists cannot catch this class of change.** One test fetches the consumer's live
schema and compares it to ours. It builds its comparison surface from named definition blocks
carrying an action, then compares those. The suggestions wire has **no such blocks** — every object
is inline — so applied there the comparison performs **zero iterations and passes vacuously**. Even
on the document it was written for, it compares nothing at the root. Pointing it at the drifted
document would have changed nothing.

**The emitted version is asserted against nothing.** Each of the three producers writes its
`schema_version` as a free-standing literal. No check ties that literal to the version its own
schema declares, so the two can diverge in either direction without a failure.

**And two documents claim the same identity.** The Hashi-facing instruction contract and Tomo's
producer copy declare an identical canonical `$id`, title and description while differing
structurally. The consumer has already diffed the wrong one of the pair and reported drift that did
not exist — a cost paid once, with nothing preventing a repeat.

### Value Proposition

The consumer rejects unknown fields outright. That makes every additive-looking change to a closed
node a breaking change for them, and makes silence the most expensive possible failure mode: the
producer believes it shipped a feature, the consumer's users find a tool that no longer opens, and
the diagnosis costs a round trip that begins with "nothing changed on our side."

This spec makes the shape of every published wire a checked property rather than a convention, so
that the question "did this change break the consumer?" is answered before the change ships rather
than after a user reports it.

## User Personas

### Primary Persona: The Tomo maintainer shipping a spec that touches a wire

- **Demographics:** The system's owner, working through a spec's implementation phase, editing a
  schema as one task among many.
- **Goals:** Land the feature. Know immediately — not two specs later — whether the edit obliges
  anyone else to act.
- **Pain Points:** The obligation is invisible at the moment of the edit. Adding a field to a schema
  looks identical whether it lands on an open node or a closed one, and only one of those breaks the
  consumer. Nothing in the test suite, the review, or the spec gates distinguishes them, so the
  correct behaviour depends entirely on remembering an unwritten rule at the right moment.

### Secondary Persona: The consumer maintaining a vendored copy

- **Demographics:** The Hashi repository, which vendors all three wire documents and compiles them
  with a strict validator.
- **Goals:** Learn that a wire is changing before the change reaches a user's vault; know precisely
  which of their own files must move.
- **Pain Points:** A shape change reaches them as a broken run rather than as a message. Their own
  structural diff can only compare what they already have against what they are given, and it
  deliberately ignores prose — so the descriptions carrying a field's meaning are invisible to it.
  They have also diffed the wrong one of two identically-identified files and reported drift that
  did not exist.

### Tertiary Persona: The vault owner

- **Demographics:** The end user, who never sees a schema.
- **Goals:** Open a Tomo run in the editor and have it work.
- **Pain Points:** Experiences the entire failure as a tool that silently stopped opening their
  documents, with an error naming a property they have never heard of. In incident 1 the fallback
  path masked it, which is why nobody reported it for two specs.

## User Journey Maps

### Primary User Journey: Change a wire and know what it costs

1. **Awareness:** The maintainer edits a schema as part of an unrelated feature.
2. **Consideration:** They have no way to tell whether the edit is consumer-affecting; today the
   distinction lives only in whether a node happens to be closed.
3. **Adoption:** They run the test suite, as they would for any change.
4. **Usage:** The suite tells them the shape changed, whether it obliges the consumer, and that the
   version must move. The change cannot land quietly.
5. **Retention:** The next wire edit produces the same signal without anyone remembering a rule.

### Secondary User Journey: Receive a wire change as a message, not a breakage

1. **Awareness:** The consumer receives a handoff carrying the schema file and a list of what moved.
2. **Consideration:** They diff the file themselves, and read the list for what the diff cannot see —
   what each field means, which of their own files must change, and whether it breaks them now or
   only on some future run.
3. **Adoption:** They vendor the change and reply.
4. **Usage:** Only then does Tomo begin emitting the new version. A user's run never encounters a
   consumer that has not vendored it.
5. **Retention:** The exchange is the same shape every time, so neither side invents a process.

### Error / Recovery Journey: A drift is discovered that predates the mechanism

1. **Awareness:** The comparison against the consumer's copy lands and immediately reports a
   difference nobody announced — as it does today for the garden-audit wire. Note this is the
   consumer-copy comparison, **not** the shape manifest: the manifest records our own schema, which
   already declares the fields, so it correctly reports nothing.
2. **Consideration:** The maintainer establishes whether it is consumer-affecting. For the live case
   it is not, because the node is open.
3. **Adoption:** The change is announced to the consumer as though it were new, and the version is
   moved.
4. **Usage:** The report returns to clean, so the next real drift is visible against a quiet
   baseline.
5. **Retention:** A detector whose report always contains known noise is a detector nobody reads.
   Reaching zero is what makes it usable.

## Feature Requirements

### Must Have Features

#### Feature 1: A shape change to a published wire fails the build

- **User Story:** As the Tomo maintainer, I want a shape change to any published wire to fail my test
  run, so that the obligation is visible at the moment of the edit rather than two specs later.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F1-AC1** — Given a published wire document, When a property is added to any object in it at any nesting depth, Then the test suite fails naming the document, the location, and the property
  - [ ] **F1-AC2** — Given a published wire document, When a property is removed, or a `required` list changes, or an `additionalProperties` value changes, Then the test suite fails naming what changed
  - [ ] **F1-AC3** — Given a wire document containing no reusable definition blocks, When its shape changes, Then the check still fails — it must not pass vacuously on a document whose objects are all inline
  - [ ] **F1-AC4** — Given a change that alters only a description or title, When the suite runs, Then it passes, because prose carries no obligation for the consumer's validator
  - [ ] **F1-AC5** — Given all three published wires unchanged, When the suite runs, Then the check passes and reports nothing

#### Feature 2: The bump rule distinguishes consumer-affecting changes from the rest

- **User Story:** As the Tomo maintainer, I want to be told whether a shape change actually obliges
  the consumer, so that the version moves when it must and stays put when it need not.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F2-AC1** — Given a property added to a node that rejects unknown properties, When the change is classified, Then it is consumer-affecting and requires the version to move
  - [ ] **F2-AC2** — Given a property added to a node that permits unknown properties, When the change is classified, Then it is not consumer-affecting and the version does not move
  - [ ] **F2-AC3** — Given a value added to an enumerated set, When the change is classified, Then it is consumer-affecting — a consumer validating against the old set rejects the new value
  - [ ] **F2-AC4** — Given a field that stops being emitted, When the change is classified, Then it is consumer-affecting if the field was required and not otherwise
  - [ ] **F2-AC5** — Given a consumer-affecting change, When the version has not moved, Then the suite fails; and given the same change with the version moved, Then it passes

#### Feature 3: The emitted version cannot diverge from the declared version

- **User Story:** As the Tomo maintainer, I want the version a producer writes into a document to be
  checked against the version its schema declares, so that a bump cannot land in one and not the
  other.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F3-AC1** — Given a producer that writes a version literal, When that literal differs from the version its own schema declares, Then the suite fails naming both values
  - [ ] **F3-AC2** — Given every producer agreeing with its schema, When the suite runs, Then it passes
  - [ ] **F3-AC3** — Given a version moved in the schema only, When the suite runs, Then it fails — the check must catch divergence in both directions

#### Feature 4: A wire change is handed over before it ships

- **User Story:** As the consumer, I want to receive the schema and an account of what moved before
  the new version reaches a user's vault, so that I can vendor it rather than discover it.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F4-AC1** — Given a consumer-affecting wire change, When it is handed over, Then the handoff carries the schema document itself, not a description of it
  - [ ] **F4-AC2** — Given a handover, When the consumer reads it, Then for each changed field it states the meaning, which of the consumer's own areas must change, and whether the change breaks them immediately or only on some future run
  - [ ] **F4-AC3** — Given a change that breaks nothing today but will break on a run of a shape not yet produced, When it is handed over, Then that distinction is stated explicitly — it is not derivable from the schema
  - [ ] **F4-AC4** — Given a handover has been sent, When the consumer has not yet confirmed, Then Tomo continues to emit the previous version
  - [ ] **F4-AC5** — Given the consumer confirms, When the next run is produced, Then it carries the new version

#### Feature 5: The two instruction documents stop claiming the same identity

- **User Story:** As the consumer, I want each schema I am given to identify itself unambiguously, so
  that I cannot diff the wrong one.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F5-AC1** — Given the two instruction documents, When their identities are compared, Then they differ
  - [ ] **F5-AC2** — Given either document in isolation, When a reader inspects it, Then it states which role it plays — the consumer-facing contract, or the producer's own copy
  - [ ] **F5-AC3** — Given the identities are corrected, When the existing parity check runs, Then it still passes — the two documents remain structurally equivalent where they are meant to be

#### Feature 6: The known live drift is closed

- **User Story:** As the Tomo maintainer, I want the drift the detection immediately reports to be
  resolved, so that the report starts from silence and a future entry means something.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F6-AC1** — Given the garden-audit wire's undeclared fields, When they are handed to the consumer, Then the handover states that they are already being emitted and have been since an earlier spec
  - [ ] **F6-AC2** — Given the consumer has vendored them, When the detection runs, Then it reports no difference for that document
  - [ ] **F6-AC3** — Given the detection is run across all three wires after this spec completes, Then it reports nothing at all

#### Feature 9: The daily side gains a source identity

*Numbered out of sequence deliberately. This feature was dropped when the PRD was drafted from the
research findings, losing a decision recorded on 2026-09-09 and already promised to the consumer.
It is appended as F9 rather than inserted, because renumbering would invalidate every reference in
the plan — the cost of the mistake should not be paid by the documents that got it right.*

- **User Story:** As the consumer, I want every daily-side entry to carry the identity of the note it
  came from, so that two notes sharing a display name cannot be confused for one another.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F9-AC1** — Given a daily-side entry in any of the three buckets, When it is emitted, Then it carries the source note's identity as a required field
  - [ ] **F9-AC2** — Given the bucket that has never carried any source identity, When an entry is emitted, Then it carries one — this is the bucket a consumer could not join back to its origin by any means
  - [ ] **F9-AC3** — Given the existing display-text field, When the identity is added, Then the display field is unchanged
  - [ ] **F9-AC4** — Given the identity now travels on the wire, When the document is parsed, Then the lossy recovery that reconstructed it after a round trip is no longer used
  - [ ] **F9-AC5** — Given this change and the garden-audit disclosure, When they are handed over, Then they travel in **one** handover with one obligation table, not two

### Should Have Features

#### Feature 7: The report says what to do, not only what changed

- **User Story:** As the Tomo maintainer, I want a failure to tell me which action it expects, so that
  the first thing I do is not work out what the failure means.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F7-AC1** — Given a failure for a consumer-affecting change, When it is reported, Then it names moving the version and handing over as the expected next steps
  - [ ] **F7-AC2** — Given a failure for a change that is not consumer-affecting, When it is reported, Then it says so and does not ask for a version move

### Could Have Features

#### Feature 8: The consumer's copy is compared automatically

- **User Story:** As the Tomo maintainer, I want the check to compare against the consumer's actual
  published copy where it can, so that divergence is caught even when it originates on their side.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] **F8-AC1** — Given the consumer's published copy is reachable, When the check runs, Then it compares against it and reports any difference
  - [ ] **F8-AC2** — Given it is not reachable, When the check runs, Then it is skipped rather than failed, and the local checks still run

### Won't Have (This Phase)

- **Renumbering the features so F9 sits with the other Must Haves.** F9 was omitted from the first
  draft and appended; renumbering would break every plan reference for cosmetic gain. The
  out-of-sequence number is the honest record of the mistake.
- **A change to the cross-repo handoff protocol.** Considered and rejected on the owner's
  instruction: the existing flow is sufficient, because the round trip through the owner *is* the
  lead time. F4-AC4's "wait for confirmation" is that rule applied to emission, not a new construct.
  No shared protocol document is edited by this spec.
- **Versioning the fourteen internal schemas.** They have no consumer outside Tomo — verified by
  searching every sibling repository. Bringing them under the rule would make the report noisy with
  changes nobody can be broken by.
- **Closing the one open node** in the garden-audit wire. It is the consumer's schema and their
  decision. Worth raising in the handover, since its openness is the only reason the live drift is
  benign, but not something this spec changes.
- **A compatibility window or dual-version emission.** Settled 2026-09-09: the consumer declined it
  and pins one schema. There is no window to design.
- **Automated version bumping.** The check reports; a person decides. A mechanism that moves the
  version by itself would satisfy the check while defeating its purpose.

## Detailed Feature Specifications

### Feature: The bump rule distinguishes consumer-affecting changes from the rest

**Description:** Not every shape change obliges the consumer, and treating them alike would make the
rule cry wolf on exactly the case that is fine. The distinction is whether the changed node rejects
unknown properties. This was established by running the consumer's own validator against their own
fixtures, not by reasoning about versioning in general.

**User Flow:**
1. Maintainer edits a published wire document.
2. Check detects a shape difference against the recorded shape.
3. Check classifies it as consumer-affecting or not.
4. If consumer-affecting and the version has not moved, the run fails and says what is expected.
5. Maintainer moves the version and hands over; or, for a non-affecting change, records the new
   shape and continues.

**Business Rules:**
- Rule 1: A property added to a node that rejects unknown properties is consumer-affecting.
- Rule 2: A property added to a node that permits them is not.
- Rule 3: A value added to an enumerated set is consumer-affecting, even though it reads as additive.
- Rule 4: A field that stops being emitted is consumer-affecting only if it was required.
- Rule 5: Prose changes are never consumer-affecting.
- Rule 6: Each published wire carries its own version. One document's move never implies another's.
- Rule 7: A consumer-affecting change is not emitted until the consumer confirms.

**Edge Cases:**
- Scenario 1: A field is added to an open node nested inside a closed one → Expected: not
  consumer-affecting; the nearest enclosing rule that governs the field is the open node's.
- Scenario 2: A node changes from permitting unknown properties to rejecting them → Expected:
  consumer-affecting, because emissions previously valid may now be rejected.
- Scenario 3: Two wires change in one spec → Expected: two version moves, one handover.
- Scenario 4: A change is detected in a document the consumer does not vendor → Expected: no
  obligation; the document is out of scope.
- Scenario 5: A drift predating the mechanism is found on first run → Expected: reported like any
  other, resolved before the baseline is considered clean.
- Scenario 6: A field is added that no current run will ever populate → Expected: still
  consumer-affecting if the node is closed. The consumer breaks on the first run that populates it,
  and that run may be months away — which is precisely why it must be stated rather than inferred.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Not opt-in — the check runs in the existing suite, so every wire edit is covered from
  the day it lands. The equivalent measure is coverage: all three published wires under detection,
  and every producer's emitted version asserted.
- **Engagement:** Every test run exercises it; no one has to remember to invoke it.
- **Quality:** Zero undetected shape changes. The measurable form: after this spec, no wire document
  differs in shape from its recorded baseline without a failing test, and the detection report is
  empty across all three documents.
- **Business Impact:** Zero consumer-visible breakages originating in an unannounced wire change.
  The target is zero, not a rate — two have already occurred and both were found by accident.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Shape difference detected | document, location, property, consumer-affecting yes/no | The core signal; a non-empty result on a clean tree is the failure this spec exists to surface |
| Version divergence detected | document, emitted value, declared value | Catches a bump landing in one place and not the other |
| Consumer-affecting change without a version move | document, changed fields | The specific failure that produced both incidents |
| Handover sent | document, version transition, field count | Establishes that the announcement preceded the emission |
| Consumer confirmation received | document, version now emitted | Closes the loop; until it arrives the old version keeps being emitted |

All metadata only — document names, locations, property names, counts. No vault content, per the
project's audit-log rule.

---

## Constraints and Assumptions

### Constraints

- The consumer rejects unknown properties on almost every node, so most additive changes are
  breaking for them. This is their deliberate position and is not being negotiated.
- Each published wire carries an independent version. A single global number cannot describe them.
- Cross-repo work happens by handoff, and the producer waits. There is no automated channel between
  the repositories and this spec does not create one.
- Handoff files are gitignored and ephemeral; anything that must outlive the exchange belongs in the
  architecture repository.
- The detection must not require network access to pass. Comparing against the consumer's published
  copy is a bonus, not a gate.
- The system is near MVP: additive changes, no regression of existing checks.

### Assumptions

- **The consumer's open node in the garden-audit wire is deliberate.** Measured as open on both
  sides; not established that either side intends to keep it that way. If it is closed on a future
  re-vendor, the live drift becomes breaking retroactively — which is the argument for closing it now
  rather than leaving it.
- **The consumer will accept being told which of their own areas must change.** The obligation was
  inferred from reading their code; they have not been asked whether they want it. It is offered in
  the handover, not imposed.
- **The eight-class measurement is not reproducible from the repository.** Every class is stated
  above and the rule is independently checkable, but no fixture or result artifact was committed.
  Flagged by validation 2026-09-10; the classification tests are what will archive it.
- **The three vendored documents are the complete set of external contracts.** Verified by searching
  every sibling repository for references; a future consumer would have to be added deliberately.
- The consumer's published copy reflects what they have released — checked against their default
  branch, not only a working tree.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The detection reports the known live drift on every run and is learned as noise | High | High if unaddressed | Feature 6 closes it as part of this spec; the baseline must be silent before the mechanism is trusted |
| The rule is right but nobody applies it, exactly as before | High | Medium | The rule is enforced by a failing test, not documented as guidance. A rule nobody enforces is what already existed |
| A consumer-affecting change is misclassified as benign | High | Low | The classification is derived from the schema's own declarations rather than from judgement, and both directions are tested |
| The version moves but the handover is forgotten | Medium | Medium | F4-AC4 makes emission conditional on confirmation, so a forgotten handover stalls the emission rather than shipping silently |
| Fixing the identity collision breaks the existing parity check | Medium | Low | F5-AC3 requires that check to still pass; the documents stay structurally equivalent where they are meant to be |
| A future wire is added and nobody brings it under the rule | Medium | Medium | The check enumerates the published documents; adding one without registering it should itself be the failure |

## Open Questions

- [ ] Should the consumer close the one open node in the garden-audit wire? Their schema, their call —
      but its openness is the only reason the live drift is benign, and leaving it open means the next
      field to land there is equally invisible.
- [ ] Does the consumer want an account of which of their own areas must change, or only what moved
      on our side? Inferred from their code, never asked.
- [ ] Where does the durable record of a wire change live, given the handoff buffers are ephemeral?
      The architecture repository is the obvious home, but nothing is written there today.
- [ ] Should the detection compare against the consumer's published copy at all, given it cannot be a
      gate? Feature 8 proposes it as optional; it may be more noise than value.

---

## Supporting Research

### Competitive Analysis

Not applicable in the usual sense — this is an internal contract between two repositories with one
maintainer. The closest external analogue is schema-registry compatibility checking, where a producer
is prevented from publishing a schema that a registered consumer cannot read. The property this spec
wants is the same one; the mechanism is a test rather than a registry, because there is exactly one
consumer and it vendors rather than subscribes.

### User Research

Three findings shaped this document, all measured rather than reasoned:

- The existing drift check is structurally incapable of catching the class of change that caused the
  incident. Applied to the document that drifted it performs zero comparisons and passes.
- A second undeclared drift is live right now in a third document, found while researching this spec
  and benign only because of one permissive node.
- Whether a change is consumer-affecting is decided by whether the node is closed — established by
  running the consumer's own compiled validator against their own committed fixtures across the
  eight change classes below, which falsified this spec's original assumption that any shape change
  is breaking.

| # | Change class | Validator result | Consumer-affecting? |
|---|---|---|---|
| 1 | Property added to a node that rejects unknown properties | rejected | **yes** |
| 2 | Property added to a node that permits them | accepted | no |
| 3 | Field that was **optional** stops being emitted | accepted | no |
| 4 | Field that was **required** stops being emitted | rejected | **yes** |
| 5 | Value added to an enumerated set | rejected | **yes** — counter-intuitive |
| 6 | Type widened, emitting an empty value where a string was declared | rejected | **yes** |
| 7 | Already-declared optional field starts being emitted | accepted | no |
| 8 | Description or title text only | accepted (ignored entirely) | no |

Classes 3 and 4 collapse into one business rule conditioned on whether the field was required, which
is why seven rules cover eight classes.

**Provenance gap, recorded rather than implied.** No artifact of that run is committed anywhere —
no fixture copy, no result table, no handoff. The classes above are transcribed from the research
report, not from a re-runnable harness, so a reader cannot reproduce the results without repeating
the work. The rule they produced is separately checkable against each schema's own declarations,
which is what the implementation actually relies on; but the *measurement* is not archived. The
tests written for the classification in the implementation phase become that archive.

The owner supplied the decisive scoping constraint directly: no new handoff protocol is needed,
because the round trip through the owner is itself the lead time. That removed a proposed
two-phase-commit construct from the design.

### Market Data

Not applicable. The relevant measurements are the two drift incidents, the eight-class change matrix
run against the consumer's validator, and the node-openness counts per document, all recorded above.
