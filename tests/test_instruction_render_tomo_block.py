#!/usr/bin/env python3
# version: 0.2.0
"""test_instruction_render_tomo_block.py — tomo: block emission in instructions.md.

T1.3 (XDD-018): Verifies that instruction-render.py injects a valid
`tomo:` block into the instructions.md frontmatter with sources=[{path}] list
replacing the old source_* kwargs pattern.

Five tests:
  1. test_emits_tomo_block_from_suggestions_source
  2. test_emits_tomo_block_from_moc_proposal_source
  3. test_emits_tomo_block_from_suggestions_fan_source
  4. test_new_run_id_not_upstream_run_id
  5. test_schema_validation_blocks_invalid_state_in_dev_mode

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
      docs/XDD/specs/018-agent-architecture-cleanup/
AC:   AC-1.3 (instruction-render emits sources cross-ref),
      AC-5.1 (bundled create_moc + child refs from moc-proposal)
SDD:  §Implementation Gotchas — new run_id, not upstream's
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)

# Import after module load so the symbols are available.
from lib.doc_frontmatter import SchemaValidationError  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(md_text: str) -> dict:
    """Parse YAML frontmatter from a markdown string.

    Returns the parsed dict, or {} if no frontmatter is found.
    """
    import yaml

    if not md_text.startswith("---"):
        return {}
    end = md_text.find("\n---", 3)
    if end == -1:
        return {}
    fm_str = md_text[3:end].strip()
    return yaml.safe_load(fm_str) or {}


def _make_metadata(
    upstream_type: str,
    upstream_path: str,
    run_id: str = "pass2-r1",
    generated: str = "2026-05-21T14:00:00Z",
    profile: str | None = None,
    tomo_version: str | None = None,
) -> dict:
    """Build a metadata dict as instruction-render main() assembles it.

    Mirrors the fields passed to render_instructions_md().
    """
    return {
        "upstream_type": upstream_type,
        "upstream_path": upstream_path,
        "run_id": run_id,
        "generated": generated,
        "profile": profile,
        "tomo_version": tomo_version,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_emits_tomo_block_from_suggestions_source(monkeypatch):
    """instructions.md frontmatter has tomo.sources with upstream path and no source_* keys."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    upstream_path = "100 Inbox/2026-05-21T12:00_suggestions.md"
    metadata = _make_metadata(
        upstream_type="suggestions",
        upstream_path=upstream_path,
        run_id="pass2-r1",
    )
    md = ir.render_instructions_md([], metadata, {})
    fm = _parse_frontmatter(md)
    tomo = fm.get("tomo", {})

    assert tomo.get("doc_type") == "instructions"
    assert tomo.get("state") == "pending-apply"
    assert tomo.get("sources") is not None
    sources = tomo["sources"]
    assert len(sources) == 1
    assert sources[0]["path"] == upstream_path
    # No old source_* keys
    source_keys = [k for k in tomo if k.startswith("source_")]
    assert source_keys == [], f"Expected no source_* keys, got {source_keys}"


def test_emits_tomo_block_from_moc_proposal_source(monkeypatch):
    """instructions.md frontmatter has tomo.sources with moc-proposal upstream path."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    upstream_path = "100 Inbox/2026-05-21T10:00_moc-proposal-notemaking.md"
    metadata = _make_metadata(
        upstream_type="moc-proposal",
        upstream_path=upstream_path,
        run_id="pass2-r2",
    )
    md = ir.render_instructions_md([], metadata, {})
    fm = _parse_frontmatter(md)
    tomo = fm.get("tomo", {})

    assert tomo.get("doc_type") == "instructions"
    assert tomo.get("state") == "pending-apply"
    assert tomo.get("sources") is not None
    sources = tomo["sources"]
    assert len(sources) == 1
    assert sources[0]["path"] == upstream_path
    # No old source_* keys
    source_keys = [k for k in tomo if k.startswith("source_")]
    assert source_keys == [], f"Expected no source_* keys, got {source_keys}"


def test_emits_tomo_block_from_suggestions_fan_source(monkeypatch):
    """instructions.md frontmatter has tomo.sources with suggestions-fan upstream path."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    upstream_path = "100 Inbox/2026-05-21_suggestions-fan.md"
    metadata = _make_metadata(
        upstream_type="suggestions-fan",
        upstream_path=upstream_path,
        run_id="pass2-r3",
    )
    md = ir.render_instructions_md([], metadata, {})
    fm = _parse_frontmatter(md)
    tomo = fm.get("tomo", {})

    assert tomo.get("doc_type") == "instructions"
    assert tomo.get("state") == "pending-apply"
    assert tomo.get("sources") is not None
    sources = tomo["sources"]
    assert len(sources) == 1
    assert sources[0]["path"] == upstream_path
    # No old source_* keys
    source_keys = [k for k in tomo if k.startswith("source_")]
    assert source_keys == [], f"Expected no source_* keys, got {source_keys}"


