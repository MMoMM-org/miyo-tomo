#!/bin/bash
# test-005-phase4.sh — Acceptance tests for spec 005 Phase 4.
#   Covers: 2 daily notes → 2 blocks date-sorted; missing daily note →
#   Create-first checkbox; log_link → mirror in top-of-doc AND per-item;
#   empty trackers → Trackers header omitted; Phase 1-3 regression.
# version: 0.1.0
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ -t 1 ]; then
    C_RESET="\033[0m"; C_GREEN="\033[32m"; C_RED="\033[31m"; C_YELLOW="\033[33m"; C_DIM="\033[2m"
else
    C_RESET=""; C_GREEN=""; C_RED=""; C_YELLOW=""; C_DIM=""
fi
pass() { printf "  ${C_GREEN}✓${C_RESET} %s\n" "$1"; }
fail() { printf "  ${C_RED}✗${C_RESET} %s\n" "$1" >&2; FAILED=1; }
skip() { printf "  ${C_YELLOW}⊘${C_RESET} %s ${C_DIM}(%s)${C_RESET}\n" "$1" "$2"; }
FAILED=0

PYTHON="python3"

# ── Fixtures ─────────────────────────────────────────────────────────────
FIXTURE_SRC="$REPO_ROOT/scripts/fixtures/test-005-phase4"
FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-005-phase4-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/items"

STATE="$FIXTURE_DIR/state.jsonl"
ITEMS_DIR="$FIXTURE_DIR/items"
OUT_DOC="$FIXTURE_DIR/suggestions-doc.json"

# Seed state with 3 done items
cat > "$STATE" <<JSONL
{"run_id":"test-phase4","stem":"reading-notes","path":"100 Inbox/reading-notes.md","status":"done","attempts":1,"started_at":null,"completed_at":null,"error":null}
{"run_id":"test-phase4","stem":"run-log","path":"100 Inbox/run-log.md","status":"done","attempts":1,"started_at":null,"completed_at":null,"error":null}
{"run_id":"test-phase4","stem":"workout-notes","path":"100 Inbox/workout-notes.md","status":"done","attempts":1,"started_at":null,"completed_at":null,"error":null}
JSONL

cp "$FIXTURE_SRC/reading_notes_atomic_log_link.json" "$ITEMS_DIR/reading-notes.result.json"
cp "$FIXTURE_SRC/run_log_tracker_log_entry.json"      "$ITEMS_DIR/run-log.result.json"
cp "$FIXTURE_SRC/workout_notes_log_entry_next_day.json" "$ITEMS_DIR/workout-notes.result.json"

# ── Run reducer ───────────────────────────────────────────────────────────
printf "\n${C_DIM}── Running reducer${C_RESET}\n"
STDERR_R="$FIXTURE_DIR/reducer.log"
if "$PYTHON" "$REPO_ROOT/scripts/suggestions-reducer.py" \
    --state "$STATE" \
    --items-dir "$ITEMS_DIR" \
    --run-id test-phase4 \
    --profile miyo \
    --output "$OUT_DOC" \
    --shared-ctx /dev/null \
    2>"$STDERR_R"; then
    pass "reducer exits 0"
else
    fail "reducer exited non-zero"
    cat "$STDERR_R" >&2
    exit 1
fi

# ── Test 1: 2 daily notes, date-sorted ───────────────────────────────────
printf "\n${C_DIM}── Test 1: 2 daily_notes_updates entries, date-sorted + structure${C_RESET}\n"
STDERR1="$FIXTURE_DIR/t1.log"
if "$PYTHON" "$FIXTURE_SRC/assert_daily_notes_render.py" "$OUT_DOC" 2>"$STDERR1"; then
    pass "2 daily notes sorted + Material für mirror + precedence note"
else
    fail "daily_notes_updates structure assertions failed"
    cat "$STDERR1" >&2
fi

# ── Test 2: exists=false → Create-first checkbox; empty trackers omitted ─
printf "\n${C_DIM}── Test 2: render rules — Create-first, header omission, null time${C_RESET}\n"
STDERR2="$FIXTURE_DIR/t2.log"
if "$PYTHON" "$FIXTURE_SRC/assert_render_rules.py" \
    "$REPO_ROOT/scripts/suggestions-reducer.py" \
    2>"$STDERR2"; then
    pass "exists=false → Create-first; empty trackers omitted; null time → end of day"
