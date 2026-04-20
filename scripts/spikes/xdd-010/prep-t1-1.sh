#!/usr/bin/env bash
# prep-t1-1.sh — Install the T1.1 fileSuggestion spike into a Tomo instance.
# version: 0.1.0
#
# After running:
#   1. Restart your Tomo session (begin-tomo.sh)
#   2. Type @CASE_A, @CASE_B, @CASE_C, @CASE_D, @CASE_E in the Tomo prompt
#   3. Record observations in findings.md (this directory)
#   4. Run restore-picker.sh when you're done

set -euo pipefail

SPIKE_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SPIKE_DIR/../../.." && pwd)"
CONFIG="$REPO_ROOT/tomo-install.json"

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: $CONFIG not found. Run install-tomo.sh first." >&2
    exit 1
fi

INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG")
if [ -z "$INSTANCE_PATH" ] || [ ! -d "$INSTANCE_PATH" ]; then
    echo "ERROR: instancePath invalid: $INSTANCE_PATH" >&2
    exit 1
fi

REAL="$INSTANCE_PATH/.claude/scripts/file-suggestion.sh"
BACKUP="$INSTANCE_PATH/.claude/scripts/file-suggestion.sh.real"
SPIKE_SRC="$SPIKE_DIR/spike-exit-codes.sh"

if [ ! -f "$REAL" ]; then
    echo "ERROR: $REAL not found. Run update-tomo.sh first." >&2
    exit 1
fi

if [ ! -f "$SPIKE_SRC" ]; then
    echo "ERROR: Spike source not found: $SPIKE_SRC" >&2
    exit 1
fi

# Back up the real picker (idempotent — keep existing backup)
if [ ! -f "$BACKUP" ]; then
    cp "$REAL" "$BACKUP"
    echo "✓ Backed up real picker → file-suggestion.sh.real"
else
    echo "✓ Backup already exists (keeping it)"
fi

# Install the spike
cp "$SPIKE_SRC" "$REAL"
chmod +x "$REAL"
echo "✓ Installed T1.1 spike into instance"
echo ""
echo "Next steps:"
echo "  1. Restart Tomo:     bash $REPO_ROOT/begin-tomo.sh"
echo "  2. In the Tomo prompt, type:"
echo "       @CASE_A  — exit 0 + valid paths"
echo "       @CASE_B  — exit 0 + empty"
echo "       @CASE_C  — exit 1 + paths"
echo "       @CASE_D  — exit 0 + non-path text"
echo "       @CASE_E  — exit 0 + mixed (for '... + N more' synthetic line)"
echo "       @        — any other query shows a SPIKE-ACTIVE hint"
echo "  3. Record each observation in:"
echo "       $SPIKE_DIR/findings.md"
echo "  4. When done:"
echo "       bash $SPIKE_DIR/restore-picker.sh"
