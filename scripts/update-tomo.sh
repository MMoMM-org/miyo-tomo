#!/bin/bash
# update-tomo.sh — Update managed files in an existing Tomo instance.
# Two-pass UX: scans + plans first (no writes), confirms with user, then executes.
# Overwrites managed files, skips user files, attempts to merge settings.json.
# Also re-runs the voice transcription wizard (XDD 009) to allow model
# changes without a full reinstall.
# version: 0.5.0
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOMO_SOURCE="$REPO_ROOT/tomo"
CONFIG_FILE="$REPO_ROOT/tomo-install.json"

# ── CLI parsing ──────────────────────────────────────────

FORCE=false
KEEP_VOICE=false
YES=false
DRY_RUN=false
FLAG_CONFIG_FILE=""

print_help() {
    cat <<'EOF'
Usage: update-tomo.sh [OPTIONS]

Updates managed files in an existing Tomo instance. Runs in two passes:
  1. Pre-flight scan — shows the plan (no writes) with status per file:
       ✓ current   — in sync, no action
       ↑ update    — content differs, will be overwritten
       + create    — destination missing, will be created
       - retire    — file removed from source, will be deleted
       ! problem   — read/scan error
  2. Confirmation — asks GO/Abort (skipped with --yes or --yolo).
  3. Execute — performs the writes and prints past-tense results:
       ✓ ok / ↑ updated / + created / - deleted / ! failed

Options:
  -f, --force        Update all files regardless of detected change
                     (treats every "current" file as "update").
      --keep-voice   Skip the voice-config wizard (keep current settings).
  -y, --yes          Skip the GO/Abort confirmation prompt.
      --yolo         Equivalent to --keep-voice --yes.
  -n, --dry-run      Show the plan and exit; never write.
      --config-file  Use an alternate tomo-install.json (test isolation).
  -h, --help         Show this help and exit.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--force)      FORCE=true ;;
        --keep-voice)    KEEP_VOICE=true ;;
        -y|--yes)        YES=true ;;
        --yolo)          KEEP_VOICE=true; YES=true ;;
        -n|--dry-run)    DRY_RUN=true ;;
        --config-file)   FLAG_CONFIG_FILE="$2"; shift ;;
        -h|--help)       print_help; exit 0 ;;
        *)
            echo "Unknown option: $1" >&2
            print_help >&2
            exit 2
            ;;
    esac
    shift
done

# ── Helpers ───────────────────────────────────────────────

print_step() { echo ""; echo "▸ $1"; }
print_info() { echo "  $1"; }
print_warn() { echo "  ⚠ $1"; }
print_err()  { echo "  ✗ $1" >&2; }
print_ok()   { echo "  ✓ $1"; }  # kept for compat with configure-voice.sh

# Plan-phase markers (future-tense — what WILL happen)
mark_planned() {
    local status="$1"; local label="$2"; local detail="$3"
    case "$status" in
        current) echo "  ✓ current  $label${detail:+  $detail}" ;;
        update)  echo "  ↑ update   $label${detail:+  $detail}" ;;
        create)  echo "  + create   $label${detail:+  $detail}" ;;
        retire)  echo "  - retire   $label${detail:+  $detail}" ;;
        problem) echo "  ! problem  $label${detail:+  $detail}" >&2 ;;
        *)       echo "  ? $status  $label${detail:+  $detail}" ;;
    esac
}

# Execute-phase markers (past-tense — what HAPPENED)
mark_did() {
    local status="$1"; local label="$2"; local detail="$3"
    case "$status" in
        ok)      echo "  ✓ ok       $label${detail:+  $detail}" ;;
        updated) echo "  ↑ updated  $label${detail:+  $detail}" ;;
        created) echo "  + created  $label${detail:+  $detail}" ;;
        deleted) echo "  - deleted  $label${detail:+  $detail}" ;;
        failed)  echo "  ! failed   $label${detail:+  $detail}" >&2 ;;
        *)       echo "  ? $status  $label${detail:+  $detail}" ;;
    esac
}

# Extract version comment from a file (# version: X.Y.Z).
# Returns the full text after the prefix verbatim — convention says number
# only, no parenthetical. If a file violates the convention, the noise
# leaks into update-tomo.sh's display output on purpose, so the violation
# stays visible and gets fixed at the source.
get_version() {
    grep -m1 '^# version:' "$1" 2>/dev/null | sed 's/^# version: *//' || echo "unknown"
}

