# /inbox — Process inbox with 2-pass workflow
# version: 0.8.1 (declutter — strip spec refs)

Process inbox items using the 2-pass suggestion/instruction workflow.
Auto-detects what to do next based on workflow document checkboxes.

## STRICT — How to Run This Command

**You (the Claude session reading this command) run the orchestration
logic DIRECTLY in your own context.** The inbox-orchestrator agent
definition at `.claude/agents/inbox-orchestrator.md` is the SPEC you
follow — treat its "Workflow" section as your instructions.

**NEVER** dispatch `inbox-orchestrator` via the `Agent` / `Task` tool.
Nested Agent-dispatches don't work in Claude Code (subagents cannot
spawn further subagents), and the `inbox-orchestrator`'s job requires
fanning out `inbox-analyst` subagents — so if you spawn the
orchestrator as a subagent, Phase B fails with "Agent tool not
available" and the pipeline stalls with no output written.

Concrete mapping:
- `inbox-orchestrator.md` Workflow Phase 0a / 0b / A / B / C → YOUR steps
- Phase B's `inbox-analyst` fan-out → dispatched by YOU via the `Agent`
  tool (3-5 in parallel, per `inbox-orchestrator.md` spec)
- Phase 0a's `voice-transcriber` dispatch (if voice enabled) →
  also by YOU via the `Agent` tool

In other words: the inbox-orchestrator is the ONLY agent on your
workflow that you IMPERSONATE rather than DISPATCH. Every other
subagent mentioned in its spec (`inbox-analyst`, `voice-transcriber`)
is dispatched normally.

`vault-executor` (cleanup) follows the same impersonation rule —
its spec is what you execute in this context.

**EXCEPTION — `instruction-builder` (Pass 2) IS dispatched** via the
`Agent` tool with `subagent_type: "instruction-builder"`. The agent's
happy path does NOT fan out further subagents, so nested-dispatch is
not an issue. Dispatching gives:
- A measurable subagent run on sonnet (per the agent's frontmatter)
  instead of the parent's session model — significantly cheaper for
  pure orchestration work.
- A separate transcript under
  `tomo-home/.claude/projects/<project>/<sid>/subagents/` for clean
  cost attribution.
- Stronger context isolation — the subagent gets only the dispatch
  prompt, not the parent's accumulated /inbox state.

Fan-resolve fallback: instruction-builder's Step 2.5 dispatches
`inbox-analyst` ONLY when `parsed-suggestions.json` has non-empty
`pending_fan_resolutions` — force-atomic items without an atomic
proposal. That nested dispatch may fail; if you hit this rare path,
fall back to impersonating instruction-builder for that one run.
The reconciliation-pair case (when both `_suggestions.md` and
`_suggestions-fan.md` are already approved) does NOT trigger
fan-resolve — Step 2.5 is skipped because there are no pending
resolutions.

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
items. (Per AC-5a.4.)

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
   `instruction-builder` via the `Agent` tool** (see EXCEPTION in the
   STRICT section above). Do NOT impersonate it.
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
3. **Captured source items?** → Run Pass 1 directly in your context,
   following `inbox-orchestrator.md` as your spec (do NOT Agent-dispatch it):
     - Phase 0a: if voice enabled, dispatch `voice-transcriber` via Agent
     - Phase 0b: resume detection via AskUserQuestion (Resume / Fresh / Inspect)
     - Phase A: build shared-ctx + state-file directly (Bash calls)
     - Phase B: dispatch `inbox-analyst` subagents via Agent (3-5 parallel)
     - Phase C: reduce + render + kado-write final Suggestions doc
4. **Nothing pending?** → Report "Inbox clear. Nothing to process."

### Pass 1 — Suggestions (fan-out)

1. `/inbox` → you impersonate the `inbox-orchestrator` spec (NEVER
   Agent-dispatch it — see STRICT section above)
2. Phase A: build `tomo-tmp/shared-ctx.json` and
   `tomo-tmp/inbox-state.jsonl` via Bash calls
3. Phase B: dispatch `inbox-analyst` subagents via the `Agent` tool in
   batches of 3-5. Each subagent reads one item, classifies it, writes
   `tomo-tmp/items/<stem>.result.json`, updates the state-file
4. Phase C: run `suggestions-reducer.py`, render markdown, write the
   final `YYYY-MM-DD_HHMM_suggestions.md` via `kado-write`
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

This command dispatches:
- `inbox-orchestrator` — Pass 1 coordinator (fan-out: Phase A + B + C)
  - spawns `inbox-analyst` subagents per item (3-5 in parallel)
- `instruction-builder` — Pass 2 action generation
- `vault-executor` — cleanup and state transitions

Note: `suggestion-builder` is retired — its format rules live in
`inbox-orchestrator` now.
