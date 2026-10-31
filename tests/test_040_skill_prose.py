#!/usr/bin/env python3
# version: 0.2.0
"""test_040_skill_prose.py — spec 040 T4.3: both inbox skills' setup and report.

Both Pass-1 paths (`suggest-handling`, `force-atomic-handling`) delete the
context file before building it, so a failed build cannot leave a previous
run's MOCs for the analysts (SDD ADR-8), and both reports relay the reducer's
`duplicate_proposals_converted` count (ADR-6). `lyt-patterns`, which the
analyst loads, is overridden by the analyst's own Step 4 for MOC matching.

RED on `main`: neither skill deletes the file nor mentions the count.
Guards (already true on `main`): identical builder commands, the WARN relay,
and `reset-tomo-tmp.sh --pass1` clearing the context and the names files.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "tomo" / "dot_claude" / "skills"
PATHS = {
    "suggest": SKILLS / "suggest-handling" / "SKILL.md",
    "force": SKILLS / "force-atomic-handling" / "SKILL.md",
}


def _text(which: str) -> str:
    return PATHS[which].read_text(encoding="utf-8")


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, re.DOTALL)


def _builder(text: str) -> str:
    (block,) = [b for b in _bash_blocks(text) if "shared-ctx-builder.py" in b]
    return block.strip()


@pytest.mark.parametrize("which", ["suggest", "force"])
def test_the_context_is_deleted_before_it_is_built(which):
    text = _text(which)
    blocks = _bash_blocks(text)
    deletes = [i for i, b in enumerate(blocks) if "rm -f tomo-tmp/shared-ctx.json" in b]
    build = next(i for i, b in enumerate(blocks) if "shared-ctx-builder.py" in b)
    assert deletes and deletes[0] < build


@pytest.mark.parametrize("which", ["suggest", "force"])
def test_the_report_relays_the_duplicate_count(which):
    text = _text(which)
    report = text[text.index("### 7. Report"):]
    assert "duplicate_proposals_converted" in report


WARNINGS_OUT = " --warnings-out tomo-tmp/setup-warnings.txt"


def test_both_builder_commands_are_identical():
    """Both paths build the same context. `--warnings-out` only saves a copy of the
    WARN lines for suggest-handling's step 3 relay (spec 043 F4), so it is the one
    allowed difference."""
    suggest = _builder(_text("suggest"))
    assert suggest.endswith(WARNINGS_OUT)
    assert suggest[: -len(WARNINGS_OUT)] == _builder(_text("force"))


@pytest.mark.parametrize("which", ["suggest", "force"])
def test_both_paths_dispatch_the_same_analyst(which):
    """F6-AC1: Features 1–5 live in `inbox-analyst`, so both paths must run it."""
    assert re.findall(r'subagent_type: "([^"]+)"', _text(which)) == ["inbox-analyst"]


@pytest.mark.parametrize("which", ["suggest", "force"])
def test_both_relay_builder_warnings(which):
    assert "repeat every `WARN:` line this script prints" in _text(which)


def test_analyst_step_4_overrides_the_lyt_patterns_matching_algorithm():
    """`lyt-patterns` is shared with moc-architect and vault-explorer, which read
    the discovery cache, so its lexical algorithm and its cache-side
    `placeholder_links` line stay. The analyst loads it too, so Step 4 must say
    which rules win — otherwise "skip at zero overlap" competes with "by meaning".
    """
    agent = (REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md").read_text(encoding="utf-8")
    step4 = agent[agent.index("### Step 4"):agent.index("### Step 5")]
    assert "replace the `lyt-patterns` skill's MOC Matching Algorithm and Placeholder link awareness" in step4


def test_reset_pass1_clears_the_context_and_names_files(tmp_path):
    tmp = tmp_path / "tomo-tmp"
    (tmp / "items").mkdir(parents=True)
    (tmp / "shared-ctx.json").write_text("{}", encoding="utf-8")
    (tmp / "items" / "note-1a2b3c4d.moc-names.txt").write_text("X\n", encoding="utf-8")
    out = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "reset-tomo-tmp.sh"), "--pass1", "--instance", str(tmp)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert not (tmp / "shared-ctx.json").exists()
    assert not list(tmp.glob("items/*.moc-names.txt"))
