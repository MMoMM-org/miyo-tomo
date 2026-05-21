#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_moc_proposal_tomo_block.py — T2.4: tomo: block in moc-proposal.

Four tests verify that suggestions-reducer.py --moc-proposal-mode emits a
well-formed `tomo:` frontmatter block (F-47 AC-1.4):

  test_proposal_doc_emits_tomo_block      — doc_type, state, run_id, updated_at present
  test_no_legacy_tag_emitted              — no tomo/* tag in frontmatter tags array
  test_existing_moc_proposal_fields_preserved — clusters/supporting_items/narrative untouched
  test_schema_validation_dev_mode         — TOMO_SCHEMA_STRICT=1 raises on bad input
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load suggestions-reducer.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("suggestions_reducer", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

render_moc_proposal_doc = _mod.render_moc_proposal_doc  # type: ignore[attr-defined]


# ── Stub config ──────────────────────────────────────────────────────────────


class _Cfg:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results


# ── Fixture builder helpers (mirror pattern from test_reducer_moc_proposal_mode.py) ──


def _cluster(
    cluster_id: str,
    *,
    title: str,
    confidence: float,
    candidate_stems: list[str],
    topic_keywords: list[str] | None = None,
    slug: str | None = None,
    location: str = "Atlas/200 Maps/",
    template: str = "t_moc_tomo",
    existing_up: list[dict] | None = None,
) -> dict:
    return {
        "cluster_id": cluster_id,
        "title": title,
        "confidence": confidence,
        "candidate_stems": candidate_stems,
        "topic_keywords": topic_keywords or [],
        "slug": slug or title.lower().replace(" ", "-"),
        "location": location,
        "template": template,
        "existing_up": existing_up or [],
    }


def _discovery_report(run_id: str = "2026-05-21-120000-abc123") -> dict:
    """Minimal DiscoveryReport with one cluster, matching the live moc-architect output."""
    return {
        "schema_version": "1",
        "run_id": run_id,
        "mode": "tag",
        "trigger_arg": "topic/applied/zsh",
        "profile": "miyo",
        "candidates_total": 2,
        "candidates_after_prefilter": 2,
        "candidates_capped": False,
        "candidates": [
            {"stem": "zsh-aliases", "path": "Atlas/202 Notes/zsh-aliases.md",
             "topics": ["zsh", "shell"], "existing_up": None,
             "existing_up_broken": False, "classification": None, "level": 0},
            {"stem": "iterm-config", "path": "Atlas/202 Notes/iterm-config.md",
             "topics": ["terminal", "shell"], "existing_up": None,
             "existing_up_broken": False, "classification": None, "level": 0},
        ],
        "topic_clusters": [
            _cluster(
                "MOC01",
                title="Shell & Terminal (MOC)",
                confidence=0.78,
                candidate_stems=["zsh-aliases", "iterm-config"],
                topic_keywords=["shell", "terminal", "zsh"],
                slug="shell-terminal-moc",
            )
        ],
        "parent_options_per_cluster": {
            "MOC01": [
                {"moc_stem": "2600 - Applied Sciences",
                 "confidence": 0.85,
                 "label": "Applied Sciences (Dewey 2600)"},
            ]
        },
        "duplicates_skipped": [],
        "squelched": [],
        "abort_reason": None,
        "abort_message": None,
        "extracted_via_llm_count": 0,
        "cache_miss_batches_used": 0,
    }


def _parse_frontmatter(body: str) -> dict:
    """Extract and parse the YAML frontmatter from a rendered proposal-doc body."""
    match = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert match, f"No YAML frontmatter block found in body:\n{body[:300]}"
    return yaml.safe_load(match.group(1)) or {}


# ── Tests ────────────────────────────────────────────────────────────────────


def test_proposal_doc_emits_tomo_block() -> None:
    """render_moc_proposal_doc emits tomo: block with doc_type, state, run_id, updated_at."""
    run_id = "2026-05-21-120000-abc123"
    report = _discovery_report(run_id=run_id)

    _filename, body = render_moc_proposal_doc(report, _Cfg())
    fm = _parse_frontmatter(body)

    assert "tomo" in fm, f"'tomo' key missing from frontmatter:\n{fm}"
    tomo = fm["tomo"]

    assert tomo.get("doc_type") == "moc-proposal", (
        f"Expected doc_type='moc-proposal', got {tomo.get('doc_type')!r}"
    )
    assert tomo.get("state") == "pending-accept", (
        f"Expected state='pending-accept', got {tomo.get('state')!r}"
    )
    assert tomo.get("run_id") == run_id, (
        f"Expected run_id={run_id!r}, got {tomo.get('run_id')!r}"
    )

    updated_at = tomo.get("updated_at")
    assert updated_at is not None, "tomo.updated_at must be set"
    # Must be ISO-8601 with Z suffix (build_tomo_block auto-sets this)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", str(updated_at)), (
        f"tomo.updated_at must be ISO-8601 with Z suffix, got {updated_at!r}"
    )


def test_no_legacy_tag_emitted() -> None:
    """No tag entry matching tomo/* or */moc-proposal/pending-accept in frontmatter tags."""
    report = _discovery_report()

    _filename, body = render_moc_proposal_doc(report, _Cfg())
    fm = _parse_frontmatter(body)

    tags = fm.get("tags") or []
    # Ensure no lifecycle tag sneaked in (F-47 v1.2 lock: state is frontmatter-only)
    for tag in tags:
        assert not str(tag).startswith("tomo/"), (
            f"Legacy tomo/* tag found: {tag!r} (F-47 v1.2 forbids lifecycle tags)"
        )
        assert "moc-proposal" not in str(tag), (
            f"Legacy moc-proposal tag found: {tag!r} (F-47 v1.2 forbids lifecycle tags)"
        )
        assert "pending-accept" not in str(tag), (
            f"Legacy pending-accept tag found: {tag!r} (F-47 v1.2 forbids lifecycle tags)"
        )


def test_existing_moc_proposal_fields_preserved() -> None:
    """Pre-F-47 proposal-doc fields (type, proposal_kind, created, trigger, status,
    tomo_skip_inbox_analysis) are all still present after adding the tomo: block."""
    report = _discovery_report()

    _filename, body = render_moc_proposal_doc(report, _Cfg())
    fm = _parse_frontmatter(body)

    # These fields were part of the F-43 proposal-doc shape and must remain
    assert fm.get("type") == "tomo-proposal", (
        f"Expected type='tomo-proposal', got {fm.get('type')!r}"
    )
    assert fm.get("proposal_kind") == "moc", (
        f"Expected proposal_kind='moc', got {fm.get('proposal_kind')!r}"
    )
    assert fm.get("created") is not None, "Expected 'created' field to be present"
    assert fm.get("trigger") is not None, "Expected 'trigger' field to be present"
    assert fm.get("status") == "pending", (
        f"Expected status='pending', got {fm.get('status')!r}"
    )
    assert fm.get("tomo_skip_inbox_analysis") is True, (
        f"Expected tomo_skip_inbox_analysis=True, got {fm.get('tomo_skip_inbox_analysis')!r}"
    )

    # Body clusters section must still be rendered (regression check)
    assert "### MOC01" in body, "Cluster section missing from body"
    assert "Shell & Terminal (MOC)" in body, "Cluster title missing from body"


def test_schema_validation_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """TOMO_SCHEMA_STRICT=1: an invalid state combination raises SchemaValidationError.

    We patch build_tomo_block at the lib.doc_frontmatter module level to force
    an invalid block through the validator, verifying that the schema gate works.
    """
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")

    # Load the lib directly so we can verify SchemaValidationError is importable
    lib_path = SCRIPTS_DIR / "lib" / "doc_frontmatter.py"
    lib_spec = importlib.util.spec_from_file_location("doc_frontmatter", lib_path)
    lib_mod = importlib.util.module_from_spec(lib_spec)
    assert lib_spec.loader is not None
    lib_spec.loader.exec_module(lib_mod)

    SchemaValidationError = lib_mod.SchemaValidationError  # type: ignore[attr-defined]
    build_tomo_block_fn = lib_mod.build_tomo_block  # type: ignore[attr-defined]

    # "moc-proposal" doc_type only allows "pending-accept" or "accepted" states.
    # Passing "invalid-state" must trigger SchemaValidationError in strict mode.
    with pytest.raises(SchemaValidationError):
        build_tomo_block_fn(
            doc_type="moc-proposal",
            state="invalid-state",
            run_id="test-run-id",
        )
