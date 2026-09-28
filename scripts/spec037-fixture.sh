#!/usr/bin/env bash
# spec037-fixture.sh — snapshot and restore the 2026-09-15 collision fixture
# in the Privat-Test vault, for spec 037 T4.3/T4.4 live runs.
#
# The plan's Success line cites `scratchpad/restore-trigger-notes.sh`, which
# does not exist anywhere in the repo. This replaces it.
#
# Snapshot BEFORE the first run. Restore between runs, and after the last one,
# so every run starts from identical vault state — T4.4 explicitly requires it.
#
#   bash scripts/spec037-fixture.sh snapshot   # take the baseline (do this first)
#   bash scripts/spec037-fixture.sh status     # what differs from the baseline now
#   bash scripts/spec037-fixture.sh restore    # put the vault back to the baseline
#
# Touches ONLY the paths this fixture owns. It never writes to tomo-privat,
# never touches the rest of the vault, and refuses to run if the baseline is
# missing or the vault path is wrong.
set -euo pipefail

VAULT="/Volumes/Moon/Coding/MiYo/temp/Privat-Test"
# NOT under $TMPDIR: that differs between a Claude session and a login shell,
# so a baseline taken in one would be invisible to the other. Fixed path.
SNAP="$HOME/.tomo-spec037-fixture-baseline"

# Everything a T4.3/T4.4 run can create, move, modify or delete.
FIXTURE_FILES=(
  "100 Inbox/Dresden.md"
  "100 Inbox/Scans/karte.png"
  "Atlas/290 Assets/295 Attachments/karte.png"
)
# Paths a run may CREATE that the baseline must not contain. Restore removes
# any that appeared. Globs are expanded at restore time, not now.
CREATED_GLOBS=(
  "Atlas/290 Assets/295 Attachments/karte (*).png"
  "Atlas/202 Notes/Dresden*.md"
  "100 Inbox/*_suggestions.md"
  "100 Inbox/*_suggestions.json"
  "100 Inbox/*_instructions.md"
  "100 Inbox/*_instructions.json"
)

die() { printf 'spec037-fixture: %s\n' "$1" >&2; exit 1; }

[ -d "$VAULT" ] || die "vault not found: $VAULT"
case "$VAULT" in
  */tomo-privat*) die "refusing to touch tomo-privat — this is a LIVE vault" ;;
esac

cmd_snapshot() {
  [ -d "$SNAP" ] && die "baseline already exists at $SNAP — delete it deliberately if you really mean to re-baseline"
  mkdir -p "$SNAP/files"
  local missing=0
  for rel in "${FIXTURE_FILES[@]}"; do
    if [ ! -f "$VAULT/$rel" ]; then
      printf '  MISSING  %s\n' "$rel"; missing=1; continue
    fi
    mkdir -p "$SNAP/files/$(dirname "$rel")"
    cp -p "$VAULT/$rel" "$SNAP/files/$rel"
    printf '  saved    %s  (%s)\n' "$rel" "$(shasum -a 256 "$VAULT/$rel" | cut -c1-12)"
  done
  # Record what already existed so restore never deletes a pre-existing file.
  : > "$SNAP/preexisting.txt"
  for glob in "${CREATED_GLOBS[@]}"; do
    while IFS= read -r f; do printf '%s\n' "${f#"$VAULT/"}" >> "$SNAP/preexisting.txt"; done \
      < <(find "$VAULT" -path "$VAULT/$glob" -type f 2>/dev/null || true)
  done
  [ "$missing" -eq 1 ] && die "one or more fixture files are missing — fix the vault before baselining"
  printf '\nBaseline written to %s\n' "$SNAP"
  printf 'Pre-existing generated files recorded: %s\n' "$(wc -l < "$SNAP/preexisting.txt" | tr -d ' ')"
}

cmd_status() {
  [ -d "$SNAP" ] || die "no baseline — run 'snapshot' first"
  local drift=0
  for rel in "${FIXTURE_FILES[@]}"; do
    if [ ! -f "$VAULT/$rel" ]; then
      printf '  GONE     %s\n' "$rel"; drift=1
    elif ! cmp -s "$VAULT/$rel" "$SNAP/files/$rel"; then
      printf '  CHANGED  %s\n' "$rel"; drift=1
    else
      printf '  ok       %s\n' "$rel"
    fi
  done
  for glob in "${CREATED_GLOBS[@]}"; do
    while IFS= read -r f; do
      local rel="${f#"$VAULT/"}"
      grep -Fxq "$rel" "$SNAP/preexisting.txt" 2>/dev/null && continue
      printf '  NEW      %s\n' "$rel"; drift=1
    done < <(find "$VAULT" -path "$VAULT/$glob" -type f 2>/dev/null || true)
  done
  [ "$drift" -eq 0 ] && printf '\nVault matches the baseline.\n' || printf '\nVault differs from the baseline (expected after a run).\n'
}

cmd_restore() {
  [ -d "$SNAP" ] || die "no baseline — cannot restore"
  for glob in "${CREATED_GLOBS[@]}"; do
    while IFS= read -r f; do
      local rel="${f#"$VAULT/"}"
      grep -Fxq "$rel" "$SNAP/preexisting.txt" 2>/dev/null && continue
      rm -f "$f" && printf '  removed  %s\n' "$rel"
    done < <(find "$VAULT" -path "$VAULT/$glob" -type f 2>/dev/null || true)
  done
  for rel in "${FIXTURE_FILES[@]}"; do
    mkdir -p "$VAULT/$(dirname "$rel")"
    cp -p "$SNAP/files/$rel" "$VAULT/$rel"
    printf '  restored %s\n' "$rel"
  done
  printf '\nFixture restored. Verifying:\n'
  cmd_status
}

case "${1:-}" in
  snapshot) cmd_snapshot ;;
  status)   cmd_status ;;
  restore)  cmd_restore ;;
  *) die "usage: $0 {snapshot|status|restore}" ;;
esac
