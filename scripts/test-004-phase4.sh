#!/bin/bash
# test-004-phase4.sh — Acceptance tests for spec 004 Plan Phase 4.
#   Covers: shared-ctx tracker_fields population, reducer rendering of
#           update_daily actions, multi-action per section.
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

# PyYAML venv (reuse phase 2 venv if present)
if ! python3 -c "import yaml" 2>/dev/null; then
    VENV_DIR="${TMPDIR:-/tmp}/tomo-004-phase2-venv"
    [ -d "$VENV_DIR" ] || { python3 -m venv "$VENV_DIR" >/dev/null 2>&1 && "$VENV_DIR/bin/pip" install -q pyyaml >/dev/null 2>&1; }
    PYTHON="$VENV_DIR/bin/python"
else
    PYTHON="python3"
fi

FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-004-phase4-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/config" "$FIXTURE_DIR/tomo-tmp/items"

# Minimal cache
cat > "$FIXTURE_DIR/config/discovery-cache.yaml" <<'YAML'
cache_version: 1
last_scan: '2026-04-15T00:00:00Z'
map_notes:
  - path: Atlas/200 Maps/Health (MOC).md
    title: Health (MOC)
    topics: [health, habits, fitness]
YAML

# Vault config with realistic MiYo trackers shape
cat > "$FIXTURE_DIR/config/vault-config.yaml" <<'YAML'
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
tags:
  prefixes:
    topic: {wildcard: true, known_values: [personal/habits]}
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
trackers:
  daily_note_trackers:
    section: "Habits"
    today_fields:
      - {name: "Sport", type: boolean}
      - {name: "WakeUpEnergy", type: integer, scale: "1–5"}
      - {name: "Japanese", type: boolean}
  end_of_day_fields:
    section: "End of the Day"
    fields:
      - {name: "Highlights", type: string}
      - {name: "DayEnergy", type: integer, scale: "1–5"}
YAML

# ── Test 1: shared-ctx tracker_fields populated correctly ──────────────────
OUT="$FIXTURE_DIR/tomo-tmp/shared-ctx.json"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
  --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
  --vault-config "$FIXTURE_DIR/config/vault-config.yaml" \
  --profiles-dir "$REPO_ROOT/tomo/profiles" \
  --run-id "test-phase4" \
  --output "$OUT" 2>/dev/null

"$PYTHON" - "$OUT" <<'PY' && pass "shared-ctx tracker_fields populated" || fail "tracker_fields populated"
import json, sys
ctx = json.load(open(sys.argv[1]))
dn = ctx.get('daily_notes', {})
assert dn.get('enabled') is True
fields = {f['name']: f for f in dn.get('tracker_fields', [])}
# All 5 expected (2 bool + 2 rating + 1 text)
assert set(fields.keys()) == {'Sport', 'WakeUpEnergy', 'Japanese', 'Highlights', 'DayEnergy'}, f'got {list(fields)}'
assert fields['Sport']['type'] == 'bool'
assert fields['Sport']['section'] == 'Habits'
assert fields['Sport']['syntax'] == 'inline_field'
assert fields['WakeUpEnergy']['type'] == 'rating_1_5'
assert fields['Highlights']['type'] == 'text'
assert fields['Highlights']['syntax'] == 'callout_body'
assert fields['Highlights']['section'] == 'End of the Day'
# Keywords auto-seeded from CamelCase split
assert 'wake up energy' in fields['WakeUpEnergy']['keywords']
assert 'wakeupenergy' in fields['WakeUpEnergy']['keywords']
PY

# ── Test 2: reducer renders update_daily action alongside create_atomic_note ──
STATE="$FIXTURE_DIR/tomo-tmp/inbox-state.jsonl"
RUN_ID="test-phase4"
cat > "$STATE" <<JSONL
{"run_id":"$RUN_ID","stem":"run-log","path":"100 Inbox/run-log.md","status":"done","attempts":1,"started_at":"2026-04-15T07:00:00Z","completed_at":"2026-04-15T07:00:03Z","error":null}
JSONL

