#!/bin/bash
# cleanup-tomo.sh — Retire a Tomo instance: deregister it and (optionally) delete
# its files from disk.
# version: 0.3.0
#
# Two SEPARATE operations, never conflated:
#   registry-only  — drop the instance from ~/.tomo/instances.json and print the
#                    on-disk paths for you to delete yourself (Finder, rm, …).
#                    Non-destructive; this script never touches your files.
#   delete-disk    — ALSO remove the instance's files (instance/, home/,
#                    launcher, tomo-install.json). Always confirmed.
#
# Selection:
#   --instance <name>  a registered instance (may live outside the repo, spec 020)
#   (default)          the repo-root dev instance ($REPO_ROOT/tomo-instance …)
#
# Interactive runs are asked r/d/N. Non-interactive runs default to the SAFE
# registry-only action; --delete-disk (which needs --force to skip the confirm)
# is required to remove files. A hardened guard refuses "/", "$HOME", the repo
# root, non-absolute, and shallow paths before any deletion.
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
REGISTRY_ONLY=false
DELETE_DISK=false
INSTANCE_NAME=""

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--force)        FORCE=true;         shift ;;
        --registry-only)   REGISTRY_ONLY=true; shift ;;
        --delete-disk)     DELETE_DISK=true;   shift ;;
        --keep-home)       KEEP_HOME=true;     shift ;;
        --keep-instance)   KEEP_INSTANCE=true; shift ;;
        -n|--dry-run)      DRY_RUN=true;       shift ;;
        --instance)        INSTANCE_NAME="$2"; shift 2 ;;
        --list)
            print_step "Registered instances (~/.tomo/instances.json)"
            _list_out="$(registry_list_check 2>/dev/null || true)"
            if [ -z "$_list_out" ]; then print_ok "none registered"; else echo "$_list_out"; fi
            exit 0
            ;;
        -h|--help)
            cat <<'HELPEOF'
Usage: cleanup-tomo.sh [OPTIONS]

Retire a Tomo instance. Two separate operations:
  registry-only  drop it from ~/.tomo/instances.json; you delete the folder.
  delete-disk    also remove the instance's files (always confirmed).

Interactive runs are asked which one. Non-interactive runs default to the safe
registry-only action; pass --delete-disk (+ --force) to remove files.

Options:
  --instance <name>  Target a registered instance (else the repo-root dev one).
  --list             List registered instances and exit.
  --registry-only    Deregister only; never touch files (no prompt).
  --delete-disk      Deregister AND delete files. Needs --force to skip confirm.
  -f, --force        Skip the disk-deletion confirmation.
      --keep-home    When deleting, preserve home/ (Claude auth credentials).
      --keep-instance  When deleting, preserve instance/.
  -n, --dry-run      Show the plan; change nothing.
  -h, --help         Show this help.

Examples:
  bash scripts/cleanup-tomo.sh --list
  bash scripts/cleanup-tomo.sh --instance tomo-privat                 # ask r/d/N
  bash scripts/cleanup-tomo.sh --instance tomo-privat --registry-only # deregister
  bash scripts/cleanup-tomo.sh --instance tomo-privat --delete-disk --force
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

if [ "$REGISTRY_ONLY" = "true" ] && [ "$DELETE_DISK" = "true" ]; then
    print_err "--registry-only and --delete-disk are mutually exclusive."
    exit 1
fi

# ── Resolve the target install directory + config ─────────

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
INSTANCE_PATH=""; HOME_DIR=""; LAUNCHER_PATH=""

if [ -f "$CONFIG_FILE" ] && command -v jq > /dev/null 2>&1; then
    INSTANCE_PATH="$(jq -r '.instancePath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
    HOME_DIR="$(jq -r '.homePath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
    LAUNCHER_PATH="$(jq -r '.launcherPath // empty' "$CONFIG_FILE" 2>/dev/null || echo '')"
fi

if [ -n "$INSTANCE_NAME" ]; then
    [ -z "$INSTANCE_PATH" ] && INSTANCE_PATH="$RESOLVED_PATH"
    [ -z "$HOME_DIR" ]      && HOME_DIR="$INSTALL_DIR/home"
    [ -z "$LAUNCHER_PATH" ] && LAUNCHER_PATH="$INSTALL_DIR/begin-tomo.sh"
else
    [ -z "$INSTANCE_PATH" ] && INSTANCE_PATH="$REPO_ROOT/tomo-instance"
    [ -z "$HOME_DIR" ]      && HOME_DIR="$REPO_ROOT/tomo-home"
    [ -z "$LAUNCHER_PATH" ] && LAUNCHER_PATH="$REPO_ROOT/begin-tomo.sh"
fi

# Registry name to drop (explicit --instance, else best-effort match by path).
DEREGISTER_NAME="$INSTANCE_NAME"
if [ -z "$DEREGISTER_NAME" ]; then
    DEREGISTER_NAME="$(registry_list 2>/dev/null | jq -r --arg p "$INSTANCE_PATH" \
        'select(.path == $p) | .name' 2>/dev/null || echo '')"
fi

# ── Safety: refuse obviously dangerous deletion targets ───

_component_count() { echo "$1" | awk -F/ '{n=0; for(i=1;i<=NF;i++) if($i!="") n++; print n}'; }

