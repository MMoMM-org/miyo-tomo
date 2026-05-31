#!/bin/bash
# configure-ide-bridge.sh — Stateful Tomo Context (Hashi IDE Bridge) wizard for install/update.
# Sourced from install-tomo.sh and update-tomo.sh. Relies on the sourcing
# script providing print_step / print_ok / print_warn / print_err helpers.
#
# Sets globals on successful run:
#   IDE_BRIDGE_ENABLED — "true" or "false"
#   IDE_BRIDGE_TOKEN   — hashi_<uuid> string (auth token for the bridge)
#   IDE_BRIDGE_PORT    — port number as string (default 23027)
# version: 0.3.1

_IDE_BRIDGE_SCHEMA_VERSION=1
_IDE_BRIDGE_DEFAULT_PORT=23027

# Persist the IDE_BRIDGE_* globals into a target JSON file's `.ide_bridge`
# block via jq. Mirrors write_voice_config — write-to-.tmp-then-mv pattern.
#
# Usage: write_ide_bridge_config <target-json-file>
write_ide_bridge_config() {
    local target="$1"
    if [ -z "$target" ]; then
        echo "write_ide_bridge_config: missing target file" >&2
        return 2
    fi
    if [ ! -f "$target" ]; then
        echo "write_ide_bridge_config: target does not exist: $target" >&2
        return 2
    fi
    jq --argjson schema "$_IDE_BRIDGE_SCHEMA_VERSION" \
       --argjson enabled "${IDE_BRIDGE_ENABLED:-false}" \
       --arg      tok    "${IDE_BRIDGE_TOKEN:-}" \
       --argjson  port   "${IDE_BRIDGE_PORT:-$_IDE_BRIDGE_DEFAULT_PORT}" \
       '.ide_bridge = { schema_version: $schema, enabled: $enabled, auth_token: $tok, port: $port }' \
       "$target" > "$target.tmp" && mv "$target.tmp" "$target"
}

# Write the IDE lock file at <home>/.claude/ide/<port>.lock.
# Directory is created at 0700; the file is NOT chmod 600 (ADR-4).
# workspace_path (4th arg): the container-side instance path; populates
# workspaceFolders so Claude Code's active workspace matches the container cwd
# (begin-tomo mounts the instance at the same path via -v $IP:$IP + -w $IP).
# Omitting the 4th arg or passing empty yields workspaceFolders: [] (backward-safe).
#
# Usage: write_ide_lock <home_dir> <port> <token> [workspace_path]
write_ide_lock() {
    local home_dir="$1"
    local port="$2"
    local token="$3"
    local workspace_path="${4:-}"
    local ide_dir="${home_dir}/.claude/ide"
    mkdir -p "$ide_dir"
    chmod 700 "$ide_dir"
    jq -n \
       --arg tok "$token" \
       --arg ws  "$workspace_path" \
       '{ pid: 0, workspaceFolders: ($ws | if . == "" then [] else [.] end), ideName: "Obsidian", transport: "ws", authToken: $tok }' \
       > "${ide_dir}/${port}.lock"
}

# Remove the IDE lock file for a given port.
#
# Usage: remove_ide_lock <home_dir> <port>
remove_ide_lock() {
    local home_dir="$1"
    local port="$2"
    rm -f "${home_dir}/.claude/ide/${port}.lock"
}

# Validate that the argument is a Hashi auth token: the literal prefix "hashi_"
# followed by a canonical 8-4-4-4-12 hex UUID.
# Trims surrounding whitespace before checking.
# Returns 0 if valid, 1 if not.
_is_hashi_token() {
    local s
    # Trim leading/trailing whitespace (bash 3.2 compatible)
    s="${1#"${1%%[![:space:]]*}"}"
    s="${s%"${s##*[![:space:]]}"}"
    # Strip required "hashi_" prefix; reject anything that doesn't start with it
    case "$s" in
        hashi_*)
            s="${s#hashi_}"
            ;;
        *)
            return 1
            ;;
    esac
    # Validate the UUID portion (8-4-4-4-12 hex groups)
    case "$s" in
        [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]-[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]-[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]-[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]-[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Validate that the argument is an integer in the range 1024..65535.
# Returns 0 if valid, 1 if not.
_is_valid_port() {
    local s="$1"
    case "$s" in
        *[!0-9]*)
            return 1
            ;;
    esac
    if [ -z "$s" ]; then
        return 1
    fi
    local n
    n=$(( s + 0 ))
    if [ "$n" -ge 1024 ] && [ "$n" -le 65535 ]; then
        return 0
    fi
    return 1
}

