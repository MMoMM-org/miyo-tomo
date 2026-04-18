---
title: "Phase 4: Index + Backlog + Cleanup"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Index + Backlog + Cleanup

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/File Formats — Master Index Format, Backlog Item Format, Redirect README Format]`
- `[ref: SDD/Runtime View — Steps 6-10]`
- `[ref: PRD/Feature 4 — Open-Items Backlog]`
- `[ref: PRD/Feature 5 — XDD Index]`

**Key Decisions**:
- ADR-2: Standalone backlog at `docs/XDD/backlog.md`
- Master index at `docs/XDD/README.md`
- Redirect at `docs/specs/README.md`

**Dependencies**:
- Phases 1-3 must be complete (all specs migrated, annotated, fleshed out)

---

## Tasks

Creates the navigational index, builds the open-items backlog, retires the old docs/specs/ location, and updates all external references.

- [x] **T4.1 Build open-items backlog** `[activity: docs-analysis]`

  1. Prime: Read all migrated specs in `docs/XDD/reference/` for post-MVP items, parking lot mentions, and TODO markers; read `docs/XDD/specs/004-*/solution.md` and `005-*/solution.md` for deferred items `[ref: SDD/File Formats — Backlog Item Format]`
  2. Test: Collect all post-MVP items, doc-debt references, and known issues from:
     - Tier spec parking lot sections
     - XDD spec "Won't Have" sections
     - Deviation callouts that note future work
     - Memory items referencing open work
  3. Implement: Create `docs/XDD/backlog.md` with three categorized tables:
     - **Features (Post-MVP)**: Periodic notes, Seigyo execution, profile switching, Templater rendering, weekly/monthly notes, automated drift detection, standalone MOC density scan
     - **Documentation Debt**: Any remaining skeletal content, cross-reference gaps, undocumented extension points
     - **Known Issues**: Any documented bugs or limitations
     Each item: ID, description, source reference, priority (Must/Should/Could), notes
  4. Validate: Every post-MVP item from tier specs appears in backlog; no duplicates; source references are valid paths
  5. Success: Backlog captures all open work with source traceability `[ref: PRD/AC — Feature 4]`

- [x] **T4.2 Create XDD master index** `[activity: docs-scaffolding]`

  1. Prime: Read SDD Master Index Format; inventory all specs (001-006) and all reference docs `[ref: SDD/File Formats — Master Index Format]`
  2. Test: Verify all spec directories and reference files exist at expected paths
  3. Implement: Create `docs/XDD/README.md` with:
     - Implementation specs table (ID, Name, Phase, Status) for 001-006
     - Architecture reference sections (Tier 1, Tier 2 Components, Tier 2 Workflows, Tier 3 by subdomain)
     - ⚠️ markers on specs with deviation annotations
     - Kokoro authority note
     - Link to backlog.md
  4. Validate: Every spec and reference file is linked from the index; all links resolve
  5. Success: Complete navigable index of all Tomo documentation `[ref: PRD/AC — Feature 5]`

- [x] **T4.3 Create reference directory README** `[activity: docs-scaffolding]` `[parallel: true]`

  1. Prime: Understand the Kokoro authority model from SDD
  2. Test: Verify `docs/XDD/reference/README.md` does not exist yet
  3. Implement: Create `docs/XDD/reference/README.md` explaining:
     - These are architecture specs migrated from `docs/specs/`
     - Kokoro is the architectural authority
     - Inline deviation callouts document where implementation differs
     - Tier hierarchy explanation (Tier 1 = framework, Tier 2 = components/workflows, Tier 3 = details)
  4. Validate: README accurately describes the reference docs collection
  5. Success: Reference docs are self-documenting `[ref: SDD/Building Block View]`

- [x] **T4.4 Retire docs/specs/ with redirect** `[activity: docs-cleanup]`

  1. Prime: Read SDD Redirect README Format `[ref: SDD/File Formats — Redirect README Format]`
  2. Test: Verify `docs/specs/` is empty except possibly for README.md
  3. Implement: Replace `docs/specs/README.md` with redirect notice pointing to `docs/XDD/README.md`. Remove any empty subdirectories left by git mv.
  4. Validate: `docs/specs/` contains only the redirect README; redirect links are correct
  5. Success: Old location clearly redirects to new location `[ref: PRD/AC — Feature 1]`

- [x] **T4.5 Update CLAUDE.md references** `[activity: docs-editing]`

  1. Prime: Read `CLAUDE.md` for all `docs/specs/` references `[ref: SDD/Acceptance Criteria — CLAUDE.md]`
  2. Test: Grep CLAUDE.md for `docs/specs/` paths
  3. Implement: Update all references to point to `docs/XDD/reference/` equivalent paths. Specifically:
     - Architecture reference: `docs/specs/tier-1/pkm-intelligence-architecture.md` → `docs/XDD/reference/tier-1/pkm-intelligence-architecture.md`
     - Any other tier spec references
  4. Validate: `grep "docs/specs/" CLAUDE.md` returns no results (except the redirect mention if any)
  5. Success: CLAUDE.md points to consolidated documentation `[ref: SDD/Acceptance Criteria — CLAUDE.md]`

- [x] **T4.6 Update XDD spec 001-003 references** `[activity: docs-editing]` `[parallel: true]`

  1. Prime: Read XDD specs 001, 002, 003 README.md files — they reference Kokoro tier specs via `docs/specs/` paths
  2. Test: Grep specs 001-003 for `docs/specs/` paths
  3. Implement: Update references to use `docs/XDD/reference/` paths
  4. Validate: No `docs/specs/` references in XDD specs 001-003
  5. Success: Existing XDD specs reference consolidated location `[ref: SDD/Risks — Technical Debt]`

- [x] **T4.7 Final cross-reference validation** `[activity: validate]`

  1. Prime: All migration, annotation, and cleanup complete
  2. Test: Run comprehensive grep for stale references:
     ```bash
     grep -r "docs/specs/" docs/ CLAUDE.md --include="*.md"
     ```
  3. Implement: Fix any remaining stale references found
  4. Validate: Zero results from stale reference grep (excluding the redirect README itself)
  5. Success: Zero broken cross-references across entire docs/ tree `[ref: PRD/Success Metrics — Reference integrity]`

- [x] **T4.8 Phase Validation (Final)** `[activity: validate]`

  - `docs/XDD/README.md` exists and links all specs + reference docs
  - `docs/XDD/backlog.md` exists with categorized items
  - `docs/XDD/reference/README.md` exists with authority note
  - `docs/specs/README.md` is a redirect notice only
  - CLAUDE.md references `docs/XDD/` not `docs/specs/`
  - `grep -r "docs/specs/" docs/ CLAUDE.md` returns only the redirect README
  - Git status shows clean state (all changes committed)
  - All PRD acceptance criteria met:
    - Feature 1 (Migration): ✅ 32 specs under reference/
    - Feature 2 (Reconciliation): ✅ deviation callouts on drifted specs
    - Feature 3 (Placeholders): ✅ skeletal specs fleshed out
    - Feature 4 (Backlog): ✅ categorized backlog with source refs
    - Feature 5 (Index): ✅ master index with navigation
