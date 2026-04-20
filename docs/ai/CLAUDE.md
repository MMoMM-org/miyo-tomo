# docs/ai/ — Memory Bank Rules

## Maintenance
- /memory-add — capture learnings from this session
- /memory-sync — verify @imports and index are in sync
- /memory-cleanup — archive resolved issues and prune stale context (run monthly)
- /memory-promote — detect promotable domain patterns → reusable skills (run when domain.md grows)

## Category definitions
- general.md: naming, code style, git workflow (longlived)
- tools.md: CI, build, local dev quirks (longlived/medium)
- domain.md: business rules, data models — PKM model, Kado contract, 2-pass flow (medium)
- decisions.md: architecture choices, ADR links (medium)
- context.md: current sprint focus, blockers (short — prune regularly)
- troubleshooting.md: known bugs + fixes (short — archive when resolved)

## Index budget: ≤ 200 lines

## Note on dual memory systems
This repo has **two** memory systems:
1. **TCS repo memory** (this dir) — shared with the team, checked into git
2. **Auto-memory** at `~/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo/memory/` — personal, not in git

Route learnings to TCS repo memory if they're useful for collaborators; to auto-memory if they're personal observations about this specific working environment.
