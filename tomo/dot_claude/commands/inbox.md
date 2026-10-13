---
name: inbox
description: Run the inbox workflow — triage, then route to the appropriate conductor.
argument-hint: "optional: --pass1 | --pass2 | --force | --recover"
---
# /inbox
# version: 0.20.0

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
python3 scripts/inbox-triage.py $ARGUMENTS
```

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

# STRICT — IMPERSONATE means: read `.claude/agents/suggestion-conductor.md`
# and execute its workflow as yourself. NEVER call `Agent()` for it.
# Why: a dispatched subagent cannot use the Agent tool, so the conductor
# would be unable to dispatch its inbox-analyst leaves.

# STRICT — DISPATCH means the opposite: call `Agent()` and do not run the
# workflow yourself. It applies to synthesis-conductor and voice-transcriber only.
# Why: both are pure script runners, so dispatch keeps their context isolated.

# STRICT — every Agent() call passes `subagent_type`. `name` only labels the
# spawned agent and selects nothing.
# Why: a dispatch without `subagent_type` silently runs general-purpose, which
# has none of the named agent's contract, tools or skills.

### 3b. Synthesize (dispatch)

When action is `synthesize`, dispatch the synthesis-conductor as a subagent:

```
Agent(
  subagent_type: "synthesis-conductor"
  prompt: "Run Pass 2 synthesis. The routing plan is at tomo-tmp/routing-plan.json. Follow your workflow Steps 1-4 exactly."
)
```

Output the synthesis-conductor's report to the user, then exit.

# STRICT — output the report unchanged. Every line beginning `- ⚠️ **` is
# copied character for character, one per line. NEVER put those lines in a
# table, NEVER summarise them, NEVER add commentary in their place.
# Why: the model rebuilt the relay lines as a table and dropped their remedy.

### 4. Transcribe (stop-gate)

When action is `transcribe`:

```
Agent(
  subagent_type: "voice-transcriber"
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
