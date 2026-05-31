#!/bin/bash
# install-tomo.sh — Create a Tomo instance from source templates.
# Copies agents, skills, commands, and configs into the instance directory.
# Sets up tomo-home/ as the Docker /home/coder mount.
# Runs the Phase 1 setup wizard: vault path, profile selection, concept mapping,
# lifecycle prefix, voice transcription, and vault-config.yaml generation.
# version: 0.4.0
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOMO_SOURCE="$REPO_ROOT/tomo"
CONFIG_FILE="$REPO_ROOT/tomo-install.json"
# Tests override this to an isolated path so they don't clobber the user's
# real installation metadata. Resolved from --config-file after argv parse.
PROFILES_DIR="$TOMO_SOURCE/profiles"
TOMO_VERSION=$(grep -m1 '^# version:' "$TOMO_SOURCE/dot_claude/rules/project-context.md" 2>/dev/null \
    | sed 's/^# version: *//' || echo "0.0.0")

# ── CLI Flags ────────────────────────────────────────────

NON_INTERACTIVE=false
FLAG_VAULT=""
FLAG_PROFILE=""
FLAG_KADO_HOST=""
FLAG_KADO_PORT=""
FLAG_KADO_TOKEN=""
FLAG_PREFIX=""
SHOW_HELP=false

FLAG_INSTANCE_LOCATION=""
FLAG_INSTANCE_NAME=""
FLAG_HOME_DIR=""
FLAG_CONFIG_FILE=""
FLAG_UPDATE=false

while [ $# -gt 0 ]; do
    case "$1" in
        --vault)       FLAG_VAULT="$2";     shift 2 ;;
        --profile)     FLAG_PROFILE="$2";   shift 2 ;;
        --kado-host)   FLAG_KADO_HOST="$2"; shift 2 ;;
        --kado-port)   FLAG_KADO_PORT="$2"; shift 2 ;;
        --kado-token)  FLAG_KADO_TOKEN="$2"; shift 2 ;;
        --prefix)      FLAG_PREFIX="$2";    shift 2 ;;
        --instance-location) FLAG_INSTANCE_LOCATION="$2"; shift 2 ;;
        --instance-name)     FLAG_INSTANCE_NAME="$2";     shift 2 ;;
        --home-dir)          FLAG_HOME_DIR="$2";          shift 2 ;;
        --config-file)       FLAG_CONFIG_FILE="$2";       shift 2 ;;
        --update)            FLAG_UPDATE=true;            shift ;;
        --non-interactive) NON_INTERACTIVE=true; shift ;;
        --help|-h)     SHOW_HELP=true;      shift ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Run with --help for usage." >&2
            exit 1
            ;;
    esac
done

# ── Help ─────────────────────────────────────────────────

if [ "$SHOW_HELP" = "true" ]; then
    cat <<'HELPEOF'
Usage: install-tomo.sh [OPTIONS]

Create or update a MiYo Tomo instance with vault configuration.

Options:
  --vault PATH          Path to Obsidian vault directory
  --profile NAME        PKM framework profile (miyo, lyt, custom)
  --kado-host HOST      Kado server host (default: host.docker.internal)
  --kado-port PORT      Kado server port (default: 37022)
  --kado-token TOKEN    Kado bearer token (must start with kado_)
  --prefix PREFIX       Lifecycle tag prefix (default: MiYo-Tomo)
  --instance-name NAME  Instance directory name (default: tomo-instance)
  --instance-location P Parent directory for the instance (default: ~/MiYo/Tomo).
                        The self-contained instance is created at
                        <location>/<name>/ holding instance/, home/,
                        tomo-install.json and begin-tomo.sh.
  --home-dir PATH       Pin the Docker home dir exactly (default derived:
                        <location>/<name>/home). For test isolation.
  --config-file PATH    Pin tomo-install.json exactly (default derived:
                        <location>/<name>/tomo-install.json). For test isolation.
  --update              Update the existing instance named by --instance-name
                        instead of creating a new one (non-interactive only)
  --non-interactive     Use defaults for all prompts (requires --vault)
  --help, -h            Show this help message

Interactive mode (default):
  Walks through vault path, profile selection, concept mapping, lifecycle
  prefix, and Kado connection. Generates vault-config.yaml in instance.
  When other instances are registered, offers a create-new vs update-<name>
  choice up front.

Non-interactive mode:
  Requires at least --vault. Uses profile defaults for concept paths.
  --instance-name names the target. By default a name already present in the
  instance registry is rejected as a duplicate; pass --update to target that
  existing instance instead. Suitable for CI/automation.

Examples:
  # Interactive setup
  ./scripts/install-tomo.sh

  # Non-interactive with MiYo profile
  ./scripts/install-tomo.sh \
    --vault /path/to/vault \
    --profile miyo \
    --kado-token kado_abc123 \
    --non-interactive

  # Re-run to update config
  ./scripts/install-tomo.sh --vault /path/to/vault
HELPEOF
    exit 0
fi

# ── ANSI Colors ──────────────────────────────────────────

if [ -t 1 ]; then
    C_RESET="\033[0m"
    C_BOLD="\033[1m"
    C_DIM=""           # disabled — dim is too hard to read on many terminals
    C_CYAN="\033[36m"
    C_GREEN="\033[32m"
    C_YELLOW="\033[33m"
    C_RED="\033[31m"
    C_BLUE="\033[34m"
    C_WHITE="\033[37m"
else
    C_RESET="" C_BOLD="" C_DIM="" C_CYAN="" C_GREEN=""
    C_YELLOW="" C_RED="" C_BLUE="" C_WHITE=""
fi

# ── Helpers ───────────────────────────────────────────────

print_step() { printf "\n${C_BOLD}${C_CYAN}▸ %s${C_RESET}\n" "$1"; }
print_ok()   { printf "  ${C_GREEN}✓${C_RESET} %s\n" "$1"; }
print_warn() { printf "  ${C_YELLOW}⚠${C_RESET} %s\n" "$1"; }
print_err()  { printf "  ${C_RED}✗${C_RESET} %s\n" "$1" >&2; }

# Read a simple YAML value: yaml_value file key
# Handles top-level and one-level-indented keys (concept_defaults.inbox style)
# Only works for simple scalar values — not nested structures.
yaml_value() {
    local file="$1" key="$2"
    grep "^  ${key}:" "$file" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d '"'"'"
}

# Read a nested YAML value: yaml_nested file parent child
# e.g., yaml_nested miyo.yaml atomic_note base_path
yaml_nested() {
    local file="$1" parent="$2" child="$3"
    sed -n "/^  ${parent}:/,/^  [a-z]/p" "$file" 2>/dev/null \
        | grep "    ${child}:" | head -1 | sed 's/.*: *//' | tr -d '"'"'"
}

# Read a YAML list under a parent: yaml_list file parent child
# Returns lines, one per value
yaml_list() {
    local file="$1" parent="$2" child="$3"
    sed -n "/^  ${parent}:/,/^  [a-z]/p" "$file" 2>/dev/null \
        | sed -n "/    ${child}:/,/^    [a-z]/p" \
        | grep '^ *- ' | sed 's/^ *- *//' | tr -d '"'"'"
}

