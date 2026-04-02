# /explore-vault — Learn vault structure
# version: 0.1.0

Discover and document the vault's structure for LYT/MOC work.

## Workflow

1. Read current vault-config.md for known structure
2. List vault folders recursively via Kado MCP `list_directory`
3. Identify MOCs (Maps of Content) — notes that primarily link to other notes
4. Discover tag taxonomy — scan frontmatter and inline tags
5. Map folder layout — purpose of each top-level folder
6. Update `.claude/rules/vault-config.md` with discoveries
7. Report: discovered MOC count, folder count, tag summary

## What to Look For

- Notes with many outgoing links and few inline content → likely MOCs
- Folder naming patterns (dates, topics, areas)
- Tag hierarchies (nested tags like `#area/work`)
- Template patterns in frontmatter
