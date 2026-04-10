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

The install script guides you through setup in 7 steps:

### 1. Vault Path

Point Tomo at your Obsidian vault directory. The script validates the path exists and checks for `.obsidian/`.

### 2. Framework Profile

Choose your PKM framework:
- **miyo** — Marcus's vault conventions (LYT-derived with customizations)
- **lyt** — Standard LYT/Ideaverse Pro conventions
- **custom** — Start from scratch

The profile provides default folder mappings, classification categories, and relationship markers. Everything can be overridden later.

### 3. Concept Mapping

For each concept (inbox, notes, maps, calendar, projects, areas, sources, templates, assets):
- The script shows the profile default path
- Lists your vault's top-level folders
- You confirm or override each mapping

### 4. Lifecycle Tag Prefix

Choose the tag prefix for Tomo's lifecycle states (default: `MiYo-Tomo`). Tags like `#MiYo-Tomo/captured` and `#MiYo-Tomo/proposed` track document state.

### 5. Kado Connection

- **Host** — where Kado runs (default: `host.docker.internal` for Docker)
- **Port** — Kado port (default: `37022`)
- **Bearer token** — your Kado API key (must start with `kado_`)

### 6. Instance Creation

The script creates your Tomo instance directory with agents, commands, skills, and config files copied from `tomo/` source.

### 7. Docker Home Setup

Sets up `tomo-home/` as the Docker `/home/coder` mount, including Claude Code auth from your host (if available).

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

## Instance as Git Repo (Recommended)

Initialize your instance directory as its own git repo:

```bash
cd tomo-instance
git init
git add -A
git commit -m "Initial Tomo instance"
```

This lets you track config changes and roll back if needed.

## Updating

```bash
git pull                        # Get latest source
bash scripts/update-tomo.sh     # Update managed files in instance
```

The update script overwrites managed files (agents, commands, hooks) if the version changed, but never touches user files (vault-config, kado-config).
