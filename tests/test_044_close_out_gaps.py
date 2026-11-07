#!/usr/bin/env python3
# version: 0.1.0
"""test_044_close_out_gaps.py — spec 044 T4.3: criteria parts no test could fail.

The close-out trace (docs/XDD/specs/044-note-from-template/close-out.md §4)
found seven criterion parts with an imperative in the runtime text, or a
script behaviour, that no test pinned: deleting the line or changing the code
left the whole suite green. Each test below fails under the mutation the
close-out names for it.

The prose pins (F1-AC1, F1-AC3, F3-AC4, F4-AC4, F7-AC2, F7-AC8) only prove the
imperative exists in note-from-template/SKILL.md; whether the model follows it
is the live walk's or the eval's evidence, as for tests/test_note_skill_prose.py.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SKILL = REPO_ROOT / "tomo" / "dot_claude" / "skills" / "note-from-template" / "SKILL.md"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_process  # noqa: E402


def _section(heading: str) -> str:
    """One `## ` section of the skill, whitespace collapsed."""
    text = SKILL.read_text(encoding="utf-8")
    begin = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", begin + 1)
    return re.sub(r"\s+", " ", text[begin:end if end != -1 else len(text)])


# ── Prose pins ─────────────────────────────────────────────────────────────


def test_an_unconfigured_selection_routes_to_the_setup():
    """F1-AC1: `include_configured: false` is what sends the run to the glob setup."""
    text = _section("1. Start")
    assert "- `include_configured` is false → step 2." in text
    assert text.index("`mode` is `process` → step 9.") < text.index("`include_configured` is false → step 2.")


def test_a_confirmed_setup_continues_the_request():
    """F1-AC3: after templates-include the same request goes on to the template choice."""
    text = _section("2. First-run setup")
    writer = text.index("vault-config-writer.py templates-include")
    resume = text.index("Otherwise rerun the step 1 `start` call (skip kept drafts already handled) "
                        "and go to step 3.")
    assert writer < resume


def test_a_skipped_optional_point_keeps_its_heading_empty_and_is_named():
    """F3-AC4: the skipped point stays as an empty heading and goes into the skipped line."""
    assert ("6. Optional points still open stay empty under their heading and go into the skipped "
            "line of step 6.") in _section("5. Ask for open points")
    draft = _section("6. Draft")
    assert "keep every heading" in draft
    assert "Skipped, left empty: <points>" in draft


def test_approval_runs_deliver():
    """F4-AC4: the Deliver answer leads to the step that runs `deliver`."""
    assert "- Deliver → step 7." in _section("6. Draft")
    assert "python3 scripts/note-instructions.py deliver --stem <stem>" in _section("7. Deliver")


def test_process_required_points_are_the_required_points_of_the_questions():
    """F7-AC2: the process file's `required` list feeds the F3 required rules."""
    text = _section("5. Ask for open points")
    assert "Required points are the process `required` list minus `missing_required`." in text
    assert "For each required point still unanswered, ask it again in plain text with no skip option." in text


def test_not_now_writes_nothing():
    """F7-AC8: "not now" writes no process file and no marker."""
    text = _section("8. Process offer")
    assert "- Not now: write nothing." in text
    not_now = text[text.index("- Not now:"):text.index("- Never for this template:")]
    assert "note-process.py" not in not_now


# ── Script behaviour ───────────────────────────────────────────────────────


OUTLINE = {
    "template": "Templates/Meeting Notes.md",
    "frontmatter": [],
    "headings": [{"level": 2, "text": "Agenda", "line": 5, "has_body": False}],
    "tokens": [],
    "templater": [],
    "frontmatter_ok": True,
}


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "vault-config.yaml").write_text(
        'profile: "miyo"\nconcepts:\n  inbox: "100 Inbox/"\n  atomic_note: "Atlas/202 Notes/"\n',
        encoding="utf-8")
    outline = tmp_path / "tomo-tmp" / "note" / "process-outline.json"
    outline.parent.mkdir(parents=True)
    outline.write_text(json.dumps(OUTLINE), encoding="utf-8")
    return tmp_path


def test_default_destination_saves_no_destination_and_new_uses_the_atomic_folder(instance, capsys):
    """F7-AC10 Default, F7-AC1: a write without --destination replaces the current one with none."""
    process = _load("co044_note_process", "note-process.py")
    ni = _load("co044_note_instructions", "note-instructions.py")
    outline = "tomo-tmp/note/process-outline.json"
    assert process.main(["write", "--template", "Meeting Notes", "--outline", outline,
                         "--destination", "Atlas/Meetings"]) == 0
    assert process.main(["write", "--template", "Meeting Notes", "--outline", outline,
                         "--required", "Agenda"]) == 0
    capsys.readouterr()
    saved = (instance / note_process.PROCESS_DIR / "Meeting Notes.md").read_text(encoding="utf-8")
    assert "destination" not in saved
    assert note_process.read_process(note_process.PROCESS_DIR, "Meeting Notes")["destination"] == ""
    assert ni.main(["new", "--template", "Templates/Meeting Notes.md"]) == 0
    assert json.loads(capsys.readouterr()[0])["default_destination"] == "Atlas/202 Notes/"
