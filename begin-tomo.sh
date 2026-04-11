#!/bin/bash
# begin-tomo.sh — Start a Tomo Docker session.
# Reads tomo-install.json for instance path and home directory.
# version: 0.1.0
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/tomo-install.json"

# ── Helpers ───────────────────────────────────────────────

print_step() { echo ""; echo "▸ $1"; }
print_ok()   { echo "  ✓ $1"; }
print_warn() { echo "  ⚠ $1"; }
print_err()  { echo "  ✗ $1" >&2; }

# ── Load config ───────────────────────────────────────────

if [ ! -f "$CONFIG_FILE" ]; then
    print_err "No tomo-install.json found. Run: bash scripts/install-tomo.sh"
    exit 1
fi

INSTANCE_NAME=$(jq -r '.instanceName' "$CONFIG_FILE")
INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG_FILE")
HOME_DIR=$(jq -r '.homePath' "$CONFIG_FILE")
TOMO_VERSION=$(jq -r '.tomoVersion' "$CONFIG_FILE")

if [ ! -d "$INSTANCE_PATH" ]; then
    print_err "Instance directory not found: $INSTANCE_PATH"
    print_err "Run: bash scripts/install-tomo.sh"
    exit 1
fi

# ── Version check ─────────────────────────────────────────

SOURCE_VERSION=$(grep -m1 '^# version:' "$SCRIPT_DIR/tomo/.claude/rules/project-context.md" 2>/dev/null | sed 's/^# version: *//' || echo "unknown")
if [ "$TOMO_VERSION" != "$SOURCE_VERSION" ] && [ "$SOURCE_VERSION" != "unknown" ]; then
    print_warn "Instance version ($TOMO_VERSION) differs from source ($SOURCE_VERSION)"
    echo "  Run: bash scripts/update-tomo.sh"
    read -rp "  Continue anyway? [y/N] " CONTINUE
    case "$CONTINUE" in
        [yY]*) ;;
        *) exit 0 ;;
    esac
fi

# ── Dev-notify-bridge ─────────────────────────────────────

print_step "Checking dev-notify-bridge"

DEV_NOTIFY_PORT="${DEV_NOTIFY_PORT:-9999}"

# Detect platform for notification backend
case "$(uname -s)" in
    Darwin)
        if ! command -v terminal-notifier > /dev/null 2>&1; then
            print_warn "terminal-notifier not installed — notifications may not appear"
            echo "  Install with: brew install terminal-notifier"
        fi
        ;;
    Linux)
        if ! command -v notify-send > /dev/null 2>&1; then
            print_warn "notify-send not found — notifications may not appear"
            echo "  Install with: sudo apt install libnotify-bin (or equivalent)"
        fi
        ;;
esac

# Start dev-notify-bridge if not already running
if ! curl -s "http://localhost:${DEV_NOTIFY_PORT}/health" > /dev/null 2>&1; then
    if command -v npx > /dev/null 2>&1; then
        npx dev-notify-bridge --port "$DEV_NOTIFY_PORT" &
        sleep 1
        print_ok "dev-notify-bridge started on port $DEV_NOTIFY_PORT"
    else
        print_warn "npx not found — dev-notify-bridge not started"
    fi
else
    print_ok "dev-notify-bridge already running on port $DEV_NOTIFY_PORT"
fi

# ── Docker image ──────────────────────────────────────────

IMAGE_NAME="miyo-tomo:latest"

if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    print_step "Building Docker image (first time)"
    docker build -t "$IMAGE_NAME" "$SCRIPT_DIR/docker/"
    print_ok "Image built: $IMAGE_NAME"
else
    print_ok "Image exists: $IMAGE_NAME"
fi

# ── Launch container ──────────────────────────────────────

CONTAINER_NAME="tomo-${INSTANCE_NAME}"

print_step "Starting Tomo container: $CONTAINER_NAME"
echo "  Instance: $INSTANCE_PATH"
echo "  Home:     $HOME_DIR"

docker run -it --rm \
    --name "$CONTAINER_NAME" \
    --hostname tomo \
    -w "$INSTANCE_PATH" \
    -e "TERM=xterm-256color" \
    -e "TOMO_INSTANCE_DIR=$INSTANCE_PATH" \
    -e "DEV_NOTIFY_PORT=$DEV_NOTIFY_PORT" \
    -v "$INSTANCE_PATH:$INSTANCE_PATH" \
    -v "$HOME_DIR:/home/coder" \
    "$IMAGE_NAME" \
    claude
