#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t3_3_parser_reads_folder.py — spec 039 T3.3 (PRD F1-AC3/4/8/9).

Pass 2 reads the owner's folder on both paths:

- markdown: `_walk_attachment_conflicts` reads the non-checkbox
  `  - Folder: \\`<dir>\\`` sub-line T3.2 renders, and
  `_join_attachment_conflict_remedies` carries its text verbatim as
  `proposed_dir`, with `dir_is_owner_supplied` = the text differs EXACTLY
  from the folder Pass 1 rendered (`dirname(destination)` of the doc record);
- wire: `build_from_wire` projects `attachment_conflicts[].proposed_dir` with
  `dir_is_owner_supplied` True whenever it is non-null.

Mechanisms and the mutation each test falsifies:

1. The folder line is read at all — mutation: drop the non-checkbox branch;
   every `proposed_dir` comes back None and the untouched/edited cases fail.
2. Exact-difference provenance, no normalisation — mutation: compare after
   `rstrip("/")`; the trailing-slash case reads False and Phase 4 never sees
   it to refuse `trailing_separator`.
3. Disagreeing duplicate folder lines collapse to "" (owner-supplied, refused
   `blank` downstream) — mutation: first-wins or last-wins; the duplicate
   test reads one of the two typed folders instead of "".
4. A backtick-wrapped body is taken between the OUTER pair — mutation: reuse
   the rename line's first-pair regex; a folder whose name contains a
   backtick reads truncated and owner-supplied though nobody touched it.
5. The folder line is entry-scoped — mutation: let a stray line before the
   first `###` heading set state; the stray test then sees it leak.

Fixtures come from the real Pass-1 renderer (`render_attachment_conflicts_block`)
and are string-edited the way an owner edits them. CON-7: fixtures and fakes
only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from attachment_plan_fakes import move_asset_actions_from_remedies  # noqa: E402


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


PARSER = _load("suggestion_parser_t039_t33", "suggestion-parser.py")
REDUCER = _load("suggestions_reducer_t039_t33", "suggestions-reducer.py")

INBOX = "100 Inbox/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
DEFAULT_DIR = ASSET_FOLDER.rstrip("/")
SOURCE = "100 Inbox/Scans/karte.png"
OCCUPIED = f"{ASSET_FOLDER}karte.png"
COMPUTED = "karte (2).png"
TYPED_DIR = "Atlas/290 Assets/Maps"

SIX_KEYS = {
    "source", "remedy", "proposed_name", "name_is_owner_supplied",
    "proposed_dir", "dir_is_owner_supplied",
}


def _conflict(proposed_name: str | None = COMPUTED, destination: str = OCCUPIED) -> dict:
    return {
        "source": SOURCE,
        "destination": destination,
        "same_file": False,
        "owner_source_items": ["100 Inbox/Dresden.md"],
        "proposed_name": proposed_name,
        "proposed_dir": None,
    }


def _rendered(conflict: dict) -> str:
    return REDUCER.render_attachment_conflicts_block([conflict], ASSET_FOLDER)


def _replace_folder_line(rendered: str, new_line: str | None) -> str:
    """Replace (or delete, when `new_line` is None) the single folder line."""
    lines = rendered.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.startswith("  - Folder:")]
    assert len(idx) == 1, lines
    if new_line is None:
        del lines[idx[0]]
    else:
        lines[idx[0]] = new_line
    return "\n".join(lines) + "\n"


def _record(markdown: str, conflict: dict) -> dict:
    records = PARSER._join_attachment_conflict_remedies(
        PARSER.parse_attachment_conflict_remedies(markdown),
        {"attachment_conflicts": [conflict]},
    )
    assert len(records) == 1, records
    return records[0]


def _folder(markdown: str, conflict: dict) -> tuple[object, object]:
    r = _record(markdown, conflict)
    return r["proposed_dir"], r["dir_is_owner_supplied"]


# ── markdown path ───────────────────────────────────────────────────────────