# Voice transcription wizard (XDD 009). Requires print_* helpers above.
# shellcheck source=lib/configure-voice.sh
. "$SCRIPT_DIR/lib/configure-voice.sh"

# Hashi IDE Bridge wizard (XDD 019). Requires print_* helpers above.
# shellcheck source=lib/configure-ide-bridge.sh
. "$SCRIPT_DIR/lib/configure-ide-bridge.sh"

# ── Load config ───────────────────────────────────────────

# Resolve the effective config-file path. Tests pass --config-file to isolate
# from the real instance; otherwise the repo-root default is used.
if [ -n "$FLAG_CONFIG_FILE" ]; then
    CONFIG_FILE="$FLAG_CONFIG_FILE"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    print_err "No tomo-install.json found. Run install-tomo.sh first."
    exit 1
fi

INSTANCE_PATH=$(jq -r '.instancePath' "$CONFIG_FILE")
HOME_DIR=$(jq -r '.homePath // empty' "$CONFIG_FILE")
LAUNCHER_PATH=$(jq -r '.launcherPath // empty' "$CONFIG_FILE")
INSTANCE_NAME=$(jq -r '.instanceName // empty' "$CONFIG_FILE")
INSTANCE_LOCATION=$(jq -r '.instanceLocation // empty' "$CONFIG_FILE")

# launcherPath fallback for older configs that predate the field.
if [ -z "$LAUNCHER_PATH" ]; then
    LAUNCHER_PATH="$INSTANCE_LOCATION/begin-tomo.sh"
fi

if [ ! -d "$INSTANCE_PATH" ]; then
    print_err "Instance directory not found: $INSTANCE_PATH"
    exit 1
fi

print_step "Updating instance at $INSTANCE_PATH"
[ "$DRY_RUN" = "true" ] && print_info "(dry-run: no writes will be performed)"
[ "$FORCE" = "true" ]   && print_info "(force: every file marked update regardless of content)"

# ── Plan tables (parallel arrays — bash 3.2 compatible) ──

PLAN_KIND=()    # versioned | bytewise | retire | settings | template | launcher
PLAN_SRC=()
PLAN_DST=()
PLAN_LABEL=()
PLAN_STATUS=()  # current | update | create | retire | problem
PLAN_DETAIL=()
PLAN_SECTION=()

add_plan() {
    PLAN_KIND+=("$1")
    PLAN_SRC+=("$2")
    PLAN_DST+=("$3")
    PLAN_LABEL+=("$4")
    PLAN_STATUS+=("$5")
    PLAN_DETAIL+=("$6")
    PLAN_SECTION+=("$7")
}

# Decide status for a versioned file (uses `# version:` comment).
# Echoes "<status>|<detail>".
scan_versioned() {
    local src="$1"; local dst="$2"
    local src_ver dst_ver
    src_ver=$(get_version "$src")
    if [ ! -f "$dst" ]; then
        echo "create|new (→ $src_ver)"
        return
    fi
    dst_ver=$(get_version "$dst")
    if [ "$FORCE" = "true" ]; then
        echo "update|forced (was $dst_ver, src $src_ver)"
    elif [ "$src_ver" = "$dst_ver" ]; then
        echo "current|$src_ver"
    else
        echo "update|$dst_ver → $src_ver"
    fi
}

# Decide status for a bytewise-compared file (schemas, profiles, templates).
scan_bytewise() {
    local src="$1"; local dst="$2"
    if [ ! -f "$dst" ]; then
        echo "create|new"
        return
    fi
    if [ "$FORCE" = "true" ]; then
        echo "update|forced"
    elif cmp -s "$src" "$dst"; then
        echo "current|"
    else
        echo "update|content differs"
    fi
}

add_versioned() {
    local src="$1"; local dst="$2"; local label="$3"; local section="$4"
    local result status detail
    result=$(scan_versioned "$src" "$dst")
    status="${result%%|*}"
    detail="${result#*|}"
    add_plan "versioned" "$src" "$dst" "$label" "$status" "$detail" "$section"
}

add_bytewise() {
    local src="$1"; local dst="$2"; local label="$3"; local section="$4"
    local result status detail
    result=$(scan_bytewise "$src" "$dst")
    status="${result%%|*}"
    detail="${result#*|}"
    add_plan "bytewise" "$src" "$dst" "$label" "$status" "$detail" "$section"
}

