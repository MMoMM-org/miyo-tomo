---
title: "Knowledge-Garden Audit Skill (/garden-audit)"
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

Turn Tomo from an inbox processor into a proactive vault-health assistant: one command
(`/garden-audit`) scans the whole Obsidian vault, surfaces every structural problem in a
prioritised review document, and lets the user apply the fixable ones through the same
review-and-approve flow they already use for inbox suggestions.

### Problem Statement

A personal knowledge vault silently accumulates structural rot that no single-note workflow
catches: notes that were never filed under a MOC (`up::` missing), notes fully disconnected from
the graph (no links at all), `up::` relations pointing at MOCs that were renamed or deleted,
`[[wikilinks]]` whose targets no longer exist, duplicate filenames that Obsidian silently
disambiguates, and MOCs that have gone stale. Today Tomo only reasons about *incoming* items in
the inbox — it has no way to reason about the *existing* vault as a whole. The user has no
periodic, trustworthy signal of where the garden needs weeding, and fixing these by hand means
manually hunting the whole vault. The consequences compound: broken navigation, notes that can
never be found again, and a graph that degrades faster than a human notices.

### Value Proposition

`/garden-audit` gives the user a single, prioritised, trustworthy snapshot of vault health and —
for the problems that have a deterministic fix — turns that snapshot into approvable actions that
apply through the existing 2-pass / Hashi machinery. It reuses everything already shipped
(discovery cache, `orphan_link.py` scoring, `instruction-render`, the ADR-026 wire, the shipped
`kado-graph-audit` Kado tool), so it adds a whole new capability with almost no new apply
surface. Unlike a raw Obsidian graph view or a dataview query, it *ranks by severity* and *offers
the fix*, not just the diagnosis.

## User Personas

### Primary Persona: Marcus — vault owner / PKM practitioner

- **Demographics:** Single power user (pre-launch test scope is the personal MiYo vault), high
  technical expertise, runs Tomo in a Docker container against his own Obsidian vault via Kado.
- **Goals:** Keep the knowledge garden navigable and connected; periodically weed structural rot
  without hand-auditing hundreds of notes; fix what's fixable with one review pass, not N manual
  edits.
- **Pain Points:** No whole-vault health signal exists today; structural problems are invisible
  until navigation breaks; manual auditing is tedious and easy to skip; a raw graph view diagnoses
  but never proposes a fix.

### Secondary Personas

None for v1. Test scope is the personal vault pre-launch (per project QA scope). The design does
not assume a multi-user model; broader personas are out of scope until Tomo ships publicly.

## User Journey Maps

### Primary User Journey: Run an audit and weed the garden

1. **Awareness:** The user senses the vault has drifted (dead links, unfiled notes) or simply
   wants a periodic health check.
2. **Consideration:** The alternative is a manual sweep (Obsidian graph view, dataview queries,
   scrolling folders) — diagnostic-only, no fixes, easy to abandon.
3. **Adoption:** The user runs `/garden-audit`. One command, whole vault, no configuration.
4. **Usage:** Tomo writes a prioritised review report (plus a JSON wire) into the vault inbox. The
   user reviews it in Obsidian: integrity breaks first, then structure gaps, then advisory flags.
   For fixable findings the user ticks the fixes they want (a best candidate is pre-selected);
   advisory findings are read-only. The user approves, then runs `/inbox`, and the approved fixes
   apply through Hashi — the same flow as inbox suggestions.
5. **Retention:** Because the audit is cheap (one bulk graph call, cache reads) and reuses the
   familiar review surface, the user runs it periodically instead of letting rot accumulate.

### Secondary User Journeys

**Healthy-vault run:** The user runs `/garden-audit` and the report says the garden is healthy
(zero findings) — a positive confirmation, not an empty file. This keeps the audit worth running
even when nothing is wrong.

## Feature Requirements

### Must Have Features

The six checks, the two-artifact output, the reuse-the-2-pass apply path for fixable findings, and
the honest caveats. The check taxonomy uses Tomo's settled terminology: **orphan** = a note with
no links at all; **unparented** = a note with links but no `up::` parent.

#### Feature 1: Whole-vault structural scan (six checks)

