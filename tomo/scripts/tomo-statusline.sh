#!/usr/bin/env bash
# version: 0.5.0
# tomo-statusline.sh — Tomo status line for Claude Code.
#
# Shows: Model | 友 instance-name | Context bar | Kado connectivity + tag access | Hashi IDE Bridge
# Kado and Hashi checks are cached for 60 seconds.
#
# Input:  JSON from Claude Code via stdin
# Output: Single formatted line with ANSI colors
#
# NOTE: No set -e / set -u — a statusline must never crash.

# ── Colors ────────────────────────────────────────────────

GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
MAGENTA_BOLD="\033[1;35m"
RESET="\033[0m"

# ── Input ─────────────────────────────────────────────────

IFS= read -r -d '' JSON_INPUT || true
JSON_INPUT="${JSON_INPUT:-{\}}"

MODEL=$(echo "$JSON_INPUT"   | jq -r '.model.display_name // "?"' 2>/dev/null || echo "?")
CTX_PCT=$(echo "$JSON_INPUT" | jq -r '.context_window.used_percentage // 0' 2>/dev/null \
  | cut -d. -f1)
CTX_PCT="${CTX_PCT:-0}"

# ── Context bar ──────────────────────────────────────────

block_bar() {
  local pct="${1:-0}"
  local filled_char="🟩" empty_char="⬜"
  [[ "$pct" -ge 70 ]] && filled_char="🟨"
  [[ "$pct" -ge 90 ]] && filled_char="🟥"
  local filled=$(( pct / 10 ))
  local empty=$(( 10 - filled ))
  local bar=""
  for (( i=0; i<filled; i++ )); do bar+="$filled_char"; done
  for (( i=0; i<empty; i++ )); do bar+="$empty_char"; done
  echo -n "$bar"
}

# ── Kado check (cached) ─────────────────────────────────

CACHE_FILE="${TMPDIR:-/tmp}/tomo-statusline-kado"
CACHE_TTL=60

# KADO_PORT is set as a side-effect of kado_check — threaded to the render.
KADO_PORT=""

cache_is_stale() {
  [[ ! -f "$1" ]] && return 0
  local mtime now
  # Linux: stat -c %Y, macOS: stat -f %m
  mtime=$(stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0)
  now=$(date +%s)
  [[ $(( now - mtime )) -ge "$CACHE_TTL" ]]
}

write_status() {
  echo "$1" > "$CACHE_FILE" 2>/dev/null
  echo "$1"
}

