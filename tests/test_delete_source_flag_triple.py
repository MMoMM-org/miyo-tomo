#!/usr/bin/env python3
# version: 0.1.0
"""test_delete_source_flag_triple.py — which `(decision, keep_source,
delete_source)` combinations Pass 2 actually honours.

Written to answer a question Hashi asked on 2026-09-29, blocking their issue
#140 (a "Delete source" control in their suggestions editor). They declined to
build the control from the field names:

> *"That is an inference from field names, not from your Pass-2 logic, and we
> are not shipping a control on it. We have coupled two wire fields on a
> plausible reading before and got it wrong twice in a row."*

Fair, and the same standard we applied to their remedy report — so the answer
they get is measured here rather than read off the source. Every row of the
table in the reply handoff is one assertion below.

**What the measurement shows.**

| `decision` | `keep_source` | `delete_source` | origin note |
|---|---|---|---|
| approve | false | false | **deleted** — paired with the `move_note` (site 3) |
| approve | false | **true**  | **deleted** — identical; the flag changes nothing |
| approve | true  | false | kept |
| approve | true  | **true**  | **kept** — `keep_source` wins |
| skip    | false | false | kept (no action at all) |
| skip    | false | **true**  | **deleted** — site 1, the explicit user delete |
| skip    | **true** | **true** | **deleted** — `keep_source` is never consulted here |

So Hashi's inference was right: `delete_source` is the **skip** leg of the
tri-state, and it is inert under `approve`. Two consequences they need and did
not ask for:

1. **`(skip, keep_source=true, delete_source=true)` is the contradictory pair,
   and it deletes.** `build_from_wire` drops `keep_source` when it builds a
   skipped entry (`suggestion-parser.py:~400`) — the field never reaches the
   builder, so there is nothing for it to lose to. A control that can set both
   would be offering the owner a "keep" that does not keep.
2. **The two Pass-2 paths normalise `delete_source` differently.** The markdown
   parser forces it to `False` on an approved item (`suggestion-parser.py:932`,
   *"If Accept is checked, Delete is irrelevant"*); `build_from_wire` copies it
   through unchanged. Inert today only because no consumer reads a confirmed
   item's copy of the flag — `_build_delete_source_actions` reads
   `skipped[].disposition` and `confirmed[].keep_source`, never
   `confirmed[].delete_source`. The wire can therefore hold a state the
   markdown cannot express, and the invariant holds on one path only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _build_delete_source_actions  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "suggestion_parser_flag_triple", SCRIPTS_DIR / "suggestion-parser.py")
PARSER = importlib.util.module_from_spec(_spec)
sys.modules["suggestion_parser_flag_triple"] = PARSER
_spec.loader.exec_module(PARSER)

INBOX = "100 Inbox/"
ORIGIN = "100 Inbox/Dresden.md"
STEM = "Dresden"


def _wire(decision: str, keep_source: bool, delete_source: bool) -> dict:
    """One suggestion, shaped after `suggestions-wire.schema.json`'s required
    set. This is the document Hashi's editor writes."""
    return {
        "suggestions": [{
            "id": "S01",
            "stem": STEM,
            "item_key": ORIGIN,
            "title": "Dresden",
            "template": "t_note_tomo",
            "location": "Atlas/202 Notes/",
            "tags": [],
            "decision": decision,
            "keep_source": keep_source,
            "delete_source": delete_source,
            "force_atomic": False,
            "suppressed": False,
            "candidate_mocs": [],
        }],
        "daily_updates": [],
    }


