#!/bin/bash
# Tomo container entry point.
# Sets up git config (fallback only), runs on-start hook if present,
# spawns socat IDE Bridge proxy if a lock file is present,
# then launches Claude Code.
# version: 0.3.0
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

# ── IDE Bridge proxy ──────────────────────────────────────
# Spawn a socat localhost→host.docker.internal TCP proxy when exactly one
# lock file is present in ~/.claude/ide/.  Port is derived from the filename
# (Business Rule 5); JSON content is not read.  The proxy runs unsupervised in
# the background (ADR-2); a dead proxy is recovered by restarting the container.
IDE_DIR="$HOME/.claude/ide"
if [ -d "$IDE_DIR" ]; then
    # Bash 3.2-safe glob: expand, then check whether the glob stayed literal
    # (no match) by testing if the expanded value ends with "/*.lock" literally.
    set +e
    _lock_list=$(ls "$IDE_DIR"/*.lock 2>/dev/null)
    _lock_count=0
    if [ -n "$_lock_list" ]; then
        _lock_count=$(echo "$_lock_list" | wc -l | tr -d ' ')
    fi
    set -e

    if [ "$_lock_count" -gt 1 ]; then
        echo "IDE Bridge: multiple .lock files found in $IDE_DIR — cannot determine port; not starting proxy" >&2
        exit 1
    elif [ "$_lock_count" -eq 1 ]; then
        _lock_file="$_lock_list"
        _port=$(basename "$_lock_file" .lock)
        socat TCP-LISTEN:"$_port",fork,reuseaddr,bind=127.0.0.1 TCP:host.docker.internal:"$_port" &
    fi
    unset _lock_list _lock_count _lock_file _port
fi

# ── Launch ────────────────────────────────────────────────
exec "$@"
