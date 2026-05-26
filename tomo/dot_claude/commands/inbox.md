---
name: inbox
description: Process inbox items using the 2-pass suggestion/instruction workflow. Auto-detects the next action based on workflow document checkboxes — impersonates instruction-builder when an approved suggestions doc exists, otherwise impersonates inbox-orchestrator to scan captured source items.
argument-hint: "optional: --pass1 | --pass2 | --recover"
---
# /inbox — Process inbox with 2-pass workflow
# version: 0.8.7

Process inbox items using the 2-pass suggestion/instruction workflow.
Auto-detects what to do next based on workflow document checkboxes.

## STRICT — How to Run This Command

| Branch | Agent | How to run |
|--------|-------|------------|
| Pass 2 | `instruction-builder` | **Impersonate** — read `agents/instruction-builder.md` and execute its Workflow in your context. Do NOT dispatch via `Agent` tool. |
| Pass 1 | `inbox-orchestrator` | **Impersonate** — read `agents/inbox-orchestrator.md` and execute its Workflow in your context. Do NOT dispatch via `Agent` tool. |

**Why impersonate both:** F-54 live-test (2026-05-22) proved subagents
cannot use the `Agent` tool at all. When the orchestrator was dispatched
as a subagent, its sidechain transcript reported "the Agent tool is not
available in this execution context" and it fell back to inlining the
`inbox-analyst` work for all 18 items serially — destroying the
parallel fan-out (Phase B's batches of 3–5). Same constraint applies
to `instruction-builder`'s Step 2.5 FAN-resolve dispatch of
`inbox-analyst`: it only works because the MAIN session impersonates
instruction-builder and does the dispatch from there.

**Concrete mapping:**
- `/inbox` (main session) reads `inbox-orchestrator.md` or
  `instruction-builder.md` and executes its workflow directly.
- Inside that workflow, the main session dispatches `inbox-analyst`
  and `voice-transcriber` via the `Agent` tool — those work because
  the dispatch happens from the main session, not from a nested subagent.

This is a 1-level dispatch (main → leaf agents), which is the only
nesting depth the platform supports.


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
subsequent `kado-search listDir` call and when executing the orchestrator's
or instruction-builder's workflow.
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
   - **If at least one matches** → impersonate `instruction-builder`
     (read `agents/instruction-builder.md` and execute its Workflow in
     your context). Step 2.5 may dispatch `inbox-analyst` via the
     `Agent` tool from this main session context. **Done.**
   - **If none match** → continue to Pass 1.

2. **Pass 1 — captured source items?**
   - **No detection at command level — impersonate unconditionally**
     `inbox-orchestrator` (read `agents/inbox-orchestrator.md` and
     execute its Workflow in your context). Phase B dispatches
     `inbox-analyst` and Phase 0a dispatches `voice-transcriber` via
     the `Agent` tool from this main session context. The orchestrator's
     Phase A2.5c truly-empty early-exit handles "nothing to do"
     gracefully (emits "Inbox is empty — nothing to process." to
     stderr and returns).
   - **Why the asymmetry with Pass 2**: Pass 2's signal (an `Approved`
     checkbox in a workflow doc) is a cheap visual scan via `listDir` +
     top-of-file read. Pass 1's signal (`tomo.doc_type=source` +
     `tomo.state=captured`) lives in frontmatter across the whole inbox,
     AND the orchestrator runs its own discovery scan in Phase A.
     Duplicating that scan at the command level would waste a Kado call
     and risk divergence between two discovery paths.
   - Wait for the orchestrator's final report and surface it to the user.