# Prompt with default: prompt_default prompt default_value
# In non-interactive mode, returns default without prompting.
prompt_default() {
    local prompt_text="$1" default_val="$2"
    if [ "$NON_INTERACTIVE" = "true" ]; then
        echo "$default_val"
        return
    fi
    local answer
    read -rp "  ${prompt_text} [${default_val}]: " answer
    # Trim leading/trailing whitespace from user input
    answer="${answer#"${answer%%[![:space:]]*}"}"
    answer="${answer%"${answer##*[![:space:]]}"}"
    echo "${answer:-$default_val}"
}

# Prompt yes/no with default: prompt_yn prompt default(Y/N)
prompt_yn() {
    local prompt_text="$1" default_val="$2"
    if [ "$NON_INTERACTIVE" = "true" ]; then
        echo "$default_val"
        return
    fi
    local answer
    read -rp "  ${prompt_text} [${default_val}]: " answer
    echo "${answer:-$default_val}"
}

# Voice transcription wizard (XDD 009) — sets VOICE_ENABLED / VOICE_MODEL /
# VOICE_LANGUAGE globals. Uses print_step/print_ok/print_warn/print_err.
# shellcheck source=lib/configure-voice.sh
. "$SCRIPT_DIR/lib/configure-voice.sh"

# Hashi IDE Bridge wizard (XDD 019) — sets IDE_BRIDGE_ENABLED / IDE_BRIDGE_TOKEN /
# IDE_BRIDGE_PORT globals. Uses print_step/print_ok/print_warn/print_err.
# shellcheck source=lib/configure-ide-bridge.sh
. "$SCRIPT_DIR/lib/configure-ide-bridge.sh"

# Instance registry (XDD 020 Phase 1) — provides registry_list /
# registry_list_check / registry_resolve / registry_upsert for the
# multi-instance front-end. Honors TOMO_REGISTRY_FILE for test isolation.
# shellcheck source=lib/instance-registry.sh
. "$SCRIPT_DIR/lib/instance-registry.sh"

# Shared launcher renderer (XDD 020 Phase 2 / ADR-7) — provides render_launcher
# which handles placeholder substitution + atomic write + chmod +x.
# shellcheck source=lib/render-launcher.sh
. "$SCRIPT_DIR/lib/render-launcher.sh"

# registry_has_name NAME — exit 0 if NAME is registered, non-zero otherwise.
registry_has_name() {
    registry_resolve "$1" >/dev/null 2>&1
}

# ── Step 1: Welcome ──────────────────────────────────────

# ── ANSI Logo ────────────────────────────────────────────

LOGO_FILE="$SCRIPT_DIR/../tomo-logo.txt"
if [ -t 1 ] && [ -f "$LOGO_FILE" ]; then
    echo ""
    cat "$LOGO_FILE"
    printf "\n\n"
fi

printf "${C_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
printf "  ${C_BOLD}MiYo Tomo${C_RESET} — Setup Wizard v${TOMO_VERSION}\n"
printf "  ${C_DIM}AI-assisted PKM workflows for Obsidian${C_RESET}\n"
printf "${C_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"

# ── Prerequisites ─────────────────────────────────────────

print_step "Checking prerequisites"
for cmd in docker git jq; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        print_err "$cmd is required but not installed."
        exit 1
    fi
    print_ok "$cmd"
done

# ── Step 2: Vault Path ──────────────────────────────────

print_step "Vault path"

VAULT_PATH=""
if [ -n "$FLAG_VAULT" ]; then
    VAULT_PATH="$FLAG_VAULT"
else
    if [ "$NON_INTERACTIVE" = "true" ]; then
        print_err "--vault is required in non-interactive mode."
        exit 1
    fi
    while true; do
        read -rp "  Where is your Obsidian vault? " VAULT_PATH
        if [ -z "$VAULT_PATH" ]; then
            print_err "Vault path cannot be empty."
            continue
        fi
        # Expand ~ if present
        case "$VAULT_PATH" in
            ~/*) VAULT_PATH="$HOME/${VAULT_PATH#\~/}" ;;
        esac
        if [ -d "$VAULT_PATH" ]; then
            break
        fi
        print_err "Directory does not exist: $VAULT_PATH"
    done
fi

# Validate vault path
if [ ! -d "$VAULT_PATH" ]; then
    print_err "Vault directory does not exist: $VAULT_PATH"
    exit 1
fi
print_ok "Vault: $VAULT_PATH"

if [ ! -d "$VAULT_PATH/.obsidian" ]; then
    print_warn "No .obsidian/ folder found — this may not be an Obsidian vault."
else
    print_ok ".obsidian/ found"
fi

# Show top-level folders
printf "\n  ${C_DIM}Top-level vault folders:${C_RESET}\n"
FOLDER_COUNT=0
for d in "$VAULT_PATH"/*/; do
    if [ -d "$d" ]; then
        dname="$(basename "$d")"
        case "$dname" in
            .*) continue ;;
        esac
        FOLDER_COUNT=$((FOLDER_COUNT + 1))
        printf "    ${C_BOLD}%2d${C_RESET}. %s/\n" "$FOLDER_COUNT" "$dname"
    fi
done
if [ "$FOLDER_COUNT" -eq 0 ]; then
    print_warn "No top-level folders found in vault."
fi

# ── Step 3: Framework Profile ────────────────────────────

print_step "Framework profile selection"

PROFILE=""
if [ -n "$FLAG_PROFILE" ]; then
    PROFILE="$FLAG_PROFILE"
else
    if [ "$NON_INTERACTIVE" = "true" ]; then
        PROFILE="miyo"
    else
        echo "  Available PKM frameworks:"
        echo "    1. miyo  — MiYo (LYT-derived, Dewey classification)"
        echo "    2. lyt   — LYT (Linking Your Thinking, Ideaverse Pro)"
        echo "    3. custom — Start with empty defaults"
        while true; do
            read -rp "  Select framework [1]: " PROFILE_CHOICE
            PROFILE_CHOICE="${PROFILE_CHOICE:-1}"
            case "$PROFILE_CHOICE" in
                1|miyo)   PROFILE="miyo";   break ;;
                2|lyt)    PROFILE="lyt";    break ;;
                3|custom) PROFILE="custom"; break ;;
                *) print_err "Invalid choice. Enter 1, 2, 3, miyo, lyt, or custom." ;;
            esac
        done
    fi
fi

PROFILE_FILE="$PROFILES_DIR/${PROFILE}.yaml"
if [ "$PROFILE" != "custom" ] && [ ! -f "$PROFILE_FILE" ]; then
    print_err "Profile not found: $PROFILE_FILE"
    exit 1
fi

if [ "$PROFILE" = "custom" ]; then
    PROFILE_VERSION="1.0"
    print_ok "Profile: custom (empty defaults)"
else
    PROFILE_VERSION=$(grep "^version:" "$PROFILE_FILE" | head -1 | sed 's/.*: *//' | tr -d '"'"'")
    PROFILE_VERSION="${PROFILE_VERSION:-1.0}"
    PROFILE_NAME=$(grep "^name:" "$PROFILE_FILE" | head -1 | sed 's/.*: *//' | tr -d '"'"'")
    print_ok "Profile: ${PROFILE} (${PROFILE_NAME}, v${PROFILE_VERSION})"
fi

# ── Step 4: Concept Mapping ──────────────────────────────

print_step "Concept mapping"
echo "  For each concept, confirm or override the default folder path."
if [ "$NON_INTERACTIVE" = "true" ]; then
    echo "  (non-interactive: using profile defaults)"
fi

# Read profile defaults for each concept
# Simple concepts: inbox, project, area, source, template, asset
# Complex concepts: atomic_note (base_path), map_note (paths), calendar (base_path)

get_profile_default() {
    local concept="$1"
    if [ "$PROFILE" = "custom" ]; then
        echo ""
        return
    fi
    case "$concept" in
        inbox|project|area|source|template|asset)
            yaml_value "$PROFILE_FILE" "$concept"
            ;;
        atomic_note)
            yaml_nested "$PROFILE_FILE" "atomic_note" "base_path"
            ;;
        map_note)
            yaml_list "$PROFILE_FILE" "map_note" "paths" | head -1
            ;;
        calendar)
            yaml_nested "$PROFILE_FILE" "calendar" "base_path"
            ;;
    esac
}

# Map concept to user-friendly name
concept_label() {
    case "$1" in
        inbox)       echo "Inbox" ;;
        atomic_note) echo "Atomic Notes" ;;
        map_note)    echo "Maps of Content (MOC)" ;;
        calendar)    echo "Calendar" ;;
        project)     echo "Projects" ;;
        area)        echo "Areas" ;;
        source)      echo "Sources" ;;
        template)    echo "Templates" ;;
        asset)       echo "Assets" ;;
    esac
}

