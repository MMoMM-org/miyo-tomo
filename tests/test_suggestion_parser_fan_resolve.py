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
import re
import subprocess
import sys
from pathlib import Path


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


def _resolve_doc_for_furano_two_blocks() -> str:
    """Force-Atomic Resolve doc with TWO approved atomic blocks under S01.

    Mirrors the multi-block render layout produced by suggestions-reducer.py:
    N atomics concatenated under the same ### SNN heading. Each block begins
    with a **Source:** field line — the boundary used by
    split_section_into_blocks — followed by **Suggested name:** and the rest
    of the fields (same order as _atomic_block in test_suggestion_parser_multi_atomic.py).
    """
    return "\n".join([
        "---",
        "type: tomo-suggestions",
        "generated: 2026-04-23T11:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-04-23T11-00-00Z-test03",
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
        "**Source:** [[Furano]]",
        "**Suggested name:** Furano trip reflections",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "**Classification:** 2600 - Applied Sciences",
        "",
        "**Decision (atomic note):**",
        "- [x] Approve",
        "- [ ] Keep in inbox",
        "- [ ] Skip (keep in inbox)",
        "- [ ] Delete source",
        "",
        "**Tags:**",
        "- topic/travel",
        "",
        "**Parent MOC:** [[Japan]]",
        "",
        "**Summary:** Day trip reflections from Furano and Biei.",
        "",
        "**Source:** [[Furano]]",
        "**Suggested name:** Furano lavender fields",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "**Classification:** 2600 - Applied Sciences",
        "",
        "**Decision (atomic note):**",
        "- [x] Approve",
        "- [ ] Keep in inbox",
        "- [ ] Skip (keep in inbox)",
        "- [ ] Delete source",
        "",
        "**Tags:**",
        "- topic/nature",
        "",
        "**Parent MOC:** [[Japan]]",
        "",
        "**Summary:** Lavender fields are the main attraction in Furano.",
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


def _primary_doc_confirmed_s01_plus_fan_furano() -> str:
    """Primary doc with an APPROVED atomic at S01 (a different note) AND a
    FAN-ticked log entry for Furano. The confirmed S01 collides with the
    resolve doc's S01 Furano — the regression this guards."""
    return "\n".join([
        "---", "type: tomo-suggestions", "generated: 2026-04-23T10:00:00Z",
        'tomo_version: "0.1.0"', "profile: miyo", "source_items: 2",
        "run_id: 2026-04-23T10-00-00Z-test01", "---", "",
        "# Inbox Suggestions — 2026-04-23", "",
        "- [x] Approved", "",
        "## Daily Notes Updates", "",
        "### [[2026-04-17]]", "",
        "**Possible Log Entries (inline text):**",
        "- after_last_line — Furano liegt im Zentrum Hokkaidos.",
        "  - Source: [[Furano]]",
        "  - [ ] Accept",
        "  - [x] Force Atomic Note (create/keep a standalone note for this item) ✅ 2026-06-18",
        "",
        "## Suggestions", "",
        "### S01 — Some Other Confirmed Note", "",
        "- [x] Accept",
        "- [ ] Skip",
        "- [ ] Delete source", "",
        "**Suggested name:** Some Other Confirmed Note",
        "**Source:** [[Other Note]]",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "**Parent MOC:** [[Concepts]]", "",
        "**Summary:** Unrelated note that happens to occupy S01.", "",
    ])


def test_fan_resolve_id_collision_with_primary_promotes(tmp_path):
    """Regression: the resolve doc's atomic id (S01) collides with an already-
    confirmed primary item (also S01). The merge must still promote the resolve
    atomic (re-numbered to a collision-free id), not drop it to pending — and
    confirmed_items must have no duplicate ids (id_index integrity)."""
    primary = tmp_path / "suggestions.md"
    resolve = tmp_path / "suggestions-fan.md"
    primary.write_text(_primary_doc_confirmed_s01_plus_fan_furano())
    resolve.write_text(_resolve_doc_for_furano())  # Furano atomic at S01

    out = _run_parser(primary, resolve)

    assert out.get("pending_fan_resolutions") == [], (
        f"collision must not drop to pending; got {out.get('pending_fan_resolutions')}"
    )
    furano = [c for c in out.get("confirmed_items", [])
              if "furano" in (c.get("source_path") or "").lower()]
    assert len(furano) == 1, f"Furano must be promoted, got {furano}"
    assert furano[0].get("from_resolve") is True, furano[0]

    ids = [c.get("id") for c in out.get("confirmed_items", [])]
    assert len(ids) == len(set(ids)), f"confirmed_items has duplicate ids: {ids}"
    assert furano[0]["id"] not in ("S01",), (
        f"resolve atomic must be re-id'd off the colliding S01, got {furano[0]['id']}"
    )
    # The renumbered id must be a well-formed S## — not None/""/garbage that would
    # also satisfy "not S01" while corrupting id_index integrity (review M12).
    assert re.match(r"^S\d+$", furano[0]["id"] or ""), (
        f"renumbered id must match ^S\\d+$, got {furano[0]['id']!r}"
    )


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


def test_fan_resolve_multi_block_promotes_all(tmp_path):
    """Scenario D (T4.2 RED): resolve doc S01 contains TWO approved atomic
    blocks — BOTH must appear in confirmed_items (from_resolve=True each),
    not just the last one (the pre-T4.2 last-wins bug).
    """
    primary = tmp_path / "suggestions.md"
    resolve = tmp_path / "suggestions-fan.md"
    primary.write_text(_primary_doc_with_fan_on_furano(include_furano_section=False))
    resolve.write_text(_resolve_doc_for_furano_two_blocks())

    out = _run_parser(primary, resolve)

    assert out.get("pending_fan_resolutions") == [], (
        f"multi-block resolve doc should clear pending; got "
        f"{out.get('pending_fan_resolutions')}"
    )

    furano_entries = [
        c for c in out.get("confirmed_items", [])
        if "furano" in (c.get("source_path") or "").lower()
    ]
    assert len(furano_entries) == 2, (
        f"expected 2 Furano confirmed items (one per block), got "
        f"{[e.get('title') for e in furano_entries]}"
    )
    for entry in furano_entries:
        assert entry.get("force_atomic") is True, entry
        assert entry.get("from_resolve") is True, entry

    titles = {e.get("title") for e in furano_entries}
    assert "Furano trip reflections" in titles, titles
    assert "Furano lavender fields" in titles, titles


def test_fan_resolve_single_block_no_regression(tmp_path):
    """Scenario E (T4.2 single-thread regression): resolve doc with ONE
    block still yields exactly 1 confirmed item — byte-identical to pre-T4.2.
    """
    primary = tmp_path / "suggestions.md"
    resolve = tmp_path / "suggestions-fan.md"
    primary.write_text(_primary_doc_with_fan_on_furano(include_furano_section=False))
    resolve.write_text(_resolve_doc_for_furano())

    out = _run_parser(primary, resolve)

    furano_entries = [
        c for c in out.get("confirmed_items", [])
        if "furano" in (c.get("source_path") or "").lower()
    ]
    assert len(furano_entries) == 1, (
        f"single-block resolve must yield exactly 1 confirmed, got "
        f"{[e.get('title') for e in furano_entries]}"
    )
    entry = furano_entries[0]
    assert entry.get("force_atomic") is True, entry
    assert entry.get("from_resolve") is True, entry


def _doc_with_proposed_moc(name: str, supporting: str, topic: str) -> str:
    """Minimal suggestions doc carrying a single approved Proposed MOC."""
    return "\n".join([
        "---",
        "type: tomo-suggestions",
        "generated: 2026-06-19T10:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-06-19T10-00-00Z-merge",
        "---",
        "",
        "# Inbox Suggestions — 2026-06-19",
        "",
        "- [x] Approved",
        "",
        "## Proposed MOCs",
        "",
        f"### Proposed MOC: {topic}",
        f"- **Name:** {name}",
        "- **Parent:** [[2700 - Art & Recreation]]",
        f"- **Supporting items:** {supporting}",
        "- **Decision:**",
        "  - [x] Approve (create this MOC with the Name above)",
        "  - [ ] Skip",
        "",
    ])


def test_fan_and_primary_proposed_mocs_merge_by_name(tmp_path):
    """Fan proposed-MOC fix: a Proposed MOC in the fan-resolve doc merges
    by-name (#67) with a same-named Proposed MOC in the primary doc → ONE
    create_moc with the union of supporting items, not two. Regression guard
    for the parser half of the fan proposed-MOC fix."""
    primary = tmp_path / "suggestions.md"
    fan = tmp_path / "suggestions-fan.md"
    primary.write_text(
        _doc_with_proposed_moc("Board Games (MOC)", "Catan", topic="Gesellschaftsspiele")
    )
    fan.write_text(
        _doc_with_proposed_moc("Board Games (MOC)", "Wingspan", topic="Games")
    )

    out = _run_parser(primary, fan)

    mocs = [c for c in out.get("confirmed_items", []) if c.get("action") == "create_moc"]
    assert len(mocs) == 1, (
        f"expected ONE merged create_moc, got {len(mocs)}: "
        f"{[m.get('title') for m in mocs]}"
    )
    assert mocs[0]["title"] == "Board Games (MOC)", mocs[0].get("title")
    supporting = mocs[0].get("supporting_items") or ""
    assert "Catan" in supporting and "Wingspan" in supporting, (
        f"merged MOC must union supporting items; got {supporting!r}"
    )
