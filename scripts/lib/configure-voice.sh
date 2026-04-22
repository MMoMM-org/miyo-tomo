#!/bin/bash
# configure-voice.sh — Stateful voice-transcription wizard for install/update.
# Sourced from install-tomo.sh and update-tomo.sh. Relies on the sourcing
# script providing print_step / print_ok / print_warn / print_err helpers.
#
# Sets globals on successful run:
#   VOICE_ENABLED   — "true" or "false"
#   VOICE_MODEL     — "tiny" | "base" | "small" | "medium" | "large-v3" | ""
#   VOICE_LANGUAGE  — "de" | "en" | "auto" | ""
# version: 0.5.0

# Resolve the directory this file lives in at SOURCE TIME. BASH_SOURCE[0]
# is reliable here (top-level of the sourced file); deep inside a
# function called later, bash 3.2 can emit it as an empty string after
# nested command substitutions — observed 2026-04-22 while writing
# configure_voice pytest coverage.
_TOMO_VOICE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_TOMO_VOICE_SCRIPTS_DIR="$(cd "$_TOMO_VOICE_LIB_DIR/.." && pwd)"

# Schema version for the `voice` block in tomo-install.json and its
# mirror. Bump only with a migration path.
_TOMO_VOICE_SCHEMA_VERSION=1

# Persist the VOICE_* globals into a target JSON file's `.voice` block
# via jq. Call site: both install-tomo.sh and update-tomo.sh use this;
# having one authoritative writer collapses the previous three-site
# duplication (review finding M9).
#
# Usage: write_voice_config <target-json-file>
write_voice_config() {
    local target="$1"
    if [ -z "$target" ]; then
        echo "write_voice_config: missing target file" >&2
        return 2
    fi
    if [ ! -f "$target" ]; then
        echo "write_voice_config: target does not exist: $target" >&2
        return 2
    fi
    jq --argjson schema "$_TOMO_VOICE_SCHEMA_VERSION" \
       --argjson enabled "${VOICE_ENABLED:-false}" \
       --arg model "${VOICE_MODEL:-}" \
       --arg lang  "${VOICE_LANGUAGE:-}" \
       '.voice = { schema_version: $schema, enabled: $enabled, model: $model, language: $lang }' \
       "$target" > "$target.tmp" && mv "$target.tmp" "$target"
}

# Known model metadata (bash 3.2 — no associative arrays)
# Keep in sync with docs/XDD/specs/009-voice-memo-transcription/solution.md
_voice_size_list="tiny base small medium large-v3"

_voice_size_info() {
    # Sizes are on-disk footprint after download (float16 weights).
    # The second column is approximate resident RAM during inference
    # (int8 quantization applied at load time) — used for the Docker
    # Desktop memory guidance below (review finding L8).
    case "$1" in
        tiny)     echo " 83 MB   fast, weak German                 (~0.3 GB RAM)" ;;
        base)     echo "145 MB   decent English                    (~0.5 GB RAM)" ;;
        small)    echo "480 MB   solid German                      (~1.0 GB RAM)" ;;
        medium)   echo "1.5 GB   very good German  (recommended)   (~2.0 GB RAM)" ;;
        large-v3) echo "3.1 GB   best quality, slowest             (~4.0 GB RAM)" ;;
        *)        echo "" ;;
    esac
}

