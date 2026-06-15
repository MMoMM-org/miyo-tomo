#!/usr/bin/env python3
# version: 0.3.0
"""test_suggestions_reducer_t6_1_placement.py — spec 022 T6.1.

Covers AC-11 / AC-12: **Placement:** line per candidate-MOC link in the
suggestions doc.

  AC-11 — never a bare [[Target#]] in the suggestions doc
  AC-12 — every anchor → exactly one **Placement:** line with ← edit hint

Fixture shapes are mirrored from the real candidate_mocs / anchor schema
(item-result.schema.json §candidate_mocs[].anchor) and the make_atomic_action
factory in test_suggestions_reducer_n_blocks.py — NOT hand-invented markdown.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

render_create_atomic_note = _mod.render_create_atomic_note  # type: ignore[attr-defined]
render_link_to_moc = _mod.render_link_to_moc  # type: ignore[attr-defined]
moc_link_line = _mod.moc_link_line  # type: ignore[attr-defined]


# ── Factories ─────────────────────────────────────────────────────────────────

def make_moc(path: str, *, score: float = 0.8, pre_check: bool = True,
             anchor: dict | None = None) -> dict:
    """Build a candidate_moc dict mirroring the schema shape."""
    moc: dict = {"path": path, "score": score, "pre_check": pre_check}
    if anchor is not None:
        moc["anchor"] = anchor
    return moc


def make_action(*, mocs: list[dict]) -> dict:
    """Build a minimal create_atomic_note action with the given candidate_mocs."""
    return {
        "kind": "create_atomic_note",
        "suggested_title": "Some Note",
        "atomic_note_worthiness": 0.8,
        "template": "t_note_tomo",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": mocs,
        "needs_new_moc": False,
        "tags_to_add": [],
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "alternatives": [],
    }


# ── moc_link_line unit tests ───────────────────────────────────────────────────

class TestMocLinkLinePlacementFormats:
    """One **Placement:** line per candidate-MOC, anchored to the four formats."""

    def test_heading_anchor_emits_under_heading(self):
        """type:heading, new_section null → '**Placement:** under `## <value>`'"""
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "heading",
            "value": "Frameworks and Methodologies",
            "placement": "inside",
            "new_section": None,
        })
        lines = moc_link_line(moc).split("\n")
        placement = next((l for l in lines if l.startswith("**Placement:**")), None)
        assert placement is not None, "Expected a **Placement:** line"
        assert placement == "**Placement:** under `## Frameworks and Methodologies`    ← edit the heading to move the link"

    def test_callout_new_section_emits_new_section_format(self):
        """type:callout, new_section set → '**Placement:** new section `## <new_section>` ...'"""
        moc = make_moc("Atlas/200 Maps/Tools MOC.md", anchor={
            "type": "callout",
            "value": "[!blocks] Key Concepts",
            "placement": "after",
            "new_section": "Agile Methods",
        })
        lines = moc_link_line(moc).split("\n")
        placement = next((l for l in lines if l.startswith("**Placement:**")), None)
        assert placement is not None, "Expected a **Placement:** line"
        assert placement == "**Placement:** new section `## Agile Methods` (created before the footer)    ← rename or change"

    def test_callout_no_new_section_emits_inside_callout(self):
        """type:callout, new_section null → 'inside the `> [!<name>]` callout'"""
        moc = make_moc("Atlas/200 Maps/Tools MOC.md", anchor={
            "type": "callout",
            "value": "[!blocks] Key Concepts",
            "placement": "inside",
            "new_section": None,
        })
        lines = moc_link_line(moc).split("\n")
        placement = next((l for l in lines if l.startswith("**Placement:**")), None)
        assert placement is not None, "Expected a **Placement:** line"
        assert placement == "**Placement:** inside the `> [!blocks]` callout    ← change to a `## Heading` to place under a section"

    def test_line_anchor_emits_under_note_title(self):
        """type:line → 'under the note title (no matching section or callout found)'"""
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "line",
            "value": "some line text",
            "placement": "after",
            "new_section": None,
        })
        lines = moc_link_line(moc).split("\n")
        placement = next((l for l in lines if l.startswith("**Placement:**")), None)
        assert placement is not None, "Expected a **Placement:** line"
        assert placement == "**Placement:** under the note title (no matching section or callout found)    ← add a `## Heading` to target a section"

    def test_absent_anchor_emits_no_placement_line(self):
        """anchor absent → no **Placement:** line (graceful back-compat)."""
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md")
        output = moc_link_line(moc)
        assert "**Placement:**" not in output

    def test_null_anchor_emits_no_placement_line(self):
        """anchor=None → no **Placement:** line."""
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor=None)
        output = moc_link_line(moc)
        assert "**Placement:**" not in output

    def test_checkbox_line_still_present_with_anchor(self):
        """The existing '- [x] [[link]]' line is preserved when anchor is present."""
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "heading",
            "value": "Core Topics",
            "placement": "inside",
            "new_section": None,
        })
        lines = moc_link_line(moc).split("\n")
        checkbox = next((l for l in lines if l.startswith("- [x]") or l.startswith("- [ ]")), None)
        assert checkbox is not None, "Checkbox line must remain"
        assert "[[Atlas/200 Maps/Philosophy MOC]]" in checkbox

    def test_placement_line_follows_checkbox(self):
        """**Placement:** appears right after the checkbox line."""
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "heading",
            "value": "Core Topics",
            "placement": "inside",
            "new_section": None,
        })
        lines = moc_link_line(moc).split("\n")
        cb_idx = next(i for i, l in enumerate(lines) if l.startswith("- ["))
        pl_idx = next((i for i, l in enumerate(lines) if l.startswith("**Placement:**")), None)
        assert pl_idx is not None
        assert pl_idx == cb_idx + 1, "Placement must immediately follow the checkbox line"

    def test_left_arrow_hint_present_in_all_anchor_types(self):
        """Every placement format contains the ← edit hint."""
        anchors = [
            {"type": "heading", "value": "Section", "placement": "inside", "new_section": None},
            {"type": "callout", "value": "[!blocks] X", "placement": "after", "new_section": "New"},
            {"type": "callout", "value": "[!blocks] X", "placement": "inside", "new_section": None},
            {"type": "line", "value": "any", "placement": "after", "new_section": None},
        ]
        for anchor in anchors:
            moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor=anchor)
            lines = moc_link_line(moc).split("\n")
            placement = next((l for l in lines if l.startswith("**Placement:**")), None)
            assert placement is not None
            assert "←" in placement, f"Missing ← in placement for anchor type={anchor['type']}"

    def test_heading_anchor_null_value_falls_back_to_line_tier(self):
        """type:heading, value:null → line-tier fallback; no empty `## ` in output.

        The schema allows value:null (unresolved LLM output). An empty heading
        text would produce '**Placement:** under `## `' — unusable for the user.
        Guard ensures the line-tier format is emitted instead.
        """
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "heading",
            "value": None,
            "placement": "inside",
            "new_section": None,
        })
        output = moc_link_line(moc)
        assert "## `" not in output, f"Empty heading must not appear: {output!r}"
        assert "**Placement:** under the note title" in output

    def test_callout_anchor_null_value_no_new_section_falls_back_to_line_tier(self):
        """type:callout, value:null, new_section:null → line-tier fallback; no empty callout.

        Without new_section the callout-name branch needs value to build `> [!name]`.
        A null value would produce `` inside the `` callout `` — empty backticks.
        Guard falls back to line-tier instead.
        """
        moc = make_moc("Atlas/200 Maps/Tools MOC.md", anchor={
            "type": "callout",
            "value": None,
            "placement": "inside",
            "new_section": None,
        })
        output = moc_link_line(moc)
        assert "inside the ``" not in output, f"Empty callout ref must not appear: {output!r}"
        assert "**Placement:** under the note title" in output

    def test_callout_truncated_value_no_closing_bracket_falls_back_to_line_tier(self):
        """type:callout, value lacks closing ']' (truncated LLM output) → line-tier fallback.

        '[!blocks' (no ']') would produce garbled '> [!blocks' callout ref via
        split("]")[0] yielding the whole string. Guard returns line-tier instead.
        """
        moc = make_moc("Atlas/200 Maps/Tools MOC.md", anchor={
            "type": "callout",
            "value": "[!blocks",
            "placement": "inside",
            "new_section": None,
        })
        output = moc_link_line(moc)
        assert "> [!blocks" not in output, f"Garbled callout ref must not appear: {output!r}"
        assert "**Placement:** under the note title" in output

    # ── T6.2 alt_headings advisory ────────────────────────────────────────────

    def test_alt_headings_present_emits_advisory_line(self):
        """anchor with non-empty alt_headings → exactly one **Other sections in this MOC:** advisory line."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": ["Routines", "Morning Practice"],
        })
        output = moc_link_line(moc)
        assert "**Other sections in this MOC:**" in output

    def test_alt_headings_advisory_contains_runner_up_as_heading(self):
        """Advisory renders runner-up heading(s) as `## <heading>` in backticks."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": ["Routines"],
        })
        output = moc_link_line(moc)
        assert "`## Routines`" in output

    def test_alt_headings_multiple_runner_ups_all_in_advisory(self):
        """Multiple runner-ups all appear in the advisory line, comma-joined."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": ["Routines", "Morning Practice"],
        })
        output = moc_link_line(moc)
        assert "`## Routines`" in output
        assert "`## Morning Practice`" in output

    def test_alt_headings_advisory_has_retarget_hint(self):
        """Advisory contains the ← edit hint pointing user to change Placement."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": ["Routines"],
        })
        output = moc_link_line(moc)
        assert "← edit the Placement above to retarget" in output

    def test_alt_headings_advisory_follows_placement_line(self):
        """Advisory appears AFTER the **Placement:** line (never before it)."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": ["Routines"],
        })
        lines = moc_link_line(moc).split("\n")
        pl_idx = next((i for i, l in enumerate(lines) if l.startswith("**Placement:**")), None)
        adv_idx = next((i for i, l in enumerate(lines) if l.startswith("**Other sections")), None)
        assert pl_idx is not None, "Placement line must exist"
        assert adv_idx is not None, "Advisory line must exist"
        assert adv_idx > pl_idx, "Advisory must follow Placement line"

    def test_absent_alt_headings_no_advisory(self):
        """anchor without alt_headings → no advisory line (most MOCs, no ambiguous fit)."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
        })
        output = moc_link_line(moc)
        assert "**Other sections in this MOC:**" not in output

    def test_null_alt_headings_no_advisory(self):
        """anchor.alt_headings=None → no advisory line."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": None,
        })
        output = moc_link_line(moc)
        assert "**Other sections in this MOC:**" not in output

    def test_empty_alt_headings_no_advisory(self):
        """anchor.alt_headings=[] → no advisory line."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": [],
        })
        output = moc_link_line(moc)
        assert "**Other sections in this MOC:**" not in output

    def test_advisory_does_not_key_off_raw_heading_count(self):
        """Advisory is driven by alt_headings field ONLY — not by a raw count of MOC headings.

        A MOC with many headings but no alt_headings must NOT trigger the advisory.
        Only the explicit alt_headings field drives it (most MOCs have ≥2 headings;
        triggering on count would flood the doc).
        """
        # This MOC has a heading anchor but no alt_headings — should NOT emit advisory
        # even though a real MOC would typically have multiple headings in its inventory.
        moc = make_moc("Atlas/200 Maps/Systems Thinking MOC.md", anchor={
            "type": "heading",
            "value": "Mental Models",
            "placement": "after",
            "new_section": None,
            # alt_headings intentionally absent — unambiguous fit
        })
        output = moc_link_line(moc)
        assert "**Other sections in this MOC:**" not in output

    def test_alt_headings_empty_string_item_filtered_out(self):
        """alt_headings with empty-string item → blank heading filtered; valid runner-up still appears."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": ["", "Routines"],
        })
        output = moc_link_line(moc)
        # Blank `## ` must NOT appear
        assert "`## `" not in output, f"Blank backtick-heading must be filtered: {output!r}"
        # Valid runner-up still renders
        assert "`## Routines`" in output
        assert "**Other sections in this MOC:**" in output

    def test_alt_headings_only_empty_strings_emits_no_advisory(self):
        """alt_headings containing only empty strings → no advisory line after filtering."""
        moc = make_moc("Atlas/200 Maps/Health MOC.md", anchor={
            "type": "heading",
            "value": "Habits",
            "placement": "after",
            "new_section": None,
            "alt_headings": [""],
        })
        output = moc_link_line(moc)
        assert "**Other sections in this MOC:**" not in output

    def test_unknown_anchor_type_falls_back_to_line_tier(self):
        """Unknown anchor type (e.g. future schema extension) falls through to line-tier.

        Pins the existing fallthrough: a type not in the current enum set must
        never raise and must produce a valid, user-readable placement hint.
        """
        moc = make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "section",
            "value": "x",
            "placement": "after",
            "new_section": None,
        })
        output = moc_link_line(moc)
        assert "**Placement:** under the note title (no matching section or callout found)" in output
        assert "←" in output


