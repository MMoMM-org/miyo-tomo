#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_render_per_atomic_header.py — T2 (F-41): per-atomic headers in renderer.

Covers:
  T2.1  Two create_atomic_note actions → two separate ### SNN — <title> headers
  T2.2  Each header uses the TITLE from its own atomic, not the first atomic's title
  T2.3  Single-atomic section → exactly one header (regression guard)
  T2.4  Header count == total create_atomic_note action count across all sections

Spec: docs/XDD/specs/016-multi-topic-atomic-notes/
"""
from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_render_mod():
    """Load suggestions-render.py as a module (not a package)."""
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_t2",
        SCRIPTS_DIR / "suggestions-render.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_atomic_action(suggestion_id: str, title: str) -> dict[str, Any]:
    """Return a minimal create_atomic_note action with the given suggestion_id and title."""
    rendered = (
        f"**Suggested name:** {title}    ← change if you want\n"
        "**Template:** [[t_note_tomo]]\n\n"
        "**Decision (atomic note):**\n"
        "- [ ] Approve\n"
        "- [ ] Skip\n"
    )
    return {
        "kind": "create_atomic_note",
        "suggestion_id": suggestion_id,
        "rendered_md": rendered,
    }


def _make_suggestions_doc(sections: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a minimal valid suggestions-doc dict with the given sections."""
    return {
        "schema_version": "1",
        "generated": "2026-06-11T10:00:00Z",
        "run_id": "2026-06-11-1000-test00",
        "profile": "miyo",
        "doc_variant": "primary",
        "source_items": len(sections),
        "sections": sections,
        "daily_notes_updates": [],
        "proposed_mocs": [],
        "needs_attention": [],
    }


