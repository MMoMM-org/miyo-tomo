# /inbox — Process inbox with 2-pass workflow
# version: 0.3.0

Process inbox items using the 2-pass suggestion/instruction workflow.
Auto-detects what to do next based on workflow document checkboxes.

## Usage

`/inbox` — Auto-detect next action (cleanup → Pass 2 → Pass 1)
`/inbox --pass1` — Force Pass 1 (generate suggestions from captured items)
`/inbox --pass2` — Force Pass 2 (generate instructions from approved suggestions)
`/inbox --cleanup` — Force cleanup (process applied instruction sets)

## How It Works

### Auto-Discovery (default)

The command checks in priority order:

1. **Instruction sets with Applied actions?** → Run cleanup (vault-executor)
   - Scan inbox for `*_instructions.md` via Kado `listDir`
   - Read each, count `- [x] Applied` vs total actions
   - Any with at least one Applied → cleanup
2. **Suggestions with `[x] Approved`?** → Run Pass 2 (instruction-builder)
   - Scan inbox for `*_suggestions.md` via Kado `listDir`
   - Read each, check for `- [x] Approved` at top
3. **Captured source items?** → Run Pass 1 (inbox-analyst → suggestion-builder)
   - Use `state-scanner.py --state captured` (still byTag for source items)
4. **Nothing pending?** → Report "Inbox clear. Nothing to process."

### Pass 1 — Suggestions

1. **inbox-analyst** reads and classifies all captured items
2. **suggestion-builder** generates suggestions document with alternatives
3. Document written to inbox as `YYYY-MM-DD_HHMM_suggestions.md`
4. Contains visible `- [ ] Approved` checkbox at top (no lifecycle tags)
5. **You review in Obsidian**, edit fields, check/uncheck items
6. Check `[x] Approved` when satisfied

### Pass 2 — Instructions

1. **instruction-builder** parses approved suggestions
2. Generates detailed per-action instructions with rendered templates
3. Instruction set + auxiliary files written to inbox
4. Per-action `- [ ] Applied` checkboxes (no lifecycle tags)
5. **You apply each action** in Obsidian and check `[x] Applied` per action
6. Run `/inbox` when done — Tomo cleans up

### Cleanup

1. **vault-executor** finds instruction sets with Applied actions
2. Transitions fully-applied source items from `captured` → `active`
3. Asks user about partially-applied items
4. Asks user whether to keep or delete completed workflow docs

## State Model

**Source items** (inbox notes): tag-based, Tomo-managed
```
captured  →  active
```

**Workflow documents** (suggestions, instructions): checkbox-based, user-facing
```
Suggestions: [ ] Approved  →  [x] Approved  (user checks)
Instructions: per action [ ] Applied → [x] Applied  (user checks)
```

## Agent

This command orchestrates four agents:
- `inbox-analyst` — classification and analysis
- `suggestion-builder` — Pass 1 document generation
- `instruction-builder` — Pass 2 action generation
- `vault-executor` — cleanup and state transitions
