#!/bin/bash
# test-notify-bridge-hook.sh — the notify hook must emit valid JSON.
#   Covers: quote/backslash escaping in $MESSAGE and $TITLE, round-trip
#   fidelity, the instance label, and the timeout/stdout flags.
# version: 0.1.0
#
# The hook ends in `|| true` and always exits 0, so asserting on its exit code
# proves nothing — Kouzou made exactly that point when reporting the defect.
# These tests put a stub `curl` first on PATH, capture the body the hook would
# have POSTed, and assert on that instead. No bridge needs to be running.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

HOOK="tomo/dot_claude/hooks/dev-notify-bridge.sh"

if [ -t 1 ]; then
    C_RESET="\033[0m"; C_GREEN="\033[32m"; C_RED="\033[31m"; C_YELLOW="\033[33m"; C_DIM="\033[2m"
else
    C_RESET=""; C_GREEN=""; C_RED=""; C_YELLOW=""; C_DIM=""
fi
pass() { printf "  ${C_GREEN}✓${C_RESET} %s\n" "$1"; }
fail() { printf "  ${C_RED}✗${C_RESET} %s\n" "$1" >&2; FAILED=1; }
skip() { printf "  ${C_YELLOW}⊘${C_RESET} %s ${C_DIM}(%s)${C_RESET}\n" "$1" "$2"; }
FAILED=0

if ! command -v jq >/dev/null 2>&1; then
    skip "notify-bridge hook" "jq not installed"
    exit 0
fi
if [ ! -f "$HOOK" ]; then
    fail "hook not found at $HOOK"
    exit 1
fi

STUB_DIR=$(mktemp -d)
trap 'rm -rf "$STUB_DIR"' EXIT

# Stub curl: walk the args, write whatever followed -d to $CURL_BODY_FILE.
cat > "$STUB_DIR/curl" <<'STUB'
#!/bin/bash
prev=""
for a in "$@"; do
    if [ "$prev" = "-d" ]; then
        printf '%s' "$a" > "$CURL_BODY_FILE"
    fi
    prev="$a"
done
printf '%s\n' "$*" > "$CURL_ARGS_FILE"
exit 0
STUB
chmod +x "$STUB_DIR/curl"

# Run the hook with a given title/message; leaves the body in $BODY.
run_hook() {
    local title="$1" message="$2"
    export CURL_BODY_FILE="$STUB_DIR/body.json"
    export CURL_ARGS_FILE="$STUB_DIR/args.txt"
    : > "$CURL_BODY_FILE"
    : > "$CURL_ARGS_FILE"
    jq -n --arg t "$title" --arg m "$message" '{title: $t, message: $m}' \
        | PATH="$STUB_DIR:$PATH" bash "$HOOK" > /dev/null 2>&1
    BODY=$(cat "$CURL_BODY_FILE")
    ARGS=$(cat "$CURL_ARGS_FILE")
}

echo "notify-bridge hook — JSON body construction"

# ── The reported defect ────────────────────────────────────────────────────
# Kouzou's verbatim repro message; the old interpolation produced HTTP 400.
NASTY='pfad C:\temp und "zitat" hier'
run_hook "Claude Code" "$NASTY"

if [ -z "$BODY" ]; then
    fail "hook posted no body at all"
elif echo "$BODY" | jq -e . > /dev/null 2>&1; then
    pass "a message with a quote and a backslash yields valid JSON"
else
    fail "malformed JSON for quote+backslash message: $BODY"
fi

GOT=$(echo "$BODY" | jq -r '.message' 2>/dev/null)
if [ "$GOT" = "$NASTY" ]; then
    pass "the message round-trips byte-for-byte"
else
    fail "message altered in transit: expected [$NASTY] got [$GOT]"
fi

# ── The same hazard in the title, which comes from Claude too ──────────────
run_hook 'say "hi" \ now' "plain"
if echo "$BODY" | jq -e . > /dev/null 2>&1; then
    pass "a title with a quote and a backslash yields valid JSON"
else
    fail "malformed JSON for quote+backslash title: $BODY"
fi

# ── Characters that are legal but must be escaped ──────────────────────────
for probe in 'newline
inside' 'tab	inside' 'unicode ü — ✓' 'brace {"a":1} inside' 'backslash-only C:\x'; do
    run_hook "Claude Code" "$probe"
    if echo "$BODY" | jq -e . > /dev/null 2>&1 \
       && [ "$(echo "$BODY" | jq -r '.message')" = "$probe" ]; then
        pass "round-trips: $(printf '%s' "$probe" | tr '\n\t' '  ' | cut -c1-32)"
    else
        fail "failed to round-trip: $(printf '%s' "$probe" | tr '\n\t' '  ')"
    fi
done

# ── An empty message must still be a well-formed body, not an absent key ───
run_hook "Claude Code" ""
if [ "$(echo "$BODY" | jq -r '.message // "ABSENT"')" = "" ]; then
    pass "an empty message stays an empty string, not a missing key"
else
    fail "empty message did not survive: $BODY"
fi

# ── The instance label, which this hook had right before the fix ───────────
export TOMO_INSTANCE_NAME="tomo-instance"
run_hook "Claude Code" "plain"
unset TOMO_INSTANCE_NAME
TITLE_OUT=$(echo "$BODY" | jq -r '.title' 2>/dev/null)
case "$TITLE_OUT" in
    "[Tomo · tomo-instance] Claude Code") pass "instance label preserved in the title" ;;
    *) fail "instance label lost or malformed: [$TITLE_OUT]" ;;
esac

# ── The two smaller points folded into the same fix ────────────────────────
case "$ARGS" in
    *"--max-time"*) pass "curl is given a timeout" ;;
    *) fail "curl has no --max-time; a wedged bridge blocks the session" ;;
esac

if grep -q '> /dev/null' "$HOOK"; then
    pass "curl stdout is discarded rather than landing in hook output"
else
    fail "curl response body still reaches the hook's stdout"
fi

# ── The defect must not be able to come back ───────────────────────────────
if grep -q 'd "{\\"title' "$HOOK"; then
    fail "the interpolated body is back in the hook"
else
    pass "no interpolated JSON body remains in the hook"
fi

echo
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}All notify-bridge hook tests passed.${C_RESET}\n"
else
    printf "${C_RED}notify-bridge hook tests FAILED.${C_RESET}\n" >&2
fi
exit "$FAILED"
