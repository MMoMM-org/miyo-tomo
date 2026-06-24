---
name: inbox
description: Run the inbox workflow — triage, then route to the appropriate conductor.
argument-hint: "optional: --pass1 | --pass2 | --force | --recover"
---
# /inbox
# version: 0.15.0

## Arguments

`--force` is a modifier: combine it with a phase, or use it alone.

- `--pass1` — run Pass 1 (suggest) now, for new sources only
- `--pass2` — run Pass 2 (synthesize), only for uncovered or content-changed docs; idle if everything is already covered
- `--pass1 --force` — re-suggest everything, including already-captured items
- `--pass2 --force` — re-synthesize ALL approved docs, ignoring coverage/drift
- `--force` (alone) — full rebuild: re-suggest (incl. captured), then synthesize all
- `--recover` — treat captured items as fresh (≈ `--pass1 --force`)

## Steps

### 1. Run triage

```bash
python3 scripts/inbox-triage.py [--force-pass1] [--force-pass2] [--force] [--recover] --registry-dir config/tag-handlers --output-dir tomo-tmp
```

Pass through any flags the user provided: `--pass1` → `--force-pass1`, `--pass2` → `--force-pass2`, `--force` → `--force`, `--recover` → `--recover`.

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
| synthesize | DISPATCH synthesis-conductor (see Step 3b) |
| transcribe | Dispatch voice-transcriber directly (see Step 4) |
| idle | Surface status to user (see Step 5) |

### 3b. Synthesize (dispatch)

When action is `synthesize`, dispatch the synthesis-conductor as a subagent:

```
Agent(
  name: "synthesis-conductor"
  prompt: "Run Pass 2 synthesis. The routing plan is at tomo-tmp/routing-plan.json. Follow your workflow Steps 1-4 exactly."
)
```

Report the synthesis-conductor's output to the user. Exit.

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

For any drift indicator with `type` == `orphaned_state`, surface its `detail` prominently as its own line (not buried in the warning list) and recommend running `/inbox --recover`.

Exit.

# STRICT — IMPERSONATE suggestion-conductor (needs Agent tool for leaf dispatch).
# STRICT — DISPATCH synthesis-conductor (pure script runner, no Agent tool needed).
# Why: dispatched subagents cannot use Agent tool. suggestion-conductor dispatches
# inbox-analyst leaf agents so it must be impersonated. synthesis-conductor only
# calls Bash scripts so dispatch is safe and keeps its context isolated.