# ── Integration: render_create_atomic_note with anchors ──────────────────────

class TestRenderCreateAtomicNotePlacement:
    """Placement lines appear in the full render_create_atomic_note output."""

    def test_one_moc_with_heading_anchor_in_full_render(self):
        """Full render contains the placement line for a heading anchor."""
        action = make_action(mocs=[make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "heading",
            "value": "Frameworks and Methodologies",
            "placement": "inside",
            "new_section": None,
        })])
        md = render_create_atomic_note(action, "source-note")
        assert "**Placement:** under `## Frameworks and Methodologies`    ← edit the heading to move the link" in md

    def test_no_bare_hash_anchor_in_full_render(self):
        """No bare [[Target#]] pattern in the rendered output (AC-11)."""
        action = make_action(mocs=[make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
            "type": "heading",
            "value": "Frameworks and Methodologies",
            "placement": "inside",
            "new_section": None,
        })])
        md = render_create_atomic_note(action, "source-note")
        # AC-11: bare [[Target#]] or [[Target#]] pattern must not appear
        assert not re.search(r"\[\[[^\]]*#[^\]]*\]\]", md), (
            f"Found bare [[Target#]] anchor in rendered output (AC-11 violation):\n{md}"
        )

    def test_two_mocs_two_placement_lines(self):
        """Two candidate_mocs → two **Placement:** lines in the output."""
        action = make_action(mocs=[
            make_moc("Atlas/200 Maps/Philosophy MOC.md", anchor={
                "type": "heading", "value": "Core Topics", "placement": "inside", "new_section": None,
            }),
            make_moc("Atlas/200 Maps/Epistemology MOC.md", anchor={
                "type": "line", "value": "any", "placement": "after", "new_section": None,
            }),
        ])
        md = render_create_atomic_note(action, "source-note")
        assert md.count("**Placement:**") == 2

    def test_moc_without_anchor_no_placement_line(self):
        """candidate_moc without anchor key → no **Placement:** line (back-compat)."""
        action = make_action(mocs=[make_moc("Atlas/200 Maps/Philosophy MOC.md")])
        md = render_create_atomic_note(action, "source-note")
        assert "**Placement:**" not in md


