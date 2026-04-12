#!/usr/bin/env bash
# version: 0.1.0
# tomo-statusline.sh — Tomo status line for Claude Code.
#
# Shows: Model | Context bar | Kado connectivity + tag access
# Kado check is cached for 60 seconds.
#
# Input:  JSON from Claude Code via stdin
# Output: Single formatted line with ANSI colors

set -euo pipefail

# ── Colors ────────────────────────────────────────────────

GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
RESET="\033[0m"

# ── Input ─────────────────────────────────────────────────

IFS= read -r -d '' JSON_INPUT || true

MODEL=$(echo "$JSON_INPUT"   | jq -r '.model.display_name // "?"')
CTX_PCT=$(echo "$JSON_INPUT" | jq -r '.context_window.used_percentage // 0' \
  | cut -d. -f1)

# ── Context bar ──────────────────────────────────────────

block_bar() {
  local pct="$1"
  local color="$GREEN"
  [[ "$pct" -ge 70 ]] && color="$YELLOW"
  [[ "$pct" -ge 90 ]] && color="$RED"
  local filled=$(( pct / 10 ))
  local empty=$(( 10 - filled ))
  printf '%b%s%s%b' "$color" \
    "$(printf "%${filled}s" | tr ' ' '█')" \
    "$(printf "%${empty}s" | tr ' ' '░')" \
    "$RESET"
}

# ── Kado check (cached) ─────────────────────────────────

CACHE_FILE="${TMPDIR:-/tmp}/tomo-statusline-kado"
CACHE_TTL=60

cache_is_stale() {
  [[ ! -f "$1" ]] && return 0
  local mtime now
  # Linux: stat -c %Y, macOS: stat -f %m
  mtime=$(stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0)
  now=$(date +%s)
  [[ $(( now - mtime )) -ge "$CACHE_TTL" ]]
}

kado_check() {
  if ! cache_is_stale "$CACHE_FILE"; then
    cat "$CACHE_FILE"
    return
  fi

  # Read .mcp.json for URL + token
  if [[ ! -f ".mcp.json" ]]; then
    echo "no_config" > "$CACHE_FILE"
    cat "$CACHE_FILE"
    return
  fi

  local url token
  url=$(jq -r '
    .mcpServers.kado.url //
    .mcpServers["miyo-kado"].url //
    empty' .mcp.json 2>/dev/null)
  token=$(jq -r '
    .mcpServers.kado.headers.Authorization //
    .mcpServers["miyo-kado"].headers.Authorization //
    empty' .mcp.json 2>/dev/null | sed 's/^Bearer //')

  if [[ -z "$url" || -z "$token" ]]; then
    echo "no_config" > "$CACHE_FILE"
    cat "$CACHE_FILE"
    return
  fi

  # Normalize endpoint
  local endpoint="${url%/}"
  [[ "$endpoint" != */mcp ]] && endpoint="$endpoint/mcp"

  # Test 1: connectivity — listDir root
  local payload='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"kado-search","arguments":{"operation":"listDir","path":"/","depth":1,"limit":1}}}'
  local response
  response=$(curl -s --max-time 2 -X POST "$endpoint" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -H "Accept: application/json" \
    -d "$payload" 2>/dev/null) || true

  if [[ -z "$response" ]]; then
    echo "unreachable" > "$CACHE_FILE"
    cat "$CACHE_FILE"
    return
  fi

  # Check for RPC or tool error
  local is_error
  is_error=$(echo "$response" | jq -r '
    if .error then "rpc"
    elif .result.isError then "tool"
    else "ok" end' 2>/dev/null)

  if [[ "$is_error" != "ok" ]]; then
    echo "error" > "$CACHE_FILE"
    cat "$CACHE_FILE"
    return
  fi

  # Test 2: tag access — read tag_prefix from vault-config, search by tag
  local tag_prefix=""
  if [[ -f "config/vault-config.yaml" ]]; then
    tag_prefix=$(grep -m1 'tag_prefix:' config/vault-config.yaml \
      | sed 's/.*tag_prefix:[[:space:]]*//' | tr -d '"' | tr -d "'" || true)
  fi

  if [[ -n "$tag_prefix" ]]; then
    local tag_query="#${tag_prefix}"
    local tag_payload
    tag_payload=$(jq -n --arg q "$tag_query" '{
      jsonrpc: "2.0", id: 2,
      method: "tools/call",
      params: {name: "kado-search", arguments: {operation: "byTag", query: $q, limit: 1}}
    }')
    local tag_response
    tag_response=$(curl -s --max-time 2 -X POST "$endpoint" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $token" \
      -H "Accept: application/json" \
      -d "$tag_payload" 2>/dev/null) || true

    if [[ -n "$tag_response" ]]; then
      local tag_text
      tag_text=$(echo "$tag_response" | jq -r '.result.content[0].text // ""' 2>/dev/null)
      if echo "$tag_text" | grep -qi "forbidden\|denied\|not.allowed"; then
        echo "tags_denied" > "$CACHE_FILE"
        cat "$CACHE_FILE"
        return
      fi
    fi
  fi

  echo "ok" > "$CACHE_FILE"
  cat "$CACHE_FILE"
}

# ── Render ────────────────────────────────────────────────

KADO_STATUS=$(kado_check)

LINE="${CYAN}[${MODEL}]${RESET}"
LINE+=" | 🧠 $(block_bar "$CTX_PCT") ${CTX_PCT}%"

case "$KADO_STATUS" in
  ok)          LINE+=" | ${GREEN}Kado ✓${RESET}" ;;
  tags_denied) LINE+=" | ${YELLOW}Kado ✓ Tags ✗${RESET}" ;;
  unreachable) LINE+=" | ${RED}Kado ✗${RESET}" ;;
  error)       LINE+=" | ${RED}Kado ✗${RESET}" ;;
  no_config)   LINE+=" | ${YELLOW}Kado ?${RESET}" ;;
  *)           LINE+=" | ${YELLOW}Kado ?${RESET}" ;;
esac

echo -e "$LINE"
