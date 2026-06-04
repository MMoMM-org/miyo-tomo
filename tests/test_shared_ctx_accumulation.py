#!/usr/bin/env python3
# version: 0.1.0
"""test_shared_ctx_accumulation.py — Tests for T3.2 of spec 015 (F-34).

Covers:
  - build_accumulation_index() passthrough, absent-field, drift-guard
  - main() conditional-add (A2/A6): field omitted when empty, present when non-empty
  - enforce_budget() accumulation trim: smallest-first, alphabetical tiebreak, count log (A4)
  - Schema validation: shared-ctx.schema.json accepts both shapes

RED before GREEN discipline (CON-1/TDD).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "shared-ctx.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))

# shared-ctx-builder.py has a hyphen — load via importlib
_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)

build_accumulation_index = scb.build_accumulation_index  # RED until implemented
enforce_budget = scb.enforce_budget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_ctx(*, include_accumulation: dict | None = None) -> dict:
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
    if include_accumulation is not None:
        ctx["accumulation_index"] = include_accumulation
    return ctx


def _validate_schema(obj: dict) -> None:
    """Validate obj against shared-ctx.schema.json. Structural fallback if jsonschema absent."""
    try:
        import jsonschema
        schema = json.loads(SCHEMA_PATH.read_text())
        jsonschema.validate(obj, schema)
    except ImportError:
        # jsonschema not installed on host — structural validation
        assert isinstance(obj, dict)
        assert "schema_version" in obj
        assert "mocs" in obj
        if "accumulation_index" in obj:
            ai = obj["accumulation_index"]
            assert isinstance(ai, dict), "accumulation_index must be an object"
            for k, v in ai.items():
                assert isinstance(k, str)
                assert isinstance(v, list)
                for item in v:
                    assert isinstance(item, str)


def _run_main_with_cache(tmp_path: Path, cache: dict, run_id: str) -> dict:
    """Run scb.main() with a minimal patched environment; return the parsed output JSON.

    Patches out the parts of main() that require a full vault (tags, profile, reconcile)
    so tests focus on the accumulation_index conditional-add logic.
    """
    import yaml

    cache_file = tmp_path / "cache.yaml"
    vault_cfg_file = tmp_path / "vault-config.yaml"
    out_file = tmp_path / "shared-ctx.json"
    profiles_dir = REPO_ROOT / "tomo" / "profiles"

    vault_cfg = {"profile": "miyo"}
    cache_file.write_text(yaml.dump(cache))
    vault_cfg_file.write_text(yaml.dump(vault_cfg))

    with patch("sys.argv", [
        "shared-ctx-builder.py",
        "--cache", str(cache_file),
        "--vault-config", str(vault_cfg_file),
        "--profiles-dir", str(profiles_dir),
        "--output", str(out_file),
        "--run-id", run_id,
        "--skip-reconcile",
    ]), patch.object(scb, "build_tag_prefixes", return_value=[]), \
       patch.object(scb, "build_classification_keywords", return_value={}), \
       patch.object(scb, "build_daily_notes", return_value=None):
        rc = scb.main()

    assert rc == 0, f"main() returned {rc}"
    return json.loads(out_file.read_text())


# ---------------------------------------------------------------------------
# T3.2-1: build_accumulation_index passthrough
# ---------------------------------------------------------------------------

def test_build_accumulation_index_passthrough():
    """Well-formed unclassified_topic_clusters passes through unchanged."""
    clusters = {
        "search": ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
        "games":  ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
    }
    cache = {"unclassified_topic_clusters": clusters}
    result = build_accumulation_index(cache)
    assert result == clusters, f"Expected passthrough, got {result}"


# ---------------------------------------------------------------------------
# T3.2-2: build_accumulation_index absent → {} (A6)
# ---------------------------------------------------------------------------

def test_build_accumulation_index_empty_when_absent():
    """Missing unclassified_topic_clusters → empty dict (A6 — legitimately empty vault)."""
    result = build_accumulation_index({})
    assert result == {}, f"Expected {{}}, got {result}"


# ---------------------------------------------------------------------------
# T3.2-3: build_accumulation_index drift guard — non-dict → {}
# ---------------------------------------------------------------------------

def test_build_accumulation_index_drift_guard():
    """Non-dict value for unclassified_topic_clusters → empty dict (drift guard)."""
    for bad_value in [None, [], "string", 42]:
        result = build_accumulation_index({"unclassified_topic_clusters": bad_value})
        assert result == {}, \
            f"Expected {{}} for bad value {bad_value!r}, got {result}"


# ---------------------------------------------------------------------------
# T3.2-4: main() omits field when empty (A2/A6)
# ---------------------------------------------------------------------------

def test_main_omits_field_when_empty(tmp_path):
    """When unclassified_topic_clusters is empty, accumulation_index must be absent."""
    cache = {
        "map_notes": [],
        "placeholder_mocs": [],
        "unclassified_topic_clusters": {},   # empty → must be omitted
    }
    ctx = _run_main_with_cache(tmp_path, cache, "test-run-empty")
    assert "accumulation_index" not in ctx, \
        f"accumulation_index should be absent when empty, got keys: {list(ctx)}"
    _validate_schema(ctx)


# ---------------------------------------------------------------------------
# T3.2-5: main() includes field when present (A2)
# ---------------------------------------------------------------------------

def test_main_includes_field_when_present(tmp_path):
    """When unclassified_topic_clusters is non-empty, accumulation_index appears in output."""
    clusters = {
        "search": ["alpha-beta-pruning", "minimax"],
        "games":  ["alpha-beta-pruning", "minimax"],
    }
    cache = {
        "map_notes": [],
        "placeholder_mocs": [],
        "unclassified_topic_clusters": clusters,
    }
    ctx = _run_main_with_cache(tmp_path, cache, "test-run-present")
    assert "accumulation_index" in ctx, \
        f"accumulation_index should be present, got keys: {list(ctx)}"
    assert ctx["accumulation_index"] == clusters
    _validate_schema(ctx)


# ---------------------------------------------------------------------------
# T3.2-6: enforce_budget drops smallest clusters first (A4)
# ---------------------------------------------------------------------------

def test_enforce_budget_drops_smallest_clusters_first():
    """Over-budget ctx: clusters dropped by smallest member-count first."""
    accumulation = {
        "search": ["alpha-beta-pruning", "minimax", "mcts"],  # 3 members — keep longest
        "medium": ["note-a", "note-b"],                        # 2 members
        "rare":   ["only-one"],                                # 1 member — drop first
    }
    ctx = _minimal_ctx(include_accumulation=accumulation)
    full_size = len(scb.serialize(ctx))

    # Make budget just tight enough that the accumulation trim pass is reached
    # but only one cluster needs dropping. Remove all moc topics headroom first
    # by using a budget that forces the accumulation pass.
    # We set budget = full_size - (bytes of "rare" entry) - 1
    # Simplest: set budget to 1 byte to force all cluster drops, then verify order.
    # Better: use full_size - 1 and verify "rare" drops before "medium".

    # Drop mocs topics to make space evaluation cleaner (avoid pass 5 interference)
    ctx["mocs"] = []  # no moc topics to drop in pass 5
    ctx_size = len(scb.serialize(ctx))

    # Force exactly one drop from accumulation
    import json as _json
    rare_entry_size = len(_json.dumps({"rare": ["only-one"]}, separators=(",", ":"))) - 2  # approx
    tight_budget = ctx_size - 1

    trimmed, dropped, acc_total, acc_kept = enforce_budget(ctx, tight_budget)

    ai = trimmed.get("accumulation_index", {})
    # "rare" (1 member) must have been dropped first
    assert "rare" not in ai, \
        f"'rare' (1 member) should be first dropped, but accumulation_index={ai}"
    # "search" (3 members) must survive longest
    assert "search" in ai, \
        f"'search' (3 members) should survive, but accumulation_index={ai}"
    assert acc_total == 3
    assert acc_kept < 3


# ---------------------------------------------------------------------------
# T3.2-6b: alphabetical tiebreak within same member count
# ---------------------------------------------------------------------------

def test_enforce_budget_alphabetical_tiebreak():
    """When two clusters have the same member count, the alphabetically later one drops first."""
    accumulation = {
        "zebra":  ["note-a", "note-b"],   # 2 members, alpha-later → drops first
        "alpaca": ["note-c", "note-d"],   # 2 members, alpha-earlier → survives
    }
    ctx = _minimal_ctx(include_accumulation=accumulation)
    ctx["mocs"] = []  # no moc topics to drain in pass 5
    ctx_size = len(scb.serialize(ctx))
    tight_budget = ctx_size - 1

    trimmed, _, acc_total, acc_kept = enforce_budget(ctx, tight_budget)

    ai = trimmed.get("accumulation_index", {})
    # At least one was dropped; if only one, it must be "zebra" (alpha-later)
    if acc_kept == 1:
        assert "zebra" not in ai, \
            "zebra (alpha-later, same count) should drop before alpaca"
        assert "alpaca" in ai, \
            "alpaca (alpha-earlier) should survive"


# ---------------------------------------------------------------------------
# T3.2-7: enforce_budget logs total and kept counts (A4)
# ---------------------------------------------------------------------------

def test_enforce_budget_logs_total_and_kept(capsys):
    """Trim pass logs accumulation_clusters_total=N accumulation_clusters_kept=K to stderr."""
    accumulation = {
        "search": ["a", "b", "c"],
        "games":  ["d", "e", "f"],
        "rare":   ["x"],
    }
    ctx = _minimal_ctx(include_accumulation=accumulation)
    ctx["mocs"] = []  # skip pass 5
    ctx_size = len(scb.serialize(ctx))
    # Force drop of at least one cluster
    tight_budget = ctx_size - 1

    enforce_budget(ctx, tight_budget)

    captured = capsys.readouterr()
    assert "accumulation_clusters_total=" in captured.err, \
        f"Expected 'accumulation_clusters_total=' in stderr, got: {captured.err!r}"
    assert "accumulation_clusters_kept=" in captured.err, \
        f"Expected 'accumulation_clusters_kept=' in stderr, got: {captured.err!r}"
