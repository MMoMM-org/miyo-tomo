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

# ── Helpers ───────────────────────────────────────────────

print_step() { echo ""; echo "▸ $1"; }
print_ok()   { echo "  ✓ $1"; }
print_warn() { echo "  ⚠ $1"; }
print_err()  { echo "  ✗ $1" >&2; }

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

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MiYo Tomo — Setup Wizard v${TOMO_VERSION}"
echo "  AI-assisted PKM workflows for Obsidian"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

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
echo "  Top-level vault folders:"
# Build indexed list of top-level directories (Bash 3.2 safe — no arrays needed for display)
VAULT_FOLDERS=""
FOLDER_COUNT=0
for d in "$VAULT_PATH"/*/; do
    if [ -d "$d" ]; then
        dname="$(basename "$d")"
        # Skip hidden folders
        case "$dname" in
            .*) continue ;;
        esac
        FOLDER_COUNT=$((FOLDER_COUNT + 1))
        VAULT_FOLDERS="${VAULT_FOLDERS}${dname}
"
        echo "    ${FOLDER_COUNT}. ${dname}/"
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

# Prompt for a single concept path
# Returns the confirmed path in CONCEPT_RESULT
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

    echo ""
    echo "  ${label}:"
    if [ -n "$default_path" ]; then
        echo "    Profile default: ${default_path}"
    else
        echo "    Profile default: (none)"
    fi

    # Show vault folders for reference
    echo "    Vault top-level folders:"
    local i=0
    local IFS_OLD="$IFS"
    IFS="
"
    for folder in $VAULT_FOLDERS; do
        i=$((i + 1))
        echo "      ${i}. ${folder}/"
    done
    IFS="$IFS_OLD"

    local answer
    if [ -n "$default_path" ]; then
        read -rp "    Use default (${default_path}) or enter path: " answer
    else
        read -rp "    Enter path: " answer
    fi

    if [ -z "$answer" ]; then
        CONCEPT_RESULT="$default_path"
    else
        # Check if answer is a number (folder selection)
        case "$answer" in
            [0-9]|[0-9][0-9])
                local j=0
                local matched=""
                IFS="
"
                for folder in $VAULT_FOLDERS; do
                    j=$((j + 1))
                    if [ "$j" -eq "$answer" ]; then
                        matched="${folder}/"
                        break
                    fi
                done
                IFS="$IFS_OLD"
                if [ -n "$matched" ]; then
                    CONCEPT_RESULT="$matched"
                else
                    CONCEPT_RESULT="$answer"
                fi
                ;;
            *)
                # Ensure trailing slash
                case "$answer" in
                    */) CONCEPT_RESULT="$answer" ;;
                    *)  CONCEPT_RESULT="${answer}/" ;;
                esac
                ;;
        esac
    fi

    # Validate path exists in vault
    if [ -n "$CONCEPT_RESULT" ] && [ ! -d "$VAULT_PATH/$CONCEPT_RESULT" ]; then
        print_warn "Folder does not exist yet: ${CONCEPT_RESULT} (OK for new setups)"
    fi

    print_ok "${label}: ${CONCEPT_RESULT}"
}

# Collect all concept paths
CONCEPTS="inbox atomic_note map_note calendar project area source template asset"

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

for concept in $CONCEPTS; do
    default_path="$(get_profile_default "$concept")"
    prompt_concept "$concept" "$default_path"
    case "$concept" in
        inbox)       C_INBOX="$CONCEPT_RESULT" ;;
        atomic_note) C_ATOMIC_NOTE="$CONCEPT_RESULT" ;;
        map_note)    C_MAP_NOTE="$CONCEPT_RESULT" ;;
        calendar)    C_CALENDAR="$CONCEPT_RESULT" ;;
        project)     C_PROJECT="$CONCEPT_RESULT" ;;
        area)        C_AREA="$CONCEPT_RESULT" ;;
        source)      C_SOURCE="$CONCEPT_RESULT" ;;
        template)    C_TEMPLATE="$CONCEPT_RESULT" ;;
        asset)       C_ASSET="$CONCEPT_RESULT" ;;
    esac
done

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
        KADO_PORT=$(prompt_default "Kado port" "37022")
    fi

    KADO_PROTOCOL=$(prompt_default "Kado protocol" "http")

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

# Example configs (only if not present)
for cfg in vault-example.yaml kado-example.yaml; do
    if [ ! -f "$INSTANCE_PATH/config/$cfg" ]; then
        cp "$TOMO_SOURCE/config/$cfg" "$INSTANCE_PATH/config/$cfg"
        print_ok "config/$cfg"
    fi
done

# ── MCP config ────────────────────────────────────────────

print_step "Configuring Kado MCP connection"

cat > "$INSTANCE_PATH/.mcp.json" << MCPEOF
{
  "mcpServers": {
    "kado": {
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

# ── Save config ───────────────────────────────────────────

print_step "Saving install config"

cat > "$CONFIG_FILE" << CFGEOF
{
  "version": "${TOMO_VERSION}",
  "instanceName": "${INSTANCE_NAME}",
  "instancePath": "${INSTANCE_PATH}",
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

# ── Update .gitignore ────────────────────────────────────

if ! grep -q "^${INSTANCE_NAME}/" "$REPO_ROOT/.gitignore" 2>/dev/null; then
    # Add instance dir if not the default (already in .gitignore)
    if [ "$INSTANCE_NAME" != "tomo-instance" ]; then
        echo "${INSTANCE_NAME}/" >> "$REPO_ROOT/.gitignore"
        print_ok "Added $INSTANCE_NAME/ to .gitignore"
    fi
fi

# ── Step 10: Done ────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Tomo instance created at: $INSTANCE_PATH"
echo "  Home directory: $HOME_DIR"
echo "  Vault config:   $VAULT_CONFIG_PATH"
echo "  Profile:        ${PROFILE} v${PROFILE_VERSION}"
echo ""
echo "  Next steps:"
echo "    1. Review config: $INSTANCE_PATH/config/vault-config.yaml"
echo "    2. Build image:   docker build -t miyo-tomo:latest ./docker/"
echo "    3. Start Tomo:    bash begin-tomo.sh"
echo "    4. First run:     use /explore-vault to complete setup"
echo ""
echo "  Recommended: initialize instance as its own git repo:"
echo "    cd $INSTANCE_PATH && git init && git add -A && git commit -m 'Initial Tomo instance'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
