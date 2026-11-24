#!/usr/bin/env python3
# version: 0.5.0
"""test_review_sdd_map.py — spec 045 Phase 5: the SDDs' Directory Maps list every /review file that exists.

The Directory Map of docs/XDD/specs/045-weekly-monthly-review/solution.md is
the as-built inventory of the spec. This test is glob-driven: it lists the
review files that exist in the worktree at run time (tests, fixtures, scripts,
libs, the command, the skill and their WHY documents) and asserts each one is
named in the map block of its component — so a file added by a later phase or
by a test split fails the test until the map names it, and a file the map
names but the tree lacks is not reported (Phase 6 files are listed ahead).
Spec 046 (T1.2) adds files to the same components, so a file passes when the
map block of its component in spec 045's OR spec 046's Directory Map names it
(spec 046 lists only its new and changed files, per component block).
Spec 047 (T1.1) adds a third map with its own block roots — ``tomo/`` (Tomo runtime
and scripts), ``docs/`` (Documentation) and ``tests/`` (Tests); its ``docs/`` block
stands for the ``docs/tomo/`` component, so a file named in any of the three maps passes.

Also pinned, as drift found at the Phase 5 checkpoint (round D):
- the map lines of the three runtime documents of Phase 5 carry an implemented marker (D3);
- the SDD names how the commented `review:` example of vault-example.yaml is checked (D4);
- the Error Handling row for an empty listing names that the skill asks before
  proposing to create notes in that folder (R6; SKILL.md step 2);
- the `place-too-deep` row says insert/new-note names the anchor and the
  placement — the refused preview carries no level (lib/review_actions sets
  `place.level` only after `_insertion` succeeds).

Pinned at the T6.1 fix round (owner decisions 2026-11-12): the SDD's Performance
requirement says week ≤ 45 / month ≤ 170 Kado calls and a 7-minute monthly KPI,
its derivation pointer names docs/tomo/scripts/lib/review_pacer.md and that
document derives the numbers; the PRD's Cost-and-time KPI says 7 minutes.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SDD = ROOT / "docs" / "XDD" / "specs" / "045-weekly-monthly-review" / "solution.md"
SDD_046 = ROOT / "docs" / "XDD" / "specs" / "046-review-template-sections" / "solution.md"
SDD_047 = ROOT / "docs" / "XDD" / "specs" / "047-review-chunked-read" / "solution.md"
# spec -> {component block of GLOBS: the first line of that component's block in the spec's map}
MAPS: dict[Path, dict[str, str]] = {
    SDD: {},
    SDD_046: {},
    SDD_047: {"docs/tomo/": "docs/"},
}

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


def _map_blocks(sdd: Path = SDD) -> dict[str, str]:
    """The fenced tree blocks of the Directory Map keyed by the GLOBS component they stand for
    (their first line, the component root, read through the spec's entry in ``MAPS``)."""
    blocks = re.findall(r"^```\n(.*?)\n```", _section(sdd.read_text(encoding="utf-8"), "Directory Map"), re.M | re.S)
    keyed = {b.split("\n", 1)[0].strip(): b for b in blocks}
    roots = {component: MAPS.get(sdd, {}).get(component, component) for component in GLOBS}
    assert set(roots.values()) <= set(keyed), f"Directory Map blocks found in {sdd.name}: {sorted(keyed)}"
    return {component: keyed[root] for component, root in roots.items()}


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


def _mapped(block: str, path: Path) -> bool:
    """Whether the block of ``block``'s component in spec 045's, 046's or 047's Directory Map names ``path``."""
    return any(_named_in(_map_blocks(sdd)[block], *_names(path)) for sdd in MAPS)


_EXISTING = _existing()


def test_the_glob_lists_the_review_files_that_exist() -> None:
    assert len(_EXISTING) >= 40, [str(p) for _, p in _EXISTING]
    assert any(p.name == "test_review_sdd_map.py" for _, p in _EXISTING)


@pytest.mark.parametrize("block,path", _EXISTING, ids=[str(p) for _, p in _EXISTING])
def test_directory_map_names_every_existing_review_file(block: str, path: Path) -> None:
    assert _mapped(block, path), (
        f"{path} is not in the Directory Map of {', '.join(str(s.relative_to(ROOT)) for s in MAPS)}: add a line naming "
        f"{' and '.join(f'`{n}`' for n in _names(path))} (with a one-line role and `# NEW (implemented, spec 045 ...)`) "
        f"to the fenced tree block that starts with `{block}`, under the folder it lives in"
    )


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


# --- T6.1 fix round: the Performance requirement carries the owner's limits, and its pointer holds -----

PRD = SDD.with_name("requirements.md")
PACER_WHY = ROOT / "docs" / "tomo" / "scripts" / "lib" / "review_pacer.md"


def _performance_requirement() -> str:
    rows = [ln for ln in _section(_sdd(), "Quality Requirements").splitlines() if ln.startswith("- **Performance:**")]
    assert len(rows) == 1, rows
    return rows[0]


def test_sdd_performance_requirement_says_45_170_calls_and_the_seven_minute_kpi() -> None:
    """Owner decisions 2026-11-12: week ≤ 45 and month ≤ 170 Kado calls (each daily links one same-day DP- and
    one 5J- note, byName + read each); the monthly Pass 1 KPI is 7 min, not 5 (a 170-call month at the pacer's
    2 s cap paces ≈ 340 s before model time)."""
    line = _performance_requirement()
    assert "a week ≤ 45 Kado calls, a month ≤ 170" in line, line
    assert "monthly Pass 1 ≤ 7 min" in line, line
    assert "≤ 5 min" not in line and "5-minute" not in line, line


def test_sdd_performance_requirement_points_at_the_derivation_in_the_pacer_why() -> None:
    """The requirement's pointer must name a document that holds the call-count derivation; `review_pacer.md`
    derives 45/170 from START_INTERVAL_S, the doubling, the 2 s cap and finish()."""
    line = _performance_requirement()
    assert "docs/tomo/scripts/lib/review_pacer.md" in line, line
    why = PACER_WHY.read_text(encoding="utf-8")
    for phrase in ("1 + 2 × 2 = 5", "≤ 170", "≤ 45", "340 s", "7 min"):
        assert phrase in why, f"review_pacer.md lacks {phrase!r}"
    assert "(≈ 110 calls) still fits" not in why and "five-minute" not in why, \
        "stale 110-call / five-minute claim in review_pacer.md"


def test_prd_cost_and_time_kpi_says_seven_minutes() -> None:
    text = PRD.read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if ln.startswith("- **Cost and time:**")]
    assert len(rows) == 1, rows
    assert "a monthly Pass 1 finishes within 7 minutes" in rows[0], rows[0]
    assert "5 minutes" not in rows[0], rows[0]
    assert "5-minute KPI" not in text, "the PRD's risk table still names the five-minute KPI"