# ── Pre-flight scan ──────────────────────────────────────

print_step "Pre-flight scan (no writes yet)"

# Agents
for f in "$TOMO_SOURCE/dot_claude/agents/"*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_versioned "$f" "$INSTANCE_PATH/.claude/agents/$name" "agents/$name" "agents"
done

# Skills (flat .md and directory-based)
for f in "$TOMO_SOURCE/dot_claude/skills/"*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_versioned "$f" "$INSTANCE_PATH/.claude/skills/$name" "skills/$name" "skills"
done
for d in "$TOMO_SOURCE/dot_claude/skills/"*/; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    src="$d/SKILL.md"
    [ -f "$src" ] || continue
    add_versioned "$src" "$INSTANCE_PATH/.claude/skills/$name/SKILL.md" "skills/$name/SKILL.md" "skills"
done

# Commands
for f in "$TOMO_SOURCE/dot_claude/commands/"*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_versioned "$f" "$INSTANCE_PATH/.claude/commands/$name" "commands/$name" "commands"
done

# Hooks
for f in "$TOMO_SOURCE/dot_claude/hooks/"*.sh; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_versioned "$f" "$INSTANCE_PATH/.claude/hooks/$name" "hooks/$name" "hooks"
done

# .claude/scripts (file-suggestion etc.)
if [ -d "$TOMO_SOURCE/dot_claude/scripts" ]; then
    for f in "$TOMO_SOURCE/dot_claude/scripts/"*.sh; do
        [ -f "$f" ] || continue
        name=$(basename "$f")
        add_versioned "$f" "$INSTANCE_PATH/.claude/scripts/$name" ".claude/scripts/$name" "claude-scripts"
    done
    for f in "$TOMO_SOURCE/dot_claude/scripts/lib/"*.sh; do
        [ -f "$f" ] || continue
        name=$(basename "$f")
        add_versioned "$f" "$INSTANCE_PATH/.claude/scripts/lib/$name" ".claude/scripts/lib/$name" "claude-scripts"
    done
fi

# Rules
add_versioned \
    "$TOMO_SOURCE/dot_claude/rules/project-context.md" \
    "$INSTANCE_PATH/.claude/rules/project-context.md" \
    "rules/project-context.md" \
    "rules"

# Runtime scripts (Python + shell)
for f in "$TOMO_SOURCE/scripts/"*.py; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_versioned "$f" "$INSTANCE_PATH/scripts/$name" "scripts/$name" "runtime-scripts"
done
add_versioned \
    "$TOMO_SOURCE/scripts/tomo-statusline.sh" \
    "$INSTANCE_PATH/scripts/tomo-statusline.sh" \
    "scripts/tomo-statusline.sh" \
    "runtime-scripts"
for f in "$TOMO_SOURCE/scripts/lib/"*.py; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_versioned "$f" "$INSTANCE_PATH/scripts/lib/$name" "scripts/lib/$name" "runtime-scripts"
done

# Retired files (delete from instance if present)
RETIRED_AGENTS=(suggestion-builder.md vault-executor.md inbox-orchestrator.md instruction-builder.md)
for name in "${RETIRED_AGENTS[@]}"; do
    dst="$INSTANCE_PATH/.claude/agents/$name"
    if [ -f "$dst" ]; then
        add_plan "retire" "" "$dst" "agents/$name" "retire" "removed from source" "retired"
    fi
done
RETIRED_COMMANDS=(execute.md)
for name in "${RETIRED_COMMANDS[@]}"; do
    dst="$INSTANCE_PATH/.claude/commands/$name"
    if [ -f "$dst" ]; then
        add_plan "retire" "" "$dst" "commands/$name" "retire" "removed from source" "retired"
    fi
done
RETIRED_SKILLS_DIRS=(pkm-workflows)
for skill_dir in "${RETIRED_SKILLS_DIRS[@]}"; do
    dst="$INSTANCE_PATH/.claude/skills/$skill_dir"
    if [ -d "$dst" ]; then
        add_plan "retire" "" "$dst" "skills/$skill_dir" "retire" "removed from source" "retired"
    fi
