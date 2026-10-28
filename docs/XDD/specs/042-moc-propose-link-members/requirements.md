---
title: "/moc-propose finds MOC members through the link graph"
status: complete
version: "1.3"
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

## Output Schema

### PRD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |
| openQuestions | string[] | No | Unresolved items requiring stakeholder input |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

---

## Product Overview

### Vision
When Tomo proposes a MOC, the notes the user has already linked together count as evidence, so the proposal reflects how the vault is actually connected, not only which words its notes share.

### Problem Statement
`/moc-propose` finds members only through tags, folders, Dewey classes, cached topics, or notes without `up::`. Every cluster is formed by an exact match on a normalised topic. Two consequences, both measured in the code:

- **Linked notes are invisible.** A note that the user linked to three members of a cluster, but whose extracted topic is worded differently, never joins that cluster. A candidate without a matching topic produces no cluster row at all and silently drops out (`moc-discovery.py:864-876`). Tomo has no link signal anywhere in MOC discovery today.
- **The user's own linking work is not used.** The vault's link graph is the clearest record of what the user considers related, and Kado already resolves it (`kado-graph`, verified live 2026-10-27). Tomo reads it nowhere in MOC discovery. Spec 015 named the original problem: "related notes accumulate silently… the user discovers them retroactively."
- **Existing MOCs cannot grow.** `/moc-propose` can only propose a new MOC. A note that links to an existing MOC but has no `up::` to it can never be proposed as that MOC's member.

### Value Proposition
- Members the user already connected show up in the proposal, with the reason stated on their line, and stay unticked until the user agrees.
- The user can start from one note (`around:<note>`) and get a MOC proposal built from its links, or from an existing MOC (`around:<MOC>`) and get its missing members.
- No new apply step: the user ticks and accepts in the same proposal doc, and `/inbox` turns it into the same kind of instruction set as today.

## User Personas

### Primary Persona: The vault owner curating MOCs
- **Demographics:** Single owner of a personal Obsidian vault (LYT / MiYo profile), several hundred atomic notes and dozens of MOCs; comfortable with wikilinks and checkboxes, does not use tags or frontmatter as an interface (owner UX model).
- **Goals:** Keep MOCs complete without hunting for notes by hand; approve structure changes from one document with checkboxes.
- **Pain Points:** Proposals miss notes the owner obviously linked together; a note that links to a MOC but lacks `up::` stays an orphan of that MOC; such gaps surface only by accident.

### Secondary Personas
None. Tomo is single-user; the Hashi executor and `/inbox` are system consumers, covered under constraints.

## User Journey Maps

### Primary User Journey: Topic proposal with link members
1. **Awareness:** The user runs `/moc-propose` in any existing mode (e.g. `tag:psychology` or scan).
2. **Consideration:** The proposal doc lists topic members ticked as before, plus link members unticked with "linked with [[A]], [[B]]".
3. **Adoption:** The user ticks the link members that belong and accepts the section.
4. **Usage:** `/inbox` produces the instruction set; the ticked link members get the same `up::` handling as topic members.
5. **Retention:** Later runs keep surfacing linked notes that topics alone would miss.

### Secondary User Journeys

**Seed journey — `around:<note>`:** The user has a note that has grown links to several others and wants a MOC around it. They run `/moc-propose around:<note>`. Tomo proposes one new MOC whose members are the seed (ticked) and its linked notes (unticked, each with its link reason). If fewer than 3 notes remain after filtering, Tomo says so and writes no proposal.

**Extension journey — `around:<MOC>`:** The user runs `/moc-propose around:<MOC>` on an existing MOC. Tomo proposes the MOC's missing members: linked notes without `up::` to that MOC. On accept and `/inbox`, each ticked note gets `up:: [[MOC]]` and the MOC gets a link bullet for it. One missing member is enough for a proposal.

**Recovery journey — budget or Kado failure:** On a large vault the run reaches its link-lookup budget, or Kado refuses a lookup. The run still writes its proposals; clusters that were not looked up carry no link members, and the run report says how many were skipped and why.

## Feature Requirements

### Must Have Features

