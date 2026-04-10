---
title: "Phase 3: Install Script + YAML Fixer"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Install Script + YAML Fixer

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `docs/specs/tier-3/wizard/install-script.md` — Full install script spec (10-step flow)
- `docs/specs/tier-3/config/frontmatter-schema.md` §1 — yaml-fixer spec
- `docs/specs/tier-2/components/setup-wizard.md` — Two-phase setup design
- `scripts/install-tomo.sh` — Existing install script to refine

**Key Decisions**:
- Install script runs on host, no Kado needed
- Must be re-runnable (detect existing config, merge/overwrite)
- Non-interactive mode via CLI flags
- yaml-fixer is standalone Python (no external dependencies beyond PyYAML)
- Bash 3.2 compatible (macOS default)

**Dependencies**:
- Phase 1 (profiles must exist for framework selection)
- Phase 2 (vault-config schema must be defined for config generation)

---

## Tasks

Refines the install script to implement the full Phase 1 setup wizard and adds the YAML resilience utility.

- [ ] **T3.1 Install Script — Profile Selection + Concept Mapping** `[activity: build-feature]`

  1. Prime: Read install script spec `[ref: docs/specs/tier-3/wizard/install-script.md]` and existing `scripts/install-tomo.sh`
  2. Test: Script offers framework selection (miyo/lyt/para/custom); loads profile defaults after selection; presents vault folders via `ls`; maps each concept (inbox, notes, maps, calendar, project, area, source, template, asset) with profile defaults; accepts user overrides; detects subdirectories where relevant
  3. Implement: Refine `scripts/install-tomo.sh` — add profile selection step, concept mapping loop with profile defaults, vault path validation (check `.obsidian/` exists)
  4. Validate: `bash -n scripts/install-tomo.sh` passes; shellcheck clean (if available); non-interactive mode works with `--vault /tmp/test-vault --profile miyo --non-interactive`
  5. Success: Script walks through all 10 steps per spec; produces valid vault-config.yaml matching schema from Phase 2

- [ ] **T3.2 Install Script — Config Generation + Non-Interactive Mode** `[activity: build-feature]`

  1. Prime: Read vault-config schema `[ref: docs/specs/tier-2/components/user-config.md]` and install script spec step 7 `[ref: docs/specs/tier-3/wizard/install-script.md]`
  2. Test: Generated vault-config.yaml has schema_version, profile, concepts, lifecycle; profile defaults fill unspecified fields; non-interactive flags (--vault, --profile, --kado-host, --kado-port, --kado-token, --prefix, --non-interactive) all work; re-running detects existing config and asks merge/overwrite/cancel
  3. Implement: Add config generation from mapped concepts + profile defaults; add CLI flag parsing; add re-run detection
  4. Validate: Generate config with `--non-interactive`, verify YAML parses and has correct structure
  5. Success: Config matches schema; re-run safely handles existing state; CLI flags documented in `--help`

- [ ] **T3.3 YAML Fixer Utility** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read frontmatter schema spec §1 `[ref: docs/specs/tier-3/config/frontmatter-schema.md §1]`
  2. Test: Fixes tab→space normalization; fixes indentation errors; quotes bare strings containing `:`; auto-closes unclosed sequences; handles empty input; handles already-valid YAML (no-op); returns exit code 0 on success, 1 on unfixable
  3. Implement: Create `scripts/yaml-fixer.py` — standalone Python script using only stdlib + PyYAML; reads stdin or file argument; outputs fixed YAML to stdout
  4. Validate: `python3 scripts/yaml-fixer.py --help` works; test with known-broken YAML samples
  5. Success: Fixer repairs common YAML errors without losing data; valid YAML passes through unchanged

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Install script syntax-checks clean. yaml-fixer handles test cases. Non-interactive install produces valid vault-config.yaml from profile defaults. Bash 3.2 compatible (no associative arrays, no `mapfile`).
