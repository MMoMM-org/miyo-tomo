#!/usr/bin/env python3
# version: 0.2.0
"""test_037_typed_rename_target_is_ignored.py — a rename target the owner types
into the suggestions markdown reaches Pass 2. **Fixed by spec 038 T4.2**; the
filename is kept so the history of the defect stays findable.

Owner decision 2026-09-29: *"Hashi soll das Ziel umbenennen können und wir
auch."* Both surfaces must let the owner name the file. Neither did, and the
markdown's failure was the worse of the two because it accepted the keystrokes
and dropped them.

**What happened before.** The markdown renders the computed name as part of a
checkbox label — `- [x] Rename to \\`…/karte (2).png\\`` — so it looks
editable. It was not: `_join_attachment_conflict_remedies` read
`proposed_name` from the structured `suggestions-doc.json` and joined it on
`source`, and the rendered text was never consulted for it. An owner who
overtyped the name got the computed one, with nothing anywhere reporting the
difference. That was the same class as the four owner-facing sentences
corrected on 2026-09-28/29 and as the wire-path loss Hashi reported on
2026-09-29: a surface that offers something it does not honour.

**What fixed it.** spec 038 T4.2: the name is read from the backtick text, the
folder prefix the renderer itself wrote is un-rendered first (owner ruling
2026-10-02), and the remainder is compared against the doc's bare name only to
decide whether the typed-name guard (`lib/typed_name_check.py`, T3.1/T3.2)
applies. The doc is no longer consulted for the value. The strict xfail and
`test_the_typed_name_is_discarded_today` were both removed with that task.

Both tests below are now plain statements of the 2026-09-29 decision. The
cases that drove the design — the un-render table, the refusal reasons, the
no-free-name line's three outcomes — live in
`tests/test_038_t4_2_parser_reads_the_typed_name.py`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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


def test_a_typed_rename_target_is_honoured():
    """**The behaviour the owner asked for**, and it now holds: spec 038 T4.2
    reads `proposed_name` from the rendered markdown instead of the structured
    doc, un-rendering the folder prefix the renderer itself wrote so the bare
    typed name is what reaches Pass 2.

    The strict xfail that stood here was removed with that task, and
    `test_the_typed_name_is_discarded_today` — which recorded the defect, not
    a contract — was deleted with it, as its own assertion message instructed.
    The case that drove the design lives on in
    `tests/test_038_t4_2_parser_reads_the_typed_name.py`, with the un-render
    table and the refusal reasons; this one stays as the plain statement of
    the owner's 2026-09-29 decision.
    """
    assert _proposed_name_for(TYPED) == TYPED