def test_new_run_id_not_upstream_run_id(monkeypatch):
    """instructions.md uses the Pass-2 run_id, NOT the upstream suggestions run_id.

    SDD §Implementation Gotchas: Pass-2 instructions emit a NEW run_id
    (the current /inbox invocation's), not the upstream suggestions doc's.
    """
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    upstream_path = "100 Inbox/2026-05-21T09:00_suggestions.md"
    metadata = _make_metadata(
        upstream_type="suggestions",
        upstream_path=upstream_path,
        run_id="pass2-r2",  # Pass-2 run ID — NOT the upstream's
    )
    # Simulate the upstream having a different run_id by passing it
    # separately to confirm the renderer uses metadata["run_id"].
    metadata["upstream_run_id"] = "upstream-r1"

    md = ir.render_instructions_md([], metadata, {})
    fm = _parse_frontmatter(md)
    tomo = fm.get("tomo", {})

    assert tomo.get("run_id") == "pass2-r2", (
        f"Expected pass2-r2, got {tomo.get('run_id')!r}"
    )
    assert tomo.get("run_id") != "upstream-r1"


def test_emits_tomo_block_when_run_id_set_but_no_upstream_type(monkeypatch, capsys):
    """tomo: block is emitted without sources when run_id set but upstream_type is None.

    Documented behavior path (SDD §_build_tomo_block_for_instructions):
    - run_id present → tomo block IS built (not None)
    - upstream_type is None → no sources emitted
    - No warning printed (warning only fires for EXPLICITLY UNKNOWN upstream_type)

    AC-1.3 edge case: instructions.md still has a valid tomo: block even when
    the upstream doc type is unknown/absent.
    """
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    metadata = {
        "upstream_type": None,
        "upstream_path": None,
        "run_id": "pass2-r1",
        "generated": "2026-05-21T14:00:00Z",
        "profile": None,
        "tomo_version": None,
    }
    md = ir.render_instructions_md([], metadata, {})
    fm = _parse_frontmatter(md)
    tomo = fm.get("tomo", {})

    assert tomo, "Expected tomo: block to be present"
    assert tomo.get("doc_type") == "instructions"
    assert tomo.get("state") == "pending-apply"
    assert tomo.get("run_id") == "pass2-r1"

    # No sources field — upstream_type=None means no cross-ref, not an error
    assert "sources" not in tomo, f"Expected no sources key, got {tomo.get('sources')}"
    # No old source_* keys either
    source_keys = [k for k in tomo if k.startswith("source_")]
    assert source_keys == [], f"Expected no source_* keys, got {source_keys}"

    # No warning emitted — silent omission is intentional for falsy upstream_type
    captured = capsys.readouterr()
    assert "[warn]" not in captured.err, (
        f"Unexpected warning for upstream_type=None: {captured.err!r}"
    )


def test_legacy_source_suggestions_path_when_no_run_id():
    """Legacy path: top-level source_suggestions emitted when run_id is absent.

    Pre-F-47 callers supply source_suggestions but no run_id / upstream_type.
    render_instructions_md must:
    - emit source_suggestions: at the TOP LEVEL of frontmatter
    - NOT emit a tomo: block (run_id is the gate)

    Backward-compat guarantee from render_instructions_md docstring comment.
    """
    metadata = {
        "source_suggestions": "inbox/x.md",
        "run_id": None,
        "upstream_type": None,
        "upstream_path": None,
        "generated": "2026-05-21T14:00:00Z",
        "profile": None,
        "tomo_version": None,
    }
    md = ir.render_instructions_md([], metadata, {})
    fm = _parse_frontmatter(md)

    # Top-level source_suggestions key must be present
    assert "source_suggestions" in fm, (
        "Expected top-level source_suggestions in frontmatter for legacy path"
    )
    assert fm["source_suggestions"] == "inbox/x.md"

    # No tomo: block when run_id is absent
    assert "tomo" not in fm, (
        "Expected NO tomo: block when run_id is None (legacy path)"
    )


def test_schema_validation_blocks_invalid_state_in_dev_mode(monkeypatch):
    """In dev mode (TOMO_SCHEMA_STRICT=1), an invalid state raises SchemaValidationError."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    # Inject a metadata dict with a bogus state via a test-only override.
    # We can't easily trigger this through render_instructions_md's normal
    # path (it always builds with state="pending-apply"), so we test the
    # build_tomo_block path directly — that is the validation gate guarding
    # every producer write (AC-1.5).
    from lib.doc_frontmatter import build_tomo_block

    with pytest.raises(SchemaValidationError):
        build_tomo_block(
            doc_type="instructions",
            state="totally-bogus-state",
            run_id="r1",
            sources=[{"path": "100 Inbox/test.md"}],
        )