# ── Directory Browser ────────────────────────────────────
# Interactive directory picker that allows drilling into subdirectories.
# Usage: browse_path [initial_relative_path]
# Sets BROWSE_RESULT to the selected relative path (with trailing slash).
# Allows: number to drill down, 0 to go up, d to confirm, or direct path entry.

BROWSE_RESULT=""
browse_path() {
    local rel_path="${1:-}"
    local concept_name="$2"

    while true; do
        local full_path="$VAULT_PATH/$rel_path"

        # Header
        echo ""
        if [ -n "$rel_path" ]; then
            printf "  ${C_DIM}Browsing:${C_RESET} ${C_CYAN}%s${C_RESET}\n" "$rel_path"
        else
            printf "  ${C_DIM}Browsing:${C_RESET} ${C_CYAN}(vault root)${C_RESET}\n"
        fi
        echo ""

        # List subdirectories
        local count=0
        local folder_list=""
        for d in "$full_path"/*/; do
            [ -d "$d" ] || continue
            local dname
            dname="$(basename "$d")"
            case "$dname" in .*) continue ;; esac
            count=$((count + 1))
            folder_list="${folder_list}${dname}
"
            printf "    ${C_BOLD}%2d${C_RESET}. %s/\n" "$count" "$dname"
        done

        if [ "$count" -eq 0 ]; then
            printf "    ${C_DIM}(no subdirectories)${C_RESET}\n"
        fi

        # Navigation options
        echo ""
        local nav_hint=""
        if [ -n "$rel_path" ]; then
            nav_hint=" 0=↑ up  "
        fi
        nav_hint="${nav_hint}${C_BOLD}d${C_RESET}=done (use current)  or type a path"
        printf "  %b\n" "$nav_hint"

        local choice
        read -rp "  > " choice

        case "$choice" in
            d|D|done|"")
                # Empty = accept current path
                if [ "$choice" = "" ] && [ -z "$rel_path" ] && [ "$count" -gt 0 ]; then
                    # At root with no selection yet — don't accept empty
                    printf "  ${C_YELLOW}Please select a folder or type 'd' to use vault root.${C_RESET}\n"
                    continue
                fi
                # Ensure trailing slash for non-empty paths
                if [ -n "$rel_path" ]; then
                    case "$rel_path" in
                        */) BROWSE_RESULT="$rel_path" ;;
                        *)  BROWSE_RESULT="${rel_path}/" ;;
                    esac
                else
                    BROWSE_RESULT=""
                fi
                return
                ;;
            0)
                if [ -n "$rel_path" ]; then
                    rel_path="$(dirname "$rel_path")"
                    # dirname of "foo/" gives "foo", dirname of "foo" gives "."
                    case "$rel_path" in
                        .|./) rel_path="" ;;
                    esac
                    # Strip trailing slash for dirname to work next time
                    case "$rel_path" in
                        */) ;; # keep it
                        "")  ;; # root
                        *)   rel_path="${rel_path}/" ;;
                    esac
                fi
                ;;
            [0-9]|[0-9][0-9])
                # Select numbered folder — drill down
                local j=0
                local selected=""
                for d in "$full_path"/*/; do
                    [ -d "$d" ] || continue
                    local dname
                    dname="$(basename "$d")"
                    case "$dname" in .*) continue ;; esac
                    j=$((j + 1))
                    if [ "$j" -eq "$choice" ]; then
                        selected="$dname"
                        break
                    fi
                done
                if [ -n "$selected" ]; then
                    rel_path="${rel_path}${selected}/"
                else
                    printf "  ${C_RED}Invalid selection.${C_RESET}\n"
                fi
                ;;
            *)
                # Direct path entry
                case "$choice" in
                    */) BROWSE_RESULT="$choice" ;;
                    *)  BROWSE_RESULT="${choice}/" ;;
                esac
                # Validate
                if [ ! -d "$VAULT_PATH/$BROWSE_RESULT" ]; then
                    print_warn "Folder does not exist yet: ${BROWSE_RESULT} (OK for new setups)"
                fi
                return
                ;;
        esac
    done
}

# ── Concept Prompt (interactive or non-interactive) ──────
# Sets CONCEPT_RESULT for the given concept.

CONCEPT_RESULT=""
prompt_concept() {
    local concept="$1"
    local default_path="$2"
    local label
    label="$(concept_label "$concept")"

    if [ "$NON_INTERACTIVE" = "true" ]; then
        CONCEPT_RESULT="$default_path"
        if [ -n "$default_path" ]; then
            print_ok "${label}: ${default_path}"
        else
            print_warn "${label}: (no default, skipped)"
        fi
        return
    fi

    # Concept header with spacing
    echo ""
    printf "  ${C_BOLD}${C_BLUE}── %s ──${C_RESET}\n" "$label"
    if [ -n "$default_path" ]; then
        printf "  ${C_DIM}Profile default:${C_RESET} ${C_GREEN}%s${C_RESET}\n" "$default_path"
    else
        printf "  ${C_DIM}Profile default:${C_RESET} ${C_YELLOW}(none)${C_RESET}\n"
    fi

    echo ""
    printf "  ${C_BOLD}d${C_RESET}=accept default  b=browse vault  or type a path\n"

    local answer
    read -rp "  > " answer

    case "$answer" in
        d|D|"")
            CONCEPT_RESULT="$default_path"
            ;;
        b|B|browse)
            # Start browser at profile default's parent, or vault root
            local start_path=""
            if [ -n "$default_path" ] && [ -d "$VAULT_PATH/$default_path" ]; then
                start_path="$default_path"
            elif [ -n "$default_path" ]; then
                # Try parent of default
                local parent
                parent="$(dirname "$default_path")"
                case "$parent" in .|./) parent="" ;; esac
                if [ -n "$parent" ] && [ -d "$VAULT_PATH/$parent" ]; then
                    start_path="${parent}/"
                fi
            fi
            browse_path "$start_path" "$label"
            CONCEPT_RESULT="$BROWSE_RESULT"
            ;;
        *)
            # Direct path entry
            case "$answer" in
                */) CONCEPT_RESULT="$answer" ;;
                *)  CONCEPT_RESULT="${answer}/" ;;
            esac
            ;;
    esac

    # Validate path exists in vault
    if [ -n "$CONCEPT_RESULT" ] && [ ! -d "$VAULT_PATH/$CONCEPT_RESULT" ]; then
        print_warn "Folder does not exist yet: ${CONCEPT_RESULT} (OK for new setups)"
    fi

    if [ -n "$CONCEPT_RESULT" ]; then
        print_ok "${label}: ${CONCEPT_RESULT}"
    else
        print_warn "${label}: (not set)"
    fi
}

# ── Collect all concept paths (with back-navigation) ─────

CONCEPTS="inbox atomic_note map_note calendar project area source template asset"
CONCEPT_COUNT=9

# Store results in individual variables (Bash 3.2 — no associative arrays)
C_INBOX=""
C_ATOMIC_NOTE=""
C_MAP_NOTE=""
C_CALENDAR=""
C_PROJECT=""
C_AREA=""
C_SOURCE=""
C_TEMPLATE=""
C_ASSET=""

# Get concept name by 1-based index
concept_at() {
    echo "$CONCEPTS" | tr ' ' '\n' | sed -n "${1}p"
}

# Store a concept result by name
store_concept() {
    case "$1" in
        inbox)       C_INBOX="$2" ;;
        atomic_note) C_ATOMIC_NOTE="$2" ;;
        map_note)    C_MAP_NOTE="$2" ;;
        calendar)    C_CALENDAR="$2" ;;
        project)     C_PROJECT="$2" ;;
        area)        C_AREA="$2" ;;
        source)      C_SOURCE="$2" ;;
        template)    C_TEMPLATE="$2" ;;
        asset)       C_ASSET="$2" ;;
    esac
}

