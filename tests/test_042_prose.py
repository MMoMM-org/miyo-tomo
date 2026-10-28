#!/usr/bin/env python3
# version: 0.1.0
"""test_042_prose.py — spec 042 T5.1: around: routing and the Discovery line.

The runtime prose must route the exact lowercase `around:` prefix (F2-AC4) to
a single-pass `moc-discovery.py --around` call followed by the reducer, and
the STRICT six-field report must carry `links: <K> members, <L> lookups` on
the `Discovery:` line on every run, K = 0 included (F7-AC1, F7-AC2), with the
`(S skipped: budget)` suffix only when clusters were skipped.

RED before T5.1: neither file mentions `around:`, the Discovery template has
no link counts, and tomo-help lists a non-existent `placeholder` mode.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOT_CLAUDE = REPO_ROOT / "tomo" / "dot_claude"
COMMAND = DOT_CLAUDE / "commands" / "moc-propose.md"
AGENT = DOT_CLAUDE / "agents" / "moc-architect.md"
HELP = DOT_CLAUDE / "commands" / "tomo-help.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin + len(start))]


def _output_block(agent: str) -> str:
    out = agent[agent.index("## Output"):]
    (block,) = re.findall(r"```\n(Mode: <.*?)```", out, re.DOTALL)
    return block


# ── F2-AC4: whitelist + mode mapping ────────────────────────────────────────


def test_command_whitelist_lists_around():
    whitelist = next(
        line for line in _text(COMMAND).splitlines() if line.startswith("Whitelisted prefixes:")
    )
    assert "`around:`" in whitelist


def test_command_usage_shows_an_around_example():
    usage = _section(_text(COMMAND), "## Usage", "## Routing Rule")
    assert "/moc-propose around:" in usage


def test_command_keeps_capitalised_variants_as_free_text_for_around():
    assert "`Around:X` → free-text" in _text(COMMAND)


def test_agent_maps_lowercase_around_to_around_mode():
    step1 = _section(_text(AGENT), "### Step 1", "### Step 2")
    assert "Argument starts with `around:` → `around` mode" in step1


def test_agent_routes_capitalised_around_to_free_text():
    step1 = _section(_text(AGENT), "### Step 1", "### Step 2")
    assert "`Around:`" in step1 and "free-text" in step1


# ── around runs take the single-pass branch ─────────────────────────────────


def test_around_has_its_own_single_pass_branch():
    agent = _text(AGENT)
    branch = _section(agent, "#### Step 3 (around mode)", "#### Step 3 (all other modes)")
    calls = re.findall(r"python3 scripts/moc-discovery\.py[^\n`]*", branch)
    assert calls == [
        'python3 scripts/moc-discovery.py --around "<trigger_arg>" --config config/vault-config.yaml)'
    ]
    assert "Skip Steps 3a/3b/3c and go to Step 4" in branch


def test_around_is_not_in_the_two_pass_table():
    table = _section(_text(AGENT), "#### Step 3a", "#### Step 3b")
    assert "| around" not in table and "--around" not in table


def test_step5_reuses_disc_json_from_the_around_branch():
    step5 = _section(_text(AGENT), "### Step 5", "### Step 6")
    assert "around" in step5


def test_reducer_call_passes_the_config():
    agent = _text(AGENT)
    (call,) = [
        line for line in agent.splitlines()
        if "python3 scripts/suggestions-reducer.py" in line and "LOCAL_PROPOSAL=" in line
    ]
    assert "--config config/vault-config.yaml" in call


# ── F7-AC1 / F7-AC2: the Discovery line ─────────────────────────────────────


def test_strict_block_still_has_six_fields():
    fields = [line.split(":", 1)[0] for line in _output_block(_text(AGENT)).strip().splitlines()]
    assert fields == ["Mode", "Trigger arg", "Profile", "Discovery", "Proposal-doc", "Aborts/notes"]


def test_mode_field_lists_around():
    (mode_line,) = [
        line for line in _output_block(_text(AGENT)).splitlines() if line.startswith("Mode:")
    ]
    assert "around" in mode_line


def test_discovery_template_carries_link_counts():
    (line,) = [
        line for line in _output_block(_text(AGENT)).splitlines() if line.startswith("Discovery:")
    ]
    assert "links: <K> members, <L> lookups" in line
    assert "(<S> skipped: budget)" in line


def test_discovery_fill_rules_cover_k_zero_and_the_budget_suffix():
    out = _text(AGENT)[_text(AGENT).index("## Output"):]
    assert "`link_stats.members_total`" in out and "`link_stats.lookups`" in out
    assert "links: 0 members, <L> lookups" in out
    assert "only when `link_stats.clusters_skipped_budget` > 0" in out
    assert "lookups failed: <F>" in out


def test_success_example_shows_link_counts():
    out = _text(AGENT)[_text(AGENT).index("**Example (success):**"):]
    example = out[:out.index("**Example (abort):**")]
    assert re.search(r"^Discovery: OK — \d+ candidates → \d+ clusters; links: \d+ members, \d+ lookups", example, re.M)


def test_abort_example_shows_zero_link_counts():
    out = _text(AGENT)[_text(AGENT).index("**Example (abort):**"):]
    assert re.search(r"^Discovery: \S+; links: 0 members, \d+ lookups$", out, re.M)


# ── tomo-help ───────────────────────────────────────────────────────────────


def _help_moc_propose_entry() -> str:
    return _section(_text(HELP), "- **moc-propose /", "- **templates /")


def test_help_lists_around():
    assert "around:" in _help_moc_propose_entry()


def test_help_no_longer_lists_a_placeholder_mode():
    assert "placeholder" not in _help_moc_propose_entry()


# ── versions bumped ─────────────────────────────────────────────────────────


def _version(path: Path) -> tuple[int, ...]:
    (v,) = re.findall(r"^# version: (\d+\.\d+\.\d+)$", _text(path), re.M)
    return tuple(int(p) for p in v.split("."))


def test_versions_were_bumped():
    assert _version(COMMAND) > (0, 3, 0)
    assert _version(AGENT) > (0, 7, 0)
    assert _version(HELP) > (0, 2, 20)
