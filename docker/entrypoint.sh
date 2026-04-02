#!/bin/bash
# Tomo container entry point.
# Sets up git config, runs on-start hook if present, then launches Claude Code.
# version: 0.1.0
set -e

# ── Git config ────────────────────────────────────────────
git config --global user.name "${GIT_USER_NAME:-Tomo}"
git config --global user.email "${GIT_USER_EMAIL:-tomo@miyo.local}"
git config --global safe.directory '*'

# ── On-start hook ─────────────────────────────────────────
# User-defined setup: cron jobs, extra tools, etc.
INSTANCE_DIR="${TOMO_INSTANCE_DIR:-}"
if [ -n "$INSTANCE_DIR" ] && [ -f "$INSTANCE_DIR/scripts/on-start.sh" ]; then
    echo "Running on-start hook..."
    bash "$INSTANCE_DIR/scripts/on-start.sh"
fi

# ── Launch ────────────────────────────────────────────────
exec "$@"
