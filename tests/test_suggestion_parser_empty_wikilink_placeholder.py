"""An empty wikilink is the document's way of saying "nothing here".

The suggestions document renders an unset Parent as a bare placeholder the
user is invited to fill in:

    - **Parent:** [[]]    ← change parent MOC if needed

`RE_WIKILINK` requires at least one character inside the brackets, so `[[]]`
does not match it and `_extract_wikilink` returns None. Every field that reads
`wl = _extract_wikilink(val)` and then falls back with `wl or val` therefore
keeps the literal string `"[[]]"` as if it were a real value.

Measured on the live 2026-09-15 run: MOC01 came out of the parser with
`parent_moc: "[[]]"`. instruction-render then tried to resolve that as a MOC
path, could not, and withheld the link with a message naming a remedy nobody
can follow — "MOC not found — create it" for a MOC with an empty name, while
the same instruction set creates the MOC the arrow points away from. Worse,
the placeholder reached the rendered note body, where the MOC template wrapped
it a second time: `> up:: [[[[]]]]`, which Hashi would have carried into the
Atlas verbatim.

`destination` and `template` share the exact fallback shape and are covered
here too — they are latent rather than observed, and a test is cheaper than
waiting for the document to render a placeholder into one of them.

The user leaving Parent empty is the ordinary case for a top-level MOC. It
must parse as "no parent", not as a parent named `[[]]`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "tomo" / "scripts" / "suggestion-parser.py"

_spec = importlib.util.spec_from_file_location("suggestion_parser_empty_wl", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


# The block exactly as the live document rendered it, arrow hint included.
LIVE_BLOCK = """## Proposed MOCs

### Proposed MOC: Kaimauern & Grundbau
- **Name:** Kaimauern & Grundbau (MOC)    ← edit this to rename the MOC before approving
- **Parent:** [[]]    ← change parent MOC if needed
- **Supporting notes:** Kai: Gründung entscheidet über Kosten, nicht Oberfläche
- **Why:** 1 note share topic Kaimauern & Grundbau and have no dedicated MOC.
- **Suggested tags:** topic/applied/engineering
- **Decision:**
  - [x] Approve (create this MOC with the Name above) ✅ 2026-09-15
"""


class TestTheLivePlaceholder:
    @staticmethod
    def _moc() -> dict:
        mocs = _mod.parse_proposed_mocs(LIVE_BLOCK)
        assert len(mocs) == 1, f"expected the approved MOC to parse, got {mocs!r}"
        return mocs[0]

    def test_parent_moc_is_empty_not_the_placeholder(self):
        """The observed defect: `parent_moc` came back as the literal `[[]]`."""
        parent = self._moc()["parent_moc"]
        assert not parent, (
            f"parent_moc is {parent!r} — an empty wikilink placeholder was kept "
            f"as a real parent value"
        )

    def test_parent_mocs_list_is_empty(self):
        """`[parent] if parent else []` puts the placeholder in the list too,
        and that list is what instruction-render iterates to emit link_to_moc."""
        assert self._moc()["parent_mocs"] == []

    def test_the_real_fields_still_parse(self):
        """The fix must not flatten the block — only the empty parent changes."""
        moc = self._moc()
        assert moc["title"] == "Kaimauern & Grundbau (MOC)"
        assert moc["tags"] == ["topic/applied/engineering"]
        assert moc["action"] == "create_moc"
        assert moc["approved"] is True


class TestARealParentStillBinds:
    def test_a_named_parent_survives(self):
        block = LIVE_BLOCK.replace(
            "- **Parent:** [[]]    ← change parent MOC if needed",
            "- **Parent:** [[Atlas/200 Maps/Engineering (MOC)]]    ← change parent MOC if needed",
        )
        moc = _mod.parse_proposed_mocs(block)[0]
        assert moc["parent_moc"] == "Atlas/200 Maps/Engineering (MOC)"
        assert moc["parent_mocs"] == ["Atlas/200 Maps/Engineering (MOC)"]

    def test_a_bare_path_without_brackets_survives(self):
        """Not every document writes the parent as a wikilink."""
        block = LIVE_BLOCK.replace(
            "- **Parent:** [[]]    ← change parent MOC if needed",
            "- **Parent:** Atlas/200 Maps/Engineering (MOC)",
        )
        assert _mod.parse_proposed_mocs(block)[0]["parent_moc"] == (
            "Atlas/200 Maps/Engineering (MOC)"
        )


@pytest.mark.parametrize("placeholder", ["[[]]", "[[ ]]", ""])
def test_every_empty_form_reads_as_absent(placeholder):
    """`[[ ]]` is what a user leaves behind after deleting the name by hand."""
    block = LIVE_BLOCK.replace(
        "- **Parent:** [[]]    ← change parent MOC if needed",
        f"- **Parent:** {placeholder}",
    )
    assert not _mod.parse_proposed_mocs(block)[0]["parent_moc"]


class TestTheSameShapeElsewhere:
    """`destination` and `template` fall back the same way.

    Latent, not observed — but the shape is identical, and a placeholder in
    either one would be written into a note's path or its template lookup.
    """

    @staticmethod
    def _section(field_line: str) -> dict:
        lines = [
            "### S01 — Test",
            "- **Source:** [[Test]]",
            "- **Suggested name:** Test",
            field_line,
            "- [x] Approve",
        ]
        return _mod.parse_section("S01", lines)

    def test_empty_destination_placeholder_is_not_a_path(self):
        dest = self._section("- **Destination:** [[]]")["destination"]
        assert dest != "[[]]", "an empty placeholder was kept as a destination path"

    def test_empty_template_placeholder_is_not_a_template(self):
        tpl = self._section("- **Template:** [[]]")["template"]
        assert tpl != "[[]]", "an empty placeholder was kept as a template name"

    def test_real_destination_and_template_survive(self):
        assert self._section("- **Destination:** Atlas/202 Notes/")["destination"] == (
            "Atlas/202 Notes/"
        )
        assert self._section("- **Template:** t_note_tomo")["template"] == "t_note_tomo"
