#!/usr/bin/env python3
# version: 0.3.0
"""test_suggestions_reducer_tag_handler_groups.py — T3.3 (spec 024).

Covers the tag-handler group-result render path in suggestions-reducer and
the surface in suggestions-render:
  1. One group → one suggestion item with composed_block + target_path + marker + Approve box.
  2. A group with N source_paths renders composed_block ONCE (N→1 merge already upstream).
  3. Two groups → two distinct suggestion items.
  4. No/empty --tag-handler-groups-dir → doc fields are ABSENT (byte-identity; proven via
     main() invocation, not just the collection helper).
  5. Rendered tag_handler_updates[] present in the doc JSON structure.
  6. The FINAL rendered markdown (suggestions-render.py) surfaces the group block.

Fixtures conform to tomo/schemas/tag-handler-group.schema.json (schema_version "1",
required: handler, target_path, marker, composed_block, source_paths).
"""
from __future__ import annotations

import importlib.util
import json
import os
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

# Load suggestions-render.py (hyphen filename → importlib).
_render_spec = importlib.util.spec_from_file_location(
    "suggestions_render", SCRIPTS_DIR / "suggestions-render.py"
)
_render_mod = importlib.util.module_from_spec(_render_spec)
assert _render_spec.loader is not None
sys.modules["suggestions_render"] = _render_mod
_render_spec.loader.exec_module(_render_mod)

render_tag_handler_updates_fn = _render_mod.render_tag_handler_updates  # type: ignore[attr-defined]
render_suggestions_fn = _render_mod.render_suggestions  # type: ignore[attr-defined]


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


def _minimal_state(state_path: Path, stems: list[str]) -> None:
    """Write a minimal JSONL state file for the reducer stub run."""
    lines = []
    for stem in stems:
        lines.append(json.dumps({
            "stem": stem,
            "path": f"100 Inbox/{stem}.md",
            "status": "done",
            "run_id": "test-run",
            "ts": "2026-06-23T12:00:00Z",
        }))
    state_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_reducer_main(tmp: Path, *, groups_dir: Path | None = None) -> dict:
    """Invoke the reducer main() with a minimal stub inbox and return the doc JSON."""
    state_path = tmp / "state.jsonl"
    items_dir = tmp / "items"
    out_path = tmp / "doc.json"
    items_dir.mkdir(parents=True, exist_ok=True)
    _minimal_state(state_path, [])  # no inbox items — we only care about tag-handler path

    # Build argv for the reducer
    argv = [
        "suggestions-reducer.py",
        "--state", str(state_path),
        "--items-dir", str(items_dir),
        "--run-id", "test-run",
        "--profile", "miyo",
        "--output", str(out_path),
        "--no-kado",
    ]
    if groups_dir is not None:
        argv += ["--tag-handler-groups-dir", str(groups_dir)]

    old_argv = sys.argv
    sys.argv = argv
    try:
        _reducer_mod.main()  # type: ignore[attr-defined]
    finally:
        sys.argv = old_argv

    return json.loads(out_path.read_text(encoding="utf-8"))


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


# ── T3.3-4: no groups dir → fields absent in doc JSON (byte-identity) ─────────


def test_no_groups_dir_unchanged() -> None:
    """When --tag-handler-groups-dir is absent or empty → doc JSON is unchanged.

    Proven via main() invocation: neither tag_handler_updates nor
    rendered_tag_handler_updates_md must be present in the output doc.
    """
    # Helper-level sanity (fast path — keeps the unit-test value)
    assert collect_tag_handler_groups(None) == [], "None dir must return empty list"
    assert collect_tag_handler_groups(Path("/tmp/does-not-exist-xxxxxxxxxxx")) == [], \
        "Missing dir must return empty list"
    with tempfile.TemporaryDirectory() as tmpdir:
        assert collect_tag_handler_groups(Path(tmpdir)) == [], \
            "Empty dir must return empty list"

    # Main()-level proof: no --tag-handler-groups-dir → fields absent from doc.
    with tempfile.TemporaryDirectory() as tmpdir:
        doc = _run_reducer_main(Path(tmpdir))

    assert "tag_handler_updates" not in doc, (
        "tag_handler_updates must be absent when no groups dir is passed — "
        f"found: {doc.get('tag_handler_updates')}"
    )
    assert "rendered_tag_handler_updates_md" not in doc, (
        "rendered_tag_handler_updates_md must be absent when no groups dir is passed"
    )


# ── T3.3-5: rendered items present in the doc JSON structure ─────────────────


def test_group_suggestion_in_doc_output() -> None:
    """tag_handler_updates[] and rendered_tag_handler_updates_md appear in doc JSON
    when groups are present, and the rendered markdown contains the composed_block."""
    g = _group(
        composed_block="- A captured insight",
        target_path="Atlas/Reading Log.md",
        marker="## Captures",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        groups_dir = Path(tmpdir)
        _write_group(groups_dir, "group-test.json", g)

        doc = _run_reducer_main(Path(tmpdir) / "run", groups_dir=groups_dir)

    assert "tag_handler_updates" in doc
    assert len(doc["tag_handler_updates"]) == 1
    assert "rendered_tag_handler_updates_md" in doc
    assert "A captured insight" in doc["rendered_tag_handler_updates_md"]


# ── T3.3-6: final rendered markdown surfaces the group block ─────────────────


def test_group_surfaces_in_final_rendered_markdown() -> None:
    """suggestions-render.py must include composed_block + target + marker + Approve
    in the final user-facing markdown (not just in the JSON)."""
    composed = "- Finished reading *The Pragmatic Programmer* ch.5"
    g = _group(
        composed_block=composed,
        target_path="Atlas/300 Reading/Reading Log.md",
        marker="## Captures",
    )
    rendered_block = render_tag_handler_updates_block([g])

    # Build a minimal suggestions-doc that render.py would consume
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
        "tag_handler_updates": [g],
        "rendered_tag_handler_updates_md": rendered_block,
        "decision_precedence_note": "",
        "proposed_mocs": [],
        "needs_attention": [],
    }

    final_lines = render_tag_handler_updates_fn(doc)
    final_md = "\n".join(final_lines)

    assert composed in final_md, "composed_block must appear verbatim in final markdown"
    assert "Reading Log" in final_md, "target note reference must appear"
    assert "## Captures" in final_md, "marker must appear"
    assert "Approve" in final_md, "Approve checkbox must be present in final markdown"


# ── T3.3-7: malformed group file is silently skipped (S1 failure-path) ────────


def test_malformed_group_file_is_skipped() -> None:
    """A malformed JSON file in the groups dir is silently skipped; valid groups load.

    Covers the `except (json.JSONDecodeError, OSError): continue` path in
    collect_tag_handler_groups — L1 failure-path coverage for the file-load loop.
    """
    valid = _group(
        composed_block="- A valid captured entry",
        source_paths=["100 Inbox/valid-note.md"],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        # Write one malformed file and one valid file
        (d / "bad-group.json").write_text("not json{", encoding="utf-8")
        _write_group(d, "good-group.json", valid)

        groups = collect_tag_handler_groups(d)

    assert len(groups) == 1, (
        f"Expected exactly 1 valid group (bad file skipped), got {len(groups)}"
    )
    assert groups[0]["composed_block"] == "- A valid captured entry"
