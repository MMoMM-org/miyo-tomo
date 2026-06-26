#!/usr/bin/env python3
# version: 0.2.0
"""test_instruction_render_four_tier_tracking.py — T7.1 metadata-only four-tier resolution telemetry.

Verifies that _emit_resolution_telemetry():
  1. Emits a single tagged stderr line with per-tier counts and MOC paths.
  2. NEVER leaks anchor.value (heading text) or any note body content.
  3. Correctly tallies all five tier/state buckets:
     heading, new_section, callout, line, unresolved.

Spec: docs/XDD/specs/022-moc-insertion-point-intelligence/
AC:   T7.1 — metadata-only telemetry, Constitution L2 Privacy constraint.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules.setdefault("instruction_render", ir)
_spec.loader.exec_module(ir)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SECRET_HEADING = "SECRET HEADING TEXT"
SECRET_CONTENT = "SECRET NOTE BODY CONTENT"


def _make_actions() -> list[dict]:
    """Build a representative set of resolved link_to_moc actions spanning all tiers.

    Includes a clearly marked sensitive string in anchor.value and target_path to
    verify privacy: those strings MUST NOT appear in the emitted telemetry line.
    """
    return [
        # --- Tier: heading (anchor.type == "heading", no new_section) ---
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Concepts MOC.md",
            "anchor": {"type": "heading", "value": SECRET_HEADING, "placement": "after"},
        },
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Projects MOC.md",
            "anchor": {"type": "heading", "value": "Other heading", "placement": "after"},
        },
        # --- Tier: new_section (top-level new_section set) ---
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Books MOC.md",
            "new_section": "New Reading List",
            "anchor": {"type": "heading", "value": "Some heading", "placement": "after"},
        },
        # --- Tier: callout (anchor.type == "callout", no new_section) ---
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Tools MOC.md",
            "anchor": {"type": "callout", "value": "[!links]", "placement": "after"},
        },
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Ideas MOC.md",
            "anchor": {"type": "callout", "value": "[!related]", "placement": "after"},
        },
        # --- Tier: line (anchor.type == "line") ---
        # (zero actions — count=0 must still appear in output)
        # --- Tier: unresolved (anchor.value is None) ---
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Archive MOC.md",
            "anchor": {"type": "heading", "value": None, "placement": "after"},
        },
        # Non-link_to_moc action — must be ignored
        {
            "action": "log_entry",
            "target_path": f"Daily/{SECRET_CONTENT}",
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_emit_resolution_telemetry_outputs_tagged_stderr_line(capsys):
    """Telemetry function emits exactly one [instruction-render] tagged stderr line."""
    actions = _make_actions()

    ir._emit_resolution_telemetry(actions)

    captured = capsys.readouterr()
    assert "[instruction-render]" in captured.err, (
        f"Expected '[instruction-render]' tag in stderr, got: {captured.err!r}"
    )
    # Exactly one telemetry line (may contain newline at end, but only one line of content)
    lines = [ln for ln in captured.err.strip().splitlines() if ln.strip()]
    assert len(lines) == 1, f"Expected exactly 1 output line, got {len(lines)}: {lines!r}"


def test_emit_resolution_telemetry_counts_all_tiers(capsys):
    """Telemetry line contains correct per-tier counts for heading/new_section/callout/line/unresolved."""
    actions = _make_actions()

    ir._emit_resolution_telemetry(actions)

    err = capsys.readouterr().err
    assert "heading=2" in err, f"Expected heading=2 in: {err!r}"
    assert "new_section=1" in err, f"Expected new_section=1 in: {err!r}"
    assert "callout=2" in err, f"Expected callout=2 in: {err!r}"
    assert "line=0" in err, f"Expected line=0 in: {err!r}"
    assert "unresolved=1" in err, f"Expected unresolved=1 in: {err!r}"


def test_emit_resolution_telemetry_includes_moc_paths_or_stems(capsys):
    """Telemetry line includes MOC path/stem metadata (permitted by Constitution L2)."""
    actions = _make_actions()

    ir._emit_resolution_telemetry(actions)

    err = capsys.readouterr().err
    # At least one MOC path/stem appears in the output
    assert "Concepts MOC" in err or "PKM" in err, (
        f"Expected MOC path metadata in stderr, got: {err!r}"
    )


def test_emit_resolution_telemetry_never_leaks_anchor_value(capsys):
    """Privacy (Constitution L2): anchor.value heading text MUST NOT appear in telemetry."""
    actions = _make_actions()

    ir._emit_resolution_telemetry(actions)

    err = capsys.readouterr().err
    assert SECRET_HEADING not in err, (
        f"PRIVACY VIOLATION: anchor.value '{SECRET_HEADING}' leaked into telemetry: {err!r}"
    )


def test_emit_resolution_telemetry_never_leaks_note_content(capsys):
    """Privacy (Constitution L2): link_to_moc fields carrying note content MUST NOT leak.

    At telemetry time a resolved link_to_moc action carries source_note_title
    (the user's note title) and line_to_add (e.g. '- [[Note Title]]'). Neither
    must appear in the emitted line. This test places SECRET_CONTENT in exactly
    those fields on a valid link_to_moc action — not in a skipped log_entry —
    so the assertion is real, not trivially passing because the action is filtered
    before any field is read.
    """
    actions = [
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Concepts MOC.md",
            "source_note_title": SECRET_CONTENT,
            "line_to_add": f"- [[{SECRET_CONTENT}]]",
            "anchor": {"type": "heading", "value": "Section", "placement": "after"},
        },
    ]

    ir._emit_resolution_telemetry(actions)

    err = capsys.readouterr().err
    assert SECRET_CONTENT not in err, (
        f"PRIVACY VIOLATION: note content '{SECRET_CONTENT}' leaked via "
        f"source_note_title/line_to_add into telemetry: {err!r}"
    )


def test_emit_resolution_telemetry_is_side_effect_free(capsys):
    """Calling telemetry must not mutate the actions list."""
    actions = _make_actions()
    original_snapshot = [dict(a) for a in actions]

    ir._emit_resolution_telemetry(actions)

    for before, after in zip(original_snapshot, actions):
        assert before == after, (
            f"Action mutated by telemetry: {before!r} → {after!r}"
        )


def test_emit_resolution_telemetry_empty_actions(capsys):
    """Empty action list emits a valid zero-count line without error."""
    ir._emit_resolution_telemetry([])

    err = capsys.readouterr().err
    assert "[instruction-render]" in err
    assert "heading=0" in err
    assert "new_section=0" in err
    assert "callout=0" in err
    assert "line=0" in err
    assert "unresolved=0" in err


def test_emit_resolution_telemetry_ignores_non_link_to_moc(capsys):
    """Non-link_to_moc actions are excluded from all tier counts."""
    actions = [
        {"action": "log_entry", "target_path": "Daily/2026-06-15.md"},
        {"action": "create_moc", "target_moc_path": "PKM/New MOC.md"},
        {
            "action": "link_to_moc",
            "target_moc_path": "PKM/Solo MOC.md",
            "anchor": {"type": "heading", "value": "Section", "placement": "after"},
        },
    ]

    ir._emit_resolution_telemetry(actions)

    err = capsys.readouterr().err
    assert "heading=1" in err, f"Expected only 1 heading from 1 link_to_moc, got: {err!r}"
    assert "mocs=1" in err or "Solo MOC" in err, (
        f"Expected 1 MOC counted, got: {err!r}"
    )


def test_emit_resolution_telemetry_target_moc_fallback(capsys):
    """target_moc fallback is used when target_moc_path is absent or None."""
    actions = [
        {
            "action": "link_to_moc",
            "target_moc_path": None,
            "target_moc": "PKM/Fallback MOC",
            "anchor": {"type": "callout", "value": "[!links]", "placement": "after"},
        },
    ]

    ir._emit_resolution_telemetry(actions)

    err = capsys.readouterr().err
    assert "callout=1" in err, f"Expected callout=1, got: {err!r}"
    assert "mocs=1" in err, f"Expected mocs=1, got: {err!r}"
    assert "Fallback MOC" in err, (
        f"Expected fallback stem 'Fallback MOC' in paths, got: {err!r}"
    )
