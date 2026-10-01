#!/usr/bin/env python3
# version: 0.2.0
"""test_037_remedy_lost_on_the_wire_path.py — the attachment-conflict remedy
did not survive Pass 2's JSON-only path, and silently became `ignore`.
**Fixed by spec 038 T2.3** — see the bottom of this docstring.

Reported by Hashi on 2026-09-29, after spec 037 shipped, and reproduced here
against Tomo's own code rather than accepted on their analysis.

**The chain, every link verifiable in this repo at the time:**

1. `tomo/schemas/suggestions-wire.schema.json` carried no attachment-conflict
   field of any kind. Its own top-level description states the invariant that
   makes this a defect rather than an omission: *"every editable decision the
   markdown offers is carried here."* Spec 037 added an editable decision to
   the markdown and did not carry it there.
2. `suggestion-parser.py:492` — `build_from_wire` hardcoded
   `"attachment_conflict_remedies": []`. The comment beside it stated the
   premise correctly ("the ADR-026 wire carries no Attachment-Conflicts data at
   all") and stopped there; the consequence was never traced.
3. ADR-026 precedence: when `emit_digest` no longer matches, Pass 2 rebuilds
   its entire output from the wire and never re-reads the markdown
   (`suggestion-parser.py:~2489`). So an edited wire took path 2.
4. `_build_move_asset_actions` treats a source absent from the remedies list as
   a plain attachment — its own docstring says "same as `ignore`".

So a user who ticked **Rename** and then did anything that edited the wire got
**Ignore**: the move went out against the occupied destination, Hashi refused
it, and the owning note was filed and its source deleted regardless.

**Why spec 037's suite could not see this.** The wire path was tested only for
CONFLICT-FREE runs, asserting byte-identical output against a pre-change golden
(`test_037_t3_0_remedy_transport.py::
test_conflict_free_run_output_is_byte_identical_to_pre_change_literal`). A
conflict run through the wire was not expressible, because the field did not
exist — so the one case that lost data was the one case no fixture could build.
The hardcoded `[]` was even deliberately proven load-bearing for golden parity,
which was true and was the wrong question.

**Trigger was not Hashi-specific.** Their editor's save is one way to change
the wire; the rule is any `emit_digest` mismatch.

**The fix (spec 038 T2.2/T2.3).** The wire gained a top-level
`attachment_conflicts[]` array (T2.2), and `build_from_wire` now projects it
into the same `{source, remedy, proposed_name}` triple the markdown path
yields, instead of hardcoding `[]` (T2.3). Two tests here changed together,
by design: the strict xfail (`test_the_wire_path_carries_the_chosen_remedy_
too`) now asserts the fixed behaviour directly, and the marker is removed;
`test_the_wire_path_returns_an_empty_list_today` and
`test_losing_the_remedy_silently_produces_the_ignore_outcome` — which recorded
the defect's wrong answer — are deleted outright. The second's closing two
assertions (an *explicit* `ignore` leaving the move at the occupied
destination) pin behaviour that survives this fix, but need no rehoming:
`tests/test_037_t3_1_remedy_outcomes.py::
test_ignore_emits_the_move_unchanged_and_skips_nothing` already pins it, more
strongly (it also asserts `len(actions)` and the action's `source`), and has
done so since spec 037 shipped — look there for `ignore`'s coverage.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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

# The SAME run's wire, carrying the owner's chosen remedy in
# `attachment_conflicts[]` (spec 038 T2.2/T2.3) — `destination`/`same_file`
# are wire-only display context `build_from_wire` does not project.
WIRE = {
    "suggestions": [],
    "daily_updates": [],
    "attachment_conflicts": [{
        "source": SOURCE,
        "destination": OCCUPIED,
        "same_file": False,
        "remedy": "rename",
        "proposed_name": "karte (2).png",
    }],
}


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
    it, yields the owner's choice.

    `name_is_owner_supplied: False` (spec 038 T3.2) joins in alongside the
    rest — the name here comes from the structured doc, never the rendered
    text."""
    assert _remedies_via_markdown() == [
        {
            "source": SOURCE, "remedy": "rename",
            "proposed_name": "karte (2).png",
            "name_is_owner_supplied": False,
        },
    ]


def test_the_markdown_path_files_the_attachment_under_the_free_name():
    """And that choice reaches the emitted action."""
    destination, skipped = _move_destination(_remedies_via_markdown())
    assert destination == RENAMED, destination
    assert skipped == [], skipped


# ---------------------------------------------------------------------------
# 2. The fix holds
# ---------------------------------------------------------------------------

def test_the_wire_path_carries_the_chosen_remedy_too():
    """**This was the defect, now fixed (spec 038 T2.3).** The wire's
    `attachment_conflicts[]` (T2.2) carries the owner's remedy, and
    `build_from_wire` now projects it to the same triple the markdown path
    yields, instead of hardcoding `[]`.

    Was `xfail(strict=True)` rather than an assertion of the then-current
    wrong answer: a test pinning the defect would have gone green forever and
    told no one. Strict meant pytest would FAIL if it ever passed — which is
    exactly what happened when the wire field landed, telling whoever added
    it to remove the marker, as this task does.

    spec 038 T3.2 adds one field the two paths do NOT share:
    `name_is_owner_supplied` — True on the wire (an editor could have
    changed `proposed_name` and this path cannot tell), False on the
    markdown (the name comes from the structured doc, never the rendered
    text). So the two triples are compared with that field stripped, and
    each path's value for it is asserted separately.
    """
    via_wire = _remedies_via_wire()
    via_markdown = _remedies_via_markdown()

    def _without_flag(records):
        return [
            {k: v for k, v in r.items() if k != "name_is_owner_supplied"}
            for r in records
        ]

    assert _without_flag(via_wire) == _without_flag(via_markdown)
    assert all(r["name_is_owner_supplied"] is True for r in via_wire)
    assert all(r["name_is_owner_supplied"] is False for r in via_markdown)
