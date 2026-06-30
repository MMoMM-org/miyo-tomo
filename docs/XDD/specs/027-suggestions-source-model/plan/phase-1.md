---
title: "Phase 1: Internal keep_origin→keep_source rename"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Internal keep_origin→keep_source rename

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-5]` — internal rename, non-breaking
- `[ref: PRD/Feature 1; terminology unification]`

**Key Decisions**:
- ADR-5: mechanical, repo-wide rename of the internal `keep_origin` concept to `keep_source`.
  No wire/schema change here (that is Phase 4) — this is the parser/reducer/render/diff field +
  the tag-handler group plumbing only.

**Dependencies**:
- None — foundation phase. Must land before Phase 2 (UX block uses `keep_source`).

---

## Tasks

Establishes the unified internal `keep_source` field across the Pass-1→Pass-2 pipeline so later
phases build on one consistent name. Non-breaking: behavior is identical, only the field/symbol
names change.

- [ ] **T1.1 Repo-wide footprint sweep & triage** `[activity: analysis]`

  1. Prime: Re-read the SDD component table `[ref: SDD/Building Block View]`.
  2. Test: N/A (discovery) — produce the authoritative hit list.
  3. Implement: `rg -n "keep_origin" tomo/ tests/` and `rg -n "Keep origin" tomo/` ; classify each
     hit as (rename-symbol) vs (Phase-2 user-facing label) vs (Phase-4 wire). Record the list in
     the phase notes so nothing is missed.
  4. Validate: every `keep_origin` occurrence is assigned to a task; no orphan hits.
  5. Success: complete triage list covering `suggestion-parser.py`, `suggestions-reducer.py`,
     `instruction-render.py`, `instructions-diff.py`, tests `[ref: SDD/Building Block View]`.

- [ ] **T1.2 Rename the parser field keep_origin→keep_source** `[activity: backend]`

  1. Prime: Read `suggestion-parser.py` keep_origin paths `[ref: SDD/Code Context; suggestion-parser.py]`.
  2. Test (red): update/extend parser tests to assert the confirmed item exposes `keep_source`
     (bool) and that the tag-handler group records carry `keep_source`; include a checked AND an
     unchecked case `[ref: PRD/F1]`.
  3. Implement (green): rename `keep_origin`→`keep_source` at the result dict (~341), checkbox
     branch (~410-411), and `parse_tag_handler_keep_origin`/`current_keep_origin` plumbing
     (~1440-1530). Keep the user-facing label parsing tolerant (Phase 2 changes the label text).
  4. Validate: parser tests pass; lint clean.
  5. Success: no `keep_origin` symbol remains in `suggestion-parser.py` `[ref: SDD/ADR-5]`.

- [ ] **T1.3 Rename render/diff plumbing keep_origin→keep_source** `[activity: backend]`

  1. Prime: Read `instruction-render.py` keep_origin plumbing + `instructions-diff.py`
     `[ref: SDD/Code Context]`.
  2. Test (red): update `_build_delete_source_actions` tests so suppression reads `keep_source`
     (keep-path AND delete-path) `[ref: PRD/F2]`; update `instructions-diff` keep-suppression test.
  3. Implement (green): rename `keep_origin_stems` (~1008), `keep_origin_group_ids` params/args
     (~983, 1312, 1347, 2400, 2579), and the `instructions-diff.py` consumer (~297) +
     `tag_handler_keep_origin_group_ids` reads. Behavior unchanged.
  4. Validate: full `instruction-render` + `instructions-diff` suites pass; lint clean.
  5. Success: no `keep_origin` symbol remains in `instruction-render.py`/`instructions-diff.py`;
     suppression behavior identical `[ref: SDD/ADR-5]`.

- [ ] **T1.4 Bump versions + docs/tomo counterparts** `[activity: backend]` `[parallel: true]`

  1. Prime: Recall the version-gated sync rule (managed scripts need a `# version:` bump).
  2. Test: N/A.
  3. Implement: bump `# version:` on every edited managed script; update the `docs/tomo/scripts/*`
     WHY counterparts for the renamed field where they mention `keep_origin`.
  4. Validate: `grep` confirms bumped versions; counterpart docs reference `keep_source`.
  5. Success: edited managed scripts carry a new `# version:` `[ref: SDD/CON-5]`.

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Run the full suite (`./venv/bin/python -m pytest tests/ -q`). Confirm green (≥ baseline 1782).
    Confirm zero `keep_origin` symbols remain in code (user-facing labels deferred to Phase 2,
    wire field deferred to Phase 4). Lint clean.