done
RETIRED_SCRIPT_TESTS=(
    test-008-phase1.py
    test-instructions-diff.py
    test-vault-config-writer.py
    test-shared-ctx-tags.py
)
RETIRED_SCRIPTS=(
    tag-captured.py
    state-init.py
    inbox-discovery.py
)
for name in "${RETIRED_SCRIPT_TESTS[@]}" "${RETIRED_SCRIPTS[@]}"; do
    dst="$INSTANCE_PATH/scripts/$name"
    if [ -f "$dst" ]; then
        add_plan "retire" "" "$dst" "scripts/$name" "retire" "moved or renamed" "retired"
    fi
done

# Profiles (bytewise)
for f in "$REPO_ROOT/tomo/profiles/"*.yaml; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_bytewise "$f" "$INSTANCE_PATH/profiles/$name" "profiles/$name" "profiles"
done

# Schemas (bytewise)
for f in "$TOMO_SOURCE/schemas/"*.json; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    add_bytewise "$f" "$INSTANCE_PATH/schemas/$name" "schemas/$name" "schemas"
done

# Templates — regenerated from schemas; check if regen would change anything.
# We compute the expected content into a tmp file and cmp.
TEMPLATE_TMP="$(mktemp)"
trap 'rm -f "$TEMPLATE_TMP" "${SETTINGS_TMP:-}"' EXIT
TEMPLATE_DST="$INSTANCE_PATH/templates/item-result.template.json"
if python3 "$TOMO_SOURCE/scripts/template-from-schema.py" \
        --schema "$TOMO_SOURCE/schemas/item-result.schema.json" \
        --output "$TEMPLATE_TMP" >/dev/null 2>&1; then
    if [ ! -f "$TEMPLATE_DST" ]; then
        add_plan "template" "$TEMPLATE_TMP" "$TEMPLATE_DST" "templates/item-result.template.json" "create" "regenerated" "templates"
    elif [ "$FORCE" = "true" ]; then
        add_plan "template" "$TEMPLATE_TMP" "$TEMPLATE_DST" "templates/item-result.template.json" "update" "forced" "templates"
    elif cmp -s "$TEMPLATE_TMP" "$TEMPLATE_DST"; then
        add_plan "template" "$TEMPLATE_TMP" "$TEMPLATE_DST" "templates/item-result.template.json" "current" "" "templates"
    else
        add_plan "template" "$TEMPLATE_TMP" "$TEMPLATE_DST" "templates/item-result.template.json" "update" "schema-driven regen" "templates"
    fi
else
    add_plan "template" "" "$TEMPLATE_DST" "templates/item-result.template.json" "problem" "template-from-schema.py failed" "templates"
fi

# Settings.json: scan only — actual merge happens at execute time (jq is the merge engine).
SRC_SETTINGS="$TOMO_SOURCE/dot_claude/settings.json"
DST_SETTINGS="$INSTANCE_PATH/.claude/settings.json"
if [ ! -f "$DST_SETTINGS" ]; then
    add_plan "settings" "$SRC_SETTINGS" "$DST_SETTINGS" "settings.json" "create" "new" "settings"
else
    # Try the same merge logic; compare result to current to decide status.
    SETTINGS_TMP="$(mktemp)"
    if jq -s '.[0] * .[1]' "$DST_SETTINGS" "$SRC_SETTINGS" > "$SETTINGS_TMP" 2>/dev/null; then
        if [ "$FORCE" = "true" ]; then
            add_plan "settings" "$SETTINGS_TMP" "$DST_SETTINGS" "settings.json" "update" "forced" "settings"
        elif cmp -s "$SETTINGS_TMP" "$DST_SETTINGS"; then
            add_plan "settings" "$SETTINGS_TMP" "$DST_SETTINGS" "settings.json" "current" "" "settings"
        else
            add_plan "settings" "$SETTINGS_TMP" "$DST_SETTINGS" "settings.json" "update" "merge changed" "settings"
        fi
    else
        rm -f "$SETTINGS_TMP"
        add_plan "settings" "$SRC_SETTINGS" "$DST_SETTINGS" "settings.json" "problem" "jq merge failed — manual fix" "settings"
    fi
fi

