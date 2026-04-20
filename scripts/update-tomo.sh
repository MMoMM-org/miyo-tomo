#!/bin/bash
# update-tomo.sh — Update managed files in an existing Tomo instance.
# Overwrites managed files, skips user files, attempts to merge settings.json.
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

# Extract version comment from a file (# version: X.Y.Z)
get_version() {
    grep -m1 '^# version:' "$1" 2>/dev/null | sed 's/^# version: *//' || echo "unknown"
}

# ── Load config ───────────────────────────────────────────

if [ ! -f "$CONFIG_FILE" ]; then
    print_err "No tomo-install.json found. Run install-tomo.sh first."
    exit 1
fi

INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG_FILE")

if [ ! -d "$INSTANCE_PATH" ]; then
    print_err "Instance directory not found: $INSTANCE_PATH"
    exit 1
fi

print_step "Updating instance at $INSTANCE_PATH"

# ── Update managed files ─────────────────────────────────

UPDATED=0
SKIPPED=0
TODO_LIST=""

# Function to update a managed file with version check
update_managed() {
    local src="$1"
    local dst="$2"
    local label="$3"

    local src_ver
    src_ver=$(get_version "$src")
    local dst_ver
    dst_ver=$(get_version "$dst")

    if [ "$src_ver" = "$dst_ver" ]; then
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    cp "$src" "$dst"
    print_ok "$label ($dst_ver → $src_ver)"
    UPDATED=$((UPDATED + 1))
}

print_step "Updating agents"
mkdir -p "$INSTANCE_PATH/.claude/agents"
for f in "$TOMO_SOURCE/dot_claude/agents/"*.md; do
    name=$(basename "$f")
    update_managed "$f" "$INSTANCE_PATH/.claude/agents/$name" "agents/$name"
done

print_step "Updating skills"
mkdir -p "$INSTANCE_PATH/.claude/skills"
# Flat .md files (internal reference docs)
for f in "$TOMO_SOURCE/dot_claude/skills/"*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    update_managed "$f" "$INSTANCE_PATH/.claude/skills/$name" "skills/$name"
done
# Directory-based skills (<name>/SKILL.md — Claude Code native skill format)
for d in "$TOMO_SOURCE/dot_claude/skills/"*/; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    src="$d/SKILL.md"
    [ -f "$src" ] || continue
    mkdir -p "$INSTANCE_PATH/.claude/skills/$name"
    update_managed "$src" "$INSTANCE_PATH/.claude/skills/$name/SKILL.md" "skills/$name/SKILL.md"
    # Copy any reference/templates/examples sub-dirs verbatim (no version tracking yet)
    for sub in reference templates examples; do
        if [ -d "$d/$sub" ]; then
            mkdir -p "$INSTANCE_PATH/.claude/skills/$name/$sub"
            cp -R "$d/$sub/." "$INSTANCE_PATH/.claude/skills/$name/$sub/"
        fi
    done
done

print_step "Updating commands"
mkdir -p "$INSTANCE_PATH/.claude/commands"
for f in "$TOMO_SOURCE/dot_claude/commands/"*.md; do
    name=$(basename "$f")
    update_managed "$f" "$INSTANCE_PATH/.claude/commands/$name" "commands/$name"
done

print_step "Updating hooks"
mkdir -p "$INSTANCE_PATH/.claude/hooks"
for f in "$TOMO_SOURCE/dot_claude/hooks/"*.sh; do
    name=$(basename "$f")
    update_managed "$f" "$INSTANCE_PATH/.claude/hooks/$name" "hooks/$name"
    chmod +x "$INSTANCE_PATH/.claude/hooks/$name"
done

print_step "Updating rules (managed only)"
update_managed \
    "$TOMO_SOURCE/dot_claude/rules/project-context.md" \
    "$INSTANCE_PATH/.claude/rules/project-context.md" \
    "rules/project-context.md"

