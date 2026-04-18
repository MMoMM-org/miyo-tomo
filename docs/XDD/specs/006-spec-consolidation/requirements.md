---
title: "Spec Consolidation — Merge docs/specs/ into docs/XDD/"
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
A single, reconciled documentation system where Tomo's specs accurately reflect what was built, reference Kokoro for architectural authority, and surface all open work in an actionable backlog.

### Problem Statement
Tomo has two parallel documentation systems that have drifted apart during 5 phases of implementation:

1. **docs/specs/** contains 32 tier-based architecture docs (Tier 1-3) — all marked "Draft" despite implementation being complete. These originated from Kokoro and describe the intended design.
2. **docs/XDD/** contains 5 implementation specs (001-005) — tracking what was actually built, with PRDs, SDDs, and plans.

The drift is concrete:
- XDD 004 (fan-out refactor) changed the agent architecture from 4 agents to an orchestrator + per-item subagent model — but tier specs still describe the old monolithic design.
- XDD 005 (daily-note extension) added 3 classification dimensions and tracker semantics — not reflected in tier specs.
- Some Tier-3 specs (instruction-set-apply, instruction-set-cleanup) are skeletal placeholders with no substantive content.
- XDD 001-003 explicitly skip PRD/SDD, referencing tier specs that haven't been updated.
- There is no index showing what's specced vs built vs still open.

**Consequence**: A developer (human or AI) consulting these docs gets an inaccurate picture of the system. The tier specs describe a system that no longer exists in its original form, while the XDD specs assume familiarity with tier specs that may be stale.

### Value Proposition
After consolidation:
- One place to understand Tomo's current architecture and implementation state.
- Kokoro remains the architectural authority; Tomo's XDD explicitly documents deviations.
- Skeletal specs are fleshed out from the working code — no more placeholders.
- An open-items backlog captures post-MVP features, parking lot items, and documentation debt in one actionable list.
- Future XDD specs (007+) can reference consolidated docs with confidence.

## User Personas

### Primary Persona: AI Session (Claude in Docker)
- **Demographics:** Claude Code instance running inside Tomo's Docker container, loaded with CLAUDE.md + agent/skill definitions, has access to Kado MCP for vault operations.
- **Goals:** Understand Tomo's architecture and capabilities quickly to execute user commands (/inbox, /explore-vault, /tomo-setup). Needs accurate specs to make correct implementation decisions when extending features.
- **Pain Points:** Consults tier specs that describe outdated agent structure. Follows specification instructions that don't match the actual script pipeline. Wastes context window loading specs that contradict each other.

### Secondary Personas

#### Marcus (Project Owner)
- **Demographics:** Solo developer, senior engineer, owns all MiYo repos. Works across Kokoro, Kouzou, Kado, Tomo, and Seigyo.
- **Goals:** Quickly orient at the start of each session. Know what's done, what's open, what's next. Make architectural decisions with accurate context.
- **Pain Points:** Has to mentally reconcile two doc systems. Can't point a new Claude session at "the docs" and trust they're accurate. Post-MVP work items are scattered across spec parking lots and memory files rather than in one backlog.

## User Journey Maps

### Primary User Journey: New Session Orientation
1. **Awareness:** Claude session starts, loads CLAUDE.md which references `docs/specs/` architecture.
2. **Consideration:** Agent needs to understand inbox workflow — reads tier-2/workflows/inbox-processing.md which describes 4-agent model (outdated).
3. **Adoption:** Agent also finds XDD 004 which describes the fan-out refactor — now has conflicting information.
4. **Usage:** Agent must spend tokens reconciling old and new specs, or worse, follows the wrong one.
5. **Retention:** After consolidation, CLAUDE.md points to XDD as the single reference. Tier specs are archived with clear "superseded by" markers.

### Secondary User Journeys

#### Feature Extension Journey
1. Marcus wants to add a new inbox action type (e.g., "create reading list").
2. Consults specs to understand the action schema and extension points.
3. **Before consolidation:** Finds the action schema in tier-3/inbox/ (incomplete) and XDD 004 solution.md (polymorphic actions[] design). Must cross-reference.
4. **After consolidation:** Finds the authoritative action schema in one place within XDD, with a clear link to Kokoro's architectural rationale.

## Feature Requirements

### Must Have Features

#### Feature 1: Spec Migration
- **User Story:** As a documentation consumer, I want all Tomo specs in one location (docs/XDD/) so that I don't have to search two directory trees.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given 32 tier-based specs exist in docs/specs/, When migration is complete, Then every spec is either migrated to docs/XDD/ or archived with a "superseded by" marker
  - [x] Given a migrated spec, When it references Kokoro architecture, Then the reference uses an explicit cross-repo pointer (path or description) rather than duplicating content
  - [x] Given the docs/specs/ directory after migration, When a user reads it, Then a top-level README explains that specs have moved and where to find them

#### Feature 2: Spec Reconciliation
- **User Story:** As a documentation consumer, I want specs to reflect what was actually built so that I can trust the documentation.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given the fan-out refactor (XDD 004) changed the agent architecture, When reconciliation is complete, Then the inbox workflow spec describes the orchestrator + per-item subagent model (not the old 4-agent monolithic model)
  - [x] Given the daily-note extension (XDD 005) added tracker semantics, When reconciliation is complete, Then the daily-note spec includes the 3 classification dimensions and tracker config
  - [x] Given a tier spec that was implemented differently than specified, When reconciliation is complete, Then the spec documents both the original intent (with Kokoro reference) and the actual implementation, noting the deviation reason

#### Feature 3: Placeholder Spec Completion
- **User Story:** As a documentation consumer, I want all specs to have substantive content so that I can understand every part of the system.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given skeletal Tier-3 specs (instruction-set-apply, instruction-set-cleanup), When completion is done, Then each has content reverse-engineered from the working code (scripts, agents, commands)
  - [x] Given a fleshed-out spec, When reviewed, Then it accurately describes the current behavior (verified against the codebase)

#### Feature 4: Open-Items Backlog
- **User Story:** As the project owner, I want a single actionable list of everything that's still open so that I can prioritize future work.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given post-MVP features scattered across tier-spec parking lots, When the backlog is produced, Then every post-MVP item is captured with its source reference
  - [x] Given documentation debt (skeletal specs, missing cross-references), When the backlog is produced, Then doc-debt items are categorized separately from feature work
  - [x] Given the backlog, When a user reads it, Then each item has: description, source (which spec/decision), category (feature/doc-debt/bug), and rough priority (must/should/could)

#### Feature 5: XDD Index
- **User Story:** As a documentation consumer, I want a top-level docs/XDD/README.md that indexes all specs so that I can navigate the documentation.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given all specs (001-006+), When the index is created, Then it lists each spec with: ID, name, phase, document status
  - [x] Given the index, When a new spec is added, Then the format supports easy addition of new rows

### Should Have Features

#### Deviation Registry
- **User Story:** As a documentation consumer, I want a summary of where Tomo's implementation deviates from Kokoro's architecture so that I understand the delta.
- **Acceptance Criteria:**
  - [x] Given implementation deviations exist, When the registry is created, Then each entry has: spec reference, Kokoro reference, what changed, why

#### Cross-Reference Validation
- **User Story:** As the project owner, I want all spec cross-references verified so that no link points to a moved or deleted document.
- **Acceptance Criteria:**
  - [x] Given cross-references in all specs, When validation runs, Then broken references are identified and fixed or flagged

### Could Have Features

#### Spec Status Normalization
- Normalize all spec statuses from "Draft" to appropriate values (Implemented, Superseded, Active) based on actual state.

#### Kokoro Sync Handoff
- Create an outbox handoff to Kokoro with a summary of architectural deviations, so Kokoro's architecture docs can be updated if desired.

### Won't Have (This Phase)

- **Rewriting Kokoro's architecture docs** — Kokoro is a separate repo with its own governance. Tomo documents deviations but doesn't modify the source.
- **Automated spec-to-code drift detection** — Useful but out of scope. This is a one-time consolidation.
- **New feature specs** — This PRD covers consolidation only. New features get their own XDD specs (007+).
- **Test suite changes** — Consolidation is documentation-only; no code changes.

## Detailed Feature Specifications

### Feature: Spec Migration (Most Complex)
**Description:** Move 32 tier-based specs from docs/specs/ into docs/XDD/ while preserving the tier hierarchy as organizational metadata, establishing Kokoro as the architectural authority, and leaving a redirect in the old location.

**User Flow:**
1. Inventory all 32 specs and classify each as: migrate (still relevant), archive (superseded by XDD), or reference-only (Kokoro owns this).
2. For "migrate" specs: copy to appropriate location within docs/XDD/, add metadata header noting origin and Kokoro reference.
3. For "archive" specs: add "superseded by XDD-NNN" header, move to docs/XDD/archive/ or annotate in place.
4. For "reference-only" specs: replace content with a pointer to Kokoro's authoritative version.
5. Create docs/specs/README.md redirect explaining the migration.
6. Update CLAUDE.md references to point to new locations.

**Business Rules:**
- Rule 1: Kokoro is the architectural authority. When a tier spec and implementation disagree, document both and note the deviation.
- Rule 2: No content duplication. If Kokoro owns the concept, reference it; don't copy it into XDD.
- Rule 3: Migrated specs must be updated to reflect current implementation before being marked as migrated.
- Rule 4: The tier hierarchy (1/2/3) becomes metadata tags, not directory structure — XDD uses flat spec IDs.

**Edge Cases:**
- Spec references another spec that was archived → Update reference to point to the archive or the superseding XDD spec.
- Spec has no implementation (post-MVP concept) → Migrate as-is, flag in open-items backlog.
- Spec is partially implemented → Document what's done and what's open.

## Success Metrics

### Key Performance Indicators
- **Completeness:** 100% of tier specs classified (migrate/archive/reference) and processed.
- **Accuracy:** 0 specs contain descriptions that contradict the actual codebase.
- **Backlog coverage:** Every post-MVP item from tier specs appears in the open-items backlog.
- **Reference integrity:** 0 broken cross-references remain after consolidation.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| spec_classified | spec_path, classification (migrate/archive/reference) | Track migration progress |
| spec_reconciled | spec_path, deviations_found, deviations_resolved | Measure drift remediation |
| backlog_item_created | source_spec, category (feature/doc-debt/bug), priority | Track backlog completeness |
| cross_reference_checked | source, target, status (valid/broken/fixed) | Measure reference integrity |

---

## Constraints and Assumptions

### Constraints
- **Kokoro is read-only:** Tomo cannot modify Kokoro's architecture docs. Deviations are documented in Tomo's XDD only.
- **No code changes:** This is a documentation-only effort. Scripts, agents, and configs are not modified.
- **Single-session scope:** Consolidation should be achievable within a focused work session (or a small number of sessions).
- **Existing XDD specs (001-005) are not restructured:** They remain as-is; consolidation adds to XDD, doesn't reorganize existing specs.

### Assumptions
- The current codebase (scripts, agents, commands) accurately represents the "as-built" state.
- Kokoro's tier-1 architecture spec (`pkm-intelligence-architecture.md`) remains the authoritative architectural reference.
- XDD 004 and 005 solution.md documents accurately describe the deviations they introduced.
- The open-items backlog will be maintained as a living document after initial creation.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Missed spec during migration | Medium | Low | Automated inventory (already done by research agents) ensures completeness |
| Incorrectly marking a spec as "superseded" when it's still authoritative | High | Medium | Cross-reference with Kokoro before archiving; use "reference-only" classification for ambiguous cases |
| Open-items backlog becomes stale immediately | Medium | Medium | Include backlog maintenance as a Could Have feature; reference from CLAUDE.md |
| Consolidation creates merge conflicts on feat/inbox-handling-and-specs branch | Low | Low | Work on a dedicated branch; docs-only changes have minimal conflict risk |
| Fleshing out placeholders from code produces specs that diverge from Kokoro intent | Medium | Medium | Always note "reverse-engineered from implementation" and include Kokoro reference for original intent |

## Open Questions

- (none — all key decisions resolved during brainstorm)

---

## Supporting Research

### Competitive Analysis
Not applicable — this is an internal documentation consolidation, not a market-facing feature.

### User Research
Based on 5 phases of development experience:
- AI sessions consistently struggle with dual documentation (observed in XDD 004-005 where tier specs were explicitly skipped in favor of direct implementation).
- Marcus identified this consolidation need after spec 005 review (2026-04-17), recorded as memory item "Spec consolidation planned as XDD 006."

### Market Data
Not applicable — internal tooling initiative.