# Container-home entrypoint.sh (versioned). Source repo → bind-mounted home.
# Delivered here so an existing user enabling the IDE Bridge via update-tomo.sh
# gets the socat-proxy entrypoint, not the stale pre-bridge one (T4.1 gap).
ENTRYPOINT_SRC="$REPO_ROOT/docker/entrypoint.sh"
if [ -n "$HOME_DIR" ] && [ -f "$ENTRYPOINT_SRC" ]; then
    add_versioned "$ENTRYPOINT_SRC" "$HOME_DIR/entrypoint.sh" "entrypoint.sh" "container-home"
fi

# begin-tomo.sh launcher (rendered from template, version-gated). The installed
# launcher retains the template's `# version:` comment, so we version-compare
# the template against the installed launcher (cannot byte-compare — rendered).
# Delivered here so an existing user gets the socat drift-rebuild / banner /
# probe launcher, not the stale pre-bridge one (T4.1 gap).
LAUNCHER_TEMPLATE="$REPO_ROOT/scripts/lib/begin-tomo.sh.template"
if [ ! -f "$LAUNCHER_TEMPLATE" ]; then
    add_plan "launcher" "$LAUNCHER_TEMPLATE" "$LAUNCHER_PATH" "begin-tomo.sh" "problem" "template missing: $LAUNCHER_TEMPLATE" "launcher"
elif [ -z "$LAUNCHER_PATH" ]; then
    add_plan "launcher" "$LAUNCHER_TEMPLATE" "$LAUNCHER_PATH" "begin-tomo.sh" "problem" "no launcherPath in config" "launcher"
else
    launcher_result=$(scan_versioned "$LAUNCHER_TEMPLATE" "$LAUNCHER_PATH")
    add_plan "launcher" "$LAUNCHER_TEMPLATE" "$LAUNCHER_PATH" "begin-tomo.sh" \
        "${launcher_result%%|*}" "${launcher_result#*|}" "launcher"
fi

# ── Print plan grouped by section ─────────────────────────

print_section_plan() {
    local section="$1"; local header="$2"
    local i printed=0
    for i in "${!PLAN_KIND[@]}"; do
        if [ "${PLAN_SECTION[$i]}" = "$section" ]; then
            if [ "$printed" = "0" ]; then
                print_step "$header"
                printed=1
            fi
            mark_planned "${PLAN_STATUS[$i]}" "${PLAN_LABEL[$i]}" "${PLAN_DETAIL[$i]}"
        fi
    done
}

print_section_plan "agents"          "Agents"
print_section_plan "skills"          "Skills"
print_section_plan "commands"        "Commands"
print_section_plan "hooks"           "Hooks"
print_section_plan "claude-scripts"  ".claude/scripts"
print_section_plan "rules"           "Rules"
print_section_plan "runtime-scripts" "Runtime scripts"
print_section_plan "retired"         "Retiring removed files"
print_section_plan "profiles"        "Profiles"
print_section_plan "schemas"         "Schemas"
print_section_plan "templates"       "Templates (regenerated from schemas)"
print_section_plan "settings"        "Settings.json"
print_section_plan "container-home"  "Container home (entrypoint)"
print_section_plan "launcher"        "Launcher (begin-tomo.sh)"

# Plan summary tally
plan_count_status() {
    local target="$1"; local n=0 s
    for s in "${PLAN_STATUS[@]}"; do
        [ "$s" = "$target" ] && n=$((n + 1))
    done
    echo "$n"
}

print_step "Plan summary"
print_info "✓ current : $(plan_count_status current)"
print_info "↑ update  : $(plan_count_status update)"
print_info "+ create  : $(plan_count_status create)"
print_info "- retire  : $(plan_count_status retire)"
PROBLEMS=$(plan_count_status problem)
[ "$PROBLEMS" -gt 0 ] && print_warn "! problem : $PROBLEMS"

# ── Voice wizard (interactive but defers writes until execute phase) ──

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

if [ "$KEEP_VOICE" = "true" ]; then
    print_step "Voice memo transcription (kept current — --keep-voice)"
    VOICE_ENABLED="$PRIOR_VOICE_ENABLED"
    VOICE_MODEL="$PRIOR_VOICE_MODEL"
    VOICE_LANGUAGE="$PRIOR_VOICE_LANGUAGE"
    print_info "enabled=$VOICE_ENABLED model=$VOICE_MODEL lang=${VOICE_LANGUAGE:-auto}"
else
    configure_voice \
        "$PRIOR_VOICE_ENABLED" \
        "$PRIOR_VOICE_MODEL" \
        "$PRIOR_VOICE_LANGUAGE" \
        "$VOICE_MODELS_DIR" \
        "false"
