---
title: "Instance Backup + Restore + Warning"
status: draft
version: "0.1"
---

# Product Requirements Document

## Product Overview

### Vision

Give the user confidence that a wiped `tomo-instance/` is not a disaster —
one command packages everything non-regenerable into a timestamped archive;
one command restores it onto a fresh install. And: warn the user upfront
about the nested-git trap so they can avoid it.

### Problem Statement

Setting up a Tomo instance is a multi-step investment:

1. `install-tomo.sh` — vault path, profile, Kado endpoint/token, prefix
   (~5 min).
2. `/tomo-setup` — concept mapping, lifecycle prefix, vault-config.yaml
   generation (~5 min).
3. `/explore-vault` — frontmatter/tags/relationships/callouts/trackers
   detection + discovery cache build (~10–20 min depending on vault size).
4. `/tomo-trackers-wizard` — per-tracker syntax + description + positive/
   negative keywords (~15 min for 25 fields at correct detail).

Total: 30+ minutes of careful interactive setup. Loss is costly:

- The `tomo-instance` gitignore + historical nested-git trap (see memory
  `feedback_no_nested_git_in_bind_mounts.md`) meant `git clean -fdX` from
  the host silently wiped the dir — multiple times in one day during the
  2026-04-20 incident.
- Even if we fix the root cause (we did — commit `baebf5c`), other paths
  to loss exist: disk failure, accidental `rm -rf`, cleanup scripts,
  container volume reset, OS reinstall.

### Value Proposition

- **Fast recovery**: `bash scripts/restore-tomo.sh backups/tomo-backup-<ts>.tar.gz`
  gets a fresh install back to the exact state it was in pre-loss.
- **User-owned cadence**: Backup is a manual command — run before risky
  changes, weekly, or whatever suits. No cron / no surprises.
- **Transparent archive**: tar.gz, inspectable with standard tools.
- **Warning in install**: New users learn about the trap up front, not
  the hard way.

## User Personas

### Primary: Post-install-setup user
- Just finished `install-tomo.sh` + `/tomo-setup` + `/explore-vault` +
  wizard runs. Wants a one-line command to freeze this hard-won state.

### Secondary: Recovering user
- Instance got wiped (any cause). Has a backup archive. Runs
  `install-tomo.sh` fresh, then `restore-tomo.sh <archive>`. Expects
  identical state + zero re-authentication drama.

## User Journey Map

### Journey 1: Take a backup

1. User is happy with current instance state.
2. Runs `bash scripts/backup-tomo.sh`.
3. Script detects the instance, packages all preservable files, writes
   `backups/tomo-backup-YYYY-MM-DD_HH-MM.tar.gz` at repo root with
   mode 600.
4. Prints archive path + content summary + size.

### Journey 2: Restore after a wipe

1. User notices `tomo-instance/` is empty/missing.
2. Runs `install-tomo.sh` to re-create the skeleton (paths, profile,
   Kado creds). Skips interactive Kado token if they prefer.
3. Runs `bash scripts/restore-tomo.sh backups/tomo-backup-<ts>.tar.gz`.
4. Script overwrites `tomo-install.json` + instance config + wizard
   outputs with the archive's content.
5. User restarts Tomo session — state matches pre-wipe.

### Journey 3: New user is warned

1. User runs `install-tomo.sh` for the first time.
2. Install prints an early notice:
   "NOTE: `tomo-instance/` is bind-mounted infrastructure. Do not run
    `git init` inside it, and be cautious with `git clean -fdX` from the
    host repo — that command cleans gitignored files and can wipe the
    instance. Run `bash scripts/backup-tomo.sh` periodically."
3. User proceeds with informed consent.

## Feature Requirements

### Must Have

#### F1 — `scripts/backup-tomo.sh`

- Reads `tomo-install.json` to find `$INSTANCE_PATH` + `$HOME_DIR`.
- Packages the following into `backups/tomo-backup-<ISO-timestamp>.tar.gz`:
  - `tomo-install.json` (paths, profile, Kado creds)
  - `tomo-instance/config/` (vault-config.yaml, user-rules/, discovery-cache.yaml)
  - `tomo-instance/.claude/settings.local.json` (if exists)
  - `tomo-instance/.mcp.json` (contains bearer, regenerable but small)
- EXCLUDES by default:
  - `tomo-instance/.claude/agents|skills|commands|hooks|rules` (regenerable
    from host repo via `update-tomo.sh`)
  - `tomo-instance/scripts/`, `profiles/`, `schemas/`, `templates/` (same)
  - `tomo-instance/tomo-tmp/` (scratch)
  - `tomo-instance/cache/` (rebuildable via `/explore-vault`)
  - `tomo-home/` entirely (container-side auth — user re-authenticates)
- Archive mode 600 (owner-only — contains Kado bearer).
- Print summary: file list + byte count + archive path.
- Exit 0 on success, non-zero with error detail on failure.

#### F2 — `scripts/restore-tomo.sh <archive.tar.gz>`

