---
title: "Route broken-`up` fixes by where the `up` actually lives"
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

When the garden audit offers to fix a broken parent link, the fix works — whether that link lives in
the note's body or in its YAML properties.

### Problem Statement

garden-audit's `broken_up` check finds notes whose declared parent no longer exists, and offers two
fixes: remove the link, or repoint it. For notes whose parent is declared as an **inline `up::`
line**, both work. For notes whose parent is a **YAML property**, both fail — because the audit does
not distinguish the two and always proposes a body-oriented fix.

The two failures have different shapes, and the quieter one is worse:

| User chooses | What we emit | What happens on a property-resident `up` |
|---|---|---|
| Remove | a body-line removal | The executor finds no `up::` line, reads that as "nothing to remove", and reports success. **The note is untouched and marked done.** |
| Repoint | a body-line replacement | The executor cannot find the line to replace and **fails loudly**, naming the missing marker. |

The remove path is the same silent-success shape that produced a month-long cross-repo investigation
this week: an action reported as applied against a note nothing happened to. The repoint path at
least tells the truth — but the user's approved fix still does not happen.

**In both cases the cause is identical: we sent the wrong kind of instruction**, because the finding
never carried the one fact that would have decided it.

**Measured, not estimated.** Of 64 notes carrying a parent declaration in the live vault, **17 are
property-resident**. Exactly **one** is currently broken, and it is the inline kind — so this is
**latent with a real population**, not an active outage. It becomes live the moment any of those 17
loses its parent.

### Value Proposition

The user approves a fix once and it happens. Today, for roughly a quarter of the notes that could
need it, approving either does nothing and says otherwise, or refuses.

There is a second beneficiary. Our sibling component deliberately left a defensive guard **unbuilt**
on our recommendation, because a guard there would have to swallow honest no-ops to catch our
mistake, and the durable fix is ours. That decision is recorded on their side and is waiting on this
work. Shipping it converts a rare-but-real failure into an unreachable one.

## User Personas

### Primary Persona: The vault owner running a garden audit

- **Demographics:** Single practitioner, high technical expertise, reviews every proposed fix before
  approving. Keeps some notes with inline Dataview fields and others with YAML properties — often
  because they arrived from different vaults or different eras of their own practice.
- **Goals:** Approve a batch of structural fixes and trust that the vault afterwards matches what was
  approved. Not to re-verify each note by hand.
- **Pain Points:** Has no way to tell, from the audit report, that a given note's fix will quietly do
  nothing. The report looks identical for both kinds of note. Discovering the failure requires
  noticing that a "fixed" note still shows a broken parent — which is exactly the thing the audit was
  supposed to notice for them.

### Secondary Personas

**The vault consolidator** — the same person merging notes from another vault. This is how mixed
declaration styles arise in the first place: the imported notes carry YAML properties, the existing
ones carry inline markers. This persona has the highest concentration of affected notes and the
lowest ability to spot the failure, because the imported notes are the least familiar.

## User Journey Maps

### Primary User Journey: Fixing a broken parent link

1. **Awareness:** The audit report lists a note whose parent no longer exists, and offers to remove
   or repoint the link.
2. **Consideration:** The user picks a fix. Today nothing in the report indicates that the choice may
   be inapplicable to this particular note.
3. **Adoption:** They approve, as they do for every other finding — the whole point of the audit is
   that findings are uniform and reviewable in bulk.
4. **Usage:** The fix is applied. The note's parent declaration is actually changed, wherever it
   lives.
5. **Retention:** The next audit no longer reports that note. Today, for a property-resident note, it
   reports it again — and the user has no explanation for why the fix "did not take".

### Secondary User Journeys

**Mixed batch.** The user approves twenty findings spanning both declaration styles in one pass. Each
is fixed correctly according to its own note; the user does not have to know which is which, and the
report does not ask them to.

**Reviewing before approving.** A user who wants to understand what will happen can see, per finding,
which kind of change is proposed. This matters more than usual here because a property change carries
a cost a body change does not.

## Feature Requirements

### Must Have Features

#### Feature 1: The finding knows where the parent is declared

- **User Story:** As a vault owner, I want each broken-parent finding to carry where the link
  actually lives, so that the right fix can be proposed for it.
- **Acceptance Criteria:**
  - [ ] Given a note declaring its parent as an inline marker, When the audit produces a finding for
        it, Then the finding records the declaration as body-resident.
  - [ ] Given a note declaring its parent as a YAML property, When the audit produces a finding for
        it, Then the finding records the declaration as property-resident.
  - [ ] Given a note with no parent declaration at all, When the audit runs, Then no broken-parent
        finding is produced for it — unchanged from today.
  - [ ] Given the audit runs, Then it makes no additional vault queries to determine this.

