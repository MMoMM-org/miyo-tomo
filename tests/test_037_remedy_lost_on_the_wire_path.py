#!/usr/bin/env python3
# version: 0.1.0
"""test_037_remedy_lost_on_the_wire_path.py — the attachment-conflict remedy
does not survive Pass 2's JSON-only path, and silently becomes `ignore`.

Reported by Hashi on 2026-09-29, after spec 037 shipped, and reproduced here
against Tomo's own code rather than accepted on their analysis.

**The chain, every link verifiable in this repo:**

1. `tomo/schemas/suggestions-wire.schema.json` carries no attachment-conflict
   field of any kind. Its own top-level description states the invariant that
   makes this a defect rather than an omission: *"every editable decision the
   markdown offers is carried here."* Spec 037 added an editable decision to
   the markdown and did not carry it there.
2. `suggestion-parser.py:492` — `build_from_wire` hardcodes
   `"attachment_conflict_remedies": []`. The comment beside it states the
   premise correctly ("the ADR-026 wire carries no Attachment-Conflicts data at
   all") and stops there; the consequence was never traced.
3. ADR-026 precedence: when `emit_digest` no longer matches, Pass 2 rebuilds
   its entire output from the wire and never re-reads the markdown
   (`suggestion-parser.py:~2489`). So an edited wire takes path 2.
4. `_build_move_asset_actions` treats a source absent from the remedies list as
   a plain attachment — its own docstring says "same as `ignore`".

So a user who ticks **Rename** and then does anything that edits the wire gets
**Ignore**: the move goes out against the occupied destination, Hashi refuses
it, and the owning note is filed and its source deleted regardless.

**Why spec 037's suite could not see this.** The wire path was tested only for
CONFLICT-FREE runs, asserting byte-identical output against a pre-change golden
(`test_037_t3_0_remedy_transport.py::
test_conflict_free_run_output_is_byte_identical_to_pre_change_literal`). A
conflict run through the wire is not expressible, because the field does not
exist — so the one case that loses data is the one case no fixture could build.
The hardcoded `[]` was even deliberately proven load-bearing for golden parity,
which is true and was the wrong question.

**Trigger is not Hashi-specific.** Their editor's save is one way to change the
wire; the rule is any `emit_digest` mismatch.

**To whoever fixes this: three tests here change together, by design.** Measured
2026-09-29 by simulating the fix (making `build_from_wire` carry the remedy):
the suite goes from `4 passed, 1 xfailed` to `3 failed`. That is the strict
xfail flipping plus the two tests that deliberately record today's wrong answer
(`test_the_wire_path_returns_an_empty_list_today` and
`test_losing_the_remedy_silently_produces_the_ignore_outcome`). They are
documentation of a defect, not of a contract — delete them with the marker. The
two baseline tests above them stay.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _build_move_asset_actions  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "suggestion_parser_wire_loss", SCRIPTS_DIR / "suggestion-parser.py")
PARSER = importlib.util.module_from_spec(_spec)
sys.modules["suggestion_parser_wire_loss"] = PARSER
_spec.loader.exec_module(PARSER)

INBOX = "100 Inbox/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
SOURCE = "100 Inbox/Scans/karte.png"
OCCUPIED = f"{ASSET_FOLDER}karte.png"
RENAMED = f"{ASSET_FOLDER}karte (2).png"

MARKDOWN = (
    "## Attachment Conflicts\n"
    "\n"
    f"### `{SOURCE}`\n"
    "\n"
    f"- **Destination:** `{OCCUPIED}` (already occupied)\n"
    "- **File comparison:** A different file already holds this name.\n"
    "\n"
    "**Remedy — choose one:**\n"
    f"- [x] Rename to `{RENAMED}`\n"
    "- [ ] Keep in inbox\n"
    "- [ ] Ignore (send the move unchanged — if the name is still taken when "
    "you apply, the move fails and the attachment stays in the inbox)\n"
)

# The structured suggestions-doc.json the markdown path joins against. This is
# the ONLY channel carrying the conflict; the wire below is its counterpart and
# has nowhere to put it.
STRUCTURED_DOC = {
    "attachment_conflicts": [{
        "source": SOURCE,
        "destination": OCCUPIED,
        "same_file": False,
        "owner_source_items": ["100 Inbox/Dresden.md"],
        "proposed_name": "karte (2).png",
    }],
}

# An edited wire for the SAME run. Shaped after the real thing
# (`suggestions-wire.schema.json`) — which is exactly why it carries no
# conflict: there is no field for one.
WIRE = {"suggestions": [], "daily_updates": []}


def _remedies_via_markdown():
    return PARSER._join_attachment_conflict_remedies(
        PARSER.parse_attachment_conflict_remedies(MARKDOWN), STRUCTURED_DOC
    )


def _remedies_via_wire():
    return PARSER.build_from_wire(WIRE, "")["attachment_conflict_remedies"]


def _move_destination(remedies):
    """The destination Pass 2 would actually emit for this attachment."""
    manifest = [{
        "id": "S01", "action": None, "title": "Dresden",
        "source_path": "Dresden.md", "rendered_file": "2026-01-01_dresden.md",
        "destination": "Atlas/202 Notes/", "parent_moc": "", "parent_mocs": [],
        "tags": [], "attachments": [SOURCE],
    }]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0],
        attachment_conflict_remedies=remedies,
    )
    moves = [a for a in actions if a["action"] == "move_asset"]
    return (moves[0]["destination"] if moves else None), skipped


# ---------------------------------------------------------------------------
# 1. Baseline — the fixture is real, and the markdown path works
# ---------------------------------------------------------------------------

def test_the_markdown_path_carries_the_chosen_remedy():
    """Passes today. Here so that the failure below cannot be dismissed as a
    malformed fixture: the same document, read the way Pass 2 normally reads
    it, yields the owner's choice."""
    assert _remedies_via_markdown() == [
        {"source": SOURCE, "remedy": "rename", "proposed_name": "karte (2).png"},
    ]