fi

# Decide whether voice config or mirror need writes (status for the plan summary).
voice_host_changed=false
voice_mirror_changed=false
if [ "$VOICE_ENABLED" != "$PRIOR_VOICE_ENABLED" ] \
   || [ "$VOICE_MODEL" != "$PRIOR_VOICE_MODEL" ] \
   || [ "$VOICE_LANGUAGE" != "$PRIOR_VOICE_LANGUAGE" ]; then
    voice_host_changed=true
    voice_mirror_changed=true
fi
# Mirror may also be stale even if wizard returned unchanged values
if [ ! -f "$VOICE_MIRROR" ]; then
    voice_mirror_changed=true
fi
if [ "$FORCE" = "true" ]; then
    voice_host_changed=true
    voice_mirror_changed=true
fi

# ── IDE Bridge wizard (XDD 019) ──────────────────────────
# Read prior values from CONFIG_FILE; keep unchanged in automated runs.

PRIOR_IDE_ENABLED=$(jq -r '.ide_bridge.enabled // false' "$CONFIG_FILE" 2>/dev/null || echo "false")
PRIOR_IDE_TOKEN=$(jq -r '.ide_bridge.auth_token // ""' "$CONFIG_FILE" 2>/dev/null || echo "")
PRIOR_IDE_PORT=$(jq -r '.ide_bridge.port // 23027' "$CONFIG_FILE" 2>/dev/null || echo "23027")

if [ "$YES" = "true" ]; then
    print_step "Hashi IDE Bridge (kept current — automated run)"
    IDE_BRIDGE_ENABLED="$PRIOR_IDE_ENABLED"
    IDE_BRIDGE_TOKEN="$PRIOR_IDE_TOKEN"
    IDE_BRIDGE_PORT="$PRIOR_IDE_PORT"
    print_info "enabled=$IDE_BRIDGE_ENABLED port=$IDE_BRIDGE_PORT"
else
    configure_ide_bridge \
        "$PRIOR_IDE_ENABLED" \
        "$PRIOR_IDE_TOKEN" \
        "$PRIOR_IDE_PORT" \
        "" \
        "false"
fi

# Decide whether IDE Bridge config needs a write.
ide_bridge_changed=false
if [ "$IDE_BRIDGE_ENABLED" != "$PRIOR_IDE_ENABLED" ] \
   || [ "$IDE_BRIDGE_TOKEN" != "$PRIOR_IDE_TOKEN" ] \
   || [ "$IDE_BRIDGE_PORT" != "$PRIOR_IDE_PORT" ]; then
    ide_bridge_changed=true
fi
if [ "$FORCE" = "true" ]; then
    ide_bridge_changed=true
fi

# ── Confirmation ─────────────────────────────────────────

if [ "$DRY_RUN" = "true" ]; then
    print_step "Dry-run — no writes performed"
    print_info "Run again without --dry-run to apply the plan above."
    exit 0
fi

if [ "$YES" != "true" ]; then
    print_step "Confirm execution"
    NEEDS_WRITE=$(( $(plan_count_status update) + $(plan_count_status create) + $(plan_count_status retire) ))
    if [ "$voice_host_changed" = "true" ];   then NEEDS_WRITE=$((NEEDS_WRITE + 1)); fi
    if [ "$voice_mirror_changed" = "true" ]; then NEEDS_WRITE=$((NEEDS_WRITE + 1)); fi
    if [ "$ide_bridge_changed" = "true" ];   then NEEDS_WRITE=$((NEEDS_WRITE + 1)); fi
    if [ "$NEEDS_WRITE" -eq 0 ]; then
        print_info "Nothing to do (every file is current). Proceeding to refresh install-config only."
    else
        print_info "About to write $NEEDS_WRITE change(s)."
    fi
    printf "  Continue? [Y/n] "
    read -r REPLY
    case "$REPLY" in
        ""|y|Y|yes|Yes|YES) ;;
        *)
            print_warn "Aborted by user — no changes made."
            exit 1
            ;;
    esac
fi

# ── Execute phase ────────────────────────────────────────

DID_UPDATED=0
DID_CREATED=0
DID_DELETED=0
DID_FAILED=0
DID_CURRENT=0

ensure_dir() { mkdir -p "$1" 2>/dev/null || true; }

