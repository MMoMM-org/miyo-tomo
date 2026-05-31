---
title: "Phase 1: Foundation libraries (registry + render-launcher)"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Foundation libraries (registry + render-launcher)

## Phase Context

**GATE**: Read before starting.
- `[ref: solution.md/Architecture; Registry schema]` — `~/.tomo/instances.json` shape + fields
- `[ref: solution.md/ADR-2]` — registry as rebuildable index, atomic write, failure handling
- `[ref: solution.md/ADR-7]` — shared launcher renderer (closes backlog D-09)
- Pattern to mirror: `scripts/lib/configure-voice.sh` / `configure-ide-bridge.sh` (sourced libs, write-tmp-then-mv jq writers)
- Current duplicated render: the 5-substitution sed block in `install-tomo.sh:1156` and `:1280` and `update-tomo.sh`

**Key Decisions:** ADR-2 (registry), ADR-7 (render-launcher). Both are pure, sourceable bash libs — no installer wiring yet, so they are unit-testable in isolation.

**Dependencies:** none (foundation). Phases 2 & 3 depend on this.

---

## Tasks

Delivers two sourced bash libraries with full unit coverage, ready for the installer/updater to consume.

- [x] **T1.1 Instance registry library** `[activity: backend-api]`
  1. Prime: Read the registry schema + ADR-2 `[ref: solution.md/ADR-2]` and the jq write-tmp-then-mv pattern in `scripts/lib/configure-ide-bridge.sh`.
  2. Test (RED): `tests/test_instance_registry.py` (or `tests/test-instance-registry.sh`) driving the lib in an isolated `HOME`/tmpdir:
     - `registry_upsert` creates `~/.tomo/instances.json` with `schema_version` + one entry (happy).
     - `registry_upsert` of an existing name overwrites in place (no duplicate).
     - `registry_resolve <name>` returns the instance dir/path fields; unknown name → non-zero + empty.
     - `registry_list` prints all entries; empty/missing file → empty list, exit 0.
     - Stale entry (path dir missing) → flagged by a `registry_list`/check mode, not a crash (failure case).
     - Corrupt/unparseable JSON → backed up + treated as empty (recovery).
     - `~/.tomo/` unwritable → clear non-zero error, no partial file (failure case).
  3. Implement (GREEN): `scripts/lib/instance-registry.sh` — `registry_path`, `registry_list`, `registry_upsert <name> <path> <repo> <version>`, `registry_resolve <name>`, `registry_remove <name>`, stale-check; atomic tmp→mv via jq; bash 3.2 safe (no assoc arrays).
  4. Validate: `bash -n`; targeted tests pass; ruff clean (if py test).
  5. Success:
     - [x] New instance recorded with name/path/repo/version/updatedAt `[ref: PRD/F2-AC1]`
     - [x] Stale entry handled gracefully, no crash `[ref: PRD/F2-AC3]`
     - [x] Missing registry → empty + recreatable `[ref: PRD/F2-AC4]`
     - [x] Unwritable `~/.tomo/` fails clearly `[ref: solution.md/Error Handling]`

- [x] **T1.2 Shared launcher renderer** `[activity: backend-api]` `[parallel: true]`
  1. Prime: Read ADR-7 + the existing duplicated sed blocks `[ref: solution.md/ADR-7]`; backlog D-09.
  2. Test (RED): `tests/test_render_launcher.py` — render `begin-tomo.sh.template` to a tmp dst with sample values; assert all 5 placeholders (`{{INSTANCE_NAME}}`, `{{INSTANCE_PATH}}`, `{{HOME_DIR}}`, `{{TOMO_REPO_ROOT}}`, `{{DEV_NOTIFY_PORT}}`) are substituted and NO `{{` remains; output is executable; atomic (no partial file on failure).
  3. Implement (GREEN): `scripts/lib/render-launcher.sh` — `render_launcher <template> <dst> <instance_name> <instance_path> <home_dir> <repo_root> <dev_notify_port>`; atomic tmp→mv; `chmod +x`.
  4. Validate: `bash -n`; tests pass.
  5. Success:
     - [x] All 5 substitutions applied; no unrendered `{{...}}` `[ref: solution.md/ADR-7]`
     - [x] One renderer reused by install + update (no duplicated sed) `[ref: backlog/D-09]` — shared helper created; install/update call-sites swap in P2/P3
     - [x] Docker `{{ index ... }}` format strings survive substitution (regression-locked)

- [x] **T1.3 Phase Validation** `[activity: validate]`
  - Run all Phase 1 tests; `bash -n` on both libs; ruff clean. Confirm libs are sourceable with no side effects on import.