- Verifies the archive exists, is readable, and contains a
  `tomo-install.json` at its root (sanity check).
- Requires `tomo-install.json` + `tomo-instance/` to already exist in the
  target repo (i.e., `install-tomo.sh` was run first). If not, error out
  with "Run install-tomo.sh first" and exit.
- Extracts files OVER the existing ones — overwriting. No silent merge.
- Warns before overwriting existing `vault-config.yaml` or
  `tomo-install.json`. Ask via read -p "Overwrite? [Y/n]".
- Exit 0 on success, describes what was restored.

#### F3 — Install-time warning

- Add a step early in `install-tomo.sh` that prints:
  ```
  ▸ Instance location & safety

    tomo-instance/ is gitignored infrastructure, not a versioned project.

    AVOID:
    • `git init` inside tomo-instance/ — install no longer does this
    • `git clean -fdX` from the host repo (cleans gitignored files)

    BACKUP your instance with: bash scripts/backup-tomo.sh
    RESTORE after a wipe:       bash scripts/restore-tomo.sh <archive>
  ```
- Only shown on first-time install (when `tomo-install.json` doesn't
  exist). Skipped on re-runs to keep the non-first-time UX snappy.

### Should Have

#### F4 — Backup rotation helper
- `backup-tomo.sh --keep N` retains only the N most recent archives,
  deletes older ones. Default: unlimited (user manages).

#### F5 — Restore offer on fresh install
- `install-tomo.sh` detects `backups/tomo-backup-*.tar.gz` near the end.
  If present, offers: "Restore from latest backup (<path>, <date>)?
  [y/N]". If yes, runs `restore-tomo.sh <latest>` automatically after
  completing install.

#### F6 — Backup include-flag

- `backup-tomo.sh --include-home` additionally packages `tomo-home/` (auth
  state) so users who don't want to re-auth on restore can opt in. Default
  excludes to keep archives small + security-safer.

### Could Have

#### F7 — Dry-run mode
- `backup-tomo.sh --dry-run` prints what would be archived without
  creating the archive. Same for restore.

#### F8 — Archive verification
- After `backup-tomo.sh` creates the archive, verify it by reading it
  back with `tar tzf` and checking the expected files list matches.

### Won't Have (MVP)

- Automatic backups on schedule (cron / launchd) — user's choice.
- Cloud upload (S3, Dropbox) — out of scope, user's choice.
- Encrypted archives (age, gpg) — user controls archive location; file
  permissions 600 + local storage is the MVP guarantee.
- Diff-based / incremental backups — full archive each time is simple
  and robust for the MB-scale data involved.

## Functional Requirements

### Inputs

- `backup-tomo.sh`: optional flags (`--keep N`, `--include-home`, `--dry-run`).
  Reads `tomo-install.json`.
- `restore-tomo.sh`: archive path (positional arg). Reads `tomo-install.json`
  to find the target.

### Outputs

- `backups/tomo-backup-<ISO-timestamp>.tar.gz` (mode 600).
- stdout: summary (file count, bytes, path).

### Acceptance Criteria

- Given a freshly-configured instance, `backup-tomo.sh` produces an archive
  ≤5 MB (typical) containing exactly the preservable files listed in F1.
- Given an archive + a fresh install (empty config), `restore-tomo.sh`
  rehydrates the instance such that `/inbox` runs identically to pre-backup.
- First-time users see the warning; second-time+ users do not.
- Archive permissions are 600 after creation.
- Restore warns before overwriting existing config.

## Non-Functional Requirements

- **Speed**: backup completes in <5 seconds for typical instance (vault-config +
  user-rules, no home dir).
- **Portability**: bash 3.2 compatible, uses `tar` + `jq` only (both in
  Dockerfile base tools and standard macOS).
- **Safety**: restore requires explicit confirmation before overwriting
  existing config. Never touches the host repo or unrelated paths.
- **Visibility**: both scripts echo every file path they touch.

## Out of Scope

- Backing up the Obsidian vault itself (that's the user's responsibility
  via their own vault backup strategy — probably Obsidian Sync, iCloud,
  or Time Machine).
- Backing up the host miyo-tomo repo (that's what GitHub is for).

## Success Metrics

- After a wipe, user recovers with `install-tomo.sh` + `restore-tomo.sh`
  in under 3 minutes (vs 30+ minutes for full re-setup).
- First-time-install users report they "felt informed" about the trap.
- Zero reported incidents of users running `git init` inside tomo-instance/
  after the warning is live.

## Answered vs Open Questions

**Answered (conversation 2026-04-20):**
- Backups are manual, not scheduled.
- Format: tar.gz.
- Includes secrets; user controls storage location + chmod 600.
- Destination: repo-root `backups/` by default (already matches
  `.backup-*` gitignore pattern).

**Open for SDD:**
- Exact file manifest (boundary cases: `tomo-home/.claude.json`?
  `tomo-tmp/state/`?).
- Rotation policy default (keep all? keep 10?).
- Interaction with `install-tomo.sh --non-interactive` — should restore
  offer be silent or error?
