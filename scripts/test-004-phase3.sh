#!/bin/bash
# test-004-phase3.sh — Acceptance tests for spec 004 Plan Phase 3.
#   Covers: state-update, suggestions-reducer, per-item-result schema round-trip.
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

# ── Fixtures ───────────────────────────────────────────────────────────────
FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-004-phase3-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/tomo-tmp/items"

STATE="$FIXTURE_DIR/tomo-tmp/inbox-state.jsonl"
ITEMS_DIR="$FIXTURE_DIR/tomo-tmp/items"
RUN_ID="test-run-phase3"

# Seed initial pending entries (normally written by state-init)
cat > "$STATE" <<JSONL
{"run_id":"$RUN_ID","stem":"item-one","path":"100 Inbox/item-one.md","status":"pending","attempts":0,"started_at":null,"completed_at":null,"error":null}
{"run_id":"$RUN_ID","stem":"item-two","path":"100 Inbox/item-two.md","status":"pending","attempts":0,"started_at":null,"completed_at":null,"error":null}
{"run_id":"$RUN_ID","stem":"item-fail","path":"100 Inbox/item-fail.md","status":"pending","attempts":0,"started_at":null,"completed_at":null,"error":null}
JSONL

# ── Test 1: state-update append + attempts counter ─────────────────────────
"$PYTHON" "$REPO_ROOT/scripts/state-update.py" \
    --state "$STATE" --stem "item-one" --status running --run-id "$RUN_ID" 2>/dev/null
"$PYTHON" "$REPO_ROOT/scripts/state-update.py" \
    --state "$STATE" --stem "item-one" --status done --run-id "$RUN_ID" 2>/dev/null

"$PYTHON" - "$STATE" <<'PY' && pass "state-update running→done transition" || fail "state-update running→done"
import json, sys
lines = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
one = [l for l in lines if l['stem'] == 'item-one']
assert len(one) == 3, f'expected 3 entries for item-one, got {len(one)}'
assert one[-1]['status'] == 'done'
assert one[-1]['attempts'] == 1
assert one[-1]['started_at'] is not None
assert one[-1]['completed_at'] is not None
PY

# ── Test 2: state-update failed path with error ────────────────────────────
"$PYTHON" "$REPO_ROOT/scripts/state-update.py" \
    --state "$STATE" --stem "item-fail" --status running --run-id "$RUN_ID" 2>/dev/null
"$PYTHON" "$REPO_ROOT/scripts/state-update.py" \
    --state "$STATE" --stem "item-fail" --status failed --run-id "$RUN_ID" \
    --error-kind "parser_error" --error-msg "malformed YAML frontmatter" 2>/dev/null

"$PYTHON" - "$STATE" <<'PY' && pass "state-update failed carries error object" || fail "state-update failed"
import json, sys
lines = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
last = [l for l in lines if l['stem'] == 'item-fail'][-1]
assert last['status'] == 'failed'
assert last['error']['kind'] == 'parser_error'
assert 'malformed' in last['error']['message']
PY

# ── Test 3: prepare two valid item-result.json fixtures ────────────────────
cat > "$ITEMS_DIR/item-one.result.json" <<'JSON'
{
  "schema_version": "1",
  "stem": "item-one",
  "path": "100 Inbox/item-one.md",
  "type": "coding_insight",
  "type_confidence": 0.85,
  "date_relevance": null,
  "issues": [],
  "duration_ms": 1200,
  "actions": [
    {
      "kind": "create_atomic_note",
      "suggested_title": "Zsh plugin loading order",
      "destination_concept": "atomic_note",
      "candidate_mocs": [
        {"path": "Atlas/200 Maps/Shell & Terminal (MOC).md", "score": 0.82, "pre_check": true}
      ],
      "classification": {"category": "2600 - Applied Sciences", "confidence": 0.6},
      "needs_new_moc": false,
      "proposed_moc_topic": null,
      "tags_to_add": ["topic/applied/shell"],
      "atomic_note_worthiness": 0.7,
      "alternatives": []
    }
  ]
}
JSON

# item-two flags needs_new_moc with topic "morning routine"
cat > "$ITEMS_DIR/item-two.result.json" <<'JSON'
{
  "schema_version": "1",
  "stem": "item-two",
  "path": "100 Inbox/item-two.md",
  "type": "system_action",
  "type_confidence": 0.9,
  "date_relevance": null,
  "issues": [],
  "duration_ms": 900,
  "actions": [
    {
      "kind": "create_atomic_note",
      "suggested_title": "Morning routine notes",
      "destination_concept": "atomic_note",
      "candidate_mocs": [],
      "classification": {"category": "2100 - Personal Management", "confidence": 0.55},
      "needs_new_moc": true,
      "proposed_moc_topic": "Morning Routine",
      "tags_to_add": ["topic/personal/habits"],
      "atomic_note_worthiness": 0.6,
      "alternatives": []
    }
  ]
}
JSON

# Mark both as done in state-file
"$PYTHON" "$REPO_ROOT/scripts/state-update.py" \
    --state "$STATE" --stem "item-two" --status done --run-id "$RUN_ID" 2>/dev/null