#### Feature 1: Link members augment topic clusters
- **User Story:** As the vault owner, I want notes that I linked to several members of a proposed MOC to appear in that proposal so that I can add them without searching.
- **Acceptance Criteria:**
  - [ ] Given a topic cluster in any existing mode and a note outside it that links to or is linked from at least 2 of its members, When `/moc-propose` runs, Then the note is listed in that cluster's Children as an unticked `- [ ]` line
  - [ ] Given a note linked with exactly 1 member of a cluster, When `/moc-propose` runs, Then it is not added to that cluster through links
  - [ ] Given a note that is already a topic member of the cluster, When it is also linked with members, Then it appears once, as a topic member, with its existing tick state
  - [ ] Given a note that qualifies for two clusters through links, When the doc is rendered, Then it is listed in each cluster it qualifies for, unticked in each
  - [ ] Given a proposal with link members, When the user ticks some and accepts the section, Then the ticked link members receive the same `up::` / `related::` / Override handling as topic members and unticked ones receive nothing

#### Feature 2: `around:<note>` — a new MOC around a seed note
- **User Story:** As the vault owner, I want to propose a MOC around one note's links so that a hub that grew organically can become a MOC.
- **Acceptance Criteria:**
  - [ ] Given a seed note that is not a MOC with at least 2 linked notes left after filtering, When the user runs `/moc-propose around:<note>`, Then one new-MOC proposal is written with the seed ticked and each linked note unticked
  - [ ] Given a seed note with fewer than 2 linked notes left after filtering, When the user runs `around:<note>`, Then no proposal is written and the run reports that fewer than 3 notes were found
  - [ ] Given a seed that is not in the cache, When the user runs `around:<note>`, Then no proposal is written and the run names the seed as not found; given a cached seed that Kado refuses or Tomo's key cannot read, Then no proposal is written and the run reports a seed lookup failure (per the seed-lookup criterion below) naming the seed
  - [ ] Given `Around:<note>` or another casing of the prefix, When the user runs it, Then it is treated as free text, consistent with the existing case-sensitive prefixes

#### Feature 3: `around:<MOC>` — extend an existing MOC with its missing members
- **User Story:** As the vault owner, I want an existing MOC's missing members proposed so that notes pointing at the MOC become proper members.
- **Acceptance Criteria:**
  - [ ] Given an existing MOC and a linked note without `up::` to that MOC, When the user runs `/moc-propose around:<MOC>`, Then an extension proposal for that MOC lists the note as an unticked missing member
  - [ ] Given an existing MOC whose linked notes all already have `up::` to it, When the user runs `around:<MOC>`, Then no proposal is written and the run reports that the MOC has no missing members
  - [ ] Given an accepted extension with ticked members, When `/inbox` processes it, Then each ticked member gets `up:: [[MOC]]` under the same existing-`up::` and Override rules as a new MOC's children, and the MOC gets one link line per ticked member that it does not already link
  - [ ] Given a ticked member that the MOC already links in its body, When the extension is applied, Then the member gets `up::` and the MOC gets no duplicate link line
  - [ ] Given an extension proposal, When it is rendered, Then it is visibly distinct from a new-MOC proposal: it names the existing MOC and offers no title, location or template choice

#### Feature 4: Each link member states why it is there
- **User Story:** As the vault owner, I want to see why a note was proposed through links so that I can judge it without opening it.
- **Acceptance Criteria:**
  - [ ] Given a link member, When the proposal doc is rendered, Then its line names the members (or the seed / MOC) it is linked with, e.g. "linked with [[A]], [[B]]"
  - [ ] Given a link member that also has an existing `up::`, When rendered, Then the line shows both the link reason and the existing-`up::` note shown today
  - [ ] Given a cluster with link members, When rendered, Then "Why this proposal" states how many members came through links, in addition to the topic sentence
  - [ ] Given any member line, When the doc is parsed back after the user's ticks, Then the member is read as the same note as before the annotation existed

#### Feature 5: Bounded link lookups with graceful degradation
- **User Story:** As the vault owner, I want a large run to finish and tell me what it skipped so that link lookups never stall or break `/moc-propose`.
- **Acceptance Criteria:**
  - [ ] Given a run whose link lookups would exceed the per-run budget, When the budget is reached, Then lookups stop, proposals are still written, clusters not looked up carry no link members, and the run report states how many clusters were not looked up because of the budget
  - [ ] Given a run, When it completes, Then it has not exceeded the per-run budget of link lookups and has not triggered a Kado rate-limit abort
  - [ ] Given Kado answers a link lookup with a rate-limit response that names a wait time, When the run handles it, Then it waits that time and retries the lookup before treating it as failed, and every retry counts toward the per-run budget
  - [ ] Given a link lookup that Kado refuses or that fails, When the run continues, Then that cluster carries no link members, the run report names the failure count, and no other part of the proposal changes
  - [ ] Given the `around:` seed lookup fails, When the run ends, Then no proposal is written and the run reports the failure rather than "fewer than 3 notes"

