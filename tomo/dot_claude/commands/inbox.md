# /inbox — Process inbox with 2-pass workflow
# version: 0.8.3

Process inbox items using the 2-pass suggestion/instruction workflow.
Auto-detects what to do next based on workflow document checkboxes.

## STRICT — How to Run This Command

**Dispatch behaviour per branch:**

| Branch | Agent | How to run |
|--------|-------|------------|
| Cleanup | `vault-executor` | Impersonate (read the spec, execute in your context) — unchanged from prior version |
| Pass 2 | `instruction-builder` | Dispatch via `Agent` tool (was already dispatched) |
| Pass 1 | `inbox-orchestrator` | **Dispatch via `Agent` tool** (changed in this version — experimental) |

**Dispatch shape for inbox-orchestrator (Pass 1):**

```
Agent({
  subagent_type: "inbox-orchestrator",
  description: "Pass 1 — orchestrate inbox synthesis",
  prompt: "Run Pass 1 on the inbox. Follow your agent definition (Phase 0a → 0b → A → B → C → D). Pass through TOMO_INBOX_RECOVER=<0|1> per the --recover flag. Report back with the final Suggestions doc path + run summary."
})
```

The orchestrator runs on sonnet per its frontmatter and dispatches its
own subagents (`voice-transcriber` in Phase 0a, `inbox-analyst` in
Phase B) internally. That's a 2-level nesting (`/inbox` →
`inbox-orchestrator` → leaf agents) which Claude Code supports in
practice (verified empirically via `instruction-builder` doing the same
nesting in Step 2.5).

**3-level nesting caveat:** the FAN-resolve subflow inside
`instruction-builder` (Step 2.5) dispatches `inbox-analyst` only when
`parsed-suggestions.json` has non-empty `pending_fan_resolutions`. If
Pass 2 is dispatched (level 1) → instruction-builder (level 2) →
inbox-analyst (level 3), the inner dispatch may fail. The
instruction-builder spec documents an inline-impersonation fallback
for that specific subflow. Normal Pass-2 flow doesn't reach this case.

## Usage

`/inbox` — Auto-detect next action (cleanup → Pass 2 → Pass 1)
`/inbox --pass1` — Force Pass 1 (generate suggestions from captured items)
`/inbox --pass2` — Force Pass 2 (generate instructions from approved suggestions)
`/inbox --cleanup` — Force cleanup (process applied instruction sets)
`/inbox --recover` — Drift recovery: treat captured notes as fresh sources for Pass-1

## --recover Flag

Purpose: recover from drift — the state where captured notes exist in the inbox but no
associated workflow doc (suggestions/instructions) is present. This happens when a
suggestions or instructions file was manually deleted mid-flow, or a run crashed after
`mark-captured.py` ran but before the Suggestions doc was written.

Behaviour:
- Orchestrator treats all `tomo.state=captured` docs as fresh sources for Pass-1.
- Re-runs the synthesis pipeline (Phase B inbox-analyst fan-out) against those captured docs.
- `mark-captured.py` re-asserts `tomo.state=captured` at run end — idempotent no-op.
- No-op if no captured docs exist in the inbox.

Implementation: sets `TOMO_INBOX_RECOVER=1` env var which the orchestrator (inbox-orchestrator.md
A2.5c.1) reads to override the newSources path list with capturedHits paths.

STRICT: --recover MUST be user-initiated. Tomo never auto-recovers silently — it cannot
distinguish drift from a steady-state residual (Hashi cleaned up; captured notes are leftovers
the user will manually file). Auto-recovery risks duplicate suggestions for already-processed
items.

## How It Works

### Step 0 — Resolve the inbox path (ALWAYS FIRST)

Before any `listDir` or scan, resolve the vault-relative inbox path from
`config/vault-config.yaml`. Do NOT hardcode `"Inbox"` or `"100 Inbox/"` —
the path varies per vault. Run:

```bash
python3 scripts/read-config-field.py --field concepts.inbox --default "100 Inbox/"
```

The stdout is the inbox path (e.g. `100 Inbox/`). Use that literal in every
subsequent `kado-search listDir` call and when dispatching to the orchestrator.
**STRICT:** do not invent a shorter or prettier path like `"Inbox"`.

