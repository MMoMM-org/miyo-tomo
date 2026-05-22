# /inbox — Process inbox with 2-pass workflow
# version: 0.8.5

Process inbox items using the 2-pass suggestion/instruction workflow.
Auto-detects what to do next based on workflow document checkboxes.

## STRICT — How to Run This Command

**Dispatch behaviour per branch:**

| Branch | Agent | How to run |
|--------|-------|------------|
| Pass 2 | `instruction-builder` | Dispatch via `Agent` tool |
| Pass 1 | `inbox-orchestrator` | Dispatch via `Agent` tool |

**Dispatch shape for Pass 1:**

```
Agent({
  subagent_type: "inbox-orchestrator",
  description: "Pass 1 — orchestrate inbox synthesis",
  prompt: "Run Pass 1 on the inbox. Follow your agent definition. Pass through TOMO_INBOX_RECOVER=<0|1> per the --recover flag. Report back with the final Suggestions doc path + run summary."
})
```

**Dispatch shape for Pass 2:**

```
Agent({
  subagent_type: "instruction-builder",
  description: "Pass 2 — build instruction set",
  prompt: "Run Pass 2 on the approved suggestions doc(s) in <resolved-inbox>. Follow your agent definition. Report back with the action count + coverage audit result."
})
```


## Usage

`/inbox` — Auto-detect next action (Pass 2 → Pass 1)
`/inbox --pass1` — Force Pass 1 (generate suggestions from captured items)
`/inbox --pass2` — Force Pass 2 (generate instructions from approved suggestions)
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

1. **Pass 2 — suggestions with `[x] Approved`?**
   - **Detection** (cheap pre-check at command level): scan the resolved
     inbox path for `*_suggestions.md` via Kado `listDir` — this glob
     matches both primary `*_suggestions.md` and companion
     `*_suggestions-fan.md` for the force-atomic flow. Read each, check
     for `- [x] Approved` at the top. When BOTH a primary and an
     approved companion `*_suggestions-fan.md` exist, they form a
     reconciliation pair — `instruction-builder` Step 2 handles the
     pairing internally.
   - **If at least one matches** → dispatch `instruction-builder` via
     the `Agent` tool (shape in STRICT section above). Wait for its
     result, surface to the user. **Done.**
   - **If none match** → continue to Pass 1.

2. **Pass 1 — captured source items?**
   - **No detection at command level — dispatch unconditionally** to
     `inbox-orchestrator` via the `Agent` tool (shape in STRICT section
     above). The orchestrator's Phase A2.5c truly-empty early-exit
     handles "nothing to do" gracefully (emits "Inbox is empty —
     nothing to process." to stderr and returns).
   - **Why the asymmetry with Pass 2**: Pass 2's signal (an `Approved`
     checkbox in a workflow doc) is a cheap visual scan via `listDir` +
     top-of-file read. Pass 1's signal (`tomo.doc_type=source` +
     `tomo.state=captured`) lives in frontmatter across the whole inbox,
     AND the orchestrator runs its own discovery scan in Phase A.
     Duplicating that scan at the command level would waste a Kado call
     and risk divergence between two discovery paths.
   - Wait for the orchestrator's final report and surface it to the user.
