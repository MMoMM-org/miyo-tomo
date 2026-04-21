# Specification: 011-instance-backup-restore

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-20 |
| **Current Phase** | DONE — scripts shipped 2026-04-20, spec docs backfilled 2026-04-21 |
| **Last Updated** | 2026-04-21 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | ready | v0.1 — open questions resolved below |
| solution.md | ready | v1.0 — reverse-engineered 2026-04-21 from shipped scripts |
| plan/ | complete | Phases 1–3 all marked done; T3.4 (README update) deferred |

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
| 2026-04-20 | Rotation is instance-name scoped | Multiple vaults / instances sharing an output dir don't delete each other's archives. Archive filename prefix `<instanceName>-` makes this safe. |
| 2026-04-20 | config/ restore = rm -rf + copy (clean slate); tomo-home/ restore = merge | config/ stale-file risk is real (obsolete user-rules, old cache); tomo-home/ is larger and more fragile, merge is safer. |

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

## Completion Summary (2026-04-21)

**Shipped (commits `371730c`, `3d09c9c`):**
- `scripts/backup-tomo.sh` v0.1.0 — staging → tar.gz → chmod 600 →
  instance-scoped rotation (keep 10 default). Default output is sibling
  to `tomo-instance/` so instance wipes don't take archives with them.
- `scripts/restore-tomo.sh` v0.1.0 — archive sanity check → extract to
  temp → confirm overwrite → restore config/.mcp/settings/home.

**Deferred (not shipped — tracked in backlog F-29):**
- Install-time warning (F3 in requirements) — explicitly de-scoped
  2026-04-20 decision. Users discover backup via docs / README.
- Archive verification (F8) — no post-write `tar -tzf` round-trip check.
  Low risk at current data scale.
- Root README mention + recovery doc section (T3.4) — `--help` text
  covers it; re-open if users ask how to recover.

## Resolved Open Questions

From the original requirements "Open for SDD" list:

- **Exact file manifest** — resolved in solution.md §"Archive Layout":
  `tomo-install.json`, `tomo-instance/config/`, `.claude/settings.local.json`,
  `.mcp.json`, `tomo-home/` (full).
- **Rotation policy** — keep 10 default, instance-name scoped, `--keep N`
  override, 0 = unlimited.
- **install-tomo.sh --non-interactive** — no interaction added; restore
  stays fully separate from install.

---
*This file is managed by the xdd-meta skill.*
