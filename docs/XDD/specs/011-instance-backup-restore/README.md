# Specification: 011-instance-backup-restore

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-20 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-04-20 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | draft | First cut — needs review |
| solution.md | pending | After requirements approved |
| plan/ | pending | |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-20 | Scope: warning + backup/restore scripts (not auto-triggers) | User is responsible for backup cadence; we provide the tooling, not a schedule |
| 2026-04-20 | Archive format: tar.gz | Universal, easy to inspect, no macOS-specific dependencies |
| 2026-04-20 | Secrets strategy: INCLUDE in archive with chmod 600 | User controls where the archive lives; stripping tokens forces re-entry, which defeats the purpose |
| 2026-04-20 | Archive destination: sibling to tomo-instance (`<parent>/tomo-backups/`), `--output` override | User preference — survives a full wipe of tomo-instance. Added to host .gitignore as `tomo-backups/`. Off-device copies still recommended for hard-disaster recovery |
| 2026-04-20 | No install-tomo.sh integration (no warning, no restore-offer) | Keep scope minimal — two standalone scripts only. Warning lives in XDD 011 backlog item if needed later |
| 2026-04-20 | Default rotation: keep 10 archives (`--keep 10`) | Bounded growth, easy override with `--keep N` (0 = unlimited) |
| 2026-04-20 | Always include tomo-home/ (auth) | User preference — restore should not require re-auth |

## Context

Two related concerns triggered by the 2026-04-20 `tomo-instance` wipe incident:

1. **Risk warning** — We recommend placing `tomo-instance/` INSIDE the host
   miyo-tomo repo, AND (until commit `baebf5c`) auto-git-init'd it. The
   nested-git-in-gitignored-dir combo is a known trap (see memory
   `feedback_no_nested_git_in_bind_mounts.md`). Users should know.

2. **Backup** — A fresh install is ~5 minutes of interactive prompts +
   `/tomo-setup` wizards (trackers, daily-log, explore-vault) that can
   take 30+ minutes. Losing the instance loses all of that. A one-shot
   backup script + restore script drastically shortens recovery.

## Scope

This spec combines both concerns because they share the same artifact set
(what lives in the instance, what's worth preserving) and the same
mental model (the instance is ephemeral — user needs tools to survive
that).

## Open Questions for Review

- Should `backup-tomo.sh` offer profiles (e.g. "config-only" vs "config + auth")?
- Include `tomo-home/` (container home with Claude Code auth) or exclude?
  Exclude means user has to re-authenticate after restore — probably OK for
  security, annoying for convenience.
- Rotate old backups automatically, or let user manage?
- Should install-tomo.sh offer to restore from a backup if one exists and
  no instance is present?
