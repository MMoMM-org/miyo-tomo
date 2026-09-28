#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t4_4_rendered_text.py — spec 037 T4.4: four text defects the
keep-in-inbox live run exposed, none of which any test could see.

Every one of these was in shipped output on 2026-09-28, in a document an
owner reads, and the whole suite was green. They are grouped here because
they share a cause: the existing tests asserted that expected substrings were
PRESENT, and none of these defects removes a substring.

1. The "**Conflicts not resolved by rename**" heading claimed "the owner
   chose otherwise". `_render_unresolved_conflict_bullet` had been made
   passive in T4.2 precisely because that claim is FALSE for a degraded
   rename — the owner chose `rename` and the run lost the name. The bullet
   complied; the heading one line above it was never revisited.

2. The "Attachment not filed" bullet joins `reason` and `remedy` with ". ",
   and every remedy began in lower case: "...karte.png'. no action needed".

3. The skipped source was rendered TWICE on one line — once backticked in the
   bullet's lead, once as a repr inside `reason` — in two quoting styles. All
   three skip kinds did this; `no_basename` additionally said "has no
   filename" in both halves.

4. The block heading was the bullet's own label verbatim ("Attachment not
   filed"), so the block read as an echo of itself. The sibling block
   ("Conflicts not resolved by rename" → "Conflict remains") never did.

