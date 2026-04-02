#!/bin/bash
# install-tomo.sh — Create a Tomo instance from source templates.
# Copies agents, skills, commands, and configs into the instance directory.
# Sets up tomo-home/ as the Docker /home/coder mount.
# version: 0.1.0
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOMO_SOURCE="$REPO_ROOT/tomo"
CONFIG_FILE="$REPO_ROOT/tomo-install.json"

# ── Helpers ───────────────────────────────────────────────

print_step() { echo ""; echo "▸ $1"; }
print_ok()   { echo "  ✓ $1"; }
print_warn() { echo "  ⚠ $1"; }
print_err()  { echo "  ✗ $1" >&2; }

# ── Prerequisites ─────────────────────────────────────────

print_step "Checking prerequisites"
for cmd in docker git jq; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        print_err "$cmd is required but not installed."
        exit 1
    fi
    print_ok "$cmd"
done

# ── Instance directory ────────────────────────────────────

print_step "Instance configuration"

if [ -f "$CONFIG_FILE" ]; then
    echo "  Found existing config: $CONFIG_FILE"
    INSTANCE_NAME=$(jq -r '.instanceName' "$CONFIG_FILE")
    INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG_FILE")
    echo "  Instance: $INSTANCE_NAME at $INSTANCE_PATH"
    read -rp "  Use existing config? [Y/n] " USE_EXISTING
    case "$USE_EXISTING" in
        [nN]*) ;;
        *) echo "  Using existing config."; REUSE=true ;;
    esac
fi

if [ "$REUSE" != "true" ]; then
    read -rp "  Instance directory name [tomo-instance]: " INSTANCE_NAME
    INSTANCE_NAME="${INSTANCE_NAME:-tomo-instance}"

    read -rp "  Instance location [${REPO_ROOT}]: " INSTANCE_LOCATION
    INSTANCE_LOCATION="${INSTANCE_LOCATION:-$REPO_ROOT}"
    INSTANCE_PATH="$INSTANCE_LOCATION/$INSTANCE_NAME"
fi

# ── Kado connection ───────────────────────────────────────

print_step "Kado MCP connection"

if [ "$REUSE" = "true" ]; then
    KADO_HOST=$(jq -r '.kado.host' "$CONFIG_FILE")
    KADO_PORT=$(jq -r '.kado.port' "$CONFIG_FILE")
    KADO_PROTOCOL=$(jq -r '.kado.protocol' "$CONFIG_FILE")
    echo "  Existing: ${KADO_PROTOCOL}://${KADO_HOST}:${KADO_PORT}"
    read -rp "  Reconfigure Kado? [y/N] " RECONFIG_KADO
    case "$RECONFIG_KADO" in
        [yY]*) REUSE_KADO=false ;;
        *) REUSE_KADO=true ;;
    esac
fi

if [ "$REUSE_KADO" != "true" ]; then
    read -rp "  Kado host [host.docker.internal]: " KADO_HOST
    KADO_HOST="${KADO_HOST:-host.docker.internal}"

    read -rp "  Kado port [37022]: " KADO_PORT
    KADO_PORT="${KADO_PORT:-37022}"

    read -rp "  Kado protocol [http]: " KADO_PROTOCOL
    KADO_PROTOCOL="${KADO_PROTOCOL:-http}"

    read -rsp "  Kado bearer token: " KADO_TOKEN
    echo ""
fi

# ── Create instance ───────────────────────────────────────

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

# vault-config (only if not present — user file)
if [ ! -f "$INSTANCE_PATH/.claude/rules/vault-config.md" ]; then
    sed -e "s|{{VAULT_NAME}}|My Vault|g" \
        -e "s|{{INBOX_PATH}}|00 Inbox|g" \
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

# ── Home directory ────────────────────────────────────────

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
  "version": "0.1.0",
  "instanceName": "${INSTANCE_NAME}",
  "instancePath": "${INSTANCE_PATH}",
  "homePath": "${HOME_DIR}",
  "kado": {
    "host": "${KADO_HOST}",
    "port": ${KADO_PORT},
    "protocol": "${KADO_PROTOCOL}"
  },
  "installedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tomoVersion": "0.1.0"
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

# ── Done ──────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Tomo instance created at: $INSTANCE_PATH"
echo "  Home directory: $HOME_DIR"
echo ""
echo "  Next steps:"
echo "    1. Review config: $INSTANCE_PATH/config/"
echo "    2. Build image:   docker build -t miyo-tomo:latest ./docker/"
echo "    3. Start Tomo:    bash begin-tomo.sh"
echo ""
echo "  Recommended: initialize instance as its own git repo:"
echo "    cd $INSTANCE_PATH && git init && git add -A && git commit -m 'Initial Tomo instance'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
