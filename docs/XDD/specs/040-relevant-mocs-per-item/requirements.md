---
title: "Every item sees every MOC, by name"
status: complete
version: "1.2"
---

# Product Requirements Document

> **Scope note.** Issue #173 reported that the MOC inventory in the shared
> context degrades as the vault grows. Research for this spec found that the
> degradation already happens at today's size and that the cause is not the
> size of the budget but the fact that every inbox item receives the whole
> inventory. It also found that the obvious fix — pick a few MOCs per item in
> advance by word overlap — would lose half of the MOC links Tomo makes today,
> because Tomo links by meaning. This spec therefore gives every item the
> *names* of all MOCs and the *detail* of only the MOCs it nominates.

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
| specId | 040-relevant-mocs-per-item |
| title | Every item sees every MOC, by name |
| status | `COMPLETE` |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 30 |
| openQuestions | 0 — the variance question is resolved by design (KPIs) |

### SectionStatus

| Section | Status | Detail |
|---------|--------|--------|
| Product Overview | `COMPLETE` | |
| User Personas | `COMPLETE` | Three; one is a machine |
| User Journey Maps | `COMPLETE` | One primary, four secondary |
| Feature Requirements | `COMPLETE` | 6 Must, 2 Should, 1 Could |
| Detailed Feature Specifications | `COMPLETE` | F1 + F2 + F3 |
| Success Metrics | `COMPLETE` | |
| Constraints and Assumptions | `COMPLETE` | |
| Risks and Mitigations | `COMPLETE` | |
| Open Questions | `COMPLETE` | One, non-blocking |
| Supporting Research | `COMPLETE` | Agent-team research, 2026-10-23 |

---

## Product Overview

### Vision

Tomo links every inbox item to the right existing MOC, with heading-level
placement, no matter how many MOCs the vault holds — and never proposes a new
MOC for a theme the vault already has.

### Problem Statement

During `/inbox`, every item is analysed by its own subagent, and every one of
those subagents receives the complete MOC inventory: each MOC's title, topics,
headings, editable callouts and footer flag. The inventory is capped by a size
budget, and when it does not fit, detail is removed for **all** MOCs at once.

Measured on the test instance on 2026-10-23 (65 MOCs):

- **Degradation has already started.** The untrimmed context is 44.7 KB against
  a 40 KB budget. Editable callouts have been removed from all 50 MOCs that had
  them, and 2 of 43 MOCs have lost their headings — so Tomo can no longer place
  a link inside a callout, and for those two MOCs not under a heading.