# --- spec 047 T1.1: spec 047's Directory Map is read too ---------------------------------------

FINGERPRINT = Path("tests/review_doc_fingerprint.py")


def test_spec_047_map_accepts_a_review_file_only_it_names() -> None:
    assert not any(_named_in(m["tests/"], FINGERPRINT.name) for m in (_map_blocks(SDD), _map_blocks(SDD_046)))
    assert _mapped("tests/", FINGERPRINT)


def test_an_unmapped_review_file_is_still_refused() -> None:
    assert not _mapped("tests/", Path("tests/review_unmapped_047_probe.py"))
    assert not _mapped("tomo/", Path("tomo/scripts/lib/review_unmapped_047_probe.py"))


def test_spec_045_and_046_maps_are_still_read() -> None:
    only_045, only_046 = Path("tests/test_review_sdd_map.py"), Path("tests/test_review_mapping.py")
    assert _named_in(_map_blocks(SDD)["tests/"], only_045.name)
    assert not _named_in(_map_blocks(SDD_046)["tests/"], only_045.name)
    assert _named_in(_map_blocks(SDD_046)["tests/"], only_046.name)
    assert not _named_in(_map_blocks(SDD)["tests/"], only_046.name)
    assert _mapped("tests/", only_045) and _mapped("tests/", only_046)


# --- spec 047 T7.4: what the 047 map marks DELETE is gone from the tree --------------------------------------

def _deleted_names() -> list[str]:
    """The basenames of the map lines of spec 047 that carry `# DELETE`, read from the untruncated map text."""
    names = []
    for block in _map_blocks(SDD_047).values():
        for line in block.splitlines():
            if "DELETE" in line:
                names += re.findall(r"[\w.-]+\.(?:py|md)", line.split("#", 1)[0])
    return names


def test_the_047_map_marks_review_read_parts_for_deletion() -> None:
    assert {"review_read_parts.py", "review_read_parts.md"} <= set(_deleted_names())


def test_no_file_the_047_map_marks_delete_exists() -> None:
    survivors = [str(p.relative_to(ROOT)) for name in _deleted_names()
                 for base in ("tomo", "docs/tomo", "tests") for p in (ROOT / base).rglob(name)]
    assert not survivors, survivors
    assert not (ROOT / "tests" / "test_review_read_parts.py").exists()


def test_every_review_file_that_exists_is_named_by_a_map_not_only_by_a_deleted_line() -> None:
    mapped_only_deleted = [str(p) for _b, p in _EXISTING if p.name in _deleted_names()]
    assert not mapped_only_deleted, mapped_only_deleted
