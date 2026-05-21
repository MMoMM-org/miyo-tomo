#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_fan_resolve_tomo_block.py — T2.5: tomo: block in fan-resolve doc.

Three tests verify that the suggestions rendering pipeline emits a well-formed
`tomo:` frontmatter block with doc_type='suggestions-fan' when the input doc
has doc_variant='fan-resolve' (F-47 AC-1.4):

  test_fan_doc_emits_tomo_block        — doc_type, state, run_id, updated_at present
  test_distinguishable_from_main_suggestions — fan doc_type != main suggestions doc_type
  test_schema_validation_dev_mode      — TOMO_SCHEMA_STRICT=1 raises on bad state

The render entry point under test is suggestions-render.py::render_frontmatter,
which reads doc_variant from the suggestions-doc dict and must emit
doc_type='suggestions-fan' when doc_variant=='fan-resolve'.

Pattern mirrors test_suggestions_render_tomo_block.py (T2.2) — direct importlib
load of the render module, no subprocess, to avoid PYTHONPATH issues.
"""
from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


# ── Fixture helpers ───────────────────────────────────────────────────────────


def _make_fan_resolve_doc(run_id: str = "2026-05-21-120000-abc123") -> dict[str, Any]:
    """Minimal suggestions-doc JSON with doc_variant='fan-resolve'.

    Mirrors the output of suggestions-reducer.py --fan-resolve:
    - doc_variant set to 'fan-resolve' (set by reducer at line 938)
    - daily_notes_updates, proposed_mocs, needs_attention all empty
    - At least one section (force-atomic item)
    """
    return {
        "schema_version": "1",
        "generated": "2026-05-21T12:00:00Z",
        "run_id": run_id,
        "profile": "miyo",
        "doc_variant": "fan-resolve",
        "source_items": 1,
        "sections": [
            {
                "id": "S01",
                "stem": "Furano",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "rendered_md": (
                            "**Source:** [[Furano]]\n"
                            "**Suggested name:** Furano Day Trip\n\n"
                            "**Decision (atomic note):**\n- [x] Approve"
                        ),
                    }
                ],
            }
        ],
        "daily_notes_updates": [],
        "rendered_daily_updates_md": "",
        "decision_precedence_note": (
            "This is a Force-Atomic Resolve doc. Approve the atomic suggestions, "
            "then tick [x] Approved and re-run /inbox."
        ),
        "proposed_mocs": [],
        "needs_attention": [],
    }


def _make_primary_doc(run_id: str = "2026-05-21-120000-abc123") -> dict[str, Any]:
    """Minimal suggestions-doc JSON with doc_variant='primary'."""
    return {
        "schema_version": "1",
        "generated": "2026-05-21T12:00:00Z",
        "run_id": run_id,
        "profile": "miyo",
        "doc_variant": "primary",
        "source_items": 1,
        "sections": [
            {
                "id": "S01",
                "stem": "Wingspan",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "rendered_md": (
                            "**Source:** [[Wingspan]]\n"
                            "**Suggested name:** Wingspan Board Game Notes\n\n"
                            "**Decision (atomic note):**\n- [ ] Approve"
                        ),
                    }
                ],
            }
        ],
        "daily_notes_updates": [],
        "rendered_daily_updates_md": "",
        "decision_precedence_note": "Daily-note decisions live in the Daily Notes Updates block.",
        "proposed_mocs": [],
        "needs_attention": [],
    }


def _import_render_module():
    """Import suggestions-render.py as a module via importlib."""
    spec = importlib.util.spec_from_file_location(
        "suggestions_render",
        SCRIPTS_DIR / "suggestions-render.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _parse_frontmatter_from_lines(lines: list[str]) -> dict:
    """Parse YAML frontmatter from the list of lines returned by render_frontmatter."""
    assert lines[0] == "---", f"Expected opening ---, got {lines[0]!r}"
    assert lines[-1] == "---", f"Expected closing ---, got {lines[-1]!r}"
    inner = "\n".join(lines[1:-1])
    return yaml.safe_load(inner) or {}


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_fan_doc_emits_tomo_block() -> None:
    """render_frontmatter on a fan-resolve doc emits tomo: with doc_type='suggestions-fan',
    state='pending-approval', the input run_id, and an ISO-8601 updated_at with Z suffix."""
    run_id = "2026-05-21-120000-abc123"
    mod = _import_render_module()
    d = _make_fan_resolve_doc(run_id=run_id)

    lines = mod.render_frontmatter(d)
    fm = _parse_frontmatter_from_lines(lines)

    assert "tomo" in fm, f"'tomo' key missing from frontmatter:\n{fm}"
    tomo = fm["tomo"]

    assert tomo.get("doc_type") == "suggestions-fan", (
        f"Expected doc_type='suggestions-fan', got {tomo.get('doc_type')!r}"
    )
    assert tomo.get("state") == "pending-approval", (
        f"Expected state='pending-approval', got {tomo.get('state')!r}"
    )
    assert tomo.get("run_id") == run_id, (
        f"Expected run_id={run_id!r}, got {tomo.get('run_id')!r}"
    )

    updated_at = tomo.get("updated_at")
    assert updated_at is not None, "tomo.updated_at must be set"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", str(updated_at)), (
        f"tomo.updated_at must be ISO-8601 with Z suffix, got {updated_at!r}"
    )


def test_distinguishable_from_main_suggestions() -> None:
    """Fan doc has doc_type='suggestions-fan'; primary doc has doc_type='suggestions'.

    A byFrontmatter query for tomo.doc_type=suggestions would NOT match the fan-doc.
    """
    run_id = "2026-05-21-120000-abc123"
    mod = _import_render_module()

    fan_lines = mod.render_frontmatter(_make_fan_resolve_doc(run_id=run_id))
    main_lines = mod.render_frontmatter(_make_primary_doc(run_id=run_id))

    fan_fm = _parse_frontmatter_from_lines(fan_lines)
    main_fm = _parse_frontmatter_from_lines(main_lines)

    fan_tomo = fan_fm.get("tomo") or {}
    main_tomo = main_fm.get("tomo") or {}

    assert fan_tomo.get("doc_type") == "suggestions-fan", (
        f"Expected fan doc_type='suggestions-fan', got {fan_tomo.get('doc_type')!r}"
    )
    assert main_tomo.get("doc_type") == "suggestions", (
        f"Expected main doc_type='suggestions', got {main_tomo.get('doc_type')!r}"
    )
    assert fan_tomo.get("doc_type") != main_tomo.get("doc_type"), (
        "Fan doc and main suggestions doc must have distinct doc_type values"
    )


def test_schema_validation_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """TOMO_SCHEMA_STRICT=1: an invalid state for suggestions-fan raises SchemaValidationError.

    We exercise build_tomo_block directly from lib.doc_frontmatter to verify
    the schema gate works for the suggestions-fan doc_type.
    """
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")

    lib_path = SCRIPTS_DIR / "lib" / "doc_frontmatter.py"
    lib_spec = importlib.util.spec_from_file_location("doc_frontmatter", lib_path)
    lib_mod = importlib.util.module_from_spec(lib_spec)
    assert lib_spec.loader is not None
    lib_spec.loader.exec_module(lib_mod)

    SchemaValidationError = lib_mod.SchemaValidationError  # type: ignore[attr-defined]
    build_tomo_block_fn = lib_mod.build_tomo_block  # type: ignore[attr-defined]

    # suggestions-fan only allows "pending-approval" or "approved" states.
    # Passing "invalid-state" must trigger SchemaValidationError in strict mode.
    with pytest.raises(SchemaValidationError):
        build_tomo_block_fn(
            doc_type="suggestions-fan",
            state="invalid-state",
            run_id="test-run-id",
        )