- **It gets worse with every MOC.** At ~96 MOCs no MOC keeps its headings; at
  ~216 the context no longer fits at all (reproduced from #173).
- **The real ceiling is lower than the budget.** The subagent loads the MOC
  list in one read. Above ~37.7 KB that read is no longer delivered whole — the
  subagent sees a 2 KB preview. The untrimmed list crosses that line at ~73
  MOCs. Raising the budget therefore cannot fix this.
- **It already costs quality.** In the archived analyst transcripts, 134 runs
  never parsed the MOC list; 80 of them hit the oversized-read path. They
  produced 98 note actions, only 26 of which carried MOC candidates.
- **It costs money per item.** The MOC list is ~14.7k tokens per item, about
  12–13% of the per-item Phase-B cost ($0.60/item baseline, 2026-10-13), paid
  again for every item in the run.

Consequence of not solving it: as the owner's vault grows, Tomo silently stops
placing links under headings, then stops seeing MOCs reliably, and the owner
receives more "create a new MOC" proposals for themes that already have one.

### Value Proposition

- **Placement quality stops depending on vault size.** Heading and callout
  placement is available for every MOC Tomo picks, at 65 MOCs and at 512.
- **No duplicate MOC proposals for existing themes.** Today nothing checks a
  proposed MOC against the MOCs that already exist; after this spec, two
  independent checks do.
- **Lower and flat per-item cost.** Each item pays for MOC names plus the detail
  of the few MOCs it nominated, instead of the detail of every MOC.

The alternative Tomo is weighed against is its own current behaviour, plus two
cheaper fixes that research rejected: raising the budget (blocked by the
read ceiling) and pre-selecting MOCs per item by word overlap (recall 0.50 —
half of today's links are by meaning, with no shared words).

## User Personas

### Primary Persona: The vault owner, reviewing `/inbox` suggestions

- **Demographics:** Runs Tomo against a personal Obsidian vault structured with
  LYT or MiYo conventions; 60–500 MOCs; writes in German and English; reviews
  suggestions as rendered markdown with checkboxes, not through tags or
  frontmatter.
- **Goals:** Each new note lands under the right MOC, under the right heading,
  with as little correction as possible. New MOCs are proposed only for themes
  that genuinely have none.
- **Pain Points:** Suggestions that link to the MOC but not to a section;
  "Proposed MOC: Vacation" when "Vacation (MOC)" already exists; quality that
  quietly drops as the vault grows, with no warning that tells them why.

### Secondary Persona: The inbox analyst (Phase-B subagent)

- **Demographics:** One language-model subagent per inbox item; reads the
  shared context and its item, writes one result file; cannot call other agents.
- **Goals:** See enough about every MOC to judge relevance by meaning; see the
  placement detail of the MOCs it nominates; get every read delivered whole.
- **Pain Points:** A read that is cut to a preview, after which it improvises;
  placement detail that was removed before it ever saw it.

### Secondary Persona: The maintainer, measuring cost and quality

- **Demographics:** The owner in their developer role; runs live tests on the
  test instance and records per-run cost in the inbox cost log.
- **Goals:** Prove that a change lowered cost without lowering Pass-1 quality,
  with numbers from a real run.
- **Pain Points:** A size budget with no stated reason; degradation that is only
  visible by reading subagent transcripts.

## User Journey Maps

### Primary User Journey: The owner processes an inbox in a large vault

1. **Awareness:** The owner drops twelve notes into the inbox and runs `/inbox`.
2. **Consideration:** Nothing to choose; the owner expects the same quality
   whether the vault has 65 or 300 MOCs.
3. **Adoption:** No action needed — the change applies to every run.
4. **Usage:** Each item's analysis sees the names of all MOCs, nominates the ones
   that fit by meaning, and receives the headings and callouts of those MOCs.
   The suggestions document shows each note with its MOC links and a proposed
   section.
5. **Retention:** Placement suggestions stay precise as the vault grows; the
   owner corrects fewer links.

### Secondary User Journey: An item matches a MOC by meaning only

A German note about a day trip to Pirna has no word in common with the MOC
"Elbsandstein & Tschechien 2026 (MOC)". The analysis sees that MOC's name,
recognises the theme, and proposes it — as it does today when it happens to
see the whole list.

### Secondary User Journey: An item has no fitting MOC

The analysis finds no existing MOC whose name covers the item's theme. Before
proposing a new MOC, it checks its proposed name against the names of all
existing MOCs. Only if none matches does the owner see a "Proposed MOC".

### Secondary User Journey (error path): A proposed name equals an existing MOC

The analysis proposes a new MOC whose name, once normalised, is the name of a
MOC that already exists. The owner does not see a "Proposed MOC" for it; the
note is offered a link to the existing MOC instead, unticked, so the owner
decides.

### Secondary User Journey: Two MOCs share a title

The vault holds "Projects" in the MOC folder and another "Projects" under an
area folder. The analysis sees both, told apart by location, and its choice
resolves to exactly one of them.

### Secondary User Journey: The maintainer compares before and after

The maintainer runs the same inbox on the test instance before and after the
change, compares the MOC candidates per item and the Phase-B cost per item,
and records both runs in the cost log.

## Feature Requirements

Features are grouped by the decision they protect. Each MoSCoW item is a
distinct behaviour; a criterion appears under exactly one feature.

### Must Have Features

#### Feature 1: Every item sees the name of every eligible MOC

- **User Story:** As the vault owner, I want every item's analysis to know all
  my MOCs by name, so that Tomo can link by meaning and not only by shared words.
- **Acceptance Criteria:**
  - [ ] Given a vault with N eligible MOCs, When an item is analysed, Then the analysis has read the title of all N MOCs.
  - [ ] Given all MOC titles in the vault are distinct, When the MOC names are delivered, Then each name is delivered without a path.
  - [ ] Given two or more MOCs share a title and at least one of them lies inside the configured MOC folders, When the names are delivered, Then each colliding MOC outside those folders carries its path and the one inside does not.
  - [ ] Given two or more MOCs share a title and none — or more than one — of them lies inside the configured MOC folders, When the names are delivered, Then every colliding MOC carries its path.
  - [ ] Given any delivered name, When the analysis nominates it, Then it resolves to exactly one MOC.
  - [ ] Given a vault with 512 eligible MOCs whose titles are of typical length (the test instance's average), When an item reads the MOC names, Then the read is delivered whole, not as a preview; longer titles raise a size warning at build time.
  - [ ] Given a classification MOC (Dewey-numbered title), When names are delivered, Then it is included, and the analysis can still tell it is a classification MOC.

#### Feature 2: Placement detail arrives for the nominated MOCs, complete

- **User Story:** As the vault owner, I want Tomo to know the headings and
  callouts of every MOC it considers linking my note to, so that it can propose where in the
  MOC the link belongs, regardless of how large my vault is.
- **Acceptance Criteria:**
  - [ ] Given the analysis has nominated MOCs for an item (up to six per thread, at most twenty per item), When it prepares placement, Then it has the headings, editable callouts and footer flag of each nominated MOC, at the same caps as today (8 headings, 4 callouts); up to three per thread become candidates.
  - [ ] Given a vault of any size up to 512 MOCs, When the context is built, Then no MOC loses its headings or editable callouts because of vault size.
  - [ ] Given a nominated MOC has no headings or callouts, When placement is prepared, Then placement falls back exactly as it does today for such a MOC.
  - [ ] Given the analysis nominated no MOC at all, When the item is analysed, Then no placement detail is read.
  - [ ] Given a nominated name does not resolve to a MOC, When placement is prepared, Then that name is dropped, the analysis records it as an issue, and the item's other candidates are unaffected. *(Amended 2026-10-24, SDD ADR-10: a name without a path cannot become a candidate.)*

#### Feature 3: A new MOC is proposed only after checking existing names

- **User Story:** As the vault owner, I want Tomo to check its proposed new MOC
  against my existing MOCs before proposing it, so that I am not asked to create
  a MOC I already have.
- **Acceptance Criteria:**
  - [ ] Given the analysis would propose a new MOC, When an existing MOC's name covers the same theme, Then it links the item to that MOC instead of proposing a new one.
  - [ ] Given no existing MOC name covers the theme, When the analysis finishes, Then it proposes the new MOC as today.
  - [ ] Given a placeholder link names the theme, When the analysis finishes, Then the placeholder still takes precedence as today (a dead link the owner wrote is not an existing MOC).

#### Feature 4: A proposal that duplicates an existing MOC name never reaches the owner

- **User Story:** As the vault owner, I want a deterministic safety net behind
  the analysis, so that a "Proposed MOC" with the name of an existing MOC never
  appears even when the analysis misses it.
- **Acceptance Criteria:**
  - [ ] Given a proposed MOC whose name, normalised for case, whitespace, punctuation, English plural and the vault's MOC suffix (the same key that groups proposals), equals the title of an eligible thematic MOC, When the suggestions document is built, Then no "Proposed MOC" is shown for it.
  - [ ] Given that case, When the suggestions document is built, Then each item that carried the proposal is offered a link to the existing MOC — to every MOC with that title when titles collide — unticked.
  - [ ] Given a proposed name that only resembles an existing title (no normalised equality), When the document is built, Then the proposal is shown unchanged.
  - [ ] Given the safety net acts, When the run finishes, Then the run summary names how many proposals it converted.

#### Feature 5: MOCs tagged `MiYo/Tomo/exclude/moc` are not inbox link candidates

- **User Story:** As the vault owner, I want to mark MOCs such as my root index
  so that Tomo never offers them as a link target for inbox notes.
- **Acceptance Criteria:**
  - [ ] Given a MOC tagged `MiYo/Tomo/exclude/moc` (frontmatter or inline), When an item is analysed, Then that MOC is not among the delivered names and is never a candidate.
  - [ ] Given that tag, When `/moc-propose` runs, Then its behaviour is unchanged (the tag still skips the MOC in uplink checks).
  - [ ] Given a proposed MOC whose name equals an excluded MOC's title, When the safety net of Feature 4 runs, Then the excluded MOC is not offered as the link (the proposal is shown, so the owner sees the collision).

#### Feature 6: Both inbox paths behave the same, and no run reads another run's data

- **User Story:** As the vault owner, I want the normal and the force-atomic
  inbox paths to give the same MOC behaviour, and a run never to use MOC data
  from an earlier run.
- **Acceptance Criteria:**
  - [ ] Given the force-atomic path, When items are analysed, Then Features 1–5 apply exactly as on the normal path.
  - [ ] Given MOC data left from an earlier run, When a new run starts, Then the new run's analyses read only data built for the new run.
  - [ ] Given a pass-1 reset of the temporary workspace, When it completes, Then no MOC data from the previous run remains.

### Should Have Features

#### S1: Placeholder names are delivered once each

- **User Story:** As the vault owner, I want the dead-link MOC names Tomo checks
  against to be delivered without repetition, so that each item's read stays
  small as my MOCs accumulate dead links.
- **Acceptance Criteria:**
  - [ ] Given a placeholder target referenced by several MOCs, When placeholder names are delivered, Then the target appears once.
  - [ ] Given a placeholder target matches an item's theme, When the analysis finishes, Then it proposes the placeholder as today.

#### S2: The owner-facing documents say where MOC detail goes

- **User Story:** As the vault owner, I want the privacy notes and the
  documentation to describe which MOC data reaches the model and when.
- **Acceptance Criteria:**
  - [ ] Given this spec ships, When the owner reads the privacy notes, Then they state that MOC names reach every item's analysis, that MOC headings and callouts reach it only for the MOCs it nominated, and that the `MiYo/Tomo/exclude/moc` tag only removes a MOC from inbox link candidates and is not an access control.
  - [ ] Given this spec ships, When the owner reads the reference documentation for inbox processing, Then it describes the name list, the per-MOC detail, and the exclude tag's new meaning for inbox candidates.

### Could Have Features

#### C1: The run reports the size of what each item read

- **User Story:** As the maintainer, I want the context build to report the size
  of the name list and of the full MOC detail, so that I can see growth before it
  becomes a problem.
- **Acceptance Criteria:**
  - [ ] Given a context build, When it finishes, Then its summary line states the byte size of the MOC name list, the number of eligible and excluded MOCs, and the number of title collisions.

### Won't Have (This Phase)

- **Pre-selecting MOCs per item by word overlap.** Measured recall 0.50 at any
  K from 3 to 30; rejected.
- **kado-graph as a relevance signal.** It walks one note's links; inbox items
  rarely have links. Stays with #82.
- **Asking Hashi whether its MOC picker uses `candidate_mocs`.** Owner decided
  not to raise it in this spec; the shape of every Tomo–Hashi channel is
  unchanged (see Constraints).
- **Owner-labelled ground truth for MOC choice.** Quality is measured as
  agreement with today's choices on the same inbox.
- **Changes to `/moc-propose`, garden-audit or vault-explorer.** They read the
  full inventory from their own cache, not from the inbox context.
- **New scoring weights or heading signals** (#125, #126).

## Detailed Feature Specifications

### Feature: F1 + F2 + F3 — names for every MOC, detail for the nominated ones, a check before proposing

**Description:** Today each item's analysis reads one list that carries every
MOC with all its detail. After this spec the analysis reads the names of all
eligible MOCs, decides by meaning which ones fit, checks a would-be new MOC
against those names, and then obtains the placement detail of only the MOCs it
nominated. Because only the names are read for every MOC, the detail no longer has
to be cut to fit, so it is complete for whichever MOC is nominated.

**User Flow:**
1. Owner runs `/inbox`.
2. System builds the run's context: eligible MOC names (with paths only where
   titles collide), full detail for every eligible MOC, and the placeholder names.
3. Each item's analysis reads the names, splits a long item into threads as
   today, and nominates up to six MOCs per thread by meaning.
4. If no existing MOC fits, the analysis checks its proposed name against the
   names before proposing a new MOC.
5. The analysis obtains the detail for its nominated MOCs (one read per
   item), keeps up to three per thread as candidates, and proposes placement.
6. The suggestions document is built; any proposal whose normalised name equals
   an eligible thematic MOC's title is turned into an unticked link to that MOC.
7. Owner reviews the suggestions as today.

**Business Rules:**
- Rule 1: A MOC is eligible when it is a MOC in the discovery cache, is still
  present in the vault when the context is built, and is not tagged
  `MiYo/Tomo/exclude/moc` (compared case-insensitively, with or without a
  leading `#`).
- Rule 2: A name carries a path only when its title collides with another
  eligible MOC's title; when exactly one of the colliding MOCs lies inside the
  configured MOC folders, that one stays bare.
- Rule 3: Placement detail is complete per MOC at today's caps; it is never
  reduced because of the number of MOCs.
- Rule 4: Classification MOCs are delivered by name, may be nominated and
  become unticked candidates as today, and are never pre-checked; the
  Classification Guard behaves as today.
- Rule 5: The safety net compares normalised names for equality only (the
  proposal-grouping key: case, whitespace, punctuation, English plural, MOC
  suffix); it never merges by similarity.
- Rule 6: Every Tomo–Hashi channel keeps its shape; only which MOCs appear in
  `candidate_mocs` may differ.

**Edge Cases:**
- Vault with zero eligible MOCs → names list is empty; every item may propose a
  new MOC; no detail is read.
- Item matches many MOCs → up to three candidates per thread, as today; at
  most twenty nominations per item.
- Item split into five threads → each thread may nominate its own MOCs; detail is
  obtained for the union.
- German item, English MOC titles → chosen by meaning; no translation rule.
- A context built before this spec (old shape) is read → the item fails with an
  issue naming the cause. This cannot occur within a run, because every run
  rebuilds the context before analysis. *(Amended 2026-10-24.)*
- Pass 2 runs after a Pass 1 whose context build failed → no context file
  exists; tracker syntax falls back to defaults, exactly as today when the
  file is missing.
- A nominated name does not resolve (mistyped by the analysis) → the name is
  dropped and logged; other candidates are unaffected. Names and detail come
  from the same per-run file, so a rename between build and analysis cannot
  occur within a run.

## Success Metrics

### Key Performance Indicators

- **Adoption:** 100% of `/inbox` runs on both paths use the new shape (no
  configuration switch).
- **Engagement:** Unchanged by design; the owner's workflow does not change.
- **Quality:**
  - On the same inbox before and after, candidate agreement is at least
    min(90%, the agreement between the two before-runs). Agreement is the share
    of before-run candidate MOC paths — the per-item union over all of the
    item's actions — that also appear in the after-run's union for that item.
    Every difference is listed in the close-out with a reason.
  - Zero "Proposed MOC" entries whose normalised name equals an eligible
    existing MOC title, in the after-run.
  - Zero MOC reads delivered as a preview in the after-run's analyses,
    measured by a transcript scanner built for this spec.
  - Every nominated non-classification MOC with headings in the vault carries its
    headings to the analysis, at 65 and at 512 MOCs.
- **Business Impact:** Per-item Phase-B cost does not rise above the
  2026-10-13 baseline ($0.603/item, 120k cache-write tokens/item); target at
  least 10% fewer cache-write tokens per item at today's vault size.

### How each criterion is verified

| Method | Criteria |
|---|---|
| Deterministic test (scripts) | F1-AC2…AC7, F2-AC2, F2-AC5 (reader side), F4-AC1…AC4, F5-AC1…AC3, F6-AC2, F6-AC3, S1-AC1, C1-AC1 |
| Prose contract test (runtime instructions say it) | F2-AC1, F2-AC3, F2-AC4, F2-AC5 (analysis side), F3-AC2, F3-AC3, F6-AC1, S1-AC2 |
| Live run on the test instance (transcripts and results) | F1-AC1, F3-AC1 (a seeded inbox item whose obvious proposal is an existing MOC's name), plus every KPI |
| Document review | S2-AC1, S2-AC2 |

Prose contract tests prove that the instructions say the right thing, not that
the language model obeys them; the live run is the evidence for behaviour.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Context build summary | eligible MOC count, excluded MOC count, title collisions, name-list bytes, full-detail bytes | Shows growth and exclusions per run (C1) |
| Analysis MOC reads (transcript scanner over the analyst subagent transcripts) | bytes per read, delivered whole or as preview | Proves the no-preview metric |
| Safety-net conversions | count of proposals converted, names | Proves the zero-duplicate metric and shows how often the analysis missed |
| Phase-B cost per item | cache-write, cache-read tokens, $ per item, run id | Cost KPI, recorded in the inbox cost log |
| Candidate comparison | per item: before candidates, after candidates, differences | Quality KPI, recorded in the close-out |

---

## Constraints and Assumptions

### Constraints

- **Proposal-first is unchanged.** Tomo writes only to the inbox; every link and
  every new MOC remains the owner's decision.
- **The analysis runs as one subagent per item and cannot dispatch others.** Any
  selection the analysis needs must happen inside its own reads.
- **A single tool result is delivered whole only up to ~37.7 KB** (smallest
  observed spill). Every read this spec introduces must stay below it at 512
  MOCs.
- **Analysts write only to their own items directory.** Anything built for all
  items is built before analysis starts.
- **Tomo–Hashi channels (ADR-029 C1–C10): no shape change.** C3
  (`_suggestions.json`) and C4 (rendered suggestions) carry the same fields;
  only the set of MOCs in `candidate_mocs` and the set of proposed MOCs may
  differ, which is what a better or worse analysis already changes today. The
  other channels are not touched. No Kokoro or Hashi handoff is required.
- **The inbox context is internal, not a published wire** (spec 035); changing
  its shape needs no wire version.
- **Supersedes spec 021 ADR-13 B-moc for inbox link candidates.** B-moc kept
  `exclude/moc` MOCs in the link-candidate pool; for inbox analysis they are now
  excluded. The `/moc-propose` audit-only behaviour of the tag is unchanged.
- **Privacy (Constitution L1):** the surface that reaches the model shrinks; the
  privacy notes must describe the new surface (S2).

### Assumptions

- In LYT and MiYo vaults nearly all MOCs live in the configured MOC folders, so
  title collisions are rare (owner statement, 2026-10-23; not measured across
  vaults).
- A MOC's title is enough for the analysis to judge relevance by meaning. Every
  zero-overlap pick in the replay is explained by the title; topics added
  nothing measurable. Not proven for a title-only list; the before/after run
  tests it.
- The archived analyst transcripts are representative of real inboxes (105
  complete analyses, 54 picks).
- The analysis follows an explicit instruction to check proposed names against
  the list; Feature 4 covers the case where it does not.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| With names only, the analysis chooses fewer or worse MOCs than with topics in view | High | Medium | Before/after run on the same inbox with the min(90%, before-run agreement) candidate-agreement bar; differences reviewed in the close-out |
| The analysis skips the existing-name check and proposes a duplicate | Medium | Medium | Feature 4 safety net catches every exact normalised match |
| A near-duplicate proposal ("Urlaub" vs "Vacation (MOC)") passes the safety net | Medium | Medium | Feature 3 instruction is the primary guard; the safety net is equality-only by design to avoid wrong merges; the owner still decides |
| Reading detail adds a step per item and raises cost | Low | Medium | Detail is read only for nominated MOCs (~514 B per MOC entry, typically 3–6 per item); cost KPI requires no increase |
| The name list itself outgrows a whole read in a very large vault | Medium | Low | Titles cost ~18.5 B per MOC (~9.5 KB at 512 with typical titles); the build warns when the list would exceed the per-read limit; a test checks 512 |
| Excluding `exclude/moc` MOCs removes a link target the owner relied on | Low | Low | The owner set the tag deliberately; documented in S2 |
| Downstream consumers relied on every MOC appearing in candidates | Low | Low | Research found none: no script re-reads the MOC list or checks candidates against it |

## Open Questions

- [x] Does the before-run's candidate set differ from run to run by itself
  (language-model variance)? *Resolved 2026-10-24:* two before-runs are taken
  (plan T1.2) and the agreement bar is min(90%, their mutual agreement) — see
  KPIs. Only the measured value itself is still to come.

---

## Supporting Research

### Competitive Analysis

Not applicable — this is an internal capacity and quality fix. The alternatives
weighed were Tomo's own options from #173: raise the budget (blocked by the
read ceiling), graded trimming (keeps the per-item fan-out cost), and a
structural fix (chosen).

### User Research

Agent-team research on 2026-10-23, four perspectives:

- **Matching:** replay of 105 complete analyst transcripts (64–65 MOCs each).
  25 of 52 thematic MOC picks had zero word overlap with the item; top-K recall
  by the documented scoring stayed at 0.50 from K=3 to K=30. Misses were
  meaning-based or cross-language (German place names → a travel MOC, a German
  Zettelkasten note → "Linking Your Thinking (MOC)"). Only the per-item analyst
  reads the MOC list; the other agents read their own cache or nothing.
- **Technical:** the analysis runs as one subagent per item and receives one
  shared context; nothing in the earlier phase reads item bodies. kado-graph
  offers single-note link walks only.
- **Performance:** measured sizes, the 37.7 KB read ceiling, and a token cost of
  ~257 tokens per MOC entry at full detail (~2 bytes per token).
- **Integration:** no consumer after the analysis re-reads the MOC list; the
  inbox context is internal; channel shapes are unchanged; documentation and
  privacy notes that describe the current shape were listed.

### Market Data

Measured sizes on the test instance (65 MOCs): full MOC entry — what a
detail read returns per MOC — 514 B average (headings, callouts and footer
account for ~153 B of it); title only ~18.5 B.
Name list at 512 MOCs ≈ 9.5 KB. Per-item MOC cost at full detail ≈ 14.7k
tokens today.
