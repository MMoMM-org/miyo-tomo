#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_orphan_render.py — T2.4: orphan link-or-create render.

Gate-named tests for rendering DiscoveryReport.orphan_suggestions (the T2.3
OrphanLinkSuggestion shape: {stem, path, kind, mode, candidates:[{target_moc,
score}], reason}) into the /moc-propose proposal-doc via
suggestions-reducer.render_moc_proposal_doc.

Assertions are locked to the ACTUAL reducer output (rendered once, then asserted
on the real strings — feedback_fixture_from_live_render), not invented markdown.

CON-3: /moc-propose writes NO vault note — render_moc_proposal_doc is a pure
(report, config) -> (filename, body) function with no Kado client, so the render
path cannot perform a kado-write. test_orphan_render_produces_proposal_doc_only_
no_vault_write guards that contract.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("suggestions_reducer", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

render_moc_proposal_doc = _mod.render_moc_proposal_doc  # type: ignore[attr-defined]


class _Cfg:
    """Duck-typed config stub exposing only max_results."""

    def __init__(self, max_results: int = 5):
        self.max_results = max_results


def _orphan(stem, *, mode, kind="note", candidates=None, reason=None, path=None) -> dict:
    return {
        "stem": stem,
        "path": path or f"Atlas/202 Notes/{stem}.md",
        "kind": kind,
        "mode": mode,
        "candidates": candidates or [],
        "reason": reason,
    }


def _report(orphan_suggestions: list[dict]) -> dict:
    return {
        "schema_version": "1",
        "run_id": "test-run",
        "mode": "tag",
        "trigger_arg": "topic/x",
        "profile": "miyo",
        "topic_clusters": [],
        "parent_options_per_cluster": {},
        "duplicates_skipped": [],
        "squelched": [],
        "orphan_suggestions": orphan_suggestions,
        "abort_reason": None,
        "abort_message": None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Gate-named tests
# ──────────────────────────────────────────────────────────────────────────────

def test_orphan_render_link_existing_top3_options():
    """A link_existing suggestion renders its top-3 link options (OQ-4)."""
    report = _report([
        _orphan(
            "zsh-tips",
            mode="link_existing",
            candidates=[
                {"target_moc": "Shell & Terminal", "score": 0.83},
                {"target_moc": "Dotfiles", "score": 0.67},
                {"target_moc": "CLI Tools", "score": 0.55},
            ],
        )
    ])
    _filename, body = render_moc_proposal_doc(report, _Cfg())

    # Locked to the real reducer output shape.
    assert "## Orphan Notes & MOCs" in body
    assert "### O01 — [[zsh-tips]] (note)" in body
    assert "- [x] up:: [[Shell & Terminal]] (score 0.83)" in body
    assert "- [ ] up:: [[Dotfiles]] (score 0.67)" in body
    assert "- [ ] up:: [[CLI Tools]] (score 0.55)" in body
    # All three candidates surfaced.
    assert body.count("up:: [[") == 3


def test_orphan_render_create_new_with_reason_and_instruction():
    """A create_new renders the reason line + an /execute stamp instruction."""
    reason = "No existing MOC shares this note's topics (quantum, physics). Proposing a new MOC."
    report = _report([
        _orphan("quantum-notes", mode="create_new", reason=reason)
    ])
    _filename, body = render_moc_proposal_doc(report, _Cfg())

    assert "### O01 — [[quantum-notes]] (note)" in body
    assert f"**Reason:** {reason}" in body
    # /execute deferred-write instruction (OQ-6); the write happens later, not now.
    assert "/execute" in body
    assert "`/moc-propose` writes nothing" in body


def test_orphan_render_produces_proposal_doc_only_no_vault_write():
    """CON-3: the render path performs NO vault write.

    render_moc_proposal_doc is a pure (report, config) -> (filename, body)
    function — it accepts no Kado client and returns markup only, so it
    structurally cannot kado-write. This guards that the orphan render did not
    introduce a Kado dependency into the render path.
    """
    sig = inspect.signature(render_moc_proposal_doc)
    params = list(sig.parameters)
    assert params == ["report", "config"], (
        f"render must stay pure (report, config); got {params!r} — a Kado client "
        "param would mean the render path can write to the vault (CON-3 violation)"
    )

    report = _report([
        _orphan(
            "lonely",
            mode="link_existing",
            candidates=[{"target_moc": "Knowledge", "score": 0.9}],
        ),
        _orphan("solo", mode="create_new", reason="No match. New MOC."),
    ])
    result = render_moc_proposal_doc(report, _Cfg())

    # Pure function contract: returns exactly (filename:str, body:str), no
    # side-effect channel. The CLI wrapper is what writes the local file; the
    # AGENT is what kado-writes — never this function.
    assert isinstance(result, tuple) and len(result) == 2
    filename, body = result
    assert isinstance(filename, str) and filename.endswith(".md")
    assert isinstance(body, str) and "## Orphan Notes & MOCs" in body
