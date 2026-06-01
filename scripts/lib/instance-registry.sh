#!/bin/bash
# instance-registry.sh — Sourceable bash library for ~/.tomo/instances.json management.
# Provides: registry_path, registry_list, registry_list_check, registry_upsert,
#           registry_resolve, registry_remove.
# Uses jq for all JSON reads/writes (atomic tmp→mv). bash 3.2 safe (no assoc arrays).
# Tests override TOMO_REGISTRY_FILE to isolate from the real ~/.tomo/.
# version: 0.1.0

_REGISTRY_DEFAULT_DIR="$HOME/.tomo"
_REGISTRY_DEFAULT_FILE="$_REGISTRY_DEFAULT_DIR/instances.json"

# ---------------------------------------------------------------------------
# registry_path — echo the registry file path
# ---------------------------------------------------------------------------
registry_path() {
    if [ -n "${TOMO_REGISTRY_FILE:-}" ]; then
        echo "$TOMO_REGISTRY_FILE"
    else
        echo "$_REGISTRY_DEFAULT_FILE"
    fi
}

# ---------------------------------------------------------------------------
# _registry_dir — echo the directory containing the registry file
# ---------------------------------------------------------------------------
_registry_dir() {
    local reg
    reg="$(registry_path)"
    dirname "$reg"
}

# ---------------------------------------------------------------------------
# _registry_ensure_dir — create the registry directory if absent; fail clearly
#                         if the directory is unwritable.
# Returns 0 on success, non-zero on failure (error to stderr).
# ---------------------------------------------------------------------------
_registry_ensure_dir() {
    local dir
    dir="$(_registry_dir)"
    if [ ! -d "$dir" ]; then
        if ! mkdir -p "$dir" 2>/dev/null; then
            echo "instance-registry: cannot create registry directory: $dir" >&2
            return 1
        fi
    fi
    if [ ! -w "$dir" ]; then
        echo "instance-registry: registry directory is not writable: $dir" >&2
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# _registry_load_safe — prints the JSON content of the registry file, or
#                        empty JSON stub if absent/corrupt.
#   If corrupt: backs up the bad file as <file>.corrupt-<timestamp> and
#               emits a warning to stderr.
#   Output: the JSON string (always a valid {"schema_version":1,"instances":[…]})
# ---------------------------------------------------------------------------
_REGISTRY_EMPTY_JSON='{"schema_version":1,"instances":[]}'

_registry_load_safe() {
    local reg
    reg="$(registry_path)"

    if [ ! -f "$reg" ]; then
        echo "$_REGISTRY_EMPTY_JSON"
        return 0
    fi

    # Validate JSON
    if jq empty "$reg" 2>/dev/null; then
        cat "$reg"
    else
        # Back up the corrupt file
        local ts
        ts="$(date -u +%Y%m%dT%H%M%SZ)"
        local backup="${reg}.corrupt-${ts}"
        cp "$reg" "$backup" 2>/dev/null || true
        echo "instance-registry: corrupt registry backed up to $backup; treating as empty" >&2
        echo "$_REGISTRY_EMPTY_JSON"
    fi
}

# ---------------------------------------------------------------------------
# _registry_write_atomic <json-string> — write JSON to registry atomically
#   Returns non-zero if the directory is unwritable.
# ---------------------------------------------------------------------------
_registry_write_atomic() {
    local json="$1"
    local reg
    reg="$(registry_path)"
    local tmp="${reg}.tmp"

    if ! _registry_ensure_dir; then
        return 1
    fi

    # Write to .tmp then mv — atomic replace
    if ! echo "$json" | jq . > "$tmp" 2>/dev/null; then
        rm -f "$tmp"
        echo "instance-registry: failed to write registry (jq error)" >&2
        return 1
    fi
    if ! mv "$tmp" "$reg"; then
        rm -f "$tmp"
        echo "instance-registry: failed to rename $tmp → $reg" >&2
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# registry_list — print all entries (one JSON object per line)
#   Empty or missing file → empty output, exit 0.
# ---------------------------------------------------------------------------
registry_list() {
    local current
    current="$(_registry_load_safe)"
    # Print each entry as compact JSON on its own line
    echo "$current" | jq -c '.instances[]' 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# registry_list_check — like registry_list but also reports stale entries
#   (entries whose path directory is missing). Stale entries are printed with
#   a "[stale]" prefix. Exit 0 always (never crash on stale data). [F2-AC3]
# ---------------------------------------------------------------------------
registry_list_check() {
    local current
    current="$(_registry_load_safe)"

    local count
    count="$(echo "$current" | jq '.instances | length')"
    local i=0
    while [ "$i" -lt "$count" ]; do
        local entry name path
        entry="$(echo "$current" | jq -c ".instances[$i]")"
        name="$(echo "$entry" | jq -r '.name')"
        path="$(echo "$entry" | jq -r '.path')"
        if [ ! -d "$path" ]; then
            echo "[stale] $name — path missing: $path"
        else
            echo "$entry"
        fi
        i=$((i + 1))
    done
    return 0
}

# ---------------------------------------------------------------------------
# registry_upsert <name> <path> <repo> <version>
#   Create or overwrite the entry keyed by unique name.
#   Sets updatedAt to ISO-8601 UTC timestamp.
# ---------------------------------------------------------------------------
registry_upsert() {
    local name="$1"
    local path="$2"
    local repo="$3"
    local version="$4"

    if [ -z "$name" ] || [ -z "$path" ] || [ -z "$repo" ] || [ -z "$version" ]; then
        echo "registry_upsert: requires <name> <path> <repo> <version>" >&2
        return 2
    fi

    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    local current
    current="$(_registry_load_safe)"

    # Filter out any existing entry with the same name, then append new one
    local new_json
    new_json="$(echo "$current" | jq \
        --arg name    "$name" \
        --arg path    "$path" \
        --arg repo    "$repo" \
        --arg version "$version" \
        --arg ts      "$ts" \
        '.instances = (
            [.instances[] | select(.name != $name)]
            + [{ name: $name, path: $path, repo: $repo, version: $version, updatedAt: $ts }]
        ) | .schema_version = 1')"

    _registry_write_atomic "$new_json"
}

# ---------------------------------------------------------------------------
# registry_resolve <name> — print the path field for the named entry.
#   Unknown name → non-zero exit + empty output.
# ---------------------------------------------------------------------------
registry_resolve() {
    local name="$1"
    if [ -z "$name" ]; then
        echo "registry_resolve: requires <name>" >&2
        return 2
    fi

    local current
    current="$(_registry_load_safe)"

    local path
    path="$(echo "$current" | jq -r --arg name "$name" \
        '.instances[] | select(.name == $name) | .path' 2>/dev/null)"

    if [ -z "$path" ]; then
        return 1
    fi
    echo "$path"
    return 0
}

# ---------------------------------------------------------------------------
# registry_remove <name> — drop the named entry (no-op if absent, exit 0).
# ---------------------------------------------------------------------------
registry_remove() {
    local name="$1"
    if [ -z "$name" ]; then
        echo "registry_remove: requires <name>" >&2
        return 2
    fi

    local current
    current="$(_registry_load_safe)"

    # Check if it even exists — if not, no-op exit 0
    local exists
    exists="$(echo "$current" | jq -r --arg name "$name" \
        '.instances[] | select(.name == $name) | .name' 2>/dev/null)"

    if [ -z "$exists" ]; then
        return 0
    fi

    local new_json
    new_json="$(echo "$current" | jq \
        --arg name "$name" \
        '.instances = [.instances[] | select(.name != $name)]')"

    _registry_write_atomic "$new_json"
}
