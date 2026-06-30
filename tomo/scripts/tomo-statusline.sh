#!/usr/bin/env bash
# version: 0.9.0
# tomo-statusline.sh — Tomo status line for Claude Code.
#
# Shows: Model | 友 instance-name | Context bar | Kado connectivity + tag access | Hashi IDE Bridge
# Kado and Hashi checks are cached for 60 seconds.
#
# Input:  JSON from Claude Code via stdin
# Output: Single formatted line with ANSI colors
#
# NOTE: No set -e / set -u — a statusline must never crash.

# ── Palette + pill rendering ──────────────────────────────
# Segment colors follow the active /theme: read ~/.claude/settings.json →
# themes/<slug>.json overrides, falling back to a built-in palette when no
# custom theme is selected. Style + caps are env-tunable:
#   TOMO_STATUSLINE_STYLE = d (two-tone, default) | c (ghost) | b (powerline)
#   TOMO_STATUSLINE_CAPS  = round (default) | square | none
# Rounded caps need a Nerd Font in the host terminal; square uses block glyphs
# that render anywhere; none omits caps. The container only emits bytes — the
# host terminal does the font rendering (docker run -it attaches the host TTY).

RESET="\033[0m"
STYLE="${TOMO_STATUSLINE_STYLE:-d}"

# Cap glyphs are embedded literally (bash 3.2 has no $'\uXXXX').
case "${TOMO_STATUSLINE_CAPS:-round}" in
  square) CAP_L="▌"; CAP_R="▐" ;;
  none)   CAP_L="";  CAP_R="" ;;
  *)      CAP_L=""; CAP_R="" ;;   # round — Nerd Font powerline half-circles
esac
PL_SEP=""                          # powerline arrow separator (style b)

# "#rrggbb" -> "r;g;b" (decimal). Invalid input -> rc 1, no output.
hex_rgb() {
  local h="${1#\#}"
  [[ "$h" =~ ^[0-9a-fA-F]{6}$ ]] || return 1
  printf '%d;%d;%d' "0x${h:0:2}" "0x${h:2:2}" "0x${h:4:2}"
}

# Read one override token's hex from the active custom theme; empty otherwise.
_SETTINGS="${HOME}/.claude/settings.json"
_THEMES_DIR="${HOME}/.claude/themes"
theme_hex() {
  local tok="$1" slug val
  [[ -f "$_SETTINGS" ]] || return 0
  slug=$(jq -r '.theme // ""' "$_SETTINGS" 2>/dev/null) || return 0
  case "$slug" in custom:*) slug="${slug#custom:}" ;; *) return 0 ;; esac
  [[ -f "$_THEMES_DIR/$slug.json" ]] || return 0
  val=$(jq -r --arg k "$tok" '.overrides[$k] // ""' "$_THEMES_DIR/$slug.json" 2>/dev/null) || return 0
  [[ "$val" =~ ^#[0-9a-fA-F]{6}$ ]] && printf '%s' "$val"
}
# token, fallback-hex -> "r;g;b" (theme value wins; fallback when absent)
pick_rgb() {
  local hx; hx=$(theme_hex "$1"); hx="${hx:-$2}"; hex_rgb "$hx"
}

# Segment palette (brand tokens for identity, state tokens for status).
RGB_MODEL=$(pick_rgb claude      "#22d3ee")   # model      (brand)
RGB_INST=$(pick_rgb  skill       "#c084fc")   # 友 instance (brand)
RGB_OK=$(pick_rgb    success     "#4ade80")   # ok    / green
RGB_WARN=$(pick_rgb  warning     "#fbbf24")   # warn  / amber
RGB_ERR=$(pick_rgb   error       "#f87171")   # error / red
RGB_INK=$(pick_rgb   inverseText "#0b0b14")   # dark text on bright pills
RGB_DIM="120;120;130"                          # empty bar / subtle

# Escape builders — emit literal \033 sequences for the final `echo -e`.
_fg() { echo -n "\033[38;2;$1m"; }
_bg() { echo -n "\033[48;2;$1m"; }

# pill <rgb> <label> -> one rendered segment (escaped, for echo -e).
# The label carries its own glyph (門:port etc.) so kanji+port stay contiguous.
# Style b returns a *filled* body WITHOUT caps/separators — the line assembler
# threads those so segments connect into one powerline.
pill() {
  local rgb="$1" label="$2"
  case "$STYLE" in
    c)  # ghost: colored caps + colored text, no fill
        echo -n "$(_fg "$rgb")${CAP_L} ${label} ${CAP_R}${RESET}" ;;
    b)  # powerline: filled body, ink text (caps/separators added by assembler)
        echo -n "$(_bg "$rgb")$(_fg "$RGB_INK") ${label} ${RESET}" ;;
    *)  # d (two-tone): solid filled pill, rounded caps, ink text
        echo -n "$(_fg "$rgb")${CAP_L}$(_bg "$rgb")$(_fg "$RGB_INK") ${label} ${RESET}$(_fg "$rgb")${CAP_R}${RESET}" ;;
  esac
}

