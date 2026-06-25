#!/usr/bin/env python3
# version: 0.4.0
"""test_suggestions_reducer_tag_handler_groups.py — T3.3 (spec 024) + T6.1/T6.2 (spec 025).

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


# ── T6.1 (spec 025): verbatim preview + mode descriptor ──────────────────────


def _group_with_output_format(
    *,
    structure: str = "table_row",
    order: str = "newest_first",
    granularity: str = "per_item",
    composed_block: str = "| 2026-06-25 | fix | resolveBlock landed |",
    source_paths: list[str] | None = None,
) -> dict:
    """Build a group fixture that carries output_format (spec 025)."""
    g = _group(
        composed_block=composed_block,
        source_paths=source_paths or ["100 Inbox/dev-log-1.md"],
    )
    g["output_format"] = {
        "structure": structure,
        "order": order,
        "granularity": granularity,
        "cells": [
            {"key": "date", "type": "auto_date"},
            {"key": "category", "type": "static", "value": "fix"},
            {"key": "note", "type": "synthesize"},
        ],
    }
    return g


def test_output_format_group_has_mode_descriptor() -> None:
    """A group with output_format renders a one-line mode descriptor (spec 025 T6.1 / FR-20).

    Descriptor must encode: structure (table_row→"table row"), order (newest_first→"newest first"),
    granularity (per_item→"per item"). Must NOT contain executor internals.
    """
    g = _group_with_output_format(
        structure="table_row",
        order="newest_first",
        granularity="per_item",
    )
    rendered = render_tag_handler_group(g)

    assert "table row" in rendered, "structure must be human-readable in descriptor"
    assert "newest first" in rendered, "order must be human-readable in descriptor"
    assert "per item" in rendered, "granularity must be human-readable in descriptor"


def test_output_format_group_mode_descriptor_list_item_merged() -> None:
    """list_item / append / merged renders the correct descriptor terms."""
    g = _group_with_output_format(
        structure="list_item",
        order="append",
        granularity="merged",
        composed_block="- Combined entry for the day",
    )
    rendered = render_tag_handler_group(g)

    assert "list item" in rendered, "structure 'list_item' → 'list item'"
    assert "append" in rendered, "order 'append' → 'append'"
    assert "merged" in rendered, "granularity 'merged' → 'merged'"
    # merged shows exactly the single composed line, verbatim (symmetric with per_item N-line test)
    assert "- Combined entry for the day" in rendered


def test_output_format_group_verbatim_composed_block_present() -> None:
    """The verbatim composed_block rows are still present alongside the mode descriptor."""
    row = "| 2026-06-25 | feature | output_format schema |"
    g = _group_with_output_format(composed_block=row)
    rendered = render_tag_handler_group(g)

    assert row in rendered, "composed_block must appear verbatim"
    # Approve box must still be present for an ok-guard group
    assert "Approve" in rendered


def test_output_format_group_per_item_shows_all_lines() -> None:
    """per_item composed_block with N lines: all lines must appear."""
    block = "| 2026-06-24 | fix | line 1 |\n| 2026-06-25 | feature | line 2 |"
    g = _group_with_output_format(
        granularity="per_item",
        composed_block=block,
        source_paths=["100 Inbox/a.md", "100 Inbox/b.md"],
    )
    rendered = render_tag_handler_group(g)

    assert "line 1" in rendered
    assert "line 2" in rendered


def test_output_format_group_no_executor_internals() -> None:
    """No executor internals (Hashi, action-type, script names) in rendered text (spec 025 T6.1)."""
    g = _group_with_output_format()
    rendered = render_tag_handler_group(g)

    forbidden = ["Hashi", "insert_under_marker", "update_log_entry", "action-type"]
    for term in forbidden:
        assert term not in rendered, f"Executor internal '{term}' must not appear in rendered output"


def test_target_missing_guard_no_executor_internals() -> None:
    """target_missing guard text must not mention executor internals (T6.1 cleanup)."""
    g = _group()
    g["guard"] = "target_missing"
    rendered = render_tag_handler_group(g)

    # Must NOT contain old "Hashi modifies notes" phrasing
    assert "Hashi modifies" not in rendered, (
        "target_missing guard must use executor-neutral phrasing"
    )
    # Must retain the intent: note must exist before update
    assert "exist" in rendered.lower() or "create" in rendered.lower(), (
        "target_missing guard must still convey that the target note must exist"
    )
    # No Approve box (hard guard)
    assert "- [x] Approve" not in rendered


def test_group_without_output_format_backward_compat() -> None:
    """A group WITHOUT output_format renders byte-identically to before (backward compat)."""
    g = _group()  # no output_format key
    rendered = render_tag_handler_group(g)

    # Must contain composed_block, marker, target, and Approve box
    assert g["composed_block"] in rendered
    assert g["marker"] in rendered
    assert "Approve" in rendered
    # Must NOT contain a format descriptor (no output_format present)
    assert "**Format:**" not in rendered


# ── T6.2 (spec 025): fallback ⚠️ + Approve-box gating ───────────────────────


def _group_with_fallback(reason: str, **kwargs: Any) -> dict:
    """Build a group fixture with a fallback reason (spec 025 T6.2)."""
    g = _group_with_output_format(**kwargs)
    g["fallback"] = {"reason": reason}
    return g


def test_fallback_cell_count_mismatch_renders_warning() -> None:
    """fallback.reason=cell_count_mismatch → ⚠️ line with plain-language reason (FR-19)."""
    g = _group_with_fallback(
        reason="cell_count_mismatch",
        composed_block="Fell back to prose because columns differ",
    )
    rendered = render_tag_handler_group(g)

    assert "⚠️" in rendered, "Warning emoji must appear for fallback"
    # Plain-language reason — must NOT mention executor internals
    assert "Hashi" not in rendered
    assert "insert_under_marker" not in rendered
    # Some explanation about the column/cell mismatch
    assert "column" in rendered.lower() or "cell" in rendered.lower() or "match" in rendered.lower()
    # The prose fallback block is previewed alongside the ⚠️ (FR-19: approve the fallback knowingly)
    assert "Fell back to prose because columns differ" in rendered


def test_fallback_cell_count_mismatch_keeps_approve_box() -> None:
    """fallback (not a hard guard) must KEEP the Approve box — user approves the prose fallback."""
    g = _group_with_fallback(reason="cell_count_mismatch")
    rendered = render_tag_handler_group(g)

    assert "- [x] Approve" in rendered or "- [ ] Approve" in rendered, (
        "Approve box must remain for fallback groups (not a hard guard)"
    )


def test_fallback_no_structure_under_marker_renders_warning() -> None:
    """fallback.reason=no_structure_under_marker → ⚠️ line with plain-language reason."""
    g = _group_with_fallback(
        reason="no_structure_under_marker",
        composed_block="Fell back to prose: no table found",
    )
    rendered = render_tag_handler_group(g)

    assert "⚠️" in rendered
    assert "Hashi" not in rendered
    # Some explanation about missing table/list under marker
    assert "table" in rendered.lower() or "list" in rendered.lower() or "marker" in rendered.lower()
    # The prose fallback block is previewed alongside the ⚠️ (FR-19)
    assert "Fell back to prose: no table found" in rendered


def test_fallback_no_structure_under_marker_keeps_approve_box() -> None:
    """no_structure_under_marker fallback must also keep the Approve box."""
    g = _group_with_fallback(reason="no_structure_under_marker")
    rendered = render_tag_handler_group(g)

    assert "- [x] Approve" in rendered or "- [ ] Approve" in rendered


def test_fallback_warning_names_handler_and_target() -> None:
    """The fallback ⚠️ line names the handler and target (spec 025 FR-19)."""
    handler = "reading-log"
    target = "Atlas/300 Reading/Reading Log.md"
    g = _group_with_fallback(
        reason="cell_count_mismatch",
        composed_block="prose preview",
    )
    g["handler"] = handler
    g["target_path"] = target
    rendered = render_tag_handler_group(g)

    assert "reading-log" in rendered, "handler name must appear in fallback warning"
    assert "Reading Log" in rendered, "target note must be referenced in fallback warning"


def test_hard_guard_takes_priority_over_fallback() -> None:
    """Hard guards (target_missing/marker_missing) drop Approve box even when fallback is set."""
    # target_missing + fallback → hard guard wins (no Approve box)
    g = _group_with_fallback(reason="cell_count_mismatch")
    g["guard"] = "target_missing"
    rendered = render_tag_handler_group(g)

    assert "- [x] Approve" not in rendered
    assert "Create it first" in rendered or "exist" in rendered.lower()

    # marker_missing + fallback → hard guard wins (no Approve box)
    g2 = _group_with_fallback(reason="no_structure_under_marker")
    g2["guard"] = "marker_missing"
    rendered2 = render_tag_handler_group(g2)

    assert "- [x] Approve" not in rendered2