# ── Test 4: suggestions-reducer runs and produces valid doc ────────────────
REDUCER_OUT="$FIXTURE_DIR/tomo-tmp/suggestions-doc.json"
if "$PYTHON" "$REPO_ROOT/scripts/suggestions-reducer.py" \
    --state "$STATE" --items-dir "$ITEMS_DIR" --run-id "$RUN_ID" \
    --profile "miyo" --output "$REDUCER_OUT" --threshold 1 2>"$FIXTURE_DIR/reducer.log"; then
    pass "suggestions-reducer exits 0"
else
    fail "suggestions-reducer failed"
    cat "$FIXTURE_DIR/reducer.log" >&2
fi

"$PYTHON" - "$REDUCER_OUT" <<'PY' && pass "reducer doc structure" || fail "reducer doc structure"
import json, sys
doc = json.load(open(sys.argv[1]))
assert doc['schema_version'] == '1'
assert doc['profile'] == 'miyo'
assert doc['source_items'] == 3  # 2 done + 1 failed
assert len(doc['sections']) == 2, f'expected 2 sections, got {len(doc["sections"])}'
assert len(doc['needs_attention']) == 1
assert doc['needs_attention'][0]['stem'] == 'item-fail'
# With threshold=1, the "Morning Routine" topic is a cluster of 1 → becomes Proposed MOC
assert len(doc['proposed_mocs']) == 1
assert doc['proposed_mocs'][0]['topic'] == 'Morning Routine'
# Rendered markdown contains wikilinks and decision block
first_action = doc['sections'][0]['actions'][0]
assert '[[item-one]]' in first_action['rendered_md']
assert 'Decision' in first_action['rendered_md']
assert '[[Atlas/200 Maps/Shell & Terminal (MOC)]]' in first_action['rendered_md']
# No forbidden patterns
assert '[[+/' not in first_action['rendered_md'], 'forbidden + prefix in output'
assert '.md]]' not in first_action['rendered_md'], '.md should not appear inside wikilinks'
PY

# ── Test 5: threshold ≥ 3 does NOT emit Proposed MOC for single item ───────
REDUCER_OUT2="$FIXTURE_DIR/tomo-tmp/suggestions-doc-threshold3.json"
"$PYTHON" "$REPO_ROOT/scripts/suggestions-reducer.py" \
    --state "$STATE" --items-dir "$ITEMS_DIR" --run-id "$RUN_ID" \
    --profile "miyo" --output "$REDUCER_OUT2" --threshold 3 2>/dev/null

"$PYTHON" - "$REDUCER_OUT2" <<'PY' && pass "threshold=3 blocks single-item clusters" || fail "threshold=3"
import json, sys
doc = json.load(open(sys.argv[1]))
assert len(doc['proposed_mocs']) == 0, f'expected no proposed_mocs, got {doc["proposed_mocs"]}'
PY

# ── Test 6: normalise_topic plural fold ────────────────────────────────────
"$PYTHON" - <<PY && pass "normalise_topic plural fold" || fail "normalise_topic"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sr", "$REPO_ROOT/scripts/suggestions-reducer.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
assert m.normalise_topic("Tools") == "tool"
assert m.normalise_topic("stories") == "story"
assert m.normalise_topic("Routines!") == "routine"
assert m.normalise_topic("shell") == "shell"
assert m.normalise_topic("") == ""
PY

# ── Test 7: heredoc/echo discipline — scan only fenced code blocks ─────────
AGENT_DIR="$REPO_ROOT/tomo/dot_claude/agents"
"$PYTHON" - "$AGENT_DIR/inbox-orchestrator.md" "$AGENT_DIR/inbox-analyst.md" <<'PY' && \
    pass "no heredoc / EXIT tails inside code blocks of new agents" || \
    fail "forbidden command pattern found inside a code block"
import re, sys
BAD = [
    re.compile(r"cat\s*<<\s*'?EOF'?"),
    re.compile(r";\s*echo\s+\"EXIT:"),
]
bad_count = 0
for path in sys.argv[1:]:
    in_code = False
    for n, line in enumerate(open(path, encoding='utf-8'), start=1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            continue
        for pat in BAD:
            if pat.search(line):
                print(f"{path}:{n}: {line.rstrip()}", file=sys.stderr)
                bad_count += 1
if bad_count:
    sys.exit(1)
PY

# ── Test 8: orchestrator frontmatter advertises kado-write ─────────────────
grep -q "mcp__kado__kado-write" "$AGENT_DIR/inbox-orchestrator.md" && \
    pass "orchestrator advertises kado-write" || \
    fail "orchestrator missing kado-write"

# ── Test 9: inbox-analyst does NOT have kado-write ─────────────────────────
if grep -E "^tools:.*mcp__kado__kado-write" "$AGENT_DIR/inbox-analyst.md" >/dev/null; then
    fail "inbox-analyst must NOT have kado-write (subagents only read)"
else
    pass "inbox-analyst correctly lacks kado-write"
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 3 (spec 004) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 3 (spec 004) tests FAILED${C_RESET}\n"
    exit 1
fi