kado_check() {
  # Return cached result if fresh
  if ! cache_is_stale "$CACHE_FILE"; then
    cat "$CACHE_FILE" 2>/dev/null || echo "unknown"
    return
  fi

  # Read .mcp.json for URL + token
  if [[ ! -f ".mcp.json" ]]; then
    write_status "no_config"
    return
  fi

  local url token
  url=$(jq -r '
    .mcpServers.kado.url //
    .mcpServers["miyo-kado"].url //
    empty' .mcp.json 2>/dev/null) || true
  token=$(jq -r '
    .mcpServers.kado.headers.Authorization //
    .mcpServers["miyo-kado"].headers.Authorization //
    empty' .mcp.json 2>/dev/null | sed 's/^Bearer //') || true

  if [[ -z "$url" || -z "$token" ]]; then
    write_status "no_config"
    return
  fi

  # Normalize endpoint — .mcp.json may already include /mcp
  local endpoint="${url%/}"
  [[ "$endpoint" != */mcp ]] && endpoint="$endpoint/mcp"

  # Helper: POST to Kado and extract JSON from SSE response.
  # Kado returns Content-Type: text/event-stream with format:
  #   event: message
  #   data: {"jsonrpc":"2.0",...}
  kado_post() {
    local raw
    raw=$(curl -s --max-time 3 -X POST "$endpoint" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $token" \
      -H "Accept: application/json, text/event-stream" \
      -d "$1" 2>/dev/null) || true
    [[ -z "$raw" ]] && return 1
    # Extract JSON: if SSE format, grab the data: line; otherwise use as-is
    if echo "$raw" | grep -q '^data: ' 2>/dev/null; then
      echo "$raw" | grep '^data: ' | head -1 | sed 's/^data: //'
    else
      echo "$raw"
    fi
  }

  # Test 1: connectivity — listDir root
  local response
  response=$(kado_post '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"kado-search","arguments":{"operation":"listDir","path":"/","depth":1,"limit":1}}}') || true

  if [[ -z "$response" ]]; then
    write_status "unreachable"
    return
  fi

  # Check for RPC or tool error
  local is_error
  is_error=$(echo "$response" | jq -r '
    if .error then "rpc"
    elif .result.isError then "tool"
    else "ok" end' 2>/dev/null) || true

  if [[ "$is_error" != "ok" ]]; then
    write_status "error"
    return
  fi

  # Test 2: tag access — read tag_prefix from vault-config, search by tag
  local tag_prefix=""
  if [[ -f "config/vault-config.yaml" ]]; then
    tag_prefix=$(grep -m1 'tag_prefix:' config/vault-config.yaml 2>/dev/null \
      | sed 's/.*tag_prefix:[[:space:]]*//' | tr -d '"' | tr -d "'") || true
  fi

  if [[ -n "$tag_prefix" ]]; then
    local tag_payload
    tag_payload=$(jq -n --arg q "#${tag_prefix}" '{
      jsonrpc: "2.0", id: 2,
      method: "tools/call",
      params: {name: "kado-search", arguments: {operation: "byTag", query: $q, limit: 1}}
    }' 2>/dev/null) || true

    if [[ -n "$tag_payload" ]]; then
      local tag_response
      tag_response=$(kado_post "$tag_payload") || true

      if [[ -n "$tag_response" ]]; then
        local tag_text
        tag_text=$(echo "$tag_response" | jq -r '.result.content[0].text // ""' 2>/dev/null) || true
        if echo "$tag_text" | grep -qi "forbidden\|denied\|not.allowed" 2>/dev/null; then
          write_status "tags_denied"
          return
        fi
      fi
    fi
  fi

  write_status "ok"
}

# Parse Kado port from .mcp.json URL — sets global KADO_PORT.
# Called after kado_check so .mcp.json is known to exist when status != no_config.
read_kado_port() {
  local url
  url=$(jq -r '
    .mcpServers.kado.url //
    .mcpServers["miyo-kado"].url //
    empty' .mcp.json 2>/dev/null) || true
  if [[ -n "$url" ]]; then
    # Extract port: match :<digits> before optional /
    KADO_PORT=$(echo "$url" | sed 's|.*:\([0-9][0-9]*\).*|\1|' 2>/dev/null) || true
  fi
  [[ -z "$KADO_PORT" ]] && KADO_PORT="?"
}

# ── Hashi check (cached) ─────────────────────────────────

HASHI_CACHE_FILE="${TMPDIR:-/tmp}/tomo-statusline-hashi"

# Result written as "<status>:<port>", e.g. "ok:23027" or "no_config"
write_hashi_status() {
  echo "$1" > "$HASHI_CACHE_FILE" 2>/dev/null
  echo "$1"
}

hashi_check() {
  # Return cached result if fresh
  if ! cache_is_stale "$HASHI_CACHE_FILE"; then
    cat "$HASHI_CACHE_FILE" 2>/dev/null || echo "no_config"
    return
  fi

  # "Configured" iff exactly one lock file exists at $HOME/.claude/ide/*.lock
  local ide_dir="${HOME}/.claude/ide"
  if [[ ! -d "$ide_dir" ]]; then
    write_hashi_status "no_config"
    return
  fi

  # Count lock files
  local lock_count=0
  local lock_file=""
  for f in "${ide_dir}"/*.lock; do
    [[ -f "$f" ]] || continue
    lock_count=$(( lock_count + 1 ))
    lock_file="$f"
  done

  if [[ "$lock_count" -eq 0 ]]; then
    write_hashi_status "no_config"
    return
  fi

  # Port comes from the lock filename: <port>.lock
  local port
  port=$(basename "$lock_file" .lock 2>/dev/null) || true
  if [[ -z "$port" ]]; then
    write_hashi_status "no_config"
    return
  fi

  # TCP-probe 127.0.0.1:<port> — ≤3s timeout, crash-proof
  local probe_rc=1
  ( timeout 3 bash -c ": </dev/tcp/127.0.0.1/${port}" ) 2>/dev/null
  probe_rc=$?

  if [[ "$probe_rc" -eq 0 ]]; then
    write_hashi_status "ok:${port}"
  else
    write_hashi_status "unreachable:${port}"
  fi
}

# ── Instance identity ────────────────────────────────────

INSTANCE_LABEL=""
if [[ -n "${TOMO_INSTANCE_DIR:-}" ]]; then
  INSTANCE_LABEL=$(basename "$TOMO_INSTANCE_DIR")
fi

# ── Render ────────────────────────────────────────────────

KADO_STATUS=$(kado_check)

# Parse Kado port from .mcp.json (after status is known)
if [[ -f ".mcp.json" ]]; then
  read_kado_port
fi
[[ -z "$KADO_PORT" ]] && KADO_PORT="?"

HASHI_STATUS=$(hashi_check)

# Split hashi status and port: format is "<status>:<port>" or "no_config"
HASHI_STATE="${HASHI_STATUS%%:*}"
HASHI_PORT="${HASHI_STATUS#*:}"
# When no colon, HASHI_PORT equals HASHI_STATUS — normalize to "?"
[[ "$HASHI_PORT" == "$HASHI_STATUS" ]] && HASHI_PORT="?"

LINE="${CYAN}[${MODEL}]${RESET}"
if [[ -n "$INSTANCE_LABEL" ]]; then
  LINE+=" | ${MAGENTA_BOLD}友${RESET} ${INSTANCE_LABEL}"
fi
LINE+=" | 🧠 $(block_bar "$CTX_PCT") ${CTX_PCT}%"

case "$KADO_STATUS" in
  ok)          LINE+=" | ${GREEN}門:${KADO_PORT} ✓${RESET}" ;;
  tags_denied) LINE+=" | ${YELLOW}門:${KADO_PORT} ✓ Tags ✗${RESET}" ;;
  unreachable) LINE+=" | ${RED}門:${KADO_PORT} ✗${RESET}" ;;
  error)       LINE+=" | ${RED}門:${KADO_PORT} ✗${RESET}" ;;
  no_config)   LINE+=" | ${YELLOW}門:${KADO_PORT} ?${RESET}" ;;
  *)           LINE+=" | ${YELLOW}門:${KADO_PORT} ?${RESET}" ;;
esac

case "$HASHI_STATE" in
  ok)          LINE+=" | ${GREEN}橋:${HASHI_PORT} ✓${RESET}" ;;
  unreachable) LINE+=" | ${RED}橋:${HASHI_PORT} ✗${RESET}" ;;
  *)           LINE+=" | ${YELLOW}橋:${HASHI_PORT} ?${RESET}" ;;
esac

echo -e "$LINE"
