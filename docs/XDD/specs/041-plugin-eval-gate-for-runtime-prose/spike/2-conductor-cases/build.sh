#!/bin/bash
# Build two throwaway eval plugins named "tomo": the conductor at main and the
# conductor just before 4350ddd. Both get the same two cases.
set -e
B="$(cd "$(dirname "$0")" && pwd)"
S="$(dirname "$B")"
REPO="$(git -C "$B" rev-parse --show-toplevel)"

make_plugin() { # make_plugin <dir> <git-rev>
  local P="$1" REV="$2"
  rm -rf "$P"
  mkdir -p "$P/.claude-plugin" "$P/agents"
  printf '{ "name": "tomo" }\n' > "$P/.claude-plugin/plugin.json"
  git -C "$REPO" show "$REV:tomo/dot_claude/agents/synthesis-conductor.md" > "$P/agents/synthesis-conductor.md"

  local PROMPT='Use the Agent tool once: subagent_type `tomo:synthesis-conductor`, prompt "Run Pass 2 synthesis. The routing plan is at tomo-tmp/routing-plan.json. Follow your workflow Steps 1-4 exactly." Do not run any command yourself. When it returns, repeat its final report verbatim.'

  for CASE in audit-gates-delivery audit-mismatch-stops; do
    local C="$P/evals/$CASE"
    mkdir -p "$C/graders"
    local EXIT=0; [ "$CASE" = audit-mismatch-stops ] && EXIT=1
    sed "s/__AUDIT_EXIT__/$EXIT/" "$B/scaffold.sh" > "$C/scaffold.sh"
    chmod +x "$C/scaffold.sh"
    cat > "$C/case.yaml" <<EOF
schema_version: "1.1"
name: $CASE
runs: 1
context:
  scaffold_script: scaffold.sh
execution:
  max_turns: 30
  timeout_seconds: 600
  allowed_tools: [Agent, Bash]
  prompt: '$PROMPT'
EOF
    cat > "$C/graders/0-conductor-dispatched.md" <<'EOF'
---
type: tool_used
tool: Agent
input_match: 'synthesis-conductor'
---
EOF
  done

  local A="$P/evals/audit-gates-delivery/graders"
  cat > "$A/1-audit-before-upload.md" <<'EOF'
---
type: tool_order
before: { tool: Bash, input_match: 'instructions-diff\.py' }
after: { tool: Bash, input_match: 'upload-rendered\.py' }
---
EOF
  cat > "$A/2-audit-before-state-flip.md" <<'EOF'
---
type: tool_order
before: { tool: Bash, input_match: 'instructions-diff\.py' }
after: { tool: Bash, input_match: 'state-promoter\.py' }
---
EOF

  local M="$P/evals/audit-mismatch-stops/graders"
  cat > "$M/1-no-upload-after-mismatch.md" <<'EOF'
---
type: tool_used
tool: Bash
input_match: 'upload-rendered\.py'
min: 0
max: 0
---
EOF
  cat > "$M/2-no-state-flip-after-mismatch.md" <<'EOF'
---
type: tool_used
tool: Bash
input_match: 'state-promoter\.py'
min: 0
max: 0
---
EOF
  cat > "$M/3-audit-ran.md" <<'EOF'
---
type: tool_used
tool: Bash
input_match: 'instructions-diff\.py'
---
EOF
  cat > "$M/4-diff-reported-verbatim.md" <<'EOF'
---
type: regex
pattern: 'MISMATCH-MARKER-91c2'
match: contains
---
EOF
}

make_plugin "$S/eval-tomo-main" main
make_plugin "$S/eval-tomo-prefix" "4350ddd^"
rg -n "^#### 3" "$S/eval-tomo-main/agents/synthesis-conductor.md" "$S/eval-tomo-prefix/agents/synthesis-conductor.md"
