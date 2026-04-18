---
title: "Phase 1: Structure + Migration"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Structure + Migration

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — Directory Map]`
- `[ref: SDD/Runtime View — Steps 2-3]`
- `[ref: PRD/Feature 1 — Spec Migration]`

**Key Decisions**:
- ADR-1: Reference docs folder with preserved tier hierarchy
- Use `git mv` to preserve file history

**Dependencies**:
- None — this is the first phase

---

## Tasks

Establishes the target directory structure and physically migrates all 32 tier specs from `docs/specs/` to `docs/XDD/reference/`.

- [x] **T1.1 Create reference directory structure** `[activity: docs-scaffolding]`

  1. Prime: Read SDD Directory Map for target structure `[ref: SDD/Building Block View — Directory Map]`
  2. Test: Verify `docs/XDD/reference/` does not already exist; verify `docs/specs/` has all 32 expected files
  3. Implement: Create directory tree:
     ```
     docs/XDD/reference/
     ├── tier-1/
     ├── tier-2/
     │   ├── components/
     │   └── workflows/
     └── tier-3/
         ├── config/
         ├── discovery/
         ├── daily-note/
         ├── inbox/
         ├── lyt-moc/
         ├── profiles/
         ├── templates/
         ├── vault-exploration/
         └── wizard/
     ```
  4. Validate: All directories exist; structure matches SDD
  5. Success: Reference directory tree matches SDD specification `[ref: PRD/AC — Feature 1]`

- [x] **T1.2 Migrate Tier 1 spec** `[activity: docs-migration]`

  1. Prime: Read `docs/specs/tier-1/pkm-intelligence-architecture.md`
  2. Test: Verify file exists at source; verify no file at target
  3. Implement: `git mv docs/specs/tier-1/pkm-intelligence-architecture.md docs/XDD/reference/tier-1/`
  4. Validate: File exists at target; git status shows rename
  5. Success: Tier 1 architecture spec accessible at `docs/XDD/reference/tier-1/` `[ref: PRD/AC — Feature 1]`

- [x] **T1.3 Migrate Tier 2 specs (6 components + 4 workflows)** `[activity: docs-migration]` `[parallel: true]`

  1. Prime: Read `docs/specs/README.md` for full Tier 2 file list
  2. Test: Verify all 10 Tier 2 files exist at source
  3. Implement: `git mv` each file to corresponding `docs/XDD/reference/tier-2/` path:
     - Components (6): universal-pkm-concepts, framework-profiles, user-config, discovery-cache, template-system, setup-wizard
     - Workflows (4): inbox-processing, daily-note, lyt-moc-linking, vault-exploration
  4. Validate: All 10 files exist at target; none remain at source
  5. Success: All Tier 2 specs migrated with history preserved `[ref: PRD/AC — Feature 1]`

- [x] **T1.4 Migrate Tier 3 specs (~26 files across 9 subdirectories)** `[activity: docs-migration]` `[parallel: true]`

  1. Prime: Inventory all Tier 3 files in `docs/specs/tier-3/`
  2. Test: Count files per subdirectory; verify target dirs are empty
  3. Implement: `git mv` each subdirectory's contents to `docs/XDD/reference/tier-3/`:
     - config/ (4 files), discovery/ (3), daily-note/ (2), inbox/ (5), lyt-moc/ (3), profiles/ (2), templates/ (2), vault-exploration/ (3), wizard/ (2)
  4. Validate: All files at target; source tier-3/ directory is empty
  5. Success: All Tier 3 specs migrated `[ref: PRD/AC — Feature 1]`

- [x] **T1.5 Update internal cross-references** `[activity: docs-editing]`

  1. Prime: Grep migrated specs for relative path references (`../tier-`, `tier-2/`, `tier-3/`)
  2. Test: Identify all cross-references that use old `docs/specs/` paths
  3. Implement: Update all internal references to use new `docs/XDD/reference/` relative paths
  4. Validate: `grep -r "docs/specs/" docs/XDD/reference/` returns no results; `grep -r "../tier-" docs/XDD/reference/` shows only valid relative refs within reference/
  5. Success: Zero broken cross-references within migrated specs `[ref: PRD/AC — Feature 2 (cross-ref)]`

- [x] **T1.6 Phase Validation** `[activity: validate]`

  - All 32 tier specs exist under `docs/XDD/reference/` with correct hierarchy
  - `docs/specs/` contains only README.md (or is empty)
  - Git tracks all moves as renames (check `git status`)
  - No broken cross-references within migrated files
