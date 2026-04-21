#!/usr/bin/env bash
# file-suggestion-v2.sh — unified picker (rg-snippet pattern applied to Kado)
# version: 0.1.0
#
# Prototype. Alternative to file-suggestion.sh — if this feels right, we
# promote it by swapping the settings.json command.
#
# Model (no scope prefixes):
#   @          → open notes + ALL inbox + ALL vault (head 15)
#   @<query>   → same set → fzf --filter "<query>" → head 15
#
# Why this shape:
#   - Empty @ still shows open notes first (active context wins)
#   - Partial query drills across all sources with one fzf pass
#   - No `inbox/` / `vault/` prefix UX (removes the "press space / backspace"
#     inserted-text friction observed with prefix selection)
#   - Dedupe preserves open-notes priority (awk !seen)
#
# Bash 3.2 compatible. Always exits 0. Same cache + kado-call lib as v1.

set -u

MAX_RESULTS=15
CACHE_DIR="${TOMO_CACHE_DIR:-${CLAUDE_PROJECT_DIR:-.}/cache}"
INBOX_CACHE_TTL=30       # seconds
VAULT_CACHE_TTL=3600     # seconds (1h)
VAULT_SCAN_PAGE=500
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# kado-call shared helper
if [ -f "$SCRIPT_DIR/lib/kado-call.sh" ]; then
    . "$SCRIPT_DIR/lib/kado-call.sh"
else
    kado_call() { return 1; }
fi

mkdir -p "$CACHE_DIR" 2>/dev/null

# Portable stat: GNU first, BSD fallback (see memory reference_stat_bsd_gnu_portability).
stat_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || printf 0; }

cache_fresh() {
    [ -f "$1" ] || return 1
    local age=$(( $(date +%s) - $(stat_mtime "$1") ))
    [ "$age" -lt "$2" ]
}

resolve_inbox_path() {
    local config="${CLAUDE_PROJECT_DIR:-.}/config/vault-config.yaml"
    local fallback="100 Inbox/"
    [ -f "$config" ] || { printf '%s' "$fallback"; return; }
    local reader="${CLAUDE_PROJECT_DIR:-.}/scripts/read-config-field.py"
    if [ -f "$reader" ]; then
        local val
        val=$(python3 "$reader" --field concepts.inbox --default "$fallback" 2>/dev/null)
        [ -n "$val" ] && { printf '%s' "$val"; return; }
    fi
    printf '%s' "$fallback"
}

# rebuild_listdir_cache <cache-file> <vault-path>
rebuild_listdir_cache() {
    local cache="$1"
    local kpath="$2"
    local tmp="$cache.tmp.$$"
    : > "$tmp"
    local cursor=""
    local safety=50
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

ensure_inbox_cache() {
    local cache="$CACHE_DIR/inbox-files.txt"
    cache_fresh "$cache" "$INBOX_CACHE_TTL" && return 0
    local inbox
    inbox=$(resolve_inbox_path)
    rebuild_listdir_cache "$cache" "$inbox" 2>/dev/null || return 1
}

ensure_vault_cache() {
    local cache="$CACHE_DIR/vault-files.txt"
    local sentinel="$CACHE_DIR/.invalidate-vault-files"
    [ -f "$sentinel" ] && rm -f "$cache" "$sentinel"
    cache_fresh "$cache" "$VAULT_CACHE_TTL" && return 0
    rebuild_listdir_cache "$cache" "/" 2>/dev/null || return 1
}

# Emit paths: open-notes (active first) → inbox (cache) → vault (cache)
collect_candidates() {
    # Open notes
    local resp
    resp=$(kado_call kado-open-notes '{"scope":"all"}' 2>/dev/null) && \
        printf '%s' "$resp" | jq -r '
            (.notes // [])
            | (map(select(.active==true)) + map(select(.active!=true)))
            | .[].path
        ' 2>/dev/null

    ensure_inbox_cache 2>/dev/null || true
    [ -f "$CACHE_DIR/inbox-files.txt" ] && cat "$CACHE_DIR/inbox-files.txt"

    ensure_vault_cache 2>/dev/null || true
    [ -f "$CACHE_DIR/vault-files.txt" ] && cat "$CACHE_DIR/vault-files.txt"
}

# Apply query filter: fzf if present, grep fallback, nothing on empty query
apply_filter() {
    local q="$1"
    if [ -z "$q" ]; then
        cat
    elif command -v fzf >/dev/null 2>&1; then
        fzf --filter "$q" 2>/dev/null
    else
        grep -i -F -- "$q" || true
    fi
}

# ── Main ──────────────────────────────────────────────────────────────
input=$(cat)
query=$(printf '%s' "$input" | jq -r '.query // ""' 2>/dev/null || printf '')

output=$(collect_candidates | awk 'NF && !seen[$0]++' | apply_filter "$query" | head -n "$MAX_RESULTS")

printf '%s' "$output"
[ -n "$output" ] && printf '\n'

# Debug log (same shape as v1, so we can compare)
if [ -z "${TOMO_PICKER_NO_LOG:-}" ]; then
    log="$CACHE_DIR/picker-debug.log"
    if ! : >> "$log" 2>/dev/null; then
        log="${HOME:-/tmp}/.tomo-picker-debug.log"
    fi
    {
        printf '\n=== v2 %s uid=%s ===\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(id -u 2>/dev/null || printf '?')"
        printf 'parsed-query=%q  output-lines=%d\n' \
            "$query" \
            "$(printf '%s' "$output" | grep -c '' 2>/dev/null || printf 0)"
        printf '%s\n' "$output" | head -n 5 | sed 's/^/  > /'
    } >> "$log" 2>/dev/null || true
fi

exit 0
