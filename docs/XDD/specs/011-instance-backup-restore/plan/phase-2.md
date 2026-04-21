---
title: "Phase 2: restore-tomo.sh"
status: complete
version: "1.0"
phase: 2
---

# Phase 2: restore-tomo.sh

## Phase Context

Implement the unpacking side: verify archive, extract to temp, confirm
overwrite, restore over existing instance. Retrospective plan — script
shipped 2026-04-20 (commit `371730c`).

## Tasks

- [x] **T2.1 CLI surface + help** `[activity: backend]` — **DONE**

  Positional arg `<archive.tar.gz>`, flags `--force`, `--dry-run`,
  `--help`. Rejects multiple positional args or unknown flags.

- [x] **T2.2 Preconditions** `[activity: backend]` — **DONE**

  - Archive file exists and readable.
  - `tomo-install.json` at repo root (install-tomo.sh was run).
  - `$INSTANCE_PATH` directory exists.
  - `jq` on PATH.

- [x] **T2.3 Archive sanity check** `[activity: backend]` — **DONE**

  `tar -tzf` output must contain `tomo-install.json` at root
  (matched via `grep '^\./tomo-install\.json$\|^tomo-install\.json$'`).
  Refuses non-Tomo archives with clear error.

- [x] **T2.4 Extract + confirm** `[activity: backend]` — **DONE**

  Extract into `mktemp -d`. Print list of targets that will be
  overwritten. `read -rp "Proceed? [y/N]"` — default no. `--force` /
  `--dry-run` skip the prompt.

- [x] **T2.5 Restore files** `[activity: backend]` — **DONE**

  - `tomo-install.json` → repo root (cp -R overwrite).
  - `tomo-instance/config/` → `rm -rf` + cp -R (clean slate).
  - `.mcp.json` → cp -R overwrite (optional, if in archive).
  - `settings.local.json` → cp -R overwrite (optional).
  - `tomo-home/` → `cp -R ./.` merge into `$HOME_DIR` (preserves
    container-side additions).

- [x] **T2.6 Final instructions** `[activity: backend]` — **DONE**

  Prints "Re-start the Tomo session with: bash begin-tomo.sh" so the
  user doesn't forget the stale container needs a fresh start.

- [x] **T2.7 Phase Validation** `[activity: validate]` — **DONE 2026-04-20**

  Live-tested: backup on working instance → wipe instance → fresh
  `install-tomo.sh` → `restore-tomo.sh <archive>` → next session had
  full state back (auth, config, wizards). Cycle confirmed by user.
