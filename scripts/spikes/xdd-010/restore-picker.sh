#!/usr/bin/env bash
# restore-picker.sh — Restore the real file-suggestion.sh after a spike.
# version: 0.1.0

set -euo pipefail

SPIKE_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SPIKE_DIR/../../.." && pwd)"
CONFIG="$REPO_ROOT/tomo-install.json"

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: $CONFIG not found." >&2
    exit 1
fi

INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG")
REAL="$INSTANCE_PATH/.claude/scripts/file-suggestion.sh"
BACKUP="$INSTANCE_PATH/.claude/scripts/file-suggestion.sh.real"

if [ ! -f "$BACKUP" ]; then
    echo "ERROR: No backup found at $BACKUP." >&2
    echo "Run update-tomo.sh to re-copy the real picker from the source." >&2
    exit 1
fi

mv "$BACKUP" "$REAL"
chmod +x "$REAL"
echo "✓ Restored real file-suggestion.sh"
echo "  Restart Tomo to pick up the restored picker."
