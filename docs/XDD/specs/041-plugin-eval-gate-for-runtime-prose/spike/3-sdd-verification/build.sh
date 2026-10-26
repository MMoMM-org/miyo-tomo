#!/bin/bash
# Verification spike for spec 041 SDD: assemble a throwaway "tomo" plugin with
# the conductor at main, the two spike cases, and one probe case.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
SEED="$REPO/docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/spike/2-conductor-cases"
P="$HERE/tomo"

rm -rf "$P"
mkdir -p "$P/.claude-plugin" "$P/agents" "$P/evals"
printf '{ "name": "tomo" }\n' > "$P/.claude-plugin/plugin.json"
git -C "$REPO" show "main:tomo/dot_claude/agents/synthesis-conductor.md" > "$P/agents/synthesis-conductor.md"
cp -R "$SEED/evals/audit-gates-delivery" "$SEED/evals/audit-mismatch-stops" "$P/evals/"

# Probe case: can the scaffold see files next to it, and is match: contains valid?
C="$P/evals/scaffold-probe"
mkdir -p "$C/graders"
printf 'SIBLING-MARKER-5d2e\n' > "$C/sibling.txt"
cat > "$C/scaffold.sh" <<'EOF'
#!/bin/bash
{
  echo "dollar0=$0"
  echo "bash_source=${BASH_SOURCE[0]}"
  echo "pwd=$(pwd)"
  d="$(dirname "$0")"
  echo "dirname_listing:"; ls -la "$d" 2>&1
  echo "sibling:"; cat "$d/sibling.txt" 2>&1
} > probe.txt
EOF
chmod +x "$C/scaffold.sh"
cat > "$C/case.yaml" <<'EOF'
schema_version: "1.1"
name: scaffold-probe
runs: 1
context:
  scaffold_script: scaffold.sh
execution:
  max_turns: 4
  timeout_seconds: 120
  allowed_tools: [Bash]
  prompt: 'Run exactly one command: `cat probe.txt`. Then repeat its full output verbatim as your final message.'
EOF
cat > "$C/graders/1-contains-mode.md" <<'EOF'
---
type: regex
pattern: 'SIBLING-MARKER-5d2e'
match: contains
target: last_message
---
EOF
cat > "$C/graders/2-default-mode.md" <<'EOF'
---
type: regex
pattern: 'dollar0='
target: last_message
---
EOF
echo "built $P"
