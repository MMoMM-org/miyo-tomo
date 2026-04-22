#!/bin/bash
# test-005-phase1.sh — Acceptance tests for spec 005 Phase 1.
#   Covers: polymorphic updates[] validation, forbidden-alias detection,
#   legacy migration, template kinds, vault-example structure, 004 regression.
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
    VENV_DIR="${TMPDIR:-/tmp}/tomo-005-phase1-venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR" >/dev/null 2>&1
        "$VENV_DIR/bin/pip" install -q pyyaml >/dev/null 2>&1 || true
    fi
    PYTHON="$VENV_DIR/bin/python"
fi
printf "${C_DIM}python: %s${C_RESET}\n" "$PYTHON"

# ── Fixtures ───────────────────────────────────────────────────────────────
FIXTURE_SRC="$REPO_ROOT/tests/fixtures/test-005-phase1"
FIXTURE_DIR="${TMPDIR:-/tmp}/tomo-005-phase1-fixtures"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR"

# Copy pre-written fixture files into TMPDIR for test use
cp "$FIXTURE_SRC/"*.json "$FIXTURE_DIR/" 2>/dev/null || true
cp "$FIXTURE_SRC/"*.py   "$FIXTURE_DIR/" 2>/dev/null || true

# ── Test 1: schema validates a valid mixed-kind updates[] result ───────────
printf "\n${C_DIM}── Test 1: valid mixed-kind updates[]${C_RESET}\n"
STDERR1="$FIXTURE_DIR/t1.log"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/validate-result.py" \
    --result "$FIXTURE_DIR/valid_mixed_updates.json" \
    2>"$STDERR1"; then
    pass "valid mixed-kind updates[] exits 0"
else
    fail "valid mixed-kind updates[] exited non-zero"
    cat "$STDERR1" >&2
fi

# ── Test 2: atomic-note-only result is valid (backwards compat) ───────────
printf "\n${C_DIM}── Test 2: atomic-note-only (backwards compat)${C_RESET}\n"
STDERR2="$FIXTURE_DIR/t2.log"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/validate-result.py" \
    --result "$FIXTURE_DIR/atomic_only.json" \
    2>"$STDERR2"; then
    pass "atomic-note-only result exits 0"
else
    fail "atomic-note-only result exited non-zero"
    cat "$STDERR2" >&2
fi

# ── Test 3a: log_entry with text: alias → exits 1 with correct message ─────
printf "\n${C_DIM}── Test 3a: log_entry text: alias${C_RESET}\n"
STDERR3A="$FIXTURE_DIR/t3a.log"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/validate-result.py" \
    --result "$FIXTURE_DIR/alias_log_entry_text.json" \
    2>"$STDERR3A"; then
    fail "log_entry text: alias should exit 1, but exited 0"
else
    if grep -q "use \`content:\` instead" "$STDERR3A"; then
        pass "log_entry text: alias exits 1 with correct message"
    else
        fail "log_entry text: alias exits 1 but message wrong"
        cat "$STDERR3A" >&2
    fi
fi

# ── Test 3b: log_link with target: alias → exits 1 with correct message ────
printf "\n${C_DIM}── Test 3b: log_link target: alias${C_RESET}\n"
STDERR3B="$FIXTURE_DIR/t3b.log"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/validate-result.py" \
    --result "$FIXTURE_DIR/alias_log_link_target.json" \
    2>"$STDERR3B"; then
    fail "log_link target: alias should exit 1, but exited 0"
else
    if grep -q "use \`target_stem:\` instead" "$STDERR3B"; then
        pass "log_link target: alias exits 1 with correct message"
    else
        fail "log_link target: alias exits 1 but message wrong"
        cat "$STDERR3B" >&2
    fi
fi

# ── Test 3c: tracker with type: alias → exits 1 with correct message ───────
printf "\n${C_DIM}── Test 3c: tracker type: alias${C_RESET}\n"
STDERR3C="$FIXTURE_DIR/t3c.log"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/validate-result.py" \
    --result "$FIXTURE_DIR/alias_tracker_type.json" \
    2>"$STDERR3C"; then
    fail "tracker type: alias should exit 1, but exited 0"