# Read a stored concept result by name
read_concept() {
    case "$1" in
        inbox)       echo "$C_INBOX" ;;
        atomic_note) echo "$C_ATOMIC_NOTE" ;;
        map_note)    echo "$C_MAP_NOTE" ;;
        calendar)    echo "$C_CALENDAR" ;;
        project)     echo "$C_PROJECT" ;;
        area)        echo "$C_AREA" ;;
        source)      echo "$C_SOURCE" ;;
        template)    echo "$C_TEMPLATE" ;;
        asset)       echo "$C_ASSET" ;;
    esac
}

# Show summary of configured concepts so far
show_concept_summary() {
    local up_to="$1"
    if [ "$up_to" -le 0 ]; then return; fi
    printf "\n  ${C_DIM}─── Configured so far ───${C_RESET}\n"
    local i=1
    while [ "$i" -le "$up_to" ]; do
        local c
        c="$(concept_at "$i")"
        local lbl
        lbl="$(concept_label "$c")"
        local val
        val="$(read_concept "$c")"
        if [ -n "$val" ]; then
            printf "  ${C_GREEN}✓${C_RESET} %-24s %s\n" "$lbl" "$val"
        else
            printf "  ${C_YELLOW}–${C_RESET} %-24s ${C_DIM}(not set)${C_RESET}\n" "$lbl"
        fi
        i=$((i + 1))
    done
}

# Main concept mapping loop with back-navigation
CIDX=1
while [ "$CIDX" -le "$CONCEPT_COUNT" ]; do
    concept="$(concept_at "$CIDX")"
    default_path="$(get_profile_default "$concept")"

    # Show summary of what's been configured (interactive only)
    if [ "$NON_INTERACTIVE" != "true" ] && [ "$CIDX" -gt 1 ]; then
        show_concept_summary "$((CIDX - 1))"
    fi

    prompt_concept "$concept" "$default_path"
    store_concept "$concept" "$CONCEPT_RESULT"

    # Back-navigation prompt (interactive only, not after last concept)
    if [ "$NON_INTERACTIVE" != "true" ] && [ "$CIDX" -lt "$CONCEPT_COUNT" ]; then
        echo ""
        printf "  ${C_BOLD}[Enter]${C_RESET} next  |  [b] go back\n"
        nav=""
        read -rp "  " nav
        case "$nav" in
            b|B|back)
                if [ "$CIDX" -gt 1 ]; then
                    CIDX=$((CIDX - 1))
                    continue
                fi
                ;;
        esac
    fi

    CIDX=$((CIDX + 1))
done

# Final summary
if [ "$NON_INTERACTIVE" != "true" ]; then
    show_concept_summary "$CONCEPT_COUNT"
    echo ""
    printf "  ${C_BOLD}[Enter]${C_RESET} confirm  |  [b] go back to last concept\n"
    read -rp "  " final_nav
    case "$final_nav" in
        b|B|back)
            # Jump back to last concept — re-enter loop
            CIDX=$CONCEPT_COUNT
            while [ "$CIDX" -ge 1 ]; do
                concept="$(concept_at "$CIDX")"
                default_path="$(get_profile_default "$concept")"
                show_concept_summary "$((CIDX - 1))"
                prompt_concept "$concept" "$default_path"
                store_concept "$concept" "$CONCEPT_RESULT"
                echo ""
                printf "  ${C_BOLD}[Enter]${C_RESET} confirm all  |  [b] go back further\n"
                read -rp "  " re_nav
                case "$re_nav" in
                    b|B|back)
                        if [ "$CIDX" -gt 1 ]; then
                            CIDX=$((CIDX - 1))
                            continue
                        fi
                        ;;
                    *)
                        break
                        ;;
                esac
            done
            ;;
    esac
fi

# Read extra profile values for complex concepts
MAP_NOTE_TAG=""
CALENDAR_DAILY_ENABLED="true"
CALENDAR_DAILY_PATH=""
if [ "$PROFILE" != "custom" ] && [ -f "$PROFILE_FILE" ]; then
    MAP_NOTE_TAG=$(yaml_list "$PROFILE_FILE" "map_note" "tags" | head -1)
    CALENDAR_DAILY_PATH=$(sed -n '/^  calendar:/,/^  [a-z]/p' "$PROFILE_FILE" 2>/dev/null \
        | sed -n '/daily:/,/^ /p' | grep 'path:' | head -1 | sed 's/.*: *//' | tr -d '"'"'" | tr -d '{}' | sed 's/^ *//')
fi

# ── Daily notes subfolder prompt ────────────────────────
# Ask for the daily notes path if calendar is configured
if [ -n "$C_CALENDAR" ] && [ "$NON_INTERACTIVE" != "true" ]; then
    print_step "Daily notes subfolder"
    echo "  Where are your daily notes stored?"
    DAILY_DEFAULT="${CALENDAR_DAILY_PATH:-${C_CALENDAR}Days/}"
    CALENDAR_DAILY_PATH=$(prompt_default "Daily notes path" "$DAILY_DEFAULT")
    print_ok "Daily: $CALENDAR_DAILY_PATH"
fi

# ── Step 5: Lifecycle Prefix ─────────────────────────────

print_step "Lifecycle tag prefix"

TAG_PREFIX=""
if [ -n "$FLAG_PREFIX" ]; then
    TAG_PREFIX="$FLAG_PREFIX"
else
    TAG_PREFIX=$(prompt_default "Tag prefix for Tomo lifecycle states" "MiYo-Tomo")
fi
print_ok "Prefix: $TAG_PREFIX"

# ── Instance directory ────────────────────────────────────
#
# Registry-driven selection (XDD 020 Phase 2, T2.1). Reads the instance
# registry and routes to one of two modes:
#   SELECT_MODE=create  — provision a new instance (name must not already exist)
#   SELECT_MODE=update   — re-run against an existing registered instance
# The actual path layout (create branch) and per-instance config / registry
# upsert are owned by T2.2 / T2.3 — this step only resolves name + mode.

print_step "Instance configuration"

REUSE=""
SELECT_MODE="create"

# Emptiness sentinel: non-empty when at least one instance is registered.
REGISTRY_LIST=$(registry_list 2>/dev/null || true)

if [ "$NON_INTERACTIVE" = "true" ]; then
    # Non-interactive contract: --instance-name names the target. A name that
    # already exists in the registry is rejected as a duplicate unless --update
    # is passed, in which case it must exist.
    if [ "$FLAG_UPDATE" = "true" ]; then
        if [ -z "$FLAG_INSTANCE_NAME" ]; then
            print_err "--update requires --instance-name."
            exit 1
        fi
        if ! registry_has_name "$FLAG_INSTANCE_NAME"; then
            print_err "Cannot update '$FLAG_INSTANCE_NAME': no such registered instance."
            exit 1
        fi
        SELECT_MODE="update"
        INSTANCE_NAME="$FLAG_INSTANCE_NAME"
    else
        if [ -n "$FLAG_INSTANCE_NAME" ] && registry_has_name "$FLAG_INSTANCE_NAME"; then
            print_err "Instance '$FLAG_INSTANCE_NAME' already exists. Pass --update to update it, or choose a different --instance-name."
            exit 1
        fi
        SELECT_MODE="create"
    fi
else
    if [ -z "$REGISTRY_LIST" ]; then
        # No instances registered yet — straight to first-instance create.
        SELECT_MODE="create"
    else
        # Existing instances registered — offer create-new vs update-<name>.
        # Show name (and path) per live entry so the user can type a name;
        # surface stale (dir-missing) entries on a second pass.
        echo "  Registered instances:"
        registry_list | jq -r '"    " + .name + "  (" + .path + ")"'
        registry_list_check | grep '^\[stale\]' | sed 's/^/    /' || true
        echo ""
        echo "    n. Create a new instance"
        echo "    Or type the name of an instance to update."
        SELECT_CHOICE=$(prompt_default "Choice (n / <name>)" "n")
        case "$SELECT_CHOICE" in
            n|N|"")
                SELECT_MODE="create"
                ;;
            *)
                if registry_has_name "$SELECT_CHOICE"; then
                    SELECT_MODE="update"
                    INSTANCE_NAME="$SELECT_CHOICE"
                else
                    print_warn "No registered instance named '$SELECT_CHOICE' — creating a new one."
                    SELECT_MODE="create"
                fi
                ;;
        esac
    fi

    if [ "$SELECT_MODE" = "create" ]; then
        # Obtain (and validate) the new instance name. Reject collisions with
        # an existing registry entry by re-prompting.
        while true; do
            if [ -n "$FLAG_INSTANCE_NAME" ]; then
                INSTANCE_NAME="$FLAG_INSTANCE_NAME"
            else
                INSTANCE_NAME=$(prompt_default "Instance directory name" "tomo-instance")
            fi
            if registry_has_name "$INSTANCE_NAME"; then
                print_warn "Instance '$INSTANCE_NAME' already exists — choose a different name."
                FLAG_INSTANCE_NAME=""
                continue
            fi
            break
        done
    fi
