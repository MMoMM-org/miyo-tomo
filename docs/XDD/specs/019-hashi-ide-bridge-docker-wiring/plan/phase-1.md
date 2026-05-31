---
title: "Phase 1: Wizard Lib & Lock File"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Wizard Lib & Lock File

Establishes the configuration foundation: a bash wizard lib that collects IDE Bridge settings, persists the `ide_bridge` block to `tomo-install.json`, and generates/removes the Claude Code IDE lock file in `tomo-home/.claude/ide/`. Everything downstream (entrypoint proxy, launch banner, statusline) reads what this phase writes.

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 1 (IDE Lock File Management); AC1-AC4]`
- `[ref: PRD/Feature 4 (Install/Update Wizard); AC1-AC5]`
- `[ref: PRD/Detailed Feature Specifications → IDE Lock File Management; Business Rules 1-6, Edge Cases]`
- `[ref: SDD/Interface Specifications; lines: 174-198]` — `ide_bridge` block + lock-file JSON shape
- `[ref: SDD/Runtime View → First-time setup; lines: 212-218]`

**Key Decisions**:
- **ADR-4**: token cleartext in `tomo-install.json` + lock file; **no `0600`** on the lock file (Business Rule 6). The lock *directory* still gets `0700` (PRD edge case).
- Business Rule 1: `pid: 0`. Rule 2: `ideName: "Obsidian"`. Rule 3: `transport: "ws"`. Rule 4: disabling removes the lock file but **preserves** `auth_token`/`port` in config. Rule 5: lock filename port == configured port == proxy port (single source = `tomo-install.json → ide_bridge.port`).
- `workspaceFolders: []` (empty — IDE-only field, no meaning in this topology).

**Dependencies**: none — this is the first phase. T1.2 depends on T1.1.

**Mirror the voice pattern exactly**: `configure-ide-bridge.sh` is the structural twin of `configure-voice.sh` (state dispatch: keep / change / disable for the already-enabled case; enable-or-decline for the disabled case; `--non-interactive` preserves state and returns early). `write_ide_bridge_config` is the twin of `write_voice_config` (single authoritative jq writer).

---

## Tasks

- [x] **T1.1 `configure-ide-bridge.sh` wizard lib (prompts + config writer + lock-file gen/remove)** `[activity: backend-shell]`

  1. **Prime**: Read `scripts/lib/configure-voice.sh` end-to-end (the structural template) and `tests/voice/test_configure_voice.py` (the subprocess test harness). Read `[ref: SDD/Interface Specifications; lines: 174-198]` for the exact `ide_bridge` block and lock-file JSON.
  2. **Test** (`tests/ide_bridge/test_configure_ide_bridge.py`, driving the lib via `bash -c` subprocess with controlled stdin, mirroring `_run_wizard`/`_parse`):
     - non-interactive fresh install → `IDE_BRIDGE_ENABLED=false`, no lock file written `[ref: PRD/F4-AC2]`
     - non-interactive preserves an existing enabled config (token + port kept) `[ref: PRD/F4-AC2]`
     - fresh install: enable `y` → valid UUID token → port `23027` (accept default on empty) → `ENABLED=true`, token + port captured `[ref: PRD/F4-AC1]`
     - invalid token (not a UUID, e.g. `not-a-uuid`) → rejected with a clear error; loops/keeps prior, does not persist garbage `[ref: PRD/F4-AC4]`
     - token with leading/trailing whitespace → trimmed then validated (PRD edge case)
     - port non-numeric (`abc`) and out-of-range (`70000`, `0`) → rejected with a clear error `[ref: PRD/F4-AC5]`
     - already-enabled state: `K` keeps; `d` disables (removes lock file, **preserves** token/port in the JSON block); `u`/change updates token-or-port and regenerates the lock `[ref: PRD/F4-AC3; Business Rule 4]`
     - `write_ide_bridge_config <target.json>` writes `.ide_bridge = {schema_version:1, enabled, auth_token, port}` and round-trips via `jq` `[ref: SDD; lines: 176-182]`
     - lock-file generator writes `<home>/.claude/ide/<port>.lock` with exactly `{pid:0, workspaceFolders:[], ideName:"Obsidian", transport:"ws", authToken:"<token>"}`; creates `<home>/.claude/ide/` at `0700`; assert via `jq -e` per field `[ref: PRD/F1-AC1, F1-AC4; Business Rules 1-3, 6]`
     - disable path removes the lock file but leaves `ide_bridge.auth_token`/`port` intact in the JSON `[ref: Business Rule 4]`
  3. **Implement**: Create `scripts/lib/configure-ide-bridge.sh` (`# version: 0.1.0`). Functions, all bash 3.2 (CON-1):
     - globals contract on success: `IDE_BRIDGE_ENABLED` ("true"/"false"), `IDE_BRIDGE_TOKEN`, `IDE_BRIDGE_PORT`
     - `write_ide_bridge_config <target-json>` — jq-merge `.ide_bridge = {schema_version:$schema, enabled:$enabled, auth_token:$tok, port:$port}` (twin of `write_voice_config`; `--argjson` for schema/enabled/port, `--arg` for token; write-to-`.tmp`-then-`mv`)
     - `write_ide_lock <home_dir> <port> <token>` — `mkdir -p "<home>/.claude/ide"`, `chmod 700` the dir; assemble JSON with `jq -n` (never hand-built strings — memory `feedback_no_regex_yaml_edit` applies to JSON too); write `<port>.lock`; do NOT chmod 600 (Rule 6)
     - `remove_ide_lock <home_dir> <port>` — `rm -f "<home>/.claude/ide/<port>.lock"` (disable path; config retained by caller)
     - `_is_uuid <s>` — case-validated 8-4-4-4-12 hex (bash `case`/`[[ =~ ]]`); trim whitespace before checking
     - `_is_valid_port <s>` — numeric, 1024–65535
     - `configure_ide_bridge <current_enabled> <current_token> <current_port> <home_dir> [non_interactive]` — relies on the sourcing script's `print_step/print_ok/print_warn/print_err`; `DEFAULT_IDE_PORT=23027` (Kado uses 23026); state dispatch identical in shape to `configure_voice`; on enable/update it sets globals only — the **caller** decides when to call `write_ide_bridge_config`/`write_ide_lock` (so install can defer lock gen until `HOME_DIR` is resolved)
  4. **Validate**: `pytest tests/ide_bridge/test_configure_ide_bridge.py -v` green; `/bin/bash -n scripts/lib/configure-ide-bridge.sh` clean.
  5. **Success**:
     - Lock file matches the exact schema; bad token/port rejected; disable preserves config `[ref: PRD/F1-AC1, F1-AC4, F4-AC4, F4-AC5; Business Rule 4]`
     - Wizard is non-destructive in `--non-interactive` `[ref: PRD/F4-AC2]`

