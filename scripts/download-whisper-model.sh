#!/bin/bash
# download-whisper-model.sh — Fetch a Systran/faster-whisper-<size> repo
# from HuggingFace into a local directory. No Python dependency on host.
# Uses the HF API for file discovery + integrity verification:
#   - manifest path validation (reject .. / leading /)
#   - size check for every file (catches truncation)
#   - sha256 verification for LFS-tracked files (the big model.bin)
# On success, writes <dest>/.download-complete as a sentinel file so the
# caller can detect an incomplete/corrupt state after an interrupted run.
# version: 0.3.0
set -e

# Clean up any partial state if the user Ctrl-Cs mid-download.
# The caller (configure_voice) only re-invokes us when the sentinel is
# missing, so wiping DEST on interrupt is always safe.
_on_interrupt() {
    local code=$?
    if [ -n "${DEST:-}" ] && [ -d "$DEST" ]; then
        echo "" >&2
        echo "⚠ Interrupted — removing partial download at $DEST" >&2
        rm -rf "${DEST:?}" 2>/dev/null || true
    fi
    trap - EXIT
    exit "$code"
}
trap _on_interrupt INT TERM

SIZE="${1:-}"
DEST="${2:-}"

if [ -z "$SIZE" ] || [ -z "$DEST" ]; then
    echo "Usage: $0 <size> <dest_dir>" >&2
    echo "  <size>      one of: tiny base small medium large-v3" >&2
    echo "  <dest_dir>  target directory (created if missing)" >&2
    exit 1
fi

case "$SIZE" in
    tiny|base|small|medium|large-v3) ;;
    *)
        echo "Invalid size: $SIZE (expected tiny|base|small|medium|large-v3)" >&2
        exit 1
        ;;
esac

for cmd in curl jq; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        echo "✗ $cmd is required but not installed." >&2
        exit 1
    fi
done

# Pick a sha256 tool — openssl is the most universally available; shasum on
# macOS and sha256sum on most Linux work too. We only need ONE.
sha256_of() {
    local file="$1"
    if command -v shasum > /dev/null 2>&1; then
        shasum -a 256 "$file" | awk '{print $1}'
    elif command -v sha256sum > /dev/null 2>&1; then
        sha256sum "$file" | awk '{print $1}'
    elif command -v openssl > /dev/null 2>&1; then
        openssl dgst -sha256 "$file" | awk '{print $NF}'
    else
        echo ""  # caller will treat empty as "unable to verify"
    fi
}

REPO="Systran/faster-whisper-${SIZE}"
API_URL="https://huggingface.co/api/models/${REPO}/tree/main"
FILE_BASE="https://huggingface.co/${REPO}/resolve/main"

# Clear any partial prior-state. Keeps the "sentinel present" assumption
# reliable: if this script re-runs and succeeds, the dir is fully consistent.
# The caller (configure_voice) only invokes us when the sentinel is missing,
# so wiping is safe.
SENTINEL="${DEST}/.download-complete"
if [ -d "$DEST" ]; then
    rm -rf "${DEST:?}"/*  "${SENTINEL}" 2>/dev/null || true
fi
mkdir -p "$DEST"

echo "→ Fetching file manifest for ${REPO}..."
manifest="$(curl -fsSL "$API_URL")" || {
    echo "✗ Failed to fetch manifest from $API_URL" >&2
    exit 2
}

# For each file, we extract: path, expected_size, and optional lfs_sha256.
# jq -c gives one compact JSON object per line so bash can iterate safely.
entries="$(echo "$manifest" | jq -c '.[] | select(.type == "file")
    | { path, size, lfs_sha256: (.lfs.oid // "") }')"
if [ -z "$entries" ]; then
    echo "✗ Empty manifest — no files to download from $REPO" >&2
    exit 2
fi

file_count="$(echo "$entries" | grep -c '^' || true)"
echo "→ ${file_count} files to download"

idx=0
verified_lines=""
while IFS= read -r entry; do
    idx=$((idx + 1))
    path="$(echo "$entry" | jq -r '.path')"
    expected_size="$(echo "$entry" | jq -r '.size')"
    lfs_sha="$(echo "$entry" | jq -r '.lfs_sha256 // empty')"
    # HF returns lfs.oid like "sha256:<hex>" — strip the prefix if present.
    lfs_sha="${lfs_sha#sha256:}"

    # Guard against a compromised or spoofed HF API response that injects
    # a path traversal (../../..) or an absolute path into the manifest —
    # either would cause us to write outside $DEST under the caller's UID.
    case "$path" in
        ""|*/..*|..*|*..|..|/*)
            echo "✗ Unsafe manifest path rejected: ${path}" >&2
            exit 3
            ;;
    esac
    case "$path" in
        *../*)
            echo "✗ Unsafe manifest path rejected (traversal): ${path}" >&2
            exit 3
            ;;
    esac

    url="${FILE_BASE}/${path}"
    out="${DEST}/${path}"
    mkdir -p "$(dirname "$out")"
    echo "  [${idx}/${file_count}] ${path} (${expected_size} bytes)"

    if ! curl -fL --retry 3 --retry-delay 2 -sS -o "$out" "$url"; then
        echo "✗ Failed to download ${path}" >&2
        rm -f "$out"
        exit 3
    fi

    # Size check — portable stat: GNU first, BSD fallback.
    actual_size="$(stat -c '%s' "$out" 2>/dev/null || stat -f '%z' "$out" 2>/dev/null || echo "")"
    if [ -z "$actual_size" ]; then
        echo "✗ stat failed on ${out}" >&2
        exit 3
    fi
    if [ "$actual_size" != "$expected_size" ]; then
        echo "✗ Size mismatch for ${path}: expected ${expected_size}, got ${actual_size}" >&2
        exit 3
    fi

    # SHA-256 check for LFS-tracked files (reliably catches corruption).
    # Non-LFS files rely on size check — git-blob-sha1 verification would
    # need extra plumbing and these files are tiny, so re-download on
    # failure is nearly free.
    verify_note="size ok"
    if [ -n "$lfs_sha" ]; then
        actual_sha="$(sha256_of "$out")"
        if [ -z "$actual_sha" ]; then
            echo "⚠ No sha256 tool available — skipping checksum for ${path}" >&2
            verify_note="size ok (sha256 unverified — no tool)"
        elif [ "$actual_sha" != "$lfs_sha" ]; then
            echo "✗ sha256 mismatch for ${path}:" >&2
            echo "    expected: ${lfs_sha}" >&2
            echo "    got:      ${actual_sha}" >&2
            exit 3
        else
            verify_note="size ok, sha256 verified"
        fi
    fi
    verified_lines="${verified_lines}${path}	${verify_note}
"
done <<EOF
$entries
EOF

# Write sentinel with a brief audit trail — size + sha256 status per file.
{
    echo "# faster-whisper-${SIZE} — download complete"
    echo "# repo:      ${REPO}"
    echo "# completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# files:"
    printf "%s" "$verified_lines" | sed 's/^/#   /'
} > "$SENTINEL"

# Report final size
if command -v du > /dev/null 2>&1; then
    size="$(du -sh "$DEST" | awk '{print $1}')"
    echo "✓ Downloaded to ${DEST} (${size}) — ${file_count} files verified"
else
    echo "✓ Downloaded to ${DEST} — ${file_count} files verified"
fi