fi

# Self-contained per-instance layout (ADR-1): <parent>/<name>/ holds
# instance/ (Claude workspace), home/ (Docker /home/coder), tomo-install.json
# and begin-tomo.sh. INSTANCE_LOCATION is the PARENT dir; INSTANCE_ROOT is
# <parent>/<name>; INSTANCE_PATH is <root>/instance.
if [ "$SELECT_MODE" = "update" ]; then
    # Re-run against an existing instance: the registry stores the instance dir
    # path (<root>/instance); the instance ROOT is its parent. CONFIG_FILE is
    # read for prior settings only if it exists.
    INSTANCE_PATH=$(registry_resolve "$INSTANCE_NAME")
    INSTANCE_ROOT="$(dirname "$INSTANCE_PATH")"
    INSTANCE_LOCATION="$(dirname "$INSTANCE_ROOT")"
    echo "  Updating instance: $INSTANCE_NAME at $INSTANCE_PATH"
else
    # CLI-flag override takes priority over prompt_default — this lets the
    # integration test scripts target an isolated tmpdir instead of
    # overwriting the user's real instance. The default path behaviour (and the
    # interactive prompt) are unchanged when the flags are not passed.
    if [ -z "$INSTANCE_NAME" ]; then
        if [ -n "$FLAG_INSTANCE_NAME" ]; then
            INSTANCE_NAME="$FLAG_INSTANCE_NAME"
        else
            INSTANCE_NAME=$(prompt_default "Instance directory name" "tomo-instance")
        fi
    fi
    # --instance-location is the PARENT dir (default ~/MiYo/Tomo). Expand a
    # leading ~ to $HOME.
    if [ -n "$FLAG_INSTANCE_LOCATION" ]; then
        INSTANCE_LOCATION="$FLAG_INSTANCE_LOCATION"
    else
        INSTANCE_LOCATION=$(prompt_default "Instance parent directory" "$HOME/MiYo/Tomo")
    fi
    case "$INSTANCE_LOCATION" in
        "~") INSTANCE_LOCATION="$HOME" ;;
        "~/"*) INSTANCE_LOCATION="$HOME/${INSTANCE_LOCATION#~/}" ;;
    esac
    INSTANCE_ROOT="$INSTANCE_LOCATION/$INSTANCE_NAME"
    INSTANCE_PATH="$INSTANCE_ROOT/instance"
fi

# Create the parent dir if absent and note it (OQ8) — only on the create
# route; the update route uses the registered path, so INSTANCE_LOCATION
# is a synthetic dirname and may differ from the user's intended parent.
if [ "$SELECT_MODE" = "create" ] && [ ! -d "$INSTANCE_LOCATION" ]; then
    mkdir -p "$INSTANCE_LOCATION"
    print_ok "Created parent directory: $INSTANCE_LOCATION"
fi

# Derive the remaining self-contained paths from INSTANCE_ROOT. Explicit
# --home-dir/--config-file pin those two exactly (test isolation); absent, they
# fall under <root>/home and <root>/tomo-install.json.
if [ -n "$FLAG_CONFIG_FILE" ]; then
    CONFIG_FILE="$FLAG_CONFIG_FILE"
else
    CONFIG_FILE="$INSTANCE_ROOT/tomo-install.json"
fi

# Reuse prior settings only when the resolved per-instance config already
# exists (update re-run against a previously provisioned instance).
if [ "$SELECT_MODE" = "update" ] && [ -f "$CONFIG_FILE" ]; then
    REUSE=true
fi

# ── Step 6: Kado connection ──────────────────────────────

print_step "Kado MCP connection"

REUSE_KADO=""
if [ "$REUSE" = "true" ]; then
    KADO_HOST=$(jq -r '.kado.host' "$CONFIG_FILE")
    KADO_PORT=$(jq -r '.kado.port' "$CONFIG_FILE")
    KADO_PROTOCOL=$(jq -r '.kado.protocol' "$CONFIG_FILE")
    echo "  Existing: ${KADO_PROTOCOL}://${KADO_HOST}:${KADO_PORT}"
    RECONFIG_KADO=$(prompt_yn "Reconfigure Kado? [y/N]" "N")
    case "$RECONFIG_KADO" in
        [yY]*) REUSE_KADO=false ;;
        *) REUSE_KADO=true ;;
    esac
fi

if [ "$REUSE_KADO" != "true" ]; then
    if [ -n "$FLAG_KADO_HOST" ]; then
        KADO_HOST="$FLAG_KADO_HOST"
    else
        KADO_HOST=$(prompt_default "Kado host" "host.docker.internal")
    fi

    if [ -n "$FLAG_KADO_PORT" ]; then
        KADO_PORT="$FLAG_KADO_PORT"
    else
        KADO_PORT=$(prompt_default "Kado port" "23026")
    fi

    # Kado is HTTP-only (local-first, no TLS)
    KADO_PROTOCOL="http"

    if [ -n "$FLAG_KADO_TOKEN" ]; then
        KADO_TOKEN="$FLAG_KADO_TOKEN"
    else
        if [ "$NON_INTERACTIVE" = "true" ]; then
            KADO_TOKEN=""
            print_warn "No --kado-token provided; .mcp.json will need manual token entry."
        else
            while true; do
                read -rsp "  Kado bearer token: " KADO_TOKEN
                echo ""
                if [ -z "$KADO_TOKEN" ]; then
                    print_warn "No token provided. You can set it later in .mcp.json."
                    break
                fi
                case "$KADO_TOKEN" in
                    kado_*) break ;;
                    *)
                        print_err "Token must start with 'kado_'. Try again."
                        ;;
                esac
            done
        fi
    fi
fi

# ── Step 6b: Git user configuration (for container .gitconfig) ──

print_step "Git user configuration"

GIT_NAME=""
GIT_EMAIL=""
HOST_GIT_NAME="$(git config --global user.name 2>/dev/null || echo '')"
HOST_GIT_EMAIL="$(git config --global user.email 2>/dev/null || echo '')"

if [ "$NON_INTERACTIVE" = "true" ]; then
    GIT_NAME="$HOST_GIT_NAME"
    GIT_EMAIL="$HOST_GIT_EMAIL"
    if [ -n "$GIT_NAME" ] && [ -n "$GIT_EMAIL" ]; then
        print_ok "Git user: $GIT_NAME <$GIT_EMAIL> (from host)"
    else
        print_warn "No host git config — container .gitconfig will be skipped."
    fi