cat > "$FIXTURE_DIR/tomo-tmp/items/run-log.result.json" <<'JSON'
{
  "schema_version": "1",
  "stem": "run-log",
  "path": "100 Inbox/run-log.md",
  "type": "system_action",
  "type_confidence": 0.9,
  "date_relevance": {"date": "2026-04-15", "source": "filename"},
  "issues": [],
  "duration_ms": 1500,
  "actions": [
    {
      "kind": "create_atomic_note",
      "suggested_title": "Morning Run — Riverside Park",
      "destination_concept": "atomic_note",
      "candidate_mocs": [
        {"path": "Atlas/200 Maps/Health (MOC).md", "score": 0.7, "pre_check": true}
      ],
      "classification": {"category": "2200 - Mind-Body Connection", "confidence": 0.6},
      "needs_new_moc": false,
      "proposed_moc_topic": null,
      "tags_to_add": ["topic/personal/habits"],
      "atomic_note_worthiness": 0.65,
      "alternatives": []
    },
    {
      "kind": "update_daily",
      "date": "2026-04-15",
      "daily_note_path": "Calendar/301 Daily/2026-04-15",
      "updates": [
        {"field": "Sport", "value": true, "syntax": "inline_field", "confidence": 0.9},
        {"field": "Highlights", "value": "Morning run, 5k riverside", "syntax": "callout_body", "confidence": 0.7}
      ]
    }
  ]
}
JSON

DOC="$FIXTURE_DIR/tomo-tmp/suggestions-doc.json"
"$PYTHON" "$REPO_ROOT/scripts/suggestions-reducer.py" \
  --state "$STATE" --items-dir "$FIXTURE_DIR/tomo-tmp/items" \
  --run-id "$RUN_ID" --profile "miyo" --output "$DOC" --threshold 3 2>/dev/null

"$PYTHON" - "$DOC" <<'PY' && pass "reducer renders multi-action section" || fail "reducer multi-action"
import json, sys
doc = json.load(open(sys.argv[1]))
assert len(doc['sections']) == 1
actions = doc['sections'][0]['actions']
assert len(actions) == 2
assert actions[0]['kind'] == 'create_atomic_note'
assert actions[1]['kind'] == 'update_daily'
ud_md = actions[1]['rendered_md']
assert '[[Calendar/301 Daily/2026-04-15]]' in ud_md
assert 'Sport:: True' in ud_md or 'Sport:: true' in ud_md
assert 'Highlights' in ud_md and 'Morning run' in ud_md
assert 'Decision (daily update):' in ud_md
assert 'Decision (atomic note):' in actions[0]['rendered_md']
# No forbidden patterns
for a in actions:
    assert '[[+/' not in a['rendered_md']
    assert '.md]]' not in a['rendered_md']
PY

# ── Test 3: pure tracker item (update_daily only) ─────────────────────────
cat >> "$STATE" <<JSONL
{"run_id":"$RUN_ID","stem":"sleep-log","path":"100 Inbox/sleep-log.md","status":"done","attempts":1,"started_at":"2026-04-15T07:05:00Z","completed_at":"2026-04-15T07:05:01Z","error":null}
JSONL

cat > "$FIXTURE_DIR/tomo-tmp/items/sleep-log.result.json" <<'JSON'
{
  "schema_version": "1",
  "stem": "sleep-log",
  "path": "100 Inbox/sleep-log.md",
  "type": "fleeting_note",
  "type_confidence": 0.6,
  "date_relevance": {"date": "2026-04-15", "source": "filename"},
  "issues": [],
  "duration_ms": 400,
  "actions": [
    {
      "kind": "update_daily",
      "date": "2026-04-15",
      "daily_note_path": "Calendar/301 Daily/2026-04-15",
      "updates": [
        {"field": "WakeUpEnergy", "value": 3, "syntax": "inline_field", "confidence": 0.8}
      ]
    }
  ]
}
JSON

DOC2="$FIXTURE_DIR/tomo-tmp/suggestions-doc-2.json"
"$PYTHON" "$REPO_ROOT/scripts/suggestions-reducer.py" \
  --state "$STATE" --items-dir "$FIXTURE_DIR/tomo-tmp/items" \
  --run-id "$RUN_ID" --profile "miyo" --output "$DOC2" --threshold 3 2>/dev/null

