#!/bin/bash
# test-005-phase3.sh — Acceptance tests for spec 005 Phase 3.
#   Covers: three-way classification fixtures (tracker+log_entry, atomic+log_link,
#   year-old cutoff, multi-date log, prose-with-dates, filename-with-time),
#   schema validation per fixture, structural assertions, Phase 1+2 regression.
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

# ── Ensure dependencies ──────────────────────────────────────────────────
if ! python3 -c "import yaml" 2>/dev/null; then
    VENV_DIR="${TMPDIR:-/tmp}/tomo-005-phase3-venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR" >/dev/null 2>&1
        "$VENV_DIR/bin/pip" install -q pyyaml >/dev/null 2>&1 || true
    fi
    PYTHON="$VENV_DIR/bin/python"
fi
printf "${C_DIM}python: %s${C_RESET}\n" "$PYTHON"

# ── Fixtures ─────────────────────────────────────────────────────────────
FIXTURE_SRC="$REPO_ROOT/scripts/fixtures/test-005-phase3"
FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-005-phase3-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR"

cp "$FIXTURE_SRC/"*.json "$FIXTURE_DIR/" 2>/dev/null || true

# ── Test 1: run-log → tracker(Sport) + log_entry, schema valid ───────────
printf "\n${C_DIM}── Test 1: run-log — tracker + log_entry${C_RESET}\n"
F1="$FIXTURE_DIR/run_log_tracker_plus_log_entry.json"
STDERR1="$FIXTURE_DIR/t1.log"
if "$PYTHON" "$REPO_ROOT/scripts/validate-result.py" --result "$F1" 2>"$STDERR1"; then
    pass "run-log: schema valid"
else
    fail "run-log: schema validation failed"
    cat "$STDERR1" >&2
fi

"$PYTHON" - "$F1" <<'PY' && pass "run-log: has tracker + log_entry in updates[]" || fail "run-log: wrong update kinds"
import json, sys
r = json.load(open(sys.argv[1]))
actions = r['actions']
assert len(actions) == 1, f'expected 1 action, got {len(actions)}'
ud = actions[0]
assert ud['kind'] == 'update_daily'
kinds = [u['kind'] for u in ud['updates']]
assert 'tracker' in kinds, f'missing tracker in {kinds}'
assert 'log_entry' in kinds, f'missing log_entry in {kinds}'
PY

"$PYTHON" - "$F1" <<'PY' && pass "run-log: tracker has confidence + reason" || fail "run-log: tracker missing confidence/reason"
import json, sys
r = json.load(open(sys.argv[1]))
tracker = next(u for u in r['actions'][0]['updates'] if u['kind'] == 'tracker')
assert 'confidence' in tracker and isinstance(tracker['confidence'], (int, float)), 'missing confidence'
assert 'reason' in tracker and len(tracker['reason']) <= 80, f'reason missing or too long ({len(tracker.get("reason",""))})'
PY

"$PYTHON" - "$F1" <<'PY' && pass "run-log: log_entry has time + time_source from filename" || fail "run-log: log_entry missing time fields"
import json, sys
r = json.load(open(sys.argv[1]))
le = next(u for u in r['actions'][0]['updates'] if u['kind'] == 'log_entry')
assert le['time'] == '07:00', f'time={le["time"]!r}'
assert le['time_source'] == 'filename', f'time_source={le["time_source"]!r}'
PY

# ── Test 2: reading-notes → atomic + log_link (NOT log_entry) ───────────
printf "\n${C_DIM}── Test 2: reading-notes — atomic + log_link${C_RESET}\n"
F2="$FIXTURE_DIR/reading_notes_atomic_plus_log_link.json"
STDERR2="$FIXTURE_DIR/t2.log"
if "$PYTHON" "$REPO_ROOT/scripts/validate-result.py" --result "$F2" 2>"$STDERR2"; then
    pass "reading-notes: schema valid"
else
    fail "reading-notes: schema validation failed"
    cat "$STDERR2" >&2
fi

