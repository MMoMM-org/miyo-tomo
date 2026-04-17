#!/bin/bash
# test-005-phase2.sh — Acceptance tests for spec 005 Phase 2.
#   Covers: tracker description/keyword passthrough, daily_log defaults, MVP
#   auto_create forcing, real-instance budget check, daily-disabled guard,
#   Spec-004 + Phase-1 regression.
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

# ── Ensure PyYAML is available ─────────────────────────────────────────────
if ! python3 -c "import yaml" 2>/dev/null; then
    VENV_DIR="${TMPDIR:-/tmp}/tomo-005-phase2-venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR" >/dev/null 2>&1
        "$VENV_DIR/bin/pip" install -q pyyaml >/dev/null 2>&1 || true
    fi
    PYTHON="$VENV_DIR/bin/python"
fi
printf "${C_DIM}python: %s${C_RESET}\n" "$PYTHON"

# ── Fixtures ───────────────────────────────────────────────────────────────
FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-005-phase2-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/config" "$FIXTURE_DIR/tomo-tmp"

# Minimal discovery cache — reused across all fixture tests
cat > "$FIXTURE_DIR/config/discovery-cache.yaml" <<'YAML'
cache_version: 1
last_scan: '2026-04-14T00:00:00Z'
vault_structure:
  total_notes: 5
map_notes:
  - path: Atlas/200 Maps/Health (MOC).md
    title: Health (MOC)
    topics: [health, habits, fitness]
tag_taxonomy:
  prefixes:
    topic:
      wildcard: true
      known_values: [personal/habits]
YAML

# ── Test 1: tracker description + keyword passthrough ─────────────────────
# 3 trackers: (a) full desc+pos+neg+extra_keywords, (b) desc only, (c) no desc
printf "\n${C_DIM}── Test 1: tracker descriptions + keyword passthrough${C_RESET}\n"
cat > "$FIXTURE_DIR/config/vault-config-trackers.yaml" <<'YAML'
schema_version: 1
profile: miyo
concepts:
  inbox: "100 Inbox/"
  calendar:
    granularities:
      daily:
        enabled: true
        path: "Calendar/301 Daily/"
naming:
  calendar_patterns:
    daily: "YYYY-MM-DD"
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
trackers:
  daily_note_trackers:
    section: "Habit"
    yesterday_fields: []
    today_fields:
      - name: "WakeUpEnergy"
        type: integer
        scale: "1-5"
        description: "Energy level on waking up, rated 1-5"
        keywords: ["wake", "energy", "morning"]
        positive_keywords: ["energized", "refreshed", "alert"]
        negative_keywords: ["tired", "groggy", "sluggish"]
      - name: "Sport"
        type: boolean
        description: "Did any physical exercise today"
        positive_keywords: ["gym", "run", "workout"]
        negative_keywords: []
  end_of_day_fields:
    section: "End of the Day"
    fields:
      - name: "DayEnergy"
        type: integer
        scale: "1-5"
YAML

OUT1="$FIXTURE_DIR/tomo-tmp/shared-ctx-trackers.json"
STDERR1="$FIXTURE_DIR/tomo-tmp/t1.err"
if "$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-trackers.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-t1" \
    --output "$OUT1" 2>"$STDERR1"; then
    pass "tracker fixture: builder exits 0"
else
    fail "tracker fixture: builder failed"
    cat "$STDERR1" >&2
