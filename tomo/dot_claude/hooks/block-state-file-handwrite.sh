#!/bin/bash
# PreToolUse hook — denies hand-writes to the fan-out state file.
# version: 0.1.0
#
# Matches Write, Edit and Bash. Write/Edit are judged on file_path; Bash is
# judged on a shell redirect aimed at the file, so reading it (cat, tail) and
# passing it as an argument (state-update.py --state ...) stay allowed.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

REASON="tomo-tmp/inbox-state.jsonl is append-only shared state written by agents running in parallel. Write it with: python3 scripts/state-update.py --state tomo-tmp/inbox-state.jsonl --item-key <item_key> --stem <stem> --path <path> --run-id <run_id> --status <running|done|failed> (add --result <file> on done). Reading the file is fine; producing its lines yourself is not."

case "$TOOL" in
  Write|Edit)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
    case "$FILE_PATH" in
      */inbox-state.jsonl|inbox-state.jsonl)
        deny "$REASON A Write replaces the whole file and drops the entries other agents appended; an Edit rewrites lines another agent may be appending to."
        ;;
    esac
    ;;
  Bash)
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
    # Only a redirect counts. `>` or `>>`, optional whitespace and quoting,
    # then any path ending in inbox-state.jsonl.
    if echo "$COMMAND" | grep -Eq '>>?[[:space:]]*"?'"'"'?[^[:space:]"'"'"']*inbox-state\.jsonl'; then
      deny "$REASON A shell redirect bypasses the schema the script enforces, and the run that did this skipped its own running record."
    fi
    ;;
esac

exit 0
