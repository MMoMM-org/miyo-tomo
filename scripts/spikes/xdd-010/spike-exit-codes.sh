#!/usr/bin/env bash
# spike-exit-codes.sh — XDD 010 Phase 1 T1.1
# version: 0.2.0
#
# Query-routed spike for testing Claude Code's fileSuggestion behaviour.
# Install ONCE with prep-t1-1.sh, then trigger each case by typing a
# specific @-query in a Tomo session. No script-editing between cases.
#
# Cases:
#   @CASE_A   exit 0 + three valid paths
#   @CASE_B   exit 0 + empty stdout
#   @CASE_C   exit 1 + valid paths (how does Claude Code treat non-zero?)
#   @CASE_D   exit 0 + non-path text (renders? inserts? searches?)
#   @CASE_E   exit 0 + mix of valid + non-path (15th synthetic line viable?)
#   @         or anything else → hint line (spike is active)
#
# Record observations in findings.md. Run restore-picker.sh when done.

set -u

input=$(cat)
query=$(printf '%s' "$input" | jq -r '.query // ""' 2>/dev/null || printf '')

case "$query" in
    CASE_A*)
        # exit 0 + three real paths — expected: picker shows them
        cat <<'EOF'
README.md
CLAUDE.md
docs/XDD/README.md
EOF
        exit 0
        ;;
    CASE_B*)
        # exit 0 + no output — expected: ??? (silent? "no results"?)
        exit 0
        ;;
    CASE_C*)
        # exit 1 + paths — expected: fallback to built-in picker? error banner?
        cat <<'EOF'
README.md
CLAUDE.md
EOF
        exit 1
        ;;
    CASE_D*)
        # exit 0 + non-path strings — what renders? what happens on pick?
        cat <<'EOF'
this is not a real path
neither is this
nor this
EOF
        exit 0
        ;;
    CASE_E*)
        # exit 0 + mix — for checking whether "... + N more" synthetic line
        # is insertable or gets sanitized
        cat <<'EOF'
README.md
(this is a hint, not a path)
CLAUDE.md
... + 42 more (type to filter)
EOF
        exit 0
        ;;
    *)
        # Any other query → hint so user knows spike is active
        printf 'SPIKE-ACTIVE type @CASE_A @CASE_B @CASE_C @CASE_D @CASE_E\n'
        exit 0
        ;;
esac
