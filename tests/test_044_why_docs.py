"""Spec 044 T3.1: the WHY mirrors for /note exist and name each decision the
runtime text will bake in, so no rationale has to live in the runtime files.

Assertions are on specific decision statements (a heading plus a distinguishing
phrase), not on a word that appears anywhere in the file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "tomo" / "dot_claude"
CMD = DOCS / "commands" / "note.md"
SKILL = DOCS / "skills" / "note-from-template.md"
AUTHOR = DOCS / "skills" / "inbox-author.md"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _text(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO)} is missing"
    return path.read_text()


def _section(text: str, heading_part: str) -> str:
    """Heading and body of the '## ' section whose heading contains heading_part."""
    parts = re.split(r"^## ", text, flags=re.M)
    for part in parts[1:]:
        head, _, body = part.partition("\n")
        if heading_part.lower() in head.lower():
            return head + "\n" + body
    raise AssertionError(f"no '## ' heading containing {heading_part!r}")


def test_mirrors_start_with_why_title():
    assert _text(CMD).startswith("# WHY: note (command)")
    assert _text(SKILL).startswith("# WHY: note-from-template (skill)")


def test_command_is_thin_shim_and_main_session():
    body = _section(_text(CMD), "Thin Shim")
    assert "note-from-template" in body
    assert "$ARGUMENTS" in body
    main = _section(_text(CMD), "Main Session")
    assert "AskUserQuestion" in main
    assert "subagent" in main.lower()
    assert "cannot" in main.lower()


@pytest.mark.parametrize(
    "heading, needles",
    [
        ("Main Session", ["AskUserQuestion", "subagent", "Agent tool"]),
        ("Printed Before", ["print", "before", "AskUserQuestion", "note.md", "draft.md"]),
        ("Abort", ["note-instructions.py drop", "note_include", "stays saved"]),
        ("Exit 2", ["exit 2", "another value", "nothing is staged"]),
        ("Resume", ["steps_done", "never a silent drop", "frozen"]),
        ("Model Fills", ["ADR-1", "scripts check"]),
        ("Delivery Is One Script", ["ADR-2", "deliver", "exit 3", "withdrawn", "nothing is written"]),
        ("Exit 3 Branches", ["steps_done", "is_frozen", "meta.json", "kept_drafts"]),
        ("Source That Moves", ["source_marked", "not marked", "source_mark", "resume", "retries"]),
        ("No Candidate Fitting", ["folder_listed", "adjust patterns", "inbox-author", "abort", "F2-AC3"]),
        ("Runtime Details", ["Templater", "F3-AC7", "F3-AC8", "headings", "previews"]),
        ("Session Start", ["ADR-6", "note-session.py", "argparse"]),
        ("Shared Parser", ["ADR-4", "template_syntax", "outline"]),
        ("Draft State", ["ADR-7", "tomo-tmp/note/", "reset-tomo-tmp.sh"]),
        ("note_include", ["ADR-5", "templates-include", "comments"]),
        ("Question Budget", ["four", "required", "Skipped, left empty"]),
        ("Template Unreadable", ["folder_listed", "never says that no template exists"]),
        ("STRICT", ["observed", "Why:"]),
        ("Eval", ["ADR-8", "not in the CLAUDE.md eval gate"]),
        ("Process", ["--process", "decline", "note-process.py"]),
    ],
)
def test_skill_mirror_names_decision(heading, needles):
    body = _section(_text(SKILL), heading)
    for needle in needles:
        assert needle.lower() in body.lower(), f"{heading!r} section lacks {needle!r}"


def test_inbox_author_has_note_redirect_entry():
    body = _section(_text(AUTHOR), "/note")
    assert "/note" in body
    assert "If found" in body
    assert "unknown" in body.lower()
    assert "built-in default" in body
    assert "note-from-template" in body


@pytest.mark.parametrize("path", [CMD, SKILL, AUTHOR])
def test_relative_links_resolve(path):
    broken = []
    for target in LINK.findall(_text(path)):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        rel = target.split("#", 1)[0]
        if rel and not (path.parent / rel).exists():
            broken.append(target)
    assert not broken, f"{path.name}: unresolved links {broken}"