#### Feature 2: Property-resident fixes are proposed as property changes

- **User Story:** As a vault owner, I want a fix to a YAML-declared parent to actually change that
  property, so that approving it changes the note.
- **Acceptance Criteria:**
  - [ ] Given a property-resident finding and the user chooses removal, When instructions are
        rendered, Then a property-removal action is emitted naming the correct property.
  - [ ] Given a property-resident finding and the user chooses to repoint, When instructions are
        rendered, Then a property-set action is emitted carrying the new value.
  - [ ] Given a body-resident finding, When instructions are rendered, Then the actions emitted are
        **byte-identical to today's** — for either choice.
  - [ ] Given a mixed batch, When instructions are rendered, Then each finding produces the action
        matching its own note.
  - [ ] Given any property action is emitted, Then the property name is derived from the configured
        parent marker rather than hardcoded.

#### Feature 3: Property changes carry a guard against a changed vault

- **User Story:** As a vault owner, I want a property change to refuse rather than overwrite if the
  note changed since the audit, so that a stale proposal cannot clobber newer work.
- **Acceptance Criteria:**
  - [ ] Given a property action is emitted, Then it carries the property's value as observed at audit
        time.
  - [ ] Given the value carried is a list, Then its order matches the note exactly — order is
        significant to the executor and a reordered value must not be treated as equal.
  - [ ] Given the property did not exist at audit time, When a set action is emitted, Then it
        expresses "must not exist" rather than "holds an empty value" — these are distinct and are
        enforced as mutually exclusive downstream.
  - [ ] Given the audit cannot determine the observed value, When the finding is processed, Then no
        property action is emitted and the finding is reported as unroutable rather than guessed.

#### Feature 4: The proposal tells the user a property change is different

- **User Story:** As a vault owner, I want to know before approving that a fix will edit YAML
  properties, because that has a cost a body edit does not.
- **Acceptance Criteria:**
  - [ ] Given a property-resident finding, When the report is rendered, Then it states that the fix
        edits a note property and names the property.
  - [ ] Given a property-resident finding, When the report is rendered, Then it warns that comments
        in the note's property block will not survive the edit.
  - [ ] Given a body-resident finding, When the report is rendered, Then no such warning appears and
        the wording is unchanged from today.

#### Feature 5: The coverage audit accounts for property actions

- **User Story:** As a vault owner, I want the pipeline's self-check to cover the new action kind, so
  that a missing or spurious property change is caught rather than passing silently.
- **Acceptance Criteria:**
  - [ ] Given approved property-resident findings, When the coverage audit runs, Then it expects
        exactly that many property actions.
  - [ ] Given fewer are emitted than expected, When the coverage audit runs, Then it reports a
        mismatch and fails.
  - [ ] Given an instruction set contains property actions, When the audit reports totals, Then they
        are included in the total rather than omitted from it.
  - [ ] Given a dry run of such a set, When it is executed, Then it describes the property actions
        rather than rejecting the set as containing an unknown action.

#### Feature 6: Older caches degrade instead of misbehaving

- **User Story:** As a vault owner, I want an audit run against a cache built before this change to
  behave predictably, so that I am not silently returned to the old broken behaviour.
- **Acceptance Criteria:**
  - [ ] Given a cache entry that predates this change, When a broken-parent finding is produced for
        it, Then no property action is emitted for it.
  - [ ] Given such an entry, When the report is rendered, Then the user is told the finding cannot be
        routed until the cache is refreshed, and how to refresh it.
  - [ ] Given such an entry, Then no body-oriented action is emitted for it either — the wrong fix is
        withheld rather than repeated.
  - [ ] Given a refreshed cache, When the audit re-runs, Then the finding routes normally.

### Should Have Features

- **Report the routing split.** Show, per run, how many findings were body-resident versus
  property-resident. Makes the population visible and would have surfaced this class of defect
  earlier.
- **Unroutable-finding summary.** A single line naming findings withheld for a stale cache, rather
  than only a per-finding note.

### Could Have Features

- **Migrate a property-resident parent to the configured style.** If the vault is configured for
  inline markers, a broken property-resident parent could be repointed *and* moved to the configured
  form in one step. Tempting and out of scope: it changes the note beyond the fix the user approved.
- **Extend routing to other relationship markers.** The same body-versus-property split applies to
  any relationship field, not just the parent. This phase covers only the parent, because it is the
  only one with a measured population and a shipped executor path.

### Won't Have (This Phase)

- **Any change to the sibling executor.** Our recommendation was explicitly that no defensive guard
  be added there, and it was accepted and recorded. This spec is the alternative to that guard, not a
  complement to it.
- **Changing how notes declare their parent.** Both forms remain valid and the existing precedence
  between them is untouched.
- **Fixing a property-resident parent that is not broken.** Only findings the audit already produces
  are in scope; this spec changes how they are fixed, not what is found.
