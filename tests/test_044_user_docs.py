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

INTERNALS = re.compile(r"\.py\b|tomo-tmp|exit code|note-session|note-instructions|note-process|template-outline|draft\.md|outline\.json")


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


def test_usage_has_note_section() -> None:
    assert "/note" in _note_usage()


def test_usage_covers_both_modes_and_first_run_and_process() -> None:
    s = _note_usage()
    assert "/note --process" in s
    assert "first" in s.lower() and "filename pattern" in s.lower()
    assert "process file" in s.lower()


def test_usage_names_both_deletions_and_recover() -> None:
    s = _note_usage()
    discard = _section(USAGE, "Discard a delivered note") if re.search(
        r"^#+ Discard a delivered note", USAGE.read_text(encoding="utf-8"), re.M) else s
    assert "/inbox --recover" in discard
    low = discard.lower()
    assert "delete the note" in low
    assert "delete the instruction set" in low


def test_usage_states_title_and_destination_rules() -> None:
    s = _note_usage().lower()
    assert "dot" in s and "invisible" in s
    assert "joiner" in s
    assert "relative" in s and "folder" in s


def test_usage_lists_note_command_in_table() -> None:
    assert re.search(r"^\| `/note` \|", USAGE.read_text(encoding="utf-8"), re.M)


def test_troubleshooting_remedy_for_template_folder_access() -> None:
    s = TROUBLE.read_text(encoding="utf-8")
    m = re.search(r"^#+ .*/note.*$", s, re.M)
    assert m, "troubleshooting needs a /note heading"
    body = _section(TROUBLE, m.group(0).lstrip("# ").strip())
    low = body.lower()
    assert "read access" in low and "template folder" in low
    assert "kado" in low and "do not use `/note`" in low


def test_instructions_json_mentions_note() -> None:
    s = INSTR.read_text(encoding="utf-8")
    assert re.search(r"`/note`[^\n]*(same shape|same format)", s, re.S)


def test_no_executor_internals_in_note_text() -> None:
    chunks = [_note_usage(), _section(TROUBLE, re.search(r"^#+ (.*/note.*)$", TROUBLE.read_text(encoding="utf-8"), re.M).group(1))]
    for line in INSTR.read_text(encoding="utf-8").splitlines():
        if "`/note`" in line:
            chunks.append(line)
    for c in chunks:
        assert not INTERNALS.search(c), INTERNALS.search(c).group(0)


def test_relative_links_resolve() -> None:
    for path in (USAGE, TROUBLE, INSTR):
        for target in re.findall(r"\]\((?!https?:|#|mailto:)([^)#\s]+)", path.read_text(encoding="utf-8")):
            assert (path.parent / target).exists(), f"{path.name}: broken link {target}"
