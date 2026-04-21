#!/usr/bin/env bash
# vault-reset.sh — Reset the test vault inbox to a known pipeline stage.
# version: 0.2.0
#
# Designed for macOS bash 3.2 (no declare -A, no mapfile).
#
# Stages of the /inbox pipeline:
#
#   raw           — pristine source items only (pre Pass 1)
#   pass1-done    — source items + unapproved *_suggestions.md
#   approved      — source items + [x] Approved *_suggestions.md
#   pass2-done    — source items + approved suggestions
#                 + rendered notes + instructions.{md,json}
#
# Subcommands:
#
#   raw                   Clear inbox, unzip the backup → pristine pre-Pass-1.
#                         Non-source files already in the inbox are moved to
#                         the archive folder first — nothing is lost.
#
#   archive               Archive Pass-2 artifacts only (rendered notes +
#                         *_instructions.md + *_instructions.json). Source
#                         items AND the Pass-1 *_suggestions.md approval
#                         marker are left in place so a Pass-2 retry works
#                         without re-reviewing. For a total wipe use `raw`.
#
#   snapshot <stage>      Copy the current inbox state to fixtures/<stage>/
#                         so it can be restored later. Useful after a
#                         successful Pass 1 / approval / Pass 2.
#
#   to <stage>            Restore the inbox from a previously-taken snapshot
#                         (after archiving whatever is there).
#
#   list                  Show available snapshots.
#
#   status                Show what's currently in the inbox.
#
# Environment:
#   VAULT   — path to the vault (default: /Volumes/Moon/Coding/MiYo/temp/Privat-Test)
#   ZIP     — path to the source-items backup zip (default: $VAULT/100 Inbox.zip)
#
# Safety:
#   - Refuses to run if $VAULT doesn't look like a vault (missing 100 Inbox/).
#   - Every destructive action archives first — sources and artifacts are
#     recoverable until you prune the archive folder.

set -eu

VAULT="${VAULT:-/Volumes/Moon/Coding/MiYo/temp/Privat-Test}"
ZIP="${ZIP:-$VAULT/100 Inbox.zip}"
INBOX="$VAULT/100 Inbox"
ARCHIVE_BASE="$INBOX/_archive"
FIXTURES_DIR="$VAULT/.vault-reset-fixtures"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*" >&2; }

check_vault() {
    [ -d "$VAULT" ] || die "vault not found: $VAULT"
    [ -d "$INBOX" ] || die "inbox not found: $INBOX (is \$VAULT correct?)"
}

timestamp() { date -u +%Y-%m-%d_%H%M%S; }

# ── Pattern detection ───────────────────────────────────────────────────
# Tomo's Pass-1/Pass-2 artifacts all share a YYYY-MM-DD_HHMM_ prefix.
# `archive` only touches Pass-2 artifacts (rendered notes + instruction
# sets). The Pass-1 suggestions doc (*_suggestions.md) is the user's
# approval marker — archiving it would lose the [x] Approved state and
# force a fresh review. For a total wipe use `raw` instead.
is_artifact() {
    # filename only, no path
    local name="$1"
    case "$name" in
        # Explicitly NEVER archive the suggestions doc — it's the approval
        # marker, not Pass-2 output.
        *_suggestions.md) return 1 ;;
        # Pass-2 instruction sets (machine + human view)
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9]_instructions.md) return 0 ;;
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9]_instructions.json) return 0 ;;
        # Any other timestamped markdown = rendered Pass-2 note
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9]_*.md) return 0 ;;
        *) return 1 ;;
    esac
}

