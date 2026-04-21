---
title: "Phase 1: backup-tomo.sh"
status: complete
version: "1.0"
phase: 1
---

# Phase 1: backup-tomo.sh

## Phase Context

Implement the packaging side: read `tomo-install.json`, stage
preservable files, create timestamped tar.gz, chmod 600, rotate old
archives. Retrospective plan — script shipped 2026-04-20 (commit
`371730c`) + filename fix 2026-04-20 (`3d09c9c`).

## Tasks

- [x] **T1.1 CLI surface + help text** `[activity: backend]` — **DONE** (commit `371730c`)

  `--output PATH`, `--keep N` (default 10), `--dry-run`, `--help`.
  Help text auto-extracted from script header comments.

- [x] **T1.2 Preconditions + config read** `[activity: backend]` — **DONE**

  Reads `tomo-install.json`, extracts `instancePath`, `instanceName`,
  `homePath` via `jq`. Exits 1 with clear message if any missing or
  `jq` / `tar` not on PATH.

- [x] **T1.3 Staging + archive creation** `[activity: backend]` — **DONE**

  `mktemp -d` staging root → `cp -R` each preservable path (config,
  settings.local.json, .mcp.json, tomo-home/) → `tar -czf`. EXIT trap
  cleans up staging. chmod 600 on archive.

- [x] **T1.4 Default output path (sibling to instance)** `[activity: backend]` — **DONE** (commit `3d09c9c`)

  Default: `<parent-of-INSTANCE_PATH>/tomo-backups/<instanceName>-<ts>.tar.gz`.
  Archive survives `rm -rf tomo-instance/`. `--output` accepts either a
  directory (timestamp file inside) or a full file path.

- [x] **T1.5 Rotation** `[activity: backend]` — **DONE**

  `--keep N` default 10; 0 = unlimited. Scoped to `${instanceName}-*.tar.gz`
  glob so shared output dirs across instances stay safe. `ls -1t |
  tail -n +$((KEEP+1))` → rm.

- [x] **T1.6 Summary + off-device reminder** `[activity: backend]` — **DONE**

  stdout prints staged file list, archive path, size, and a yellow
  warning reminding the user to copy archives off-device for disaster
  recovery.

- [x] **T1.7 Phase Validation** `[activity: validate]` — **DONE 2026-04-20**

  Live-run against active instance: archive created, chmod 600, contents
  verified via `tar -tzf`, rotation confirmed after a second run.
