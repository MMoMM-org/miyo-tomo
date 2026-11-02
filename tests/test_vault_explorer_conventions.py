"""vault-explorer follows the agent conventions (#44)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

AGENT = Path(__file__).resolve().parent.parent / "tomo" / "dot_claude" / "agents" / "vault-explorer.md"
TEXT = AGENT.read_text(encoding="utf-8")
FRONT = yaml.safe_load(re.match(r"^---\n(.*?)\n---", TEXT, re.S).group(1))
HEADINGS = re.findall(r"^## (.+)$", TEXT, re.M)


def test_description_triggers_on_the_command():
    assert FRONT["description"].startswith("MUST BE USED")
    assert "/explore-vault" in FRONT["description"]


def test_agent_tool_is_not_granted():
    assert "Agent" not in [t.strip() for t in FRONT["tools"].split(",")]


def test_writer_colour():
    assert FRONT["color"] == "green"


def test_announcement_follows_the_title_block():
    assert "\n**Active agent: vault-explorer**\n" in TEXT[: TEXT.index("## Identity")]


def test_sections_in_order():
    wanted = ["Identity", "Constraints", "Mission", "Workflow", "Decision: Run Mode", "Edge Cases", "Output"]
    assert [h for h in HEADINGS if h in wanted] == wanted


def test_findings_are_printed_before_every_question():
    section = TEXT[TEXT.index("## Constraints") : TEXT.index("## Mission")]
    rule = next(ln for ln in section.splitlines() if ln.startswith("- **STRICT:** Print the complete findings"))
    for phrase in ("visible text", "before its AskUserQuestion call", "Findings in thinking count as not printed"):
        assert phrase in rule


def test_schema_paths_resolve_inside_the_instance():
    assert "tomo/schemas/" not in TEXT
    assert "--schema schemas/vault-config-trackers.schema.json" in TEXT


def test_modified_after_is_unix_milliseconds():
    assert "modifiedAfter: <unix-ms-14d-ago>" in TEXT
    assert "iso-timestamp" not in TEXT


def test_tracker_findings_list_every_field_as_text():
    step = TEXT[TEXT.index("### Step 7") : TEXT.index("Use AskUserQuestion with multiSelect: \"Which of these fields")]
    assert "Print this list as visible text, one line per detected field" in step


def test_templates_summary_points_at_step_8_for_missing_files():
    assert "`templates_mapped_count`, `templates_unmapped_count`" in TEXT
    assert "templates_found_count" not in TEXT
    assert "Missing template files come from Step 8" in TEXT


def test_run_mode_table_keeps_all_three_modes():
    section = TEXT[TEXT.index("## Decision: Run Mode") : TEXT.index("## Edge Cases")]
    rows = [ln for ln in section.splitlines() if ln.startswith("| ")]
    assert len(rows) == 4  # header + three modes
    for phrase in ("--confirm", "Do not modify vault-config.yaml", "Rebuild discovery cache",
                   "This will overwrite current config sections. Proceed? [Y/n]"):
        assert phrase in section
