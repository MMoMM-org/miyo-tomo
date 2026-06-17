"""test_proposed_moc_merge.py — #67: same-name Proposed MOCs merge into one create_moc.

When a user renames two distinct Proposed MOCs to the same final Name, the
pipeline must emit ONE create_moc whose supporting_items is the union of the
group — otherwise two create_moc land at the same destination and the second
overwrites the first on apply, silently dropping children.

Covers both layers:
  - suggestion-parser.parse_proposed_mocs — primary merge by final Name.
  - instruction-render._build_create_moc_actions — defense-in-depth dedupe by
    destination (union supporting_items) so a duplicate can never reach Hashi.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_parser_spec = importlib.util.spec_from_file_location(
    "suggestion_parser", SCRIPTS_DIR / "suggestion-parser.py"
)
_parser = importlib.util.module_from_spec(_parser_spec)
assert _parser_spec.loader is not None
sys.modules["suggestion_parser"] = _parser
_parser_spec.loader.exec_module(_parser)

_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render"] = _ir
_ir_spec.loader.exec_module(_ir)


def _proposed_block(header: str, name: str, parent: str, items: str) -> list[str]:
    return [
        f"### Proposed MOC: {header}",
        "",
        "- [x] Approve",
        "- [ ] Skip",
        "",
        f"**Name:** {name}",
        f"**Parent:** [[{parent}]]",
        f"**Supporting items:** {items}",
        "",
    ]


def _doc(*blocks: list[str]) -> str:
    parts = ["## Proposed MOCs", ""]
    for b in blocks:
        parts += b
    parts += ["## Next Section", ""]
    return "\n".join(parts)


# ── parser-side merge ───────────────────────────────────────────────────────


class TestParserMergeByName:
    def test_same_name_proposals_merge_to_one(self):
        text = _doc(
            _proposed_block("Gesellschaftsspiele", "Board Games (MOC)",
                            "2700 - Art & Recreation", "S01"),
            _proposed_block("Brettspiele", "Board Games (MOC)",
                            "2700 - Art & Recreation", "S02, S03"),
        )
        mocs = _parser.parse_proposed_mocs(text)
        assert len(mocs) == 1
        assert mocs[0]["title"] == "Board Games (MOC)"

    def test_supporting_items_are_unioned(self):
        text = _doc(
            _proposed_block("A", "Board Games (MOC)", "2700 - Art", "S01"),
            _proposed_block("B", "Board Games (MOC)", "2700 - Art", "S02, S03"),
        )
        items = _parser.parse_proposed_mocs(text)[0]["supporting_items"]
        assert items == "S01, S02, S03"

    def test_first_parent_kept_on_merge(self):
        text = _doc(
            _proposed_block("A", "Board Games (MOC)", "First Parent", "S01"),
            _proposed_block("B", "Board Games (MOC)", "Second Parent", "S02"),
        )
        moc = _parser.parse_proposed_mocs(text)[0]
        assert "First Parent" in moc["parent_moc"]

    def test_distinct_names_not_merged(self):
        text = _doc(
            _proposed_block("A", "Board Games (MOC)", "2700 - Art", "S01"),
            _proposed_block("B", "Card Games (MOC)", "2700 - Art", "S02"),
        )
        names = {m["title"] for m in _parser.parse_proposed_mocs(text)}
        assert names == {"Board Games (MOC)", "Card Games (MOC)"}

    def test_union_dedupes_repeated_items(self):
        text = _doc(
            _proposed_block("A", "Board Games (MOC)", "2700 - Art", "S01, S02"),
            _proposed_block("B", "Board Games (MOC)", "2700 - Art", "S02, S03"),
        )
        assert _parser.parse_proposed_mocs(text)[0]["supporting_items"] == "S01, S02, S03"


# ── render-side defense-in-depth dedupe ─────────────────────────────────────


class TestRenderDedupeByDestination:
    def test_duplicate_create_moc_collapsed(self):
        manifest = [
            {"action": "create_moc", "title": "Board Games (MOC)",
             "destination": "Atlas/200 Maps/", "rendered_file": "bg.md",
             "supporting_items": "S01"},
            {"action": "create_moc", "title": "Board Games (MOC)",
             "destination": "Atlas/200 Maps/", "rendered_file": "bg2.md",
             "supporting_items": "S02, S03"},
        ]
        actions = _ir._build_create_moc_actions(manifest, "100 Inbox/", [0])
        creates = [a for a in actions if a["action"] == "create_moc"]
        assert len(creates) == 1
        assert creates[0]["supporting_items"] == "S01, S02, S03"

    def test_distinct_destinations_kept(self):
        manifest = [
            {"action": "create_moc", "title": "A (MOC)", "destination": "Atlas/200 Maps/",
             "rendered_file": "a.md", "supporting_items": "S01"},
            {"action": "create_moc", "title": "B (MOC)", "destination": "Atlas/200 Maps/",
             "rendered_file": "b.md", "supporting_items": "S02"},
        ]
        creates = [a for a in _ir._build_create_moc_actions(manifest, "100 Inbox/", [0])
                   if a["action"] == "create_moc"]
        assert len(creates) == 2

    def test_union_supporting_items_helper_list_shape(self):
        assert _ir._union_supporting_items(["A", "B"], ["B", "C"]) == ["A", "B", "C"]

    def test_union_supporting_items_helper_string_shape(self):
        assert _ir._union_supporting_items("A, B", "B, C") == "A, B, C"
