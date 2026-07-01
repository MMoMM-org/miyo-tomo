#!/bin/bash
# PreToolUse hook — denies ScheduleWakeup calls that would re-run /inbox.
# version: 0.1.0

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // ""')

if echo "$PROMPT" | grep -qi 'inbox'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Tomo /inbox runs only on explicit user invocation. Do not self-schedule or re-run it via ScheduleWakeup. Report current status to the user and exit; they will re-run /inbox when the prior run has been applied."
    }
  }'
  exit 0
fi

exit 0