fi

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: all 3 fields present" || fail "tracker fixture: all 3 fields present"
import json, sys
ctx = json.load(open(sys.argv[1]))
tf = ctx['daily_notes']['tracker_fields']
assert len(tf) == 3, f'expected 3, got {len(tf)}: {[f["name"] for f in tf]}'
PY

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: WakeUpEnergy — full desc + pos + neg keywords" || fail "tracker fixture: WakeUpEnergy"
import json, sys
ctx = json.load(open(sys.argv[1]))
wu = next(f for f in ctx['daily_notes']['tracker_fields'] if f['name'] == 'WakeUpEnergy')
assert wu['description'] == 'Energy level on waking up, rated 1-5', f'desc={wu["description"]!r}'
assert wu['type'] == 'rating_1_5'
assert 'energized' in wu['positive_keywords'], f'pos_kw={wu["positive_keywords"]}'
assert 'tired' in wu['negative_keywords'], f'neg_kw={wu["negative_keywords"]}'
assert 'wake' in wu['keywords'], f'kw={wu["keywords"]}'
PY

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: Sport — desc present, negative_keywords empty" || fail "tracker fixture: Sport"
import json, sys
ctx = json.load(open(sys.argv[1]))
sp = next(f for f in ctx['daily_notes']['tracker_fields'] if f['name'] == 'Sport')
assert sp['description'] == 'Did any physical exercise today', f'desc={sp["description"]!r}'
assert 'gym' in sp['positive_keywords'], f'pos_kw={sp["positive_keywords"]}'
assert sp['negative_keywords'] == [], f'neg_kw={sp["negative_keywords"]}'
PY

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: DayEnergy — empty description (missing desc)" || fail "tracker fixture: DayEnergy empty desc"
import json, sys
ctx = json.load(open(sys.argv[1]))
de = next(f for f in ctx['daily_notes']['tracker_fields'] if f['name'] == 'DayEnergy')
assert de['description'] == '', f'expected empty string, got {de["description"]!r}'
assert de['positive_keywords'] == []
assert de['negative_keywords'] == []
PY

if grep -q "WARN:.*DayEnergy" "$STDERR1"; then
    pass "tracker fixture: WARN emitted for missing description (DayEnergy)"
else
    fail "tracker fixture: WARN not emitted for missing description"
fi

# ── Test 2: daily_log absent in vault-config → defaults applied ───────────
printf "\n${C_DIM}── Test 2: daily_log absent → sane defaults${C_RESET}\n"
cat > "$FIXTURE_DIR/config/vault-config-no-dl.yaml" <<'YAML'
schema_version: 1
profile: miyo
concepts:
  inbox: "100 Inbox/"
  calendar:
    granularities:
      daily:
        enabled: true
        path: "Calendar/301 Daily/"
naming:
  calendar_patterns:
    daily: "YYYY-MM-DD"
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
YAML

OUT2="$FIXTURE_DIR/tomo-tmp/shared-ctx-no-dl.json"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-no-dl.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-t2" \
    --output "$OUT2" 2>/dev/null

"$PYTHON" - "$OUT2" <<'PY' && pass "daily_log absent → defaults: section, heading_level=1, cutoff_days=30, all auto_create false" || fail "daily_log absent → defaults"
import json, sys
ctx = json.load(open(sys.argv[1]))
dl = ctx['daily_notes']['daily_log']
assert dl['section'] == 'Daily Log', f'section={dl["section"]!r}'
assert dl['heading_level'] == 1, f'heading_level={dl["heading_level"]}'
assert dl['link_format'] == 'bullet', f'link_format={dl["link_format"]!r}'
assert dl['cutoff_days'] == 30, f'cutoff_days={dl["cutoff_days"]}'
assert dl['time_extraction']['enabled'] is True
assert dl['time_extraction']['sources'] == ['content', 'filename']
assert dl['time_extraction']['fallback'] == 'append_end_of_day'
assert dl['auto_create_if_missing'] == {'past': False, 'today': False, 'future': False}, \
    f'acim={dl["auto_create_if_missing"]}'
PY

# ── Test 3: auto_create_if_missing.today=true → forced false + WARN ───────
printf "\n${C_DIM}── Test 3: auto_create_if_missing.today=true → forced false${C_RESET}\n"
cat > "$FIXTURE_DIR/config/vault-config-acim.yaml" <<'YAML'
schema_version: 1
profile: miyo
concepts:
  inbox: "100 Inbox/"
  calendar:
    granularities:
      daily:
        enabled: true
        path: "Calendar/301 Daily/"
naming:
  calendar_patterns:
    daily: "YYYY-MM-DD"
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
daily_log:
  section: "Daily Log"
  heading_level: 2
  time_extraction:
    enabled: true
    sources: ["content", "filename"]
    fallback: "append_end_of_day"
  link_format: "bullet"
  cutoff_days: 60
  auto_create_if_missing:
    past: false
    today: true
    future: false
YAML

OUT3="$FIXTURE_DIR/tomo-tmp/shared-ctx-acim.json"
STDERR3="$FIXTURE_DIR/tomo-tmp/t3.err"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-acim.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-t3" \
    --output "$OUT3" 2>"$STDERR3"

