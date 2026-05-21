#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_render_tomo_block.py — T2.2 (F-47 Phase 2): suggestions-render.py emits tomo: block.

Covers:
  AC-1.2  suggestions doc carries doc_type=suggestions, state=pending-approval, run_id, updated_at
  §6.1    Phase C3 — render emits tomo: block, no mirrored lifecycle tag (v1.2 lock)
  ADR-4   TOMO_SCHEMA_STRICT=1 causes SchemaValidationError when invalid state is produced

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
"""
from __future__ import annotations

import importlib
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


# ---------------------------------------------------------------------------
# Minimal suggestions-doc fixture (mirrors real suggestions-doc.json shape)
# ---------------------------------------------------------------------------

def make_suggestions_doc(run_id: str = "2026-05-21-1430-abc123") -> dict[str, Any]:
    """Return the minimum valid suggestions-doc dict that render_frontmatter accepts."""
    return {
        "schema_version": "1",
        "generated": "2026-05-21T14:30:00Z",
        "run_id": run_id,
        "profile": "miyo",
        "doc_variant": "primary",
        "source_items": 2,
        "sections": [
            {
                "id": "S01",
                "stem": "Test Note",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "rendered_md": "**Suggested name:** Test Note — Sample\n\n**Decision (atomic note):**\n- [ ] Approve",
                    }
                ],
            }
        ],
        "daily_notes_updates": [],
        "proposed_mocs": [],
        "needs_attention": [],
    }


# ---------------------------------------------------------------------------
# Import helpers — import render functions from the scripts dir
# ---------------------------------------------------------------------------

def _import_render_frontmatter():
    """Import render_frontmatter from suggestions-render.py.

    suggestions-render.py lives at tomo/scripts/suggestions-render.py.
    It is not a package; we load it as a module via importlib.
    """
    spec = importlib.util.spec_from_file_location(
        "suggestions_render",
        SCRIPTS_DIR / "suggestions-render.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# T2.2 tests
# ---------------------------------------------------------------------------


class TestSuggestionsRenderTomoBlock:
    """Verify suggestions-render.py emits a correct tomo: block in frontmatter."""

    def test_emits_tomo_block_with_correct_fields(self):
        """render_frontmatter includes tomo: with doc_type, state, run_id, updated_at."""
        mod = _import_render_frontmatter()
        run_id = "2026-05-21-1430-abc123"
        d = make_suggestions_doc(run_id=run_id)

        lines = mod.render_frontmatter(d)
        raw_yaml = "\n".join(lines).strip("---").strip()
        fm = yaml.safe_load(raw_yaml)

        assert "tomo" in fm, "tomo: key must be present in frontmatter"
        tomo = fm["tomo"]
        assert isinstance(tomo, dict), "tomo: must be a dict"
        assert tomo["doc_type"] == "suggestions"
        assert tomo["state"] == "pending-approval"
        assert tomo["run_id"] == run_id
        assert "updated_at" in tomo, "updated_at must be auto-set"

    def test_updated_at_is_valid_iso8601_with_z_suffix(self):
        """tomo.updated_at is a valid ISO-8601 UTC string ending in Z."""
        mod = _import_render_frontmatter()
        d = make_suggestions_doc()

        lines = mod.render_frontmatter(d)
        raw_yaml = "\n".join(lines).strip("---").strip()
        fm = yaml.safe_load(raw_yaml)

        updated_at = fm["tomo"]["updated_at"]
        assert isinstance(updated_at, str), "updated_at must be a string"
        assert updated_at.endswith("Z"), f"updated_at must end in Z, got: {updated_at!r}"
        # ISO-8601 basic pattern: YYYY-MM-DDTHH:MM:SSZ
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        assert iso_pattern.match(updated_at), (
            f"updated_at is not valid ISO-8601 UTC: {updated_at!r}"
        )

    def test_no_mirrored_lifecycle_tag(self):
        """No tag matching tomo/* or */suggestions/* patterns in rendered output (v1.2 lock)."""
        mod = _import_render_frontmatter()
        d = make_suggestions_doc()

        lines = mod.render_frontmatter(d)
        raw_yaml = "\n".join(lines).strip("---").strip()
        fm = yaml.safe_load(raw_yaml)

        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        tomo_tag_pattern = re.compile(
            r"(^tomo/|/suggestions/|/pending-approval)", re.IGNORECASE
        )
        for tag in tags:
            assert not tomo_tag_pattern.search(str(tag)), (
                f"Mirrored lifecycle tag found (v1.2 lock violated): {tag!r}"
            )

    def test_schema_validation_failure_in_dev_mode_blocks_render(self, monkeypatch):
        """TOMO_SCHEMA_STRICT=1 + invalid state causes SchemaValidationError.

        Strategy: monkeypatch build_tomo_block in the loaded render module so it
        passes state='applied' (illegal for suggestions doc_type). After GREEN
        implementation, build_tomo_block is a module-level name in suggestions-render.py,
        so monkeypatch.setattr works directly on the loaded module object.
        """
        monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")

        mod = _import_render_frontmatter()

        import importlib as _importlib
        lib_mod = _importlib.import_module("lib.doc_frontmatter")
        _importlib.reload(lib_mod)
        SchemaValidationError = lib_mod.SchemaValidationError
        real_build = lib_mod.build_tomo_block

        # Patch the module-level name in the render module so render_frontmatter
        # indirectly calls our wrapper that injects an illegal state.
        def _bad_build_tomo_block(doc_type, state, run_id, **kwargs):
            return real_build(
                doc_type=doc_type,
                state="applied",  # illegal for doc_type=suggestions
                run_id=run_id,
                **kwargs,
            )

        # The attribute must exist after GREEN implementation; this will raise
        # AttributeError if the import was not added (still a useful failure).
        monkeypatch.setattr(mod, "build_tomo_block", _bad_build_tomo_block)

        d = make_suggestions_doc()
        with pytest.raises(SchemaValidationError):
            mod.render_frontmatter(d)

    def test_frontmatter_yaml_well_formed(self):
        """render_frontmatter output between --- delimiters parses as valid YAML with tomo: dict.

        Repro-guard for feedback_frontmatter_newline_guard: ensures no malformed
        lines around the tomo: block cause yaml.safe_load to fail or return a scalar.
        """
        mod = _import_render_frontmatter()
        d = make_suggestions_doc()

        lines = mod.render_frontmatter(d)
        assert lines[0] == "---", "First line must be opening ---"
        assert lines[-1] == "---", "Last line must be closing ---"

        # Everything between the two --- delimiters
        inner_lines = lines[1:-1]
        raw_yaml = "\n".join(inner_lines)

        fm = yaml.safe_load(raw_yaml)
        assert isinstance(fm, dict), "Frontmatter must parse to a dict"
        assert "tomo" in fm, "tomo: key must be present"
        assert isinstance(fm["tomo"], dict), (
            "tomo: value must resolve to a sub-dict (not a scalar/None)"
        )
