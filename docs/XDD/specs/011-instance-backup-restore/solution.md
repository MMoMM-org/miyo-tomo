---
title: "Instance Backup + Restore — Solution Design"
status: ready
version: "1.0"
---

# Solution Design

> Reverse-engineered 2026-04-21 from shipped implementation (commits
> `371730c` feat, `3d09c9c` fix). Describes what exists today; marks
> deferred items.

## Architecture Summary

Two standalone bash scripts at `scripts/backup-tomo.sh` and
`scripts/restore-tomo.sh`. Both read `tomo-install.json` at repo root
to locate `$INSTANCE_PATH` and `$HOME_DIR`. Neither script touches the
host miyo-tomo repo or Obsidian vault.

Archive format is a plain `tar.gz` with a fixed internal layout —
inspectable with standard tools, transferable between machines, no
format dependencies beyond `tar` + `gzip`.

## Archive Layout

```
<archive>.tar.gz
├── tomo-install.json             # paths, profile, Kado creds
└── tomo-instance/
    ├── config/                   # vault-config.yaml, user-rules/,
    │                             #   discovery-cache.yaml, vault-config.md
    ├── .claude/
    │   └── settings.local.json   # user's per-install overrides
    └── .mcp.json                 # Kado bearer + endpoint
└── tomo-home/                    # full container /home/coder
                                  #   (Claude Code auth, session state)
```

Everything outside this list is regenerable from the source repo via
`update-tomo.sh` (agents, skills, commands, hooks, rules, runtime
scripts, profiles, schemas, templates) or by re-running the wizards
(`tomo-tmp/`, `cache/`).

## Script Contracts

### `backup-tomo.sh`

| Aspect | Detail |
|---|---|
| Flags | `--output PATH` \| `--keep N` (default 10, 0 = unlimited) \| `--dry-run` \| `--help` |
| Default output | `<parent-of-$INSTANCE_PATH>/tomo-backups/<instanceName>-<ISO-ts>.tar.gz` |
| Naming | Timestamp format `YYYY-MM-DD_HH-MM-SS`. `<instanceName>` from `tomo-install.json.instanceName` (fallback `tomo-instance`), so multiple instances share a dir without collision. |
| Staging | `mktemp -d` → `cp -R` each stage path → `tar -czf` the staging root. Cleanup via EXIT trap. |
| Mode | `chmod 600` the archive (bearer + Claude Code creds inside). |
| Rotation | Scoped to `${instanceName}-*.tar.gz` glob in output dir, `ls -1t | tail -n +$((KEEP+1))` → rm. Other instances' archives in the same dir are untouched. |
| Output summary | file list (staged `+ path` per item), final size, off-device-copy reminder. |
| Exit codes | 0 success, 1 missing tomo-install.json / instance dir / jq / tar / unknown flag. |

### `restore-tomo.sh`

| Aspect | Detail |
|---|---|
| Arg | `<archive.tar.gz>` (positional, required) |
| Flags | `--force` (skip confirmation) \| `--dry-run` \| `--help` |
| Preconditions | `tomo-install.json` + `$INSTANCE_PATH` must exist — restore refuses on a non-installed tree. |
| Sanity check | Archive must contain `tomo-install.json` at its root — else "not a Tomo backup" + exit 1. |
| Extract | `tar -xzf` into `mktemp -d`; EXIT trap cleans up. |
| Confirmation | Lists targets that will be overwritten; `read -rp "Proceed? [y/N]"`; default = no. Skipped under `--force` or `--dry-run`. |
| Overwrite policy | `tomo-install.json` + `.mcp.json` + `settings.local.json` via `cp -R` (overwrite). `config/` is `rm -rf`'d then re-copied (clean slate to avoid stale leftovers). `tomo-home/` via `cp -R tomo-home/. $HOME_DIR/` (merge — preserves any container-side additions). |
| Exit codes | 0 success, 1 missing archive / missing install / missing jq / extra positional args. |

## Design Decisions (shipped)

| Decision | Rationale |
|---|---|
| Archive at `<parent>/tomo-backups/`, not `<repo>/backups/` | Sibling to `tomo-instance/` survives `rm -rf tomo-instance/`; parent-of-instance is stable across users regardless of repo layout. |
| Instance name in archive filename | Multiple instances (e.g. multiple vaults) share an output dir without stepping on each other during rotation. |
| Include `tomo-home/` (auth) | User preference 2026-04-20 — restore should not require re-authenticating Claude Code. |
| Include bearer + creds, chmod 600 | Stripping would force re-entry and defeat the "fast recovery" value prop. User controls archive location. |
| Rotation = 10, instance-scoped | Bounded growth; rotation does not touch other instances' archives. |
| `config/` restore = `rm -rf` then copy | Clean slate. Merge semantics here would leave stale files from previous runs. |
| `tomo-home/` restore = `cp -R ./.` (merge) | Keeps container-side additions. Safer than wipe since home-dir state is larger and more fragile. |

## Out of Scope (shipped)

- **Install-time warning (F3)** — planned as P3 in this spec; deferred
  per decision 2026-04-20 "No install-tomo.sh integration". Users
  discover backup via docs / README / running into trouble once. Note
  still parked in backlog F-29.
- **Archive verification (F8)** — `tar -czf` exit code is trusted; no
  post-write `tar -tzf` check. Low risk at MB-scale, documented gap.
- **Encrypted archives, cloud upload, scheduling** — all user-owned
  (README + Time Machine / iCloud / Dropbox suffice).

## Known Limits

- Restore overwrites `tomo-install.json` with archive content — if the
  user's active install path differs from the archive's (e.g. restoring
  onto a renamed repo), they must edit the JSON afterward. Not
  automated.
- No multi-archive chaining (diff/incremental). Full snapshot each time.
- Archive trusts the filesystem — symlinks inside the staged paths are
  followed via `cp -R`. No symlink protection beyond whatever `tar` does.