else
    if [ -n "$HOST_GIT_NAME" ] && [ -n "$HOST_GIT_EMAIL" ]; then
        echo "  Host git config: ${HOST_GIT_NAME} <${HOST_GIT_EMAIL}>"
        echo ""
        echo "    1. Use host values (recommended)"
        echo "    2. Enter different values"
        echo "    3. Skip (no container git config)"
        printf "  ${C_BOLD}[1]${C_RESET} choice: "
        read -r GIT_CHOICE
        GIT_CHOICE="${GIT_CHOICE:-1}"
    else
        echo "  No git config found on host."
        echo ""
        echo "    1. Enter values"
        echo "    2. Skip (no container git config)"
        printf "  ${C_BOLD}[1]${C_RESET} choice: "
        read -r GIT_CHOICE
        GIT_CHOICE="${GIT_CHOICE:-1}"
        # Remap so '1' = enter, '2' = skip
        case "$GIT_CHOICE" in
            1) GIT_CHOICE=2 ;;
            2) GIT_CHOICE=3 ;;
        esac
    fi

    case "$GIT_CHOICE" in
        1)
            GIT_NAME="$HOST_GIT_NAME"
            GIT_EMAIL="$HOST_GIT_EMAIL"
            print_ok "Git user: $GIT_NAME <$GIT_EMAIL>"
            ;;
        2)
            read -rp "  Name:  " GIT_NAME
            read -rp "  Email: " GIT_EMAIL
            if [ -n "$GIT_NAME" ] && [ -n "$GIT_EMAIL" ]; then
                print_ok "Git user: $GIT_NAME <$GIT_EMAIL>"
            else
                print_warn "Empty values — skipping container git config."
                GIT_NAME=""
                GIT_EMAIL=""
            fi
            ;;
        *)
            print_warn "Skipped container git config."
            ;;
    esac
fi

# Values flow into $HOME_DIR/.gitconfig below — used INSIDE the container
# for any git ops the user might run there. The instance itself is NOT
# git-init'd (see 'Writing instance .gitignore' step below).

# ── Step 6c: Voice transcription (XDD 009) ──────────────
# Load prior voice settings from tomo-install.json when re-running install,
# then run the stateful wizard. The wizard downloads the selected model
# into $INSTANCE_PATH/voice/models/ if enabled.

PRIOR_VOICE_ENABLED="false"
PRIOR_VOICE_MODEL=""
PRIOR_VOICE_LANGUAGE=""
if [ -f "$CONFIG_FILE" ]; then
    PRIOR_VOICE_ENABLED=$(jq -r '.voice.enabled // false' "$CONFIG_FILE" 2>/dev/null || echo "false")
    PRIOR_VOICE_MODEL=$(jq -r '.voice.model // ""' "$CONFIG_FILE" 2>/dev/null || echo "")
    PRIOR_VOICE_LANGUAGE=$(jq -r '.voice.language // ""' "$CONFIG_FILE" 2>/dev/null || echo "")
fi

VOICE_MODELS_DIR="$INSTANCE_PATH/voice/models"
configure_voice \
    "$PRIOR_VOICE_ENABLED" \
    "$PRIOR_VOICE_MODEL" \
    "$PRIOR_VOICE_LANGUAGE" \
    "$VOICE_MODELS_DIR" \
    "$NON_INTERACTIVE"

# ── Step 6d: Hashi IDE Bridge (XDD 019) ─────────────────
# Load prior IDE Bridge settings from tomo-install.json when re-running install,
# then run the stateful wizard. Lock file generation is deferred until HOME_DIR
# is resolved in Step 9 below.

PRIOR_IDE_ENABLED="false"
PRIOR_IDE_TOKEN=""
PRIOR_IDE_PORT="23027"
if [ -f "$CONFIG_FILE" ]; then
    PRIOR_IDE_ENABLED=$(jq -r '.ide_bridge.enabled // false' "$CONFIG_FILE" 2>/dev/null || echo "false")
    PRIOR_IDE_TOKEN=$(jq -r '.ide_bridge.auth_token // ""' "$CONFIG_FILE" 2>/dev/null || echo "")
    PRIOR_IDE_PORT=$(jq -r '.ide_bridge.port // 23027' "$CONFIG_FILE" 2>/dev/null || echo "23027")
fi

configure_ide_bridge \
    "$PRIOR_IDE_ENABLED" \
    "$PRIOR_IDE_TOKEN" \
    "$PRIOR_IDE_PORT" \
    "" \
    "$NON_INTERACTIVE"

# ── Step 7: Re-run detection & config generation ─────────

print_step "Generating vault-config.yaml"

VAULT_CONFIG_PATH="$INSTANCE_PATH/config/vault-config.yaml"

# Ensure instance config dir exists for re-run detection
mkdir -p "$INSTANCE_PATH/config" 2>/dev/null || true

if [ -f "$VAULT_CONFIG_PATH" ]; then
    echo "  Existing vault-config.yaml found."
    if [ "$NON_INTERACTIVE" = "true" ]; then
        CONFIG_ACTION="overwrite"
    else
        echo "    1. overwrite — Replace with new config"
        echo "    2. cancel    — Keep existing, skip generation"
        read -rp "  Action [1]: " CONFIG_ACTION_CHOICE
        CONFIG_ACTION_CHOICE="${CONFIG_ACTION_CHOICE:-1}"
        case "$CONFIG_ACTION_CHOICE" in
            1|overwrite) CONFIG_ACTION="overwrite" ;;
            2|cancel)    CONFIG_ACTION="cancel" ;;
            *)           CONFIG_ACTION="overwrite" ;;
        esac
    fi

    if [ "$CONFIG_ACTION" = "cancel" ]; then
        print_warn "Skipping vault-config.yaml generation."
    fi
fi

if [ "${CONFIG_ACTION:-generate}" != "cancel" ]; then
    # Build the YAML — minimal starter config
    GENERATED_DATE="$(date -u +%Y-%m-%d)"

    cat > "$VAULT_CONFIG_PATH" <<YAMLEOF
# Generated by install-tomo.sh on ${GENERATED_DATE}
# version: 0.2.0
schema_version: 1

profile: "${PROFILE}"
profile_version: "${PROFILE_VERSION}"

concepts:
  inbox: "${C_INBOX}"

  atomic_note:
    base_path: "${C_ATOMIC_NOTE}"

  map_note:
    paths:
      - "${C_MAP_NOTE}"
YAMLEOF

    # Add map_note tags if available from profile
    if [ -n "$MAP_NOTE_TAG" ]; then
        cat >> "$VAULT_CONFIG_PATH" <<YAMLEOF
    tags:
      - "${MAP_NOTE_TAG}"
YAMLEOF
    fi

    cat >> "$VAULT_CONFIG_PATH" <<YAMLEOF

  calendar:
    base_path: "${C_CALENDAR}"
    granularities:
      daily:
        enabled: ${CALENDAR_DAILY_ENABLED}
        path: "${CALENDAR_DAILY_PATH:-${C_CALENDAR}Days/}"

  project: "${C_PROJECT}"
  area: "${C_AREA}"
  source: "${C_SOURCE}"
  template: "${C_TEMPLATE}"
  asset: "${C_ASSET}"

lifecycle:
  tag_prefix: "${TAG_PREFIX}"

# Everything else (naming, templates, frontmatter, relationships,
# callouts, tags) comes from the profile defaults.
# Run /tomo-setup in Tomo to detect and configure these (delegates to /explore-vault).

# tomo.moc_proposal — tunables for /moc-propose (F-43). The block is OPTIONAL;
# when absent, the loader (shared-ctx-builder.py::load_moc_proposal_config)
# returns the spec defaults shown here. Uncomment + override only what you
# want to change. See docs/XDD/specs/013-moc-creation-skill/solution.md §10.
# tomo:
#   moc_proposal:
#     min_notes: 3                # cluster floor — ignore clusters with <N child notes
#     confidence_threshold: 0.15  # silhouette/score floor (0.0–1.0); higher = stricter
#     max_results: 5              # render top-N clusters per /moc-propose run
#     candidate_cap: 200          # abort if mode selects > N notes
#     cache_miss_max_batches: 5   # abort if topic-extraction needs > N × 10-note batches
#     squelch_runs: 3             # rejected clusters stay suppressed for N runs
YAMLEOF

    print_ok "vault-config.yaml"
fi

# ── Step 8: Create instance ──────────────────────────────

print_step "Creating instance at $INSTANCE_PATH"