"$PYTHON" - "$F2" <<'PY' && pass "reading-notes: create_atomic_note + update_daily with log_link" || fail "reading-notes: wrong action structure"
import json, sys
r = json.load(open(sys.argv[1]))
action_kinds = [a['kind'] for a in r['actions']]
assert 'create_atomic_note' in action_kinds, f'missing create_atomic_note in {action_kinds}'
assert 'update_daily' in action_kinds, f'missing update_daily in {action_kinds}'
ud = next(a for a in r['actions'] if a['kind'] == 'update_daily')
update_kinds = [u['kind'] for u in ud['updates']]
assert 'log_link' in update_kinds, f'expected log_link, got {update_kinds}'
assert 'log_entry' not in update_kinds, f'log_entry must NOT coexist with create_atomic_note'
PY

"$PYTHON" - "$F2" <<'PY' && pass "reading-notes: log_link has target_stem + reason" || fail "reading-notes: log_link missing fields"
import json, sys
r = json.load(open(sys.argv[1]))
ud = next(a for a in r['actions'] if a['kind'] == 'update_daily')
ll = next(u for u in ud['updates'] if u['kind'] == 'log_link')
assert 'target_stem' in ll and len(ll['target_stem']) > 0, 'missing target_stem'
assert 'reason' in ll and len(ll['reason']) <= 80, f'reason missing or too long'
PY

# ── Test 3: year-old item → zero update_daily, atomic still present ──────
printf "\n${C_DIM}── Test 3: year-old item — no update_daily${C_RESET}\n"
F3="$FIXTURE_DIR/year_old_no_daily.json"
STDERR3="$FIXTURE_DIR/t3.log"
if "$PYTHON" "$REPO_ROOT/scripts/validate-result.py" --result "$F3" 2>"$STDERR3"; then
    pass "year-old: schema valid"
else
    fail "year-old: schema validation failed"
    cat "$STDERR3" >&2
fi

"$PYTHON" - "$F3" <<'PY' && pass "year-old: zero update_daily actions, atomic note present" || fail "year-old: wrong actions"
import json, sys
r = json.load(open(sys.argv[1]))
action_kinds = [a['kind'] for a in r['actions']]
assert 'update_daily' not in action_kinds, f'update_daily must not appear for year-old item, got {action_kinds}'
assert 'create_atomic_note' in action_kinds, f'create_atomic_note must still be present'
PY

# ── Test 4: multi-date log → 3 separate update_daily actions ────────────
printf "\n${C_DIM}── Test 4: multi-date log — N update_daily actions${C_RESET}\n"
F4="$FIXTURE_DIR/multi_date_log.json"
STDERR4="$FIXTURE_DIR/t4.log"
if "$PYTHON" "$REPO_ROOT/scripts/validate-result.py" --result "$F4" 2>"$STDERR4"; then
    pass "multi-date: schema valid"
else
    fail "multi-date: schema validation failed"
    cat "$STDERR4" >&2
fi

"$PYTHON" - "$F4" <<'PY' && pass "multi-date: 3 update_daily actions with distinct dates" || fail "multi-date: wrong action count or dates"
import json, sys
r = json.load(open(sys.argv[1]))
ud_actions = [a for a in r['actions'] if a['kind'] == 'update_daily']
assert len(ud_actions) == 3, f'expected 3 update_daily, got {len(ud_actions)}'
dates = sorted(a['date'] for a in ud_actions)
assert dates == ['2026-03-10', '2026-03-13', '2026-03-15'], f'dates={dates}'
PY

"$PYTHON" - "$F4" <<'PY' && pass "multi-date: each action has log_entry with reason" || fail "multi-date: updates missing log_entry or reason"
import json, sys
r = json.load(open(sys.argv[1]))
for a in r['actions']:
    if a['kind'] != 'update_daily':
        continue
    assert len(a['updates']) >= 1, f'empty updates for date={a["date"]}'
    for u in a['updates']:
        assert u['kind'] == 'log_entry', f'expected log_entry, got {u["kind"]}'
        assert 'reason' in u and len(u['reason']) <= 80, f'reason missing or too long for date={a["date"]}'
PY

