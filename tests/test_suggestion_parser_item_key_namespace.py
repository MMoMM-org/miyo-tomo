"""`item_keys_by_section_id` must key on the id the markdown heading shows.

The rendered markdown numbers its headings from a flat counter — that is the
action's `suggestion_id`. The suggestions-doc keeps its own `sections[].id`
from the reducer, which counts every section including ones the markdown never
renders as a heading. The two sequences therefore diverge as soon as anything
is skipped, and they share a namespace: both read `S01`, `S02`, `S03`.

Registering both into one flat lookup makes them collide. Measured on the live
2026-09-15 document, six of eleven ids resolved to None through the ambiguity
rule, and every confirmed item came out of the parser with `item_key: None`.

Pass 2 then reconstructed each source path from `inbox_path + stem`. That is
correct for a note at the inbox root and wrong for one in a subfolder, so the
run dropped S04 (`100 Inbox/Fotos/Kai.md`, probed as `100 Inbox/Kai.md`) and
with it a move_note, a move_asset, a link_to_moc and a delete_source. The
coverage audit caught it — 24 actions rendered against 27 expected.

The ambiguity rule itself is right and stays: a wrong key names a specific
wrong note, which is worse than no key at all. Without the cross-check in
`bind_section_item_key`, heading S04 (Kai) would have been handed the item_key
of the Elbsandstein migration plan.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "tomo" / "scripts" / "suggestion-parser.py"

_spec = importlib.util.spec_from_file_location("suggestion_parser_ns", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

lookup = _mod.item_keys_by_section_id


def _section(sid: str, key: str, stem: str, suggestion_id: str | None = None) -> dict:
    action = {"kind": "create_atomic_note"}
    if suggestion_id:
        action["suggestion_id"] = suggestion_id
    return {"id": sid, "item_key": key, "stem": stem, "actions": [action]}


class TestTheLiveCollision:
    """Reproduces the 2026-09-15 document's shape."""

    @staticmethod
    def _doc() -> dict:
        # Reducer ids skip S02/S06/S11 (sections the markdown renders no
        # heading for); the markdown renumbers contiguously, so from the
        # second entry on the two sequences are offset.
        return {"sections": [
            _section("S01", "100 Inbox/Bautzen.md", "Bautzen", "S01"),
            _section("S03", "100 Inbox/Dresden.md", "Dresden", "S02"),
            _section("S04", "100 Inbox/Elbsandstein.md", "Elbsandstein", "S03"),
            _section("S05", "100 Inbox/Fotos/Kai.md", "Kai", "S04"),
            _section("S07", "100 Inbox/Meissen.md", "Meissen", "S05"),
            _section("S08", "100 Inbox/Reise/Prager Burg.md", "Prager Burg", "S06"),
        ]}

    def test_every_heading_id_resolves(self):
        lk = lookup(self._doc())
        unresolved = [sid for sid in ("S01", "S02", "S03", "S04", "S05", "S06")
                      if lk.get(sid) is None]
        assert not unresolved, (
            f"heading ids {unresolved} did not resolve — the section-id "
            f"namespace is colliding with the suggestion_id namespace"
        )

    def test_the_subfolder_note_binds_to_its_real_path(self):
        """S04 is Kai, at `100 Inbox/Fotos/Kai.md`. Under the collision it
        resolved to None and Pass 2 probed `100 Inbox/Kai.md` instead."""
        assert lookup(self._doc())["S04"][0] == "100 Inbox/Fotos/Kai.md"

    def test_no_heading_id_resolves_to_another_sources_key(self):
        """The failure mode the ambiguity rule exists to prevent: heading S04
        is Kai, and the reducer's section S04 is the Elbsandstein plan."""
        lk = lookup(self._doc())
        for sid, expected_stem in [("S03", "Elbsandstein"), ("S04", "Kai"),
                                   ("S05", "Meissen"), ("S06", "Prager Burg")]:
            entry = lk.get(sid)
            assert entry is not None and entry[1] == expected_stem, (
                f"{sid} resolved to {entry!r}, expected the {expected_stem} source"
            )


class TestTheAmbiguityRuleStillHolds:
    def test_one_suggestion_id_on_two_sources_is_refused(self):
        """Genuine ambiguity — never guessed. This is the rule that kept the
        live run from filing Kai's note out of Elbsandstein's source."""
        doc = {"sections": [
            _section("S01", "100 Inbox/A.md", "A", "S01"),
            _section("S02", "100 Inbox/B.md", "B", "S01"),
        ]}
        assert lookup(doc)["S01"] is None

    def test_the_same_source_twice_is_not_ambiguous(self):
        """F-41: one source can produce several atomics, each its own heading.
        They share the source's key, so this must bind, not refuse."""
        doc = {"sections": [{
            "id": "S01", "item_key": "100 Inbox/A.md", "stem": "A",
            "actions": [
                {"kind": "create_atomic_note", "suggestion_id": "S01"},
                {"kind": "create_atomic_note", "suggestion_id": "S02"},
            ],
        }]}
        lk = lookup(doc)
        assert lk["S01"][0] == "100 Inbox/A.md"
        assert lk["S02"][0] == "100 Inbox/A.md"


class TestBackwardCompatibility:
    def test_a_section_without_suggestion_ids_falls_back_to_its_own_id(self):
        """Documents written before the flat counter carry no suggestion_id.
        Their heading shows the section id, so that must still resolve."""
        doc = {"sections": [_section("S01", "100 Inbox/A.md", "A")]}
        assert lookup(doc)["S01"][0] == "100 Inbox/A.md"

    def test_the_fallback_does_not_reintroduce_the_collision(self):
        """A mixed document: one legacy section and one modern. The legacy
        section's id must not poison a suggestion_id that happens to match."""
        doc = {"sections": [
            _section("S02", "100 Inbox/Legacy.md", "Legacy"),
            _section("S03", "100 Inbox/Modern.md", "Modern", "S02"),
        ]}
        lk = lookup(doc)
        # Both want "S02". The legacy fallback must not win over, nor collide
        # with, a heading id that a rendered document actually shows.
        assert lk.get("S02") is not None, "the real heading id was lost"
        assert lk["S02"][1] == "Modern"

    def test_sections_without_an_item_key_are_skipped(self):
        doc = {"sections": [{"id": "S01", "stem": "A", "actions": []}]}
        assert lookup(doc) == {}

    def test_empty_and_missing_input(self):
        assert lookup({}) == {}
        assert lookup({"sections": []}) == {}


@pytest.mark.parametrize("stem,parsed,should_bind", [
    ("Kai", "Kai", True),
    ("Kai", "Fotos/Kai", True),          # path-qualified link, spec 034 T5.1
    ("Kai", "Kai.md", True),
    ("Kai", "Someone else", False),       # user retyped the Source line
])
def test_bind_cross_checks_the_display_stem(stem, parsed, should_bind):
    """The guard that made the live failure safe instead of catastrophic."""
    item = {"id": "S04", "source_path": parsed}
    _mod.bind_section_item_key(item, {"S04": ("100 Inbox/Fotos/Kai.md", stem)})
    assert ("item_key" in item) is should_bind