else
    if grep -q "use \`kind:\` instead" "$STDERR3C"; then
        pass "tracker type: alias exits 1 with correct message"
    else
        fail "tracker type: alias exits 1 but message wrong"
        cat "$STDERR3C" >&2
    fi
fi

# ── Test 4: legacy update (no kind:) → exits 0 + WARN + treated as tracker ─
printf "\n${C_DIM}── Test 4: legacy update migration${C_RESET}\n"
STDERR4="$FIXTURE_DIR/t4.log"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/validate-result.py" \
    --result "$FIXTURE_DIR/legacy_no_kind.json" \
    2>"$STDERR4"; then
    if grep -q "WARN" "$STDERR4" && grep -q "treated as tracker" "$STDERR4"; then
        pass "legacy update exits 0 with WARN + treated as tracker"
    else
        fail "legacy update exits 0 but missing WARN/treated-as-tracker in stderr"
        cat "$STDERR4" >&2
    fi
else
    fail "legacy update should exit 0, but exited non-zero"
    cat "$STDERR4" >&2
fi

# ── Test 5: regenerated template validates ─────────────────────────────────
printf "\n${C_DIM}── Test 5: template validates against schema${C_RESET}\n"
STDERR5="$FIXTURE_DIR/t5.log"
if "$PYTHON" "$REPO_ROOT/tomo/scripts/validate-result.py" \
    --result "$REPO_ROOT/tomo/templates/item-result.template.json" \
    --schema "$REPO_ROOT/tomo/schemas/item-result.schema.json" \
    2>"$STDERR5"; then
    pass "item-result.template.json validates against schema"
else
    fail "item-result.template.json failed schema validation"
    cat "$STDERR5" >&2
fi

# ── Test 6: template contains all three update kinds ──────────────────────
printf "\n${C_DIM}── Test 6: template contains all three update kinds${C_RESET}\n"
STDERR6="$FIXTURE_DIR/t6.log"
if "$PYTHON" "$FIXTURE_DIR/assert_template_kinds.py" \
    "$REPO_ROOT/tomo/templates/item-result.template.json" \
    2>"$STDERR6"; then
    pass "template updates[] contains tracker, log_entry, log_link"
else
    fail "template missing one or more update kinds"
    cat "$STDERR6" >&2
fi

# ── Test 7: vault-example.yaml parses and has required structure ───────────
printf "\n${C_DIM}── Test 7: vault-example.yaml structure${C_RESET}\n"
STDERR7="$FIXTURE_DIR/t7.log"
if "$PYTHON" "$FIXTURE_DIR/assert_vault_example.py" \
    "$REPO_ROOT/tomo/config/vault-example.yaml" \
    2>"$STDERR7"; then
    pass "vault-example.yaml structure is valid"
else
    fail "vault-example.yaml structure check failed"
    cat "$STDERR7" >&2
fi

# ── Test 8: Spec-004 regression ────────────────────────────────────────────
printf "\n${C_DIM}── Test 8a: spec-004 phase 3 regression${C_RESET}\n"
if bash "$REPO_ROOT/tests/test-004-phase3.sh" >/dev/null 2>&1; then
    pass "test-004-phase3.sh passes"
else
    fail "test-004-phase3.sh regression failure"
    bash "$REPO_ROOT/tests/test-004-phase3.sh" >&2 || true
fi

printf "\n${C_DIM}── Test 8b: spec-004 phase 4 regression${C_RESET}\n"
if bash "$REPO_ROOT/tests/test-004-phase4.sh" >/dev/null 2>&1; then
    pass "test-004-phase4.sh passes"
else
    fail "test-004-phase4.sh regression failure"
    bash "$REPO_ROOT/tests/test-004-phase4.sh" >&2 || true
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 1 (spec 005) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 1 (spec 005) tests FAILED${C_RESET}\n"
    exit 1
fi
