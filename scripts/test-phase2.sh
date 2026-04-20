#!/bin/bash
# test-phase2.sh — Validate all Phase 2 (Vault Explorer) deliverables
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
        echo "  [FAIL] $label — pattern '$pattern' not found in $path"
        FAIL=$((FAIL + 1))
    fi
}

# ── Test 1: Python scripts syntax ─────────────────────────────
echo "── Test 1: Python scripts syntax check ──────────────────────────────────────────────"

check "lib/__init__.py — exists" test -f scripts/lib/__init__.py
check "lib/kado_client.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/lib/kado_client.py', doraise=True)"
check "vault-scan.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/vault-scan.py', doraise=True)"
check "topic-extract.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/topic-extract.py', doraise=True)"
check "moc-tree-builder.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/moc-tree-builder.py', doraise=True)"
check "cache-builder.py — syntax" python3 -c "import py_compile; py_compile.compile('scripts/cache-builder.py', doraise=True)"

# ── Test 2: Topic extractor functional test ───────────────────
echo ""
echo "── Test 2: Topic extractor functional test ──────────────────────────────────────────────"

TOPIC_INPUT='---
title: Test Note
tags:
  - topic/knowledge/lyt
---
# [[Test Note]]
## Important Section
## Related
Some text about [[Obsidian]] and [[PKM]].'

TOPIC_TMP="$TMPDIR/topic-test-$$.json"
echo "$TOPIC_INPUT" | python3 scripts/topic-extract.py --title "Test Note" > "$TOPIC_TMP" 2>/dev/null
check "topic-extract.py — produces JSON output" python3 -c "import json; json.load(open('$TOPIC_TMP'))"
check "topic-extract.py — has topics key" python3 -c "import json; d=json.load(open('$TOPIC_TMP')); assert 'topics' in d"
check "topic-extract.py — extracts topics" python3 -c "import json; d=json.load(open('$TOPIC_TMP')); assert len(d['topics']) > 0"
check "topic-extract.py — has source_methods" python3 -c "import json; d=json.load(open('$TOPIC_TMP')); assert 'source_methods' in d"
rm -f "$TOPIC_TMP"

# ── Test 3: Kado client structure ─────────────────────────────
echo ""
echo "── Test 3: Kado client library structure ──────────────────────────────────────────────"

check_contains "kado_client.py — has KadoClient class" scripts/lib/kado_client.py "class KadoClient"
check_contains "kado_client.py — has read_note method" scripts/lib/kado_client.py "def read_note"
check_contains "kado_client.py — has list_dir method" scripts/lib/kado_client.py "def list_dir"
check_contains "kado_client.py — has search_by_tag method" scripts/lib/kado_client.py "def search_by_tag"
check_contains "kado_client.py — has test_connection method" scripts/lib/kado_client.py "def test_connection"

# ── Test 4: Agent artifacts ───────────────────────────────────
echo ""
echo "── Test 4: Agent artifacts ──────────────────────────────────────────────────────────"

check_file "vault-explorer.md agent" tomo/dot_claude/agents/vault-explorer.md
check_contains "vault-explorer.md — has version" tomo/dot_claude/agents/vault-explorer.md "version:"
check_contains "vault-explorer.md — has workflow" tomo/dot_claude/agents/vault-explorer.md "## Workflow"
check_contains "vault-explorer.md — references vault-scan.py" tomo/dot_claude/agents/vault-explorer.md "vault-scan.py"
check_contains "vault-explorer.md — references moc-tree-builder.py" tomo/dot_claude/agents/vault-explorer.md "moc-tree-builder.py"
check_contains "vault-explorer.md — references cache-builder.py" tomo/dot_claude/agents/vault-explorer.md "cache-builder.py"

check_file "explore-vault.md command" tomo/dot_claude/commands/explore-vault.md
check_contains "explore-vault.md — has version" tomo/dot_claude/commands/explore-vault.md "version:"
check_contains "explore-vault.md — references vault-explorer agent" tomo/dot_claude/commands/explore-vault.md "vault-explorer"

check_file "lyt-patterns.md skill" tomo/dot_claude/skills/lyt-patterns/SKILL.md
check_contains "lyt-patterns.md — has MOC Matching" tomo/dot_claude/skills/lyt-patterns/SKILL.md "MOC Matching"
check_contains "lyt-patterns.md — has Section Placement" tomo/dot_claude/skills/lyt-patterns/SKILL.md "Section Placement"
check_contains "lyt-patterns.md — has Mental Squeeze" tomo/dot_claude/skills/lyt-patterns/SKILL.md "Mental Squeeze"

check_file "obsidian-fields.md skill" tomo/dot_claude/skills/obsidian-fields/SKILL.md
check_contains "obsidian-fields.md — has Frontmatter" tomo/dot_claude/skills/obsidian-fields/SKILL.md "Frontmatter"
check_contains "obsidian-fields.md — has Relationship" tomo/dot_claude/skills/obsidian-fields/SKILL.md "Relationship"
check_contains "obsidian-fields.md — has Callout" tomo/dot_claude/skills/obsidian-fields/SKILL.md "Callout"
check_contains "obsidian-fields.md — has Tag Taxonomy" tomo/dot_claude/skills/obsidian-fields/SKILL.md "Tag Taxonomy"

# ── Test 5: Phase 1 still passes ─────────────────────────────
echo ""
echo "── Test 5: Phase 1 regression check ──────────────────────────────────────────────"

if [ -f scripts/test-phase1.sh ]; then
    if bash scripts/test-phase1.sh > /dev/null 2>&1; then
        echo "  [PASS] Phase 1 tests still pass"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] Phase 1 tests have regressions"
        FAIL=$((FAIL + 1))
    fi
else
    echo "  [SKIP] Phase 1 test script not found"
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 2 Validation Results"
echo "  PASS: $PASS   FAIL: $FAIL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
