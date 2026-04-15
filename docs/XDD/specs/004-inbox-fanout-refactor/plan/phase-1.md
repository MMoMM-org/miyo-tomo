# Phase 1 — Scaffolding

## Goal

Establish the contract surface: schemas, empty script stubs, empty agent
definitions. Nothing runs end-to-end yet. All subsequent phases have stable
targets to fill in.

## Acceptance Gate

- [ ] All new files created with headers and version comments
- [ ] JSON-schema files validate (syntactically correct JSON Schema)
- [ ] Agent frontmatter parses without errors
- [ ] `scripts/*.py --help` works for all new scripts (returns usage, exits 0)

## Tasks

### 1.1 JSON Schema Contracts

Create `tomo/schemas/` with formal JSON Schemas:

- `tomo/schemas/shared-ctx.schema.json` — matches SDD `shared-ctx.json` spec
- `tomo/schemas/state-entry.schema.json` — matches state-line spec
- `tomo/schemas/item-result.schema.json` — matches `result.json` spec with
  polymorphic `actions[]` (use JSON Schema `oneOf` with discriminator `kind`)
- `tomo/schemas/suggestions-doc.schema.json` — reducer output spec

**Why schemas first:** Every downstream script validates against them. Prevents
silent schema drift.

### 1.2 Script Stubs

Create in `scripts/`:

- `scripts/shared-ctx-builder.py`
- `scripts/state-init.py`
- `scripts/state-update.py`
- `scripts/suggestions-reducer.py`

Each stub:
- `#!/usr/bin/env python3` + version comment
- Argparse with documented flags (don't implement logic)
- `if __name__ == "__main__":` returns exit 0 with a "not implemented" stderr
  message
- Header docstring listing inputs/outputs per the SDD

### 1.3 Agent Scaffolds

Create empty agent definitions:

- `tomo/.claude/agents/inbox-orchestrator.md` — YAML frontmatter (name, desc,
  model, tools including `mcp__kado__kado-search`, `mcp__kado__kado-read`,
  `mcp__kado__kado-write`, `Bash`, `Write`, `Read`, `Glob`, `Grep`,
  `AskUserQuestion`, `Agent`). Body is TBD — will be filled in Phase 3.

Do NOT touch `suggestion-builder.md` yet — retirement is Phase 5.

### 1.4 vault-config.yaml Extensions

Update `tomo/config/vault-example.yaml` to document the new settings:

```yaml
tomo:
  suggestions:
    proposable_tag_prefixes: ["topic"]
    excluded_tag_prefixes: ["type", "status", "projects", "content", "mcp"]
    parallel: 5
```

No changes to the live `tomo-instance/config/vault-config.yaml` in this phase
— that happens in Phase 2 when it's actually consumed.

### 1.5 tomo-tmp Directory Layout

Update `scripts/install-tomo.sh` to also create `tomo-tmp/items/` so it exists
from day one.

## Tests

- [ ] `python3 -c "import json; json.load(open('tomo/schemas/shared-ctx.schema.json'))"` succeeds
- [ ] `python3 scripts/shared-ctx-builder.py --help` exits 0
- [ ] `python3 scripts/state-init.py --help` exits 0
- [ ] `python3 scripts/state-update.py --help` exits 0
- [ ] `python3 scripts/suggestions-reducer.py --help` exits 0
- [ ] `ls tomo/.claude/agents/inbox-orchestrator.md` exists with parseable YAML frontmatter

## Hand-off to Phase 2

Phase 2 builds Phase A logic inside `shared-ctx-builder.py` and
`state-init.py`. Both scripts have their CLI and contract already defined here.