#### Feature 6: Link members respect the same boundaries as every other member
- **User Story:** As the vault owner, I want link members filtered like any other candidate so that daily notes, MOCs and excluded notes never appear as members.
- **Acceptance Criteria:**
  - [ ] Given a linked note that is a periodic note (daily, weekly, monthly, …), a MOC, an attachment, a note in the inbox, or outside the atomic-note paths, When `/moc-propose` runs, Then it is never proposed as a link member
  - [ ] Given a linked note tagged `exclude/note`, When `/moc-propose` runs, Then it is never proposed as a link member
  - [ ] Given a periodic note that links two members, When link qualification is counted, Then that periodic note does not make anything a link member by itself (periodic notes are not members and do not act as a bridge)
  - [ ] Given a linked note outside Tomo's key scope, When `/moc-propose` runs, Then it is never proposed and nothing in the doc reveals its name

### Should Have Features

#### Feature 7: The run report counts link members
- **User Story:** As the vault owner, I want the closing report to say what links contributed so that I can tell whether the feature helps on my vault.
- **Acceptance Criteria:**
  - [ ] Given a run, When it ends, Then the report states the number of link members proposed across all proposals and the number of link lookups made
  - [ ] Given a run with no link members, When it ends, Then the report states 0 rather than omitting the line

### Could Have Features
- Rank link members by how many members they link with, highest first, within the Children list.

### Won't Have (This Phase)
- **2-hop members (`related`).** Live data showed 2-hop results dominated by periodic-note hubs; 1-hop only.
- **Link signals in `/inbox` Pass 1.** Spec 040 rejected this (fresh inbox items carry no links); unchanged.
- **Ticking link members by default.** Owner decision: they always start unticked.
- **Clusters formed purely from links in the existing modes.** Links add members to topic clusters; only `around:` builds a proposal from links alone.
- **Removing members from an existing MOC**, or reordering it. Extension only adds.
- **Any change to the Hashi wire format.**

## Detailed Feature Specifications

### Feature: `around:<MOC>` — extend an existing MOC
**Description:** The user names an existing MOC. Tomo looks at the notes linked with it, keeps those that pass the member filters and do not already have `up::` to that MOC, and proposes them as missing members in a new section type of the proposal doc. Accepting it and running `/inbox` produces instructions that add `up:: [[MOC]]` to each ticked note and a link line to the MOC for each ticked note it does not already link.

**User Flow:**
1. User runs `/moc-propose around:<MOC name>`.
2. System recognises the target as an existing MOC, finds its linked notes, filters them and drops those already pointing `up::` to it.
3. System writes a proposal doc with one extension section: the MOC's name, the missing members unticked with their link reason and existing-`up::` state, the Override toggle, and an Accept box.
4. User ticks members and Accept.
5. User runs `/inbox`; the instruction set adds `up::` to each ticked note and a link line to the MOC for each ticked note it does not already link.
6. User applies the instruction set (Hashi or by hand), as today.

**Business Rules:**
- Rule 1: A member is missing when it is linked with the MOC in either direction, passes Feature 6's filters, and has no `up::` to that MOC, inline or in frontmatter (compared by note name, case-insensitive). Limit: only a note's first inline `up::` is known to discovery, so a note whose first inline parent is another note but which also names the MOC is still proposed, unticked.
- Rule 2: A missing member that has an `up::` to another note follows the same existing-`up::` and Override rules as a new MOC's child.
- Rule 3: The MOC gets a link line only for ticked members it does not already link; a note linked from the MOC body is never linked twice.
- Rule 4: One missing member suffices for a proposal.
- Rule 5: All extension members start unticked.
- Rule 6: An extension never removes or reorders anything in the MOC.

**Edge Cases:**
- The named target matches both a MOC and a non-MOC note by name → Expected: the run stops and names both, asking the user to give a path.
- The MOC itself has `up::` to one of its linked notes (a parent MOC) → Expected: that parent is not proposed as a member (it is a MOC, Feature 6).
- A linked note has `up::` to this MOC through frontmatter rather than an inline field (including a list of parents) → Expected: it counts as already a member and is not proposed.
- The MOC has no body anchor where a link line can be placed → Expected: the member still gets `up::`; the run reports that the MOC line could not be placed, as other MOC-placement failures are reported today.
- The MOC is renamed or deleted between proposal and `/inbox` → Expected: the section is withheld with a stated cause, as for any proposal whose target is gone.

## Success Metrics