# ── Archive helpers ─────────────────────────────────────────────────────
archive_artifacts() {
    local ts dest count
    ts=$(timestamp)
    dest="$ARCHIVE_BASE/$ts"
    count=0
    mkdir -p "$dest"
    for f in "$INBOX"/*.md "$INBOX"/*.json; do
        [ -e "$f" ] || continue
        local name
        name=$(basename "$f")
        if is_artifact "$name"; then
            mv -- "$f" "$dest/$name"
            count=$((count+1))
        fi
    done
    if [ "$count" -eq 0 ]; then
        rmdir "$dest" 2>/dev/null || true
        info "archive: no Tomo artifacts to move."
    else
        info "archive: moved $count artifact(s) → ${dest#$VAULT/}"
    fi
}

archive_everything_in_inbox() {
    local ts dest
    ts=$(timestamp)
    dest="$ARCHIVE_BASE/pre-raw-$ts"
    mkdir -p "$dest"
    local moved=0
    # Move everything except _archive itself
    for f in "$INBOX"/* "$INBOX"/.[!.]*; do
        [ -e "$f" ] || continue
        case "$(basename "$f")" in
            _archive) continue ;;
        esac
        mv -- "$f" "$dest/" 2>/dev/null && moved=$((moved+1)) || true
    done
    if [ "$moved" -eq 0 ]; then
        rmdir "$dest" 2>/dev/null || true
        info "archive: inbox already empty."
    else
        info "archive: moved $moved item(s) → ${dest#$VAULT/}"
    fi
}

# ── Subcommands ─────────────────────────────────────────────────────────

cmd_raw() {
    check_vault
    [ -f "$ZIP" ] || die "backup zip not found: $ZIP"
    archive_everything_in_inbox
    info "raw: unzipping $(basename "$ZIP") → 100 Inbox/"
    # Strip the "100 Inbox/" prefix so contents land at the right level; skip __MACOSX
    ( cd "$VAULT" && unzip -q -o "$ZIP" -x "__MACOSX/*" )
    # Count resulting source items
    local count
    count=$(find "$INBOX" -maxdepth 1 -type f -name "*.md" ! -name "[0-9][0-9][0-9][0-9]-*" | wc -l | tr -d ' ')
    info "raw: restored — $count source item(s) in inbox."
}

cmd_archive() {
    check_vault
    archive_artifacts
}

cmd_snapshot() {
    local stage="${1:-}"
    [ -n "$stage" ] || die "usage: vault-reset.sh snapshot <stage>"
    check_vault
    local dest="$FIXTURES_DIR/$stage"
    if [ -d "$dest" ]; then
        info "snapshot: overwriting existing $stage fixture at $dest"
        rm -rf "$dest"
    fi
    mkdir -p "$dest"
    # Copy inbox minus _archive
    local n=0
    for f in "$INBOX"/*.md "$INBOX"/*.json; do
        [ -e "$f" ] || continue
        cp -- "$f" "$dest/"
        n=$((n+1))
    done
    info "snapshot[$stage]: saved $n file(s) → $dest"
}

cmd_to() {
    local stage="${1:-}"
    [ -n "$stage" ] || die "usage: vault-reset.sh to <stage>"
    check_vault
    local src="$FIXTURES_DIR/$stage"
    [ -d "$src" ] || die "no snapshot for '$stage' at $src (run 'snapshot $stage' first)"
    archive_everything_in_inbox
    local n=0
    for f in "$src"/*.md "$src"/*.json; do
        [ -e "$f" ] || continue
        cp -- "$f" "$INBOX/"
        n=$((n+1))
    done
    info "to[$stage]: restored $n file(s) from $src"
}

cmd_list() {
    if [ ! -d "$FIXTURES_DIR" ]; then
        info "no snapshots yet. run 'vault-reset.sh snapshot <stage>' after a pipeline run."
        return 0
    fi
    info "snapshots in $FIXTURES_DIR:"
    for d in "$FIXTURES_DIR"/*/; do
        [ -d "$d" ] || continue
        local name n
        name=$(basename "$d")
        n=$(find "$d" -maxdepth 1 -type f | wc -l | tr -d ' ')
        printf '  %-20s %s file(s)\n' "$name" "$n" >&2
    done
}

cmd_status() {
    check_vault
    local sources=0 suggestions=0 instructions=0 rendered=0 other=0
    for f in "$INBOX"/*.md "$INBOX"/*.json; do
        [ -e "$f" ] || continue
        local name
        name=$(basename "$f")
        case "$name" in
            *_suggestions.md)   suggestions=$((suggestions+1)) ;;
            *_instructions.md|*_instructions.json) instructions=$((instructions+1)) ;;
            [0-9]*_[0-9]*_*.md) rendered=$((rendered+1)) ;;
            *.md)               sources=$((sources+1)) ;;
            *)                  other=$((other+1)) ;;
        esac
    done
    info "inbox: $INBOX"
    info "  source items:      $sources"
    info "  suggestions docs:  $suggestions"
    info "  instruction files: $instructions"
    info "  rendered notes:    $rendered"
    info "  other:             $other"
    if [ -d "$ARCHIVE_BASE" ]; then
        local a
        a=$(find "$ARCHIVE_BASE" -maxdepth 1 -type d ! -path "$ARCHIVE_BASE" | wc -l | tr -d ' ')
        info "  archive snapshots: $a ($ARCHIVE_BASE)"
    fi
}

usage() {
    sed -n '2,40p' "$0"
    exit 1
}

main() {
    local cmd="${1:-}"
    case "$cmd" in
        raw)      shift; cmd_raw "$@" ;;
        archive)  shift; cmd_archive "$@" ;;
        snapshot) shift; cmd_snapshot "$@" ;;
        to)       shift; cmd_to "$@" ;;
        list)     shift; cmd_list "$@" ;;
        status)   shift; cmd_status "$@" ;;
        ""|-h|--help|help) usage ;;
        *) die "unknown subcommand: $cmd (see: $0 --help)" ;;
    esac
}

main "$@"
