#!/bin/bash
# PreToolUse hook — denies ScheduleWakeup. Cancelling one stays allowed.
# version: 0.2.0

INPUT=$(cat)
STOP=$(echo "$INPUT" | jq -r '.tool_input.stop // false')

if [ "$STOP" = "true" ]; then
  exit 0
fi

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: "ScheduleWakeup is not part of any Tomo workflow. Dispatched agents report back on their own — a task-notification arrives for each one, and the harness re-invokes you then. Nothing here needs polling, and /inbox runs only when the user invokes it. Wait for the notifications, or report status and exit."
  }
}'
exit 0