# Prompt for a valid Hashi auth token (hashi_<uuid>). Re-prompts on invalid input.
# If prior_token is non-empty, user can press Enter to keep it.
#
# Usage: _prompt_token <prior_token>
# Sets global IDE_BRIDGE_TOKEN on success.
_prompt_token() {
    local prior="$1"
    local prompt_hint=""
    if [ -n "$prior" ]; then
        prompt_hint=" [keep: ${prior}]"
    fi
    while true; do
        local raw
        read -rp "  Auth token (hashi_<uuid>)${prompt_hint}: " raw
        # Trim whitespace
        local trimmed
        trimmed="${raw#"${raw%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        if [ -z "$trimmed" ] && [ -n "$prior" ]; then
            IDE_BRIDGE_TOKEN="$prior"
            return 0
        fi
        if _is_hashi_token "$trimmed"; then
            IDE_BRIDGE_TOKEN="$trimmed"
            return 0
        fi
        print_err "Invalid auth token '$trimmed' — expected Hashi format hashi_<uuid> (e.g. hashi_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
    done
}

# Prompt for a valid port number. Re-prompts on invalid input.
# Defaults to _IDE_BRIDGE_DEFAULT_PORT if empty input given.
#
# Usage: _prompt_port <current_port>
# Sets global IDE_BRIDGE_PORT on success.
_prompt_port() {
    local current="${1:-$_IDE_BRIDGE_DEFAULT_PORT}"
    while true; do
        local raw
        read -rp "  Port [${current}]: " raw
        local val="${raw:-$current}"
        if _is_valid_port "$val"; then
            IDE_BRIDGE_PORT="$val"
            return 0
        fi
        print_err "Invalid port '$val' — expected integer in 1024..65535"
    done
}

# Usage:
#   configure_ide_bridge <current_enabled> <current_token> <current_port> \
#                        <home_dir> [non_interactive]
# Where:
#   current_*        — existing state (from tomo-install.json, or "false"/"" for fresh installs)
#   home_dir         — container home dir (lock file written here by the caller)
#   non_interactive  — "true" to suppress all prompts (keeps current state)
configure_ide_bridge() {
    local current_enabled="${1:-false}"
    local current_token="${2:-}"
    local current_port="${3:-$_IDE_BRIDGE_DEFAULT_PORT}"
    local home_dir="${4:-}"
    local non_interactive="${5:-false}"

    IDE_BRIDGE_ENABLED="$current_enabled"
    IDE_BRIDGE_TOKEN="$current_token"
    IDE_BRIDGE_PORT="${current_port:-$_IDE_BRIDGE_DEFAULT_PORT}"

    print_step "Tomo Context"

    if [ "$non_interactive" = "true" ]; then
        if [ "$IDE_BRIDGE_ENABLED" = "true" ]; then
            print_ok "Tomo Context: kept ENABLED (port=$IDE_BRIDGE_PORT)"
        else
            IDE_BRIDGE_ENABLED="false"
            print_ok "Tomo Context: disabled (non-interactive default)"
        fi
        return 0
    fi

    echo "  Tomo Context — connect Hashi (Obsidian plugin) to Claude Code inside the container."
    echo ""

    # ── State dispatch ───────────────────────────────────
    if [ "$IDE_BRIDGE_ENABLED" = "true" ]; then
        echo "  Currently: ENABLED  (port=${IDE_BRIDGE_PORT})"
        echo ""
        echo "    [K] keep current settings"
        echo "    [c] change token or port"
        echo "    [d] disable Tomo Context"
        local choice
        read -rp "  > " choice
        choice="${choice:-K}"
        case "$choice" in
            k|K|keep)
                print_ok "Tomo Context: kept ENABLED"
                return 0
                ;;
            d|D|disable)
                IDE_BRIDGE_ENABLED="false"
                print_ok "Tomo Context: disabled"
                return 0
                ;;
            c|C|change)
                ;;
            *)
                print_warn "Unrecognised choice — keeping current settings"
                return 0
                ;;
        esac
    else
        echo "  Currently: DISABLED"
        echo ""
        local enable
        read -rp "  Enable Tomo Context? [y/N]: " enable
        case "$enable" in
            y|Y|yes)
                IDE_BRIDGE_ENABLED="true"
                ;;
            *)
                IDE_BRIDGE_ENABLED="false"
                print_ok "Tomo Context: remains disabled"
                return 0
                ;;
        esac
    fi

    # ── Token + port collection ──────────────────────────
    echo ""
    _prompt_token "$IDE_BRIDGE_TOKEN"
    _prompt_port  "$IDE_BRIDGE_PORT"

    print_ok "Tomo Context: ENABLED (port=$IDE_BRIDGE_PORT)"
    return 0
}