mkdir -p "$INSTANCE_PATH"
mkdir -p "$INSTANCE_PATH/.claude/agents"
mkdir -p "$INSTANCE_PATH/.claude/skills"
mkdir -p "$INSTANCE_PATH/.claude/commands"
mkdir -p "$INSTANCE_PATH/.claude/rules"
mkdir -p "$INSTANCE_PATH/.claude/hooks"
mkdir -p "$INSTANCE_PATH/config"
mkdir -p "$INSTANCE_PATH/config/user-rules"
mkdir -p "$INSTANCE_PATH/scripts"
mkdir -p "$INSTANCE_PATH/voice/models"

# ── Copy managed files ────────────────────────────────────

print_step "Copying managed files from tomo/ source"

# Agents
cp "$TOMO_SOURCE/dot_claude/agents/"*.md "$INSTANCE_PATH/.claude/agents/"
print_ok "agents"

# Skills — handle BOTH formats:
#   - flat .md files (internal reference docs loaded by agents via `skills:` frontmatter)
#   - <name>/SKILL.md directories (Claude Code native skills, invoked via Skill(name))
# Recursive copy with -R covers both.
cp -R "$TOMO_SOURCE/dot_claude/skills/." "$INSTANCE_PATH/.claude/skills/"
print_ok "skills (flat .md + <name>/SKILL.md)"

# Commands
cp "$TOMO_SOURCE/dot_claude/commands/"*.md "$INSTANCE_PATH/.claude/commands/"
print_ok "commands"

# Rules (project-context only — templates are rendered separately)
cp "$TOMO_SOURCE/dot_claude/rules/project-context.md" "$INSTANCE_PATH/.claude/rules/"
print_ok "rules/project-context.md"

# Hooks
cp "$TOMO_SOURCE/dot_claude/hooks/"*.sh "$INSTANCE_PATH/.claude/hooks/"
chmod +x "$INSTANCE_PATH/.claude/hooks/"*.sh
print_ok "hooks"

# Scripts (file-suggestion.sh and any future .claude-resident scripts)
mkdir -p "$INSTANCE_PATH/.claude/scripts"
if [ -d "$TOMO_SOURCE/dot_claude/scripts" ]; then
    cp -R "$TOMO_SOURCE/dot_claude/scripts/." "$INSTANCE_PATH/.claude/scripts/"
    find "$INSTANCE_PATH/.claude/scripts" -name "*.sh" -exec chmod +x {} \;
    print_ok ".claude/scripts (file-suggestion etc.)"
fi

# Cache directory (used by file-suggestion.sh; mounted into container)
mkdir -p "$INSTANCE_PATH/cache"
print_ok "cache/"

# Settings
cp "$TOMO_SOURCE/dot_claude/settings.json" "$INSTANCE_PATH/.claude/settings.json"

# Runtime Python scripts (used by agents via `python3 scripts/<name>.py`)
# and their shared kado_client library. Host-side scripts (install,
# cleanup, update, begin-tomo template, test-phase*) are NOT copied.
cp "$TOMO_SOURCE/scripts/"*.py "$INSTANCE_PATH/scripts/"
cp "$TOMO_SOURCE/scripts/tomo-statusline.sh" "$INSTANCE_PATH/scripts/"
chmod +x "$INSTANCE_PATH/scripts/tomo-statusline.sh"
mkdir -p "$INSTANCE_PATH/scripts/lib"
cp "$TOMO_SOURCE/scripts/lib/"*.py "$INSTANCE_PATH/scripts/lib/"
print_ok "scripts (Python runtime + statusline + lib/)"

# Profiles — needed at runtime so shared-ctx-builder and other tools can load
# classification keywords and other profile data.
mkdir -p "$INSTANCE_PATH/profiles"
cp "$PROFILES_DIR/"*.yaml "$INSTANCE_PATH/profiles/"
print_ok "profiles/"

# JSON Schemas — referenced by Python scripts for validation
mkdir -p "$INSTANCE_PATH/schemas"
cp "$TOMO_SOURCE/schemas/"*.json "$INSTANCE_PATH/schemas/"
print_ok "schemas/"

# JSON templates — generated from schemas; consumed by agents at runtime
mkdir -p "$INSTANCE_PATH/templates"
# Regenerate in the instance from the authoritative schemas so the template
# is always current. No py-yaml dep — uses stdlib only.
python3 "$TOMO_SOURCE/scripts/template-from-schema.py" \
    --schema "$INSTANCE_PATH/schemas/item-result.schema.json" \
    --output "$INSTANCE_PATH/templates/item-result.template.json" \
    >/dev/null 2>&1 || cp "$TOMO_SOURCE/templates/"*.json "$INSTANCE_PATH/templates/" 2>/dev/null
print_ok "templates/"
print_ok "settings.json"

# ── Render templates ──────────────────────────────────────

print_step "Rendering templates"

# CLAUDE.md
sed -e "s|{{INSTANCE_NAME}}|${INSTANCE_NAME}|g" \
    -e "s|{{KADO_HOST}}|${KADO_HOST}|g" \
    -e "s|{{KADO_PORT}}|${KADO_PORT}|g" \
    -e "s|{{KADO_PROTOCOL}}|${KADO_PROTOCOL}|g" \
    "$TOMO_SOURCE/CLAUDE.md.template" > "$INSTANCE_PATH/CLAUDE.md"
print_ok "CLAUDE.md"

# vault-config human-readable summary (rendered with actual vault info)
if [ ! -f "$INSTANCE_PATH/config/vault-config.md" ]; then
    VAULT_NAME="$(basename "$VAULT_PATH")"
    sed -e "s|{{VAULT_NAME}}|${VAULT_NAME}|g" \
        -e "s|{{INBOX_PATH}}|${C_INBOX}|g" \
        "$TOMO_SOURCE/config/vault-config.md.template" > "$INSTANCE_PATH/config/vault-config.md"
    print_ok "config/vault-config.md (new)"
else
    print_warn "config/vault-config.md exists — skipped"
fi

# kado-config human-readable summary (only if not present — user file)
if [ ! -f "$INSTANCE_PATH/config/kado-config.md" ]; then
    sed -e "s|{{KADO_HOST}}|${KADO_HOST}|g" \
        -e "s|{{KADO_PORT}}|${KADO_PORT}|g" \
        -e "s|{{KADO_PROTOCOL}}|${KADO_PROTOCOL}|g" \
        "$TOMO_SOURCE/config/kado-config.md.template" > "$INSTANCE_PATH/config/kado-config.md"
    print_ok "config/kado-config.md (new)"
else
    print_warn "config/kado-config.md exists — skipped"
fi

# vault-example.yaml stays in tomo/config/ as schema reference — not copied to instance

# user-rules README (only if not present — user territory)
if [ ! -f "$INSTANCE_PATH/config/user-rules/README.md" ]; then
    cp "$TOMO_SOURCE/config/templates/user-rules-README.md" \
       "$INSTANCE_PATH/config/user-rules/README.md"
    print_ok "user-rules/README.md (new)"
else
    print_warn "user-rules/README.md exists — skipped"
fi

# ── MCP config ────────────────────────────────────────────

print_step "Configuring Kado MCP connection"

cat > "$INSTANCE_PATH/.mcp.json" << MCPEOF
{
  "mcpServers": {
    "kado": {
      "type": "http",
      "url": "${KADO_PROTOCOL}://${KADO_HOST}:${KADO_PORT}/mcp",
      "headers": {
        "Authorization": "Bearer ${KADO_TOKEN}"
      }
    }
  }
}
MCPEOF
print_ok ".mcp.json"

# ── Step 9: Home directory ───────────────────────────────

print_step "Setting up tomo-home/"

if [ -n "$FLAG_HOME_DIR" ]; then
    HOME_DIR="$FLAG_HOME_DIR"
else
    HOME_DIR="$INSTANCE_ROOT/home"
fi
mkdir -p "$HOME_DIR/.claude"

# Copy entrypoint
cp "$REPO_ROOT/docker/entrypoint.sh" "$HOME_DIR/entrypoint.sh"
chmod +x "$HOME_DIR/entrypoint.sh"
print_ok "entrypoint.sh"

