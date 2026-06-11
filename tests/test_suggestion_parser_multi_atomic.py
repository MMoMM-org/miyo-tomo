#!/usr/bin/env python3
"""Behavioural tests for F-41 (XDD 016) Phase 4 — N-entry section parsing.

The renderer emits N atomic blocks under ONE `### S01` heading (OQ5,
Phase 3). Each block starts with a `**Source:** [[stem]]` field line. The
parser must split that single section into N confirmed items rather than
collapsing them to one (last-wins).

Scenarios:
  1. Two atomic blocks, both Approve [x]      → 2 confirmed, distinct titles
  2. Mixed approval (block1 [x], block2 Skip) → 1 confirmed, 1 skipped
  3. Force-Atomic on a daily log entry whose stem has 2 unapproved blocks
     → BOTH promoted
  4. Single-block section                     → exactly 1 item (CON-2)

Each doc is fed through the real parser via subprocess so the full
argparse + pipeline flow is exercised (mirrors
test_suggestion_parser_fan_resolve.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PARSER = REPO_ROOT / "tomo" / "scripts" / "suggestion-parser.py"


# ──────────────────────────────────────────────────────────────────────
# Fixture helpers
# ──────────────────────────────────────────────────────────────────────

def _doc_header() -> list[str]:
    return [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-06-10T10:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-06-10T10-00-00Z-test01",
        "---",
        "",
        "# Inbox Suggestions — 2026-06-10",
        "",
        "- [x] Approved — check this box when you have finished reviewing",
        "",
        "## Summary",
        "",
        "- Items processed: 1",
        "",
    ]


def _atomic_block(title: str, *, accept: bool, skip: bool = False) -> list[str]:
    """One atomic block as the reducer/renderer emit it — starts at **Source:**."""
    return [
        "**Source:** [[memo]]",
        f"**Suggested name:** {title}",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "",
        "**Decision (atomic note):**",
        f"- [{'x' if accept else ' '}] Approve",
        "- [ ] Keep in inbox",
        f"- [{'x' if skip else ' '}] Skip (keep in inbox)",
        "- [ ] Delete source",
        "",
    ]


def _two_atomic_doc(*, b1_accept: bool, b2_accept: bool, b2_skip: bool = False) -> str:
    parts = _doc_header()
    parts += ["## Suggestions", "", "### S01 — Memo split", ""]
    parts += _atomic_block("First Topic", accept=b1_accept)
    parts += _atomic_block("Second Topic", accept=b2_accept, skip=b2_skip)
    return "\n".join(parts)


def _single_atomic_doc() -> str:
    parts = _doc_header()
    parts += ["## Suggestions", "", "### S01 — Memo single", ""]
    parts += _atomic_block("Only Topic", accept=True)
    return "\n".join(parts)


def _two_atomic_fan_doc() -> str:
    """Two unapproved atomic blocks for 'memo' + a daily log entry with
    Force Atomic Note ticked for the same stem."""
    parts = _doc_header()
    parts += [
        "## Daily Notes Updates",
        "",
        "### [[2026-06-10]]",
        "",
        "**Possible Log Entries (inline text):**",
        "- after_last_line — Memo about two distinct things worth splitting.",
        "  - Reason: worthiness 0.3 — inline log entry",
        "  - Source: [[memo]]",
        "  - [ ] Accept",
        "  - [x] Force Atomic Note (create/keep a standalone note for this item)",
        "",
        "## Suggestions",
        "",
        "### S01 — Memo split",
        "",
    ]
    parts += _atomic_block("First Topic", accept=False)
    parts += _atomic_block("Second Topic", accept=False)
    return "\n".join(parts)


def _run_parser(primary_path: Path) -> dict:
    cmd = [sys.executable, str(PARSER), "--file", str(primary_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, (
        f"parser exit {result.returncode}; stderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def _stem(src: str | None) -> str:
    if not src:
        return ""
    return src.rsplit("/", 1)[-1].replace(".md", "").strip("[]").lower()


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_two_atomic_blocks_both_approved_yield_two_items(tmp_path):
    primary = tmp_path / "suggestions.md"
    primary.write_text(_two_atomic_doc(b1_accept=True, b2_accept=True))

    out = _run_parser(primary)

    memo = [c for c in out["confirmed_items"] if _stem(c.get("source_path")) == "memo"]
    assert len(memo) == 2, f"expected 2 confirmed memo items, got {memo}"
    titles = sorted(c["title"] for c in memo)
    assert titles == ["First Topic", "Second Topic"], titles
    for c in memo:
        assert _stem(c["source_path"]) == "memo", c


def test_mixed_approval_in_one_section_splits_confirmed_and_skipped(tmp_path):
    primary = tmp_path / "suggestions.md"
    primary.write_text(_two_atomic_doc(b1_accept=True, b2_accept=False, b2_skip=True))

    out = _run_parser(primary)

    confirmed = [
        c for c in out["confirmed_items"] if _stem(c.get("source_path")) == "memo"
    ]
    assert len(confirmed) == 1, f"expected 1 confirmed, got {confirmed}"
    assert confirmed[0]["title"] == "First Topic", confirmed[0]

    skipped = [
        s for s in out["skipped"] if _stem(s.get("source_path")) == "memo"
    ]
    assert len(skipped) == 1, f"expected 1 skipped memo, got {skipped}"


def test_force_atomic_promotes_both_unapproved_blocks(tmp_path):
    primary = tmp_path / "suggestions.md"
    primary.write_text(_two_atomic_fan_doc())

    out = _run_parser(primary)

    memo = [c for c in out["confirmed_items"] if _stem(c.get("source_path")) == "memo"]
    assert len(memo) == 2, f"Force-Atomic must promote BOTH blocks, got {memo}"
    titles = sorted(c["title"] for c in memo)
    assert titles == ["First Topic", "Second Topic"], titles
    for c in memo:
        assert c.get("force_atomic") is True, c


def test_single_block_section_yields_exactly_one_item(tmp_path):
    primary = tmp_path / "suggestions.md"
    primary.write_text(_single_atomic_doc())

    out = _run_parser(primary)

    memo = [c for c in out["confirmed_items"] if _stem(c.get("source_path")) == "memo"]
    assert len(memo) == 1, f"single block must yield exactly 1 item, got {memo}"
    assert memo[0]["title"] == "Only Topic", memo[0]
    assert memo[0]["id"] == "S01", memo[0]
