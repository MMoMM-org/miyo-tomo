#!/bin/bash
# cleanup-tomo.sh — Remove files/dirs created by install-tomo.sh, for one instance.
# version: 0.2.0
#
# Two modes:
#   Default (no --instance): the repo-root dev instance ($REPO_ROOT/tomo-instance
#     etc., via $REPO_ROOT/tomo-install.json). Behaviour unchanged from v0.1.
#   --instance <name>: a REGISTERED instance from ~/.tomo/instances.json, which
#     since spec 020 may live OUTSIDE the repo (e.g. <parent>/<name>/). Targets
#     come from that instance's own tomo-install.json.
#
# Safety (this script runs `rm -rf`):
#   - Targets for --instance mode come only from the registry (the trust anchor
#     for a path being a Tomo instance) + that instance's tomo-install.json.
#   - Every target passes a hardened dangerous-path guard: never "/", "$HOME",
#     the repo root, a non-absolute path, or a shallow (< 3 component) path.
#   - An OUTSIDE-repo target defaults to a DRY RUN; it deletes only with --force.
#   - The registry entry is dropped after a successful --instance cleanup.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/instance-registry.sh
. "$SCRIPT_DIR/lib/instance-registry.sh"

# ── Colors ────────────────────────────────────────────────

if [ -t 1 ]; then
    C_RESET="\033[0m"; C_BOLD="\033[1m"; C_CYAN="\033[36m"
    C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"
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
DRY_RUN_EXPLICIT=false
INSTANCE_NAME=""

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--force)        FORCE=true;                          shift ;;
        --keep-home)       KEEP_HOME=true;                      shift ;;
        --keep-instance)   KEEP_INSTANCE=true;                  shift ;;
        -n|--dry-run)      DRY_RUN=true; DRY_RUN_EXPLICIT=true; shift ;;
        --instance)        INSTANCE_NAME="$2";                  shift 2 ;;
        --list)
            print_step "Registered instances (~/.tomo/instances.json)"
            _list_out="$(registry_list_check 2>/dev/null || true)"
            if [ -z "$_list_out" ]; then
                print_ok "none registered"
            else
                echo "$_list_out"
            fi
            exit 0
            ;;
        -h|--help)
            cat <<'HELPEOF'
Usage: cleanup-tomo.sh [OPTIONS]

Remove files/dirs created by install-tomo.sh for ONE instance.

Options:
  --instance <name>     Target a registered instance (~/.tomo/instances.json).
                        Post-020 instances live outside the repo; an
                        outside-repo target is a DRY RUN unless --force is given.
  --list                List registered instances and exit.
  -f, --force           Skip confirmation; required to actually delete an
                        outside-repo instance.
      --keep-home       Preserve home/ (keeps Claude auth credentials)
      --keep-instance   Preserve instance/
  -n, --dry-run         Show what would be removed without deleting
  -h, --help            Show this help