# ── Input ─────────────────────────────────────────────────

IFS= read -r -d '' JSON_INPUT || true
JSON_INPUT="${JSON_INPUT:-{\}}"

MODEL=$(echo "$JSON_INPUT"   | jq -r '.model.display_name // "?"' 2>/dev/null || echo "?")
CTX_PCT=$(echo "$JSON_INPUT" | jq -r '.context_window.used_percentage // 0' 2>/dev/null \
  | cut -d. -f1)
CTX_PCT="${CTX_PCT:-0}"

# ── Context bar ──────────────────────────────────────────

ctx_bar() {
  # pct -> an 8-cell block bar "████░░░░". The pill color conveys the state
  # (ok/warn/crit); the bar conveys the fill level. Block glyphs render in any
  # font, so this stays readable with or without a Nerd Font.
  local pct="${1:-0}" filled empty bar="" i
  filled=$(( (pct + 6) / 13 ))
  [[ $filled -lt 0 ]] && filled=0
  [[ $filled -gt 8 ]] && filled=8
  empty=$(( 8 - filled ))
  for (( i=0; i<filled; i++ )); do bar+="█"; done
  for (( i=0; i<empty;  i++ )); do bar+="░"; done
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

  # Test 2: frontmatter read access — byFrontmatter tomo.state=captured probe
  # ADR-6/F6-AC3: probe verifies READ access via a known tomo.state value;
  # empty result on a fresh vault is fine — the call succeeding is the signal.
  # Does NOT read lifecycle.tag_prefix from vault-config (ADR-6).
  local fm_payload
  fm_payload=$(jq -n '{
    jsonrpc: "2.0", id: 2,
    method: "tools/call",
    params: {name: "kado-search", arguments: {operation: "byFrontmatter", query: "tomo.state=captured", limit: 1}}
  }' 2>/dev/null) || true

  if [[ -n "$fm_payload" ]]; then
    local fm_response
    fm_response=$(kado_post "$fm_payload") || true

    if [[ -n "$fm_response" ]]; then
      local fm_text
      fm_text=$(echo "$fm_response" | jq -r '.result.content[0].text // ""' 2>/dev/null) || true
      if echo "$fm_text" | grep -qi "forbidden\|denied\|not.allowed" 2>/dev/null; then
        write_status "tags_denied"
        return
      fi
    fi
  fi

  write_status "ok"
}

