#!/bin/bash
# reset-tomo-tmp.sh — Reset the tomo-tmp/ working directory in an instance.
# version: 0.1.0
#
# tomo-tmp/ holds Pass-1 + Pass-2 working state inside a Tomo instance:
# inbox-state.jsonl, items/<stem>.result.json, shared-ctx.json,
# suggestions{,-doc,-rendered,-fan{,-doc,-rendered}}{.json,.md},
# parsed-suggestions.json, rendered/<files>, voice/summary.json.
#
# Manual cleanup between test runs is error-prone and easy to forget.
# This script gives three reset modes:
#
#   --pass2    Clear ONLY Pass-2 outputs. Keeps Pass-1 state intact so
#              you can re-run Pass 2 against the existing approved
#              suggestions.md without redoing analysis.
#              Removes: parsed-suggestions.json, rendered/
#
#   --pass1    Full reset for a fresh Pass 1. Removes everything
#              EXCEPT archive/ (history) and voice/ subdirs (so
#              transcripts don't have to re-run unless they're stale).
#              Removes: parsed-suggestions.json, rendered/, items/,
#              shared-ctx.json, inbox-state.jsonl, all suggestions*
#              files, .run_id, voice/summary.json
#
#   --all      Nuclear option. Same as --pass1 PLUS clears archive/
#              and voice/ models. Use when you want a totally clean
#              state including run history.
#
# By default, runs --pass2 (the most common case after editing
# suggestions.md). The script always reports what was removed.
#
# Usage:
#   ./scripts/reset-tomo-tmp.sh                # --pass2 default
#   ./scripts/reset-tomo-tmp.sh --pass2
#   ./scripts/reset-tomo-tmp.sh --pass1
#   ./scripts/reset-tomo-tmp.sh --all
#   ./scripts/reset-tomo-tmp.sh --instance ./other-instance/tomo-tmp
#   ./scripts/reset-tomo-tmp.sh --dry-run --pass1
#
# Exit codes:
#   0 — reset completed (or --dry-run reported what would happen)
#   1 — instance / tomo-tmp directory not found
#   2 — argument error

set -e

# ── Defaults ───────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTANCE_TMP=""
MODE="pass2"
DRY_RUN=false

# ── CLI parsing ────────────────────────────────────────────

while [ $# -gt 0 ]; do
    case "$1" in
        --pass2)     MODE="pass2";     shift ;;
        --pass1)     MODE="pass1";     shift ;;
        --all)       MODE="all";       shift ;;
        --dry-run)   DRY_RUN=true;     shift ;;
        --instance)  INSTANCE_TMP="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,40p' "$0"
            exit 0 ;;
        *)
            echo "error: unknown argument: $1" >&2
            echo "use -h for usage" >&2
            exit 2 ;;
    esac
done

# ── Resolve tomo-tmp path ──────────────────────────────────

if [ -z "$INSTANCE_TMP" ]; then
    # Read from tomo-install.json if present, else default location
    if [ -f "$REPO_ROOT/tomo-install.json" ]; then
        INSTANCE_PATH=$(python3 -c "
import json, sys
try:
    d = json.load(open('$REPO_ROOT/tomo-install.json'))
    print(d.get('install_path') or '')
except Exception:
    pass
")
        if [ -n "$INSTANCE_PATH" ]; then
            INSTANCE_TMP="$INSTANCE_PATH/tomo-tmp"
        fi
    fi
    if [ -z "$INSTANCE_TMP" ]; then
        INSTANCE_TMP="$REPO_ROOT/tomo-instance/tomo-tmp"
    fi
fi

if [ ! -d "$INSTANCE_TMP" ]; then
    echo "error: tomo-tmp not found at $INSTANCE_TMP" >&2
    echo "       pass --instance <path> or run from a repo with tomo-install.json" >&2
    exit 1
fi

# ── Helpers ────────────────────────────────────────────────

remove() {
    local target="$1"
    [ -e "$target" ] || return 0
    if [ "$DRY_RUN" = "true" ]; then
        printf "  [dry-run] would remove: %s\n" "$target"
    else
        rm -rf "$target"
        printf "  ✓ removed: %s\n" "${target#$INSTANCE_TMP/}"
    fi
}

print_header() {
    if [ "$DRY_RUN" = "true" ]; then
        echo "▸ DRY-RUN — reset-tomo-tmp ($MODE) on $INSTANCE_TMP"
    else
        echo "▸ Reset tomo-tmp ($MODE) on $INSTANCE_TMP"
    fi
}

# ── Mode-specific removals ─────────────────────────────────

# Pass-2 outputs (always cleared in every mode)
PASS2_TARGETS=(
    "$INSTANCE_TMP/parsed-suggestions.json"
    "$INSTANCE_TMP/rendered"
)

# Pass-1 outputs (cleared in --pass1 and --all)
PASS1_TARGETS=(
    "$INSTANCE_TMP/items"
    "$INSTANCE_TMP/shared-ctx.json"
    "$INSTANCE_TMP/inbox-state.jsonl"
    "$INSTANCE_TMP/suggestions.md"
    "$INSTANCE_TMP/suggestions-rendered.md"
    "$INSTANCE_TMP/suggestions-doc.json"
    "$INSTANCE_TMP/suggestions-fan.md"
    "$INSTANCE_TMP/suggestions-fan-rendered.md"
    "$INSTANCE_TMP/suggestions-fan-doc.json"
    "$INSTANCE_TMP/.run_id"
    "$INSTANCE_TMP/voice/summary.json"
)

# Nuclear (only --all)
ALL_TARGETS=(
    "$INSTANCE_TMP/archive"
    "$INSTANCE_TMP/voice"
)

print_header
echo ""

# Pass-2 outputs (always)
for t in "${PASS2_TARGETS[@]}"; do
    remove "$t"
done

# Pass-1 outputs (--pass1 / --all)
if [ "$MODE" = "pass1" ] || [ "$MODE" = "all" ]; then
    for t in "${PASS1_TARGETS[@]}"; do
        remove "$t"
    done
fi

# Nuclear (--all)
if [ "$MODE" = "all" ]; then
    for t in "${ALL_TARGETS[@]}"; do
        remove "$t"
    done
fi

echo ""
if [ "$DRY_RUN" = "true" ]; then
    echo "▸ Dry-run complete. Re-run without --dry-run to actually remove."
else
    echo "▸ Reset complete. tomo-tmp now contains:"
    ls -1 "$INSTANCE_TMP" 2>/dev/null | sed 's/^/    /'
fi
