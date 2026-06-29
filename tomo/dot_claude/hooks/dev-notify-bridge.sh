#!/bin/bash
# Notification hook — forwards Claude Code events to dev-notify-bridge on host.
# dev-notify-bridge must be running on host (started by begin-tomo.sh).
# version: 0.2.0

INPUT=$(cat)
BASE_TITLE=$(echo "$INPUT" | jq -r '.title // "Tomo"')
MESSAGE=$(echo "$INPUT" | jq -r '.message // ""')

# Resolve the instance label the same way the statusline does:
# TOMO_INSTANCE_NAME (injected by begin-tomo.sh), then basename of the
# instance dir, so multi-instance users can tell which Tomo is waiting.
INSTANCE_LABEL=""
if [ -n "${TOMO_INSTANCE_NAME:-}" ]; then
  INSTANCE_LABEL="$TOMO_INSTANCE_NAME"
elif [ -n "${TOMO_INSTANCE_DIR:-}" ]; then
  INSTANCE_LABEL="$(basename "$TOMO_INSTANCE_DIR")"
fi

if [ -n "$INSTANCE_LABEL" ]; then
  TITLE="[Tomo · ${INSTANCE_LABEL}] ${BASE_TITLE}"
else
  TITLE="[Tomo] ${BASE_TITLE}"
fi

# dev-notify-bridge listens on host port (default 9999, configurable via env)
PORT="${DEV_NOTIFY_PORT:-9999}"

curl -s -X POST "http://host.docker.internal:${PORT}/notify" \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"${TITLE}\", \"message\": \"${MESSAGE}\"}" \
  2>/dev/null || true

exit 0
