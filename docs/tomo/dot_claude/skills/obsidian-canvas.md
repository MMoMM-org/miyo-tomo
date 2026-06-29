# WHY: obsidian-canvas (skill)

> Rationale for decisions in `tomo/dot_claude/skills/obsidian-canvas/SKILL.md`.
> Attribution: adapted from github.com/kepano/obsidian-skills (json-canvas/SKILL.md, MIT licence)
> and the JSON Canvas 1.0 specification at jsoncanvas.org.

## Why This Skill Exists

Obsidian Canvas files (`.canvas`) are a distinct format from `.md` notes and `.base` database files.
They follow the open JSON Canvas 1.0 spec and carry a specific node/edge schema that is easy to
get wrong without a reference (dangling edge IDs, wrong required fields per node type, newline
encoding pitfalls). Codifying that knowledge as a skill avoids repeated re-derivation from the
spec during canvas authoring tasks.

## ADR-6: Access-Agnostic Format

The skill body contains zero references to Kado, MCP tools, or any write transport. This follows
the ADR-6 access-agnostic principle: format knowledge is stable across execution contexts (host
session, Docker session, future runtimes). Transport concerns belong in the agent or command that
invokes this skill, not here. If a consumer needs to write a `.canvas` file, it brings its own
write path.

## ADR-8: Differentiated Trigger Description

The description is written to be disjoint from the two sibling format skills:

- `obsidian-markdown` — targets `.md` syntax (callouts, wikilinks, dataview). No canvas terms.
- `obsidian-bases` — targets `.base` files (Obsidian Bases / database format). No canvas terms.
- `obsidian-canvas` (this skill) — targets `.canvas` files / JSON Canvas / canvas nodes/edges.
  The description explicitly says "Do NOT activate for .base files, .md notes" to prevent
  cross-trigger when a task mentions both formats in the same session.

The exclusion clause is load-bearing: without it, a prompt like "add a canvas card linking to my
daily note" could match both obsidian-canvas and obsidian-markdown. The explicit NOT clause
anchors routing to the JSON Canvas format specifically.

## Why the "Covers…" Sentence Was Stripped from the Description

An earlier draft included "Covers node types (text, file, link, group), edge connections…" in the
description. Per skill-author conventions, descriptions that summarize content risk the agent
treating the description as a shortcut and skipping the body. Removed; content lives in the skill
body only.

## Attribution

- kepano/obsidian-skills, skills/json-canvas/SKILL.md — adapted (not copied verbatim), MIT licence.
  Source: https://github.com/kepano/obsidian-skills
- JSON Canvas 1.0 specification — consulted for field names, defaults, and color system.
  Source: https://jsoncanvas.org/spec/1.0/
  GitHub: https://github.com/obsidianmd/jsoncanvas
