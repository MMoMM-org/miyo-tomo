#!/usr/bin/env bash
# spike-suffix-marker.sh — XDD 010 Phase 1 T1.2
#
# Emits one path with a " (active)" suffix and one without. Restart Claude
# in the instance, type `@`, pick the suffixed entry, then observe:
#   1. Did the picker show the suffix in the UI?
#   2. Did the inserted text include the suffix?
#   3. Did Claude resolve the file content (i.e. did it read the file)?

# Adjust paths to ones that actually exist in your test vault.
cat <<'EOF'
README.md (active)
CLAUDE.md
docs/XDD/README.md
EOF
exit 0
