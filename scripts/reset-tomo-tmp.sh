#!/bin/bash
# reset-tomo-tmp.sh — Reset the tomo-tmp/ working directory in an instance.
# version: 0.3.0
#
# tomo-tmp/ accumulates state across /inbox phases. This script resets
# to a clean state before a specific phase, so you can re-run from that
# point without leftovers from a broken or completed run.
#
# Modes (match the routing-plan action vocabulary):
#
#   --all          Nuclear. Wipes everything including voice/ and archive/.
#                  Use when you want a totally clean instance.
#
#   --transcribe   Reset to before transcription. Clears voice summary
#                  so voice-precheck runs fresh. Transcripts in the vault
#                  are untouched (Kado-managed, not local files).
#
#   --pass1        Reset to before Pass 1 (suggest action). Clears triage
#                  output, routing plan, items, shared-ctx, state file,
#                  inbox-cache, tag-handler staging, and any orphaned result
#                  files. Keeps voice/ so transcription doesn't re-run.
#
#   --fan-resolve  Reset fan-resolve outputs only. Clears fan-specific
#                  items and suggestions-fan files. Keeps the parent
#                  suggestions doc and non-fan items intact.
#
#   --pass2        Reset to before Pass 2 (synthesize action). Clears
#                  parsed suggestions and rendered output. Keeps the
#                  approved suggestions docs and state file intact.
#                  This is the default (most common after editing
#                  suggestions.md in Obsidian).
#
# Usage:
#   ./scripts/reset-tomo-tmp.sh                    # --pass2 default
#   ./scripts/reset-tomo-tmp.sh --pass1
#   ./scripts/reset-tomo-tmp.sh --all
#   ./scripts/reset-tomo-tmp.sh --dry-run --pass1
#   ./scripts/reset-tomo-tmp.sh --instance ./other-instance/tomo-tmp
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
        --pass2)        MODE="pass2";       shift ;;
        --pass1)        MODE="pass1";       shift ;;
        --fan-resolve)  MODE="fan-resolve";  shift ;;
        --transcribe)   MODE="transcribe";  shift ;;
        --all)          MODE="all";         shift ;;
        --dry-run)      DRY_RUN=true;       shift ;;
        --instance)     INSTANCE_TMP="$2";  shift 2 ;;
        -h|--help)
            sed -n '1,44p' "$0"
            exit 0 ;;
        *)
            echo "error: unknown argument: $1" >&2
            echo "use -h for usage" >&2
            exit 2 ;;
    esac
done

# ── Resolve tomo-tmp path ──────────────────────────────────

if [ -z "$INSTANCE_TMP" ]; then
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

removed=0

remove() {
    local target="$1"
    [ -e "$target" ] || return 0
    if [ "$DRY_RUN" = "true" ]; then
        printf "  [dry-run] would remove: %s\n" "${target#"$INSTANCE_TMP"/}"
    else
        rm -rf "$target"
        printf "  - removed: %s\n" "${target#"$INSTANCE_TMP"/}"
    fi
    removed=$((removed + 1))
}

remove_glob() {
    local pattern="$1"
    local found=0
    for f in $pattern; do
        [ -e "$f" ] || continue
        remove "$f"
        found=$((found + 1))
    done
}

print_header() {
    local label="$MODE"
    if [ "$DRY_RUN" = "true" ]; then
        echo "DRY-RUN reset-tomo-tmp ($label)"
    else
        echo "reset-tomo-tmp ($label)"
    fi
}

# ── Mode: --all ───────────────────────────────────────────

reset_all() {
    remove "$INSTANCE_TMP/voice"
    remove "$INSTANCE_TMP/archive"
    reset_pass1
}

# ── Mode: --transcribe ────────────────────────────────────

reset_transcribe() {
    remove "$INSTANCE_TMP/voice/summary.json"
}

# ── Mode: --pass1 ─────────────────────────────────────────

reset_pass1() {
    # Triage output
    remove "$INSTANCE_TMP/routing-plan.json"
    remove "$INSTANCE_TMP/inbox-cache"

    # Run state
    remove "$INSTANCE_TMP/run-id.txt"
    remove "$INSTANCE_TMP/.run_id"
    remove "$INSTANCE_TMP/inbox-state.jsonl"
    remove "$INSTANCE_TMP/shared-ctx.json"

    # Pass 1 results
    remove "$INSTANCE_TMP/items"
    remove_glob "$INSTANCE_TMP/item-*.result.json"

    # Tag-handler staging (per-run; carries no run_id, so stale groups from a
    # prior run would otherwise leak into the next suggestions doc)
    remove "$INSTANCE_TMP/tag-handler-groups"
    remove "$INSTANCE_TMP/tag-handler-group-stubs.json"

    # Suggestions docs (local copies)
    remove "$INSTANCE_TMP/suggestions.md"
    remove "$INSTANCE_TMP/suggestions-doc.json"
    remove "$INSTANCE_TMP/suggestions-rendered.md"
    remove "$INSTANCE_TMP/suggestions-wire.json"

    # Fan-resolve docs
    remove "$INSTANCE_TMP/suggestions-fan.md"
    remove "$INSTANCE_TMP/suggestions-fan-doc.json"
    remove "$INSTANCE_TMP/suggestions-fan-rendered.md"

    # Pass 2 outputs
    reset_pass2
}

# ── Mode: --fan-resolve ───────────────────────────────────

reset_fan_resolve() {
    remove "$INSTANCE_TMP/suggestions-fan.md"
    remove "$INSTANCE_TMP/suggestions-fan-doc.json"
    remove "$INSTANCE_TMP/suggestions-fan-rendered.md"
}

# ── Mode: --pass2 ─────────────────────────────────────────

reset_pass2() {
    remove "$INSTANCE_TMP/parsed-suggestions.json"
    remove "$INSTANCE_TMP/rendered"
}

# ── Execute ───────────────────────────────────────────────

print_header

case "$MODE" in
    all)         reset_all ;;
    transcribe)  reset_transcribe ;;
    pass1)       reset_pass1 ;;
    fan-resolve) reset_fan_resolve ;;
    pass2)       reset_pass2 ;;
esac

if [ "$removed" -eq 0 ]; then
    echo "  (nothing to remove — already clean)"
fi

echo ""
if [ "$DRY_RUN" = "true" ]; then
    echo "Dry-run complete. Re-run without --dry-run to apply."
else
    remaining=$(ls -1 "$INSTANCE_TMP" 2>/dev/null | wc -l | tr -d ' ')
    echo "Done. tomo-tmp has $remaining item(s) remaining."
fi