def test_untouched_folder_line_is_the_rendered_text_not_owner_supplied():
    for conflict in (_conflict(), _conflict(proposed_name=None)):
        assert _folder(_rendered(conflict), conflict) == (DEFAULT_DIR, False)


def test_edited_folder_is_verbatim_and_owner_supplied():
    c = _conflict()
    md = _replace_folder_line(_rendered(c), f"  - Folder: `{TYPED_DIR}`")
    assert _folder(md, c) == (TYPED_DIR, True)


def test_default_folder_with_trailing_slash_is_verbatim_and_owner_supplied():
    """No normalisation here: Phase 4 refuses `trailing_separator`, on both
    paths alike — the parser must not decide the slash away."""
    c = _conflict()
    md = _replace_folder_line(_rendered(c), f"  - Folder: `{DEFAULT_DIR}/`")
    assert _folder(md, c) == (f"{DEFAULT_DIR}/", True)


def test_edge_whitespace_inside_the_backticks_is_kept():
    c = _conflict()
    md = _replace_folder_line(_rendered(c), f"  - Folder: ` {TYPED_DIR}`")
    assert _folder(md, c) == (f" {TYPED_DIR}", True)


def test_deleted_folder_line_is_none_not_owner_supplied():
    c = _conflict()
    md = _replace_folder_line(_rendered(c), None)
    assert _folder(md, c) == (None, False)


def test_blank_backticks_are_empty_and_owner_supplied():
    c = _conflict()
    md = _replace_folder_line(_rendered(c), "  - Folder: ``")
    assert _folder(md, c) == ("", True)


def test_blank_backticks_rendered_for_a_folderless_destination_are_untouched():
    """Exact-difference rule: "" is the rendered text when the destination has
    no folder component, so leaving it alone is not an owner edit."""
    c = _conflict(destination="karte.png")
    assert _folder(_rendered(c), c) == ("", False)


def test_folder_name_containing_a_backtick_round_trips_untouched():
    c = _conflict(destination="Atlas/Odd`Name/karte.png")
    md = _rendered(c)
    assert "  - Folder: `Atlas/Odd`Name`" in md.splitlines()
    assert _folder(md, c) == ("Atlas/Odd`Name", False)


def test_folder_line_without_backticks_is_malformed_empty_and_owner_supplied():
    """Owner removed the backticks: no guess at what they meant, no silent
    fallback to the default — "" is refused `blank` downstream."""
    c = _conflict()
    md = _replace_folder_line(_rendered(c), f"  - Folder: {TYPED_DIR}")
    assert _folder(md, c) == ("", True)


def test_text_after_the_closing_backtick_is_malformed():
    c = _conflict()
    md = _replace_folder_line(_rendered(c), f"  - Folder: `{TYPED_DIR}` (moved)")
    assert _folder(md, c) == ("", True)


def test_two_agreeing_folder_lines_read_as_one():
    c = _conflict()
    line = f"  - Folder: `{TYPED_DIR}`"
    md = _replace_folder_line(_rendered(c), line + "\n" + line)
    assert _folder(md, c) == (TYPED_DIR, True)


def test_two_disagreeing_folder_lines_are_refusable_not_resolved():
    """Neither first-wins nor last-wins: either would silently drop one of
    two owner edits. The entry carries "" so the move is withheld."""
    c = _conflict()
    for first, second in ((DEFAULT_DIR, TYPED_DIR), (TYPED_DIR, DEFAULT_DIR)):
        md = _replace_folder_line(
            _rendered(c), f"  - Folder: `{first}`\n  - Folder: `{second}`"
        )
        assert _folder(md, c) == ("", True), (first, second)


def test_folder_line_outside_an_entry_is_ignored():
    c = _conflict()
    rendered = _rendered(c)
    stray = f"- Folder: `{TYPED_DIR}`"
    head, sep, rest = rendered.partition("### ")
    md = head + stray + "\n\n" + sep + rest + "\n## Next Section\n\n" + stray + "\n"
    assert _folder(md, c) == (DEFAULT_DIR, False)


