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

# F7-AC1 names these three; the table may list more, never fewer.
PRD_NAMED = (
    "tomo/dot_claude/agents/synthesis-conductor.md",
    "tomo/dot_claude/commands/inbox.md",
    "tomo/dot_claude/settings.json",
)


def _coverage_rows(readme: Path = README) -> list[tuple[str, str]]:
    """(first cell, second cell) of the table whose first header is 'Runtime file'."""
    assert readme.is_file(), "evals/README.md is missing"
    rows: list[tuple[str, str]] = []
    in_table = False
    for line in readme.read_text().splitlines():
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


def _table_paths(rows: list[tuple[str, str]]) -> set[str]:
    return {re.sub(r"[`\s]", "", first) for first, _ in rows}


def _case_dirs() -> list[str]:
    return [
        d.name for d in sorted(EVALS.iterdir())
        if d.is_dir() and not d.name.startswith("_") and (d / "case.yaml").is_file()
    ]


PATH_PREFIXES = ("evals/", "scripts/", "tests/", "tomo/")


def _readme_paths(text: str) -> tuple[list[str], list[str]]:
    """(checkable, skipped) repo paths from the inline-backticked tokens of a README."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    checked: list[str] = []
    skipped: list[str] = []
    for token in re.findall(r"`([^`\n]+)`", text):
        if not token.startswith(PATH_PREFIXES):
            continue
        token = token.rstrip(".,:;)")
        if re.search(r"[<*\s…]", token):
            skipped.append(token)
        else:
            checked.append(token)
    return checked, skipped


def _missing_paths(text: str) -> list[str]:
    return [p for p in _readme_paths(text)[0] if not (REPO / p).exists()]


def _claude_eval_bullet(claude_md: Path = REPO / "CLAUDE.md") -> str:
    rules = _section(claude_md, "Rules")
    bullets = [b for b in rules.split("\n- ") if "evals/README.md" in b]
    assert bullets, "no Rules bullet names evals/README.md"
    return bullets[0]


def _rule_sync_problems(rows: list[tuple[str, str]], bullet: str) -> list[str]:
    table = _table_paths(rows)
    named = set(re.findall(r"`(tomo/[^`\s]+)`", bullet))
    problems = [f"table path missing from the CLAUDE.md rule: {p}" for p in sorted(table - named)]
    problems += [f"CLAUDE.md rule names a path not in the table: {p}" for p in sorted(named - table)]
    return problems


def _section(path: Path, heading: str) -> str:
    text = path.read_text()
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"{path.name}: no '## {heading}' section"
    return m.group(1)


def test_every_covered_path_exists():
    for first, _ in _coverage_rows():
        for p in re.findall(r"`([^`]+)`", first):
            assert (REPO / p).exists(), f"coverage table names a missing path: {p}"


def test_prd_named_files_are_in_the_table():
    table = _table_paths(_coverage_rows())
    for f in PRD_NAMED:
        assert f in table, f"{f} not in the coverage table"


def test_every_table_row_names_an_existing_case():
    existing = set(_case_dirs())
    for first, second in _coverage_rows():
        named = set(re.findall(r"`([a-z][a-z0-9-]+)`", second))
        assert named & existing, f"{first} lists no existing case directory"


def test_every_case_directory_appears_in_the_table():
    table = "\n".join(f"{a} {b}" for a, b in _coverage_rows())
    cases = _case_dirs()
    assert cases, "no cases found"
    for name in cases:
        assert name in table, f"case {name} missing from the coverage table"


def test_every_case_named_in_the_table_exists():
    for _, second in _coverage_rows():
        for name in re.findall(r"`([a-z][a-z0-9-]+)`", second):
            assert (EVALS / name / "case.yaml").is_file(), f"unknown case {name}"


def test_readme_covers_run_exit_codes_and_adding_a_case():
    text = README.read_text()
    for code, verdict in ((0, "GREEN"), (1, "RED"), (2, "NOT GRADED"), (3, "REFUSED")):
        assert re.search(rf"^\|\s*{code}\s*\|\s*{verdict}\s*\|", text, re.M), (
            f"exit-code table lacks the row for {code} {verdict}"
        )
    for needle in ("scripts/run-evals.sh", "AUDIT_RESULT", "WITHHELD_DELETES", "WITHHELD_ATTACH",
                   "evals/_lib/no-leak.md", "evals/_mutations/README.md"):
        assert needle in text, f"evals/README.md lacks {needle}"


def test_root_claude_md_rule_names_readme_and_green():
    assert "GREEN" in _claude_eval_bullet()


def test_claude_md_rule_states_the_pr_record_and_the_exemption():
    """F7-AC2: the whole suite, before merge, with verdict, cost and results path in
    the PR; a single-case run does not count. F7-AC3: other files need no run."""
    bullet = _claude_eval_bullet()
    for needle in ("full-suite GREEN", "before merge", "verdict line", "cost", "results path",
                   "`--case` run does not count", "Other files need no run"):
        assert needle in bullet, f"CLAUDE.md eval rule lacks: {needle}"


def test_claude_md_rule_tracks_the_coverage_table():
    problems = _rule_sync_problems(_coverage_rows(), _claude_eval_bullet())
    assert not problems, problems


def test_every_repo_path_in_the_readme_exists():
    checked, skipped = _readme_paths(README.read_text())
    assert checked, "no repo paths found in evals/README.md"
    assert not _missing_paths(README.read_text()), _missing_paths(README.read_text())
    # skipped tokens are placeholders/globs that cannot be checked; keep them few
    assert len(skipped) <= 3, skipped


def test_tools_memory_mentions_the_runner():
    assert "scripts/run-evals.sh" in (REPO / "docs/ai/memory/tools.md").read_text()


def test_root_readme_links_the_eval_readme():
    assert re.search(r"\]\(evals/README\.md\)", (REPO / "README.md").read_text())


def test_memory_index_lists_the_eval_readme_as_critical_documentation():
    crit = _section(REPO / "docs/ai/memory/memory.md", "Critical Documentation")
    assert "evals/README.md" in crit
