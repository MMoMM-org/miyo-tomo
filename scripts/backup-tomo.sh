#!/bin/bash
# backup-tomo.sh — Archive preservable Tomo instance state.
# version: 0.1.0
#
# Packages user-configured files into a timestamped tar.gz:
#   - tomo-install.json                     (paths, profile, Kado creds)
#   - tomo-instance/config/                 (vault-config.yaml, user-rules/, discovery-cache.yaml)
#   - tomo-instance/.claude/settings.local.json
#   - tomo-instance/.mcp.json
#   - tomo-home/                            (Claude Code auth — skip re-auth on restore)
#
# Excludes regenerable content (managed files from source repo, tomo-tmp/,
# cache/, backups/ itself).
#
# Usage: bash scripts/backup-tomo.sh [OPTIONS]
#   --output PATH   Destination — directory or full file path.
#                   Default: <parent-of-INSTANCE_PATH>/tomo-backups/<instance>-<ts>.tar.gz
#                   (sibling to tomo-instance/, survives `rm -rf tomo-instance`)
#   --keep N        Retain only the N most recent archives for THIS instance
#                   in the output dir. Default: 10.  0 = unlimited.
#   --dry-run       Print what would be archived; do not create file.
#   --help, -h
#
# Archive naming uses the instanceName from tomo-install.json so multiple
# vaults / multiple instances keep their archive sets distinguishable in a
# shared output dir.

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

OUTPUT=""
KEEP=10
DRY_RUN=false
SHOW_HELP=false

while [ $# -gt 0 ]; do
    case "$1" in
        --output)  OUTPUT="$2"; shift 2 ;;
        --keep)    KEEP="$2";   shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) SHOW_HELP=true; shift ;;
        *)
            print_err "Unknown option: $1"
            echo "Run with --help for usage." >&2
            exit 1
            ;;
    esac
done

if [ "$SHOW_HELP" = "true" ]; then
    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

# ── Preconditions ────────────────────────────────────────

if [ ! -f "$CONFIG_FILE" ]; then
    print_err "No tomo-install.json found. Run install-tomo.sh first."
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    print_err "jq is required but not installed."
    exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
    print_err "tar is required but not installed."
    exit 1
fi

INSTANCE_PATH="$(jq -r '.instancePath' "$CONFIG_FILE")"
INSTANCE_NAME="$(jq -r '.instanceName // "tomo-instance"' "$CONFIG_FILE")"
HOME_DIR="$(jq -r '.homePath // empty' "$CONFIG_FILE")"

if [ -z "$INSTANCE_PATH" ] || [ ! -d "$INSTANCE_PATH" ]; then
    print_err "Instance directory not found: $INSTANCE_PATH"
    exit 1
fi

# ── Compute output path ──────────────────────────────────

TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"
# Filename includes instance name so users with multiple instances /
# vaults keep their archive sets distinguishable in a shared output dir.
ARCHIVE_NAME="${INSTANCE_NAME}-${TIMESTAMP}.tar.gz"
# Default: sibling to the instance dir (not inside it), so a wipe of
# the instance does not take the archives with it.
DEFAULT_OUTPUT_DIR="$(dirname "$INSTANCE_PATH")/tomo-backups"

if [ -z "$OUTPUT" ]; then
    OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
    OUTPUT_FILE="$OUTPUT_DIR/$ARCHIVE_NAME"
elif [ -d "$OUTPUT" ]; then
    OUTPUT_DIR="$OUTPUT"
    OUTPUT_FILE="$OUTPUT_DIR/$ARCHIVE_NAME"
else
    OUTPUT_DIR="$(dirname "$OUTPUT")"
    OUTPUT_FILE="$OUTPUT"
fi

mkdir -p "$OUTPUT_DIR"

# ── Collect file list ────────────────────────────────────

print_step "Backing up Tomo instance"
echo "  Instance: $INSTANCE_PATH"
echo "  Archive:  $OUTPUT_FILE"

# Build tar inclusion list (paths relative to a temp staging root so the
# archive has a clean structure regardless of instance location on disk).
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

stage() {
    local src="$1"   # absolute path on disk
    local rel="$2"   # path inside the archive
    if [ -e "$src" ]; then
        mkdir -p "$(dirname "$STAGE_DIR/$rel")"
        cp -R "$src" "$STAGE_DIR/$rel"
        echo "  + $rel"
        return 0
    fi
    return 1
}

# Metadata at archive root
stage "$CONFIG_FILE" "tomo-install.json" || print_warn "tomo-install.json missing"

# Instance config (user-edited)
stage "$INSTANCE_PATH/config" "tomo-instance/config" || print_warn "config/ missing"
stage "$INSTANCE_PATH/.claude/settings.local.json" "tomo-instance/.claude/settings.local.json" || true
stage "$INSTANCE_PATH/.mcp.json" "tomo-instance/.mcp.json" || true

# Home dir (auth) — always included per spec decision 2026-04-20
if [ -n "$HOME_DIR" ] && [ -d "$HOME_DIR" ]; then
    stage "$HOME_DIR" "tomo-home" || true
else
    print_warn "HOME_DIR not in tomo-install.json or dir missing — skipping tomo-home"
fi

# ── Create archive ───────────────────────────────────────

if [ "$DRY_RUN" = "true" ]; then
    print_step "Dry-run — not creating archive"
    du -sh "$STAGE_DIR" 2>/dev/null || true
    exit 0
fi

print_step "Creating archive"
tar -czf "$OUTPUT_FILE" -C "$STAGE_DIR" . 2>/dev/null
chmod 600 "$OUTPUT_FILE"

ARCHIVE_SIZE="$(du -h "$OUTPUT_FILE" | cut -f1)"
print_ok "$OUTPUT_FILE ($ARCHIVE_SIZE)"

# ── Rotation ─────────────────────────────────────────────

if [ "$KEEP" -gt 0 ] && [ -d "$OUTPUT_DIR" ]; then
    print_step "Rotating (keep last $KEEP for instance '$INSTANCE_NAME')"
    # Rotation is scoped to THIS instance — don't touch other instances'
    # archives that might live in a shared output dir.
    OLD_ARCHIVES="$(ls -1t "$OUTPUT_DIR"/${INSTANCE_NAME}-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) || true)"
    if [ -n "$OLD_ARCHIVES" ]; then
        echo "$OLD_ARCHIVES" | while IFS= read -r old; do
            [ -n "$old" ] || continue
            rm -f "$old"
            echo "  − $(basename "$old")"
        done
    else
        echo "  (none to remove)"
    fi
fi

# ── Final summary + safety warning ───────────────────────

print_step "Done"
echo ""
echo "  Archive: $OUTPUT_FILE"
echo "  Location is a sibling of tomo-instance/ — survives an instance wipe."
echo ""
print_warn "For real disaster recovery (disk failure, OS reinstall), copy the"
print_warn "archive off-device periodically:"
echo "    cp \"$OUTPUT_FILE\" ~/Dropbox/tomo-backups/"
echo "    (or iCloud, external drive, etc.)"
echo ""
