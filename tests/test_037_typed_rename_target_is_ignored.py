#!/usr/bin/env python3
# version: 0.1.0
"""test_037_typed_rename_target_is_ignored.py — a rename target the owner types
into the suggestions markdown is silently discarded.

Owner decision 2026-09-29: *"Hashi soll das Ziel umbenennen können und wir
auch."* Both surfaces must let the owner name the file. Today **neither** does,
and the markdown's failure is the worse of the two because it accepts the
keystrokes and drops them.

**What happens today.** The markdown renders the computed name as part of a
checkbox label — `- [x] Rename to \\`…/karte (2).png\\`` — so it looks editable.
It is not. `_join_attachment_conflict_remedies` reads `proposed_name` from the
structured `suggestions-doc.json` and joins it on `source`; the rendered text is
never consulted for it (`suggestion-parser.py:~2370`). An owner who overtypes
the name gets the computed one, with nothing anywhere reporting the difference.

That is the same class as the four owner-facing sentences corrected on
2026-09-28/29 and as the wire-path loss Hashi reported on 2026-09-29: a surface
that offers something it does not honour. It is listed with them in
`docs/XDD/backlog.md`.

**Why this is not fixed here.** Honouring a typed name is not a parse change.
An arbitrary name needs sanitising to an Obsidian-safe filename, checking for
freeness against the same vault listing `_propose_asset_name` uses, and a
defined answer for when the typed name is itself taken — and the same value has
to reach Hashi's editor, which means the suggestions wire field that spec 038
owes anyway. It is one design, not two patches.

**To whoever fixes it:** the strict xfail below flips, and
`test_the_typed_name_is_discarded_today` goes with it — that one documents the
defect, not a contract.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "suggestion_parser_typed_rename", SCRIPTS_DIR / "suggestion-parser.py")
PARSER = importlib.util.module_from_spec(_spec)
sys.modules["suggestion_parser_typed_rename"] = PARSER
_spec.loader.exec_module(PARSER)

SOURCE = "100 Inbox/Scans/karte.png"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
COMPUTED = "karte (2).png"
TYPED = "karte-dresden-1938.png"

# What Pass 1 computed and wrote to the structured doc.
STRUCTURED_DOC = {
    "attachment_conflicts": [{
        "source": SOURCE,
        "destination": f"{ASSET_FOLDER}karte.png",
        "same_file": False,
        "owner_source_items": ["100 Inbox/Dresden.md"],
        "proposed_name": COMPUTED,
    }],
}


def _markdown(rename_target: str) -> str:
    return (
        "## Attachment Conflicts\n"
        "\n"
        f"### `{SOURCE}`\n"
        "\n"
        f"- **Destination:** `{ASSET_FOLDER}karte.png` (already occupied)\n"
        "\n"
        "**Remedy — choose one:**\n"
        f"- [x] Rename to `{ASSET_FOLDER}{rename_target}`\n"
        "- [ ] Keep in inbox\n"
        "- [ ] Ignore (send the move unchanged — if the name is still taken "
        "when you apply, the move fails and the attachment stays in the inbox)\n"
    )


def _proposed_name_for(rename_target: str) -> str | None:
    remedies = PARSER._join_attachment_conflict_remedies(
        PARSER.parse_attachment_conflict_remedies(_markdown(rename_target)),
        STRUCTURED_DOC,
    )
    assert len(remedies) == 1, remedies
    assert remedies[0]["remedy"] == "rename", remedies[0]
    return remedies[0]["proposed_name"]


def test_the_untouched_default_resolves_to_the_computed_name():
    """Baseline. The common case works and must keep working: an owner who
    leaves the pre-ticked default alone files under the name Pass 1 computed."""
    assert _proposed_name_for(COMPUTED) == COMPUTED


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Owner decision 2026-09-29: both Tomo's markdown and Hashi's editor "
        "must let the owner name the file. Today the markdown discards a typed "
        "name — `proposed_name` is read from the structured doc, never from the "
        "rendered text. Needs sanitisation, a freeness check and the spec 038 "
        "wire field, so it is one design rather than a parse tweak. Remove this "
        "marker when it lands."
    ),
)
def test_a_typed_rename_target_is_honoured():
    """**The behaviour the owner asked for**, stated as the assertion that will
    pass once it exists.

    Strict, so that whoever implements it is told to delete this marker rather
    than leaving a passing xfail nobody reads.
    """
    assert _proposed_name_for(TYPED) == TYPED


def test_the_typed_name_is_discarded_today():
    """Today's answer, recorded plainly — and it is the silence that makes this
    worth a test rather than a backlog line.

    The owner typed a name, the document accepted the keystrokes, and Pass 2
    uses a different one. Nothing in either document reports the substitution,
    so the owner has no way to learn that their input did not count.
    """
    assert _proposed_name_for(TYPED) == COMPUTED, (
        "if a typed name now survives, the defect is fixed and the xfail above "
        "should have flipped — delete this test with it"
    )