def test_folder_line_does_not_disturb_the_remedy_or_the_name():
    c = _conflict()
    md = _replace_folder_line(_rendered(c), f"  - Folder: `{TYPED_DIR}`")
    r = _record(md, c)
    assert r["remedy"] == "rename"
    assert r["proposed_name"] == COMPUTED
    assert r["name_is_owner_supplied"] is False


def test_source_missing_from_the_doc_degrades_like_the_name():
    c = _conflict()
    md = _replace_folder_line(_rendered(c), f"  - Folder: `{TYPED_DIR}`")
    records = PARSER._join_attachment_conflict_remedies(
        PARSER.parse_attachment_conflict_remedies(md), {"attachment_conflicts": []}
    )
    assert records[0]["proposed_dir"] is None
    assert records[0]["dir_is_owner_supplied"] is False


def test_a_folder_typed_inside_the_rename_backticks_is_still_refused_separator():
    """F1-AC8: the folder line does not make the rename line's own separator
    legal. The folder line itself is untouched here."""
    c = _conflict()
    lines = _rendered(c).splitlines()
    i = [n for n, ln in enumerate(lines) if "] Rename to " in ln][0]
    lines[i] = f"- [x] Rename to `Archive/{COMPUTED}`"
    r = _record("\n".join(lines) + "\n", c)
    assert r["proposed_name"] == f"Archive/{COMPUTED}"
    assert r["name_is_owner_supplied"] is True
    assert (r["proposed_dir"], r["dir_is_owner_supplied"]) == (DEFAULT_DIR, False)
    manifest = [{
        "id": "S01", "action": None, "title": "Dresden",
        "source_path": "Dresden.md", "rendered_file": "2026-01-01_0900_dresden.md",
        "destination": "Atlas/202 Notes/", "parent_moc": "", "parent_mocs": [],
        "tags": [], "attachments": [SOURCE],
    }]
    actions, skipped = move_asset_actions_from_remedies(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=[r]
    )
    assert actions == [], actions
    assert [s["refusal_reason"] for s in skipped] == ["separator_present"], skipped


def test_markdown_records_carry_exactly_six_keys():
    c = _conflict()
    assert set(_record(_rendered(c), c)) == SIX_KEYS


# ── wire path ───────────────────────────────────────────────────────────────

def _wire_remedies(proposed_dir: object) -> list[dict]:
    wire = {
        "suggestions": [],
        "attachment_conflicts": [{
            "source": SOURCE, "destination": OCCUPIED, "same_file": False,
            "remedy": "rename", "proposed_name": COMPUTED,
            "proposed_dir": proposed_dir,
        }],
    }
    return PARSER.build_from_wire(wire, "t_moc_tomo")["attachment_conflict_remedies"]


def test_wire_projects_a_non_null_folder_as_owner_supplied():
    for value in (TYPED_DIR, DEFAULT_DIR, f"{DEFAULT_DIR}/", ""):
        (r,) = _wire_remedies(value)
        assert (r["proposed_dir"], r["dir_is_owner_supplied"]) == (value, True), value


def test_wire_null_folder_is_none_not_owner_supplied():
    (r,) = _wire_remedies(None)
    assert (r["proposed_dir"], r["dir_is_owner_supplied"]) == (None, False)


def test_wire_records_carry_exactly_six_keys():
    (r,) = _wire_remedies(TYPED_DIR)
    assert set(r) == SIX_KEYS


# ── inventory (F1-AC9) ──────────────────────────────────────────────────────

def test_inventory_row_d26_names_the_wire_field_and_the_folder_literal():
    inventory = json.loads(
        (REPO_ROOT / "tomo" / "schemas" / "suggestions-decision-inventory.json")
        .read_text(encoding="utf-8")
    )
    rows = {row["id"]: row for row in inventory["decisions"]}
    assert "D26" in rows
    d26 = rows["D26"]
    assert d26["wire_field"] == "attachment_conflicts[].proposed_dir"
    assert d26["editable"] is True
    assert "- Folder:" in d26["parser_label"]
