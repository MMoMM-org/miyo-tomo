#!/usr/bin/env python3
# version: 0.1.0
"""test_shared_ctx_no_accumulation.py — T3.1 tests for spec 021 (F-34).

Verifies that accumulation (Condition B) has been removed from shared-ctx-builder:

  - shared-ctx output has NO accumulation_index key
  - enforce_budget no longer trims accumulation (Pass-6 gone)
  - --max-bytes default is 40960
  - placeholder_mocs is NEVER trimmed even under a tiny budget
  - a corrected-placeholder envelope fits within 40960
  - schema no longer declares accumulation_index AND still validates a
    no-accumulation ctx (H3)
  - golden-baseline guard: build_mocs + build_placeholder_mocs output is
    byte-equal to the T3.0 baseline for all 4 fixtures (mocs + placeholder_mocs
    arrays only)

RED before GREEN discipline (CON-1/TDD).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "shared-ctx.schema.json"
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "021-ac-baseline" / "ac-baseline.json"
FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "test-015-t4-1"

sys.path.insert(0, str(SCRIPTS_DIR))

# shared-ctx-builder.py has a hyphen — load via importlib
_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)

enforce_budget = scb.enforce_budget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_ctx(*, include_placeholder_mocs: list | None = None) -> dict:
    """Return the minimum valid ctx dict for enforce_budget tests."""
    ctx = {
        "schema_version": "1",
        "run_id": "test-run",
        "mocs": [
            {"path": "Atlas/Foo MOC.md", "title": "Foo MOC",
             "topics": ["foo", "bar"], "is_classification": False}
        ],
        "tag_prefixes": [],
        "classification_keywords": {},
    }
    if include_placeholder_mocs is not None:
        ctx["placeholder_mocs"] = include_placeholder_mocs
    return ctx


def _validate_schema(obj: dict) -> None:
    """Validate obj against shared-ctx.schema.json."""
    try:
        import jsonschema
        schema = json.loads(SCHEMA_PATH.read_text())
        jsonschema.validate(obj, schema)
    except ImportError:
        # Structural fallback if jsonschema absent
        assert isinstance(obj, dict)
        assert "schema_version" in obj
        assert "mocs" in obj


def _run_main_with_cache(tmp_path: Path, cache: dict, run_id: str,
                          extra_args: list[str] | None = None) -> dict:
    """Run scb.main() with a minimal patched environment; return parsed output JSON."""
    import yaml

    cache_file = tmp_path / "cache.yaml"
    vault_cfg_file = tmp_path / "vault-config.yaml"
    out_file = tmp_path / "shared-ctx.json"
    profiles_dir = REPO_ROOT / "tomo" / "profiles"

    vault_cfg = {"profile": "miyo"}
    cache_file.write_text(yaml.dump(cache))
    vault_cfg_file.write_text(yaml.dump(vault_cfg))

    argv = [
        "shared-ctx-builder.py",
        "--cache", str(cache_file),
        "--vault-config", str(vault_cfg_file),
        "--profiles-dir", str(profiles_dir),
        "--output", str(out_file),
        "--run-id", run_id,
        "--skip-reconcile",
    ] + (extra_args or [])

    with patch("sys.argv", argv), \
         patch.object(scb, "build_tag_prefixes", return_value=[]), \
         patch.object(scb, "build_classification_keywords", return_value={}), \
         patch.object(scb, "build_daily_notes", return_value=None):
        rc = scb.main()

    assert rc == 0, f"main() returned {rc}"
    return json.loads(out_file.read_text())


# ---------------------------------------------------------------------------
# T3.1-1: shared-ctx output has NO accumulation_index key
# ---------------------------------------------------------------------------

def test_output_has_no_accumulation_index(tmp_path):
    """shared-ctx output must never contain accumulation_index regardless of cache content."""
    cache = {
        "map_notes": [],
        "placeholder_mocs": [],
        # Even if the producer still emits this, the consumer must ignore it:
        "unclassified_topic_clusters": {
            "search": ["alpha-beta-pruning", "minimax"],
            "games": ["alpha-beta-pruning", "minimax"],
        },
    }
    ctx = _run_main_with_cache(tmp_path, cache, "test-run-no-accum")
    assert "accumulation_index" not in ctx, (
        f"accumulation_index must be absent from shared-ctx output after T3.1, "
        f"got keys: {list(ctx)}"
    )
    _validate_schema(ctx)


# ---------------------------------------------------------------------------
# T3.1-2: enforce_budget return shape is (ctx, dropped) — no accumulation tuple
# ---------------------------------------------------------------------------

def test_enforce_budget_returns_two_tuple():
    """enforce_budget must return (ctx, moc_topics_dropped) — no acc_total/acc_kept."""
    ctx = _minimal_ctx()
    result = enforce_budget(ctx, max_bytes=999_999)
    assert len(result) == 2, (
        f"enforce_budget must return a 2-tuple (ctx, dropped), got {len(result)}-tuple: {result!r}"
    )
    trimmed_ctx, dropped = result
    assert isinstance(trimmed_ctx, dict)
    assert isinstance(dropped, int)


# ---------------------------------------------------------------------------
# T3.1-3: --max-bytes default is 40960
# ---------------------------------------------------------------------------

def test_max_bytes_default_is_40960():
    """build_arg_parser() must default --max-bytes to 40960."""
    parser = scb.build_arg_parser()
    defaults = parser.parse_args([
        "--cache", "x", "--vault-config", "y", "--output", "z"
    ])
    assert defaults.max_bytes == 40960, (
        f"Expected --max-bytes default 40960, got {defaults.max_bytes}"
    )


# ---------------------------------------------------------------------------
# T3.1-4: placeholder_mocs never trimmed even under tiny budget
# ---------------------------------------------------------------------------

def test_placeholder_mocs_never_trimmed():
    """placeholder_mocs must survive enforce_budget even when ctx exceeds a tiny budget."""
    placeholders = [
        {"target": "Search MOC", "referenced_by": "Atlas/Foo MOC.md"},
        {"target": "Games MOC", "referenced_by": "Atlas/Bar MOC.md"},
    ]
    ctx = _minimal_ctx(include_placeholder_mocs=placeholders)
    # Give a budget of 1 byte — far too small; placeholder must still survive
    trimmed, _dropped = enforce_budget(ctx, max_bytes=1)
    assert "placeholder_mocs" in trimmed, (
        "placeholder_mocs must survive enforce_budget regardless of budget pressure"
    )
    assert trimmed["placeholder_mocs"] == placeholders, (
        f"placeholder_mocs must be unmodified, got: {trimmed['placeholder_mocs']!r}"
    )


# ---------------------------------------------------------------------------
# T3.1-5: a corrected-placeholder envelope fits within 40960
# ---------------------------------------------------------------------------

def test_placeholder_envelope_fits_in_default_budget(tmp_path):
    """A typical corrected-placeholder shared-ctx fits within the 40960-byte budget."""
    # Build a ctx with several placeholder_mocs and a handful of real MOCs
    placeholders = [
        {"target": "Search MOC", "referenced_by": "Atlas/Software MOC.md"},
        {"target": "Games MOC", "referenced_by": "Atlas/Entertainment MOC.md"},
        {"target": "History MOC", "referenced_by": "Atlas/Humanities MOC.md"},
    ]
    mocs = [
        {"path": f"Atlas/{i} MOC.md", "title": f"Topic {i} MOC",
         "topics": ["topic"], "is_classification": False}
        for i in range(20)
    ]
    ctx: dict = {
        "schema_version": "1",
        "run_id": "budget-test",
        "mocs": mocs,
        "tag_prefixes": [],
        "classification_keywords": {},
        "placeholder_mocs": placeholders,
    }
    trimmed, _dropped = enforce_budget(ctx, max_bytes=40960)
    data = scb.serialize(trimmed)
    assert len(data) <= 40960, (
        f"Envelope should fit in 40960 bytes, got {len(data)} bytes"
    )


# ---------------------------------------------------------------------------
# T3.1-6: schema does NOT declare accumulation_index (H3)
# ---------------------------------------------------------------------------

def test_schema_has_no_accumulation_index():
    """shared-ctx.schema.json must not declare accumulation_index after T3.1."""
    schema = json.loads(SCHEMA_PATH.read_text())
    props = schema.get("properties", {})
    assert "accumulation_index" not in props, (
        "accumulation_index must be removed from shared-ctx.schema.json properties"
    )


# ---------------------------------------------------------------------------
# T3.1-7: schema validates a no-accumulation ctx (H3)
# ---------------------------------------------------------------------------

def test_schema_validates_no_accumulation_ctx():
    """Schema must validate a ctx that has no accumulation_index key."""
    ctx = {
        "schema_version": "1",
        "run_id": "schema-test",
        "mocs": [
            {"path": "Atlas/Foo MOC.md", "title": "Foo MOC",
             "topics": ["foo"], "is_classification": False}
        ],
        "tag_prefixes": [],
        "classification_keywords": {},
    }
    _validate_schema(ctx)  # must not raise


# ---------------------------------------------------------------------------
# T3.1-8: schema rejects ctx that still has accumulation_index (additionalProperties: false)
# ---------------------------------------------------------------------------

def test_schema_rejects_accumulation_index_field():
    """Schema must REJECT a ctx with accumulation_index (additionalProperties: false)."""
    try:
        import jsonschema
    except ImportError:
        import pytest
        pytest.skip("jsonschema not available")

    schema = json.loads(SCHEMA_PATH.read_text())
    ctx_with_accum = {
        "schema_version": "1",
        "run_id": "schema-reject-test",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
        "accumulation_index": {"search": ["note-a"]},
    }
    try:
        jsonschema.validate(ctx_with_accum, schema)
        raise AssertionError(
            "Schema should have rejected accumulation_index, but validation passed"
        )
    except jsonschema.ValidationError:
        pass  # Expected: schema correctly rejects the removed field


# ---------------------------------------------------------------------------
# T3.1-9: golden-baseline guard — mocs + placeholder_mocs byte-equal to T3.0
# ---------------------------------------------------------------------------

def test_golden_baseline_mocs_and_placeholder_mocs_unchanged():
    """build_mocs + build_placeholder_mocs must produce byte-identical output for
    the 4 T3.0 baseline fixtures after accumulation removal (mocs/placeholder_mocs
    arrays only — agent_step4_ac_contract is allowed to change in T3.2)."""
    if not BASELINE_PATH.exists():
        import pytest
        pytest.skip(f"Baseline not found: {BASELINE_PATH}")

    baseline = json.loads(BASELINE_PATH.read_text())
    baseline_by_fixture = {e["fixture"]: e for e in baseline["fixtures"]}

    SCENARIOS = [
        "scenario_a_accumulation_match.json",
        "scenario_b_no_match.json",
        "scenario_c_placeholder_wins.json",
        "scenario_d_absent_index.json",
    ]

    for fname in SCENARIOS:
        path = FIXTURE_SRC / fname
        if not path.exists():
            import pytest
            pytest.skip(f"Fixture not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        ctx = data["shared_ctx"]

        # Rebuild cache the same way generate.py does
        cache: dict = {
            "map_notes": [
                {"path": m["path"], "title": m["title"], "topics": m["topics"]}
                for m in ctx.get("mocs", [])
            ],
        }
        if "placeholder_mocs" in ctx:
            cache["placeholder_mocs"] = ctx["placeholder_mocs"]

        built_mocs = scb.build_mocs(cache)
        built_placeholders = scb.build_placeholder_mocs(cache)

        expected = baseline_by_fixture[fname]
        assert built_mocs == expected["mocs"], (
            f"Fixture {fname}: build_mocs() output changed after T3.1\n"
            f"  expected: {expected['mocs']}\n"
            f"  got:      {built_mocs}"
        )
        assert built_placeholders == expected["placeholder_mocs"], (
            f"Fixture {fname}: build_placeholder_mocs() output changed after T3.1\n"
            f"  expected: {expected['placeholder_mocs']}\n"
            f"  got:      {built_placeholders}"
        )
