# scripts/ — Utility Scripts

## Nature of this directory
- Host-side shell scripts (install-tomo.sh, update-tomo.sh, cleanup-tomo.sh, test-*.sh)
- Runtime Python scripts (copied into `$INSTANCE_PATH/scripts/` at install time)
- Shared library `scripts/lib/` (kado_client.py)
- Fixtures for integration tests under `scripts/fixtures/`

## TDD (for Python scripts)
- RED: Write failing test first. No implementation before a failing test.
- GREEN: Minimal code to make the test pass. Nothing more.
- REFACTOR: Clean up only after GREEN. Run tests again.

## Conventions
- Python scripts must use a venv (see ~/Kouzou/standards/guardrails.md)
- Shell scripts must run on bash 3.2 (macOS default) — no `declare -A`
- `$TOMO_SOURCE` = `$REPO_ROOT/tomo` — the template source dir
- Template source: `tomo/dot_claude/` (visible name, renamed at install → `.claude/`)
- Instance destination paths keep `.claude/` (Claude Code runtime requires it)

## Stack Rules
<!-- Generic fallback — no stack-specific rules detected -->
