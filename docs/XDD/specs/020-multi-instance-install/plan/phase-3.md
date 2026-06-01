---
title: "Phase 3: Per-instance update + launcher identity & update-check"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Per-instance update + launcher identity & update-check

## Phase Context

**GATE**: Read before starting.
- `[ref: solution.md/Key Flows; Update (select instance)]`
- `[ref: solution.md/ADR-3]` — identity: `TOMO_INSTANCE_NAME` env + sanitized `--hostname`
- `[ref: solution.md/ADR-4]` — non-fatal launcher update-availability check + portable semver compare
- Current code: `update-tomo.sh` (single-config read); `begin-tomo.sh.template:483-499` (docker run flags); `tomo-statusline.sh:264` (label source)

**Key Decisions:** ADR-3 (identity), ADR-4 (update-check), ADR-7 (update re-renders launcher via shared helper).

**Dependencies:** Phase 1 (libs), Phase 2 (instances exist + are registered).

---

## Tasks

Makes update per-instance and gives each launcher its identity + an update-availability check.

- [x] **T3.1 Per-instance update selection** `[activity: backend-api]`
  1. Prime: update flow `[ref: solution.md/Key Flows]`.
  2. Test (RED): isolated tmpdir, two registered instances:
     - `update-tomo.sh --instance <name>` resolves via registry and updates ONLY that instance's files/config/version `[ref: PRD/F4-AC1]`.
     - `update-tomo.sh --config-file <path>` updates the explicit instance (test-friendly) `[ref: PRD/F4-AC2]`.
     - Updating one instance leaves the other byte-unchanged `[ref: PRD/F4-AC1]`.
  3. Implement (GREEN): source `instance-registry.sh`; add `--instance <name>` (→ `registry_resolve`); read that instance's `tomo-install.json`; re-render its launcher via `render-launcher.sh`; refresh `tomoVersion` + `registry_upsert`.
  4. Validate: `bash -n`; tests pass; bump `update-tomo.sh` `# version:`.
  5. Success: per-instance update isolation `[ref: PRD/F4-AC1, F4-AC2]`.

- [x] **T3.2 Container identity (name surfaced in container + Hashi)** `[activity: backend-api]` `[parallel: true]`
  1. Prime: ADR-3 `[ref: solution.md/ADR-3]`.
  2. Test (RED): render `begin-tomo.sh.template` and assert the docker-run line carries `-e TOMO_INSTANCE_NAME=<raw>`, `--hostname <sanitized>` (chars mapped to `[a-zA-Z0-9-]`, no leading/trailing dash, fallback `tomo`), and keeps `--label miyo.tomo.instance-name=<raw>`; statusline test: `TOMO_INSTANCE_NAME` set → shown; unset → falls back to `basename $TOMO_INSTANCE_DIR` `[ref: PRD/F3-AC1, F3-AC2, F3-AC3]`.
  3. Implement (GREEN): edit `begin-tomo.sh.template` docker-run (add env + hostname, add a sanitize helper); edit `tomo-statusline.sh:264` to prefer `TOMO_INSTANCE_NAME`.
  4. Validate: `bash -n`; tests pass; bump `begin-tomo.sh.template` + `tomo-statusline.sh` `# version:`.
  5. Success: each container reports its own name; Hashi label intact `[ref: PRD/F3-AC1, F3-AC2, F3-AC3]`.

- [x] **T3.3 Launcher update-availability check** `[activity: backend-api]`
  1. Prime: ADR-4 `[ref: solution.md/ADR-4]`.
  2. Test (RED): drive the launcher's check block with stubbed versions:
     - installed < repo `# version:` → warns (installed vs available) + offers update `[ref: PRD/F5-AC1, F5-AC2]`.
     - installed == or > repo → silent, proceeds `[ref: PRD/F5-AC3]`.
     - repo path missing / version unreadable → non-fatal skip + note, launch proceeds `[ref: PRD/F5-AC4]`.
     - portable semver compare correct for multi-digit fields (e.g. 0.9.0 < 0.10.0) — guards against lexical/`sort -V` pitfalls.
  3. Implement (GREEN): add a non-fatal check block to `begin-tomo.sh.template` reading repo `# version:` from baked `TOMO_REPO_ROOT/tomo/dot_claude/rules/project-context.md`, compare to baked installed version via a bash-3.2 field-by-field numeric compare; on behind → prompt to run `update-tomo.sh --instance <name>` then relaunch; never `set -e`-abort.
  4. Validate: `bash -n`; tests pass.
  5. Success: behind → prompt; current → silent; broken → skip; never blocks launch `[ref: PRD/F5-AC1..AC4]`.

- [x] **T3.4 Phase Validation** `[activity: validate]`
  - All Phase 3 tests; `bash -n` on all edited shell; ruff. Confirm the check is non-fatal under every failure branch.
