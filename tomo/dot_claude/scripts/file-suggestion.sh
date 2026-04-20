#!/usr/bin/env bash
# file-suggestion.sh — custom @-picker for Tomo instance
# version: 0.3.0
#
# Spec: docs/XDD/specs/010-custom-file-picker/
#
# Reads `{"query": "<text>"}` from stdin and emits up to 15 newline-separated
# file paths to stdout. Routes by query prefix:
#   inbox/<text>  → cached kado-search of inbox folder (30s TTL)
#   vault/<text>  → fzf on cached full vault listing (1h TTL + sentinel)
#   <anything>    → kado-open-notes (active first, position-only marker)
#
# Why `inbox/` and `vault/` suffix-slash (not leading `/inbox`):
# Queries that start with `/` trigger Claude Code's built-in absolute-path
# completion (showing /boot /dev /etc etc.) and bypass this script entirely.
# Any scope prefix must start with a non-slash character.
#
# Bash 3.2 compatible. Always exits 0 — Claude Code does not fall back to its
# built-in picker on non-zero exit (confirmed T1.1), and non-zero just hides
# our results silently. Best-effort empty response is always preferable.
#
# Active-note marker is position-only: the first emitted line is the active
# note when one exists (suffix-hack rejected, T1.2 decision).
#
# kado-open-notes returns vault-relative paths. Claude Code's @-resolver will
# try to read them as instance-local files and fail with ENOENT; the calling
# Claude session then falls back to kado-read. Decided tradeoff (spec README).

set -u

# ── Config ────────────────────────────────────────────────────────────
MAX_RESULTS=15
MAX_REAL_RESULTS=$MAX_RESULTS    # no "... + N more" synthetic line for MVP
CACHE_DIR="${TOMO_CACHE_DIR:-${CLAUDE_PROJECT_DIR:-.}/cache}"
INBOX_CACHE_TTL=30      # seconds
VAULT_CACHE_TTL=3600    # seconds (1h)
VAULT_SCAN_PAGE=500     # per kado-search page
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Best-effort imports. If lib is missing, we degrade to empty results.
if [ -f "$SCRIPT_DIR/lib/kado-call.sh" ]; then
    . "$SCRIPT_DIR/lib/kado-call.sh"
else
    kado_call() { return 1; }
fi

mkdir -p "$CACHE_DIR" 2>/dev/null

# Detect fzf once (fallback to grep substring if missing).
if command -v fzf >/dev/null 2>&1; then
    FZF_AVAILABLE=1
else
    FZF_AVAILABLE=0
fi

# ── Helpers ───────────────────────────────────────────────────────────

# filter_lines <query>   — stdin: path list, stdout: filtered ≤MAX_RESULTS
filter_lines() {
    local q="$1"
    if [ -z "$q" ]; then
        head -n "$MAX_REAL_RESULTS"
        return
    fi
    if [ "$FZF_AVAILABLE" = "1" ]; then
        fzf --filter "$q" 2>/dev/null | head -n "$MAX_REAL_RESULTS"
    else
        grep -i -F -- "$q" | head -n "$MAX_REAL_RESULTS"
    fi
}

# cache_fresh <path> <ttl_seconds>    — exit 0 if cache exists and is fresh
cache_fresh() {
    local path="$1"
    local ttl="$2"
    [ -f "$path" ] || return 1
    local now mtime age
    now=$(date +%s)
    # Portable mtime: macOS `stat -f %m`, Linux `stat -c %Y`.
    mtime=$(stat -f %m "$path" 2>/dev/null || stat -c %Y "$path" 2>/dev/null || printf 0)
    age=$(( now - mtime ))
    [ "$age" -lt "$ttl" ]
}

# resolve_inbox_path — read concepts.inbox from vault-config.yaml; stdout: path
resolve_inbox_path() {
    local config="${CLAUDE_PROJECT_DIR:-.}/config/vault-config.yaml"
    local fallback="100 Inbox/"
    if [ ! -f "$config" ]; then
        printf '%s' "$fallback"
        return
    fi
    local reader="${CLAUDE_PROJECT_DIR:-.}/scripts/read-config-field.py"
    if [ -x "$reader" ] || [ -f "$reader" ]; then
        local val
        val=$(python3 "$reader" --field concepts.inbox --default "$fallback" 2>/dev/null)
        [ -n "$val" ] && { printf '%s' "$val"; return; }
    fi
    # Last-resort: line-grep. Matches `  inbox: "100 Inbox/"` under concepts:.
    local val
    val=$(awk '/^concepts:/{in_c=1;next} /^[^ ]/{in_c=0} in_c && /^  inbox:/{sub(/^  inbox:[[:space:]]*/,"");gsub(/^["'"'"']|["'"'"']$/,"");print;exit}' "$config" 2>/dev/null)
    if [ -n "$val" ]; then
        printf '%s' "$val"
    else
        printf '%s' "$fallback"
    fi
}

