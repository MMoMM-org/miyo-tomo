#!/bin/bash
# test-phase1.sh — Phase 1 integration validation.
# Validates all Phase 1 deliverables: profiles, install script, templates,
# yaml-fixer, and vault-config example.
# version: 0.1.0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
CLEANUP_DIRS=""

# ── Helpers ───────────────────────────────────────────────

pass() {
    echo "  [PASS] $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "  [FAIL] $1"
    FAIL=$((FAIL + 1))
}

section() {
    echo ""
    echo "── $1 ──────────────────────────────────────────────"
}

cleanup() {
    for d in $CLEANUP_DIRS; do
        rm -rf "$d"
    done
}

trap cleanup EXIT

# ── YAML parser resolution ────────────────────────────────

YAML_PYTHON=""
if [ -x "$TMPDIR/yaml-check/bin/python" ]; then
    if "$TMPDIR/yaml-check/bin/python" -c "import yaml" 2>/dev/null; then
        YAML_PYTHON="$TMPDIR/yaml-check/bin/python"
    fi
fi

if [ -z "$YAML_PYTHON" ] && python3 -c "import yaml" 2>/dev/null; then
    YAML_PYTHON="python3"
fi

# yaml_parse FILE — exits 0 if parseable YAML, 1 otherwise
yaml_parse() {
    local file="$1"
    if [ -n "$YAML_PYTHON" ]; then
        "$YAML_PYTHON" -c "
import yaml, sys
with open(sys.argv[1]) as f:
    list(yaml.safe_load_all(f))
" "$file" 2>/dev/null
    else
        # Fallback: basic structure checks
        grep -q "^schema_version\|^name:\|^version:\|^profile:" "$file" 2>/dev/null
    fi
}

# yaml_parse_text TEXT — parses YAML from a string
yaml_parse_text() {
    local text="$1"
    if [ -n "$YAML_PYTHON" ]; then
        echo "$text" | "$YAML_PYTHON" -c "
import yaml, sys
list(yaml.safe_load_all(sys.stdin))
" 2>/dev/null
    else
        # Fallback: check it has at least one colon-separated key
        echo "$text" | grep -q ":"
    fi
}

# ── Test 1: Profiles parse as YAML ───────────────────────

section "Test 1: Profiles parse as YAML"

for profile in miyo lyt; do
    profile_file="$REPO_ROOT/tomo/profiles/${profile}.yaml"
    if [ ! -f "$profile_file" ]; then
        fail "profiles/${profile}.yaml — file missing"
        continue
    fi

    if [ -n "$YAML_PYTHON" ]; then
        if yaml_parse "$profile_file"; then
            pass "profiles/${profile}.yaml — valid YAML"
        else
            fail "profiles/${profile}.yaml — YAML parse error"
        fi
    else
        # Fallback: check required keys exist
        MISSING_KEYS=""
        for key in name version; do
            if ! grep -q "^${key}:" "$profile_file" 2>/dev/null; then
                MISSING_KEYS="${MISSING_KEYS} ${key}"
            fi
        done
        if [ -z "$MISSING_KEYS" ]; then
            pass "profiles/${profile}.yaml — required keys present (no PyYAML)"
        else
            fail "profiles/${profile}.yaml — missing keys:${MISSING_KEYS}"
        fi
    fi
done

# ── Test 2: Install script syntax ────────────────────────

section "Test 2: Install script syntax check"

if bash -n "$REPO_ROOT/scripts/install-tomo.sh" 2>/dev/null; then
    pass "install-tomo.sh — bash syntax OK"
else
    fail "install-tomo.sh — bash syntax error"
fi

# ── Test 3: Install script non-interactive mode ───────────

section "Test 3: Install script non-interactive mode"

TEST_VAULT="$TMPDIR/tomo-test-vault-$$"
TEST_INSTANCE="$TMPDIR/tomo-test-instance-$$"
CLEANUP_DIRS="$TEST_VAULT $TEST_INSTANCE"

mkdir -p "$TEST_VAULT/.obsidian"

# Capture install output to a temp file so we can inspect it on failure
INSTALL_OUT="$TMPDIR/tomo-install-out-$$.txt"
CLEANUP_DIRS="$CLEANUP_DIRS $INSTALL_OUT"

INSTALL_EXIT=0
bash "$REPO_ROOT/scripts/install-tomo.sh" \
    --vault "$TEST_VAULT" \
    --profile miyo \
    --kado-token kado_test \
    --non-interactive \
    > "$INSTALL_OUT" 2>&1 || INSTALL_EXIT=$?

# Check instance directory was created (the install script defaults to REPO_ROOT/tomo-instance)
INSTANCE_PATH="$REPO_ROOT/tomo-instance"
if [ -d "$INSTANCE_PATH" ]; then
    pass "Instance directory created: tomo-instance/"
else
    fail "Instance directory not created (expected: tomo-instance/)"
    echo "    Install output:"
    while IFS= read -r line; do
        echo "    | $line"
    done < "$INSTALL_OUT"
fi

# Check vault-config.yaml was generated
VAULT_CONFIG="$INSTANCE_PATH/config/vault-config.yaml"
if [ -f "$VAULT_CONFIG" ]; then
    pass "vault-config.yaml generated"
else
    fail "vault-config.yaml not generated"
    VAULT_CONFIG=""
fi

