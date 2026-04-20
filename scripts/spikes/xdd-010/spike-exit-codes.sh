#!/usr/bin/env bash
# spike-exit-codes.sh — XDD 010 Phase 1 T1.1
#
# Comment in / out one CASE at a time, then restart Claude in the instance
# and type `@x` to observe the picker behaviour.

# ── CASE A — exit 0, three valid paths ───────────────────────────────
# (Default — most likely good behaviour.)
cat <<'EOF'
README.md
CLAUDE.md
docs/XDD/README.md
EOF
exit 0

# ── CASE B — exit 0, empty stdout ────────────────────────────────────
# exit 0

# ── CASE C — exit 1, valid paths ─────────────────────────────────────
# cat <<'EOF'
# README.md
# CLAUDE.md
# EOF
# exit 1

# ── CASE D — exit 0, non-path text ───────────────────────────────────
# cat <<'EOF'
# this is not a real path
# neither is this
# nor this
# EOF
# exit 0

# ── CASE E — exit 0, mix of valid + non-path ─────────────────────────
# cat <<'EOF'
# README.md
# (this is a hint, not a path)
# CLAUDE.md
# EOF
# exit 0
