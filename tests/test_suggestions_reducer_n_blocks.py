#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_n_blocks.py — F-41 T3.2.

Covers AC-4/OQ5: N independent Accept blocks in the rendered suggestions doc.

Two create_atomic_note actions from a single source stem must produce TWO
independent rendered blocks in the output — one **Source:** + one
**Decision (atomic note):** per atomic, not collapsed to one.

Test is the A4/OQ5 regression guard regardless of whether a production fix
was required; see T3.2 task notes.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load suggestions-reducer.py (hyphen filename → importlib).
_reducer_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py"
)
_reducer_mod = importlib.util.module_from_spec(_reducer_spec)
assert _reducer_spec.loader is not None
sys.modules["suggestions_reducer"] = _reducer_mod
_reducer_spec.loader.exec_module(_reducer_mod)

render_create_atomic_note = _reducer_mod.render_create_atomic_note  # type: ignore[attr-defined]
RENDERERS = _reducer_mod.RENDERERS  # type: ignore[attr-defined]

# Load suggestions-render.py (hyphen filename → importlib).
_render_spec = importlib.util.spec_from_file_location(
    "suggestions_render", SCRIPTS_DIR / "suggestions-render.py"
)
_render_mod = importlib.util.module_from_spec(_render_spec)
assert _render_spec.loader is not None
sys.modules["suggestions_render"] = _render_mod
_render_spec.loader.exec_module(_render_mod)

render_suggestions = _render_mod.render_suggestions  # type: ignore[attr-defined]


# ── Factories ─────────────────────────────────────────────────────────────────


def make_atomic_action(
    *,
    title: str,
    worthiness: float = 0.8,
    moc_path: str = "Atlas/200 Maps/Philosophy MOC.md",
) -> dict:
    return {
        "kind": "create_atomic_note",
        "suggested_title": title,
        "atomic_note_worthiness": worthiness,
        "template": "t_note_tomo",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [
            {"path": moc_path, "score": 0.85, "pre_check": False}
        ],
        "needs_new_moc": False,
        "tags_to_add": [],
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "alternatives": [],
    }


def make_sections_with_two_atomics(stem: str = "source-note") -> list[dict]:
    """Build a sections list as the reducer would produce it for a single source
    with two create_atomic_note actions (distinct titles, same stem)."""
    actions = [
        make_atomic_action(title="Stoicism Introduction"),
        make_atomic_action(title="Epicureanism Overview"),
    ]
    rendered_actions: list[dict] = []
    for action in actions:
        rendered_md = render_create_atomic_note(action, stem)
        rendered_actions.append({"kind": "create_atomic_note", "rendered_md": rendered_md})

    return [
        {
            "id": "S01",
            "stem": stem,
            "actions": rendered_actions,
        }
    ]


def make_minimal_doc(sections: list[dict]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "generated": "2026-06-11T10:00:00Z",
        "run_id": "2026-06-11-1000-test",
        "profile": "miyo",
        "doc_variant": "primary",
        "source_items": 1,
        "sections": sections,
        "daily_notes_updates": [],
        "rendered_daily_updates_md": "",
        "proposed_mocs": [],
        "needs_attention": [],
        "decision_precedence_note": "",
    }


# ── T3.2 tests ────────────────────────────────────────────────────────────────


def test_two_atomics_produce_two_decision_blocks():
    """Two create_atomic_note actions → two **Decision (atomic note):** blocks."""
    stem = "source-note"
    doc = make_minimal_doc(make_sections_with_two_atomics(stem))
    lines = render_suggestions(doc)
    output = "\n".join(lines)

    decision_count = output.count("**Decision (atomic note):**")
    assert decision_count == 2, (
        f"Expected 2 '**Decision (atomic note):**' blocks, got {decision_count}.\n"
        f"Output:\n{output}"
    )


def test_two_atomics_produce_two_source_lines():
    """Two create_atomic_note actions from one source → two **Source:** lines."""
    stem = "source-note"
    doc = make_minimal_doc(make_sections_with_two_atomics(stem))
    lines = render_suggestions(doc)
    output = "\n".join(lines)

    source_count = output.count(f"**Source:** [[{stem}]]")
    assert source_count == 2, (
        f"Expected 2 '**Source:** [[{stem}]]' lines, got {source_count}.\n"
        f"Output:\n{output}"
    )


def test_two_atomics_have_distinct_titles():
    """Each atomic block contains its own distinct suggested title."""
    stem = "source-note"
    doc = make_minimal_doc(make_sections_with_two_atomics(stem))
    lines = render_suggestions(doc)
    output = "\n".join(lines)

    assert "**Suggested name:** Stoicism Introduction" in output
    assert "**Suggested name:** Epicureanism Overview" in output


def test_two_atomics_each_independently_approvable():
    """Each atomic block carries its own Approve checkbox (two total)."""
    stem = "source-note"
    doc = make_minimal_doc(make_sections_with_two_atomics(stem))
    lines = render_suggestions(doc)
    output = "\n".join(lines)

    # Each **Decision (atomic note):** block is followed by an Approve checkbox.
    # Count occurrences of the approve line pattern.
    approve_count = len(re.findall(r"- \[.\] Approve\b", output))
    assert approve_count == 2, (
        f"Expected 2 Approve checkboxes (one per atomic), got {approve_count}.\n"
        f"Output:\n{output}"
    )


# ── CON-2: single-thread output stays byte-identical ─────────────────────────


def test_single_atomic_output_unchanged():
    """Single create_atomic_note → exactly one block (CON-2 regression guard)."""
    stem = "solo-note"
    action = make_atomic_action(title="Solo Topic")
    rendered_md = render_create_atomic_note(action, stem)
    doc = make_minimal_doc([
        {
            "id": "S01",
            "stem": stem,
            "actions": [{"kind": "create_atomic_note", "rendered_md": rendered_md}],
        }
    ])
    lines = render_suggestions(doc)
    output = "\n".join(lines)

    assert output.count("**Decision (atomic note):**") == 1
    assert output.count(f"**Source:** [[{stem}]]") == 1
    assert "**Suggested name:** Solo Topic" in output
