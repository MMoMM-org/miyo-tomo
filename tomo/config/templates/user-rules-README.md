# Vault Conventions (User Rules)
<!-- version: 0.1.0 -->

This directory holds your **vault-specific behavioral rules** — conventions that
Tomo should apply when proposing tags, destinations, templates, etc. These rules
override framework defaults.

## How it works

Rules are written in natural language. Agents consult the relevant file when
they make decisions that match its topic. Unlike `vault-config.yaml` (structural
data: paths, schemas), these files capture **behavior** — things that don't fit
into YAML.

Your instance's `CLAUDE.md` references these files descriptively, so they're
lazy-loaded only when relevant. Agents read them when a task touches their topic.

## Suggested topic files

Create these as you discover your own conventions. Examples:

- `tagging.md` — tag-selection rules (which `type/*` per note, template-vs-tag
  precedence, tag normalization specifics)
- `destinations.md` — where notes go (which folders accept which types, which
  targets get MOC links, which don't)
- `templates.md` — template-selection rules (which template for which note type
  and destination)

You can add more topic files as needed (e.g., `daily-notes.md`, `projects.md`).
After adding a new file, reference it in the "Vault Conventions" section of
your instance's `CLAUDE.md` so agents know it exists.

## Format

Short bullet lists work best. Each rule should be:
- A single, testable statement
- Explicit about its scope (which note types, which operations)
- Brief on the **why** when the rule is non-obvious

Example:
```markdown
# Tag Selection

- Do NOT propose `type/*` tags. Templates set the type on render —
  proposing the tag duplicates the template's role.
- Exception: inbox items may carry `type/note/zettel` as a capture marker.
  That tag disappears when the note is moved out of the inbox.
```

## What NOT to put here

- Structural data (paths, folder layout, concept mapping) → that's `vault-config.yaml`
- Tag taxonomy (known values per prefix, wildcard flags) → that's `vault-config.yaml`
- Framework-agnostic logic (MOC matching, state machines) → that's in skills, don't duplicate
- One-off fixes for a single note → rules should generalize