# Check vault-config.yaml contents
if [ -n "$VAULT_CONFIG" ]; then
    if grep -q "schema_version" "$VAULT_CONFIG" 2>/dev/null; then
        pass "vault-config.yaml contains schema_version"
    else
        fail "vault-config.yaml missing schema_version"
    fi

    if grep -q "profile: .miyo." "$VAULT_CONFIG" 2>/dev/null; then
        pass "vault-config.yaml contains profile: miyo"
    else
        fail "vault-config.yaml missing 'profile: miyo'"
    fi

    if grep -q "^concepts:" "$VAULT_CONFIG" 2>/dev/null; then
        pass "vault-config.yaml contains concepts block"
    else
        fail "vault-config.yaml missing concepts block"
    fi
fi

# Clean up the generated instance so we don't pollute the repo
rm -rf "$REPO_ROOT/tomo-instance"
rm -f "$REPO_ROOT/tomo-install.json"
if [ -d "$REPO_ROOT/tomo-home" ]; then
    rm -rf "$REPO_ROOT/tomo-home"
fi

# ── Test 4: Templates exist and have valid structure ──────

section "Test 4: Config templates structure"

TEMPLATES_DIR="$REPO_ROOT/tomo/config/templates"
EXPECTED_TEMPLATES="t_daily_tomo.md t_moc_tomo.md t_note_tomo.md t_project_tomo.md t_source_tomo.md"

for tmpl in $EXPECTED_TEMPLATES; do
    tmpl_path="$TEMPLATES_DIR/$tmpl"
    if [ ! -f "$tmpl_path" ]; then
        fail "$tmpl — file missing"
        continue
    fi
    pass "$tmpl — exists"

    # Check for {{title}} placeholder
    if grep -q "{{title}}" "$tmpl_path" 2>/dev/null; then
        pass "$tmpl — contains {{title}}"
    else
        fail "$tmpl — missing {{title}}"
    fi

    # Check for frontmatter delimiters (at least two occurrences of ---)
    DELIM_COUNT=$(grep -c "^---" "$tmpl_path" 2>/dev/null || true)
    if [ "$DELIM_COUNT" -ge 2 ]; then
        pass "$tmpl — frontmatter delimiters present"
    else
        fail "$tmpl — missing frontmatter delimiters (found: $DELIM_COUNT)"
    fi
done

# ── Test 5: yaml-fixer works ──────────────────────────────

section "Test 5: yaml-fixer.py"

YAML_FIXER="$REPO_ROOT/scripts/yaml-fixer.py"

# --help exits 0
if python3 "$YAML_FIXER" --help > /dev/null 2>&1; then
    pass "yaml-fixer.py --help exits 0"
else
    fail "yaml-fixer.py --help did not exit 0"
fi

# Valid YAML passes through
VALID_YAML="name: test
version: 1.0
items:
  - alpha
  - beta
"
FIXER_OUT="$(echo "$VALID_YAML" | python3 "$YAML_FIXER" 2>/dev/null)"
FIXER_EXIT=$?
if [ "$FIXER_EXIT" -eq 0 ]; then
    pass "yaml-fixer.py — valid YAML passes through (exit 0)"
else
    fail "yaml-fixer.py — valid YAML exited $FIXER_EXIT"
fi

# Check output preserves key content
if echo "$FIXER_OUT" | grep -q "name: test" 2>/dev/null; then
    pass "yaml-fixer.py — output preserves content"
else
    fail "yaml-fixer.py — output did not preserve content"
fi

# --check mode: valid YAML exits 0
YAML_CHECK_EXIT=0
echo "$VALID_YAML" | python3 "$YAML_FIXER" --check 2>/dev/null || YAML_CHECK_EXIT=$?
if [ -n "$YAML_PYTHON" ]; then
    # With PyYAML available, valid YAML should exit 0
    if [ "$YAML_CHECK_EXIT" -eq 0 ]; then
        pass "yaml-fixer.py --check — valid YAML exits 0"
    else
        fail "yaml-fixer.py --check — valid YAML exited $YAML_CHECK_EXIT (expected 0)"
    fi
else
    # Without PyYAML, --check always exits 0 (is_valid_yaml returns True)
    if [ "$YAML_CHECK_EXIT" -eq 0 ]; then
        pass "yaml-fixer.py --check — exits 0 (no PyYAML, always valid)"
    else
        fail "yaml-fixer.py --check — exited $YAML_CHECK_EXIT (unexpected)"
    fi
fi

# ── Test 6: vault-config example parses ──────────────────

section "Test 6: vault-example.yaml parses as valid YAML"

VAULT_EXAMPLE="$REPO_ROOT/tomo/config/vault-example.yaml"
if [ ! -f "$VAULT_EXAMPLE" ]; then
    fail "vault-example.yaml — file missing"
else
    if [ -n "$YAML_PYTHON" ]; then
        if yaml_parse "$VAULT_EXAMPLE"; then
            pass "vault-example.yaml — valid YAML"
        else
            fail "vault-example.yaml — YAML parse error"
        fi
    else
        # Fallback: check file has colon-separated key-value pairs
        if grep -q ":" "$VAULT_EXAMPLE" 2>/dev/null; then
            pass "vault-example.yaml — has key-value structure (no PyYAML)"
        else
            fail "vault-example.yaml — no key-value pairs found"
        fi
    fi
fi

# ── Summary ───────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Phase 1 Validation Results"
echo "  PASS: $PASS   FAIL: $FAIL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
