# MiYo Tomo (友)

AI-assisted PKM workflows for Obsidian via MiYo Kado MCP server.
Tomo runs inside a Docker container with sandbox isolation — all vault access goes through Kado.

@~/Kouzou/standards/general.md

## Project Files
@~/Kouzou/projects/miyo/team.md

## Key Directories

- `tomo/` — source of truth: agents, skills, commands, config templates (versioned)
- `tomo-instance/` — Docker workspace, gitignored, created by install script
- `tomo-home/` — Docker /home/coder, gitignored
- `docker/` — Dockerfile and container config
- `scripts/` — install and update scripts

## Rules

- NEVER modify vault files directly — all vault access goes through Kado MCP
- Propose changes as instruction set entries — never execute without approval
- Instance directory is self-contained — no runtime references back to tomo/
- All managed files in tomo/ must include a version comment for update tracking
