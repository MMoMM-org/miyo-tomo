#!/usr/bin/env bash
# file-suggestion.sh — custom @-picker for Tomo instance
# version: 0.1.0
#
# Spec: docs/XDD/specs/010-custom-file-picker/
#
# Reads `{"query": "<text>"}` from stdin and emits up to 15 newline-separated
# file paths to stdout. Routes by query prefix:
#   /inbox <text> → cached Kado-search of inbox
#   /vault <text> → fzf on cached vault file list
#   <anything>    → kado-open-notes (active first)
#
# Bash 3.2 compatible. Always exits 0 (non-zero would make Claude Code fall
# back to its built-in picker, which scans the wrong directory in the Tomo
# instance — graceful empty result is better).

set -u

# ── Config ────────────────────────────────────────────────────────────
MAX_RESULTS=15
CACHE_DIR="${TOMO_CACHE_DIR:-${CLAUDE_PROJECT_DIR:-.}/cache}"
INBOX_CACHE_TTL=30      # seconds
VAULT_CACHE_TTL=3600    # seconds (1h)

# ── Handler stubs (Phase 2 will replace these) ────────────────────────

handle_open_notes() {
    # Phase 2 T2.1 will replace this with a kado-open-notes call.
    printf 'STUB-open-notes:%s\n' "$1"
}

handle_inbox() {
    # Phase 2 T2.2 will replace this with cached kado-search.
    printf 'STUB-inbox:%s\n' "$1"
}

handle_vault() {
    # Phase 2 T2.3 will replace this with fzf on cached vault list.
    printf 'STUB-vault:%s\n' "$1"
}

# ── Read query from stdin ─────────────────────────────────────────────
input=$(cat)
query=$(printf '%s' "$input" | jq -r '.query // ""' 2>/dev/null || printf '')

# ── Route by prefix ───────────────────────────────────────────────────
case "$query" in
    /inbox\ *)  handle_inbox  "${query#/inbox }"  ;;
    /inbox)     handle_inbox  ""                  ;;
    /vault\ *)  handle_vault  "${query#/vault }"  ;;
    /vault)     handle_vault  ""                  ;;
    *)          handle_open_notes "$query"        ;;
esac

exit 0
