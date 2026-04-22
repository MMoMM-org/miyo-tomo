#!/bin/bash
# test-004-phase2.sh — Acceptance tests for spec 004 Plan Phase 2.
#   Covers: shared-ctx-builder + state-init.
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
FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-004-phase2-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/config" "$FIXTURE_DIR/tomo-tmp"

cat > "$FIXTURE_DIR/config/discovery-cache.yaml" <<'YAML'
cache_version: 1
last_scan: '2026-04-15T00:00:00Z'
vault_structure:
  total_notes: 10
map_notes:
  - path: Atlas/200 Maps/Shell & Terminal (MOC).md
    title: Shell & Terminal (MOC)
    topics: [shell, zsh, terminal]
  - path: Atlas/200 Maps/2600 - Applied Sciences.md
    title: 2600 - Applied Sciences
    topics: []
  - path: Atlas/200 Maps/Empty Fallback (MOC).md
    title: Empty Fallback (MOC)
    topics: []
tag_taxonomy:
  prefixes:
    topic:
      wildcard: true
      known_values: [applied/shell, applied/tools]
    status:
      wildcard: true
      known_values: [inwork]
YAML

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
    topic:
      wildcard: true
      known_values: [applied/shell]
tomo:
  suggestions:
    proposable_tag_prefixes: [topic]
    excluded_tag_prefixes: [type, status, projects, content, mcp]
    parallel: 5
YAML

# ── Test 1: shared-ctx-builder ──────────────────────────────────────────────
OUT="$FIXTURE_DIR/tomo-tmp/shared-ctx.json"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-004" \
    --output "$OUT" 2>"$FIXTURE_DIR/shared-ctx.log"; then
    pass "shared-ctx-builder exits 0"
else
    fail "shared-ctx-builder failed"
    cat "$FIXTURE_DIR/shared-ctx.log" >&2
fi

if [ -f "$OUT" ]; then
    SIZE=$(wc -c < "$OUT" | tr -d ' ')
    if [ "$SIZE" -le 15360 ]; then
        pass "shared-ctx.json ≤ 15 KB (size=${SIZE}B)"
    else
        fail "shared-ctx.json too large: $SIZE"
    fi

    "$PYTHON" - "$OUT" <<'PY' && pass "shared-ctx.json content checks" || fail "shared-ctx.json content checks"
import json, sys
ctx = json.load(open(sys.argv[1]))
assert ctx['schema_version'] == '1', 'schema_version mismatch'
mocs = {m['title']: m for m in ctx['mocs']}
assert len(mocs) == 3, f'expected 3 mocs, got {len(mocs)}'
assert mocs['2600 - Applied Sciences']['is_classification'] is True
assert mocs['Shell & Terminal (MOC)']['is_classification'] is False
assert mocs['Empty Fallback (MOC)']['topics'] == ['Empty Fallback (MOC)']
assert mocs['2600 - Applied Sciences']['topics'] == ['2600 - Applied Sciences']
tag_names = [tp['name'] for tp in ctx['tag_prefixes']]
assert tag_names == ['topic'], f'expected [topic], got {tag_names}'
assert '2600 - Applied Sciences' in ctx['classification_keywords']
assert ctx['daily_notes']['enabled'] is True
assert 'Calendar/301 Daily/YYYY-MM-DD' in ctx['daily_notes']['path_pattern']
assert ctx['daily_notes']['tracker_fields'] == []
PY
fi

# ── Test 2: shared-ctx-builder with daily disabled omits daily_notes ────────
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

OUT2="$FIXTURE_DIR/tomo-tmp/shared-ctx-no-daily.json"
"$PYTHON" "$REPO_ROOT/tomo/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config-no-daily.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-004-no-daily" \
    --output "$OUT2" 2>/dev/null || true

if [ -f "$OUT2" ]; then
    "$PYTHON" - "$OUT2" <<'PY' && pass "daily_notes absent when disabled" || fail "daily_notes absent when disabled"
import json, sys
ctx = json.load(open(sys.argv[1]))
assert 'daily_notes' not in ctx
PY
fi

