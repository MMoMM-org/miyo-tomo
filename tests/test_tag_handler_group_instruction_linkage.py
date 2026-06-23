#!/usr/bin/env python3
# version: 0.1.0
"""test_tag_handler_group_instruction_linkage.py — T4.1 (spec 024 Phase 4).

Covers the approval→render linkage that turns an APPROVED tag-handler group
into a Hashi insert_under_marker instruction. Four coordinated units:
  1. tag-handler-group.group_id        — deterministic, markdown-safe slug.
  2. suggestions-reducer render         — group_id surfaces in the rendered block.
  3. suggestion-parser                  — approved group ids extracted (skipped NOT).
  4. instruction-render                 — one insert_under_marker per approved group;
                                          marker stripped to anchor value; content
                                          = composed_block (multi-line preserved);
                                          skipped group → no instruction.
Also validates an emitted instruction against hashi-instructions.schema.json.

Fixtures conform to tomo/schemas/tag-handler-group.schema.json.
Spec: docs/XDD/specs/024-tag-handler-framework/solution.md §6.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_DIR = REPO_ROOT / "tomo" / "schemas"

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    """Load a hyphenated top-level script as a module — house pattern."""
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_group_mod = _load("tag_handler_group", "tag-handler-group.py")
_reducer_mod = _load("suggestions_reducer", "suggestions-reducer.py")
_parser_mod = _load("suggestion_parser", "suggestion-parser.py")
_render_mod = _load("instruction_render", "instruction-render.py")

group_id = _group_mod.group_id
render_tag_handler_group = _reducer_mod.render_tag_handler_group
render_tag_handler_updates_block = _reducer_mod.render_tag_handler_updates_block
parse_tag_handler_groups = _parser_mod.parse_tag_handler_groups
_build_insert_under_marker_actions = _render_mod._build_insert_under_marker_actions
_marker_to_anchor_value = _render_mod._marker_to_anchor_value

from jsonschema import validate as _validate  # noqa: E402

INSTRUCTIONS_SCHEMA = json.loads(
    (SCHEMA_DIR / "hashi-instructions.schema.json").read_text(encoding="utf-8")
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _group(
    *,
    handler: str = "tsukai",
    target_path: str | None = "Efforts/400 On/Tomo Dev Log.md",
    marker: str = "## Captures",
    composed_block: str = "### 2026-06-23\n\n- Shipped X (feature)\n- Decided Y (architecture)",
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
        "source_paths": source_paths or ["100 Inbox/MiYo-Tsukai-Tomo-cap-1.md"],
    }
    if placement is not None:
        g["placement"] = placement
    if compose_mode is not None:
        g["compose_mode"] = compose_mode
    return g


def _wrap_instructions(actions: list[dict]) -> dict:
    """Wrap actions in a minimal valid tomo-instructions doc for schema validation."""
    return {
        "schema_version": "1",
        "type": "tomo-instructions",
        "generated": "2026-06-23T12:00:00Z",
        "profile": "miyo",
        "actions": actions,
    }


# ── 1. group_id — deterministic & distinct ────────────────────────────────────


def test_group_id_deterministic():
    """Same (handler, target_path) → same id; different pair → different id."""
    g1 = _group(handler="tsukai", target_path="Efforts/Tomo Dev Log.md")
    g2 = _group(handler="tsukai", target_path="Efforts/Tomo Dev Log.md")
    assert group_id(g1) == group_id(g2)

    g3 = _group(handler="tsukai", target_path="Efforts/Kado Dev Log.md")
    assert group_id(g1) != group_id(g3)
    g4 = _group(handler="reading-log", target_path="Efforts/Tomo Dev Log.md")
    assert group_id(g1) != group_id(g4)


def test_group_id_markdown_safe():
    """The id has no spaces or markdown-special chars (embeddable in a suggestion)."""
    gid = group_id(_group())
    assert " " not in gid
    assert all(c.isalnum() or c == "-" for c in gid), gid
    assert gid.startswith("th-")


def test_group_id_null_target_well_formed():
    """A null target_path still yields a well-formed id (group never emits anyway)."""
    gid = group_id(_group(target_path=None))
    assert gid.startswith("th-")
    assert " " not in gid


# ── 2. reducer renders the group id ───────────────────────────────────────────


def test_reducer_renders_group_id():
    """render_tag_handler_group surfaces group_id(group) in its block."""
    g = _group()
    block = render_tag_handler_group(g)
    assert group_id(g) in block
    # Embedded as a **Group:** field line so the parser can extract it.
    assert f"**Group:** `{group_id(g)}`" in block


# ── 3. parser extracts approved ids (skipped NOT) ─────────────────────────────


def _render_section(groups: list[dict]) -> str:
    """Render the full ## Tag-Handler Updates markdown section for a list of groups."""
    return render_tag_handler_updates_block(groups)