"$PYTHON" - "$OUT3" <<'PY' && pass "auto_create_if_missing.today forced to false; other daily_log fields preserved" || fail "auto_create_if_missing not forced to false"
import json, sys
ctx = json.load(open(sys.argv[1]))
dl = ctx['daily_notes']['daily_log']
acim = dl['auto_create_if_missing']
assert acim['today'] is False, f'today={acim["today"]!r}'
assert acim['past'] is False, f'past={acim["past"]!r}'
assert acim['future'] is False, f'future={acim["future"]!r}'
assert dl['heading_level'] == 2, f'heading_level={dl["heading_level"]}'
assert dl['cutoff_days'] == 60, f'cutoff_days={dl["cutoff_days"]}'
PY

if grep -q "WARN:.*auto_create_if_missing forced" "$STDERR3"; then
    pass "auto_create_if_missing.today=true → WARN emitted in stderr"
else
    fail "auto_create_if_missing: WARN not emitted in stderr"
    cat "$STDERR3" >&2
fi

# ── Test 4: real-instance dry run ≤ 15 KB ────────────────────────────────
printf "\n${C_DIM}── Test 4: real-instance dry run ≤ 15 KB${C_RESET}\n"
if [ -f "$REPO_ROOT/tomo-instance/config/discovery-cache.yaml" ]; then
    REAL_OUT="$FIXTURE_DIR/tomo-tmp/real-shared-ctx.json"
    REAL_ERR="$FIXTURE_DIR/tomo-tmp/t4-real.err"
    if "$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
        --cache "$REPO_ROOT/tomo-instance/config/discovery-cache.yaml" \
        --vault-config "$REPO_ROOT/tomo-instance/config/vault-config.yaml" \
        --profiles-dir "$REPO_ROOT/tomo/profiles" \
        --run-id "test-005-p2-real" \
        --output "$REAL_OUT" 2>"$REAL_ERR"; then
        SIZE=$(wc -c < "$REAL_OUT" | tr -d ' ')
        if [ "$SIZE" -le 15360 ]; then
            pass "real-instance: shared-ctx ≤ 15 KB (${SIZE}B)"
        else
            fail "real-instance: over budget — ${SIZE}B > 15360"
        fi
    else
        fail "real-instance: builder exited non-zero"
        cat "$REAL_ERR" >&2
    fi
else
    skip "real-instance dry run" "tomo-instance not set up"
fi

# ── Test 5: calendar.daily.enabled=false → no daily_notes block ──────────
printf "\n${C_DIM}── Test 5: calendar.daily.enabled=false → daily_notes omitted${C_RESET}\n"
cat > "$FIXTURE_DIR/config/vault-config-no-daily.yaml" <<'YAML'
schema_version: 1
profile: miyo
concepts:
  inbox: "100 Inbox/"
  calendar:
    granularities:
      daily:
        enabled: false
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
YAML

OUT5="$FIXTURE_DIR/tomo-tmp/shared-ctx-no-daily.json"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-no-daily.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-t5" \
    --output "$OUT5" 2>/dev/null

"$PYTHON" - "$OUT5" <<'PY' && pass "calendar.daily.enabled=false → daily_notes absent (regression guard)" || fail "calendar.daily.enabled=false → daily_notes still present"
import json, sys
ctx = json.load(open(sys.argv[1]))
assert 'daily_notes' not in ctx, f'daily_notes must be absent; keys={list(ctx.keys())}'
PY

# ── Test 6: Spec-004 regression ────────────────────────────────────────────
printf "\n${C_DIM}── Test 6: spec-004 phase 2 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-004-phase2.sh" >/dev/null 2>&1; then
    pass "test-004-phase2.sh passes"
else
    fail "test-004-phase2.sh regression failure"
    bash "$REPO_ROOT/scripts/test-004-phase2.sh" >&2 || true
fi

# ── Test 7: Phase-1 regression ─────────────────────────────────────────────
printf "\n${C_DIM}── Test 7: spec-005 phase 1 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase1.sh" >/dev/null 2>&1; then
    pass "test-005-phase1.sh passes"
else
    fail "test-005-phase1.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase1.sh" >&2 || true
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 2 (spec 005) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 2 (spec 005) tests FAILED${C_RESET}\n"
    exit 1
fi
