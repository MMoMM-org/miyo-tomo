#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t2_4_parse_remedy.py — spec 037 T2.4.

`parse_attachment_conflict_remedies(text) -> list[dict]` reads the three
`## Attachment Conflicts` remedy checkboxes rendered by T2.2/T2.3's
`render_attachment_conflicts_block` back into `remedy` — `rename` ·
`keep_in_inbox` · `ignore` — applying PRD Business Rules 2-4 and ADR-4's
null-`proposed_name` exception. This file pins that resolution exhaustively,
per the T2.4 deviation block in
`docs/XDD/specs/037-asset-destination-collision-is-a-pass1-decision/
plan/phase-2.md`.

Every function below builds its own minimal `## Attachment Conflicts`
fixture text by hand rather than routing through the reducer's renderer —
T2.4 pins the PARSER's read of the three checkbox lines, not the round trip
through render + parse, which stays the renderer's own contract (T2.2/T2.3).
The three checkbox lines mirror `render_attachment_conflicts_block`'s exact
rendered text verbatim (`tomo/scripts/suggestions-reducer.py:~1514-1524`):

    ### `<source>`

    - **Destination:** `<destination>` (already occupied)
    - **Embedded by:**
      - [[owner]]
    - **File comparison:** ...

    **Remedy — choose one:**
    - [x] Rename to `<destination-folder><proposed_name>`
    - [ ] Keep in inbox
    - [ ] Ignore (the move is sent as-is and will fail — the attachment stays in the inbox)

  1. `test_rename_ticked_alone_yields_rename` — mutation: resolve the
     document's own default to `ignore`, making Rule 2 unreachable.
  2. `test_keep_in_inbox_ticked_alone_yields_keep_in_inbox` — mutation: fold
     it into Rule 3's ignore branch.
  3. `test_ignore_ticked_alone_yields_ignore` — mutation: return `None` for
     an explicit tick, relying on the caller's fallback.
  4. `test_rename_cleared_nothing_else_ticked_yields_ignore` — mutation:
     resolve to `keep_in_inbox` — the quiet outcome ADR-4 argues against.
  5. `test_two_remedies_ticked_without_rename_yields_ignore` — mutation:
     first-wins instead of contradiction.
  6. `test_rename_ticked_and_ignore_ticked_yields_ignore_not_rename` — NOT a
     duplicate of #5: kills an implementation that treats the pre-ticked
     rename as sticky (default-wins over a later contradiction), which a
     two-tick test without rename cannot catch.
  7. `test_null_proposal_rename_ticked_alone_yields_ignore` — mutation: pass
     `remedy: rename` through with a null proposal.
  8. `test_entry_missing_checkbox_lines_still_yields_a_string` — mutation:
     leave `remedy` unset when a line is absent.
  9. `test_no_attachment_conflicts_section_yields_empty_list` — mutation:
     fabricate a single empty entry when the section is missing.
  10. `test_two_attachment_conflicts_sections_only_parses_first` — pins a
      DELIBERATE contract (see the test's own docstring), not a bug:
      mutation: in `_walk_attachment_conflicts`, replace the terminating
      `break` with a continue-style re-entry (drop back to `in_section =
      False` and `continue` instead of breaking the loop) so a second
      `## Attachment Conflicts` section further down the document is also
      scanned. Do NOT apply that change to the parser — this test exists to
      keep it out.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PARSER = _load_module("suggestion_parser_t037_t2_4", "suggestion-parser.py")

SOURCE = "100 Inbox/Scans/karte.png"
DESTINATION = "Atlas/290 Assets/295 Attachments/karte.png"
RENAME_TARGET = "Atlas/290 Assets/295 Attachments/karte (2).png"

_PREAMBLE = (
    "## Attachment Conflicts\n"
    "\n"
    f"### `{SOURCE}`\n"
    "\n"
    f"- **Destination:** `{DESTINATION}` (already occupied)\n"
    "- **Embedded by:**\n"
    "  - [[karte]]\n"
    "- **File comparison:** A different file already holds this name.\n"
    "\n"
    "**Remedy — choose one:**\n"
)


def _doc(*checkbox_lines: str) -> str:
    """One conflict entry, with the given remedy checkbox lines verbatim
    (a line simply omitted from the call reproduces a deleted line)."""
    return _PREAMBLE + "\n".join(checkbox_lines) + "\n"


RENAME_TICKED = f"- [x] Rename to `{RENAME_TARGET}`"
RENAME_UNTICKED = f"- [ ] Rename to `{RENAME_TARGET}`"
RENAME_IMPOSSIBLE_TICKED = "- [x] Rename — no free name available"
RENAME_IMPOSSIBLE_UNTICKED = "- [ ] Rename — no free name available"
KEEP_TICKED = "- [x] Keep in inbox"
KEEP_UNTICKED = "- [ ] Keep in inbox"
IGNORE_TICKED = (
    "- [x] Ignore (the move is sent as-is and will fail — "
    "the attachment stays in the inbox)"
)
IGNORE_UNTICKED = (
    "- [ ] Ignore (the move is sent as-is and will fail — "
    "the attachment stays in the inbox)"
)


def _remedy(text: str) -> str:
    entries = PARSER.parse_attachment_conflict_remedies(text)
    assert len(entries) == 1, entries
    assert entries[0]["source"] == SOURCE
    return entries[0]["remedy"]


# ---------------------------------------------------------------------------
# 1. Rename left ticked, nothing else (Rule 2)
# ---------------------------------------------------------------------------

def test_rename_ticked_alone_yields_rename():
    text = _doc(RENAME_TICKED, KEEP_UNTICKED, IGNORE_UNTICKED)
    assert _remedy(text) == "rename"


# ---------------------------------------------------------------------------
# 2. Keep-in-inbox ticked alone
# ---------------------------------------------------------------------------

def test_keep_in_inbox_ticked_alone_yields_keep_in_inbox():
    text = _doc(RENAME_UNTICKED, KEEP_TICKED, IGNORE_UNTICKED)
    assert _remedy(text) == "keep_in_inbox"


# ---------------------------------------------------------------------------
# 3. Ignore ticked alone
# ---------------------------------------------------------------------------

def test_ignore_ticked_alone_yields_ignore():
    text = _doc(RENAME_UNTICKED, KEEP_UNTICKED, IGNORE_TICKED)
    assert _remedy(text) == "ignore"


# ---------------------------------------------------------------------------
# 4. Rename cleared, nothing else ticked (Rule 3, PRD F2-AC5, SDD ADR-4)
# ---------------------------------------------------------------------------

def test_rename_cleared_nothing_else_ticked_yields_ignore():
    text = _doc(RENAME_UNTICKED, KEEP_UNTICKED, IGNORE_UNTICKED)
    assert _remedy(text) == "ignore"


# ---------------------------------------------------------------------------
# 5. Two remedies ticked, NOT involving rename (Rule 4)
# ---------------------------------------------------------------------------

def test_two_remedies_ticked_without_rename_yields_ignore():
    text = _doc(RENAME_UNTICKED, KEEP_TICKED, IGNORE_TICKED)
    assert _remedy(text) == "ignore"


# ---------------------------------------------------------------------------
# 6. Rename stays ticked AND ignore is also ticked — not a duplicate of #5
# ---------------------------------------------------------------------------

def test_rename_ticked_and_ignore_ticked_yields_ignore_not_rename():
    text = _doc(RENAME_TICKED, KEEP_UNTICKED, IGNORE_TICKED)
    assert _remedy(text) == "ignore"


# ---------------------------------------------------------------------------
# 7. proposed_name is null and rename is ticked alone (ADR-4 exception,
#    owner decision 2026-09-23)
# ---------------------------------------------------------------------------

def test_null_proposal_rename_ticked_alone_yields_ignore():
    text = _doc(RENAME_IMPOSSIBLE_TICKED, KEEP_UNTICKED, IGNORE_UNTICKED)
    assert _remedy(text) == "ignore"


# ---------------------------------------------------------------------------
# 8. A conflict entry missing one or more checkbox lines still yields a
#    string, never None
# ---------------------------------------------------------------------------

def test_entry_missing_checkbox_lines_still_yields_a_string():
    # The Ignore line was deleted from the document entirely — not just
    # unticked. A deleted line parses as an unticked line: zero ticks, Rule 3.
    text = _doc(RENAME_UNTICKED, KEEP_UNTICKED)
    remedy = _remedy(text)
    assert remedy is not None
    assert remedy == "ignore"

    # Every remedy line deleted — still resolves, never None.
    text_bare = _PREAMBLE.rstrip("\n") + "\n"
    remedy_bare = _remedy(text_bare)
    assert remedy_bare is not None
    assert remedy_bare == "ignore"


# ---------------------------------------------------------------------------
# 9. No `## Attachment Conflicts` section at all
# ---------------------------------------------------------------------------

def test_no_attachment_conflicts_section_yields_empty_list():
    text = "## Some Other Section\n\nNothing here.\n"
    assert PARSER.parse_attachment_conflict_remedies(text) == []


# ---------------------------------------------------------------------------
# 10. Two `## Attachment Conflicts` sections in one document — the walker
#     stops at the first non-matching `## ` heading and never resumes, so
#     only the first section's entries are returned.
#
#     This is a DELIBERATE, stated contract (see `_walk_attachment_
#     conflicts`'s docstring and `docs/tomo/scripts/suggestion-parser.md`),
#     not a bug being pinned by accident: the renderer only ever emits one
#     such section, so two can only arrive via a hand edit or a bad merge,
#     and which one carries the owner's intent is genuinely ambiguous.
#     First-section-wins was chosen over silently merging two sections that
#     may contradict each other. A future reader must NOT "fix" this by
#     making the walker resume into a later section.
# ---------------------------------------------------------------------------

def test_two_attachment_conflicts_sections_only_parses_first():
    text = (
        "## Attachment Conflicts\n"
        "\n"
        "### `a.png`\n"
        "\n"
        "- **Destination:** `Atlas/290 Assets/295 Attachments/a.png` (already occupied)\n"
        "- **Embedded by:**\n"
        "  - [[owner-a]]\n"
        "- **File comparison:** A different file already holds this name.\n"
        "\n"
        "**Remedy — choose one:**\n"
        "- [x] Rename to `Atlas/290 Assets/295 Attachments/a (2).png`\n"
        "- [ ] Keep in inbox\n"
        "- [ ] Ignore (the move is sent as-is and will fail — "
        "the attachment stays in the inbox)\n"
        "\n"
        "## Some Other Section\n"
        "\n"
        "Unrelated content that separates the two sections.\n"
        "\n"
        "## Attachment Conflicts\n"
        "\n"
        "### `c.png`\n"
        "\n"
        "- **Destination:** `Atlas/290 Assets/295 Attachments/c.png` (already occupied)\n"
        "- **Embedded by:**\n"
        "  - [[owner-c]]\n"
        "- **File comparison:** A different file already holds this name.\n"
        "\n"
        "**Remedy — choose one:**\n"
        "- [ ] Rename to `Atlas/290 Assets/295 Attachments/c (2).png`\n"
        "- [x] Keep in inbox\n"
        "- [ ] Ignore (the move is sent as-is and will fail — "
        "the attachment stays in the inbox)\n"
    )
    entries = PARSER.parse_attachment_conflict_remedies(text)
    assert entries == [{"source": "a.png", "remedy": "rename"}]
