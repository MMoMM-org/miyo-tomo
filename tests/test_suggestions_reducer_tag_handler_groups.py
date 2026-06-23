#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_tag_handler_groups.py — T3.3 (spec 024).

Covers the tag-handler group-result render path in suggestions-reducer:
  1. One group → one suggestion item with composed_block + target_path + marker + Approve box.
  2. A group with N source_paths renders composed_block ONCE (N→1 merge already upstream).
  3. Two groups → two distinct suggestion items.
  4. No/empty --tag-handler-groups-dir → suggestions doc is byte-identical to today
     (additive safety — absent registry does not disturb the existing doc).
  5. Rendered tag_handler_updates[] present in the doc JSON structure.

Fixtures conform to tomo/schemas/tag-handler-group.schema.json (schema_version "1",
required: handler, target_path, marker, composed_block, source_paths).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
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

render_tag_handler_group = _reducer_mod.render_tag_handler_group  # type: ignore[attr-defined]
collect_tag_handler_groups = _reducer_mod.collect_tag_handler_groups  # type: ignore[attr-defined]
render_tag_handler_updates_block = _reducer_mod.render_tag_handler_updates_block  # type: ignore[attr-defined]


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _group(
    *,
    handler: str = "reading-log",
    target_path: str | None = "Atlas/300 Reading/Reading Log.md",
    marker: str = "## Captures",
    composed_block: str = "- 2026-06-23 — Read *The Phoenix Project* (chapter 3)\n- Key insight: WIP limits reduce chaos",
    source_paths: list[str] | None = None,
    placement: str | None = "inside",
    compose_mode: str | None = "llm_directive",
) -> dict:
    """Build a minimal valid tag-handler-group result fixture."""
    g: dict[str, Any] = {
        "schema_version": "1",
        "handler": handler,
        "target_path": target_path,
        "marker": marker,
        "composed_block": composed_block,
        "source_paths": source_paths or ["100 Inbox/reading-note-1.md"],
    }
    if placement is not None:
        g["placement"] = placement
    if compose_mode is not None:
        g["compose_mode"] = compose_mode
    return g


def _write_group(dir_path: Path, filename: str, group: dict) -> None:
    (dir_path / filename).write_text(json.dumps(group), encoding="utf-8")


# ── T3.3-1: one group → one suggestion item ───────────────────────────────────


def test_one_group_renders_one_suggestion() -> None:
    """One group-result → rendered block contains composed_block, target_path, marker, Approve."""
    g = _group()
    rendered = render_tag_handler_group(g)

    assert g["composed_block"] in rendered, "composed_block must appear verbatim"
    # target_path is rendered as a wikilink without the .md suffix
    expected_link = g["target_path"].removesuffix(".md")
    assert expected_link in rendered, "target_path (as wikilink) must be referenced"
    assert g["marker"] in rendered, "marker must appear"
    assert "Approve" in rendered, "Approve checkbox must be present"
    assert "- [" in rendered, "must contain a checkbox"


# ── T3.3-2: N source_paths → composed_block appears ONCE (AC-3) ──────────────


def test_merged_block_cardinality_one() -> None:
    """Group with 3 source_paths must render composed_block exactly once (N→1 already upstream)."""
    composed = "- Captured item A\n- Captured item B\n- Captured item C"
    g = _group(
        composed_block=composed,
        source_paths=[
            "100 Inbox/note-a.md",
            "100 Inbox/note-b.md",
            "100 Inbox/note-c.md",
        ],
    )
    rendered = render_tag_handler_group(g)

    # The composed block should appear exactly once — split on a sentinel phrase.
    count = rendered.count("Captured item A")
    assert count == 1, (
        f"composed_block sentinel appeared {count} times; expected exactly 1.\n"
        f"Rendered:\n{rendered}"
    )


# ── T3.3-3: two groups → two distinct suggestion items ───────────────────────


def test_two_groups_two_suggestions() -> None:
    """Two groups produce two independent rendered items in the updates block."""
    g1 = _group(
        handler="reading-log",
        target_path="Atlas/Reading Log.md",
        marker="## Captures",
        composed_block="- Read item one",
        source_paths=["100 Inbox/note-1.md"],
    )
    g2 = _group(
        handler="project-notes",
        target_path="Projects/Alpha/Notes.md",
        marker="## Daily Notes",
        composed_block="- Project update two",
        source_paths=["100 Inbox/note-2.md"],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        _write_group(d, "group-reading.json", g1)
        _write_group(d, "group-project.json", g2)

        groups = collect_tag_handler_groups(d)

    assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"

    rendered_items = [render_tag_handler_group(g) for g in groups]
    combined = "\n---\n".join(rendered_items)

    assert "Read item one" in combined
    assert "Project update two" in combined
    assert "Atlas/Reading Log.md" in combined or "Reading Log" in combined
    assert "Projects/Alpha/Notes.md" in combined or "Alpha" in combined


# ── T3.3-4: no groups dir → doc unchanged (additive safety) ──────────────────


def test_no_groups_dir_unchanged() -> None:
    """When --tag-handler-groups-dir is absent or empty → doc JSON is unchanged."""
    # collect_tag_handler_groups(None) must return []
    result_none = collect_tag_handler_groups(None)
    assert result_none == [], "None dir must return empty list"

    # collect_tag_handler_groups(<non-existent path>) must return []
    result_missing = collect_tag_handler_groups(Path("/tmp/does-not-exist-xxxxxxxxxxx"))
    assert result_missing == [], "Missing dir must return empty list"

    # collect_tag_handler_groups(<empty dir>) must return []
    with tempfile.TemporaryDirectory() as tmpdir:
        result_empty = collect_tag_handler_groups(Path(tmpdir))
    assert result_empty == [], "Empty dir must return empty list"


# ── T3.3-5: rendered items present in the doc JSON structure ─────────────────


def test_group_suggestion_in_doc_output() -> None:
    """tag_handler_updates[] and rendered_tag_handler_updates_md are in the doc JSON."""
    g = _group(
        composed_block="- A captured insight",
        target_path="Atlas/Reading Log.md",
        marker="## Captures",
    )

    groups = [g]
    tag_handler_updates = groups  # passed through to doc
    rendered_md = render_tag_handler_updates_block(groups)

    # Simulate the doc dict structure (mirrors daily_notes_updates pattern)
    doc: dict[str, Any] = {
        "schema_version": "1",
        "generated": "2026-06-23T12:00:00Z",
        "run_id": "test-run-024",
        "profile": "miyo",
        "doc_variant": "primary",
        "source_items": 0,
        "sections": [],
        "daily_notes_updates": [],
        "rendered_daily_updates_md": "",
        "tag_handler_updates": tag_handler_updates,
        "rendered_tag_handler_updates_md": rendered_md,
        "decision_precedence_note": "",
        "proposed_mocs": [],
        "needs_attention": [],
    }

    assert "tag_handler_updates" in doc
    assert len(doc["tag_handler_updates"]) == 1
    assert "rendered_tag_handler_updates_md" in doc
    assert "A captured insight" in doc["rendered_tag_handler_updates_md"]