Targets (read from the instance's tomo-install.json):
  - instance workspace dir (incl. its .git/ repo)
  - home dir (Docker /home/coder mount with auth)
  - begin-tomo.sh launcher
  - tomo-install.json

Examples:
  bash scripts/cleanup-tomo.sh --list
  bash scripts/cleanup-tomo.sh --dry-run                 # repo-root dev instance
  bash scripts/cleanup-tomo.sh                           # repo-root, with confirm
  bash scripts/cleanup-tomo.sh --instance tomo-privat    # outside-repo → dry run
  bash scripts/cleanup-tomo.sh --instance tomo-privat --force   # actually delete
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

# ── Resolve the target install directory + config ─────────
# INSTALL_DIR holds tomo-install.json; for the repo-root dev instance that is
# REPO_ROOT, for a registered instance it is the parent of the instance dir.

if [ -n "$INSTANCE_NAME" ]; then
    if ! RESOLVED_PATH="$(registry_resolve "$INSTANCE_NAME" 2>/dev/null)"; then
        print_err "Unknown instance: '$INSTANCE_NAME'. Try: cleanup-tomo.sh --list"
        exit 1
    fi
    INSTALL_DIR="$(dirname "$RESOLVED_PATH")"
else
    INSTALL_DIR="$REPO_ROOT"
fi

CONFIG_FILE="$INSTALL_DIR/tomo-install.json"

INSTANCE_PATH=""
HOME_DIR=""
LAUNCHER_PATH=""

if [ -f "$CONFIG_FILE" ] && command -v jq > /dev/null 2>&1; then
    INSTANCE_PATH="$(jq -r '.instancePath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
    HOME_DIR="$(jq -r '.homePath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
    LAUNCHER_PATH="$(jq -r '.launcherPath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
fi

# Fallbacks: derive from the registry path (--instance) or repo defaults.
if [ -n "$INSTANCE_NAME" ]; then
    [ -z "$INSTANCE_PATH" ] && INSTANCE_PATH="$RESOLVED_PATH"
    [ -z "$HOME_DIR" ]      && HOME_DIR="$INSTALL_DIR/home"
    [ -z "$LAUNCHER_PATH" ] && LAUNCHER_PATH="$INSTALL_DIR/begin-tomo.sh"
else
    [ -z "$INSTANCE_PATH" ] && INSTANCE_PATH="$REPO_ROOT/tomo-instance"
    [ -z "$HOME_DIR" ]      && HOME_DIR="$REPO_ROOT/tomo-home"
    [ -z "$LAUNCHER_PATH" ] && LAUNCHER_PATH="$REPO_ROOT/begin-tomo.sh"
fi

# ── Safety: refuse obviously dangerous targets ────────────
# Replaces the v0.1 "must be inside repo" rule (which blocked outside-repo
# instances entirely). The registry is now the trust anchor for a path being a
# Tomo instance; this guard is the backstop against nuking a root/home/shallow
# path regardless of how it was resolved.

_component_count() {
    # Count non-empty path components (bash 3.2 safe; no arrays).
    echo "$1" | awk -F/ '{n=0; for(i=1;i<=NF;i++) if($i!="") n++; print n}'
}

assert_safe_target() {
    path="$1"; label="$2"
    case "$path" in
        "") return 0 ;;                # empty → nothing to delete, skip
        /*) : ;;                       # absolute — required
        *)  print_err "Refusing non-absolute path ($label): $path"; exit 1 ;;
    esac
    if [ "$path" = "/" ] || [ "$path" = "$HOME" ] || [ "$path" = "$REPO_ROOT" ]; then
        print_err "Refusing to delete a protected path ($label): $path"
        exit 1
    fi
    if [ "$(_component_count "$path")" -lt 3 ]; then
        print_err "Refusing shallow path ($label): $path"
        exit 1
    fi
    return 0
}

# ── Outside-repo posture: dry-run unless --force ──────────

OUTSIDE_REPO=false
case "$INSTALL_DIR" in
    "$REPO_ROOT"|"$REPO_ROOT"/*) OUTSIDE_REPO=false ;;
    *)                           OUTSIDE_REPO=true ;;
esac

if [ "$OUTSIDE_REPO" = "true" ] && [ "$FORCE" != "true" ] && [ "$DRY_RUN_EXPLICIT" != "true" ]; then
    DRY_RUN=true
    OUTSIDE_DRYRUN_FORCED=true
fi

# ── Plan ──────────────────────────────────────────────────

print_step "Cleanup plan"
if [ -n "$INSTANCE_NAME" ]; then
    echo "  Instance: $INSTANCE_NAME  ($([ "$OUTSIDE_REPO" = "true" ] && echo 'outside repo' || echo 'in repo'))"
fi
echo "  Config dir: $INSTALL_DIR"
echo ""

FOUND_ANY=false

if [ "$KEEP_INSTANCE" != "true" ] && [ -e "$INSTANCE_PATH" ]; then
    assert_safe_target "$INSTANCE_PATH" "instance"
    printf "  ${C_YELLOW}–${C_RESET} instance: %s\n" "$INSTANCE_PATH"
    FOUND_ANY=true
fi

if [ "$KEEP_HOME" != "true" ] && [ -e "$HOME_DIR" ]; then
    assert_safe_target "$HOME_DIR" "home"
    printf "  ${C_YELLOW}–${C_RESET} home:     %s\n" "$HOME_DIR"
    if [ -f "$HOME_DIR/.claude/.credentials.json" ] || [ -f "$HOME_DIR/.claude.json" ]; then
        print_warn "  contains Claude auth credentials!"
    fi
    FOUND_ANY=true
fi

if [ -f "$LAUNCHER_PATH" ]; then
    assert_safe_target "$LAUNCHER_PATH" "launcher"
    printf "  ${C_YELLOW}–${C_RESET} launcher: %s\n" "$LAUNCHER_PATH"
    FOUND_ANY=true
fi

if [ -f "$CONFIG_FILE" ]; then
    assert_safe_target "$CONFIG_FILE" "config"
    printf "  ${C_YELLOW}–${C_RESET} config:   %s\n" "$CONFIG_FILE"
    FOUND_ANY=true
fi

if [ "$FOUND_ANY" != "true" ]; then
    echo ""
    print_ok "Nothing to clean up — already clean."
    # Still drop a stale registry entry if the name resolves to nothing on disk.
    if [ -n "$INSTANCE_NAME" ]; then
        registry_remove "$INSTANCE_NAME" >/dev/null 2>&1 || true
        print_ok "deregistered '$INSTANCE_NAME' (no files remained)"
    fi
    exit 0
fi

# ── Confirm ───────────────────────────────────────────────

if [ "$DRY_RUN" = "true" ]; then
    echo ""
    if [ "${OUTSIDE_DRYRUN_FORCED:-false}" = "true" ]; then
        print_warn "Outside-repo instance — dry run. Re-run with --force to delete."
    else
        print_warn "Dry run — nothing removed."
    fi
    exit 0
fi

if [ "$FORCE" != "true" ]; then
    echo ""
    printf "  ${C_BOLD}Proceed with cleanup? [y/N]:${C_RESET} "
    read -r ANSWER
    case "$ANSWER" in
        [yY]|[yY][eE][sS]) ;;
        *) print_warn "Aborted."; exit 0 ;;
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

# ── Deregister ────────────────────────────────────────────
# --instance mode: drop the named entry. Legacy repo-root mode: best-effort
# drop any entry whose path matches the deleted instance (keeps the registry
# consistent with what's on disk).

if [ -n "$INSTANCE_NAME" ]; then
    registry_remove "$INSTANCE_NAME" >/dev/null 2>&1 || true
    print_ok "deregistered '$INSTANCE_NAME'"
elif [ "$KEEP_INSTANCE" != "true" ]; then
    _match_name="$(registry_list 2>/dev/null | jq -r --arg p "$INSTANCE_PATH" \
        'select(.path == $p) | .name' 2>/dev/null || echo '')"
    if [ -n "$_match_name" ]; then
        registry_remove "$_match_name" >/dev/null 2>&1 || true
        print_ok "deregistered '$_match_name'"
    fi
fi

echo ""
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
printf "  ${C_BOLD}${C_GREEN}✓ Cleanup complete${C_RESET}\n"
printf "  Run ${C_CYAN}bash scripts/install-tomo.sh${C_RESET} to start fresh.\n"
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
