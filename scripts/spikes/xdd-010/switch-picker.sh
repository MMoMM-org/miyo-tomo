#!/usr/bin/env bash
# switch-picker.sh — flip between v1 and v2 file-suggestion picker in the instance.
# version: 0.1.0
#
# Usage:
#   bash scripts/spikes/xdd-010/switch-picker.sh v2   — install v2 (unified)
#   bash scripts/spikes/xdd-010/switch-picker.sh v1   — restore v1 (scope-prefix)
#   bash scripts/spikes/xdd-010/switch-picker.sh status — show which is active
#
# Both scripts live in tomo/dot_claude/scripts/. This script swaps the
# instance's .claude/scripts/file-suggestion.sh between them. Claude Code
# re-reads fileSuggestion on each keystroke, so no Tomo restart needed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CONFIG="$REPO_ROOT/tomo-install.json"
INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG")

V1_SRC="$REPO_ROOT/tomo/dot_claude/scripts/file-suggestion.sh"
V2_SRC="$REPO_ROOT/tomo/dot_claude/scripts/file-suggestion-v2.sh"
TARGET="$INSTANCE_PATH/.claude/scripts/file-suggestion.sh"

mode="${1:-status}"

case "$mode" in
    v2)
        [ -f "$V2_SRC" ] || { echo "ERROR: v2 source not found: $V2_SRC" >&2; exit 1; }
        cp "$V2_SRC" "$TARGET"
        chmod +x "$TARGET"
        echo "✓ Installed v2 (unified, no scope prefixes): $(head -3 "$TARGET" | tail -1)"
        ;;
    v1)
        [ -f "$V1_SRC" ] || { echo "ERROR: v1 source not found: $V1_SRC" >&2; exit 1; }
        cp "$V1_SRC" "$TARGET"
        chmod +x "$TARGET"
        echo "✓ Installed v1 (scope-prefix): $(head -3 "$TARGET" | tail -1)"
        ;;
    status)
        printf 'active: %s\n' "$(head -3 "$TARGET" | tail -1)"
        ;;
    *)
        echo "usage: $0 {v1|v2|status}" >&2
        exit 1
        ;;
esac