### Auto-Discovery (default)

After Step 0 resolves the inbox path, the command checks in priority order:

1. **Instruction sets with Applied actions?** → Run cleanup (vault-executor)
   - Scan the resolved inbox path for `*_instructions.md` via Kado `listDir`
     (pass the resolved path, not a literal like `"Inbox"`)
   - Read each, count `- [x] Applied` vs total actions
   - Any with at least one Applied → cleanup
2. **Suggestions with `[x] Approved`?** → Run Pass 2 by **dispatching
   `instruction-builder` via the `Agent` tool** (see STRICT section
   above). Do NOT impersonate it.
   - Scan the resolved inbox path for `*_suggestions.md` via Kado `listDir`
     (this glob matches both primary `*_suggestions.md` and companion
     `*_suggestions-fan.md` for the force-atomic flow)
   - Read each, check for `- [x] Approved` at top
   - When BOTH a primary doc and an approved companion `*_suggestions-fan.md`
     exist, they are a reconciliation pair — `instruction-builder` Step 2
     handles the pairing internally by reading both files into `tomo-tmp/`
     and passing `--fan-resolve-file` to the parser.
   - **Dispatch shape:**
     ```
     Agent({
       subagent_type: "instruction-builder",
       description: "Pass 2 — build instruction set",
       prompt: "Run Pass 2 on the approved suggestions doc(s) in <resolved-inbox>. Follow your agent definition. Report back with the action count + coverage audit result."
     })
     ```
   - The subagent runs on sonnet per its frontmatter; you wait for the
     final result message and surface it to the user.
3. **Captured source items?** → Run Pass 1 by **dispatching
   `inbox-orchestrator` via the `Agent` tool** (see STRICT section above).
   The agent runs Phase 0a → 0b → A → B → C → D itself, dispatching
   `voice-transcriber` and `inbox-analyst` from inside its own context.
   You wait for the agent's final report and surface it to the user.
4. **Nothing pending?** → Report "Inbox clear. Nothing to process."

### Pass 1 — Suggestions (fan-out)

1. `/inbox` → dispatch `inbox-orchestrator` via the `Agent` tool (see
   STRICT section above)
2. Inside the orchestrator subagent: Phase A builds
   `tomo-tmp/shared-ctx.json` and `tomo-tmp/inbox-state.jsonl` via
   Bash calls
3. Phase B: orchestrator dispatches `inbox-analyst` subagents via the
   `Agent` tool in batches of 3-5. Each analyst reads one item,
   classifies it, writes `tomo-tmp/items/<stem>.result.json`, updates
   the state-file
4. Phase C: orchestrator runs `suggestions-reducer.py`, renders markdown,
   writes the final `YYYY-MM-DD_HHMM_suggestions.md` via `kado-write`
5. Document contains visible `- [ ] Approved` checkbox + per-action tri-state
   decision checkboxes (Approve / Skip / Delete source)
6. **You review in Obsidian**, edit, check decisions
7. Check `[x] Approved` when satisfied

### Pass 2 — Instructions

1. **instruction-builder** parses approved suggestions (pure orchestrator — no markdown assembly)
2. `instruction-render.py` deterministically produces rendered notes,
   `instructions.json` (canonical machine-readable — see
   `tomo/schemas/instructions.schema.json`), and `instructions.md`
   (human-readable view, rendered from the JSON)
3. Instruction set + rendered files written to inbox via Kado
4. Per-action `- [ ] Applied` checkboxes (no lifecycle tags)
5. **You apply each action** in Obsidian and check `[x] Applied` per action
   (future: Tomo Hashi plugin reads `instructions.json` directly and executes)
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

This command uses:
- `inbox-orchestrator` — Pass 1 coordinator (dispatched; fan-out: Phase A + B + C)
  - spawns `inbox-analyst` subagents per item (3-5 in parallel)
  - spawns `voice-transcriber` if Phase 0a is enabled and audio is present
- `instruction-builder` — Pass 2 action generation (dispatched)
- `vault-executor` — cleanup and state transitions (impersonated)
