#!/usr/bin/env python3
# version: 0.1.0
"""test_note_process.py — Behavioural tests for note-process.py (spec 044 T2.4).

Covers the CLI over lib.note_process for config/note-processes/<stem>.md:
- read: without --outline (missing_required empty), with --outline
  (missing_required set), missing file, broken file (error, exit 0, no file text)
- write: from an outline file; rejects an absent required point with exit 1 and
  writes nothing; --required trimming; guidance from a file; replaces a decline
- decline: writes the marker that read then reports as declined
- bad invocation (exit 2, no file text): malformed outline, missing guidance
  file, malformed stem, missing --outline
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "note-process.py"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_process  # noqa: E402

TEMPLATE = "Meeting Notes"
SECRET = "SECRET-MARKER-9c1e client Zyx"
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
READ_KEYS = {"exists", "declined", "destination", "required", "guidance",
             "missing_required", "error"}


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("note_process_cli", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _outline(instance: Path, data=OUTLINE, raw: str | None = None) -> str:
    path = instance / "tomo-tmp" / "note" / "process-outline.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw if raw is not None else json.dumps(data), encoding="utf-8")
    return str(path.relative_to(instance))


def _process_file(instance: Path) -> Path:
    return instance / note_process.PROCESS_DIR / f"{TEMPLATE}.md"


def _seed(instance: Path, text: str) -> None:
    path = _process_file(instance)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(mod, capsys, argv):
    code = mod.main(argv)
    out, err = capsys.readouterr()
    return code, (json.loads(out) if out.strip() else None), out, err


# ---------------------------------------------------------------- read

def test_read_missing_file_reports_not_exists(mod, instance, capsys):
    code, out, *_ = _run(mod, capsys, ["read", "--template", TEMPLATE])
    assert code == 0
    assert set(out) == READ_KEYS
    assert out["exists"] is False and out["declined"] is False and out["error"] == ""


def test_read_without_outline_leaves_missing_required_empty(mod, instance, capsys):
    _seed(instance, "---\ndestination: Atlas\nrequired: [Agenda, Risks]\n---\nAsk agenda first.\n")
    code, out, *_ = _run(mod, capsys, ["read", "--template", TEMPLATE])
    assert code == 0
    assert out["destination"] == "Atlas/"
    assert out["required"] == ["Agenda", "Risks"]
    assert out["guidance"] == "Ask agenda first."
    assert out["missing_required"] == []


def test_read_with_outline_reports_missing_required(mod, instance, capsys):
    _seed(instance, "---\nrequired: [Agenda, Risks]\n---\n")
    outline = _outline(instance)
    code, out, *_ = _run(mod, capsys, ["read", "--template", TEMPLATE, "--outline", outline])
    assert code == 0
    assert out["missing_required"] == ["Risks"]


def test_read_broken_file_reports_error_without_file_text(mod, instance, capsys):
    _seed(instance, f"---\ndestination: [{SECRET}\n---\n{SECRET}\n")
    code, out, raw, err = _run(mod, capsys, ["read", "--template", TEMPLATE])
    assert code == 0
    assert out["exists"] is True and out["error"]
    assert SECRET not in raw and SECRET not in err


# ---------------------------------------------------------------- write

def test_write_from_outline_file_writes_process(mod, instance, capsys):
    outline = _outline(instance)
    guidance = instance / "guidance.txt"
    guidance.write_text("Ask decisions last.\n", encoding="utf-8")
    code, out, *_ = _run(mod, capsys, [
        "write", "--template", TEMPLATE, "--outline", outline, "--destination", "Atlas/Meetings",
        "--required", " Agenda , Decisions,,", "--guidance-file", str(guidance)])
    assert code == 0
    assert out == {"written": True, "rejected_required": []}
    back = note_process.read_process(note_process.PROCESS_DIR, TEMPLATE)
    assert back["destination"] == "Atlas/Meetings/"
    assert back["required"] == ["Agenda", "Decisions"]
    assert back["guidance"] == "Ask decisions last."


def test_write_rejects_absent_required_point_and_writes_nothing(mod, instance, capsys):
    outline = _outline(instance)
    code, out, *_ = _run(mod, capsys, [
        "write", "--template", TEMPLATE, "--outline", outline, "--required", "Agenda,Risks"])
    assert code == 1
    assert out == {"written": False, "rejected_required": ["Risks"]}
    assert not _process_file(instance).exists()


def test_write_rejected_keeps_existing_file_untouched(mod, instance, capsys):
    _seed(instance, "---\noffer: never\n---\n")
    before = _process_file(instance).read_bytes()
    outline = _outline(instance)
    code, *_ = _run(mod, capsys, [
        "write", "--template", TEMPLATE, "--outline", outline, "--required", "Risks"])
    assert code == 1
    assert _process_file(instance).read_bytes() == before


def test_point_name_with_comma_is_split_and_rejected(mod, instance, capsys):
    outline = _outline(instance, {**OUTLINE, "headings": [
        {"level": 2, "text": "Risks, issues", "line": 5, "has_body": False}]})
    code, out, *_ = _run(mod, capsys, [
        "write", "--template", TEMPLATE, "--outline", outline, "--required", "Risks, issues"])
    assert code == 1
    assert out["rejected_required"] == ["Risks", "issues"]
    assert not _process_file(instance).exists()


# ---------------------------------------------------------------- decline

def test_decline_writes_marker_read_reports_declined(mod, instance, capsys):
    code, out, *_ = _run(mod, capsys, ["decline", "--template", TEMPLATE])
    assert code == 0 and out == {"written": True}
    code, out, *_ = _run(mod, capsys, ["read", "--template", TEMPLATE])
    assert out["exists"] is True and out["declined"] is True


def test_write_after_decline_replaces_marker(mod, instance, capsys):
    _run(mod, capsys, ["decline", "--template", TEMPLATE])
    outline = _outline(instance)
    code, out, *_ = _run(mod, capsys, [
        "write", "--template", TEMPLATE, "--outline", outline, "--destination", "Atlas/"])
    assert code == 0 and out["written"] is True
    code, out, *_ = _run(mod, capsys, ["read", "--template", TEMPLATE])
    assert out["declined"] is False and out["destination"] == "Atlas/"


# ---------------------------------------------------------------- bad invocation

@pytest.mark.parametrize("raw", [
    None,                                           # missing file
    f"not json {SECRET}",                           # not JSON
    json.dumps([SECRET]),                           # not an object
    json.dumps({"template": SECRET, "error": "KadoError: x"}),  # template-outline error shape
    json.dumps({**OUTLINE, "headings": SECRET}),    # list field not a list
    json.dumps({**OUTLINE, "tokens": [SECRET]}),    # list item not an object
])
@pytest.mark.parametrize("command", ["read", "write"])
def test_malformed_outline_exits_2_without_file_text(mod, instance, capsys, raw, command):
    outline = "tomo-tmp/note/absent.json" if raw is None else _outline(instance, raw=raw)
    _seed(instance, "---\nrequired: [Agenda]\n---\n")
    before = _process_file(instance).read_bytes()
    code, out, raw_out, err = _run(mod, capsys, [
        command, "--template", TEMPLATE, "--outline", outline, "--required", "Agenda"]
        if command == "write" else [command, "--template", TEMPLATE, "--outline", outline])
    assert code == 2
    assert raw_out == ""
    assert SECRET not in err and err.strip()
    assert _process_file(instance).read_bytes() == before


def test_missing_guidance_file_exits_2_and_writes_nothing(mod, instance, capsys):
    outline = _outline(instance)
    code, _, raw_out, err = _run(mod, capsys, [
        "write", "--template", TEMPLATE, "--outline", outline, "--guidance-file", "absent.txt"])
    assert code == 2 and raw_out == "" and err.strip()
    assert not _process_file(instance).exists()


@pytest.mark.parametrize("stem", ["../escape", "a/b", ".hidden", "  "])
@pytest.mark.parametrize("command", ["read", "decline"])
def test_malformed_stem_exits_2_without_echo(mod, instance, capsys, stem, command):
    code, _, raw_out, err = _run(mod, capsys, [command, "--template", stem])
    assert code == 2 and raw_out == ""
    assert stem.strip() == "" or stem not in err
    assert not (instance / note_process.PROCESS_DIR).exists()


def test_write_requires_outline(mod, instance, capsys):
    with pytest.raises(SystemExit) as exc:
        mod.main(["write", "--template", TEMPLATE])
    assert exc.value.code == 2
    assert not _process_file(instance).exists()


def test_output_is_ascii_escaped(mod, instance, capsys):
    _seed(instance, "---\ndestination: Ätlas\n---\nFrage zuerst.\n")
    code, out, raw_out, _ = _run(mod, capsys, ["read", "--template", TEMPLATE])
    assert code == 0 and raw_out.isascii()
    assert out["destination"] == "Ätlas/"
