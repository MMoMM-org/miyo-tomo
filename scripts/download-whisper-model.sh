#!/bin/bash
# download-whisper-model.sh — Fetch a Systran/faster-whisper-<size> repo
# from HuggingFace into a local directory. No Python dependency on host.
# Uses the HF API to discover the file list, then curl per file.
# version: 0.1.0
set -e

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

REPO="Systran/faster-whisper-${SIZE}"
API_URL="https://huggingface.co/api/models/${REPO}/tree/main"
FILE_BASE="https://huggingface.co/${REPO}/resolve/main"

mkdir -p "$DEST"

echo "→ Fetching file manifest for ${REPO}..."
manifest="$(curl -fsSL "$API_URL")" || {
    echo "✗ Failed to fetch manifest from $API_URL" >&2
    exit 2
}

files="$(echo "$manifest" | jq -r '.[] | select(.type == "file") | .path')"
if [ -z "$files" ]; then
    echo "✗ Empty manifest — no files to download from $REPO" >&2
    exit 2
fi

file_count=0
for f in $files; do
    file_count=$((file_count + 1))
done
echo "→ ${file_count} files to download"

idx=0
for f in $files; do
    idx=$((idx + 1))
    url="${FILE_BASE}/${f}"
    out="${DEST}/${f}"
    mkdir -p "$(dirname "$out")"
    echo "  [${idx}/${file_count}] ${f}"
    if ! curl -fL --retry 3 --retry-delay 2 -sS -o "$out" "$url"; then
        echo "✗ Failed to download ${f}" >&2
        rm -f "$out"
        exit 3
    fi
    if [ ! -s "$out" ]; then
        echo "✗ Empty file after download: ${out}" >&2
        exit 3
    fi
done

# Report final size
if command -v du > /dev/null 2>&1; then
    size="$(du -sh "$DEST" | awk '{print $1}')"
    echo "✓ Downloaded to ${DEST} (${size})"
else
    echo "✓ Downloaded to ${DEST}"
fi
