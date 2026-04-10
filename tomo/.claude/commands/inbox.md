# /inbox — Process inbox with 2-pass workflow
# version: 0.2.0

Process inbox items using the 2-pass suggestion/instruction workflow.
Automatically detects what to do next based on lifecycle state tags.

## Usage

`/inbox` — Auto-detect next action (cleanup → Pass 2 → Pass 1)
`/inbox --pass1` — Force Pass 1 (generate suggestions from captured items)
`/inbox --pass2` — Force Pass 2 (generate instructions from confirmed suggestions)
`/inbox --cleanup` — Force cleanup (archive applied instruction sets)

## How It Works

### Auto-Discovery (default)

The command checks lifecycle states in priority order:

1. **Applied items found?** → Run cleanup (vault-executor agent)
2. **Confirmed suggestions found?** → Run Pass 2 (instruction-builder agent)
3. **Captured items found?** → Run Pass 1 (inbox-analyst → suggestion-builder agents)
4. **Nothing pending?** → Report "Inbox clear. Nothing to process."

Discovery uses:
```bash
python3 scripts/state-scanner.py --config config/vault-config.yaml --discover
```

### Pass 1 — Suggestions

1. **inbox-analyst** reads and classifies all captured items
2. **suggestion-builder** generates suggestions document with alternatives
3. Document written to inbox as `YYYY-MM-DD_HHMM_suggestions.md`
4. Tagged as `#MiYo-Tomo/proposed`
5. **You review in Obsidian**, edit fields, check/uncheck items
6. Change tag to `confirmed` when ready

### Pass 2 — Instructions

1. **instruction-builder** parses confirmed suggestions
2. Generates detailed per-action instructions with rendered templates
3. Instruction set + auxiliary files written to inbox
4. Tagged as `#MiYo-Tomo/instructions`
5. **You apply each action** in Obsidian (move files, add links, update trackers)
6. Change tag to `applied` when done

### Cleanup

1. **vault-executor** finds applied instruction sets
2. Transitions fully-applied source items to `active`
3. Archives suggestions and instruction documents
4. Optionally moves/deletes auxiliary files

## State Machine

```
captured → proposed → confirmed → instructions → applied → active
                                                          → archived
```

Tags set by Tomo: `captured`, `proposed`, `instructions`, `active`, `archived`
Tags set by you: `confirmed`, `applied`

## Agent

This command orchestrates four agents:
- `inbox-analyst` — classification and analysis
- `suggestion-builder` — Pass 1 document generation
- `instruction-builder` — Pass 2 action generation
- `vault-executor` — cleanup and state transitions
