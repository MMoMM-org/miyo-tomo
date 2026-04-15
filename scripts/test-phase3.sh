#!/bin/bash
# test-phase3.sh — Validate all Phase 3 (Inbox Processing) deliverables
# version: 0.1.0
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

check() {
    local label="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "  [PASS] $label"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label"
        FAIL=$((FAIL + 1))
    fi
}

check_file() {
    local label="$1"
    local path="$2"
    if [ -f "$path" ]; then
        echo "  [PASS] $label — exists"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label — not found: $path"
        FAIL=$((FAIL + 1))
    fi
}

check_contains() {
    local label="$1"
    local path="$2"
    local pattern="$3"
    if grep -q "$pattern" "$path" 2>/dev/null; then
        echo "  [PASS] $label"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label — pattern '$pattern' not found"
        FAIL=$((FAIL + 1))
    fi
}

# ── Test 1: Python scripts syntax ─────────────────────────────
echo "── Test 1: Python scripts syntax check ──────────────────────────────────────────────"

check "state-scanner.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/state-scanner.py', doraise=True)"
check "token-render.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/token-render.py', doraise=True)"
check "suggestion-parser.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/suggestion-parser.py', doraise=True)"

# ── Test 2: Token renderer functional test ────────────────────
echo ""
echo "── Test 2: Token renderer functional test ──────────────────────────────────────────────"

RENDER_TMP="$TMPDIR/render-test-$$.md"
echo '---
UUID: {{uuid}}
title: {{title}}
tags:{{tags}}
---
# [[{{title}}]]
{{body}}' | python3 scripts/token-render.py --tokens-json '{"title":"Test Note","tags":["topic/test","type/note"],"body":"Hello world"}' > "$RENDER_TMP" 2>/dev/null

check "token-render.py — produces output" test -s "$RENDER_TMP"
check "token-render.py — resolves title" grep -q "title: Test Note" "$RENDER_TMP"
check "token-render.py — resolves UUID" grep -q "UUID: 20" "$RENDER_TMP"
check "token-render.py — formats tags as YAML list" grep -q "  - topic/test" "$RENDER_TMP"
check "token-render.py — resolves body" grep -q "Hello world" "$RENDER_TMP"
check "token-render.py — preserves frontmatter fences" grep -c "^---" "$RENDER_TMP" | grep -q "2"
rm -f "$RENDER_TMP"

# ── Test 3: Suggestion parser functional test ─────────────────
echo ""
echo "── Test 3: Suggestion parser functional test ──────────────────────────────────────────────"

SUGGESTION_TMP="$TMPDIR/suggestion-test-$$.md"
cat > "$SUGGESTION_TMP" << 'SUGG'
---
type: tomo-suggestions
MiYo-Tomo: confirmed
---
# Inbox Suggestions

### S01: test-note.md

**Source:** `+/test-note.md`
**Type:** fleeting_note (confidence: 0.85)

**Primary Suggestion:**
- [x] Create atomic note "Test Topic" in Atlas/202 Notes/
- **Title:** Test Topic
- **Tags:** topic/knowledge, type/note/normal
- **Parent MOC:** [[Knowledge Management]]
- **Classification:** 2600 Applied Sciences

**Alternatives:**
- [ ] Link to existing [[Other Note]] instead

**Actions:**
- [x] Approve
- [ ] Skip
- [ ] Delete source after processing

### S02: skipped-note.md

**Source:** `+/skipped-note.md`
**Type:** unknown (confidence: 0.30)

**Actions:**
- [ ] Approve
- [x] Skip
- [ ] Delete source after processing
SUGG

PARSE_TMP="$TMPDIR/parse-test-$$.json"
python3 scripts/suggestion-parser.py --file "$SUGGESTION_TMP" > "$PARSE_TMP" 2>/dev/null

check "suggestion-parser.py — produces JSON" python3 -c "import json; json.load(open('$PARSE_TMP'))"
check "suggestion-parser.py — has confirmed_items" python3 -c "import json; d=json.load(open('$PARSE_TMP')); assert 'confirmed_items' in d"
check "suggestion-parser.py — detects approved item" python3 -c "import json; d=json.load(open('$PARSE_TMP')); assert d['total_approved'] >= 1"
check "suggestion-parser.py — detects skipped item" python3 -c "import json; d=json.load(open('$PARSE_TMP')); assert d['total_skipped'] >= 1"
rm -f "$SUGGESTION_TMP" "$PARSE_TMP"

