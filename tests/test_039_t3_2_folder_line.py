#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t3_2_folder_line.py — spec 039 T3.2 (PRD F1-AC2).

Pass 1 renders a non-checkbox `  - Folder: \\`<dirname(destination)>\\`` sub-line
directly under the Rename line, in both rename variants, and conflict records
carry `proposed_dir: None`. Pass 2's parser must keep ignoring that line until
T3.3 teaches it to read it.

Mutations guarded: dropping the sub-line from either variant (exact-line
assertions); emitting it as a checkbox (the parser round-trip changes);
omitting `proposed_dir` from records (schema + detect assertions);
a parser that misreads the folder line as a name or a tick (round-trip test).

CON-7: fixtures and fakes only.
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


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_module("suggestions_reducer_t039_t32", "suggestions-reducer.py")
PARSER = _load_module("suggestion_parser_t039_t32", "suggestion-parser.py")

SOURCE = "100 Inbox/Scans/karte.png"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
DEST = f"{ASSET_FOLDER}karte.png"
FOLDER_LINE = f"  - Folder: `{ASSET_FOLDER.rstrip('/')}`"


def _conflict(**overrides) -> dict:
    base = {
        "source": SOURCE,
        "destination": DEST,
        "same_file": None,
        "owner_source_items": ["100 Inbox/Scans/karte.md"],
        "proposed_name": "karte (2).png",
        "proposed_dir": None,
    }
    base.update(overrides)
    return base


def _lines(conflict: dict) -> list[str]:
    return REDUCER.render_attachment_conflicts_block([conflict], ASSET_FOLDER).splitlines()


def test_ordinary_conflict_folder_line_directly_after_rename_line():
    lines = _lines(_conflict())
    i = lines.index(f"- [x] Rename to `{ASSET_FOLDER}karte (2).png`")
    assert lines[i + 1] == FOLDER_LINE, lines
    assert lines[i + 2] == "- [ ] Keep in inbox", lines


def test_no_free_name_variant_renders_folder_line_too():
    lines = _lines(_conflict(proposed_name=None))
    marker = REDUCER.RENAME_IMPOSSIBLE_MARKER
    i = lines.index(f"- [ ] Rename to `` — {marker}")
    assert lines[i + 1] == FOLDER_LINE, lines
    assert lines[i + 2] == "- [x] Keep in inbox", lines


def test_folder_line_is_not_a_checkbox():
    assert "[" not in FOLDER_LINE.split("Folder:")[0]


def test_folder_text_is_dirname_of_destination_verbatim():
    lines = _lines(_conflict(destination="Some Folder/Sub/x.png"))
    assert "  - Folder: `Some Folder/Sub`" in lines


def test_destination_without_folder_component_renders_empty_backticks():
    lines = _lines(_conflict(destination="x.png"))
    assert "  - Folder: ``" in lines


def test_detect_records_carry_proposed_dir_none():
    result = REDUCER.detect_attachment_conflicts(
        [("100 Inbox/Scans/karte.md", [{
            "kind": "create_atomic_note",
            "suppressed": False,
            "attachments": [SOURCE],
        }])],
        ASSET_FOLDER,
        lambda folder: {DEST.casefold(): DEST},
    )
    assert len(result) == 1
    assert "proposed_dir" in result[0]
    assert result[0]["proposed_dir"] is None


def test_conflict_free_block_is_empty():
    assert REDUCER.render_attachment_conflicts_block([], ASSET_FOLDER) == ""


def _schema_and_doc(conflict: dict) -> tuple[dict, dict]:
    schema = json.loads(
        (REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json").read_text(
            encoding="utf-8"
        )
    )
    doc = {
        "schema_version": "1",
        "generated": "2026-10-12T00:00:00Z",
        "run_id": "t039-t3-2",
        "profile": "miyo",
        "source_items": 1,
        "sections": [],
        "attachment_conflicts": [conflict],
        "rendered_attachment_conflicts_md": REDUCER.render_attachment_conflicts_block(
            [conflict], ASSET_FOLDER
        ),
    }
    return schema, doc


def test_record_with_proposed_dir_validates_and_without_it_fails():
    from jsonschema import ValidationError, validate  # noqa: PLC0415
    import pytest  # noqa: PLC0415

    schema, doc = _schema_and_doc(_conflict())
    validate(instance=doc, schema=schema)
    schema, doc = _schema_and_doc(_conflict(proposed_dir="Elsewhere"))
    validate(instance=doc, schema=schema)
    bare = _conflict()
    del bare["proposed_dir"]
    schema, doc = _schema_and_doc(bare)
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


def _remedies(text: str) -> list[dict]:
    return PARSER.parse_attachment_conflict_remedies(text)


def test_untouched_doc_with_folder_line_parses_to_same_remedies_as_without():
    for conflict in (_conflict(), _conflict(proposed_name=None)):
        with_line = REDUCER.render_attachment_conflicts_block([conflict], ASSET_FOLDER)
        without = "\n".join(
            ln for ln in with_line.splitlines() if not ln.startswith("  - Folder:")
        ) + "\n"
        assert with_line != without
        assert _remedies(with_line) == _remedies(without), (with_line,)
        assert len(_remedies(with_line)) == 1
