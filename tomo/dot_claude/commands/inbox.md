---
name: inbox
description: Run the inbox workflow — triage, then route to the appropriate conductor.
argument-hint: "optional: --pass1 | --pass2 | --recover"
---
# /inbox
# version: 0.10.0

## Arguments

- `--pass1` — force Pass 1 (suggest) regardless of inbox state
- `--pass2` — force Pass 2 (synthesize) regardless of inbox state
- `--recover` — treat captured items as fresh (re-process)

## Steps

### 1. Run triage

```bash
python3 scripts/inbox-triage.py [--force-pass1] [--force-pass2] [--recover] --output-dir tomo-tmp
```

Pass through any flags the user provided: `--pass1` → `--force-pass1`, `--pass2` → `--force-pass2`, `--recover` → `--recover`.

### 2. Read routing plan

```bash
cat tomo-tmp/routing-plan.json
```

Extract the `action` field from the JSON output.

### 3. Route on action

| action | Route |
|--------|-------|
| suggest | IMPERSONATE suggestion-conductor |
| fan-resolve | IMPERSONATE suggestion-conductor |
| synthesize | IMPERSONATE synthesis-conductor |
| transcribe | Dispatch voice-transcriber directly (see Step 4) |
| idle | Surface status to user (see Step 5) |

### 4. Transcribe (stop-gate)

When action is `transcribe`:

```
Agent(
  name: "voice-transcriber"
  prompt: "Transcribe audio files in the inbox. inbox_path: <inbox_path from routing-plan.json>"
)
```

After transcription, report: "N transcript(s) created. Review, then re-run /inbox."

Exit. Do NOT continue to any conductor.

### 5. Idle

When action is `idle`:

Read `idle_reasons` and `pending_approval` from `tomo-tmp/routing-plan.json`.

Report to user:
- "Inbox is idle."
- List each idle reason
- If `pending_approval` is non-empty: "Waiting for approval on: [list paths]"

If `drift_indicators` is non-empty, surface those as warnings.

Exit.

# STRICT — IMPERSONATE conductors, NEVER dispatch them via Agent/Task tool.
# Why: Conductors need the Agent tool for leaf dispatch; dispatched subagents cannot use Agent.
