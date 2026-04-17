#!/bin/bash
# test-005-phase2.sh — Acceptance tests for spec 005 Plan Phase 2.
#   Covers: tracker descriptions + keyword passthrough, daily_log defaults,
#           auto_create_if_missing forced to false, real-instance budget,
#           daily-disabled regression guard.
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

# ── Ensure PyYAML is available ─────────────────────────────────────────────
if ! python3 -c "import yaml" 2>/dev/null; then
    VENV_DIR="${TMPDIR:-/tmp}/tomo-004-phase2-venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR" >/dev/null 2>&1
        "$VENV_DIR/bin/pip" install -q pyyaml >/dev/null 2>&1 || true
    fi
    PYTHON="$VENV_DIR/bin/python"
else
    PYTHON="python3"
fi
printf "${C_DIM}python: %s${C_RESET}\n" "$PYTHON"

# ── Fixtures ───────────────────────────────────────────────────────────────
FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-005-phase2-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/config" "$FIXTURE_DIR/tomo-tmp"

# Minimal discovery cache (reused across all fixture tests)
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

# ── Test 1: tracker descriptions + keyword passthrough ────────────────────
# 3 trackers: full desc+keywords, desc-only, no desc at all
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
STDERR1="$FIXTURE_DIR/tomo-tmp/shared-ctx-trackers.err"
if "$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-trackers.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-trackers" \
    --output "$OUT1" 2>"$STDERR1"; then
    pass "tracker fixture: builder exits 0"
else
    fail "tracker fixture: builder failed"
fi

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: all 3 fields present" || fail "tracker fixture: fields count"
import json, sys
ctx = json.load(open(sys.argv[1]))
tf = ctx['daily_notes']['tracker_fields']
assert len(tf) == 3, f'expected 3 tracker_fields, got {len(tf)}: {[f["name"] for f in tf]}'
PY

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: WakeUpEnergy has full desc + keywords" || fail "tracker fixture: WakeUpEnergy"
import json, sys
ctx = json.load(open(sys.argv[1]))
wu = next(f for f in ctx['daily_notes']['tracker_fields'] if f['name'] == 'WakeUpEnergy')
assert wu['description'] == 'Energy level on waking up, rated 1-5', f'bad desc: {wu["description"]!r}'
assert wu['type'] == 'rating_1_5'
assert 'energized' in wu['positive_keywords'], f'missing: {wu["positive_keywords"]}'
assert 'tired' in wu['negative_keywords'], f'missing: {wu["negative_keywords"]}'
assert 'wake' in wu['keywords']
PY

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: Sport has desc + empty negative_keywords" || fail "tracker fixture: Sport"
import json, sys
ctx = json.load(open(sys.argv[1]))
sp = next(f for f in ctx['daily_notes']['tracker_fields'] if f['name'] == 'Sport')
assert sp['description'] == 'Did any physical exercise today'
assert 'gym' in sp['positive_keywords']
assert sp['negative_keywords'] == []
PY

"$PYTHON" - "$OUT1" <<'PY' && pass "tracker fixture: DayEnergy has empty description" || fail "tracker fixture: DayEnergy empty desc"
import json, sys
ctx = json.load(open(sys.argv[1]))
de = next(f for f in ctx['daily_notes']['tracker_fields'] if f['name'] == 'DayEnergy')
assert de['description'] == '', f'expected empty string, got {de["description"]!r}'
assert de['positive_keywords'] == []
assert de['negative_keywords'] == []
PY

# WARN for missing description must appear in stderr
if grep -q "WARN:.*DayEnergy" "$STDERR1"; then
    pass "tracker fixture: WARN emitted for DayEnergy (no description)"
else
    fail "tracker fixture: missing WARN for DayEnergy"
fi

# ── Test 2: daily_log absent → defaults applied ───────────────────────────
cat > "$FIXTURE_DIR/config/vault-config-no-daily-log.yaml" <<'YAML'
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
    --vault-config "$FIXTURE_DIR/config/vault-config-no-daily-log.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-no-dl" \
    --output "$OUT2" 2>/dev/null

