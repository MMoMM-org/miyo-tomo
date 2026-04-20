# MiYo Tomo (友)

AI-assisted PKM workflows for Obsidian via MiYo Kado MCP server.
Tomo runs inside a Docker container with sandbox isolation — all vault access goes through Kado.

@~/Kouzou/standards/general.md

## Project Files
@~/Kouzou/projects/miyo/team.md

## Key Directories

- `tomo/` — source of truth: agents, skills, commands, config templates, profiles (versioned)
- `tomo/profiles/` — framework profiles (miyo.yaml, lyt.yaml)
- `tomo/config/templates/` — reference templates for note types
- `scripts/` — install, utility, and Python scan scripts
- `scripts/lib/` — shared Python library (kado_client)
- `docs/XDD/` — all specs: implementation (specs/) and architecture reference (reference/tier-1, tier-2, tier-3)
- `docs/XDD/backlog.md` — open items (post-MVP features, doc debt)
- `docker/` — Dockerfile and container config
- `tomo-instance/` — Docker workspace, gitignored, created by install script
- `tomo-home/` — Docker /home/coder, gitignored

## Architecture

4-layer Knowledge Stack: Universal PKM Concepts → Framework Profiles → User Config → Discovery Cache.
2-pass inbox model: Suggestions (Pass 1) → User confirms → Instructions (Pass 2) → User applies.
MVP execution boundary: Tomo writes only to inbox folder; user applies everything else.

See `docs/XDD/reference/tier-1/pkm-intelligence-architecture.md` for full architecture.
See `docs/XDD/README.md` for the consolidated documentation index.

## Rules

- NEVER modify vault files directly — all vault access goes through Kado MCP
- Propose changes via 2-pass model — never execute without user approval
- Instance directory is self-contained at runtime — agents, commands, skills, configs, and credentials all live inside the instance. The only exception is the generated `begin-tomo.sh` launcher, which references the Tomo source repo for Docker image builds and version checks (a launch-time dependency, not a runtime one).
- All managed files in tomo/ must include a version comment for update tracking
- Profiles are pure data (YAML) — logic lives in skills
- Layer precedence: User Config > Profile > Universal Concepts; Discovery Cache is advisory only

## Memory & Context
@docs/ai/memory/memory.md

## Routing Rules
<!-- Run /memory-add to capture learnings. -->
- Personal/workflow corrections → global (~/.claude/includes/) or ~/Kouzou/standards/
- Repo conventions/style → docs/ai/memory/general.md
- Tool/CI/build knowledge → docs/ai/memory/tools.md
- Domain/business rules → docs/ai/memory/domain.md
- Architectural decisions → docs/ai/memory/decisions.md
- Current focus/blockers → docs/ai/memory/context.md
- Bugs/fixes → docs/ai/memory/troubleshooting.md