# ── Test 3: size-budget enforcement ─────────────────────────────────────────
# Construct a cache with huge topic lists so the builder must trim them.
cat > "$FIXTURE_DIR/config/discovery-cache-large.yaml" <<'YAML'
cache_version: 1
last_scan: '2026-04-15T00:00:00Z'
map_notes:
YAML
# 50 MOCs each with 100 long topic entries → would be well over 15 KB raw
for i in $(seq 1 50); do
    printf "  - path: Atlas/200 Maps/Big%02d.md\n    title: Big MOC %02d\n    topics:\n" "$i" "$i" >> "$FIXTURE_DIR/config/discovery-cache-large.yaml"
    for j in $(seq 1 100); do
        printf "    - topic_very_long_description_entry_%02d_%02d\n" "$i" "$j" >> "$FIXTURE_DIR/config/discovery-cache-large.yaml"
    done
done

OUT3="$FIXTURE_DIR/tomo-tmp/shared-ctx-large.json"
"$PYTHON" "$REPO_ROOT/tomo/scripts/shared-ctx-builder.py" \
    --cache "$FIXTURE_DIR/config/discovery-cache-large.yaml" \
    --vault-config "$FIXTURE_DIR/config/vault-config.yaml" \
    --profiles-dir "$REPO_ROOT/tomo/profiles" \
    --run-id "test-004-large" \
    --max-bytes 15360 \
    --output "$OUT3" 2>"$FIXTURE_DIR/large.log" || true

if [ -f "$OUT3" ]; then
    SIZE3=$(wc -c < "$OUT3" | tr -d ' ')
    "$PYTHON" - "$OUT3" "$SIZE3" <<'PY' && pass "budget enforcement keeps all 50 MOCs, trims topics" || fail "budget enforcement"
import json, sys
ctx = json.load(open(sys.argv[1]))
size = int(sys.argv[2])
assert len(ctx['mocs']) == 50, f'dropped MOCs: kept only {len(ctx["mocs"])}'
assert size <= 15360, f'still over budget: {size}'
PY
fi

# ── Test 4: state-init helper checks (regex logic) ─────────────────────────
"$PYTHON" - <<PY && pass "state-init skip-suffix logic" || fail "state-init skip-suffix logic"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("state_init", "$REPO_ROOT/tomo/scripts/state-init.py")
m = importlib.util.module_from_spec(spec)
# The module imports kado_client at module-scope. Inject a stub so we don't need Kado.
import types
sys.modules.setdefault("lib", types.ModuleType("lib"))
class _StubClient:
    def __init__(self, *a, **k): pass
    def list_dir(self, *a, **k): return []
class _StubError(Exception): pass
_kado_mod = types.ModuleType("lib.kado_client")
_kado_mod.KadoClient = _StubClient
_kado_mod.KadoError = _StubError
sys.modules["lib.kado_client"] = _kado_mod
spec.loader.exec_module(m)
assert m.is_skippable('100 Inbox/2026-04-10_1430_suggestions.md')
assert m.is_skippable('100 Inbox/2026-04-10_1430_instructions.md')
assert m.is_skippable('100 Inbox/note-diff.md')
assert not m.is_skippable('100 Inbox/20260410_note.md')
assert m.extract_stem('100 Inbox/foo.md') == 'foo'
PY

# ── Test 5: state-init against live Kado (optional) ─────────────────────────
if [ -n "${KADO_URL:-}" ] && [ -n "${KADO_TOKEN:-}" ]; then
    STATE_OUT="$FIXTURE_DIR/tomo-tmp/inbox-state.jsonl"
    if "$PYTHON" "$REPO_ROOT/tomo/scripts/state-init.py" \
        --inbox-path "${KADO_INBOX_PATH:-100 Inbox/}" \
        --run-id "test-004" \
        --output "$STATE_OUT" 2>"$FIXTURE_DIR/state-init.log"; then
        COUNT=$(wc -l < "$STATE_OUT" | tr -d ' ')
        pass "state-init live run produced $COUNT lines"
    else
        fail "state-init live run failed"
        cat "$FIXTURE_DIR/state-init.log" >&2
    fi
else
    skip "state-init live run" "KADO_URL/KADO_TOKEN not set"
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 2 (spec 004) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 2 (spec 004) tests FAILED${C_RESET}\n"
    exit 1
fi
