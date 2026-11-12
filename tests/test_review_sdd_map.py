#!/usr/bin/env python3
# version: 0.2.0
"""test_review_sdd_map.py — spec 045 Phase 5: the SDD's Directory Map lists every /review file that exists.

The Directory Map of docs/XDD/specs/045-weekly-monthly-review/solution.md is
the as-built inventory of the spec. This test is glob-driven: it lists the
review files that exist in the worktree at run time (tests, fixtures, scripts,
libs, the command, the skill and their WHY documents) and asserts each one is
named in the map block of its component — so a file added by a later phase or
by a test split fails the test until the map names it, and a file the map
names but the tree lacks is not reported (Phase 6 files are listed ahead).

Also pinned, as drift found at the Phase 5 checkpoint (round D):
- the map lines of the three runtime documents of Phase 5 carry an implemented marker (D3);
- the SDD names how the commented `review:` example of vault-example.yaml is checked (D4);
- the Error Handling row for an empty listing names that the skill asks before
  proposing to create notes in that folder (R6; SKILL.md step 2);
- the `place-too-deep` row says insert/new-note names the anchor and the
  placement — the refused preview carries no level (lib/review_actions sets
  `place.level` only after `_insertion` succeeds).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SDD = ROOT / "docs" / "XDD" / "specs" / "045-weekly-monthly-review" / "solution.md"

GLOBS: dict[str, list[str]] = {
    # component block (first line of the fenced tree) -> globs relative to ROOT
    "tomo/": [
        "tomo/scripts/review-*.py",
        "tomo/scripts/lib/review_*.py",
        "tomo/dot_claude/commands/review.md",
        "tomo/dot_claude/skills/periodic-review/SKILL.md",
    ],
    "docs/tomo/": [
        "docs/tomo/**/review*.md",
        "docs/tomo/**/periodic-review.md",
    ],
    "tests/": [
        "tests/test_review_*.py",
        "tests/review_*.py",
    ],
}


def _sdd() -> str:
    return SDD.read_text(encoding="utf-8")


def _section(text: str, heading_pattern: str) -> str:
    """The body of the first heading matching ``heading_pattern`` up to the next heading of the same or a higher level."""
    m = re.search(rf"^(#+) ({heading_pattern})\s*$", text, re.M)
    assert m, f"missing heading matching {heading_pattern!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _map_blocks() -> dict[str, str]:
    """The fenced tree blocks of the Directory Map, keyed by their first line (the component root)."""
    blocks = re.findall(r"^```\n(.*?)\n```", _section(_sdd(), "Directory Map"), re.M | re.S)
    keyed = {b.split("\n", 1)[0].strip(): b for b in blocks}
    assert set(GLOBS) <= set(keyed), f"Directory Map blocks found: {sorted(keyed)}"
    return keyed


def _existing() -> list[tuple[str, Path]]:
    found = []
    for block, patterns in GLOBS.items():
        for pattern in patterns:
            found.extend((block, p.relative_to(ROOT)) for p in ROOT.glob(pattern) if p.is_file())
    return sorted(set(found))


def _names(path: Path) -> tuple[str, ...]:
    """The tokens the map shows for the file: its basename; `SKILL.md` also its skill folder (a tree line above)."""
    return (f"{path.parent.name}/", path.name) if path.name == "SKILL.md" else (path.name,)


def _named_in(block_text: str, *names: str) -> bool:
    # a name is its own token: `review.md` does not match `periodic-review.md`, `review_doc.md` not `review_doc_parse.md`
    return all(re.search(rf"(?<![\w.-]){re.escape(n)}(?![\w.-])", block_text) for n in names)


_EXISTING = _existing()


def test_the_glob_lists_the_review_files_that_exist() -> None:
    assert len(_EXISTING) >= 40, [str(p) for _, p in _EXISTING]
    assert any(p.name == "test_review_sdd_map.py" for _, p in _EXISTING)


@pytest.mark.parametrize("block,path", _EXISTING, ids=[str(p) for _, p in _EXISTING])
def test_directory_map_names_every_existing_review_file(block: str, path: Path) -> None:
    assert _named_in(_map_blocks()[block], *_names(path)), \
        f"SDD Directory Map block `{block}` does not name {path}"


# --- D3: implemented markers on the Phase 5 runtime documents -----------------------------

@pytest.mark.parametrize("block,name", [
    ("tomo/", "review.md"),
    ("tomo/", "SKILL.md"),
    ("docs/tomo/", "tomo-help.md"),
])
def test_phase_5_runtime_documents_carry_an_implemented_marker(block: str, name: str) -> None:
    lines = [ln for ln in _map_blocks()[block].splitlines() if _named_in(ln, name)]
    assert lines, f"no map line names {name} in block `{block}`"
    assert all("implemented, spec 045 Phase 5" in ln for ln in lines), lines


# --- D4: the SDD names how the commented review: example is checked -----------------------

def test_sdd_names_how_the_commented_review_example_is_checked() -> None:
    text = _sdd()
    m = re.search(r"^.*vault-example\.yaml.*review_setup.*$", text, re.M)
    assert m, "the SDD needs a line that names the check of the commented review: example"
    line = m.group(0)
    for phrase in ("lib.review_config", "review_setup", "current_setup",
                   "vault-config-review.schema.json", "input_problems", "tests/test_review_privacy_docs.py"):
        assert phrase in line, f"missing {phrase!r} in: {line}"


# --- place-too-deep: insert/new-note names the anchor and the placement, not a level ------

def test_error_handling_place_too_deep_row_names_anchor_and_placement() -> None:
    """lib/review_actions sets `place.level` only after `_insertion` succeeds, so a refused insert/new-note
    preview carries anchor and placement (what SKILL.md names); only replace mode knows the level 6."""
    rows = [ln for ln in _section(_sdd(), "Error Handling").splitlines() if "`place-too-deep` + `headings`" in ln]
    assert len(rows) == 1, rows
    assert "names the anchor and the placement" in rows[0], rows[0]
    assert "names the anchor and its level" not in rows[0], rows[0]


# --- R6: the empty-listing row names the ask before creating notes there ------------------

def test_error_handling_empty_listing_row_names_the_ask_before_creating_notes() -> None:
    rows = [ln for ln in _section(_sdd(), "Error Handling").splitlines() if "kado-none" in ln]
    assert len(rows) == 1, rows
    assert "asks before proposing to create notes" in rows[0], rows[0]