def test_parser_extracts_approved_group_id():
    """A group whose Approve box is [x] is extracted by its id."""
    g = _group()
    md = _render_section([g])
    approved = parse_tag_handler_groups(md)
    assert approved == [group_id(g)]


def test_skipped_group_not_extracted():
    """A group ticked [x] Skip (Approve unchecked) is NOT in the approved set."""
    g = _group()
    md = _render_section([g])
    # Flip the default `- [x] Approve` / `- [ ] Skip` to Skip.
    md_skipped = md.replace("- [x] Approve", "- [ ] Approve").replace(
        "- [ ] Skip", "- [x] Skip"
    )
    approved = parse_tag_handler_groups(md_skipped)
    assert approved == []


def test_parser_mixed_approve_skip():
    """Two groups, one approved one skipped → only the approved id returned."""
    g_yes = _group(handler="tsukai", target_path="Efforts/Tomo Dev Log.md")
    g_no = _group(handler="reading-log", target_path="Atlas/Reading Log.md")
    md = _render_section([g_yes, g_no])
    # Skip the SECOND group only — flip its checkboxes in isolation by slicing.
    gid_no = group_id(g_no)
    idx = md.index(f"**Group:** `{gid_no}`")
    head, tail = md[:idx], md[idx:]
    tail = tail.replace("- [x] Approve", "- [ ] Approve", 1).replace(
        "- [ ] Skip", "- [x] Skip", 1
    )
    md = head + tail
    approved = parse_tag_handler_groups(md)
    assert approved == [group_id(g_yes)]


def test_parser_absent_section():
    """A doc with no Tag-Handler Updates section → empty list."""
    assert parse_tag_handler_groups("## Suggestions\n\nnothing here\n") == []


# ── 4. marker → anchor value ──────────────────────────────────────────────────


def test_marker_to_anchor_value_strip():
    """'## Captures' → 'Captures' (leading #-run + single space stripped)."""
    assert _marker_to_anchor_value("## Captures") == "Captures"
    assert _marker_to_anchor_value("# Top") == "Top"
    assert _marker_to_anchor_value("###  Spaced") == "Spaced"  # extra leading space trimmed
    assert _marker_to_anchor_value("No Hashes") == "No Hashes"
    assert _marker_to_anchor_value("  ## Padded  ") == "Padded"


# ── 5. render emits insert_under_marker for approved group ────────────────────


def test_render_emits_insert_under_marker():
    """An approved group → one insert_under_marker with the expected shape."""
    g = _group()
    actions = _build_insert_under_marker_actions([g], [group_id(g)], [0])
    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "insert_under_marker"
    assert a["target_path"] == "Efforts/400 On/Tomo Dev Log.md"
    assert a["anchor"] == {"type": "heading", "value": "Captures"}
    assert a["placement"] == "inside"
    assert a["content"] == g["composed_block"]
    assert a["id"].startswith("I")


def test_render_emits_validates_against_schema():
    """An emitted insert_under_marker action validates against the Hashi schema."""
    g = _group()
    actions = _build_insert_under_marker_actions([g], [group_id(g)], [0])
    for a in actions:
        a["applied"] = False  # build_actions stamps this; mirror it here
    _validate(instance=_wrap_instructions(actions), schema=INSTRUCTIONS_SCHEMA)


def test_skipped_group_no_instruction():
    """A group NOT in the approved set produces NO instruction."""
    g = _group()
    actions = _build_insert_under_marker_actions([g], [], [0])
    assert actions == []
    # Approved set names a DIFFERENT id → still nothing.
    actions = _build_insert_under_marker_actions([g], ["th-other-x"], [0])
    assert actions == []


def test_content_is_composed_block_multiline():
    """content equals composed_block verbatim — embedded newlines preserved."""
    block = "### 2026-06-23\n\n- line one\n- line two\n\n- after blank"
    g = _group(composed_block=block)
    actions = _build_insert_under_marker_actions([g], [group_id(g)], [0])
    assert actions[0]["content"] == block
    assert "\n" in actions[0]["content"]


def test_placement_default_inside():
    """A group with no placement defaults to 'inside'."""
    g = _group(placement=None)
    actions = _build_insert_under_marker_actions([g], [group_id(g)], [0])
    assert actions[0]["placement"] == "inside"


def test_null_target_group_no_instruction():
    """An approved group with a null target_path emits no path-less instruction."""
    g = _group(target_path=None)
    actions = _build_insert_under_marker_actions([g], [group_id(g)], [0])
    assert actions == []


# ── 6. end-to-end reducer→parser→render gate ──────────────────────────────────


def test_end_to_end_approved_then_render():
    """Render section → parse approved ids → emit instruction for the approved group."""
    g = _group()
    md = _render_section([g])
    approved = parse_tag_handler_groups(md)
    actions = _build_insert_under_marker_actions([g], approved, [0])
    assert len(actions) == 1
    assert actions[0]["target_path"] == g["target_path"]
    assert actions[0]["content"] == g["composed_block"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
