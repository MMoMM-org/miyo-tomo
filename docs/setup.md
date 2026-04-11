# Tomo Setup Guide

## Prerequisites

- Docker installed and running
- Git, jq
- Python 3
- [MiYo Kado](https://github.com/MMoMM-org/miyo-kado) v0.1.6+ running and accessible

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/MMoMM-org/miyo-tomo.git
cd miyo-tomo

# 2. Run the install script
bash scripts/install-tomo.sh

# 3. Build the Docker image
docker build -t miyo-tomo:latest ./docker/

# 4. Start Tomo
bash begin-tomo.sh
```

## Install Script Walkthrough

The install script guides you through setup in 8 steps:

### 1. Vault Path

Point Tomo at your Obsidian vault directory. The script validates the path exists and checks for `.obsidian/`.

### 2. Framework Profile

Choose your PKM framework:
- **miyo** — Marcus's vault conventions (LYT-derived with customizations)
- **lyt** — Standard LYT/Ideaverse Pro conventions
- **custom** — Start from scratch

The profile provides default folder mappings, classification categories, and relationship markers. Everything can be overridden later.

### 3. Concept Mapping

For each concept (inbox, notes, maps, calendar, projects, areas, sources, templates, assets) you have three options at each prompt:

- **`d`** — accept the profile default
- **`b`** — launch the directory browser to drill into your vault structure
- **Type a path directly** — for quick manual entry

The directory browser lets you navigate: number keys descend into a subfolder, `0` goes back up, `d` confirms the current path. After each concept, `[b]` takes you back to re-do the previous one, and a final summary lets you jump back to any concept before confirming all.

### 4. Lifecycle Tag Prefix

Choose the tag prefix for Tomo's lifecycle states (default: `MiYo-Tomo`). Tags like `#MiYo-Tomo/captured` and `#MiYo-Tomo/proposed` track document state.

### 5. Kado Connection

- **Host** — where Kado runs (default: `host.docker.internal` for Docker)
- **Port** — Kado port (default: `37022`)
- **Bearer token** — your Kado API key (must start with `kado_`)

### 6. Git User Configuration

Tomo sets up a git identity so commits made inside the Docker container (and in the auto-initialized instance repo) are attributed correctly. The script reads your host's global git config and offers three options:

- **Use host values** (recommended) — reuses your `git config --global user.name/email`
- **Enter different values** — prompts for name and email
- **Skip** — no git config; you can set it manually later

The values are written to `tomo-home/.gitconfig` (global for the container) and also set as local config in the instance repo.

### 7. Instance Creation

The script creates your Tomo instance directory with agents, commands, skills, and config files copied from `tomo/` source. It then:

1. Writes an instance-level `.gitignore` excluding secrets (`.mcp.json` with your Kado token) and runtime state
2. Runs `git init` inside the instance
3. Sets local git user (if provided in step 6)
4. Creates an initial commit

If the instance directory already contains a `.git/`, the script skips init and leaves it alone. Git failures never abort the install.

### 8. Docker Home Setup

Sets up `tomo-home/` as the Docker `/home/coder` mount, including Claude Code auth from your host (if available) and the `.gitconfig` from step 6.

## Non-Interactive Mode

For automated setups:

```bash
bash scripts/install-tomo.sh \
  --vault /path/to/vault \
  --profile miyo \
  --kado-host host.docker.internal \
  --kado-port 37022 \
  --kado-token kado_your_token \
  --prefix MiYo-Tomo \
  --non-interactive
```

## After Installation

### First Session — Explore Your Vault

Start Tomo and run the vault explorer:

```
/explore-vault
```

This scans your vault via Kado to discover:
- Folder structure and note counts
- Frontmatter field patterns
- Tag taxonomy
- Relationship markers (up::, related::)
- Callout usage (editable vs protected)
- MOC hierarchy and topics

You confirm each discovery step. Results are written to `vault-config.yaml` and `discovery-cache.yaml`.

### Processing Inbox

Once exploration is complete:

```
/inbox
```

Tomo auto-detects what to do next based on lifecycle state tags.

## Authentication

### Existing Claude Code User

The install script extracts auth from `~/.claude.json` and `~/.claude/.credentials.json` automatically.

### First-Time User

1. Run `bash begin-tomo.sh`
2. Claude Code prompts for authentication
3. Follow the browser login flow
4. See [Troubleshooting](troubleshooting.md) if the auth callback fails

## Instance Git Repository

The install script automatically initializes `tomo-instance/` as its own git repo with an initial commit (see Step 7). This is independent of the parent miyo-tomo repo — `tomo-instance/` is gitignored at the parent level, so there's no conflict.

The instance `.gitignore` excludes:
- `.mcp.json` — contains your Kado bearer token, never commit this
- `.claude/settings.local.json`, `.claude/*.log`, `.claude/cache/` — Claude Code runtime state
- OS cruft (`.DS_Store`, `Thumbs.db`)

If the install flow detects an existing `.git/` inside the instance path, it leaves it alone. You can always re-run the install to refresh managed files without losing your git history.

## Cleanup / Re-install

For a clean re-run (useful during testing or after config mistakes):

```bash
bash scripts/cleanup-tomo.sh              # interactive with confirmation
bash scripts/cleanup-tomo.sh --force      # skip confirmation
bash scripts/cleanup-tomo.sh --dry-run    # preview what would be removed
bash scripts/cleanup-tomo.sh --keep-home  # preserve Claude auth credentials
```

The cleanup script removes `tomo-instance/`, `tomo-home/`, and `tomo-install.json`. It refuses to delete anything outside the repo root as a safety check.

## Updating

```bash
git pull                        # Get latest source
bash scripts/update-tomo.sh     # Update managed files in instance
```

The update script overwrites managed files (agents, commands, hooks) if the version changed, but never touches user files (vault-config, kado-config).