- **Rewriting a property to remove the comment-loss cost.** The cost is inherent to how properties
  are written by the vault application. It is disclosed, not engineered around.
- **Re-reading notes at audit time to obtain values.** The parent's declared value is already
  observed when the discovery cache is built. Introducing per-note reads here would repeat a pattern
  already rejected on rate-limiting grounds.

## Detailed Feature Specifications

### Feature: Property-resident fixes are proposed as property changes

**Description:** The audit already knows, for every note, whether its parent came from the body or
from a property — it has recorded this for as long as the cache has existed. What it has never done
is *use* it. The change is to carry that fact from the cache into the finding, and to branch on it
when the user's chosen fix is turned into an instruction.

**User Flow:**

1. User runs the garden audit.
2. System produces broken-parent findings, each carrying where the parent is declared and what value
   is declared there.
3. System renders the report, marking property-resident findings and their added cost.
4. User approves a mix of findings, choosing remove or repoint per finding, exactly as today.
5. System emits, per finding, the action matching that note's declaration style.
6. User applies. Every approved fix changes its note.

**Business Rules:**

- Rule 1: The declaration site is determined at cache-build time and carried through unchanged. The
  audit never re-derives it.
- Rule 2: Body-resident findings produce exactly the actions they produce today — this is a routing
  addition, not a rewrite.
- Rule 3: A property action names its property by deriving it from the configured parent marker.
  Hardcoding the property name is not acceptable, because markers are profile-driven.
- Rule 4: Every property action carries the value observed at audit time, faithfully — including list
  order.
- Rule 5: "Property absent" and "property holds an empty value" are distinct states and must be
  expressed distinctly.
- Rule 6: If the declaration site or the observed value is unavailable, no action is emitted for that
  finding and it is reported. Emitting the body-oriented action as a fallback is forbidden — that is
  the current defect.
- Rule 7: A property change never implies any other change to the note.
- Rule 8: The user's choice between remove and repoint is unchanged; routing happens after the choice
  and is invisible in the choosing.

**Edge Cases:**

- A note declares its parent in **both** a property and an inline marker → Expected: the existing
  precedence decides which one the audit considered broken, and the fix targets that one. The other
  is left alone.
- The property holds a list with several entries, only one of which is broken → Expected: the
  emitted value is the whole intended new list, not an item operation. The executor has no item-level
  operations by design.
- The property holds a scalar rather than a list → Expected: handled; the observed shape is carried
  faithfully rather than normalised into a list.
- The property holds a literal empty value → Expected: distinguishable from the property being
  absent.
- The note's property block contains comments → Expected: the user is warned before approving, since
  they will be lost on a successful edit.
- The cache predates this change → Expected: Feature 6 — withhold and report, never fall back.
- The vault is configured for a different parent marker → Expected: the property name follows the
  configuration.
- Two findings target the same note → Expected: not currently possible for this check, and if it
  became possible, the actions must not both claim the same property.

## Success Metrics

### Key Performance Indicators

- **Correctness — routing:** 100% of broken-parent findings produce an action matching their own
  note's declaration style. Baseline today: property-resident findings are routed correctly 0% of the
  time.
- **Correctness — no silent success:** zero actions reported as applied against a note that was not
  changed. This is the defect class; it should become unreachable rather than rare.
- **Correctness — no wrong-kind fallback:** zero body-oriented actions emitted for property-resident
  findings, including when the cache is stale.
- **Regression safety:** body-resident findings produce byte-identical instruction sets to today's.
- **Cost:** zero additional vault queries per run. A measurable increase is a failure of Rule 1 and
  of the design's central claim.
- **Audit integrity:** the new action kind appears in the coverage audit's totals.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Finding routed | declaration site, per finding and per run | The headline: confirms routing fires and shows the split. A run with zero property-resident findings is indistinguishable from broken routing without this |
| Finding unroutable | reason (stale cache / missing value), note | Validates Rule 6. A rising count means the cache-refresh path is not reaching users |
| Property actions emitted | count per run | Reconciles against the coverage audit |
| Vault queries per run | existing per-run counter | Guards the zero-added-cost claim. Note the counter is known to under-report and is being corrected in spec 031; this metric depends on that correction |
| Comment-loss warnings shown | count per run | Confirms the disclosure reaches the user before approval rather than after |

## Constraints and Assumptions

### Constraints

- **The executor's property-edit contract is fixed and shipped.** It requires a guard value, compares
  it exactly, treats list order as significant, and enforces "absent" and "empty" as mutually
  exclusive. We consume that contract; we do not negotiate it in this phase.
- **A successful property edit drops comments in the property block.** Inherent to how the vault
  application writes properties. Must be disclosed, cannot be avoided.
