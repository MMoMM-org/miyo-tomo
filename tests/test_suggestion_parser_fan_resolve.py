#!/usr/bin/env python3
# version: 0.1.0
"""Regression guard for XDD 012 — Force Atomic Note synthesis.

Covers three parser scenarios for Force Atomic Note reconciliation:
(A) FAN without primary section AND no resolve doc → pending_fan_resolutions
(B) FAN without primary section BUT with resolve doc → promoted from resolve
(C) FAN with primary section (legacy 2665f81 path) → promoted, no resolve marker

Each scenario uses a minimal synthetic suggestions doc fed through the
actual parser via subprocess so the full argparse + pipeline flow is
exercised.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PARSER = REPO_ROOT / "tomo" / "scripts" / "suggestion-parser.py"


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

def _primary_doc_with_fan_on_furano(include_furano_section: bool) -> str:
    """Suggestions doc carrying a FAN-ticked log entry for 'Furano'.

    Layout mirrors the shape produced by suggestions-reducer.py +
    suggestions-render.py — date header `### [[YYYY-MM-DD]]`, log block
    `**Possible Log Entries (inline text):**`, entries with
    `[ ] Accept` / `[ ] Force Atomic Note` sub-bullets.

    When include_furano_section is False, there is NO per-item S## section
    for Furano in the primary doc — this simulates the worthiness-below-
    threshold case that triggers XDD 012's resolve path.
    """
    parts = [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-04-23T10:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 3",
        "run_id: 2026-04-23T10-00-00Z-test01",
        "---",
        "",
        "# Inbox Suggestions — 2026-04-23",
        "",
        "- [x] Approved — check this box when you have finished reviewing, then run `/inbox` for Pass 2",
        "",
        "## Summary",
        "",
        "- Items processed: 3",
        "",
        "## Daily Notes Updates",
        "",
        "### [[2026-04-17]]",
        "",
        "**Possible Log Entries (inline text):**",
        "- after_last_line — Furano liegt im Zentrum Hokkaidos und ist bekannt für die Lavendelfelder.",
        "  - Reason: Short descriptive note (280 chars), worthiness 0.3 — inline log entry",
        "  - Source: [[Furano]]",
        "  - [ ] Accept",
        "  - [x] Force Atomic Note (create/keep a standalone note for this item)",
        "",
        "## Suggestions",
        "",
    ]

    if include_furano_section:
        parts += [
            "### S01 — Furano trip reflections",
            "",
            "- [ ] Accept",
            "- [ ] Skip",
            "- [ ] Delete source",
            "",
            "**Suggested name:** Furano trip reflections",
            "**Source:** [[Furano]]",
            "**Type:** fleeting_note",
            "**Template:** Atomic Note.md",
            "**Destination:** Atlas/202 Notes/",
            "**Classification:** 2600 - Applied Sciences",
            "",
            "**Tags:**",
            "- topic/travel",
            "",
            "**Parent MOC:** [[Japan]]",
            "",
            "**Summary:** Day trip reflections from Furano and Biei.",
            "",
        ]

    return "\n".join(parts)


def _resolve_doc_for_furano() -> str:
    """Force-Atomic Resolve doc carrying an approved atomic for Furano."""
    return "\n".join([
        "---",
        "type: tomo-suggestions",
        "generated: 2026-04-23T11:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-04-23T11-00-00Z-test02",
        "---",
        "",
        "# Inbox Suggestions — Force-Atomic Resolve — 2026-04-23",
        "",
        "- [x] Approved",
        "",
        "## Summary",
        "",
        "- Items processed: 1",
        "- Sections: 1",
        "",
        "## Suggestions",
        "",
        "### S01 — Furano trip reflections",
        "",
        "- [x] Accept",
        "- [ ] Skip",
        "- [ ] Delete source",
        "",
        "**Suggested name:** Furano trip reflections",
        "**Source:** [[Furano]]",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "**Classification:** 2600 - Applied Sciences",
        "",
        "**Tags:**",
        "- topic/travel",
        "",
        "**Parent MOC:** [[Japan]]",
        "",
        "**Summary:** Day trip reflections from Furano and Biei.",
        "",
    ])


def _run_parser(primary_path: Path, resolve_path: Path | None = None) -> dict:
    cmd = [sys.executable, str(PARSER), "--file", str(primary_path)]
    if resolve_path is not None:
        cmd += ["--fan-resolve-file", str(resolve_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, (
        f"parser exit {result.returncode}; stderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_fan_without_section_no_resolve_populates_pending(tmp_path):
    """Scenario A: FAN ticked, no per-item section, no resolve doc.

    Parser must add the item to pending_fan_resolutions[] and MUST NOT
    add a confirmed_items entry for it. The log_entry itself still
    appears in daily_updates.
    """
    primary = tmp_path / "suggestions.md"
    primary.write_text(_primary_doc_with_fan_on_furano(include_furano_section=False))

    out = _run_parser(primary)

    pending = out.get("pending_fan_resolutions") or []
    assert len(pending) == 1, f"expected 1 pending, got {pending}"
    assert pending[0]["stem"] == "furano", pending[0]
    # The log entry carries an inline summary — ensure it flowed through.
    assert "furano" in pending[0]["log_entry_summary"].lower() or \
           "biei" in pending[0]["log_entry_summary"].lower(), pending[0]

    # No confirmed atomic for Furano.
    confirmed_stems = [
        c.get("source_path", "").rsplit("/", 1)[-1].replace(".md", "").lower()
        for c in out.get("confirmed_items", [])
    ]
    assert "furano" not in confirmed_stems, (
        f"FAN without resolve should NOT produce a confirmed item; got "
        f"{confirmed_stems}"
    )


def test_fan_with_resolve_promotes_from_resolve(tmp_path):
    """Scenario B: FAN ticked, no primary section, resolve doc present.

    Parser must merge the resolve-doc's atomic into confirmed_items,
    tag it with both force_atomic and from_resolve markers, and clear
    pending_fan_resolutions.
    """
    primary = tmp_path / "suggestions.md"
    resolve = tmp_path / "suggestions-fan.md"
    primary.write_text(_primary_doc_with_fan_on_furano(include_furano_section=False))
    resolve.write_text(_resolve_doc_for_furano())

    out = _run_parser(primary, resolve)

    assert out.get("pending_fan_resolutions") == [], (
        f"resolve doc should clear pending; got "
        f"{out.get('pending_fan_resolutions')}"
    )

    furano_entries = [
        c for c in out.get("confirmed_items", [])
        if "furano" in (c.get("source_path") or "").lower()
    ]
    assert len(furano_entries) == 1, (
        f"expected 1 Furano confirmed, got {furano_entries}"
    )
    entry = furano_entries[0]
    assert entry.get("force_atomic") is True, entry
    assert entry.get("from_resolve") is True, entry


def test_fan_with_primary_section_uses_legacy_promote(tmp_path):
    """Scenario C: FAN ticked AND primary-doc per-item section present.

    Parser must use the legacy promote path (commit 2665f81) — entry
    has force_atomic=True but NO from_resolve marker, and no resolve
    doc is consulted.
    """
    primary = tmp_path / "suggestions.md"
    primary.write_text(_primary_doc_with_fan_on_furano(include_furano_section=True))

    out = _run_parser(primary)

    assert out.get("pending_fan_resolutions") == []

    furano_entries = [
        c for c in out.get("confirmed_items", [])
        if "furano" in (c.get("source_path") or "").lower()
    ]
    assert len(furano_entries) == 1, furano_entries
    entry = furano_entries[0]
    assert entry.get("force_atomic") is True, entry
    assert entry.get("from_resolve") is not True, (
        f"legacy path must NOT set from_resolve; got {entry}"
    )
