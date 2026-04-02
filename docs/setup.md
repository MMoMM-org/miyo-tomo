# Tomo Setup Guide

## Prerequisites

- Docker installed and running
- Git
- jq
- Node.js / npm (for dev-notify-bridge)
- **macOS:** `brew install terminal-notifier` (for notifications)
- **Linux:** `notify-send` from `libnotify` (usually pre-installed on desktop distros)

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/MMoMM-org/miyo-tomo.git
cd miyo-tomo

# 2. Run the install script
bash scripts/install-tomo.sh

# 3. Start Tomo
bash begin-tomo.sh
```

## Install Script Walkthrough

The install script will ask for:

1. **Instance directory name** — where Tomo runs (default: `tomo-instance/`)
2. **Instance location** — where to create it (default: repo root)
3. **Kado host** — where Kado MCP runs (default: `host.docker.internal`)
4. **Kado port** — Kado port (default: `37022`)
5. **Kado bearer token** — your Kado API token

## Authentication

### Existing Claude Code User

If you already have Claude Code installed on your host, the install script extracts your auth automatically from `~/.claude.json` and `~/.claude/.credentials.json`.

### First-Time User

If this is your first Claude Code installation:

1. Run `bash begin-tomo.sh`
2. Claude Code will prompt for authentication
3. Follow the browser login flow
4. See [Troubleshooting](troubleshooting.md) if the auth callback fails

## Instance as Git Repo (Recommended)

We strongly recommend initializing your instance directory as its own git repo:

```bash
cd tomo-instance    # or your custom instance name
git init
git add -A
git commit -m "Initial Tomo instance"
```

This lets you:
- Track changes to your vault config and custom rules
- Roll back if something goes wrong
- Back up your instance configuration

## Updating

When you pull new Tomo versions:

```bash
git pull                        # Get latest source
bash scripts/update-tomo.sh     # Update managed files in your instance
```

The update script:
- **Overwrites** managed files (agents, commands, hooks) if the version changed
- **Never touches** user files (vault-config, kado-config)
- **Attempts to merge** settings.json — reports a TODO list if merge fails
