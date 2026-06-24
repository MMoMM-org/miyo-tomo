---
name: tomo-tag-handler-wizard
description: Create or edit a Tomo tag-handler config (e.g. the tsukai handler) that routes MiYo/<Feature>/… tagged inbox captures into a target note. Loads the tomo-tag-handler-wizard skill, which guides the config via questions and writes the schema-validated JSON.
argument-hint: "no arguments needed"
---
# /tomo-tag-handler-wizard — Create or edit a tag-handler config
# version: 0.1.0

Create or edit a tag-handler config for the Tomo tag-handler framework — capture
routing, e.g. Tomo Tsukai's `MiYo/Tsukai/<repo>` captures into a dev-log note under
`## Captures`.

## STRICT — How to Run This Command

Load and follow the `tomo-tag-handler-wizard` skill: read
`.claude/skills/tomo-tag-handler-wizard/SKILL.md` and execute its workflow in your
context. It gathers the handler fields via `AskUserQuestion` and writes the config
schema-validated via `scripts/tag-handler-writer.py` — never hand-edit the JSON.

Authoritative spec: `.claude/skills/tomo-tag-handler-wizard/SKILL.md`.

## Usage

```
/tomo-tag-handler-wizard        # create a new handler, or edit an existing one
```

Config lives at `config/tag-handlers/<feature>.json` (user-owned; `update-tomo`
preserves your edits). Key fields: `target.map` (captured segment → target note
path), `placement` (`after` = top/newest-first · `inside` = end · `before`),
`marker` (the heading anchor). Modify-only — the target note must already exist and
contain the `marker` heading.