These tests build `skipped_assets` through `_build_move_asset_actions` rather
than hand-writing entries, because defects 2 and 3 live in the SEAM between
the reason (render_actions.py) and the remedy (render_md.py). A fixture that
supplies its own `reason` cannot see them — which is why the T4.2 file, which
does exactly that, stayed green through all four.
"""
from __future__ import annotations

import re
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
BASE_METADATA = {"generated": "2026-09-28T12:00:00Z"}

HELD = "100 Inbox/Scans/karte.png"
CLASH_A = "100 Inbox/Reise/Ufer.jpg"
CLASH_B = "100 Inbox/Places/Ufer.jpg"
NO_NAME = "100 Inbox/Images/"


def _entry(source_path, attachments):
    return {
        "id": "S01", "action": None, "title": "Some Note",
        "source_path": source_path, "rendered_file": f"2026-01-01_0900_{source_path}",
        "destination": "Atlas/202 Notes/", "parent_moc": "", "parent_mocs": [],
        "tags": [], "attachments": attachments,
    }


def _all_three_kinds():
    """One render carrying every `skipped_assets` kind, built by the real
    producer. `keep_in_inbox` yields `vault_collision_held`; the two Ufer
    paths collide on one destination; the trailing-slash path has no
    basename."""
    manifest = [
        _entry("karte.md", [HELD]),
        _entry("ufer.md", [CLASH_A, CLASH_B]),
        _entry("images.md", [NO_NAME]),
    ]
    remedies = [{"source": HELD, "remedy": "keep_in_inbox", "proposed_name": None}]
    _actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0],
        attachment_conflict_remedies=remedies,
    )
    kinds = {s["kind"] for s in skipped}
    assert kinds == {"vault_collision_held", "collision", "no_basename"}, kinds
    md = render_instructions_md([], {**BASE_METADATA, "skipped_assets": skipped}, {})
    return skipped, md


def _filed_bullets(md):
    return [ln for ln in md.splitlines()
            if ln.startswith("- ⚠️ **Attachment not filed:**")]


# ---------------------------------------------------------------------------
# 1. The heading must not assert an intent the bullet refuses to assert
# ---------------------------------------------------------------------------

def test_the_unresolved_conflicts_heading_never_claims_the_owner_chose():
    """Mutation: restore "— the owner chose otherwise, and Pass 2 did not
    resolve these:" as the heading. Nothing else changes, and every T4.2
    assertion stays green, because they all read the BULLETS.

    Why it matters: `skipped_assets` unifies keep-in-inbox and a degraded
    rename under one `vault_collision_held` kind, so both render beneath this
    heading. For the degraded rename the owner chose `rename`; the name was
    lost by this run. Telling them they chose otherwise reports a decision
    they did not make — the exact defect T4.2 fixed one line lower down.
    """
    metadata = {
        **BASE_METADATA,
        "attachment_conflict_remedies": [
            {"source": HELD, "remedy": "ignore", "proposed_name": None},
        ],
    }
    md = render_instructions_md([], metadata, {})
    heading = next(
        ln for ln in md.splitlines()
        if ln.startswith("**Conflicts not resolved by rename**")
    )
    assert "the owner chose" not in heading, heading
    assert "chose otherwise" not in heading, heading


# ---------------------------------------------------------------------------
# 2. reason + remedy is two sentences, so the second starts in upper case
# ---------------------------------------------------------------------------

def test_no_attachment_bullet_opens_a_sentence_in_lower_case():
    """Mutation: lower-case the first letter of any remedy string in
    render_md.py's `skipped_assets` loop.

    Checks every kind, because each supplies its own remedy and one branch
    can regress alone. The `". "` join is what makes this a sentence boundary
    at all — a bullet that joined with an em-dash would not need this.
    """
    _skipped, md = _all_three_kinds()
    bullets = _filed_bullets(md)
    assert len(bullets) == 3, bullets
    for ln in bullets:
        for sentence in re.findall(r"\. ([A-Za-z])", ln):
            assert sentence.isupper(), (
                f"a sentence opens in lower case after a full stop: {ln}"
            )


# ---------------------------------------------------------------------------
# 3. One bullet names its attachment once, in one style
# ---------------------------------------------------------------------------

def test_a_skipped_attachment_is_named_exactly_once_in_its_bullet():
    """Mutation: put the source path back into any `reason` in
    render_actions.py — e.g. restore `f"...not to file {path!r} over..."`.

    A COUNT assertion, deliberately. Every pre-existing test here asserted
    the path was PRESENT, which stays true when it appears twice; that is why
    four separate reason strings carried a duplicate for three specs without
    one test noticing.
    """
    _skipped, md = _all_three_kinds()
    bullets = _filed_bullets(md)
    assert len(bullets) == 3, bullets
    by_source = {s: ln for s in (HELD, CLASH_B, NO_NAME)
                 for ln in bullets if f"`{s}`" in ln}
    assert len(by_source) == 3, by_source
    for source, ln in by_source.items():
        assert ln.count(source) == 1, f"{source} named {ln.count(source)}×: {ln}"
    # The claimant of a collision has no field of its own, so it legitimately
    # appears in `reason` — but in backticks, like every other path.
    for ln in bullets:
        assert "'" not in ln, f"a path renders as a repr rather than in backticks: {ln}"


def test_the_no_basename_bullet_does_not_say_the_same_thing_twice():
    """Mutation: restore the remedy to "The inbox entry has no filename —
    inspect that inbox path directly, ...". Both halves then say the file has
    no name, in a two-clause sentence that tells the owner one fact.

    Separate from the count test above because it is a PROSE duplication, not
    a path one: no substring is repeated exactly, so the count assertion
    cannot see it.
    """
    _skipped, md = _all_three_kinds()
    ln = next(b for b in _filed_bullets(md) if f"`{NO_NAME}`" in b)
    assert ln.lower().count("no filename") == 1, ln
    assert ln.lower().count("has no") == 1, ln


# ---------------------------------------------------------------------------
# 4. The heading is not the bullet's own label
# ---------------------------------------------------------------------------

def test_the_attachments_block_heading_is_not_the_bullet_label():
    """Mutation: restore "**Attachment not filed** — these attachments were
    left in the inbox:".

    The sibling block already reads correctly — heading "Conflicts not
    resolved by rename", bullets "Conflict remains:" — so this asserts a
    convention the document half-followed rather than inventing one.
    """
    _skipped, md = _all_three_kinds()
    headings = [ln for ln in md.splitlines()
                if ln.startswith("**") and ln.rstrip().endswith(":")]
    attach_heading = next(ln for ln in headings if "inbox" in ln.lower())
    assert not attach_heading.startswith("**Attachment not filed**"), attach_heading
    assert _filed_bullets(md), "no bullets rendered, so the heading check is vacuous"
