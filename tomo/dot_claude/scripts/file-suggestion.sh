#!/usr/bin/env bash
# file-suggestion.sh — custom @-picker for Tomo instance
# version: 0.4.0
#
# Spec: docs/XDD/specs/010-custom-file-picker/
#
# Reads `{"query": "<text>"}` from stdin and emits up to 15 newline-separated
# file paths to stdout. Routes by query prefix:
#   inbox/<text>  → ONLY inbox files (cached kado-search, 30s TTL)
#   vault/<text>  → ONLY vault files (fzf on cached listing, 1h TTL)
#   <empty>       → currently-open Obsidian notes (active first)
#   <text>        → merged: open notes ▶ inbox ▶ vault, deduped, top 15
#
# Why `inbox/` and `vault/` suffix-slash (not leading `/inbox`):
# Queries that start with `/` trigger Claude Code's built-in absolute-path
# completion (showing /boot /dev /etc etc.) and bypass this script entirely.
# Any scope prefix must start with a non-slash character.
#
# Why default-scope is merged: when the user types `@inb`, they likely want
# inbox items, but their open notes don't contain "inb". Merged default
# surfaces matches from every scope so discovery doesn't require memorising
# the `inbox/` prefix. Explicit scopes still exist for narrow filtering.
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

# filter_strict <query>  — stdin: paths, stdout: case-insensitive substring
#                          matches (predictable — used for inbox + merged).
filter_strict() {
    local q="$1"
    if [ -z "$q" ]; then
        cat
        return
    fi
    grep -i -F -- "$q" || true
}

# filter_fuzzy <query>   — stdin: paths, stdout: fzf fuzzy matches (loose —
#                          used only for explicit `vault/<q>` scope).
filter_fuzzy() {
    local q="$1"
    if [ -z "$q" ]; then
        cat
        return
    fi
    if [ "$FZF_AVAILABLE" = "1" ]; then
        fzf --filter "$q" 2>/dev/null
    else
        grep -i -F -- "$q" || true
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

# ── Source emitters (no truncation — caller caps with head) ───────────

emit_open_notes() {
    local q="$1"
    local resp
    resp=$(kado_call kado-open-notes '{"scope":"all"}') || return 0
    # Sort: active first, then others in Kado's order. Substring filter if q.
    local jq_filter='
        (.notes // [])
        | (map(select(.active==true)) + map(select(.active!=true)))
        | map(.path)
    '
    if [ -n "$q" ]; then
        jq_filter="$jq_filter"' | map(select(ascii_downcase | contains($q | ascii_downcase)))'
        printf '%s' "$resp" | jq -r --arg q "$q" "$jq_filter | .[]" 2>/dev/null
    else
        printf '%s' "$resp" | jq -r "$jq_filter | .[]" 2>/dev/null
    fi
}

ensure_inbox_cache() {
    local cache="$CACHE_DIR/inbox-files.txt"
    cache_fresh "$cache" "$INBOX_CACHE_TTL" && return 0
    local inbox
    inbox=$(resolve_inbox_path)
    rebuild_listdir_cache "$cache" "$inbox" 2>/dev/null || return 1
}

emit_inbox() {
    local q="$1"
    local cache="$CACHE_DIR/inbox-files.txt"
    ensure_inbox_cache || { [ -f "$cache" ] || return 0; }
    [ -f "$cache" ] || return 0
    filter_strict "$q" < "$cache"
}

ensure_vault_cache() {
    local cache="$CACHE_DIR/vault-files.txt"
    local sentinel="$CACHE_DIR/.invalidate-vault-files"
    if [ -f "$sentinel" ]; then
        rm -f "$cache" "$sentinel"
    fi
    cache_fresh "$cache" "$VAULT_CACHE_TTL" && return 0
    rebuild_listdir_cache "$cache" "/" 2>/dev/null || return 1
}

emit_vault() {
    # Explicit `vault/<q>` scope only — uses fuzzy match. For the merged
    # default scope, use emit_vault_strict below (substring) instead.
    local q="$1"
    local cache="$CACHE_DIR/vault-files.txt"
    ensure_vault_cache || { [ -f "$cache" ] || return 0; }
    [ -f "$cache" ] || return 0
    filter_fuzzy "$q" < "$cache"
}

emit_vault_strict() {
    local q="$1"
    local cache="$CACHE_DIR/vault-files.txt"
    ensure_vault_cache || { [ -f "$cache" ] || return 0; }
    [ -f "$cache" ] || return 0
    filter_strict "$q" < "$cache"
}

# ── Read query + route ────────────────────────────────────────────────

input=$(cat)
query=$(printf '%s' "$input" | jq -r '.query // ""' 2>/dev/null || printf '')

case "$query" in
    inbox/*)
        emit_inbox "${query#inbox/}" | head -n "$MAX_RESULTS"
        ;;
    vault/*)
        emit_vault "${query#vault/}" | head -n "$MAX_RESULTS"
        ;;
    "")
        # Empty default scope: only open notes (don't flood with vault).
        emit_open_notes "" | head -n "$MAX_RESULTS"
        ;;
    *)
        # Merged default: open notes first (active), then inbox, then vault.
        # Uses strict substring for inbox + vault (predictable in merged
        # scope; fuzzy matching would surface buchstaben-streuung noise).
        # Dedupe (awk !seen) preserves first-seen order, so open always wins.
        {
            emit_open_notes    "$query"
            emit_inbox         "$query"
            emit_vault_strict  "$query"
        } | awk 'NF && !seen[$0]++' | head -n "$MAX_RESULTS"
        ;;
esac

exit 0
