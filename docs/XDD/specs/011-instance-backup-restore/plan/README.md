---
title: "Instance Backup + Restore — Implementation Plan"
status: complete
version: "1.0"
---

# Implementation Plan

## Context Priming

**Specification**:
- `docs/XDD/specs/011-instance-backup-restore/README.md`
- `docs/XDD/specs/011-instance-backup-restore/requirements.md`
- `docs/XDD/specs/011-instance-backup-restore/solution.md`

**Shipped implementation** (commits `371730c`, `3d09c9c`):
- `scripts/backup-tomo.sh` v0.1.0
- `scripts/restore-tomo.sh` v0.1.0

## Implementation Phases

- [x] [Phase 1: backup-tomo.sh](phase-1.md) — shipped 2026-04-20
- [x] [Phase 2: restore-tomo.sh](phase-2.md) — shipped 2026-04-20
- [x] [Phase 3: Finalize + document](phase-3.md) — 2026-04-21

## Phase Dependencies

Linear: 1 → 2 → 3. Phase 2 depends on Phase 1's archive layout contract.
Phase 3 depends on both shipping.

## Acceptance for Spec Completion

- ✅ `backup-tomo.sh` packages preservable files into `tar.gz`, chmod 600,
  sibling-of-instance default location, rotation keeps 10.
- ✅ `restore-tomo.sh` rehydrates onto a fresh install with explicit
  overwrite confirmation.
- ✅ Both scripts run on bash 3.2 (macOS default), use only `tar` + `jq`.
- ✅ Restore requires `install-tomo.sh` to have been run first.
- ⏳ Install-time warning (F3) deferred — tracked in backlog F-29.