# ── render_link_to_moc AC-11 reconciliation ───────────────────────────────────

class TestRenderLinkToMocAC11:
    """render_link_to_moc must never emit a bare [[Target#section]] (AC-11)."""

    def test_no_bare_hash_anchor_in_link_to_moc_empty_section(self):
        """Empty section_name → no [[Target#]] in output."""
        action = {"kind": "link_to_moc", "target_moc": "Philosophy MOC", "section_name": ""}
        md = render_link_to_moc(action, "source-note")
        assert "[[Philosophy MOC#]]" not in md, (
            f"Bare [[Target#]] must not appear (AC-11):\n{md}"
        )

    def test_no_bare_hash_anchor_in_link_to_moc_with_section(self):
        """section_name present → no [[Target#Section]] bare wikilink (AC-11)."""
        action = {"kind": "link_to_moc", "target_moc": "Philosophy MOC", "section_name": "Core Topics"}
        md = render_link_to_moc(action, "source-note")
        assert not re.search(r"\[\[[^\]]*#[^\]]*\]\]", md), (
            f"Bare [[Target#]] wikilink must not appear (AC-11):\n{md}"
        )

    def test_link_to_moc_contains_source(self):
        """Source wikilink still present in render_link_to_moc output."""
        action = {"kind": "link_to_moc", "target_moc": "Philosophy MOC", "section_name": ""}
        md = render_link_to_moc(action, "source-note")
        assert "[[source-note]]" in md

    def test_link_to_moc_contains_target(self):
        """Target MOC name still visible in render_link_to_moc output."""
        action = {"kind": "link_to_moc", "target_moc": "Philosophy MOC", "section_name": "Core Topics"}
        md = render_link_to_moc(action, "source-note")
        assert "Philosophy MOC" in md