"$PYTHON" - "$DOC2" <<'PY' && pass "pure tracker item → single update_daily action" || fail "pure tracker"
import json, sys
doc = json.load(open(sys.argv[1]))
sleep_section = next(s for s in doc['sections'] if s['stem'] == 'sleep-log')
assert len(sleep_section['actions']) == 1
assert sleep_section['actions'][0]['kind'] == 'update_daily'
assert 'WakeUpEnergy:: 3' in sleep_section['actions'][0]['rendered_md']
PY

# ── Test 4: daily disabled → no daily_notes section at all ────────────────
cat > "$FIXTURE_DIR/config/vault-config-no-daily.yaml" <<'YAML'
schema_version: 1
profile: miyo
concepts:
  inbox: "100 Inbox/"
  calendar:
    granularities:
      daily: {enabled: false}
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
trackers:
  daily_note_trackers:
    section: "Habits"
    today_fields:
      - {name: "Sport", type: boolean}
YAML

OUT_NO="$FIXTURE_DIR/tomo-tmp/shared-ctx-no-daily.json"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
  --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
  --vault-config "$FIXTURE_DIR/config/vault-config-no-daily.yaml" \
  --profiles-dir "$REPO_ROOT/tomo/profiles" \
  --run-id "test-phase4-no-daily" \
  --output "$OUT_NO" 2>/dev/null

"$PYTHON" - "$OUT_NO" <<'PY' && pass "daily disabled → no daily_notes block (regression guard)" || fail "daily disabled"
import json, sys
ctx = json.load(open(sys.argv[1]))
assert 'daily_notes' not in ctx, 'daily_notes must be omitted when disabled'
PY

# ── Test 5: tracker_fields with custom keywords override ──────────────────
cat > "$FIXTURE_DIR/config/vault-config-custom-kw.yaml" <<'YAML'
schema_version: 1
profile: miyo
concepts:
  inbox: "100 Inbox/"
  calendar:
    granularities:
      daily: {enabled: true, path: "Calendar/301 Daily/"}
naming:
  calendar_patterns: {daily: "YYYY-MM-DD"}
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
trackers:
  daily_note_trackers:
    section: "Habits"
    today_fields:
      - name: "Sport"
        type: boolean
        keywords: ["run", "workout", "gym", "yoga", "bike", "swim"]
YAML

OUT_KW="$FIXTURE_DIR/tomo-tmp/shared-ctx-kw.json"
"$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
  --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
  --vault-config "$FIXTURE_DIR/config/vault-config-custom-kw.yaml" \
  --profiles-dir "$REPO_ROOT/tomo/profiles" \
  --run-id "test-phase4-kw" \
  --output "$OUT_KW" 2>/dev/null

"$PYTHON" - "$OUT_KW" <<'PY' && pass "custom keywords merge with auto-seeded ones" || fail "custom keywords"
import json, sys
ctx = json.load(open(sys.argv[1]))
sport = next(f for f in ctx['daily_notes']['tracker_fields'] if f['name'] == 'Sport')
kws = set(sport['keywords'])
assert 'sport' in kws           # auto-seeded from name
assert 'run' in kws              # custom
assert 'yoga' in kws             # custom
PY

# ── Test 6: real-instance dry run (no assertion — informational) ───────────
if [ -f "$REPO_ROOT/tomo-instance/config/discovery-cache.yaml" ]; then
    REAL_OUT="$FIXTURE_DIR/tomo-tmp/real-shared-ctx.json"
    if "$PYTHON" "$REPO_ROOT/scripts/shared-ctx-builder.py" \
        --cache "$REPO_ROOT/tomo-instance/config/discovery-cache.yaml" \
        --vault-config "$REPO_ROOT/tomo-instance/config/vault-config.yaml" \
        --profiles-dir "$REPO_ROOT/tomo-instance/profiles" \
        --run-id "test-phase4-real" \
        --output "$REAL_OUT" 2>"$FIXTURE_DIR/real.log"; then
        N=$("$PYTHON" -c "import json; print(len(json.load(open('$REAL_OUT')).get('daily_notes',{}).get('tracker_fields',[])))")
        SIZE=$(wc -c < "$REAL_OUT" | tr -d ' ')
        pass "real-instance: $N tracker fields, $SIZE bytes (budget 15360)"
    else
        fail "real-instance dry run failed"
    fi
else
    skip "real-instance dry run" "instance not set up"
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 4 (spec 004) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 4 (spec 004) tests FAILED${C_RESET}\n"
    exit 1
fi
