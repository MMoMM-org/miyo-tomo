#!/usr/bin/env python3
"""test_038_t4_5_asset_notice_extraction.py — spec 038 T4.5, step 3(a).

T4.5 relays every withheld attachment into the shell report, and the way it
earns "one source, two surfaces" is an extraction: the "Attachment not filed"
bullet, built inline inside `render_instructions_md`'s `skipped_assets` loop,
becomes `_render_skipped_asset_notice(entry) -> str` beside
`_render_withdrawn_delete_notice` — called from the loop AND, a second time,
from the relay writer in `instruction-render.py`. The delete relay already
works exactly that way, and the comment at its call site states the reason
outright: calling the same function twice is what stops the two surfaces
drifting apart.

**The literals below were captured from the rendered document at the commit
BEFORE the extraction** (`2a06ee9`, 2026-10-03), by running the four kinds
through the real `_build_move_asset_actions` chain and printing the
"Attachments still in the inbox" block verbatim. That order is the whole
point of this file: literals read off the *new* function would pin whatever
the extraction happens to emit, which is a tautology. These pin the
pre-extraction behaviour, so the document the owner reviews is provably
unchanged by the refactor.

Mutations this file catches — each one actually fires:
  * the extracted function joining `remedy` with anything but `. ` + `.`
    (T4.4's live run already produced "...karte.png'. no action needed" from
    a lower-case branch opening, so this sentence shape is load-bearing);
  * a `kind` branch picking up another branch's `remedy` text — the `if`/
    `elif` order is reproduced by hand during the move and a mis-ordered
    `elif` swaps `vault_collision_held` and `typed_name_refused`, whose
    remedies differ only in their second half;
  * the loop losing the backticks, the `⚠️` marker, or the `**…:**` label
    while being reduced to a single `append` call;
  * the unrecognised-`kind` fallback being softened into one of the four
    real remedies (`test_unrecognised_kind_keeps_its_loud_fallback`).

No containment assertions anywhere below: whole lines only. Two were removed
from this spec as unsound (`e3008f9`, `5ed5b76`) — the text embeds the
owner's own typed name and inbox paths, so a forbidden-substring rule breaks
on an attachment literally named `move_asset.png`, and one refusal reason is
`blank`, an enum token that is also an English word.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _build_move_asset_actions  # noqa: E402
from lib.render_md import render_instructions_md  # noqa: E402

INBOX = "100 Inbox/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
BASE_METADATA = {"generated": "2026-10-03T12:00:00Z"}

# One attachment per withholding `kind`, each reaching exactly one branch.
NO_BASENAME_SOURCE = "100 Inbox/Scans/"
HELD_SOURCE = "100 Inbox/Scans/karte.png"
COLLIDE_FIRST = "100 Inbox/Scans/A/foto.jpg"
COLLIDE_SECOND = "100 Inbox/Scans/B/foto.jpg"
REFUSED_SOURCE = "100 Inbox/Scans/bild.png"
REFUSED_TYPED_NAME = "sub/dir.png"

# ── The pre-extraction document, captured at `2a06ee9` ────────────────────
# Whole lines, in render order. Nothing here is composed from the production
# code's own strings — that is what makes it a pin and not a mirror.

EXPECTED_BLOCK = [
    "**Attachments still in the inbox** — none of these were filed:",
    "",
    "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/` — the inbox path has no "
    "filename. Inspect that inbox path directly — this is not a naming conflict.",
    "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/karte.png` — kept in inbox: "
    "the owner chose not to file it over the occupied destination "
    "`Atlas/290 Assets/295 Attachments/karte.png`. No action needed unless you "
    "change your mind: before applying, tick Rename in the suggestions document "
    "and run `/inbox --pass2 --force`; afterwards, rename the file in the inbox "
    "and re-run `/inbox`.",
    "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/B/foto.jpg` — destination "
    "collision: it also resolves to `Atlas/290 Assets/295 Attachments/foto.jpg`, "
    "already claimed by `100 Inbox/Scans/A/foto.jpg`. Rename one of the two "
    "files so they no longer share "
    "`Atlas/290 Assets/295 Attachments/foto.jpg`, then re-run `/inbox`.",
    "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/bild.png` — typed name "
    "refused: `sub/dir.png` contains a path separator, which is not allowed in "
    "a filename. Type a usable name for it: before applying, correct the name "
    "in the suggestions document and run `/inbox --pass2 --force`; afterwards, "
    "it is still in the inbox, so re-run `/inbox` and name it again.",
]

# The deliberate loud fallback (T4.5 step 3(e)): an unrecognised `kind` must
# never inherit another kind's instruction, so it says so — and now says so in
# the shell too. Captured the same way, at the same commit.
EXPECTED_FALLBACK_LINE = (
    "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/x.png` — something new "
    "happened. (No remedy defined for skip kind 'brand_new_kind' — check "
    "render_md.py)."
)


def _item(id_: str, source_path: str, attachments: list[str]) -> dict:
    return {
        "id": id_, "action": None, "title": "Some Note",
        "source_path": source_path,
        "rendered_file": f"2026-01-01_0900_{source_path}",
        "destination": "Atlas/202 Notes/", "parent_moc": "", "parent_mocs": [],
        "tags": [], "attachments": attachments,
    }


def build_four_kinds_skipped_assets() -> list[dict]:
    """Every `kind` that withholds a move, built through the real production
    chain rather than hand-written: `reason` lives in the seam between
    `render_actions.py` and `render_md.py`, and a fixture supplying its own
    `reason` is blind to a regression on either side of that seam
    (`tests/test_038_t3_4_refusal_reported.py`'s rationale).

    Shared with the relay tests, which must compare the two surfaces over the
    same entries.
    """
    manifest = [
        _item("S01", "note-a.md", [NO_BASENAME_SOURCE, HELD_SOURCE]),
        _item("S02", "note-b.md", [COLLIDE_FIRST, COLLIDE_SECOND]),
        _item("S03", "note-c.md", [REFUSED_SOURCE]),
    ]
    remedies = [
        {"source": HELD_SOURCE, "remedy": "keep_in_inbox"},
        {"source": REFUSED_SOURCE, "remedy": "rename",
         "proposed_name": REFUSED_TYPED_NAME, "name_is_owner_supplied": True},
    ]
    _actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0],
        attachment_conflict_remedies=remedies,
    )
    assert [s["kind"] for s in skipped] == [
        "no_basename", "vault_collision_held", "collision", "typed_name_refused",
    ], skipped
    return skipped


def _rendered_block(skipped: list[dict]) -> list[str]:
    """The "Attachments still in the inbox" block as rendered, heading line
    through last bullet."""
    md = render_instructions_md(
        [], {**BASE_METADATA, "skipped_assets": skipped}, {}
    )
    lines = md.splitlines()
    start = next(
        i for i, ln in enumerate(lines)
        if ln.startswith("**Attachments still in the inbox**")
    )
    end = start + 1
    last_bullet = start
    while end < len(lines):
        if lines[end].startswith("- ⚠️ **Attachment not filed:**"):
            last_bullet = end
        elif lines[end].startswith("**") or lines[end].startswith("## "):
            break
        end += 1
    return lines[start:last_bullet + 1]


class TestExtractionIsBehaviourPreserving:
    def test_extraction_preserves_rendered_document_byte_identical(self):
        """The four kinds' block, line for line, against literals captured
        BEFORE `_render_skipped_asset_notice` existed.

        Mutation that fires: swap the `vault_collision_held` and
        `typed_name_refused` branches in the extracted function — both open
        "…: before applying, …" and differ only afterwards, so a reader
        skimming the move would not catch it. Two lines of this list change.
        """
        assert _rendered_block(build_four_kinds_skipped_assets()) == EXPECTED_BLOCK

    def test_unrecognised_kind_keeps_its_loud_fallback(self):
        """An unknown `kind` names itself and the file to check, and must not
        quietly inherit a real remedy.

        Mutation that fires: replace the `else` branch's text with any of the
        four real remedies — the line below stops matching. Hand-written
        entry on purpose: no production path emits an unknown `kind`, which is
        exactly why the fallback has no other test.
        """
        skipped = [{
            "source": "100 Inbox/Scans/x.png",
            "reason": "something new happened",
            "kind": "brand_new_kind",
        }]
        assert _rendered_block(skipped)[-1] == EXPECTED_FALLBACK_LINE
