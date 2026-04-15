# /inbox — Process inbox with 2-pass workflow
# version: 0.4.0 (Pass 1 uses fan-out orchestrator, spec 004)

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
3. **Captured source items?** → Run Pass 1 via `inbox-orchestrator`
   - Dispatches to the `inbox-orchestrator` agent, which runs the fan-out
     pipeline: Phase A (shared-ctx + state-file) → Phase B (parallel
     `inbox-analyst` subagents, 3-5 at a time) → Phase C (reduce + render
     + `kado-write` final Suggestions doc)
   - Resumable: if a prior run's `tomo-tmp/inbox-state.jsonl` exists, the
     orchestrator asks via AskUserQuestion (Resume / Fresh run / Inspect)
4. **Nothing pending?** → Report "Inbox clear. Nothing to process."

### Pass 1 — Suggestions (fan-out)

1. `/inbox` dispatches to the **inbox-orchestrator** agent
2. Phase A: orchestrator builds `tomo-tmp/shared-ctx.json` and
   `tomo-tmp/inbox-state.jsonl`
3. Phase B: orchestrator spawns `inbox-analyst` subagents in batches of 3-5.
   Each subagent reads one item, classifies it, writes
   `tomo-tmp/items/<stem>.result.json`, updates the state-file
4. Phase C: orchestrator runs `suggestions-reducer.py`, renders markdown,
   writes the final `YYYY-MM-DD_HHMM_suggestions.md` via `kado-write`
5. Document contains visible `- [ ] Approved` checkbox + per-action tri-state
   decision checkboxes (Approve / Skip / Delete source)
6. **You review in Obsidian**, edit, check decisions
7. Check `[x] Approved` when satisfied

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

## Agents

This command dispatches:
- `inbox-orchestrator` — Pass 1 coordinator (fan-out: Phase A + B + C)
  - spawns `inbox-analyst` subagents per item (3-5 in parallel)
- `instruction-builder` — Pass 2 action generation
- `vault-executor` — cleanup and state transitions

Note: `suggestion-builder` is retired — its format rules live in
`inbox-orchestrator` now.