- **User Story:** As the vault owner, I want one command to scan the whole vault for structural
  problems so that I get a complete health picture without hand-auditing every note.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a note has links but no `up::` marker, When `/garden-audit` runs, Then it is
    reported as an **unparented** finding with up to 3 candidate MOCs to file it under (or a
    create-new-MOC option when none is a good match).
  - [ ] Given a note has zero resolved links in and out, When `/garden-audit` runs, Then it is
    reported as an **orphan** finding.
  - [ ] Given a note's `up::` targets a MOC that does not exist, When `/garden-audit` runs, Then it
    is reported as a **broken `up::`** finding offering to repoint it to a valid MOC.
  - [ ] Given a note contains a `[[wikilink]]` whose target does not resolve, When `/garden-audit`
    runs, Then it is reported as a **dead wikilink** finding naming the source note, the unresolved
    target text, and its occurrence count.
  - [ ] Given two or more notes share a filename stem, When `/garden-audit` runs, Then they are
    reported together as a **duplicate-stems** advisory finding.
  - [ ] Given a MOC has not been modified within the stale threshold, When `/garden-audit` runs,
    Then it is reported as a **stale-MOC** advisory finding.

#### Feature 2: Prioritised review report + JSON wire (two artifacts)

- **User Story:** As the vault owner, I want the findings in a single prioritised document I can
  review in Obsidian, backed by a structured wire, so that I can act on the worst problems first
  and so a future Hashi editor can drive the same data.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a completed scan, When the report is written, Then findings are ordered by severity
    tier: integrity breaks (broken `up::`, dead wikilinks) → structure gaps (unparented, orphan) →
    advisory (stale MOC, duplicate stems).
  - [ ] Given a completed scan, When output is produced, Then Tomo emits both a markdown review
    report AND a schema-valid JSON wire (ADR-026) that is a complete structured mirror of the
    review surface.
  - [ ] Given the report is written to the vault inbox, When the user opens it, Then a Summary
    section shows per-tier counts and the report carries the standing caveats (index-lag,
    ACL-scope) near the top.
  - [ ] Given an empty section (no findings of that category), When the report renders, Then that
    section is omitted rather than shown empty.

#### Feature 3: Approve-and-apply for fixable findings (reuse 2-pass)

- **User Story:** As the vault owner, I want to approve the fixes I want and have them applied
  through the flow I already use, so that I don't learn a new apply surface.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given fixable findings (unparented, orphan, broken `up::`, dead wikilink), When the report
    renders, Then each carries a checkbox with a sensible default pre-selected; advisory findings
    (duplicate stems, stale MOC) render read-only with no checkbox.
  - [ ] Given the user approves fixable findings and runs `/inbox`, When triage picks up the
    approved audit, Then the approved fixes render into the existing instruction-set format and
    apply through Hashi — no new apply path.
  - [ ] Given an unparented or orphan finding is approved with a chosen MOC, When it applies, Then
    both the MOC-side child bullet AND the note's own `up::` line are written.
  - [ ] Given a fix has no shipped Hashi action yet (dead-wikilink edit, `up::` removal), When the
    wire is emitted, Then the fix intent is still fully encoded in the JSON wire as the contract
    Hashi's editor + new action will be built against (example-driven handoff).

#### Feature 4: Trustworthy, cheap, honest scan

- **User Story:** As the vault owner, I want the audit to be cheap to run and honest about its
  limits so that I run it often and don't over-trust a single snapshot.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a whole-vault scan, When the link graph is needed, Then it is fetched via the bulk
    `kado-graph-audit` tool in O(1) Kado calls (paginated by cursor), not one call per note.
  - [ ] Given the vault has notes outside the audit key's ACL, When the report renders, Then it
    states the audit reports only what the key can see (absent findings ≠ "clean").
  - [ ] Given the Obsidian index may be transiently stale after a restart or large external change,
    When the report renders, Then it carries a note that results reflect the current index and a
    single run is a snapshot, not ground truth.

### Should Have Features

- **Pre-selected best fix.** For unparented/orphan findings, the highest-scoring candidate MOC is
  pre-checked (reusing `orphan_link.py` overlap scoring), so the common case is one-click approve.
- **Overflow disclosure.** When a category is truncated for readability, the report shows the total
  count as a denominator so the user knows coverage (e.g. "N more not shown").

### Could Have Features