# ── Test 5: prose with dates → single update_daily at most-recent date ──
printf "\n${C_DIM}── Test 5: prose with dates — single most-recent date${C_RESET}\n"
F5="$FIXTURE_DIR/prose_with_dates.json"
STDERR5="$FIXTURE_DIR/t5.log"
if "$PYTHON" "$REPO_ROOT/scripts/validate-result.py" --result "$F5" 2>"$STDERR5"; then
    pass "prose-dates: schema valid"
else
    fail "prose-dates: schema validation failed"
    cat "$STDERR5" >&2
fi

"$PYTHON" - "$F5" <<'PY' && pass "prose-dates: exactly 1 update_daily at 2026-03-17" || fail "prose-dates: wrong date or count"
import json, sys
r = json.load(open(sys.argv[1]))
ud_actions = [a for a in r['actions'] if a['kind'] == 'update_daily']
assert len(ud_actions) == 1, f'expected 1 update_daily, got {len(ud_actions)}'
assert ud_actions[0]['date'] == '2026-03-17', f'date={ud_actions[0]["date"]}'
PY

# ── Test 6: filename with time → log_entry has time + time_source ───────
printf "\n${C_DIM}── Test 6: filename with time — time extraction${C_RESET}\n"
F6="$FIXTURE_DIR/filename_with_time.json"
STDERR6="$FIXTURE_DIR/t6.log"
if "$PYTHON" "$REPO_ROOT/scripts/validate-result.py" --result "$F6" 2>"$STDERR6"; then
    pass "filename-time: schema valid"
else
    fail "filename-time: schema validation failed"
    cat "$STDERR6" >&2
fi

"$PYTHON" - "$F6" <<'PY' && pass "filename-time: time=07:00 and time_source=filename" || fail "filename-time: wrong time fields"
import json, sys
r = json.load(open(sys.argv[1]))
ud = next(a for a in r['actions'] if a['kind'] == 'update_daily')
le = next(u for u in ud['updates'] if u['kind'] == 'log_entry')
assert le['time'] == '07:00', f'time={le["time"]!r}'
assert le['time_source'] == 'filename', f'time_source={le["time_source"]!r}'
PY

# ── Test 7: all fixtures have reason ≤80 chars on every update entry ─────
printf "\n${C_DIM}── Test 7: all fixtures — reason ≤80 chars on every update${C_RESET}\n"
"$PYTHON" - "$FIXTURE_DIR" <<'PY' && pass "all fixtures: every update entry has reason ≤80 chars" || fail "some fixtures missing reason or too long"
import json, sys, os, glob
fixture_dir = sys.argv[1]
for fp in sorted(glob.glob(os.path.join(fixture_dir, '*.json'))):
    r = json.load(open(fp))
    for ai, a in enumerate(r.get('actions', [])):
        if a['kind'] != 'update_daily':
            continue
        for ui, u in enumerate(a.get('updates', [])):
            fn = os.path.basename(fp)
            assert 'reason' in u, f'{fn} actions[{ai}].updates[{ui}] missing reason'
            assert len(u['reason']) <= 80, f'{fn} actions[{ai}].updates[{ui}] reason too long ({len(u["reason"])})'
PY

# ── Test 8: Spec-005 Phase 1+2 regression ────────────────────────────────
printf "\n${C_DIM}── Test 8a: spec-005 phase 1 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase1.sh" >/dev/null 2>&1; then
    pass "test-005-phase1.sh passes"
else
    fail "test-005-phase1.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase1.sh" >&2 || true
fi

printf "\n${C_DIM}── Test 8b: spec-005 phase 2 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase2.sh" >/dev/null 2>&1; then
    pass "test-005-phase2.sh passes"
else
    fail "test-005-phase2.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase2.sh" >&2 || true
fi

# ── Test 9: Spec-004 regression ──────────────────────────────────────────
printf "\n${C_DIM}── Test 9: spec-004 phase 3 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-004-phase3.sh" >/dev/null 2>&1; then
    pass "test-004-phase3.sh passes"
else
    fail "test-004-phase3.sh regression failure"
    bash "$REPO_ROOT/scripts/test-004-phase3.sh" >&2 || true
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 3 (spec 005) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 3 (spec 005) tests FAILED${C_RESET}\n"
    exit 1
fi
