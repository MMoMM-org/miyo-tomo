#!/bin/bash
# cleanup-tomo.sh — Remove files/dirs created by install-tomo.sh.
# Useful for testing install flows from a clean state.
# version: 0.1.0
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/tomo-install.json"

# ── Colors ────────────────────────────────────────────────

if [ -t 1 ]; then
    C_RESET="\033[0m"
    C_BOLD="\033[1m"
    C_CYAN="\033[36m"
    C_GREEN="\033[32m"
    C_YELLOW="\033[33m"
    C_RED="\033[31m"
else
    C_RESET="" C_BOLD="" C_CYAN="" C_GREEN="" C_YELLOW="" C_RED=""
fi

print_step() { printf "\n${C_BOLD}${C_CYAN}▸ %s${C_RESET}\n" "$1"; }
print_ok()   { printf "  ${C_GREEN}✓${C_RESET} %s\n" "$1"; }
print_warn() { printf "  ${C_YELLOW}⚠${C_RESET} %s\n" "$1"; }
print_err()  { printf "  ${C_RED}✗${C_RESET} %s\n" "$1" >&2; }

# ── CLI flags ─────────────────────────────────────────────

FORCE=false
KEEP_HOME=false
KEEP_INSTANCE=false
DRY_RUN=false

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--force)        FORCE=true;         shift ;;
        --keep-home)       KEEP_HOME=true;     shift ;;
        --keep-instance)   KEEP_INSTANCE=true; shift ;;
        -n|--dry-run)      DRY_RUN=true;       shift ;;
        -h|--help)
            cat <<'HELPEOF'
Usage: cleanup-tomo.sh [OPTIONS]

Remove files/dirs created by install-tomo.sh for a clean re-install.
Safe: refuses to delete paths outside the Tomo repo.

Options:
  -f, --force           Skip confirmation prompt
      --keep-home       Preserve tomo-home/ (keeps Claude auth credentials)
      --keep-instance   Preserve tomo-instance/
  -n, --dry-run         Show what would be removed without deleting
  -h, --help            Show this help

Targets (reads tomo-install.json to find custom paths):
  - tomo-instance/           (instance workspace, incl. its .git/ repo)
  - tomo-home/               (Docker /home/coder mount with auth)
  - begin-tomo.sh            (generated launcher at instance location)
  - tomo-install.json        (install config)

Examples:
  # Preview
  bash scripts/cleanup-tomo.sh --dry-run

  # Full cleanup with confirmation
  bash scripts/cleanup-tomo.sh

  # Force cleanup but keep auth credentials
  bash scripts/cleanup-tomo.sh --force --keep-home
HELPEOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Run with --help for usage." >&2
            exit 1
            ;;
    esac
done

# ── Determine targets ─────────────────────────────────────

INSTANCE_PATH=""
HOME_DIR=""
LAUNCHER_PATH=""

if [ -f "$CONFIG_FILE" ] && command -v jq > /dev/null 2>&1; then
    INSTANCE_PATH="$(jq -r '.instancePath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
    HOME_DIR="$(jq -r '.homePath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
    LAUNCHER_PATH="$(jq -r '.launcherPath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
fi

# Fallbacks to default locations
[ -z "$INSTANCE_PATH" ] && INSTANCE_PATH="$REPO_ROOT/tomo-instance"
[ -z "$HOME_DIR" ]      && HOME_DIR="$REPO_ROOT/tomo-home"
[ -z "$LAUNCHER_PATH" ] && LAUNCHER_PATH="$REPO_ROOT/begin-tomo.sh"

# ── Safety: refuse paths outside repo ────────────────────

check_safe() {
    local path="$1" label="$2"
    # Resolve to absolute; if it doesn't exist yet, best-effort
    case "$path" in
        "$REPO_ROOT"/*) return 0 ;;
        "$REPO_ROOT")
            print_err "Refusing to delete repo root ($label): $path"
            exit 1
            ;;
        *)
            print_err "Refusing to delete path outside repo ($label): $path"
            exit 1
            ;;
    esac
}

# ── Plan ──────────────────────────────────────────────────

print_step "Cleanup plan"

echo "  Repo root: $REPO_ROOT"
echo ""

FOUND_ANY=false

if [ "$KEEP_INSTANCE" != "true" ] && [ -e "$INSTANCE_PATH" ]; then
    check_safe "$INSTANCE_PATH" "instance"
    printf "  ${C_YELLOW}–${C_RESET} instance: %s\n" "$INSTANCE_PATH"
    FOUND_ANY=true
fi

if [ "$KEEP_HOME" != "true" ] && [ -e "$HOME_DIR" ]; then
    check_safe "$HOME_DIR" "home"
    printf "  ${C_YELLOW}–${C_RESET} home:     %s\n" "$HOME_DIR"
    if [ -f "$HOME_DIR/.claude/.credentials.json" ] || [ -f "$HOME_DIR/.claude.json" ]; then
        print_warn "  contains Claude auth credentials!"
    fi
    FOUND_ANY=true
fi

if [ -f "$LAUNCHER_PATH" ]; then
    check_safe "$LAUNCHER_PATH" "launcher"
    printf "  ${C_YELLOW}–${C_RESET} launcher: %s\n" "$LAUNCHER_PATH"
    FOUND_ANY=true
fi

if [ -f "$CONFIG_FILE" ]; then
    printf "  ${C_YELLOW}–${C_RESET} config:   %s\n" "$CONFIG_FILE"
    FOUND_ANY=true
fi

if [ "$FOUND_ANY" != "true" ]; then
    echo ""
    print_ok "Nothing to clean up — already clean."
    exit 0
fi

# ── Confirm ───────────────────────────────────────────────

if [ "$DRY_RUN" = "true" ]; then
    echo ""
    print_warn "Dry run — nothing removed."
    exit 0
fi

if [ "$FORCE" != "true" ]; then
    echo ""
    printf "  ${C_BOLD}Proceed with cleanup? [y/N]:${C_RESET} "
    read -r ANSWER
    case "$ANSWER" in
        [yY]|[yY][eE][sS]) ;;
        *)
            print_warn "Aborted."
            exit 0
            ;;
    esac
fi

# ── Remove ────────────────────────────────────────────────

print_step "Removing files"

if [ "$KEEP_INSTANCE" != "true" ] && [ -e "$INSTANCE_PATH" ]; then
    rm -rf "$INSTANCE_PATH"
    print_ok "removed $INSTANCE_PATH"
fi

if [ "$KEEP_HOME" != "true" ] && [ -e "$HOME_DIR" ]; then
    rm -rf "$HOME_DIR"
    print_ok "removed $HOME_DIR"
fi

if [ -f "$LAUNCHER_PATH" ]; then
    rm -f "$LAUNCHER_PATH"
    print_ok "removed $LAUNCHER_PATH"
fi

if [ -f "$CONFIG_FILE" ]; then
    rm -f "$CONFIG_FILE"
    print_ok "removed $CONFIG_FILE"
fi

echo ""
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
printf "  ${C_BOLD}${C_GREEN}✓ Cleanup complete${C_RESET}\n"
printf "  Run ${C_CYAN}bash scripts/install-tomo.sh${C_RESET} to start fresh.\n"
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