assert_safe_target() {
    path="$1"; label="$2"
    [ -z "$path" ] && return 0
    case "$path" in
        /*) : ;;
        *)  print_err "Refusing non-absolute path ($label): $path"; exit 1 ;;
    esac
    if [ "$path" = "/" ] || [ "$path" = "$HOME" ] || [ "$path" = "$REPO_ROOT" ]; then
        print_err "Refusing to delete a protected path ($label): $path"; exit 1
    fi
    if [ "$(_component_count "$path")" -lt 3 ]; then
        print_err "Refusing shallow path ($label): $path"; exit 1
    fi
    return 0
}

# ── Plan ──────────────────────────────────────────────────

print_step "Instance"
[ -n "$INSTANCE_NAME" ] && echo "  name:     $INSTANCE_NAME"
if [ -n "$DEREGISTER_NAME" ]; then echo "  registry: $DEREGISTER_NAME"; else echo "  registry: (not registered)"; fi
echo ""
print_step "On-disk paths"
_show() {
    [ -z "$1" ] && return 0
    if [ -e "$1" ]; then printf "  ${C_YELLOW}–${C_RESET} %-9s %s\n" "$2" "$1"
    else printf "    %-9s %s ${C_CYAN}(absent)${C_RESET}\n" "$2" "$1"; fi
}
_show "$INSTANCE_PATH" "instance:"
_show "$HOME_DIR" "home:"
_show "$LAUNCHER_PATH" "launcher:"
_show "$CONFIG_FILE" "config:"
if [ -f "$HOME_DIR/.claude/.credentials.json" ] || [ -f "$HOME_DIR/.claude.json" ]; then
    print_warn "home/ contains Claude auth credentials"
fi

if [ "$DRY_RUN" = "true" ]; then
    echo ""; print_warn "Dry run — nothing changed."
    exit 0
fi

# ── Decide the action: registry | disk ────────────────────

ACTION=""
CONFIRMED=false
if [ "$REGISTRY_ONLY" = "true" ]; then
    ACTION="registry"
elif [ "$DELETE_DISK" = "true" ]; then
    ACTION="disk"
    [ "$FORCE" = "true" ] && CONFIRMED=true
elif [ -t 0 ]; then
    echo ""
    printf "  ${C_BOLD}Retire this instance — [r] registry only  [d] delete files too  [N] cancel:${C_RESET} "
    read -r CHOICE
    case "$CHOICE" in
        [rR]) ACTION="registry" ;;
        [dD]) ACTION="disk"; CONFIRMED=true ;;
        *)    print_warn "Aborted."; exit 0 ;;
    esac
else
    ACTION="registry"
    print_warn "Non-interactive: defaulting to registry-only (pass --delete-disk --force to remove files)."
fi

# ── Execute ───────────────────────────────────────────────

_deregister() {
    if [ -n "$DEREGISTER_NAME" ]; then
        registry_remove "$DEREGISTER_NAME" >/dev/null 2>&1 || true
        print_ok "deregistered '$DEREGISTER_NAME'"
    else
        print_ok "nothing to deregister (not in registry)"
    fi
}

if [ "$ACTION" = "registry" ]; then
    print_step "Deregister only"
    _deregister
    echo ""
    print_step "Delete these yourself (Finder, rm, …):"
    _any=false
    for p in "$INSTANCE_PATH" "$HOME_DIR" "$LAUNCHER_PATH" "$CONFIG_FILE"; do
        if [ -n "$p" ] && [ -e "$p" ]; then echo "  $p"; _any=true; fi
    done
    [ "$_any" != "true" ] && print_ok "no files left on disk"
    exit 0
fi

# ACTION = disk
if [ "$CONFIRMED" != "true" ]; then
    if [ -t 0 ]; then
        echo ""
        printf "  ${C_BOLD}Delete the files listed above? [y/N]:${C_RESET} "
        read -r ANSWER
        case "$ANSWER" in [yY]|[yY][eE][sS]) CONFIRMED=true ;; *) print_warn "Aborted."; exit 0 ;; esac
    else
        print_err "Refusing to delete files without --force in a non-interactive run."
        exit 1
    fi
fi

print_step "Removing files"
if [ "$KEEP_INSTANCE" != "true" ] && [ -e "$INSTANCE_PATH" ]; then
    assert_safe_target "$INSTANCE_PATH" "instance"; rm -rf "$INSTANCE_PATH"; print_ok "removed $INSTANCE_PATH"
fi
if [ "$KEEP_HOME" != "true" ] && [ -e "$HOME_DIR" ]; then
    assert_safe_target "$HOME_DIR" "home"; rm -rf "$HOME_DIR"; print_ok "removed $HOME_DIR"
fi
if [ -f "$LAUNCHER_PATH" ]; then
    assert_safe_target "$LAUNCHER_PATH" "launcher"; rm -f "$LAUNCHER_PATH"; print_ok "removed $LAUNCHER_PATH"
fi
if [ -f "$CONFIG_FILE" ]; then
    assert_safe_target "$CONFIG_FILE" "config"; rm -f "$CONFIG_FILE"; print_ok "removed $CONFIG_FILE"
fi

_deregister

echo ""
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
printf "  ${C_BOLD}${C_GREEN}✓ Cleanup complete${C_RESET}\n"
printf "  Run ${C_CYAN}bash scripts/install-tomo.sh${C_RESET} to start fresh.\n"
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
