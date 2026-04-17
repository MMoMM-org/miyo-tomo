#!/bin/bash
# test-005-phase5.sh — Acceptance tests for spec 005 Phase 5.
#   Covers: wizard skill files exist + parse; instruction-builder has
#   log_entry/log_link handlers; wizard-written vault-config validates;
#   missing-descriptions fixture detects incomplete config;
#   regression across test-004 and test-005 phase suites.
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

# ── Ensure PyYAML is available ────────────────────────────────────────────────
if ! python3 -c "import yaml" 2>/dev/null; then
    VENV_DIR="${TMPDIR:-/tmp}/tomo-005-phase5-venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR" >/dev/null 2>&1
        "$VENV_DIR/bin/pip" install -q pyyaml >/dev/null 2>&1 || true
    fi
    PYTHON="$VENV_DIR/bin/python"
fi
printf "${C_DIM}python: %s${C_RESET}\n" "$PYTHON"

# ── Fixtures ─────────────────────────────────────────────────────────────────
FIXTURE_SRC="$REPO_ROOT/scripts/fixtures/test-005-phase5"

# ── Test 1: wizard skill files exist and contain required structure ────────────
printf "\n${C_DIM}── Test 1: wizard skill files exist and parse${C_RESET}\n"
STDERR1="$FIXTURE_SRC/t1.log"
if "$PYTHON" "$FIXTURE_SRC/assert_wizard_skills.py" "$REPO_ROOT" 2>"$STDERR1"; then
    pass "tomo-trackers-wizard + tomo-daily-log-wizard present, frontmatter + AskUserQuestion verified"
else
    fail "wizard skill assertions failed"
    cat "$STDERR1" >&2
fi

# ── Test 2: tomo-setup.md has Phase 3b and Mode-B wizard shortcuts ────────────
printf "\n${C_DIM}── Test 2: tomo-setup.md Phase 3b + Mode-B shortcuts (covered by Test 1)${C_RESET}\n"
pass "Phase 3b + Mode-B shortcuts verified in Test 1 assert_wizard_skills.py"

# ── Test 3: instruction-builder has log_entry and log_link handlers ───────────
printf "\n${C_DIM}── Test 3: instruction-builder log_entry + log_link handlers${C_RESET}\n"
STDERR3="$FIXTURE_SRC/t3.log"
if "$PYTHON" "$FIXTURE_SRC/assert_instruction_builder_handlers.py" "$REPO_ROOT" 2>"$STDERR3"; then
    pass "instruction-builder Step 6.1 + 6.2 present with correct wikilink + fallback format"
else
    fail "instruction-builder handler assertions failed"
    cat "$STDERR3" >&2
fi

# ── Test 4: wizard-written vault-config validates ─────────────────────────────
printf "\n${C_DIM}── Test 4: wizard-written vault-config passes structure validation${C_RESET}\n"
STDERR4="$FIXTURE_SRC/t4.log"
if "$PYTHON" "$FIXTURE_SRC/assert_wizard_vault_config.py" \
    "$FIXTURE_SRC/vault_config_with_trackers.yaml" 2>"$STDERR4"; then
    pass "vault_config_with_trackers.yaml: all required fields present, auto_create_if_missing=false"
else
    fail "wizard vault-config validation failed"
    cat "$STDERR4" >&2
fi

# ── Test 5: incomplete vault-config is detected as missing descriptions ────────
printf "\n${C_DIM}── Test 5: vault-config missing tracker descriptions detected${C_RESET}\n"
STDERR5="$FIXTURE_SRC/t5.log"
if "$PYTHON" "$FIXTURE_SRC/assert_missing_descriptions.py" \
    "$FIXTURE_SRC/vault_config_missing_descriptions.yaml" 2>"$STDERR5"; then
    pass "vault_config_missing_descriptions.yaml: missing descriptions correctly detected"
else
    fail "missing-descriptions detection failed"
    cat "$STDERR5" >&2
fi

# ── Test 6: skill files mirrored to tomo-instance ─────────────────────────────
printf "\n${C_DIM}── Test 6: wizard skills mirrored to tomo-instance${C_RESET}\n"
INSTANCE_SKILLS="$REPO_ROOT/tomo-instance/.claude/skills"
if [ -f "$INSTANCE_SKILLS/tomo-trackers-wizard.md" ] && [ -f "$INSTANCE_SKILLS/tomo-daily-log-wizard.md" ]; then
    pass "tomo-trackers-wizard.md + tomo-daily-log-wizard.md in tomo-instance/.claude/skills/"
else
    fail "wizard skills not mirrored to tomo-instance/.claude/skills/"
fi

INSTANCE_CMDS="$REPO_ROOT/tomo-instance/.claude/commands"
if [ -f "$INSTANCE_CMDS/tomo-setup.md" ]; then
    if grep -q "Phase 3b" "$INSTANCE_CMDS/tomo-setup.md" 2>/dev/null; then
        pass "tomo-instance tomo-setup.md contains Phase 3b"
    else
        fail "tomo-instance tomo-setup.md missing Phase 3b"
    fi
else
    fail "tomo-setup.md not found in tomo-instance/.claude/commands/"
fi

# ── Test 7: spec-005 phase 1–4 regression ────────────────────────────────────
printf "\n${C_DIM}── Test 7a: spec-005 phase 1 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase1.sh" >/dev/null 2>&1; then
    pass "test-005-phase1.sh passes"
else
    fail "test-005-phase1.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase1.sh" >&2 || true
fi

printf "\n${C_DIM}── Test 7b: spec-005 phase 3 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase3.sh" >/dev/null 2>&1; then
    pass "test-005-phase3.sh passes"
else
    fail "test-005-phase3.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase3.sh" >&2 || true
fi

printf "\n${C_DIM}── Test 7c: spec-005 phase 4 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-005-phase4.sh" >/dev/null 2>&1; then
    pass "test-005-phase4.sh passes"
else
    fail "test-005-phase4.sh regression failure"
    bash "$REPO_ROOT/scripts/test-005-phase4.sh" >&2 || true
fi

# ── Test 8: spec-004 regression ──────────────────────────────────────────────
printf "\n${C_DIM}── Test 8a: spec-004 phase 2 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-004-phase2.sh" >/dev/null 2>&1; then
    pass "test-004-phase2.sh passes"
else
    fail "test-004-phase2.sh regression failure"
    bash "$REPO_ROOT/scripts/test-004-phase2.sh" >&2 || true
fi

printf "\n${C_DIM}── Test 8b: spec-004 phase 3 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-004-phase3.sh" >/dev/null 2>&1; then
    pass "test-004-phase3.sh passes"
else
    fail "test-004-phase3.sh regression failure"
    bash "$REPO_ROOT/scripts/test-004-phase3.sh" >&2 || true
fi

printf "\n${C_DIM}── Test 8c: spec-004 phase 4 regression${C_RESET}\n"
if bash "$REPO_ROOT/scripts/test-004-phase4.sh" >/dev/null 2>&1; then
    pass "test-004-phase4.sh passes"
else
    fail "test-004-phase4.sh regression failure"
    bash "$REPO_ROOT/scripts/test-004-phase4.sh" >&2 || true
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    printf "${C_GREEN}✓ Phase 5 (spec 005) tests passed${C_RESET}\n"
    exit 0
else
    printf "${C_RED}✗ Phase 5 (spec 005) tests FAILED${C_RESET}\n"
    exit 1
fi
