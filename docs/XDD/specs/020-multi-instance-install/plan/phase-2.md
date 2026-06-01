---
title: "Phase 2: Install multi-instance flow"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Install multi-instance flow

## Phase Context

**GATE**: Read before starting.
- `[ref: solution.md/Key Flows; Install (create new)]`
- `[ref: solution.md/ADR-1]` — layout + default parent `~/MiYo/Tomo/`, create-with-note (OQ8)
- `[ref: solution.md/ADR-2]` — registry upsert + discovery
- `[ref: solution.md/tomo-install.json delta]` — drop `lifecyclePrefix`, add `repoPath`
- Current code: `install-tomo.sh:13,755,788,1222,1270,1289-1311` (config path, re-run prompt, INSTANCE_PATH, HOME_DIR, LAUNCHER_PATH, config write block)

**Key Decisions:** ADR-1, ADR-2, ADR-7 (uses `render-launcher.sh` from Phase 1).

**Dependencies:** Phase 1 (registry + render-launcher libs).

---

## Tasks

Rewires `install-tomo.sh` from single-config to a registry-backed, per-instance layout. (Tag-prefix removal happens in Phase 4 to keep Part A and Part B reviewable separately — Phase 2 leaves the prefix step untouched.)

- [x] **T2.1 Instance-selection front-end (list / create-new / update-existing)** `[activity: backend-api]`
  1. Prime: Read the install flow + ADR-2 `[ref: solution.md/Key Flows]`.
  2. Test (RED): isolated `HOME`/tmpdir + isolation flags:
     - No registry → install proceeds as first-instance create (happy) `[ref: PRD/F2-AC4]`.
     - One registered instance → re-run lists it and offers create-new vs update-`<name>` (replaces the `Use existing config? [Y/n]` at `:755`) `[ref: PRD/F2-AC2]`.
     - Duplicate name on create → rejected/re-prompted (interactive) / non-zero (non-interactive) `[ref: solution.md/Error Handling]`.
  3. Implement (GREEN): source `instance-registry.sh`; replace the `:755` single-config branch with registry-driven listing + a create/update choice.
  4. Validate: `bash -n`; tests pass.
  5. Success: re-run discovers existing instances and routes correctly `[ref: PRD/F2-AC2]`.

- [x] **T2.2 Per-instance path layout + parent prompt** `[activity: backend-api]`
  1. Prime: ADR-1 layout `[ref: solution.md/ADR-1]`.
  2. Test (RED):
     - Create-new produces `<parent>/<name>/{instance/, home/, tomo-install.json, begin-tomo.sh}` with default parent `~/MiYo/Tomo/` (overridable) `[ref: PRD/F1-AC1]`.
     - Default parent absent → created with a printed note (OQ8) `[ref: solution.md/ADR-1]`.
     - Second instance leaves the first's files byte-unchanged `[ref: PRD/F1-AC2]`.
  3. Implement (GREEN): compute `INSTANCE_PATH=<parent>/<name>/instance`, `HOME_DIR=<parent>/<name>/home`, `CONFIG_FILE=<parent>/<name>/tomo-install.json`, `LAUNCHER_PATH=<parent>/<name>/begin-tomo.sh`; prompt parent (default `~/MiYo/Tomo/`).
  4. Validate: `bash -n`; tests pass; manual: no writes outside the instance dir.
  5. Success: self-contained layout; no cross-instance clobbering `[ref: PRD/F1-AC1, F1-AC2, F1-AC3]`.

- [x] **T2.3 Per-instance config write + registry upsert + launcher render** `[activity: backend-api]`
  1. Prime: config delta + render-launcher `[ref: solution.md/tomo-install.json delta; ADR-7]`.
  2. Test (RED):
     - `tomo-install.json` written into the instance dir includes `repoPath` and `tomoVersion`; (still includes `lifecyclePrefix` until Phase 4 — assert it's the ONLY remaining tag-prefix reference) `[ref: PRD/F1-AC1]`.
     - `render-launcher.sh` produces the instance launcher with no unrendered `{{...}}` `[ref: solution.md/ADR-7]`.
     - `registry_upsert` records the new instance `[ref: PRD/F2-AC1]`.
  3. Implement (GREEN): point the config-write block (`:1289`) at the per-instance `CONFIG_FILE`, add `repoPath`; call `render_launcher`; call `registry_upsert`.
  4. Validate: `bash -n`; tests pass; bump `install-tomo.sh` `# version:`.
  5. Success: a created instance is self-describing (config + launcher) and registered `[ref: PRD/F1, F2-AC1]`.

- [x] **T2.4 Phase Validation** `[activity: validate]`
  - Full install-flow tests via isolated tmpdirs (never `$REPO_ROOT/tomo-instance`); `bash -n`; ruff. Two-instance isolation test green.