print_step "Updating runtime scripts"
mkdir -p "$INSTANCE_PATH/scripts/lib"
for f in "$REPO_ROOT/scripts/"*.py; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    update_managed "$f" "$INSTANCE_PATH/scripts/$name" "scripts/$name"
done
update_managed \
    "$REPO_ROOT/scripts/tomo-statusline.sh" \
    "$INSTANCE_PATH/scripts/tomo-statusline.sh" \
    "scripts/tomo-statusline.sh"
chmod +x "$INSTANCE_PATH/scripts/tomo-statusline.sh" 2>/dev/null || true
for f in "$REPO_ROOT/scripts/lib/"*.py; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    update_managed "$f" "$INSTANCE_PATH/scripts/lib/$name" "scripts/lib/$name"
done

# ── Retire removed managed files (spec 004 migration) ───
# Agents and scripts that were deleted from source must also be removed from
# the instance, otherwise stale definitions linger.
print_step "Retiring removed files"
RETIRED_AGENTS=(suggestion-builder.md)
for name in "${RETIRED_AGENTS[@]}"; do
    dst="$INSTANCE_PATH/.claude/agents/$name"
    if [ -f "$dst" ]; then
        rm -f "$dst"
        print_ok "retired agents/$name"
    fi
done

# ── Profiles + JSON schemas (added in spec 004) ──────────
print_step "Updating profiles"
mkdir -p "$INSTANCE_PATH/profiles"
for f in "$REPO_ROOT/tomo/profiles/"*.yaml; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    cp "$f" "$INSTANCE_PATH/profiles/$name"
    print_ok "profiles/$name"
done

print_step "Updating schemas"
mkdir -p "$INSTANCE_PATH/schemas"
for f in "$TOMO_SOURCE/schemas/"*.json; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    cp "$f" "$INSTANCE_PATH/schemas/$name"
    print_ok "schemas/$name"
done

print_step "Regenerating templates from schemas"
mkdir -p "$INSTANCE_PATH/templates"
python3 "$REPO_ROOT/scripts/template-from-schema.py" \
    --schema "$INSTANCE_PATH/schemas/item-result.schema.json" \
    --output "$INSTANCE_PATH/templates/item-result.template.json" \
    >/dev/null 2>&1 && print_ok "templates/item-result.template.json"

# ── Ensure tomo-tmp scratch dirs exist ───────────────────
mkdir -p "$INSTANCE_PATH/tomo-tmp/items"

# ── Merge settings.json ──────────────────────────────────

print_step "Merging settings.json"

SRC_SETTINGS="$TOMO_SOURCE/dot_claude/settings.json"
DST_SETTINGS="$INSTANCE_PATH/.claude/settings.json"

if [ -f "$DST_SETTINGS" ]; then
    # Best-effort merge: add new hooks from source that don't exist in destination
    # If this fails, add to TODO list
    if jq -s '.[0] * .[1]' "$DST_SETTINGS" "$SRC_SETTINGS" > "$DST_SETTINGS.merged" 2>/dev/null; then
        mv "$DST_SETTINGS.merged" "$DST_SETTINGS"
        print_ok "settings.json (merged)"
    else
        rm -f "$DST_SETTINGS.merged"
        print_warn "settings.json merge failed — added to TODO list"
        TODO_LIST="${TODO_LIST}\n- [ ] Manually merge settings.json: compare $SRC_SETTINGS with $DST_SETTINGS"
    fi
else
    cp "$SRC_SETTINGS" "$DST_SETTINGS"
    print_ok "settings.json (new)"
fi

# ── Update install config version ─────────────────────────

SOURCE_VERSION=$(get_version "$TOMO_SOURCE/dot_claude/rules/project-context.md")
jq --arg v "$SOURCE_VERSION" '.tomoVersion = $v | .updatedAt = now | .updatedAt = (now | strftime("%Y-%m-%dT%H:%M:%SZ"))' \
    "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"

# ── Summary ───────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Updated: $UPDATED files"
echo "  Skipped: $SKIPPED files (already current)"

if [ -n "$TODO_LIST" ]; then
    echo ""
    echo "  Manual steps required:"
    echo -e "$TODO_LIST"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