def _make_section(sid: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": sid, "stem": sid + "_stem", "actions": actions}


# Regex that matches a suggestions header: ### SNN — <anything>
_HEADER_RE = re.compile(r"^### S\d+")


def _collect_headers(lines: list[str]) -> list[str]:
    return [ln for ln in lines if _HEADER_RE.match(ln)]


# ---------------------------------------------------------------------------
# T2.1 — two atomics in one section → two separate ### SNN — <title> headers
# ---------------------------------------------------------------------------

class TestPerAtomicHeaders:

    def test_two_actions_produce_two_headers(self):
        """A section with 2 create_atomic_note actions must emit 2 distinct ### headers."""
        mod = _load_render_mod()
        doc = _make_suggestions_doc([
            _make_section("S01", [
                _make_atomic_action("S01", "Alpha Note"),
                _make_atomic_action("S02", "Beta Note"),
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        assert len(headers) == 2, (
            f"Expected 2 headers for 2 atomics, got {len(headers)}: {headers}"
        )

    # T2.2 — each header uses the title from ITS OWN atomic
    def test_each_header_uses_own_atomic_title(self):
        """Headers must use the 'Suggested name' from their respective atomic blocks."""
        mod = _load_render_mod()
        doc = _make_suggestions_doc([
            _make_section("S01", [
                _make_atomic_action("S01", "Alpha Note"),
                _make_atomic_action("S02", "Beta Note"),
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        # First header must contain the FIRST atomic's title
        assert "Alpha Note" in headers[0], (
            f"First header should contain 'Alpha Note', got: {headers[0]!r}"
        )
        # Second header must contain the SECOND atomic's title (not Alpha)
        assert "Beta Note" in headers[1], (
            f"Second header should contain 'Beta Note', got: {headers[1]!r}"
        )
        assert "Alpha Note" not in headers[1], (
            f"Second header must NOT reuse first atomic's title: {headers[1]!r}"
        )

    # T2.3 — single-atomic section → exactly one header (regression)
    def test_single_action_produces_one_header(self):
        """Single-atomic section must still emit exactly one ### SNN — <title> header."""
        mod = _load_render_mod()
        doc = _make_suggestions_doc([
            _make_section("S01", [
                _make_atomic_action("S01", "Solo Note"),
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        assert len(headers) == 1, (
            f"Expected 1 header for 1 atomic, got {len(headers)}: {headers}"
        )
        assert "Solo Note" in headers[0]

    # T2.4 — header count == total create_atomic_note actions across sections
    def test_header_count_equals_total_atomic_action_count(self):
        """Total ### headers == total create_atomic_note actions across all sections."""
        mod = _load_render_mod()
        doc = _make_suggestions_doc([
            _make_section("S01", [
                _make_atomic_action("S01", "Alpha"),
                _make_atomic_action("S02", "Beta"),
            ]),
            _make_section("S03", [
                _make_atomic_action("S03", "Gamma"),
            ]),
            _make_section("S04", [
                _make_atomic_action("S04", "Delta"),
                _make_atomic_action("S05", "Epsilon"),
                _make_atomic_action("S06", "Zeta"),
            ]),
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        total_atomics = sum(
            1
            for s in doc["sections"]
            for a in s["actions"]
            if a.get("kind") == "create_atomic_note"
        )
        assert len(headers) == total_atomics, (
            f"Expected {total_atomics} headers, got {len(headers)}: {headers}"
        )

    def test_header_uses_suggestion_id_from_action(self):
        """Each header must use suggestion_id from the action, not the section id."""
        mod = _load_render_mod()
        doc = _make_suggestions_doc([
            _make_section("S01", [
                _make_atomic_action("S01", "Alpha"),
                _make_atomic_action("S02", "Beta"),
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        assert headers[0].startswith("### S01 —"), (
            f"First header must start with '### S01 —', got: {headers[0]!r}"
        )
        assert headers[1].startswith("### S02 —"), (
            f"Second header must start with '### S02 —', got: {headers[1]!r}"
        )

    def test_arrow_trimming_preserved_per_atomic(self):
        """The ← trimming rule still applies per-atomic title extraction."""
        mod = _load_render_mod()
        rendered = (
            "**Suggested name:** MOC Strukturierung    ← change if you want\n"
            "**Decision (atomic note):**\n- [ ] Approve\n"
        )
        doc = _make_suggestions_doc([
            _make_section("S01", [
                {
                    "kind": "create_atomic_note",
                    "suggestion_id": "S01",
                    "rendered_md": rendered,
                }
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        assert len(headers) == 1
        # ← and everything after must be stripped
        assert "←" not in headers[0], (
            f"Arrow not trimmed from header: {headers[0]!r}"
        )
        assert "MOC Strukturierung" in headers[0]

    def test_fallback_to_section_id_when_no_suggestion_id(self):
        """If action has no suggestion_id, fall back to section id for the first action."""
        mod = _load_render_mod()
        doc = _make_suggestions_doc([
            _make_section("S05", [
                {
                    "kind": "create_atomic_note",
                    "rendered_md": "**Suggested name:** Fallback Note\n**Decision:**\n- [ ] Approve\n",
                    # no suggestion_id key at all
                }
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        assert len(headers) == 1, f"Expected 1 header, got {len(headers)}"
        # Should use section id S05 as fallback
        assert "S05" in headers[0], (
            f"Fallback to section id 'S05' expected in header: {headers[0]!r}"
        )
        assert "Fallback Note" in headers[0]

    def test_header_appears_directly_before_its_block(self):
        """Each ### header must appear directly before (or immediately before) its rendered_md block."""
        mod = _load_render_mod()
        title1, title2 = "Alpha Note", "Beta Note"
        block1_marker = "Source Alpha"
        block2_marker = "Source Beta"
        doc = _make_suggestions_doc([
            _make_section("S01", [
                {
                    "kind": "create_atomic_note",
                    "suggestion_id": "S01",
                    "rendered_md": f"**Suggested name:** {title1}\n{block1_marker}\n",
                },
                {
                    "kind": "create_atomic_note",
                    "suggestion_id": "S02",
                    "rendered_md": f"**Suggested name:** {title2}\n{block2_marker}\n",
                },
            ])
        ])

        lines = mod.render_suggestions(doc)
        text = "\n".join(lines)

        # Header for S01 must precede block1_marker content
        idx_h1 = text.find("### S01")
        idx_b1 = text.find(block1_marker)
        idx_h2 = text.find("### S02")
        idx_b2 = text.find(block2_marker)

        assert 0 <= idx_h1 < idx_b1, "### S01 header must precede block1 content"
        assert 0 <= idx_h2 < idx_b2, "### S02 header must precede block2 content"
        # Header S01 must come before header S02
        assert idx_h1 < idx_h2, "### S01 must precede ### S02"
        # Block1 content must appear between the two headers
        assert idx_h1 < idx_b1 < idx_h2, "block1 must be between ### S01 and ### S02"

    # W2 — non-atomic action (link_to_moc) must not receive a ### header
    def test_non_atomic_action_gets_no_header(self):
        """A section with one create_atomic_note and one link_to_moc must emit exactly
        ONE ### header (for the atomic) and render the link_to_moc rendered_md WITHOUT
        a header prefix."""
        mod = _load_render_mod()
        link_rendered = "- **Link to MOC:** [[Some MOC]]\n"
        doc = _make_suggestions_doc([
            _make_section("S01", [
                _make_atomic_action("S01", "Alpha Note"),
                {
                    "kind": "link_to_moc",
                    "rendered_md": link_rendered,
                },
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)

        # Exactly one header — for the atomic only
        assert len(headers) == 1, (
            f"Expected 1 header (only for atomic), got {len(headers)}: {headers}"
        )
        assert "Alpha Note" in headers[0], (
            f"The single header must belong to the atomic, got: {headers[0]!r}"
        )

        # link_to_moc rendered_md must still appear in output
        text = "\n".join(lines)
        assert "Some MOC" in text, "link_to_moc rendered_md must appear in output"

        # No header line directly before the link_to_moc content
        for i, ln in enumerate(lines):
            if "Some MOC" in ln:
                if i > 0:
                    assert not _HEADER_RE.match(lines[i - 1]), (
                        f"Line before link_to_moc content must not be a ### header, "
                        f"got: {lines[i - 1]!r}"
                    )

    def test_header_uses_action_suggestion_id_not_section_id(self):
        """Header must use the action's suggestion_id, NOT the parent section's id.

        Guard: section id='S99', action suggestion_id='S01'.  A renderer that
        accidentally sources the ID from the section would emit '### S99 —';
        the correct renderer emits '### S01 —'.
        """
        mod = _load_render_mod()
        link_rendered = "- **Link to MOC:** [[Guard MOC]]\n"
        doc = _make_suggestions_doc([
            _make_section("S99", [
                _make_atomic_action("S01", "Guard Note"),
                {
                    "kind": "link_to_moc",
                    "rendered_md": link_rendered,
                },
            ])
        ])

        lines = mod.render_suggestions(doc)
        headers = _collect_headers(lines)
        text = "\n".join(lines)

        # Exactly one header — for the atomic action
        assert len(headers) == 1, (
            f"Expected 1 header, got {len(headers)}: {headers}"
        )
        # Header must use the ACTION's suggestion_id ("S01"), not the section id ("S99")
        assert headers[0].startswith("### S01 —"), (
            f"Header must start with '### S01 —' (action suggestion_id), "
            f"got: {headers[0]!r}"
        )
        assert "### S99" not in text, (
            "Section id 'S99' must NOT appear as a header — action suggestion_id takes precedence"
        )

        # link_to_moc rendered_md must still appear without a header prefix
        assert "Guard MOC" in text, "link_to_moc rendered_md must appear in output"
        for i, ln in enumerate(lines):
            if "Guard MOC" in ln:
                if i > 0:
                    assert not _HEADER_RE.match(lines[i - 1]), (
                        f"Line before link_to_moc content must not be a ### header, "
                        f"got: {lines[i - 1]!r}"
                    )
