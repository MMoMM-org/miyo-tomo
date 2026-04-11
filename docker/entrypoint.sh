#!/bin/bash
# Tomo container entry point.
# Sets up git config (fallback only), runs on-start hook if present,
# then launches Claude Code.
# version: 0.2.0
set -e

# ── Git config (fallback only) ───────────────────────────
# If tomo-home/.gitconfig is present (written by install-tomo.sh), it already
# supplies user.name/email — don't overwrite it. Only set defaults when no
# identity is configured yet.
if ! git config --global --get user.name > /dev/null 2>&1; then
    git config --global user.name "${GIT_USER_NAME:-Tomo}"
fi
if ! git config --global --get user.email > /dev/null 2>&1; then
    git config --global user.email "${GIT_USER_EMAIL:-tomo@miyo.local}"
fi
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
