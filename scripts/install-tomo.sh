#!/bin/bash
# install-tomo.sh — Create a Tomo instance from source templates.
# Copies agents, skills, commands, and configs into the instance directory.
# Sets up tomo-home/ as the Docker /home/coder mount.
# Runs the Phase 1 setup wizard: vault path, profile selection, concept mapping,
# lifecycle prefix, and vault-config.yaml generation.
# version: 0.2.0
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOMO_SOURCE="$REPO_ROOT/tomo"
CONFIG_FILE="$REPO_ROOT/tomo-install.json"
PROFILES_DIR="$TOMO_SOURCE/profiles"
TOMO_VERSION="0.2.0"

# ── CLI Flags ────────────────────────────────────────────

NON_INTERACTIVE=false
FLAG_VAULT=""
FLAG_PROFILE=""
FLAG_KADO_HOST=""
FLAG_KADO_PORT=""
FLAG_KADO_TOKEN=""
FLAG_PREFIX=""
SHOW_HELP=false

while [ $# -gt 0 ]; do
    case "$1" in
        --vault)       FLAG_VAULT="$2";     shift 2 ;;
        --profile)     FLAG_PROFILE="$2";   shift 2 ;;
        --kado-host)   FLAG_KADO_HOST="$2"; shift 2 ;;
        --kado-port)   FLAG_KADO_PORT="$2"; shift 2 ;;
        --kado-token)  FLAG_KADO_TOKEN="$2"; shift 2 ;;
        --prefix)      FLAG_PREFIX="$2";    shift 2 ;;
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
  --non-interactive     Use defaults for all prompts (requires --vault)
  --help, -h            Show this help message

Interactive mode (default):
  Walks through vault path, profile selection, concept mapping, lifecycle
  prefix, and Kado connection. Generates vault-config.yaml in instance.

Non-interactive mode:
  Requires at least --vault. Uses profile defaults for concept paths.
  Suitable for CI/automation.

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

print_step "Instance configuration"

REUSE=""
if [ -f "$CONFIG_FILE" ]; then
    echo "  Found existing config: $CONFIG_FILE"
    INSTANCE_NAME=$(jq -r '.instanceName' "$CONFIG_FILE")
    INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG_FILE")
    # instanceLocation was added in a later version; derive from instancePath as fallback
    INSTANCE_LOCATION=$(jq -r '.instanceLocation // empty' "$CONFIG_FILE")
    if [ -z "$INSTANCE_LOCATION" ]; then
        INSTANCE_LOCATION="$(dirname "$INSTANCE_PATH")"
    fi
    echo "  Instance: $INSTANCE_NAME at $INSTANCE_PATH"
    USE_EXISTING=$(prompt_yn "Use existing config? [Y/n]" "Y")
    case "$USE_EXISTING" in
        [nN]*) ;;
        *) echo "  Using existing config."; REUSE=true ;;
    esac
fi

if [ "$REUSE" != "true" ]; then
    INSTANCE_NAME=$(prompt_default "Instance directory name" "tomo-instance")
    INSTANCE_LOCATION=$(prompt_default "Instance location" "$REPO_ROOT")
    INSTANCE_PATH="$INSTANCE_LOCATION/$INSTANCE_NAME"
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

# ── Step 6b: Git user configuration ──────────────────────

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
        print_warn "No host git config — skipped."
    fi
else
    if [ -n "$HOST_GIT_NAME" ] && [ -n "$HOST_GIT_EMAIL" ]; then
        echo "  Host git config: ${HOST_GIT_NAME} <${HOST_GIT_EMAIL}>"
        echo ""
        echo "    1. Use host values (recommended)"
        echo "    2. Enter different values"
        echo "    3. Skip (no git config)"
        printf "  ${C_BOLD}[1]${C_RESET} choice: "
        read -r GIT_CHOICE
        GIT_CHOICE="${GIT_CHOICE:-1}"
    else
        echo "  No git config found on host."
        echo ""
        echo "    1. Enter values"
        echo "    2. Skip (no git config)"
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
                print_warn "Empty values — skipping git config."
                GIT_NAME=""
                GIT_EMAIL=""
            fi
            ;;
        *)
            print_warn "Skipped git config (can be set later)."
            ;;
    esac
