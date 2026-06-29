# docs/tomo/scripts/validate-yaml.md

WHY file for `tomo/scripts/validate-yaml.py`.

## Why this script exists

Obsidian Bases (`.base` files) use YAML, not JSON. The original spec 026 ADR-4 assumed both
`.base` and `.canvas` were JSON; this was incorrect. Fetching the kepano/obsidian-skills source
during T2.2 implementation confirmed that `.base` files contain valid YAML (indented key-value
structure with expression strings as filter values). `.canvas` files remain JSON Canvas 1.0
(validated by `validate-json.py`).

This script provides the same deterministic parse-gate for `.base` that `validate-json.py`
provides for `.canvas` — ensuring a malformed file is caught before any vault write.

## Why yaml.safe_load (not yaml.load)

`yaml.safe_load` parses YAML without executing arbitrary Python constructors. `yaml.load` with
an unconstrained Loader can execute Python code embedded in the YAML (CVE class). For a gate
that processes user-controlled `.base` files, `safe_load` is mandatory.

## Why exit 0 on valid, exit 1 on malformed or missing

Matches the contract of `validate-json.py` exactly so callers route by extension:
- `.canvas` → `validate-json.py`
- `.base` → `validate-yaml.py`

The same exit-code contract means `inbox-author` / `kado-write-patterns` can dispatch by
extension without special-casing the gate result.

## Why read-only

The gate must not modify the vault or produce side-effect files. It is invoked before any write
decision; if it writes something, it has already broken the safety invariant it exists to enforce.

## Spec references

- Spec 026 ADR-4 (corrected): `.base` is YAML; `.canvas` is JSON; separate gates per extension
- Spec 026 ADR-9: safety logic in deterministic scripts, not LLM glue; unit-tested in both directions
- PRD Feature 4 AC: invalid artefact never reaches the vault
- T1.4 implementation: `tests/test_validate_yaml.py` (10 tests — valid, malformed, missing, write-nothing)