- **A failed property edit leaves the file byte-identical.** A guarantee we may rely on, not one we
  provide.
- **The parent marker is profile-driven.** Nothing may hardcode the property name.
- **Zero additional vault queries.** The observed value must come from data already gathered when the
  cache is built. Per-note reads at audit time repeat a pattern already rejected on rate-limiting
  grounds.
- **Existing caches lack any new field.** The design must degrade visibly rather than crash or fall
  back to the broken behaviour.
- **Additive only.** Body-resident behaviour is a hot path and must not change.

### Assumptions

- The declaration site recorded at cache-build time still reflects the note at apply time. If it does
  not, the guard value catches it — that is what the guard is for.
- Users want the fix applied where the parent actually lives, rather than migrated to the configured
  style. Migration is listed as explicitly out of scope on that basis; if this assumption is wrong,
  the Could-have becomes the requirement.
- The comment-loss cost is acceptable when disclosed. If users decline property fixes because of it,
  the disclosure is doing its job and the finding remains reportable-but-unfixed, which is strictly
  better than today's silent no-op.
- The population is stable enough that a latent defect is worth fixing before it becomes active. The
  measured seventeen makes this a matter of when, not whether.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The new action kind is omitted from the coverage audit's reconciliation list, so it passes green while the actions go unchecked | High | **High** — this is the default outcome of adding a kind, and it is the second consecutive spec to face it | Feature 5 makes it an acceptance criterion. Beyond this spec: the recurrence argues for a checklist rather than vigilance |
| A stale cache silently falls back to the body-oriented action, reproducing the exact defect | High | Medium | Rule 6 forbids the fallback; Feature 6 requires withhold-and-report. The fallback is the tempting implementation, which is why it is named as forbidden rather than merely undesirable |
| The observed value is normalised on the way into the cache, so the guard fails on ordering or shape noise | Medium | Medium | Rule 4 requires faithful carriage. An acceptance criterion covers list order specifically, because the executor treats it as significant |
| Comment loss surprises a user after the fact | Medium | Medium | Feature 4 puts the warning at approval time. A post-hoc note would be too late by construction |
| Scope drifts into migrating declaration styles | Medium | Low | Explicit Won't-Have with a stated rationale: it changes the note beyond the approved fix |
| Body-resident behaviour changes as a side effect of adding the branch | High | Low | Byte-identical output is an acceptance criterion, not an aspiration |

## Open Questions

- [ ] **Where is the observed property value captured, and in what shape?** It is available for free
      at cache-build time, in two places. Whether it is captured by extending the existing parent
      parser (keeping one source of truth) or read separately at the cache-build site (duplicating
      the property-name derivation) is a design decision with maintenance consequences. **This is the
      spec's central question and belongs in the SDD as an ADR.**
- [ ] **What exactly does a stale-cache finding look like to the user?** Feature 6 requires withhold
      and report; the wording and placement should be decided with the report's existing conventions
      in view rather than invented.
- [ ] **Should the routing split be surfaced per run?** Listed as a Should-have. It is cheap and it is
      the observability that would have caught this class earlier — but it adds a line to a report
      that is already dense.

---

## Supporting Research

### Competitive Analysis

Not applicable as a market comparison. The instructive comparison is internal: this is the **third**
defect of the same family found this week. All three shared one shape — an action that could not
possibly succeed reported as having succeeded, because the executor read "I found nothing to change"
as "there was nothing to change".

Two were fixed in the executor by making the impossible case fail loudly. The third — this one — was
deliberately **not** fixed there, because the honest guard could not be written: in a vault using
inline markers, "no marker line" genuinely does mean "nothing to remove". That asymmetry is what
makes this a producer-side problem. The lesson carried forward: when a guard cannot distinguish a
real no-op from a misrouted action, the routing is what needs fixing.

### User Research

Direct observation against the live vault rather than interviews.

- **Population:** 64 notes carry a parent declaration; 17 are property-resident, 18 inline, 29 have
  none. Property-resident is a quarter of all notes and nearly half of all declarations.
- **Current breakage:** exactly one, and it is inline — so the defect is latent today. The measured
  gap between "population" and "currently broken" is what sets this spec's urgency at low.
- **Origin of the mix:** the property-resident notes correspond to an import from another vault which
  used properties, into a vault configured for inline markers. Mixed declaration styles are a
  consequence of consolidation, not of inconsistency — which suggests the population grows with each
  import rather than decaying.
- **Discoverability:** the failure is invisible in the report and invisible in the applied result.
  The only signal is the same finding reappearing in a later audit, which reads as the audit being
  wrong rather than the fix being wrong.

### Market Data

Not applicable. The number that matters for design is seventeen: large enough that the defect will
occur, small enough that no batching, pagination or performance work is warranted anywhere in this
feature.