- [x] **T1.2 Wire the wizard into `install-tomo.sh` and `update-tomo.sh`** `[activity: backend-shell]`

  1. **Prime**: Re-read the voice call-sites you mirror — `install-tomo.sh` Step 6c (`configure_voice`, lines ~910-930) and the save-config block (lines ~1257-1298, including the `"voice": {}` seed and the `write_voice_config`/instance-mirror calls); `update-tomo.sh` voice wizard (lines ~424-469) and persist block (lines ~631-659). Note the **deviation**: IDE Bridge writes **no instance mirror** (the lock file in bind-mounted `tomo-home` is the runtime source).
  2. **Test**:
     - extend `tests/ide_bridge/test_configure_ide_bridge.py` (or a sibling) with an **isolated** `install-tomo.sh` smoke that passes `--non-interactive` + all four isolation flags (`--instance-location`/`--instance-name`/`--home-dir`/`--config-file` → `tmp_path`) and asserts the run still succeeds and writes `.ide_bridge` (empty/`enabled:false` is fine non-interactively) — proving the wiring doesn't break the existing install path `[ref: CON-6]` `[ref: memory: feedback_test_scripts_must_never_touch_real_install]`
     - a focused test that, given an enabled `ide_bridge` config + a `home_dir`, the lock file lands at `<home>/.claude/ide/<port>.lock` (drive the call-site helper, not a full interactive install) `[ref: PRD/F1-AC1]`
  3. **Implement**:
     - `install-tomo.sh` (`# version:` bump): source `lib/configure-ide-bridge.sh` next to the voice source (line ~181); add **Step 6d** right after the voice wizard — load prior `ide_bridge.{enabled,auth_token,port}` from `$CONFIG_FILE` (jq, with `// false`/`// ""`/`// 23027` fallbacks), call `configure_ide_bridge`; seed `"ide_bridge": {}` into the generated `tomo-install.json` heredoc (sibling of `"voice": {}`, line ~1278); after `HOME_DIR` is resolved and config saved, call `write_ide_bridge_config "$CONFIG_FILE"` then, if enabled, `write_ide_lock "$HOME_DIR" "$IDE_BRIDGE_PORT" "$IDE_BRIDGE_TOKEN"` (else `remove_ide_lock`). **Sequencing note**: lock generation MUST be after `HOME_DIR` exists (Step 9 region), not in Step 6d.
     - `update-tomo.sh` (`# version:` bump): source the lib; resolve `HOME_DIR` from `.homePath` in `$CONFIG_FILE`; add the IDE Bridge wizard alongside the voice wizard (read prior from `$CONFIG_FILE` `.ide_bridge`; honor `--keep-voice`? no — add nothing new to flags unless needed, default behavior is interactive keep/update/disable); on change, `write_ide_bridge_config "$CONFIG_FILE"` and regenerate (`write_ide_lock`) or remove (`remove_ide_lock`) the lock file under `$HOME_DIR`. Surface the lock create/update/delete via the existing `mark_did` markers for a consistent plan/execute report.
  4. **Validate**: `pytest tests/` (full suite stays green — CON-6); `/bin/bash -n` on both scripts; manual `update-tomo.sh --dry-run` shows no crash and (if config present) reports the IDE Bridge state.
  5. **Success**:
     - Fresh install with IDE Bridge enabled produces the lock file in `tomo-home` `[ref: PRD/F1-AC1]`
     - `update-tomo.sh` creates the lock without a reinstall, and the keep/update/disable path works `[ref: PRD/F1-AC2, F1-AC3, F4-AC3]`
     - Voice wizard + existing install/update flows unchanged `[ref: CON-6]`

- [x] **T1.3 Phase Validation** `[activity: validate]`

  Run `pytest tests/ide_bridge/ tests/voice/ -v` and the full `pytest tests/`. `/bin/bash -n` on `configure-ide-bridge.sh`, `install-tomo.sh`, `update-tomo.sh`. Confirm no test touched the real `$REPO_ROOT/tomo-instance` (all used `tmp_path` + isolation flags). Verify against PRD Feature 1 + Feature 4 ACs and SDD interface spec.