fi

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
# Run /explore-vault in Tomo to detect and configure these.
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
mkdir -p "$INSTANCE_PATH/scripts"

# ── Copy managed files ────────────────────────────────────

print_step "Copying managed files from tomo/ source"

# Agents
cp "$TOMO_SOURCE/.claude/agents/"*.md "$INSTANCE_PATH/.claude/agents/"
print_ok "agents"

# Skills
cp "$TOMO_SOURCE/.claude/skills/"*.md "$INSTANCE_PATH/.claude/skills/"
print_ok "skills"

# Commands
cp "$TOMO_SOURCE/.claude/commands/"*.md "$INSTANCE_PATH/.claude/commands/"
print_ok "commands"

# Rules (project-context only — templates are rendered separately)
cp "$TOMO_SOURCE/.claude/rules/project-context.md" "$INSTANCE_PATH/.claude/rules/"
print_ok "rules/project-context.md"

# Hooks
cp "$TOMO_SOURCE/.claude/hooks/"*.sh "$INSTANCE_PATH/.claude/hooks/"
chmod +x "$INSTANCE_PATH/.claude/hooks/"*.sh
print_ok "hooks"

# Settings
cp "$TOMO_SOURCE/.claude/settings.json" "$INSTANCE_PATH/.claude/settings.json"

# Runtime Python scripts (used by agents via `python3 scripts/<name>.py`)
# and their shared kado_client library. Host-side scripts (install,
# cleanup, update, begin-tomo template, test-phase*) are NOT copied.
cp "$REPO_ROOT/scripts/"*.py "$INSTANCE_PATH/scripts/"
mkdir -p "$INSTANCE_PATH/scripts/lib"
cp "$REPO_ROOT/scripts/lib/"*.py "$INSTANCE_PATH/scripts/lib/"
print_ok "scripts (Python runtime + lib/)"
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

# vault-config rule (rendered with actual vault info)
if [ ! -f "$INSTANCE_PATH/.claude/rules/vault-config.md" ]; then
    VAULT_NAME="$(basename "$VAULT_PATH")"
    sed -e "s|{{VAULT_NAME}}|${VAULT_NAME}|g" \
        -e "s|{{INBOX_PATH}}|${C_INBOX}|g" \
        "$TOMO_SOURCE/.claude/rules/vault-config.template.md" > "$INSTANCE_PATH/.claude/rules/vault-config.md"
    print_ok "vault-config.md (new)"
else
    print_warn "vault-config.md exists — skipped"
fi

# kado-config (only if not present — user file)
if [ ! -f "$INSTANCE_PATH/.claude/rules/kado-config.md" ]; then
    sed -e "s|{{KADO_HOST}}|${KADO_HOST}|g" \
        -e "s|{{KADO_PORT}}|${KADO_PORT}|g" \
        -e "s|{{KADO_PROTOCOL}}|${KADO_PROTOCOL}|g" \
        "$TOMO_SOURCE/.claude/rules/kado-config.template.md" > "$INSTANCE_PATH/.claude/rules/kado-config.md"
    print_ok "kado-config.md (new)"
else
    print_warn "kado-config.md exists — skipped"
fi

# vault-example.yaml stays in tomo/config/ as schema reference — not copied to instance

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

HOME_DIR="$REPO_ROOT/tomo-home"
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

LAUNCHER_TEMPLATE="$REPO_ROOT/scripts/begin-tomo.sh.template"
LAUNCHER_PATH="$INSTANCE_LOCATION/begin-tomo.sh"

if [ ! -f "$LAUNCHER_TEMPLATE" ]; then
    print_err "Launcher template not found: $LAUNCHER_TEMPLATE"
    exit 1