# Usage:
#   configure_voice <current_enabled> <current_model> <current_language> \
#                   <models_base_dir> [non_interactive]
# Where:
#   current_*        — existing state (from tomo-install.json, or "false" / "" for fresh installs)
#   models_base_dir  — directory where per-size model subdirs live
#                      (e.g. $INSTANCE_PATH/voice/models)
#   non_interactive  — "true" to suppress all prompts (keeps current state)
configure_voice() {
    local current_enabled="${1:-false}"
    local current_model="${2:-}"
    local current_language="${3:-}"
    local models_base_dir="${4:-}"
    local non_interactive="${5:-false}"

    VOICE_ENABLED="$current_enabled"
    VOICE_MODEL="$current_model"
    VOICE_LANGUAGE="$current_language"

    print_step "Voice memo transcription"

    if [ "$non_interactive" = "true" ]; then
        if [ "$VOICE_ENABLED" = "true" ]; then
            print_ok "Voice: kept ENABLED (model=$VOICE_MODEL, lang=${VOICE_LANGUAGE:-auto})"
        else
            VOICE_ENABLED="false"
            print_ok "Voice: disabled (non-interactive default)"
        fi
        return 0
    fi

    echo "  Transcribe inbox audio via local Whisper (faster-whisper, CPU-only)."
    echo ""

    # ── State dispatch ───────────────────────────────────
    local want_change="false"
    if [ "$VOICE_ENABLED" = "true" ]; then
        echo "  Currently: ENABLED  (model=${VOICE_MODEL}, lang=${VOICE_LANGUAGE:-auto})"
        echo ""
        echo "    [K] keep current settings"
        echo "    [c] change model or language"
        echo "    [d] disable voice"
        local choice
        read -rp "  > " choice
        choice="${choice:-K}"
        case "$choice" in
            k|K|keep)
                print_ok "Voice: kept ENABLED"
                return 0
                ;;
            d|D|disable)
                VOICE_ENABLED="false"
                print_ok "Voice: disabled"
                if [ -n "$models_base_dir" ] && [ -d "$models_base_dir" ]; then
                    local existing
                    existing="$(ls -1 "$models_base_dir" 2>/dev/null | wc -l | tr -d ' ')"
                    if [ "$existing" -gt 0 ]; then
                        local remove
                        read -rp "  Remove $existing model dir(s) from $models_base_dir? [y/N]: " remove
                        case "$remove" in
                            y|Y|yes)
                                # Use find instead of `rm -rf "$dir"/faster-whisper-*` —
                                # the glob breaks when the base path contains spaces
                                # (word-splitting shifts the glob anchor).
                                find "$models_base_dir" -maxdepth 1 \
                                    -name 'faster-whisper-*' -exec rm -rf {} +
                                print_ok "Model files removed"
                                ;;
                        esac
                    fi
                fi
                return 0
                ;;
            c|C|change)
                want_change="true"
                ;;
            *)
                print_warn "Unrecognised choice — keeping current settings"
                return 0
                ;;
        esac
    else
        echo "  Currently: DISABLED"
        echo ""
        local enable
        read -rp "  Enable voice transcription? [y/N]: " enable
        case "$enable" in
            y|Y|yes)
                VOICE_ENABLED="true"
                want_change="true"
                ;;
            *)
                VOICE_ENABLED="false"
                print_ok "Voice: remains disabled"
                return 0
                ;;
        esac
    fi

    # ── Model selection ──────────────────────────────────
    echo ""
    echo "  Whisper model sizes:"
    for sz in $_voice_size_list; do
        printf "    %-9s %s\n" "$sz" "$(_voice_size_info "$sz")"
    done
    echo ""
    echo "  Tip: Docker Desktop's memory limit (Settings → Resources) needs"
    echo "       to cover the selected model's RAM footprint + ~1 GB headroom."
    echo "       Default Docker Desktop memory (8 GB) is plenty for medium."
    echo ""
    local default_model="${VOICE_MODEL:-medium}"
    local new_model
    read -rp "  Model [${default_model}]: " new_model
    new_model="${new_model:-$default_model}"

    local valid=""
    for sz in $_voice_size_list; do
        if [ "$new_model" = "$sz" ]; then valid="yes"; break; fi
    done
    if [ -z "$valid" ]; then
        print_err "Invalid model '$new_model' — keeping $default_model"
        new_model="$default_model"
    fi
    VOICE_MODEL="$new_model"

    # ── Language hint ────────────────────────────────────
    local default_lang="${VOICE_LANGUAGE:-de}"
    echo ""
    echo "  Primary audio language: de | en | auto"
    local new_lang
    read -rp "  Language [${default_lang}]: " new_lang
    new_lang="${new_lang:-$default_lang}"
    # Allowlist — unvalidated input would inject into tomo-install.json
    # via jq/heredoc write paths (review finding M1). Also protects the
    # CLI from receiving a non-Whisper language code.
    case "$new_lang" in
        de|en|auto|"") ;;
        *)
            print_err "Invalid language '$new_lang' — expected de|en|auto, keeping '$default_lang'"
            new_lang="$default_lang"
            ;;
    esac
    VOICE_LANGUAGE="$new_lang"

    # ── Ensure model files present ───────────────────────
    # Check the .download-complete sentinel rather than model.bin — catches
    # the case where a prior download was interrupted and left a partial
    # directory behind (only model.bin succeeded, others missing).
    if [ -n "$models_base_dir" ]; then
        local target_dir="${models_base_dir}/faster-whisper-${VOICE_MODEL}"
        if [ -f "$target_dir/.download-complete" ]; then
            print_ok "Model already on disk: $target_dir (verified)"
        else
            if [ -d "$target_dir" ]; then
                print_warn "Partial or unverified model dir detected — re-downloading"
            fi
            local dl="$_TOMO_VOICE_SCRIPTS_DIR/download-whisper-model.sh"
            if [ ! -x "$dl" ]; then
                print_err "Download helper not found or not executable: $dl"
                return 1
            fi
            mkdir -p "$models_base_dir"
            print_ok "Downloading ${VOICE_MODEL} → ${target_dir}"
            if ! "$dl" "$VOICE_MODEL" "$target_dir"; then
                print_err "Download failed — voice will be unavailable until retried"
                return 1
            fi
        fi
    fi

    print_ok "Voice: ENABLED (model=$VOICE_MODEL, lang=$VOICE_LANGUAGE)"
    return 0
}
