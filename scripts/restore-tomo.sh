#!/bin/bash
# restore-tomo.sh — Restore a Tomo instance from a backup archive.
# version: 0.1.0
#
# Expects install-tomo.sh to have been run first (the fresh instance + host
# repo scaffolding must exist). This script overwrites user-edited config
# files + home/auth state from the archive.
#
# Usage: bash scripts/restore-tomo.sh <archive.tar.gz> [OPTIONS]
#   --force        Skip confirmation prompts before overwriting
#   --dry-run      List what would be restored without writing
#   --help, -h

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/tomo-install.json"

# ── Colors ────────────────────────────────────────────────

if [ -t 1 ]; then
    C_RESET="\033[0m"; C_BOLD="\033[1m"; C_CYAN="\033[36m"
    C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"
else
    C_RESET=""; C_BOLD=""; C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""
fi

print_step() { printf "\n${C_BOLD}${C_CYAN}▸ %s${C_RESET}\n" "$1"; }
print_ok()   { printf "  ${C_GREEN}✓${C_RESET} %s\n" "$1"; }
print_warn() { printf "  ${C_YELLOW}⚠${C_RESET} %s\n" "$1"; }
print_err()  { printf "  ${C_RED}✗${C_RESET} %s\n" "$1" >&2; }

# ── CLI flags ─────────────────────────────────────────────

ARCHIVE=""
FORCE=false
DRY_RUN=false
SHOW_HELP=false

while [ $# -gt 0 ]; do
    case "$1" in
        --force)   FORCE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) SHOW_HELP=true; shift ;;
        -*)
            print_err "Unknown option: $1"
            echo "Run with --help for usage." >&2
            exit 1
            ;;
        *)
            if [ -z "$ARCHIVE" ]; then ARCHIVE="$1"; else
                print_err "Only one archive path accepted."
                exit 1
            fi
            shift
            ;;
    esac
done

if [ "$SHOW_HELP" = "true" ]; then
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

if [ -z "$ARCHIVE" ]; then
    print_err "Usage: bash scripts/restore-tomo.sh <archive.tar.gz>"
    exit 1
fi

# ── Preconditions ────────────────────────────────────────

if [ ! -f "$ARCHIVE" ]; then
    print_err "Archive not found: $ARCHIVE"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    print_err "No tomo-install.json found. Run install-tomo.sh first."
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    print_err "jq is required but not installed."
    exit 1
fi

INSTANCE_PATH="$(jq -r '.instancePath' "$CONFIG_FILE")"
HOME_DIR="$(jq -r '.homePath // empty' "$CONFIG_FILE")"

if [ ! -d "$INSTANCE_PATH" ]; then
    print_err "Instance directory not found: $INSTANCE_PATH"
    print_err "Run install-tomo.sh to create the target first."
    exit 1
fi

# ── Inspect archive ──────────────────────────────────────

print_step "Inspecting archive"
echo "  Archive: $ARCHIVE"

# Sanity check: archive must contain tomo-install.json at root.
if ! tar -tzf "$ARCHIVE" 2>/dev/null | grep -q '^\./tomo-install\.json$\|^tomo-install\.json$'; then
    print_err "Archive does not contain tomo-install.json at the root — not a Tomo backup?"
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

tar -xzf "$ARCHIVE" -C "$TMP_DIR"
print_ok "Extracted to $TMP_DIR"

echo "  Archive contents:"
find "$TMP_DIR" -maxdepth 3 -mindepth 1 -print 2>/dev/null \
    | sed "s|^$TMP_DIR/|    |"

# ── Confirm overwrite (unless --force) ───────────────────

if [ "$FORCE" != "true" ] && [ "$DRY_RUN" != "true" ]; then
    echo ""
    print_warn "Restore will OVERWRITE:"
    echo "    $CONFIG_FILE"
    echo "    $INSTANCE_PATH/config/"
    echo "    $INSTANCE_PATH/.mcp.json (if present in archive)"
    echo "    $INSTANCE_PATH/.claude/settings.local.json (if present)"
    if [ -n "$HOME_DIR" ] && [ -d "$TMP_DIR/tomo-home" ]; then
        echo "    $HOME_DIR/*"
    fi
    read -rp "  Proceed? [y/N] " CONFIRM
    case "$CONFIRM" in
        [yY]*) ;;
        *) print_warn "Aborted."; exit 0 ;;
    esac
fi

if [ "$DRY_RUN" = "true" ]; then
    print_step "Dry-run — no files written"
    exit 0
fi

# ── Restore files ────────────────────────────────────────

print_step "Restoring files"

restore_file() {
    local src="$1"   # inside TMP_DIR
    local dst="$2"   # target on disk
    if [ -e "$TMP_DIR/$src" ]; then
        mkdir -p "$(dirname "$dst")"
        cp -R "$TMP_DIR/$src" "$dst"
        print_ok "$dst"
    fi
}

# tomo-install.json at repo root
restore_file "tomo-install.json" "$CONFIG_FILE"

# Instance config
if [ -d "$TMP_DIR/tomo-instance/config" ]; then
    rm -rf "$INSTANCE_PATH/config"
    cp -R "$TMP_DIR/tomo-instance/config" "$INSTANCE_PATH/config"
    print_ok "$INSTANCE_PATH/config"
fi

restore_file "tomo-instance/.mcp.json" "$INSTANCE_PATH/.mcp.json"
restore_file "tomo-instance/.claude/settings.local.json" "$INSTANCE_PATH/.claude/settings.local.json"

# Voice config mirror (XDD 009) — restored if present. As a fallback,
# if the mirror is absent from the archive but tomo-install.json has a
# voice block, derive it so runtime agents pick voice back up without
# the user having to re-run update-tomo.sh.
restore_file "tomo-instance/voice/config.json" "$INSTANCE_PATH/voice/config.json"
if [ ! -f "$INSTANCE_PATH/voice/config.json" ] \
   && [ -f "$CONFIG_FILE" ] \
   && command -v jq > /dev/null 2>&1 \
   && [ "$(jq -r '.voice // empty' "$CONFIG_FILE")" != "" ]; then
    mkdir -p "$INSTANCE_PATH/voice"
    jq '.voice' "$CONFIG_FILE" > "$INSTANCE_PATH/voice/config.json"
    print_ok "$INSTANCE_PATH/voice/config.json (derived from tomo-install.json)"
fi

# Home dir (auth) — restore over existing
if [ -d "$TMP_DIR/tomo-home" ] && [ -n "$HOME_DIR" ]; then
    mkdir -p "$HOME_DIR"
    cp -R "$TMP_DIR/tomo-home/." "$HOME_DIR/"
    print_ok "$HOME_DIR/ (auth + Claude Code state)"
fi

print_step "Done"
echo ""
echo "Re-start the Tomo session with: bash begin-tomo.sh"
echo ""