else
    fail "render-rule assertions failed"
    cat "$STDERR2" >&2
fi

# ── Test 3: log_link mirror in both top-of-doc AND per-item ──────────────
printf "\n${C_DIM}── Test 3: log_link mirror in top-of-doc AND per-item section${C_RESET}\n"
STDERR3="$FIXTURE_DIR/t3.log"
"$PYTHON" - "$OUT_DOC" <<'PY' 2>"$STDERR3" && pass "log_link appears in daily_notes_updates AND per-item rendered_md" || { fail "log_link mirror check failed"; cat "$STDERR3" >&2; }
import json, sys
doc = json.load(open(sys.argv[1]))

# Top-of-doc: 2026-04-15 should have log_links
dnu = doc["daily_notes_updates"]
d0 = next(d for d in dnu if d["daily_note_stem"] == "2026-04-15")
assert len(d0["log_links"]) >= 1, f"no log_links in top-of-doc for 2026-04-15"

# Per-item: reading-notes create_atomic_note rendered_md should have Material für
reading_sec = next(s for s in doc["sections"] if s["stem"] == "reading-notes")
atomic = next(a for a in reading_sec["actions"] if a["kind"] == "create_atomic_note")
assert "Material für" in atomic["rendered_md"], \
    f"Material für not in per-item section for reading-notes"
PY

# ── Test 4: empty trackers → Trackers header omitted in rendered block ────
printf "\n${C_DIM}── Test 4: empty trackers → Trackers header omitted${C_RESET}\n"
STDERR4="$FIXTURE_DIR/t4.log"
"$PYTHON" - "$OUT_DOC" "$REPO_ROOT/scripts/suggestions-reducer.py" <<'PY' 2>"$STDERR4" && pass "workout-notes (no trackers) renders without Trackers header" || { fail "tracker-omission check failed"; cat "$STDERR4" >&2; }
import json, sys, importlib.util
doc = json.load(open(sys.argv[1]))

# Load renderer
spec = importlib.util.spec_from_file_location("reducer", sys.argv[2])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Render only the 2026-04-16 entry (workout-notes, no trackers)
d1 = next(d for d in doc["daily_notes_updates"] if d["daily_note_stem"] == "2026-04-16")
rendered = mod.render_daily_notes_updates_block([d1])
assert "Possible Trackers" not in rendered, \
    f"Possible Trackers header should be absent for 2026-04-16:\n{rendered[:400]}"
assert "Possible Log Entries" in rendered, \
    f"Possible Log Entries missing for 2026-04-16:\n{rendered[:400]}"
PY

# ── Test 5: decision_precedence_note present in doc ───────────────────────
printf "\n${C_DIM}── Test 5: decision_precedence_note in suggestions-doc.json${C_RESET}\n"
STDERR5="$FIXTURE_DIR/t5.log"
"$PYTHON" - "$OUT_DOC" <<'PY' 2>"$STDERR5" && pass "decision_precedence_note present and non-empty" || { fail "decision_precedence_note check failed"; cat "$STDERR5" >&2; }
import json, sys
doc = json.load(open(sys.argv[1]))
assert "decision_precedence_note" in doc, "decision_precedence_note missing"
assert len(doc["decision_precedence_note"]) > 10, "decision_precedence_note too short"
PY

# ── Test 6: spec-005 Phase 1-3 regression ────────────────────────────────
printf "\n${C_DIM}── Test 6a: spec-005 phase 1 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase1.sh" >/dev/null 2>&1; then
    pass "test-005-phase1.sh passes"
else
    fail "test-005-phase1.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase1.sh" >&2 || true
fi

printf "\n${C_DIM}── Test 6b: spec-005 phase 3 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase3.sh" >/dev/null 2>&1; then
    pass "test-005-phase3.sh passes"
else
    fail "test-005-phase3.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase3.sh" >&2 || true
fi

# ── Test 7: spec-004 regression ──────────────────────────────────────────
printf "\n${C_DIM}── Test 7: spec-004 phase 3 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-004-phase3.sh" >/dev/null 2>&1; then
    pass "test-004-phase3.sh passes"
else
    fail "test-004-phase3.sh regression failure"
    bash "$REPO_ROOT/scripts/test-004-phase3.sh" >&2 || true
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 4 (spec 005) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 4 (spec 005) tests FAILED${C_RESET}\n"
    exit 1
fi