# Parse Kado port from .mcp.json URL — sets global KADO_PORT.
# Re-reads .mcp.json rather than threading the URL out of kado_check because
# kado_check returns early on a cache hit (no URL was parsed in that path).
# Re-reading the tiny local file cleanly covers both the cache-hit and live paths.
read_kado_port() {
  local url
  url=$(jq -r '
    .mcpServers.kado.url //
    .mcpServers["miyo-kado"].url //
    empty' .mcp.json 2>/dev/null) || true
  if [[ -n "$url" ]]; then
    # Extract port: match :<digits> before optional /
    KADO_PORT=$(echo "$url" | sed 's|.*:\([0-9][0-9]*\).*|\1|' 2>/dev/null) || true
    # Validate: sed returns the full string unchanged when there is no match —
    # reject any non-numeric result so we never render e.g. 門:http://...
    [[ "$KADO_PORT" =~ ^[0-9]+$ ]] || KADO_PORT="?"
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

  # Multiple locks = ambiguous — show yellow no_config, never pick one arbitrarily.
  # Mirrors the entrypoint's fail-fast-on-multiple-locks posture.
  if [[ "$lock_count" -gt 1 ]]; then
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

  # TCP-probe the real host upstream <host>:<port> — ≤3s timeout, crash-proof.
  # Target is host.docker.internal (the host where Hashi listens), NOT 127.0.0.1:
  # inside the container 127.0.0.1:<port> is the socat listener, which accepts
  # unconditionally before its upstream connect() — probing it yields a false
  # green whenever socat runs, regardless of Hashi (#48). HASHI_PROBE_HOST is an
  # injectable override for tests; default resolves via the docker --add-host
  # host-gateway mapping.
  local probe_host="${HASHI_PROBE_HOST:-host.docker.internal}"
  local probe_rc=1
  ( timeout 3 bash -c ": </dev/tcp/${probe_host}/${port}" ) 2>/dev/null
  probe_rc=$?

  if [[ "$probe_rc" -eq 0 ]]; then
    write_hashi_status "ok:${port}"
  else
    write_hashi_status "unreachable:${port}"
  fi
}

# ── Instance identity ────────────────────────────────────

INSTANCE_LABEL=""
if [[ -n "${TOMO_INSTANCE_NAME:-}" ]]; then
  INSTANCE_LABEL="$TOMO_INSTANCE_NAME"
elif [[ -n "${TOMO_INSTANCE_DIR:-}" ]]; then
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

# Collect segments (parallel rgb + label arrays) in render order. Optional
# segments (instance, Hashi) are simply not appended when absent.
SEG_RGB=()
SEG_LBL=()

SEG_RGB+=("$RGB_MODEL"); SEG_LBL+=("✦ ${MODEL}")

if [[ -n "$INSTANCE_LABEL" ]]; then
  SEG_RGB+=("$RGB_INST"); SEG_LBL+=("友 ${INSTANCE_LABEL}")
fi

CTX_RGB="$RGB_OK"
[[ "$CTX_PCT" -ge 70 ]] && CTX_RGB="$RGB_WARN"
[[ "$CTX_PCT" -ge 90 ]] && CTX_RGB="$RGB_ERR"
SEG_RGB+=("$CTX_RGB"); SEG_LBL+=("🧠 $(ctx_bar "$CTX_PCT") ${CTX_PCT}%")

case "$KADO_STATUS" in
  ok)          SEG_RGB+=("$RGB_OK");   SEG_LBL+=("門:${KADO_PORT} ✓") ;;
  tags_denied) SEG_RGB+=("$RGB_WARN"); SEG_LBL+=("門:${KADO_PORT} ✓ Tags ✗") ;;
  unreachable) SEG_RGB+=("$RGB_ERR");  SEG_LBL+=("門:${KADO_PORT} ✗") ;;
  error)       SEG_RGB+=("$RGB_ERR");  SEG_LBL+=("門:${KADO_PORT} ✗") ;;
  *)           SEG_RGB+=("$RGB_WARN"); SEG_LBL+=("門:${KADO_PORT} ?") ;;
esac

# Hashi segment is shown ONLY when the IDE bridge is in use — i.e. a lock file
# exists (ok/unreachable). When not configured/active, omit it entirely.
case "$HASHI_STATE" in
  ok)          SEG_RGB+=("$RGB_OK");  SEG_LBL+=("橋:${HASHI_PORT} ✓") ;;
  unreachable) SEG_RGB+=("$RGB_ERR"); SEG_LBL+=("橋:${HASHI_PORT} ✗") ;;
  *)           : ;;
esac

# ── Assemble by style ────────────────────────────────────
LINE=""
SEG_N="${#SEG_RGB[@]}"
if [[ "$STYLE" == "b" ]]; then
  # Connected powerline: rounded outer caps + arrow separators that blend each
  # segment's color into the next.
  LINE+="$(_fg "${SEG_RGB[0]}")${CAP_L}"
  i=0
  while [[ "$i" -lt "$SEG_N" ]]; do
    LINE+="$(_bg "${SEG_RGB[$i]}")$(_fg "$RGB_INK") ${SEG_LBL[$i]} "
    j=$(( i + 1 ))
    if [[ "$j" -lt "$SEG_N" ]]; then
      LINE+="$(_fg "${SEG_RGB[$i]}")$(_bg "${SEG_RGB[$j]}")${PL_SEP}"
    else
      LINE+="${RESET}$(_fg "${SEG_RGB[$i]}")${CAP_R}${RESET}"
    fi
    i="$j"
  done
else
  # d (two-tone) / c (ghost): self-contained pills, space-separated.
  i=0
  while [[ "$i" -lt "$SEG_N" ]]; do
    [[ "$i" -gt 0 ]] && LINE+=" "
    LINE+="$(pill "${SEG_RGB[$i]}" "${SEG_LBL[$i]}")"
    i=$(( i + 1 ))
  done
fi

echo -e "$LINE"