fi

sed -e "s|{{INSTANCE_PATH}}|${INSTANCE_PATH}|g" \
    -e "s|{{INSTANCE_NAME}}|${INSTANCE_NAME}|g" \
    -e "s|{{HOME_DIR}}|${HOME_DIR}|g" \
    -e "s|{{TOMO_REPO_ROOT}}|${REPO_ROOT}|g" \
    -e "s|{{DEV_NOTIFY_PORT}}|9999|g" \
    "$LAUNCHER_TEMPLATE" > "$LAUNCHER_PATH"
chmod +x "$LAUNCHER_PATH"
print_ok "begin-tomo.sh → $LAUNCHER_PATH"

# ── Save config ───────────────────────────────────────────

print_step "Saving install config"

cat > "$CONFIG_FILE" << CFGEOF
{
  "version": "${TOMO_VERSION}",
  "instanceName": "${INSTANCE_NAME}",
  "instanceLocation": "${INSTANCE_LOCATION}",
  "instancePath": "${INSTANCE_PATH}",
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
  "installedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tomoVersion": "${TOMO_VERSION}"
}
CFGEOF
print_ok "tomo-install.json"

# ── Update .gitignore (parent repo) ──────────────────────

if ! grep -q "^${INSTANCE_NAME}/" "$REPO_ROOT/.gitignore" 2>/dev/null; then
    # Add instance dir if not the default (already in .gitignore)
    if [ "$INSTANCE_NAME" != "tomo-instance" ]; then
        echo "${INSTANCE_NAME}/" >> "$REPO_ROOT/.gitignore"
        print_ok "Added $INSTANCE_NAME/ to .gitignore"
    fi
fi

# ── Initialize instance git repository ───────────────────

print_step "Initializing instance git repository"

# Write instance .gitignore first (excludes secrets and runtime state)
cat > "$INSTANCE_PATH/.gitignore" <<IGNOREEOF
# MiYo Tomo instance — secrets and runtime state
# The bearer token in .mcp.json must never be committed.
.mcp.json

# Claude Code runtime / local overrides
.claude/settings.local.json
.claude/*.log
.claude/cache/

# OS
.DS_Store
Thumbs.db
IGNOREEOF
print_ok ".gitignore"

# Detect existing repo: if .git exists, don't touch it.
if [ -d "$INSTANCE_PATH/.git" ]; then
    print_warn "Instance already has a .git/ — skipping init."
else
    if git -C "$INSTANCE_PATH" init --quiet 2>/dev/null; then
        print_ok "git init"

        # Set local git user (overrides global in this repo)
        if [ -n "$GIT_NAME" ] && [ -n "$GIT_EMAIL" ]; then
            git -C "$INSTANCE_PATH" config user.name "$GIT_NAME" 2>/dev/null || true
            git -C "$INSTANCE_PATH" config user.email "$GIT_EMAIL" 2>/dev/null || true
            print_ok "git config user.name/email"
        fi

        # Ensure default branch is main (for older git versions that default to master)
        git -C "$INSTANCE_PATH" symbolic-ref HEAD refs/heads/main 2>/dev/null || true

        # Initial commit — requires git user to be set
        if [ -n "$GIT_NAME" ] && [ -n "$GIT_EMAIL" ]; then
            if git -C "$INSTANCE_PATH" add -A 2>/dev/null && \
               git -C "$INSTANCE_PATH" commit -m "Initial Tomo instance" --quiet 2>/dev/null; then
                print_ok "Initial commit"
            else
                print_warn "Initial commit failed — please commit manually."
            fi
        else
            print_warn "No git user set — skipping initial commit."
            print_warn "  To commit later: cd $INSTANCE_PATH && git add -A && git commit -m 'Initial'"
        fi
    else
        print_warn "git init failed — please initialize manually."
    fi
fi

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
printf "    3. First run:     ${C_DIM}use /explore-vault to complete setup${C_RESET}\n"
printf "${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}\n"