execute_one() {
    local i="$1"
    local kind="${PLAN_KIND[$i]}"
    local src="${PLAN_SRC[$i]}"
    local dst="${PLAN_DST[$i]}"
    local label="${PLAN_LABEL[$i]}"
    local status="${PLAN_STATUS[$i]}"
    local detail="${PLAN_DETAIL[$i]}"

    case "$status" in
        current)
            DID_CURRENT=$((DID_CURRENT + 1))
            # don't print per-file for "current" in execute phase — keeps output tight
            return
            ;;
        problem)
            mark_did "failed" "$label" "$detail"
            DID_FAILED=$((DID_FAILED + 1))
            return
            ;;
        retire)
            if [ -d "$dst" ]; then
                rm_cmd="rm -rf"
            else
                rm_cmd="rm -f"
            fi
            if $rm_cmd "$dst" 2>/dev/null; then
                mark_did "deleted" "$label" ""
                DID_DELETED=$((DID_DELETED + 1))
            else
                mark_did "failed" "$label" "rm failed"
                DID_FAILED=$((DID_FAILED + 1))
            fi
            return
            ;;
    esac

    # status is "update" or "create" — perform a write
    ensure_dir "$(dirname "$dst")"

    case "$kind" in
        versioned|bytewise|template|settings)
            if cp "$src" "$dst" 2>/dev/null; then
                # Hooks, statusline and the container entrypoint need exec bit
                case "$label" in
                    hooks/*|scripts/tomo-statusline.sh|.claude/scripts/*|entrypoint.sh) chmod +x "$dst" 2>/dev/null || true ;;
                esac
                if [ "$status" = "create" ]; then
                    mark_did "created" "$label" "$detail"
                    DID_CREATED=$((DID_CREATED + 1))
                else
                    mark_did "updated" "$label" "$detail"
                    DID_UPDATED=$((DID_UPDATED + 1))
                fi
            else
                mark_did "failed" "$label" "cp failed"
                DID_FAILED=$((DID_FAILED + 1))
            fi
            ;;
        launcher)
            # Render the template into the launcher path with the same five
            # substitutions install-tomo.sh uses. DEV_NOTIFY_PORT is the
            # constant 9999 (matches install).
            if sed -e "s|{{INSTANCE_PATH}}|${INSTANCE_PATH}|g" \
                   -e "s|{{INSTANCE_NAME}}|${INSTANCE_NAME}|g" \
                   -e "s|{{HOME_DIR}}|${HOME_DIR}|g" \
                   -e "s|{{TOMO_REPO_ROOT}}|${REPO_ROOT}|g" \
                   -e "s|{{DEV_NOTIFY_PORT}}|9999|g" \
                   "$src" > "$dst" 2>/dev/null; then
                chmod +x "$dst" 2>/dev/null || true
                if [ "$status" = "create" ]; then
                    mark_did "created" "$label" "$detail"
                    DID_CREATED=$((DID_CREATED + 1))
                else
                    mark_did "updated" "$label" "$detail"
                    DID_UPDATED=$((DID_UPDATED + 1))
                fi
            else
                mark_did "failed" "$label" "render failed"
                DID_FAILED=$((DID_FAILED + 1))
            fi
            ;;
        *)
            mark_did "failed" "$label" "unknown kind: $kind"
            DID_FAILED=$((DID_FAILED + 1))
            ;;
    esac
}

# Walk the plan in section order so the output mirrors the plan layout.
execute_section() {
    local section="$1"; local header="$2"; local i printed=0
    for i in "${!PLAN_KIND[@]}"; do
        if [ "${PLAN_SECTION[$i]}" = "$section" ]; then
            local status="${PLAN_STATUS[$i]}"
            # Skip "current" entries entirely in execute phase
            if [ "$status" = "current" ]; then
                DID_CURRENT=$((DID_CURRENT + 1))
                continue
            fi
            if [ "$printed" = "0" ]; then
                print_step "$header"
                printed=1
            fi
            execute_one "$i"
        fi
    done
}

execute_section "agents"          "Agents"
execute_section "skills"          "Skills"
execute_section "commands"        "Commands"
execute_section "hooks"           "Hooks"
execute_section "claude-scripts"  ".claude/scripts"
execute_section "rules"           "Rules"
execute_section "runtime-scripts" "Runtime scripts"
execute_section "retired"         "Retiring removed files"
execute_section "profiles"        "Profiles"
execute_section "schemas"         "Schemas"
execute_section "templates"       "Templates"
execute_section "settings"        "Settings.json"
execute_section "container-home"  "Container home (entrypoint)"
execute_section "launcher"        "Launcher (begin-tomo.sh)"

# tomo-tmp scratch dirs (idempotent, no plan entry)
ensure_dir "$INSTANCE_PATH/tomo-tmp/items"
ensure_dir "$INSTANCE_PATH/cache"

# ── Persist voice settings ───────────────────────────────

if [ "$voice_host_changed" = "true" ] || [ "$voice_mirror_changed" = "true" ]; then
    print_step "Voice configuration"
    if [ "$voice_host_changed" = "true" ]; then
        if write_voice_config "$CONFIG_FILE" 2>/dev/null; then
            mark_did "updated" "tomo-install.json (.voice)" ""
            DID_UPDATED=$((DID_UPDATED + 1))
        else
            mark_did "failed" "tomo-install.json (.voice)" "write_voice_config failed"
            DID_FAILED=$((DID_FAILED + 1))
        fi
    fi
    if [ "$voice_mirror_changed" = "true" ]; then
        ensure_dir "$INSTANCE_PATH/voice"
        if jq '.voice' "$CONFIG_FILE" > "$VOICE_MIRROR" 2>/dev/null; then
            if [ -f "$VOICE_MIRROR" ]; then
                mark_did "updated" "voice/config.json (instance mirror)" ""
                DID_UPDATED=$((DID_UPDATED + 1))
            else
                mark_did "created" "voice/config.json (instance mirror)" ""
                DID_CREATED=$((DID_CREATED + 1))
            fi
        else
            mark_did "failed" "voice/config.json (instance mirror)" "jq write failed"
            DID_FAILED=$((DID_FAILED + 1))
        fi
    fi
fi

# ── Persist IDE Bridge settings ─────────────────────────────────────────────

if [ "$ide_bridge_changed" = "true" ] && [ "$DRY_RUN" = "false" ]; then
    print_step "IDE Bridge configuration"
    if write_ide_bridge_config "$CONFIG_FILE" 2>/dev/null; then
        mark_did "updated" "tomo-install.json (.ide_bridge)" ""
        DID_UPDATED=$((DID_UPDATED + 1))
    else
        mark_did "failed" "tomo-install.json (.ide_bridge)" "write_ide_bridge_config failed"
        DID_FAILED=$((DID_FAILED + 1))
    fi
    lock_path="${HOME_DIR}/.claude/ide/${IDE_BRIDGE_PORT}.lock"
    if [ "$IDE_BRIDGE_ENABLED" = "true" ]; then
        lock_existed=false
        [ -f "$lock_path" ] && lock_existed=true
        write_ide_lock "$HOME_DIR" "$IDE_BRIDGE_PORT" "$IDE_BRIDGE_TOKEN"
        if [ "$lock_existed" = "true" ]; then
            mark_did "updated" "ide lock: $lock_path" ""
            DID_UPDATED=$((DID_UPDATED + 1))
        else
            mark_did "created" "ide lock: $lock_path" ""
            DID_CREATED=$((DID_CREATED + 1))
        fi
    else
        if [ -f "$lock_path" ]; then
            remove_ide_lock "$HOME_DIR" "$IDE_BRIDGE_PORT"
            mark_did "deleted" "ide lock: $lock_path" ""
            DID_DELETED=$((DID_DELETED + 1))
        fi
    fi
fi

# ── Update install config version ─────────────────────────

SOURCE_VERSION=$(get_version "$TOMO_SOURCE/dot_claude/rules/project-context.md")
jq --arg v "$SOURCE_VERSION" '.tomoVersion = $v | .updatedAt = (now | strftime("%Y-%m-%dT%H:%M:%SZ"))' \
    "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"

# ── Final summary ────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ current : $DID_CURRENT  files"
echo "  ↑ updated : $DID_UPDATED  files"
echo "  + created : $DID_CREATED  files"
echo "  - deleted : $DID_DELETED  files"
[ "$DID_FAILED" -gt 0 ] && echo "  ! failed  : $DID_FAILED  files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ "$DID_FAILED" -gt 0 ] && exit 1
exit 0
