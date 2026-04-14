#!/usr/bin/env bash
# test-splash.sh — Preview the Tomo splash screen (logo above tagline).
# version: 0.2.0

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOGO_FILE="$REPO_ROOT/assets/tomo-small-logo-50.txt"

# ── Colors ────────────────────────────────────────────────

if [ -t 1 ]; then
    C_RESET="\033[0m"
    C_BOLD="\033[1m"
    C_DIM="\033[2m"
    C_MAGENTA_BOLD="\033[1;35m"
    C_CYAN="\033[36m"
else
    C_RESET="" C_BOLD="" C_DIM="" C_MAGENTA_BOLD="" C_CYAN=""
fi

# ── Version ───────────────────────────────────────────────

VERSION="$(grep -m1 '^# version:' "$REPO_ROOT/tomo/.claude/rules/project-context.md" 2>/dev/null \
    | sed 's/^# version: *//' || echo '0.0.0')"

# ── Render ────────────────────────────────────────────────

if [ ! -f "$LOGO_FILE" ]; then
    echo "error: logo file not found: $LOGO_FILE" >&2
    exit 1
fi

# Strip leading and trailing blank lines from the logo, then print.
printf "\n"
awk '
    { lines[NR] = $0 }
    END {
        first = 1
        while (first <= NR && lines[first] ~ /^[[:space:]]*$/) first++
        last = NR
        while (last >= first && lines[last] ~ /^[[:space:]]*$/) last--
        for (i = first; i <= last; i++) print lines[i]
    }
' "$LOGO_FILE"
printf "\n"

# Text roughly centered under the 50-column logo.
# Kanji 友 renders as 2 cells, so indent compensates.
printf "               %b友  MiYo Tomo%b %bv%s%b\n" \
    "$C_MAGENTA_BOLD" "$C_RESET" "$C_DIM" "$VERSION" "$C_RESET"
printf "           %bPersonal Knowledge Companion%b\n" "$C_CYAN" "$C_RESET"
printf "             AI handles processes,\n"
printf "                 not decisions\n"
