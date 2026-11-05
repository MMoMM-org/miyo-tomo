"""test_044_user_docs.py — spec 044 F9: users can find and follow the /note documentation.

Pins the /note section of docs/usage.md (modes, first run, process files, the discard
path of two deletions and `/inbox --recover`), the troubleshooting remedy, the
instructions-json.md sentence, and that none of it leaks executor internals.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
USAGE = DOCS / "usage.md"
TROUBLE = DOCS / "troubleshooting.md"
INSTR = DOCS / "instructions-json.md"

INTERNAL_TERMS = [
    r"\.py\b", "tomo-tmp", "exit code", "note-session", "note-instructions",
    "note-process", "template-outline", r"draft\.md", r"outline\.json",
]
INTERNALS = re.compile("|".join(INTERNAL_TERMS))


def _section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, re.M)
    assert m, f"{path.name}: missing heading {heading!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _note_usage() -> str:
    return _section(USAGE, "Write a note from a template")


def _trouble_section() -> str:
    m = re.search(r"^#+ (.*/note.*)$", TROUBLE.read_text(encoding="utf-8"), re.M)
    assert m, "troubleshooting needs a /note heading"
    return _section(TROUBLE, m.group(1))


def test_usage_has_note_section() -> None:
    assert re.search(r"^## Write a note from a template\s*$", USAGE.read_text(encoding="utf-8"), re.M)
    assert "`/note` turns your material into a note" in _note_usage()


def test_usage_covers_both_modes_and_first_run_and_process() -> None:
    s = _note_usage()
    assert "`/note --process <template>`" in s
    assert "The first time you use `/note`" in s and "filename patterns" in s
    assert "A process file remembers" in s


def test_usage_names_both_deletions_and_recover() -> None:
    discard = _section(USAGE, "Discard a delivered note")
    assert "Run `/inbox --recover`" in discard
    assert "Delete the note in Obsidian" in discard
    assert "Delete the instruction set in Obsidian" in discard


def test_usage_states_title_and_destination_rules() -> None:
    s = _note_usage()
    assert "may not start with a dot" in s
    assert "invisible characters" in s
    assert "zero-width joiner" in s
    assert "relative vault folder" in s and "not an absolute path" in s


def test_usage_lists_note_command_in_table() -> None:
    assert re.search(r"^\| `/note` \|[^\n]*\(#write-a-note-from-a-template\)", USAGE.read_text(encoding="utf-8"), re.M)


def test_troubleshooting_remedy_for_template_folder_access() -> None:
    low = _trouble_section().lower()
    assert "read access" in low and "template folder" in low
    assert "kado" in low and "do not use `/note`" in low


def test_instructions_json_mentions_note() -> None:
    s = INSTR.read_text(encoding="utf-8")
    assert re.search(r"`/note`[^\n]*same shape", s)


def test_no_executor_internals_in_note_text() -> None:
    chunks = {"usage.md /note section": _note_usage(), "troubleshooting.md /note section": _trouble_section()}
    for i, line in enumerate(INSTR.read_text(encoding="utf-8").splitlines(), 1):
        if "`/note`" in line:
            chunks[f"instructions-json.md line {i}"] = line
    for name, c in chunks.items():
        hit = INTERNALS.search(c)
        assert not hit, f"{name} leaks executor internal {hit.group(0)!r}"


def test_relative_links_resolve() -> None:
    for path in (USAGE, TROUBLE, INSTR):
        for target in re.findall(r"\]\((?!https?:|#|mailto:)([^)#\s]+)", path.read_text(encoding="utf-8")):
            assert (path.parent / target).exists(), f"{path.name}: broken link {target}"