None promoted for v1. All nice-to-haves are explicitly parked below to keep this a single release.

### Won't Have (This Phase)

- **Auto-fix for advisory checks** — rename/merge for duplicate stems, archive-move for stale MOCs.
  These need human judgment and new action types; v1 keeps them report-only.
- **Scheduled/periodic invocation** — v1 is on-demand `/garden-audit` only.
- **Per-note `kado-graph` fallback** — YAGNI; the bulk `kado-graph-audit` shipped (Kado v1.2.0).
- **Incremental audit** (`filter.modifiedAfter`, F-48) — separate epic-#16 item.
- **Configurable stale threshold** — start with a hardcoded default (N months); config deferred.
- **Removing a broken `up::` line as a v1 apply action** — v1's fixable path for broken `up::` is
  *repoint to a valid MOC* (a shipped action); *removal* is encoded in the wire but applied only
  once Hashi ships the body-edit action.

## Detailed Feature Specifications

### Feature: `/garden-audit` end-to-end

**Description:** A user-invoked, whole-vault health audit that mirrors the shipped `/moc-propose`
track. It scans via the discovery cache + the bulk `kado-graph-audit` tool + directory
modification times, classifies and prioritises findings, writes a review report and a JSON wire
into the vault inbox, and — on approval via `/inbox` — applies the fixable subset through Hashi.

**User Flow:**
1. User runs `/garden-audit`.
2. System scans the vault (cache reads for unparented/broken-`up::`/duplicate-stems; one bulk
   `kado-graph-audit` call for orphan/dead-wikilink; directory mod-times for stale MOC),
   classifies and prioritises findings, and writes the report + wire to the inbox.
3. User reviews in Obsidian, ticks the fixes to apply (advisory findings are read-only), approves.
4. User runs `/inbox`; approved fixes render into the instruction set and apply via Hashi.

**Business Rules:**
- Rule 1: Fixable checks are 1–4 (unparented, orphan, broken `up::`, dead wikilink); advisory
  checks are 5–6 (duplicate stems, stale MOC) — advisory never emits a Hashi action.
- Rule 2: Findings are severity-ordered: integrity breaks > structure gaps > advisory.
- Rule 3: The JSON wire is a complete mirror of the review surface and encodes fix intent for ALL
  fixable findings, including those whose Hashi action does not exist yet.
- Rule 4: Filing an unparented/orphan note writes both the MOC-side bullet and the note's `up::`.
- Rule 5: Broken `up::` is detected from the discovery cache alone (no graph call needed).

**Edge Cases:**
- Empty vault → Report renders with a "no notes found — is Tomo configured?" line; no wire actions.
- Zero findings → Positive "vault is healthy" completion report; no checkboxes, no actions.
- All-advisory run → Report renders advisory sections; Summary states "no fixable findings";
  the approve/apply affordance is absent so the user cannot tick an empty approval.
- Huge result set → `kado-graph-audit` paginates by cursor; the scan concatenates pages; the
  report shows total counts as the coverage denominator.
- Target outside the key's ACL → silently omitted by Kado; the report states the ACL-scope caveat.
- Index lag → the report carries the "results reflect the current index" caveat.

## Success Metrics

### Key Performance Indicators

This is internal PKM tooling (single pre-launch user), so metrics are correctness/behaviour
outcomes rather than adoption funnels.

- **Adoption:** The audit is run periodically by the vault owner (it is cheap and reuses the
  familiar review surface) rather than abandoned as too heavy.
- **Engagement:** A single run produces a complete, prioritised report + a schema-valid wire, and
  the fixable findings can be approved and applied in one `/inbox` pass.
- **Quality:** Advisory findings never emit a Hashi action; the link graph is fetched in O(1) Kado
  calls (no 429 storms); the report communicates index-lag and ACL-scope so a run is understood as
  a snapshot.
- **Business Impact:** Measurable reduction in vault structural rot over repeated runs (fewer
  orphans/dead links/broken `up::` on a subsequent audit of the same vault).

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Audit run completed | per-tier finding counts, total orphans/deadLinks (metadata only) | Confirm the scan ran and gauge vault-health trend across runs |
| Fixable findings approved + applied | count of applied fixes by check type | Verify the approve-apply path works end-to-end |
| Bulk graph call | page count, cursor pages traversed | Confirm O(1)-per-page behaviour, watch for pagination on large vaults |