def _deleted_paths(decision: str, keep_source: bool, delete_source: bool) -> list[str]:
    """Every origin path Pass 2 would emit a `delete_source` action for.

    Drives the real ADR-026 JSON-only path end to end: `build_from_wire` to
    split confirmed from skipped, then the real delete builder. The `move_note`
    is synthetic because `_build_move_note_actions` is not what is under test —
    site 3 pairs a delete with the moves that consumed the origin, so an
    approved item needs one to be reachable at all.
    """
    parsed = PARSER.build_from_wire(_wire(decision, keep_source, delete_source), "")
    confirmed = parsed["confirmed_items"]
    skipped = parsed["skipped"]
    move_notes = [{
        "id": "A01",
        "action": "move_note",
        "source_inbox_item": ORIGIN,
        "audio_peer": None,
    }] if confirmed else []
    actions = _build_delete_source_actions(
        confirmed, move_notes, [], skipped, INBOX, [0],
    )
    return sorted(a["source_path"] for a in actions)


# ---------------------------------------------------------------------------
# approve — `delete_source` is inert, `keep_source` decides
# ---------------------------------------------------------------------------

def test_approve_deletes_the_origin_by_default():
    """Baseline for the two rows below: with neither flag set, the origin goes
    with the move. If this ever stops holding, the rest of the table says
    nothing useful."""
    assert _deleted_paths("approve", keep_source=False, delete_source=False) == [ORIGIN]


def test_approve_with_delete_source_is_indistinguishable_from_without():
    """Hashi's first question, answered: **no**, `delete_source: true` does
    nothing under `approve`. Same single delete, from the move pairing — not
    from the flag."""
    with_flag = _deleted_paths("approve", keep_source=False, delete_source=True)
    without = _deleted_paths("approve", keep_source=False, delete_source=False)
    assert with_flag == without == [ORIGIN]


def test_keep_source_suppresses_the_paired_delete():
    assert _deleted_paths("approve", keep_source=True, delete_source=False) == []


def test_keep_source_wins_over_delete_source_on_an_approved_item():
    """Hashi's second question for the approve case: `keep_source` wins, and
    not by precedence — `delete_source` is simply never read here."""
    assert _deleted_paths("approve", keep_source=True, delete_source=True) == []


# ---------------------------------------------------------------------------
# skip — `delete_source` is the third leg, and `keep_source` is not consulted
# ---------------------------------------------------------------------------

def test_skip_alone_emits_nothing():
    assert _deleted_paths("skip", keep_source=False, delete_source=False) == []


def test_skip_with_delete_source_deletes_the_origin():
    """The tri-state's third leg, confirmed: discard the suggestion AND remove
    the origin. This is the behaviour their control needs to be able to set."""
    assert _deleted_paths("skip", keep_source=False, delete_source=True) == [ORIGIN]


def test_keep_source_does_not_protect_a_skipped_origin():
    """Hashi's second question for the skip case, and the one worth a warning:
    **the pair is contradictory and the delete wins.**

    Not a precedence rule — `build_from_wire` never copies `keep_source` into a
    skipped entry, so the builder cannot see it. A control offering both would
    let the owner tick "keep" and lose the file.
    """
    assert _deleted_paths("skip", keep_source=True, delete_source=True) == [ORIGIN]


# ---------------------------------------------------------------------------
# The divergence between the two Pass-2 paths
# ---------------------------------------------------------------------------

def test_the_wire_path_does_not_normalise_delete_source_on_approve():
    """The markdown parser forces `delete_source = False` when Accept is
    ticked; `build_from_wire` does not.

    Harmless today — proven by
    `test_approve_with_delete_source_is_indistinguishable_from_without`, since
    no consumer reads a confirmed item's copy. Asserted anyway because it is
    the precondition that makes it harmless: the moment something downstream
    starts reading `confirmed[].delete_source`, the two paths disagree about a
    deletion, and this test is where that shows up.
    """
    approved = PARSER.build_from_wire(
        _wire("approve", keep_source=False, delete_source=True), "")
    assert approved["confirmed_items"][0]["delete_source"] is True

    markdown_result = PARSER.parse_section("S01", [
        "- **Source:** `Dresden.md`",
        "- **Suggested name:** Dresden",
        "- [x] Approve",
        "- [x] Delete source",
    ])
    assert markdown_result["approved"] is True
    assert markdown_result["delete_source"] is False