# Auth — copy from host if available
if [ -f "$HOME/.claude.json" ]; then
    # Extract auth fields only
    jq '{oauthAccount, userID, hasAvailableSubscription, hasActiveSubscription, currentOrgId, currentPlanName, planExpiresAt, planRenewsAt}' \
        "$HOME/.claude.json" > "$HOME_DIR/.claude.json" 2>/dev/null || true
    print_ok ".claude.json (auth extracted from host)"
else
    print_warn "No ~/.claude.json found — run 'claude login' inside the container on first start"
fi

if [ -f "$HOME/.claude/.credentials.json" ]; then
    cp "$HOME/.claude/.credentials.json" "$HOME_DIR/.claude/.credentials.json"
    print_ok ".credentials.json (copied from host)"
else
    print_warn "No .credentials.json found — browser auth will be needed"
fi

# Write .gitconfig for the Docker container user (coder)
# This applies globally inside the container for all git operations.
if [ -n "$GIT_NAME" ] && [ -n "$GIT_EMAIL" ]; then
    cat > "$HOME_DIR/.gitconfig" <<GITEOF
[user]
    name = ${GIT_NAME}
    email = ${GIT_EMAIL}

[init]
    defaultBranch = main

[safe]
    directory = *
GITEOF
    print_ok ".gitconfig (container git user)"
fi

# ── Generate begin-tomo.sh launcher ──────────────────────

print_step "Generating begin-tomo.sh launcher"

LAUNCHER_TEMPLATE="$REPO_ROOT/scripts/lib/begin-tomo.sh.template"
LAUNCHER_PATH="$INSTANCE_ROOT/begin-tomo.sh"

if [ ! -f "$LAUNCHER_TEMPLATE" ]; then
    print_err "Launcher template not found: $LAUNCHER_TEMPLATE"
    exit 1
fi

render_launcher "$LAUNCHER_TEMPLATE" "$LAUNCHER_PATH" "$INSTANCE_NAME" "$INSTANCE_PATH" "$HOME_DIR" "$REPO_ROOT" "9999"
print_ok "begin-tomo.sh → $LAUNCHER_PATH"

# ── Save config ───────────────────────────────────────────

print_step "Saving install config"

cat > "$CONFIG_FILE" << CFGEOF
{
  "version": "${TOMO_VERSION}",
  "instanceName": "${INSTANCE_NAME}",
  "instanceLocation": "${INSTANCE_LOCATION}",
  "instancePath": "${INSTANCE_PATH}",
  "repoPath": "${REPO_ROOT}",
  "launcherPath": "${LAUNCHER_PATH}",
  "homePath": "${HOME_DIR}",
  "vaultPath": "${VAULT_PATH}",
  "profile": "${PROFILE}",
  "profileVersion": "${PROFILE_VERSION}",
  "lifecyclePrefix": "${TAG_PREFIX}",
  "kado": {
    "host": "${KADO_HOST}",
    "port": ${KADO_PORT},
    "protocol": "${KADO_PROTOCOL}"
  },
  "voice": {},
  "ide_bridge": {},
  "installedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tomoVersion": "${TOMO_VERSION}"
}
CFGEOF
print_ok "tomo-install.json"

# Register the instance so future installs can route to it (ADR-2 / D-09).
# INSTANCE_PATH = <root>/instance — the convention update routing depends on.
registry_upsert "$INSTANCE_NAME" "$INSTANCE_PATH" "$REPO_ROOT" "$TOMO_VERSION"
print_ok "instance registered: $INSTANCE_NAME → $INSTANCE_PATH"

# Persist the voice block via the shared write_voice_config helper —
# single authoritative writer for schema_version + enabled/model/language.
# Review findings M1 (jq-safe assembly), L4 (schema_version), M9 (dedup).
write_voice_config "$CONFIG_FILE"

# Mirror the voice block into the instance so runtime agents can read it.
# tomo-install.json lives at the HOST repo root and is NOT accessible from
# inside the Docker container (only $INSTANCE_PATH is bind-mounted). The
# voice-transcriber agent and inbox-orchestrator's Phase 0a both read the
# mirrored file at voice/config.json (relative to the instance cwd).
mkdir -p "$INSTANCE_PATH/voice"
jq '.voice // {"enabled": false, "model": "", "language": ""}' "$CONFIG_FILE" \
    > "$INSTANCE_PATH/voice/config.json"
print_ok "voice/config.json (mirrored into instance)"

# Persist the IDE Bridge block. No instance mirror — the lock file written
# into the bind-mounted tomo-home IS the runtime source for the entrypoint
# and statusline; begin-tomo reads tomo-install.json host-side (XDD 019).
write_ide_bridge_config "$CONFIG_FILE"
if [ "$IDE_BRIDGE_ENABLED" = "true" ]; then
    write_ide_lock "$HOME_DIR" "$IDE_BRIDGE_PORT" "$IDE_BRIDGE_TOKEN" "$INSTANCE_PATH"
    print_ok "ide lock: $HOME_DIR/.claude/ide/${IDE_BRIDGE_PORT}.lock"
else
    remove_ide_lock "$HOME_DIR" "$IDE_BRIDGE_PORT"
fi

# Instances live OUTSIDE the repo now (ADR-1), so no repo-.gitignore entry is
# needed; the obsolete append block was removed. The instance-root .gitignore
# below is still written for users who choose to `git init` their instance.

# ── Instance scratch dir + .gitignore (optional) ─────────
#
# We intentionally do NOT `git init` inside the instance. Rationale:
#   - Instance is bind-mounted infrastructure, not a code project
#   - Versioning lives in the HOST repo (miyo-tomo source)
#   - A nested .git/ invites subtle bugs: when it becomes corrupt,
#     git commands run with cwd inside the instance walk UP to the
#     parent repo silently (observed 2026-04-20 — "tomo-instance wipe"
#     incident where a corrupt inner .git turned `git clean -fdX` from
#     the host into a tomo-instance-wipe).
#
# We still write a .gitignore at the instance root so that users who
# CHOOSE to `git init` manually have sensible defaults.

print_step "Writing instance .gitignore + scratch dir"

cat > "$INSTANCE_PATH/.gitignore" <<IGNOREEOF
# MiYo Tomo instance — secrets and runtime state
# NOTE: instance is NOT auto-git-init'd by install. If you `git init` here
# manually, these patterns exclude the most sensitive / ephemeral files.
#
# The bearer token in .mcp.json must never be committed.
.mcp.json

# Claude Code runtime / local overrides
.claude/settings.local.json
.claude/*.log
.claude/cache/

# Tomo scratch dir — pipeline intermediates, cleared between runs
tomo-tmp/

# OS
.DS_Store
Thumbs.db
IGNOREEOF
print_ok ".gitignore"

mkdir -p "$INSTANCE_PATH/tomo-tmp/items"
print_ok "tomo-tmp/ scratch dir (+ items/)"

# ── Step 10: Done ────────────────────────────────────────

echo ""
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
printf "  ${C_BOLD}${C_GREEN}✓ Tomo instance created${C_RESET}\n"
echo ""
printf "  Instance:     ${C_CYAN}%s${C_RESET}\n" "$INSTANCE_PATH"
printf "  Home:         ${C_CYAN}%s${C_RESET}\n" "$HOME_DIR"
printf "  Vault config: ${C_CYAN}%s${C_RESET}\n" "$VAULT_CONFIG_PATH"
printf "  Profile:      ${C_CYAN}%s v%s${C_RESET}\n" "$PROFILE" "$PROFILE_VERSION"
echo ""
printf "  ${C_BOLD}Next steps:${C_RESET}\n"
printf "    1. Review config: ${C_DIM}%s/config/vault-config.yaml${C_RESET}\n" "$INSTANCE_PATH"
printf "    2. Start Tomo:    ${C_DIM}bash %s${C_RESET}\n" "$LAUNCHER_PATH"
printf "       (builds the Docker image on first run)\n"
printf "    3. First run:     ${C_DIM}use /tomo-setup to complete setup${C_RESET}\n"
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