_(Tracking is metadata-only per Constitution L2 — never note bodies or heading text.)_

---

## Constraints and Assumptions

### Constraints
- **Local-first + Kado-gated.** All vault access goes through Kado; the audit reports only what the
  audit key's ACL permits (Constitution L1 privacy; default-deny).
- **Metadata-only telemetry** (Constitution L2) — paths, counts, target text; never note bodies.
- **Reuse over rebuild.** v1 must reuse the shipped pipeline (discovery cache, `orphan_link.py`,
  `instruction-render`, the ADR-026 wire) and add no new apply path for the checks that map to
  shipped Hashi actions.
- **Roadmap sequencing.** Garden-audit is roadmap item 2, built after the shipped MOC-creation
  track, with live-vault validation against the personal test vault before merge.

### Assumptions
- The bulk `kado-graph-audit` tool (Kado v1.2.0) is available and returns
  `{ orphans[], deadLinks[], total, cursor, truncated }` as contracted (dependency satisfied).
- The discovery cache is populated and reasonably fresh (the user runs `/explore-vault` when
  needed); the audit reads it and fails gracefully with guidance when it is empty/stale.
- Hashi will build its editor + the new body-edit action against the complete real JSON wire that
  Tomo produces — the wire is the example-driven contract, delivered when Tomo's build is done.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| No shipped Hashi action edits/removes a free-text body `[[link]]` or removes a broken `up::` | Medium | High | Encode the fix intent fully in the JSON wire now; deliver the complete real wire as the example-driven handoff so Hashi builds the editor + new action against a concrete contract, not a spec string. Until then those specific fixes are surfaced but not auto-applied. |
| Index-lag false positives (a note briefly reads as orphaned / a fixed link as still dead) | Low | Medium | Surface the index-lag caveat in every report; treat a single run as a snapshot; no destructive auto-action on advisory findings. |
| Large vault → many `kado-graph-audit` pages | Low | Low | Cursor pagination + inherited 429/backoff in the Kado client; show total-count denominator; overflow disclosure in the report. |
| User over-trusts a run / applies a wrong fix | Medium | Low | Human-in-the-loop review + approval for every fixable finding (2-pass); advisory findings never auto-apply; best-candidate is a default, not a commitment. |

## Open Questions

- [ ] Exact shape of the NEW Hashi body-edit action(s) for dead-wikilink fix and `up::` removal —
  Tomo proposes the wire encoding; final action schema is co-defined with Hashi against the real
  example. (SDD/PLAN, not PRD.)
- [ ] Default stale-MOC threshold value (N months) — pick a sensible default in SDD; config is a
  parked Won't-Have.
- [ ] Whether orphan findings default to "link to best MOC" or "flag only" when no candidate MOC
  clears the overlap threshold — resolve in SDD (reuse `orphan_link.py` create-new vs link-existing
  behaviour).

---

## Supporting Research

### Competitive Analysis

Obsidian-native alternatives (core graph view, the "orphaned files" / "broken links" community
plugins, dataview queries) are **diagnostic-only**: they surface disconnected notes or unresolved
links but do not rank by severity, do not distinguish orphan from unparented, and do not offer an
approve-and-apply fix path. `/garden-audit`'s differentiator is *diagnosis + prioritisation +
approvable fix through the existing review flow*, all inside Tomo's privacy-gated, local-first
model. The `obsidian-ops-team` template was evaluated during the roadmap and rejected (hardcoded
paths, bypasses Kado, conflicts with the 2-pass model).

### User Research

Two research passes this session (Requirements/UX and Integration/Technical) verified the design
against the real codebase and produced the acceptance criteria, edge-case catalogue, and
check→action mapping above. A spec-reviewer pass approved the upstream brainstorm design and
confirmed every reused component exists. Key research findings folded into this PRD: broken `up::`
is cache-only (no graph call); filing a note needs two actions (MOC bullet + `up::` line); the
dead-wikilink and `up::`-removal fixes have no shipped Hashi action, handled example-driven.

### Market Data

Not applicable — internal PKM tooling for a single pre-launch vault. Scope is deliberately the
personal MiYo vault until Tomo ships publicly.