def test_the_markdown_path_files_the_attachment_under_the_free_name():
    """And that choice reaches the emitted action."""
    destination, skipped = _move_destination(_remedies_via_markdown())
    assert destination == RENAMED, destination
    assert skipped == [], skipped


# ---------------------------------------------------------------------------
# 2. The defect
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=True,
    reason=(
        "spec 037's remedy is not carried on the suggestions wire, so the "
        "ADR-026 JSON-only path returns [] and the owner's choice is lost. "
        "Reported by Hashi 2026-09-29; fix requires a wire field, which is a "
        "consumer-coordinated change. Remove this marker when it lands."
    ),
)
def test_the_wire_path_carries_the_chosen_remedy_too():
    """**This is the defect, stated as the behaviour we want.**

    Marked `xfail(strict=True)` rather than asserting today's wrong answer: a
    test that pins the defect would go green forever and tell no one. Strict
    means pytest FAILS if it ever passes, so whoever adds the wire field is
    told to delete this marker.
    """
    assert _remedies_via_wire() == _remedies_via_markdown()


def test_the_wire_path_returns_an_empty_list_today():
    """The current answer, recorded plainly so the xfail above is not the only
    evidence and a reader need not run it to know what happens."""
    assert _remedies_via_wire() == []


# ---------------------------------------------------------------------------
# 3. The consequence — an empty list is not neutral, it is `ignore`
# ---------------------------------------------------------------------------

def test_losing_the_remedy_silently_produces_the_ignore_outcome():
    """The part that makes this data loss rather than a missing feature.

    An empty remedies list is not "no decision" — `_build_move_asset_actions`
    treats an absent source as a plain attachment, which is byte-for-byte the
    `ignore` outcome: the move goes out against the destination Pass 1 already
    found occupied. Hashi then refuses it, while the owning note is filed and
    its source deleted regardless.

    So the owner ticks the one remedy that files the attachment safely, and
    Pass 2 emits the one that cannot.
    """
    chosen, _ = _move_destination(_remedies_via_markdown())
    lost, lost_skipped = _move_destination(_remedies_via_wire())

    assert chosen == RENAMED
    assert lost == OCCUPIED, (
        "if this is no longer the occupied destination the defect has changed "
        f"shape and this file needs rereading: {lost}"
    )
    assert lost != chosen

    explicit_ignore, _ = _move_destination(
        [{"source": SOURCE, "remedy": "ignore", "proposed_name": None}]
    )
    assert lost == explicit_ignore, (
        "a lost remedy must be indistinguishable from an explicit ignore — "
        "that indistinguishability is why nothing reports a problem"
    )
    assert lost_skipped == [], (
        "and nothing is recorded as skipped, so no report names it either"
    )
