#!/bin/bash
# render-launcher.sh — Sourceable lib: substitute 5 placeholders in begin-tomo.sh.template.
# version: 0.1.0

# render_launcher <template> <dst> <instance_name> <instance_path> <home_dir> <repo_root> <dev_notify_port>
#
# Renders <template> to <dst> by substituting exactly 5 placeholders:
#   {{INSTANCE_NAME}}   ← instance_name
#   {{INSTANCE_PATH}}   ← instance_path
#   {{HOME_DIR}}        ← home_dir
#   {{TOMO_REPO_ROOT}}  ← repo_root
#   {{DEV_NOTIFY_PORT}} ← dev_notify_port
#
# Write is atomic: output goes to <dst>.tmp, then mv to <dst>.
# On any failure the .tmp file is cleaned up and non-zero is returned;
# the dst is never left in a partially-written state.
#
# sed-special characters (& | /) in replacement values are escaped so they
# render literally.  Uses \x01 as the sed delimiter to avoid collisions with
# paths that contain the more common delimiters (| / ,).

render_launcher() {
    local template="$1"
    local dst="$2"
    local instance_name="$3"
    local instance_path="$4"
    local home_dir="$5"
    local repo_root="$6"
    local dev_notify_port="$7"

    if [ -z "$template" ] || [ -z "$dst" ] || [ -z "$instance_name" ] || \
       [ -z "$instance_path" ] || [ -z "$home_dir" ] || [ -z "$repo_root" ] || \
       [ -z "$dev_notify_port" ]; then
        printf 'render_launcher: missing argument(s)\n' >&2
        return 1
    fi

    if [ ! -f "$template" ]; then
        printf 'render_launcher: template not found: %s\n' "$template" >&2
        return 1
    fi

    local tmp="${dst}.tmp"

    # Escape values so sed treats them as literal replacement text.
    # The chosen delimiter is \x01 (unlikely in any path).  We must escape:
    #   & → \&   (sed expands & to the matched text in the replacement side)
    #   \ → \\   (escape-char itself)
    #   \x01 (our delimiter) — escape any literal \x01 in the value (paranoia)
    _escape_sed_replacement() {
        # Order: backslash first, then delimiter, then ampersand.
        printf '%s' "$1" \
            | sed 's/\\/\\\\/g' \
            | sed $'s/\x01/\\\x01/g' \
            | sed 's/&/\\&/g'
    }

    local esc_instance_name esc_instance_path esc_home_dir esc_repo_root esc_dev_notify_port
    esc_instance_name=$(_escape_sed_replacement "$instance_name")
    esc_instance_path=$(_escape_sed_replacement "$instance_path")
    esc_home_dir=$(_escape_sed_replacement "$home_dir")
    esc_repo_root=$(_escape_sed_replacement "$repo_root")
    esc_dev_notify_port=$(_escape_sed_replacement "$dev_notify_port")

    # Render to tmp; clean up on failure.
    # Using \x01 as delimiter (printf octal \001) to sidestep / | , collisions.
    if sed \
        -e $'s\x01{{INSTANCE_PATH}}\x01'"${esc_instance_path}"$'\x01g' \
        -e $'s\x01{{INSTANCE_NAME}}\x01'"${esc_instance_name}"$'\x01g' \
        -e $'s\x01{{HOME_DIR}}\x01'"${esc_home_dir}"$'\x01g' \
        -e $'s\x01{{TOMO_REPO_ROOT}}\x01'"${esc_repo_root}"$'\x01g' \
        -e $'s\x01{{DEV_NOTIFY_PORT}}\x01'"${esc_dev_notify_port}"$'\x01g' \
        "$template" > "$tmp" 2>/dev/null; then
        chmod +x "$tmp"
        mv "$tmp" "$dst"
    else
        local rc=$?
        rm -f "$tmp"
        return $rc
    fi
}