"$PYTHON" - "$OUT2" <<'PY' && pass "no daily_log in vault-config → defaults applied" || fail "no daily_log → defaults"
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
assert dl['auto_create_if_missing'] == {'past': False, 'today': False, 'future': False}
PY

# ── Test 3: auto_create_if_missing.today=true → forced false + warning ────
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
STDERR3="$FIXTURE_DIR/tomo-tmp/shared-ctx-acim.err"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-acim.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-acim" \
    --output "$OUT3" 2>"$STDERR3"

"$PYTHON" - "$OUT3" <<'PY' && pass "auto_create_if_missing.today forced to false in output" || fail "auto_create_if_missing not forced to false"
import json, sys
ctx = json.load(open(sys.argv[1]))
dl = ctx['daily_notes']['daily_log']
acim = dl['auto_create_if_missing']
assert acim['today'] is False, f'today={acim["today"]!r}'
assert acim['past'] is False, f'past={acim["past"]!r}'
assert acim['future'] is False, f'future={acim["future"]!r}'
# Other fields from vault-config were preserved
assert dl['heading_level'] == 2
assert dl['cutoff_days'] == 60
PY

if grep -q "WARN:.*auto_create_if_missing forced" "$STDERR3"; then
    pass "auto_create_if_missing.today=true → WARN emitted"
else
    fail "auto_create_if_missing: missing WARN in stderr"
fi

# ── Test 4: daily disabled → no daily_notes section at all ──────────────
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

OUT4="$FIXTURE_DIR/tomo-tmp/shared-ctx-no-daily.json"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-no-daily.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-005-p2-no-daily" \
    --output "$OUT4" 2>/dev/null

"$PYTHON" - "$OUT4" <<'PY' && pass "calendar.daily.enabled=false → no daily_notes block (regression guard)" || fail "daily disabled: daily_notes still present"
import json, sys
ctx = json.load(open(sys.argv[1]))
assert 'daily_notes' not in ctx, f'daily_notes must be absent when disabled, keys={list(ctx.keys())}'
PY

# ── Test 5: real-instance dry run ≤ 15 KB ────────────────────────────────
if [ -f "$REPO_ROOT/tomo-instance/config/discovery-cache.yaml" ]; then
    REAL_OUT="$FIXTURE_DIR/tomo-tmp/real-shared-ctx.json"
    REAL_ERR="$FIXTURE_DIR/tomo-tmp/real.err"
    if "$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
        --cache "$REPO_ROOT/tomo-instance/config/discovery-cache.yaml" \
        --vault-config "$REPO_ROOT/tomo-instance/config/vault-config.yaml" \
        --profiles-dir "$REPO_ROOT/tomo/profiles" \
        --run-id "test-005-p2-real" \
        --output "$REAL_OUT" 2>"$REAL_ERR"; then
        SIZE=$(wc -c < "$REAL_OUT" | tr -d ' ')
        if [ "$SIZE" -le 15360 ]; then
            pass "real-instance: shared-ctx ≤ 15 KB (size=${SIZE}B)"
        else
            fail "real-instance: shared-ctx over budget: ${SIZE}B > 15360"
        fi
        N_TF=$("$PYTHON" - "$REAL_OUT" <<'PY'
import json, sys
ctx = json.load(open(sys.argv[1]))
print(len(ctx.get('daily_notes', {}).get('tracker_fields', [])))
PY
        )
        printf "  ${C_DIM}real-instance: tracker_fields=%s daily_log_present=%s${C_RESET}\n" \
            "$N_TF" \
            "$("$PYTHON" - "$REAL_OUT" <<'PY'
import json, sys
ctx = json.load(open(sys.argv[1]))
print('yes' if 'daily_log' in ctx.get('daily_notes', {}) else 'no')
PY
            )"
    else
        fail "real-instance: builder failed"
        cat "$REAL_ERR" >&2
    fi
else
    skip "real-instance dry run" "tomo-instance not set up"
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 2 (spec 005) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 2 (spec 005) tests FAILED${C_RESET}\n"
    exit 1
fi
