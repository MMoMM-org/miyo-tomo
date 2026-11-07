#!/usr/bin/env python3
# version: 0.1.2
"""test_note_process_lib.py — Behavioural tests for lib.note_process (spec 044 T1.3).

Covers the process file owner for config/note-processes/<template-stem>.md:
- read: missing file, full file, destination only, guidance only, decline
  marker alone (declined, no process), broken YAML and wrong types (error set,
  no exception)
- missing_required: required points absent from an outline
- write: rejects a required point absent from the outline and writes nothing;
  replaces a decline marker
- decline: writes a marker that read reports as declined
- the schema documents the frontmatter a written file carries
- destination follows lib/note_paths.vault_folder on write (DestinationError)
  and read (error set); dedicated stem error; check_outline and a tolerant
  outline_points
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
SCHEMA_PATH = Path(__file__).parent.parent / "tomo" / "schemas" / "note-process.schema.json"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_process  # noqa: E402

TEMPLATE = "Meeting Notes"

OUTLINE = {
    "template": "Templates/Meeting Notes.md",
    "frontmatter": [{"key": "attendees", "has_value": False, "line": 2}],
    "headings": [
        {"level": 2, "text": "Agenda", "line": 5, "has_body": False},
        {"level": 2, "text": "Decisions", "line": 7, "has_body": False},
    ],
    "tokens": [
        {"name": "title", "line": 1, "prefilled": False},
        {"name": "date_iso", "line": 3, "prefilled": True},
    ],
    "templater": [],
    "frontmatter_ok": True,
}


def _write(process_dir: Path, text: str) -> Path:
    process_dir.mkdir(parents=True, exist_ok=True)
    path = process_dir / f"{TEMPLATE}.md"
    path.write_text(text, encoding="utf-8")
    return path


# ── Outline points ───────────────────────────────────────────────────────────


def test_points_are_headings_frontmatter_keys_and_open_tokens():
    assert note_process.outline_points(OUTLINE) == ["attendees", "Agenda", "Decisions", "title"]


# ── read ─────────────────────────────────────────────────────────────────────


def test_read_missing_file_reports_no_process(tmp_path):
    result = note_process.read_process(tmp_path, TEMPLATE)

    assert result == {
        "exists": False, "declined": False, "destination": "", "required": [],
        "guidance": "", "missing_required": [], "error": "",
    }


def test_read_full_file(tmp_path):
    _write(tmp_path, (
        "---\ndestination: Efforts/Meetings/\nrequired:\n  - Agenda\n  - Decisions\n---\n"
        "Ask for decisions first.\n"
    ))

    result = note_process.read_process(tmp_path, TEMPLATE, OUTLINE)

    assert result["exists"] is True
    assert result["declined"] is False
    assert result["destination"] == "Efforts/Meetings/"
    assert result["required"] == ["Agenda", "Decisions"]
    assert result["guidance"] == "Ask for decisions first."
    assert result["missing_required"] == []
    assert result["error"] == ""


def test_read_destination_only(tmp_path):
    _write(tmp_path, "---\ndestination: Efforts/Meetings\n---\n")

    result = note_process.read_process(tmp_path, TEMPLATE)

    assert result["exists"] is True
    assert result["destination"] == "Efforts/Meetings/"
    assert result["required"] == []
    assert result["guidance"] == ""


def test_read_guidance_only_without_frontmatter(tmp_path):
    _write(tmp_path, "Keep it short.\n")

    result = note_process.read_process(tmp_path, TEMPLATE)

    assert result["exists"] is True
    assert result["declined"] is False
    assert result["destination"] == ""
    assert result["guidance"] == "Keep it short."
    assert result["error"] == ""


def test_decline_marker_alone_reads_as_declined_with_no_process(tmp_path):
    _write(tmp_path, "---\noffer: never\n---\n")

    result = note_process.read_process(tmp_path, TEMPLATE, OUTLINE)

    assert result == {
        "exists": True, "declined": True, "destination": "", "required": [],
        "guidance": "", "missing_required": [], "error": "",
    }


def test_offer_never_beside_other_fields_is_a_process_not_a_decline(tmp_path):
    _write(tmp_path, "---\noffer: never\ndestination: Efforts/\n---\n")

    result = note_process.read_process(tmp_path, TEMPLATE)

    assert result["declined"] is False
    assert result["destination"] == "Efforts/"


@pytest.mark.parametrize("text", [
    "---\ndestination: [unclosed\n---\n",
    "---\ndestination: Efforts/\n",
    "---\n- a list\n---\n",
    "---\nrequired: Agenda\n---\n",
    "---\ndestination: 42\n---\n",
    "---\noffer: sometimes\n---\n",
])
def test_broken_file_sets_error_without_raising(tmp_path, text):
    _write(tmp_path, text)

    result = note_process.read_process(tmp_path, TEMPLATE, OUTLINE)

    assert result["exists"] is True
    assert result["error"]
    assert result["declined"] is False
    assert result["required"] == []
    assert result["missing_required"] == []


def test_error_text_never_carries_the_file_content(tmp_path):
    _write(tmp_path, "---\ndestination: [secret-client-name\n---\n")

    result = note_process.read_process(tmp_path, TEMPLATE)

    assert "secret-client-name" not in result["error"]


# ── missing_required ─────────────────────────────────────────────────────────


def test_missing_required_lists_points_absent_from_the_outline(tmp_path):
    _write(tmp_path, "---\nrequired:\n  - Agenda\n  - Risks\n  - date_iso\n---\n")

    result = note_process.read_process(tmp_path, TEMPLATE, OUTLINE)

    assert result["required"] == ["Agenda", "Risks", "date_iso"]
    assert result["missing_required"] == ["Risks", "date_iso"]


def test_missing_required_is_empty_without_an_outline(tmp_path):
    _write(tmp_path, "---\nrequired:\n  - Risks\n---\n")

    assert note_process.read_process(tmp_path, TEMPLATE)["missing_required"] == []


# ── write ────────────────────────────────────────────────────────────────────


def test_write_rejects_a_required_point_absent_from_the_outline(tmp_path):
    result = note_process.write_process(
        tmp_path, TEMPLATE, OUTLINE, destination="Efforts/", required=["Agenda", "Risks"],
    )

    assert result == {"written": False, "rejected_required": ["Risks"]}
    assert not (tmp_path / f"{TEMPLATE}.md").exists()


def test_write_then_read_round_trip(tmp_path):
    result = note_process.write_process(
        tmp_path / "note-processes", TEMPLATE, OUTLINE, destination="Efforts/Meetings",
        required=["Agenda", "title"], guidance="Ask for decisions first.\n",
    )

    assert result == {"written": True, "rejected_required": []}
    read = note_process.read_process(tmp_path / "note-processes", TEMPLATE, OUTLINE)
    assert read["destination"] == "Efforts/Meetings/"
    assert read["required"] == ["Agenda", "title"]
    assert read["guidance"] == "Ask for decisions first."
    assert read["declined"] is False


def test_written_frontmatter_validates_against_the_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    note_process.write_process(
        tmp_path, TEMPLATE, OUTLINE, destination="Efforts/", required=["Agenda"],
    )
    text = (tmp_path / f"{TEMPLATE}.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---\n")[1])
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    jsonschema.validate(frontmatter, schema)
    jsonschema.validate({"offer": "never"}, schema)


def test_decline_then_write_replaces_the_marker(tmp_path):
    assert note_process.write_decline(tmp_path, TEMPLATE) == {"written": True}
    assert note_process.read_process(tmp_path, TEMPLATE)["declined"] is True

    note_process.write_process(tmp_path, TEMPLATE, OUTLINE, destination="Efforts/")

    read = note_process.read_process(tmp_path, TEMPLATE)
    assert read["declined"] is False
    assert read["destination"] == "Efforts/"
    assert "offer" not in (tmp_path / f"{TEMPLATE}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", ["", "../escape", "a/b", ".hidden"])
def test_a_malformed_template_stem_is_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        note_process.read_process(tmp_path, bad)
    with pytest.raises(ValueError):
        note_process.write_decline(tmp_path, bad)


# ── Drift findings: decline rule, destination without slash, privacy ─────────

MARKER = "SECRETMARKER"


def test_offer_never_with_a_body_is_a_process_not_a_decline(tmp_path):
    _write(tmp_path, "---\noffer: never\n---\nKeep it short.\n")

    result = note_process.read_process(tmp_path, TEMPLATE)

    assert result["declined"] is False
    assert result["guidance"] == "Keep it short."
    assert result["error"] == ""


def test_schema_accepts_a_destination_without_trailing_slash():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    jsonschema.validate({"destination": "Efforts/Meetings"}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"destination": ""}, schema)


def test_malformed_template_stem_error_does_not_echo_the_stem(tmp_path):
    with pytest.raises(ValueError) as read_exc:
        note_process.read_process(tmp_path, f"../{MARKER}")
    with pytest.raises(ValueError) as write_exc:
        note_process.write_decline(tmp_path, f"{MARKER}/x")

    assert MARKER not in str(read_exc.value)
    assert MARKER not in str(write_exc.value)


@pytest.mark.parametrize("text", [
    f"---\ndestination: [{MARKER}\n---\n",
    f"---\n- {MARKER}\n---\n",
    f"---\nrequired: {MARKER}\n---\n",
    f"---\noffer: {MARKER}\n---\n",
    f"---\ndestination: {MARKER}/\n",
])
def test_no_read_error_carries_a_value_from_the_file(tmp_path, text):
    _write(tmp_path, text)

    result = note_process.read_process(tmp_path, TEMPLATE)

    assert result["error"]
    assert MARKER not in result["error"]


# ── T2.4: destinations follow the shared /note path rules ────────────────────

from lib import note_paths  # noqa: E402

BAD_DESTINATIONS = ["../x", "../../x", "/abs", "/", "a//b", "a//b\\c", "a\\b", "a\x07b",
                    "a\u200bb", "", "   ", ".hidden", "{{dest}}"]


@pytest.mark.parametrize("dest", BAD_DESTINATIONS)
def test_write_rejects_a_destination_the_path_rules_refuse(tmp_path, dest):
    with pytest.raises(note_process.DestinationError) as exc:
        note_process.write_process(tmp_path, TEMPLATE, OUTLINE, destination=dest)

    assert not (tmp_path / f"{TEMPLATE}.md").exists()
    assert dest.strip() == "" or dest not in str(exc.value)


@pytest.mark.parametrize("dest", BAD_DESTINATIONS + [42])
def test_read_reports_a_stored_bad_destination_as_an_error(tmp_path, dest):
    head = yaml.safe_dump({"destination": dest, "required": ["Agenda"]}, allow_unicode=True)
    _write(tmp_path, f"---\n{head}---\nGuide.\n")

    result = note_process.read_process(tmp_path, TEMPLATE, OUTLINE)

    assert result["exists"] is True and result["declined"] is False
    assert result["error"] == "destination is not a relative vault folder"
    assert result["destination"] == ""
    assert result["required"] == [] and result["guidance"] == ""


@pytest.mark.parametrize("empty_key", ["destination:", "offer:", "destination: ~\noffer: null"])
def test_an_empty_destination_or_offer_key_reads_as_unset(tmp_path, empty_key):
    _write(tmp_path, f"---\n{empty_key}\nrequired:\n  - Agenda\n---\nGuide.\n")

    result = note_process.read_process(tmp_path, TEMPLATE, OUTLINE)

    assert result == {
        "exists": True, "declined": False, "destination": "", "required": ["Agenda"],
        "guidance": "Guide.", "missing_required": [], "error": "",
    }


def test_an_empty_offer_key_alone_is_neither_a_decline_nor_broken(tmp_path):
    _write(tmp_path, "---\noffer:\n---\n")

    result = note_process.read_process(tmp_path, TEMPLATE)

    assert result["exists"] is True
    assert result["declined"] is False
    assert result["error"] == ""


@pytest.mark.parametrize("dest", ["../x", "''", "42"])
def test_a_present_invalid_destination_beside_an_empty_offer_is_still_broken(tmp_path, dest):
    _write(tmp_path, f"---\ndestination: {dest}\noffer:\nrequired:\n  - Agenda\n---\nGuide.\n")

    result = note_process.read_process(tmp_path, TEMPLATE, OUTLINE)

    assert result["error"] == "destination is not a relative vault folder"
    assert result["required"] == [] and result["guidance"] == ""


@pytest.mark.parametrize("dest", ["Efforts/Meetings", "  Efforts/Meetings/ ", "Ätlas",
                                  "Atlas/\U0001F469\u200d\U0001F4BB"])
def test_written_destination_reads_back_as_vault_folder_gives_it(tmp_path, dest):
    note_process.write_process(tmp_path, TEMPLATE, OUTLINE, destination=dest)

    read = note_process.read_process(tmp_path, TEMPLATE)

    assert read["error"] == ""
    assert read["destination"] == note_paths.vault_folder(dest)


def test_a_malformed_stem_raises_the_dedicated_stem_error(tmp_path):
    with pytest.raises(note_process.TemplateStemError):
        note_process.read_process(tmp_path, "../x")


# ── outline shape lives in the library ───────────────────────────────────────


def test_outline_points_skips_items_that_are_not_objects():
    outline = {"frontmatter": "bad", "headings": ["x", {"text": "Agenda"}, 7], "tokens": None}

    assert note_process.outline_points(outline) == ["Agenda"]


@pytest.mark.parametrize("data", [
    [MARKER], {"template": MARKER}, {**OUTLINE, "headings": MARKER},
    {**OUTLINE, "tokens": [MARKER]},
])
def test_check_outline_refuses_a_wrong_shape_without_echo(data):
    with pytest.raises(note_process.OutlineError) as exc:
        note_process.check_outline(data)

    assert MARKER not in str(exc.value)


def test_check_outline_returns_a_good_outline():
    assert note_process.check_outline(OUTLINE) is OUTLINE
