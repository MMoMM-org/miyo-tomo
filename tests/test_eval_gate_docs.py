"""The gate's documentation (spec 041, T4.3): a coding session must be able to
tell from the repo alone whether its change needs the eval suite.

Assertions are on substance (paths, case names, links), not on exact prose.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
README = EVALS / "README.md"

COVERED = (
    "tomo/dot_claude/agents/synthesis-conductor.md",
    "tomo/dot_claude/commands/inbox.md",
    "tomo/dot_claude/settings.json",
)


def _coverage_rows() -> list[tuple[str, str]]:
    """(first cell, second cell) of the table whose first header is 'Runtime file'."""
    assert README.is_file(), "evals/README.md is missing"
    rows: list[tuple[str, str]] = []
    in_table = False
    for line in README.read_text().splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0].lower().startswith("runtime file"):
                in_table = True
                continue
            if in_table and not set(cells[0]) <= set("-: "):
                rows.append((cells[0], cells[1] if len(cells) > 1 else ""))
        elif in_table:
            break
    assert rows, "no coverage table found in evals/README.md"
    return rows


def _section(path: Path, heading: str) -> str:
    text = path.read_text()
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"{path.name}: no '## {heading}' section"
    return m.group(1)


def test_every_covered_path_exists():
    for first, _ in _coverage_rows():
        for p in re.findall(r"`([^`]+)`", first):
            assert (REPO / p).exists(), f"coverage table names a missing path: {p}"


def test_the_three_runtime_files_are_listed_with_cases():
    rows = {re.sub(r"[`\s]", "", first): second for first, second in _coverage_rows()}
    for f in COVERED:
        assert f in rows, f"{f} not in the coverage table"
        assert re.search(r"[a-z]+-[a-z-]+", rows[f]), f"{f} lists no covering case"


def test_every_case_directory_appears_in_the_table():
    table = "\n".join(f"{a} {b}" for a, b in _coverage_rows())
    cases = [
        d.name for d in sorted(EVALS.iterdir())
        if d.is_dir() and not d.name.startswith("_") and (d / "case.yaml").is_file()
    ]
    assert cases, "no cases found"
    for name in cases:
        assert name in table, f"case {name} missing from the coverage table"


def test_every_case_named_in_the_table_exists():
    for _, second in _coverage_rows():
        for name in re.findall(r"`([a-z][a-z0-9-]+)`", second):
            assert (EVALS / name / "case.yaml").is_file(), f"unknown case {name}"


def test_readme_covers_run_exit_codes_and_adding_a_case():
    text = README.read_text()
    for needle in ("scripts/run-evals.sh", "GREEN", "RED", "NOT GRADED", "REFUSED",
                   "AUDIT_RESULT", "WITHHELD_DELETES", "WITHHELD_ATTACH",
                   "evals/_lib/no-leak.md", "evals/_mutations/README.md"):
        assert needle in text, f"evals/README.md lacks {needle}"


def test_root_claude_md_rule_names_readme_and_green():
    rules = _section(REPO / "CLAUDE.md", "Rules")
    bullets = [b for b in rules.split("\n- ") if "evals/README.md" in b]
    assert bullets, "no Rules bullet names evals/README.md"
    assert "GREEN" in bullets[0]


def test_tools_memory_mentions_the_runner():
    assert "scripts/run-evals.sh" in (REPO / "docs/ai/memory/tools.md").read_text()


def test_root_readme_links_the_eval_readme():
    assert re.search(r"\]\(evals/README\.md\)", (REPO / "README.md").read_text())


def test_memory_index_lists_the_eval_readme_as_critical_documentation():
    crit = _section(REPO / "docs/ai/memory/memory.md", "Critical Documentation")
    assert "evals/README.md" in crit
