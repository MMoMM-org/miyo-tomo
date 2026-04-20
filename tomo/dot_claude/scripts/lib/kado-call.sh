#!/usr/bin/env bash
# kado-call.sh — Minimal Kado MCP caller for shell scripts.
# version: 0.1.1
#
# Source this file:   . "$(dirname "$0")/lib/kado-call.sh"
#
# Provides:
#   kado_call <tool-name> <json-args>     → response content text (inner JSON) on stdout, exit 0
#                                         → empty + non-zero on error
#
# Resolution order for endpoint + bearer:
#   1. Environment: $KADO_URL and $KADO_TOKEN (if both set, used as-is)
#   2. $CLAUDE_PROJECT_DIR/.mcp.json — read once, cached in process env
#
# The response is SSE-framed; this function unwraps the first `data:` line and
# extracts result.content[0].text as plain text (typically a JSON string the
# caller parses with jq).
#
# Bash 3.2 compatible. Dependencies: curl, jq.

kado_call() {
    local tool="$1"
    local args_json="$2"

    # Resolve endpoint + token on first call (cached in process env).
    if [ -z "${KADO_URL:-}" ] || [ -z "${KADO_TOKEN:-}" ]; then
        local mcp_json="${CLAUDE_PROJECT_DIR:-.}/.mcp.json"
        if [ ! -f "$mcp_json" ]; then
            return 1
        fi
        KADO_URL=$(jq -r '.mcpServers.kado.url // empty' "$mcp_json" 2>/dev/null)
        KADO_TOKEN=$(jq -r '.mcpServers.kado.headers.Authorization // empty' "$mcp_json" 2>/dev/null | sed 's/^Bearer //')
        if [ -z "$KADO_URL" ] || [ -z "$KADO_TOKEN" ]; then
            return 1
        fi
        export KADO_URL KADO_TOKEN
    fi

    local body
    body=$(jq -cn --arg name "$tool" --argjson args "$args_json" \
        '{jsonrpc:"2.0",id:1,method:"tools/call",params:{name:$name,arguments:$args}}')

    local raw
    raw=$(curl -sS -N --max-time 5 "$KADO_URL" \
        -H "Authorization: Bearer $KADO_TOKEN" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "$body" 2>/dev/null) || return 1

    # Empty response (curl failed silently, timeout, etc.)
    if [ -z "$raw" ]; then
        return 1
    fi

    # SSE unwrap: extract first `data:` line's payload.
    local payload
    payload=$(printf '%s' "$raw" | awk '/^data: /{sub(/^data: /,""); print; exit}')
    if [ -z "$payload" ]; then
        payload="$raw"
    fi

    # Must look like JSON to parse.
    case "$payload" in
        '{'*|'['*) ;;
        *) return 1 ;;
    esac

    # Extract inner text content; non-zero if error shape.
    printf '%s' "$payload" | jq -er '.result.content[0].text // empty' 2>/dev/null
}