### Key Performance Indicators
- **Adoption:** On the test vault, at least 3 of the topic proposals from a default scan carry at least one link member; `around:` produces a proposal for at least one real hub note and one real MOC.
- **Engagement:** In the owner's first live review, the owner ticks at least half of the link members shown (precision proxy).
- **Quality:** No run exceeds the link-lookup budget; 0 Kado rate-limit aborts across the validation runs; 0 periodic notes, MOCs, attachments or out-of-scope notes proposed as link members.
- **Business Impact:** Every ticked link member reaches the instruction set and gets its `up::` (and, for extensions, its MOC line) — no ticked member lost between doc and instructions.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Run finished | mode, proposals written, link members proposed, link lookups made, clusters not looked up (budget), lookups failed | Adoption, budget and failure metrics (Features 5, 7) |
| Proposal accepted | proposal type (new / extension), members ticked by source (topic / link / seed) | Precision proxy (engagement) |
| Instructions rendered | relationship lines and MOC lines emitted per accepted extension | Business impact: ticked members reach the instructions |

Tracking records counts and note paths only, never note content (MiYo Constitution, metadata-only).

---

## Constraints and Assumptions

### Constraints
- Proposal-first: `/moc-propose` never writes to vault notes; all changes go through the user's ticks, `/inbox` and the instruction set (spec 021).
- Kado limits requests per IP to 20 per 5 s by default, in the container as on the host, shared with the session's own MCP calls; link lookups need a per-run budget wherever the run happens.
- Tomo sees only what its Kado key may read; notes outside that scope are silently absent from link results and must stay invisible.
- No change to the Hashi wire format; extension uses relationship and MOC-link instructions that already exist.
- The proposal doc is written by the renderer only and parsed back after the user's ticks; added annotations must not change which note a line refers to.
- Runtime prose (agents, commands) follows the repo's runtime-file rules: imperatives only, rationale in `docs/tomo/`.

### Assumptions
- Kado's link graph reflects the vault within seconds of an edit; a run right after a bulk change may see slightly stale links.
- Links in frontmatter count as links (verified live for `up:`).
- The owner's vault keeps periodic notes identifiable through the profile's calendar configuration.
- Most clusters are small enough that looking up their members fits the budget on the owner's vault (hundreds of notes, dozens of MOCs).

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Hub notes (dailies, indexes) make unrelated notes look linked | High | High | Periodic notes and MOCs are neither members nor bridges (Feature 6); ≥ 2 members required (Feature 1) |
| Link lookups trigger Kado rate limiting and stall the run | High | Medium | Per-run budget, paced lookups, degrade instead of abort (Feature 5) |
| Too many unticked link members clutter the doc | Medium | Medium | ≥ 2-member threshold; unticked by default; Could-have ranking |
| Extension appends a duplicate link line to the MOC | Medium | Low | Rule 3: only for members the MOC does not already link |
| Adding members changes a cluster's identity and resurfaces a proposal the user rejected earlier | Medium | Medium | Rejected-proposal muting is keyed so that link members do not resurface it (SDD to define) |
| A note outside the key's scope leaks by name | High | Low | Out-of-scope notes are never named (Feature 6) |

## Open Questions

- [x] Shape — augment every mode AND `around:` (owner, 2026-10-27)
- [x] 1-hop only (owner)
- [x] Unticked by default (owner)
- [x] `around:<MOC>` extends with missing members; `up::` plus MOC link line; ≥ 1 member (owner)
- [x] Budget exhausted → truncate and report (owner)
- [ ] The exact per-run lookup budget (research suggests about 60 lookups); to be fixed in the SDD with the measured vault numbers.

---

## Supporting Research

### Competitive Analysis
Kado's `kado-graph` was itself motivated by a comparison with `aaronsb/obsidian-mcp-plugin`, which offers graph navigation but no proposal workflow (Kado handoff 2026-06-24). Obsidian's own graph view and backlinks pane show links but do not turn them into MOC membership. Tomo's distinguishing step is turning link evidence into a reviewable, checkbox-approved proposal.

### User Research
- Owner UX model (memory): signals are filenames, checkboxes and the `/inbox` summary; no tag or frontmatter interaction.
- Live probe on the test vault (2026-10-27): a MOC had 6 neighbours and 66 2-hop notes; a plain note had 2 neighbours (a daily and a weekly note) and all 32 of its 2-hop notes came through those periodic notes. Lookups took 6–29 ms each.
- Spec 040: link signals do not help inbox triage because new items carry no links.

### Market Data
Not applicable: single-user personal tool. Vault size reference points from earlier specs: 64 MOCs + 295 notes (spec 033); 209 atomic notes, 206 without `up::` (spec 021).