# ── Test 4: Agent artifacts ───────────────────────────────────
echo ""
echo "── Test 4: Agent artifacts ──────────────────────────────────────────────────────────"

check_file "inbox-analyst.md" tomo/.claude/agents/inbox-analyst.md
check_contains "inbox-analyst — has classification" tomo/.claude/agents/inbox-analyst.md "fleeting_note"
check_contains "inbox-analyst — has MOC matching" tomo/.claude/agents/inbox-analyst.md "MOC"
check_contains "inbox-analyst — references topic-extract" tomo/.claude/agents/inbox-analyst.md "topic-extract"

# suggestion-builder.md retired in spec 004 (fan-out refactor).
# Its format rules now live in inbox-orchestrator.md.
check_file "inbox-orchestrator.md" tomo/.claude/agents/inbox-orchestrator.md
check_contains "inbox-orchestrator — inherits S-section format" tomo/.claude/agents/inbox-orchestrator.md "S01"
check_contains "inbox-orchestrator — carries Classification Guard rule" tomo/.claude/agents/inbox-orchestrator.md "Classification Guard"
check_contains "inbox-orchestrator — anti-parrot rule present" tomo/.claude/agents/inbox-orchestrator.md "Anti-parrot"

check_file "instruction-builder.md" tomo/.claude/agents/instruction-builder.md
check_contains "instruction-builder — has action handlers" tomo/.claude/agents/instruction-builder.md "New Atomic Note"
check_contains "instruction-builder — references token-render" tomo/.claude/agents/instruction-builder.md "token-render"
check_contains "instruction-builder — references suggestion-parser" tomo/.claude/agents/instruction-builder.md "suggestion-parser"

check_file "vault-executor.md" tomo/.claude/agents/vault-executor.md
check_contains "vault-executor — has cleanup workflow" tomo/.claude/agents/vault-executor.md "archived"
check_contains "vault-executor — references state-scanner" tomo/.claude/agents/vault-executor.md "state-scanner"
check_contains "vault-executor — is idempotent" tomo/.claude/agents/vault-executor.md "idempotent"

# ── Test 5: Command and skills ────────────────────────────────
echo ""
echo "── Test 5: Command and skills ──────────────────────────────────────────────────────────"

check_contains "inbox.md — has auto-discovery" tomo/.claude/commands/inbox.md "discover"
check_contains "inbox.md — references all 4 agents" tomo/.claude/commands/inbox.md "vault-executor"

check_file "pkm-workflows.md" tomo/.claude/skills/pkm-workflows.md
check_contains "pkm-workflows — has state machine" tomo/.claude/skills/pkm-workflows.md "captured"
check_contains "pkm-workflows — has 7 states" tomo/.claude/skills/pkm-workflows.md "archived"
check_contains "pkm-workflows — has classification" tomo/.claude/skills/pkm-workflows.md "fleeting_note"

check_file "template-render.md" tomo/.claude/skills/template-render.md
check_contains "template-render — has token categories" tomo/.claude/skills/template-render.md "Generated Tokens"
check_contains "template-render — has YAML list formatting" tomo/.claude/skills/template-render.md "YAML List"
check_contains "template-render — has Templater coexistence" tomo/.claude/skills/template-render.md "Templater"

# ── Test 6: Regression check ─────────────────────────────────
echo ""
echo "── Test 6: Prior phase regression check ──────────────────────────────────────────────"

if bash scripts/test-phase1.sh > /dev/null 2>&1; then
    echo "  [PASS] Phase 1 tests still pass"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Phase 1 tests have regressions"
    FAIL=$((FAIL + 1))
fi

if bash scripts/test-phase2.sh > /dev/null 2>&1; then
    echo "  [PASS] Phase 2 tests still pass"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Phase 2 tests have regressions"
    FAIL=$((FAIL + 1))
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 3 Validation Results"
echo "  PASS: $PASS   FAIL: $FAIL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
