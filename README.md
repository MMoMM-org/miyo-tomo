# MiYo Tomo (友)

AI-assisted PKM workflows for Obsidian via [MiYo Kado](https://github.com/MMoMM-org/miyo-kado) MCP server.

Tomo runs inside an isolated Docker container. All vault access goes through Kado — no direct filesystem access to your Obsidian vault.

## What Tomo Does

- **`/inbox`** — Analyses inbox files and generates a structured instruction set
- **`/execute`** — Executes approved actions from an instruction set
- **`/explore-vault`** — Discovers vault structure (MOCs, tags, folders)

## How It Works

1. You trigger `/inbox` — Tomo reads your inbox via Kado, analyses each file, and creates an instruction set
2. You review the instruction set in Obsidian — check the actions you approve
3. You trigger `/execute` — Tomo processes only the checked actions via Kado

Tomo proposes, you decide.

## Quick Start

```bash
git clone https://github.com/MMoMM-org/miyo-tomo.git
cd miyo-tomo
bash scripts/install-tomo.sh
bash begin-tomo.sh
```

See [docs/setup.md](docs/setup.md) for detailed instructions.

## Prerequisites

- Docker
- Git, jq
- [MiYo Kado](https://github.com/MMoMM-org/miyo-kado) running and accessible
- **macOS:** `brew install terminal-notifier` (for notifications)
- **Linux:** `libnotify` / `notify-send` (for notifications)

## Repository Structure

```
miyo-tomo/
├── tomo/               # Source of truth — agents, skills, commands, config templates
├── docker/             # Dockerfile and container config
├── scripts/            # Install and update scripts
├── docs/               # Setup guide, troubleshooting, workflow docs
├── begin-tomo.sh       # Start a Tomo session
├── tomo-instance/      # (gitignored) Docker workspace, created by install script
└── tomo-home/          # (gitignored) Docker /home/coder
```

## Platform Support

| Platform | Status |
|----------|--------|
| macOS    | Supported |
| Linux    | Supported |
| Windows  | PRs welcome — not maintained by us |

## Architecture

Tomo is part of the [MiYo](https://github.com/MMoMM-org) ecosystem:

- **Kokoro** (心) — Architecture and decisions (private)
- **Kouzou** (構造) — Claude Code infrastructure (private)
- **Kado** (門) — MCP server for Obsidian vault access (public)
- **Tomo** (友) — AI workflows (this repo, public)
- **Seigyo** (制御) — Obsidian control plugin (public, post-MVP)

## License

MIT