# rebuild_listdir_cache <cache> <kado_path>
#   Populates <cache> with .md file paths from a recursive listDir.
#   Cursor-paginates in VAULT_SCAN_PAGE-sized pages. Atomic rename.
rebuild_listdir_cache() {
    local cache="$1"
    local kpath="$2"
    local tmp="$cache.tmp.$$"
    : > "$tmp"
    local cursor=""
    local safety=50   # hard cap — ~25k files max
    while [ "$safety" -gt 0 ]; do
        safety=$(( safety - 1 ))
        local args
        if [ -n "$cursor" ]; then
            args=$(jq -cn --arg p "$kpath" --arg c "$cursor" --argjson lim "$VAULT_SCAN_PAGE" \
                '{operation:"listDir",path:$p,depth:99,limit:$lim,cursor:$c}')
        else
            args=$(jq -cn --arg p "$kpath" --argjson lim "$VAULT_SCAN_PAGE" \
                '{operation:"listDir",path:$p,depth:99,limit:$lim}')
        fi
        local resp
        resp=$(kado_call kado-search "$args") || { rm -f "$tmp"; return 1; }
        printf '%s' "$resp" | jq -r '.items[] | select(.type=="file" and (.name | endswith(".md"))) | .path' >> "$tmp" 2>/dev/null || true
        cursor=$(printf '%s' "$resp" | jq -r '.nextCursor // empty' 2>/dev/null)
        [ -z "$cursor" ] && break
    done
    mv "$tmp" "$cache"
}

# ── Handlers ──────────────────────────────────────────────────────────

handle_open_notes() {
    local q="$1"
    local resp
    resp=$(kado_call kado-open-notes '{"scope":"all"}') || return 0
    # Sort: active first (at most one), then others in Kado's order. Optional
    # substring filter on path basename when the user typed text alongside @.
    local jq_filter='
        (.notes // [])
        | (map(select(.active==true)) + map(select(.active!=true)))
        | map(.path)
    '
    if [ -n "$q" ]; then
        jq_filter="$jq_filter"' | map(select(ascii_downcase | contains($q | ascii_downcase)))'
        printf '%s' "$resp" | jq -r --arg q "$q" "$jq_filter | .[]" 2>/dev/null | head -n "$MAX_REAL_RESULTS"
    else
        printf '%s' "$resp" | jq -r "$jq_filter | .[]" 2>/dev/null | head -n "$MAX_REAL_RESULTS"
    fi
}

handle_inbox() {
    local q="$1"
    local cache="$CACHE_DIR/inbox-files.txt"
    if ! cache_fresh "$cache" "$INBOX_CACHE_TTL"; then
        local inbox
        inbox=$(resolve_inbox_path)
        rebuild_listdir_cache "$cache" "$inbox" 2>/dev/null || { [ -f "$cache" ] || return 0; }
    fi
    [ -f "$cache" ] || return 0
    filter_lines "$q" < "$cache"
}

handle_vault() {
    local q="$1"
    local cache="$CACHE_DIR/vault-files.txt"
    local sentinel="$CACHE_DIR/.invalidate-vault-files"
    if [ -f "$sentinel" ]; then
        rm -f "$cache" "$sentinel"
    fi
    if ! cache_fresh "$cache" "$VAULT_CACHE_TTL"; then
        rebuild_listdir_cache "$cache" "/" 2>/dev/null || { [ -f "$cache" ] || return 0; }
    fi
    [ -f "$cache" ] || return 0
    filter_lines "$q" < "$cache"
}

# ── Read query + route ────────────────────────────────────────────────

input=$(cat)
query=$(printf '%s' "$input" | jq -r '.query // ""' 2>/dev/null || printf '')

case "$query" in
    inbox/*)    handle_inbox       "${query#inbox/}"   ;;
    vault/*)    handle_vault       "${query#vault/}"   ;;
    *)          handle_open_notes  "$query"            ;;
esac

exit 0
