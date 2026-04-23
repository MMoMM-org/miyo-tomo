#!/bin/bash
# update-tomo.sh — Update managed files in an existing Tomo instance.
# Overwrites managed files, skips user files, attempts to merge settings.json.
# Also re-runs the voice transcription wizard (XDD 009) to allow model
# changes without a full reinstall.
# version: 0.3.0 (voice prior-state: instance mirror wins on desync + warns)
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

# Voice transcription wizard (XDD 009). Requires print_* helpers above.
# shellcheck source=lib/configure-voice.sh
. "$SCRIPT_DIR/lib/configure-voice.sh"

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

print_step "Updating .claude/scripts (file-suggestion etc.)"
mkdir -p "$INSTANCE_PATH/.claude/scripts/lib"
if [ -d "$TOMO_SOURCE/dot_claude/scripts" ]; then
    for f in "$TOMO_SOURCE/dot_claude/scripts/"*.sh; do
        [ -f "$f" ] || continue
        name=$(basename "$f")
        update_managed "$f" "$INSTANCE_PATH/.claude/scripts/$name" ".claude/scripts/$name"
        chmod +x "$INSTANCE_PATH/.claude/scripts/$name"
    done
    for f in "$TOMO_SOURCE/dot_claude/scripts/lib/"*.sh; do
        [ -f "$f" ] || continue
        name=$(basename "$f")
        update_managed "$f" "$INSTANCE_PATH/.claude/scripts/lib/$name" ".claude/scripts/lib/$name"
    done
fi
mkdir -p "$INSTANCE_PATH/cache"

print_step "Updating rules (managed only)"
# mkdir -p was missing pre-2026-04-23; restore-from-old-backup hit
# `cp: No such file or directory` because the instance predates the
# rules dir. Every other update_managed block has a matching mkdir —
# this one just got skipped.
mkdir -p "$INSTANCE_PATH/.claude/rules"
update_managed \
    "$TOMO_SOURCE/dot_claude/rules/project-context.md" \
    "$INSTANCE_PATH/.claude/rules/project-context.md" \
    "rules/project-context.md"

print_step "Updating runtime scripts"
mkdir -p "$INSTANCE_PATH/scripts/lib"
# Runtime Python scripts now live under $TOMO_SOURCE/scripts/. $REPO_ROOT/scripts/
# holds only the user-invoked install/update/backup/cleanup/restore helpers.
for f in "$TOMO_SOURCE/scripts/"*.py; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    update_managed "$f" "$INSTANCE_PATH/scripts/$name" "scripts/$name"
done
update_managed \
    "$TOMO_SOURCE/scripts/tomo-statusline.sh" \
    "$INSTANCE_PATH/scripts/tomo-statusline.sh" \
    "scripts/tomo-statusline.sh"
chmod +x "$INSTANCE_PATH/scripts/tomo-statusline.sh" 2>/dev/null || true
for f in "$TOMO_SOURCE/scripts/lib/"*.py; do
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

# Python unit tests moved from scripts/ to tests/ at repo root (2026-04-21).
# Tests don't run inside the container runtime — they live at host/repo level.
RETIRED_SCRIPT_TESTS=(
    test-008-phase1.py
    test-instructions-diff.py
    test-vault-config-writer.py
    test-shared-ctx-tags.py
)
for name in "${RETIRED_SCRIPT_TESTS[@]}"; do
    dst="$INSTANCE_PATH/scripts/$name"
    if [ -f "$dst" ]; then
        rm -f "$dst"
        print_ok "retired scripts/$name (moved to repo-root tests/)"
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
python3 "$TOMO_SOURCE/scripts/template-from-schema.py" \
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

# ── Voice transcription wizard (XDD 009) ─────────────────
# Read prior state from BOTH the host config and the instance mirror.
# If they disagree, prefer the MIRROR (runtime reality) and warn —
# the runtime agent reads the mirror, so that's the "effective current
# state" from the user's perspective. Host wins in the final write, so
# picking mirror as prior means the wizard offers to keep the currently-
# active state as default rather than silently resurrecting a stale
# host-side setting.

VOICE_MIRROR="$INSTANCE_PATH/voice/config.json"

_host_enabled="$(jq -r '.voice.enabled // false' "$CONFIG_FILE" 2>/dev/null || echo "false")"
_host_model="$(jq -r '.voice.model // ""' "$CONFIG_FILE" 2>/dev/null || echo "")"
_host_lang="$(jq -r '.voice.language // ""' "$CONFIG_FILE" 2>/dev/null || echo "")"

if [ -f "$VOICE_MIRROR" ]; then
    _mirror_enabled="$(jq -r '.enabled // false' "$VOICE_MIRROR" 2>/dev/null || echo "false")"
    _mirror_model="$(jq -r '.model // ""' "$VOICE_MIRROR" 2>/dev/null || echo "")"
    _mirror_lang="$(jq -r '.language // ""' "$VOICE_MIRROR" 2>/dev/null || echo "")"
    if [ "$_host_enabled" != "$_mirror_enabled" ] \
       || [ "$_host_model" != "$_mirror_model" ] \
       || [ "$_host_lang" != "$_mirror_lang" ]; then
        print_warn "Voice config desync detected:"
        print_warn "  host:   enabled=$_host_enabled, model=$_host_model, lang=$_host_lang"
        print_warn "  mirror: enabled=$_mirror_enabled, model=$_mirror_model, lang=$_mirror_lang"
        print_warn "Using mirror as prior — wizard final answer will overwrite BOTH."
    fi
    PRIOR_VOICE_ENABLED="$_mirror_enabled"
    PRIOR_VOICE_MODEL="$_mirror_model"
    PRIOR_VOICE_LANGUAGE="$_mirror_lang"
else
    PRIOR_VOICE_ENABLED="$_host_enabled"
    PRIOR_VOICE_MODEL="$_host_model"
    PRIOR_VOICE_LANGUAGE="$_host_lang"
fi
unset _host_enabled _host_model _host_lang _mirror_enabled _mirror_model _mirror_lang

VOICE_MODELS_DIR="$INSTANCE_PATH/voice/models"

configure_voice \
    "$PRIOR_VOICE_ENABLED" \
    "$PRIOR_VOICE_MODEL" \
    "$PRIOR_VOICE_LANGUAGE" \
    "$VOICE_MODELS_DIR" \
    "false"

# Persist voice settings via the shared write_voice_config helper —
# see scripts/lib/configure-voice.sh. Matches install-tomo.sh exactly.
write_voice_config "$CONFIG_FILE"

# Mirror the updated voice block into the instance so runtime agents can
# read it. tomo-install.json is HOST-only; the container only sees
# $INSTANCE_PATH. See install-tomo.sh for the same mirror logic.
mkdir -p "$INSTANCE_PATH/voice"
jq '.voice' "$CONFIG_FILE" > "$INSTANCE_PATH/voice/config.json"
print_ok "voice/config.json (mirrored into instance)"

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
