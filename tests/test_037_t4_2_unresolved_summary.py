#!/usr/bin/env python3
# version: 0.3.0
"""test_037_t4_2_unresolved_summary.py — spec 037 T4.2: Pass 2's summary
names what it did not resolve.

Two defects fixed together in `render_instructions_md`'s "## Skipped —
un-appliable actions" section:

1. A live regression T3.1 shipped: a `keep_in_inbox`/degraded-rename
   `skipped_assets` entry carries `kind: "vault_collision_held"`, which had
   no branch in the "**Attachment not filed**" loop and fell through to the
   loud "(no remedy defined ...)" placeholder — a real user-facing defect,
   since every Phase 3 test asserted on `skipped_assets` as data and none
   rendered it (`tests/test_037_t3_1_remedy_outcomes.py`).
2. PRD C2/S2 (spec 037): an `ignore`d conflict reaches NO report anywhere —
   `_build_move_asset_actions` emits its move unchanged against the occupied
   destination and records nothing (`render_actions.py:819-823`). This file
   adds "**Conflicts not resolved by rename**", built from the union of
   `skipped_assets` (`kind == "vault_collision_held"`) and
   `attachment_conflict_remedies` (`remedy == "ignore"`) — two source lists,
   not one filter, because `remedy != "rename"` on `attachment_conflict_
   remedies` alone silently drops a DEGRADED rename (`proposed_name: null`,
   SDD:292's "A rename that lost its name" degrades to keep-in-inbox, but its
   OWN `remedy` field still reads `"rename"`).

ADR-11 (`render_md.py:668`, owner ruling 2026-09-27): no rendered line in
either report names a wire action (`move_asset`) — both use the `⚠️
**<label>:**` convention `_withdrawn_links_note` and Pass 1 already share.

Second owner ruling, same date: a `vault_collision_held` source appears in
BOTH reports by design (see the module docstring in `render_md.py` and
`docs/tomo/scripts/lib/render_md.md:384-402`), but the two bullets rendered
the same `reason` sentence twice — "Conflicts not resolved by rename" was
built as "Attachment not filed" plus a remedy clause, not as its own answer.
The ruling: keep both blocks, stop repeating the sentence. "Conflict
remains" states the decision and its consequence; "Attachment not filed"
states where the file is and what to do about it. Neither may lose a fact
it alone carries. `test_conflict_remains_never_repeats_attachment_not_filed`
below pins this mechanically — by sentence, not by a vaguer "different
wording somewhere" check.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_md import render_instructions_md  # noqa: E402

BASE_METADATA = {"generated": "2026-09-27T12:00:00Z"}


def _skipped(**overrides) -> dict:
    entry = {
        "source": "100 Inbox/Scans/karte.jpg",
        "destination": "Atlas/290 Assets/295 Attachments/karte.jpg",
        "reason": "some reason",
        "kind": "vault_collision_held",
    }
    entry.update(overrides)
    return entry


def _remedy(**overrides) -> dict:
    entry = {"source": "100 Inbox/Scans/karte.jpg", "remedy": "ignore", "proposed_name": None}
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------
# 1. The T3.1 regression: vault_collision_held must not fall through
# ---------------------------------------------------------------------------

def test_vault_collision_held_no_longer_falls_back_to_unrecognized_kind():
    """Mutation: delete the `elif kind == "vault_collision_held"` branch —
    the catch-all `(no remedy defined for skip kind ...)` returns, which is
    exactly the live defect T3.1 shipped."""
    metadata = {
        **BASE_METADATA,
        "skipped_assets": [_skipped(
            reason="kept in inbox: the owner chose not to file "
                   "'100 Inbox/Scans/karte.jpg' over the occupied destination "
                   "'Atlas/290 Assets/295 Attachments/karte.jpg'",
        )],
    }
    md = render_instructions_md([], metadata, {})
    assert "no remedy defined" not in md.lower(), md
    assert "kept in inbox" in md, md
    assert "100 Inbox/Scans/karte.jpg" in md


# ---------------------------------------------------------------------------
# 2. ADR-11 — no rendered line names a wire action, in either report
# ---------------------------------------------------------------------------

def test_no_rendered_line_names_move_asset():
    """All three `skipped_assets` kinds (no_basename, collision,
    vault_collision_held) plus an `ignore` conflict, in one render. Mutation:
    revert the bullet to `f"- \\`move_asset\\` → ..."` — this is the ONE
    place the literal string can appear (a normal move_asset ACTION renders
    as "Move attachment: <name>", never the wire name — render_md.py:95-102)."""
    metadata = {
        **BASE_METADATA,
        "skipped_assets": [
            _skipped(source="100 Inbox/Images/", destination=None,
                     reason="no basename", kind="no_basename"),
            _skipped(source="100 Inbox/Scans/a.jpg", destination="Atlas/a.jpg",
                     reason="destination collision", kind="collision"),
            _skipped(source="100 Inbox/Scans/b.jpg", destination="Atlas/b.jpg",
                     reason="kept in inbox: the owner chose not to file it",
                     kind="vault_collision_held"),
        ],
        "attachment_conflict_remedies": [_remedy(source="100 Inbox/Scans/c.jpg")],
    }
    md = render_instructions_md([], metadata, {})
    assert "move_asset" not in md, md
    assert "⚠️ **Attachment not filed:**" in md
    assert "⚠️ **Conflict remains:**" in md


# ---------------------------------------------------------------------------
# 3. The three-remedy fixture: names the two non-rename sources, never the
#    rename source, in the unresolved-conflicts report
# ---------------------------------------------------------------------------

KEEP_SOURCE = "100 Inbox/Scans/keep.jpg"
IGNORE_SOURCE = "100 Inbox/Scans/ignore.jpg"
RENAME_SOURCE = "100 Inbox/Scans/rename.jpg"


def _three_remedy_metadata() -> dict:
    return {
        **BASE_METADATA,
        "skipped_assets": [_skipped(
            source=KEEP_SOURCE,
            destination="Atlas/keep.jpg",
            reason=f"kept in inbox: the owner chose not to file {KEEP_SOURCE!r} "
                   "over the occupied destination 'Atlas/keep.jpg'",
            kind="vault_collision_held",
        )],
        "attachment_conflict_remedies": [
            {"source": KEEP_SOURCE, "remedy": "keep_in_inbox", "proposed_name": None},
            {"source": IGNORE_SOURCE, "remedy": "ignore", "proposed_name": None},
            {"source": RENAME_SOURCE, "remedy": "rename", "proposed_name": "rename-2.jpg"},
        ],
    }


def test_unresolved_report_names_the_two_non_rename_sources_verbatim():
    md = render_instructions_md([], _three_remedy_metadata(), {})
    section = md.split("**Conflicts not resolved by rename**", 1)[1]
    # Cut at the next blank-line-terminated block so a coincidental mention
    # of RENAME_SOURCE elsewhere in the document (e.g. its normal move
    # action, which legitimately exists) is not what the assertion below
    # is reading.
    section = "\n\n".join(section.split("\n\n")[:2])
    assert KEEP_SOURCE in section, section
    assert IGNORE_SOURCE in section, section


def test_unresolved_report_never_names_the_successful_rename_source():
    """Mutation: filter `attachment_conflict_remedies` on `remedy != "rename"`
    instead of the two-list union — for THIS fixture it happens to produce
    the same two entries, so this assertion alone cannot distinguish the
    approaches; it exists to pin the invariant the next test's mutation
    actually breaks."""
    md = render_instructions_md([], _three_remedy_metadata(), {})
    section = md.split("**Conflicts not resolved by rename**", 1)[1]
    section = "\n\n".join(section.split("\n\n")[:2])
    assert RENAME_SOURCE not in section, section


# ---------------------------------------------------------------------------
# 4. The degraded-rename source: present via skipped_assets even though its
#    OWN `remedy` field still reads "rename"
# ---------------------------------------------------------------------------

DEGRADED_SOURCE = "100 Inbox/Scans/degraded.jpg"


def test_degraded_rename_is_reported_despite_its_remedy_field_saying_rename():
    """Mutation: `[r for r in attachment_conflict_remedies if r.get("remedy")
    != "rename"]` in place of the two-list union. SDD:292 — a rename whose
    `proposed_name` came back null degrades to keep-in-inbox at render time
    (`render_actions.py:780-784`) and lands in `skipped_assets` with
    `kind: "vault_collision_held"`, but the `attachment_conflict_remedies`
    entry that PRODUCED it still says `"remedy": "rename"` — filtering that
    list on `!= "rename"` drops it. Sourcing from `skipped_assets` instead
    (which already carries the degrade) does not."""
    metadata = {
        **BASE_METADATA,
        "skipped_assets": [_skipped(
            source=DEGRADED_SOURCE,
            destination="Atlas/degraded.jpg",
            reason=f"kept in inbox: {DEGRADED_SOURCE!r} was to be filed under "
                   "a new name beside the occupied destination "
                   "'Atlas/degraded.jpg', and that name is no longer "
                   "available to this run",
            kind="vault_collision_held",
        )],
        "attachment_conflict_remedies": [
            # proposed_name is null — the degrade SDD:292 describes. The
            # `remedy` key itself is untouched: still "rename".
            {"source": DEGRADED_SOURCE, "remedy": "rename", "proposed_name": None},
        ],
    }
    md = render_instructions_md([], metadata, {})
    section = md.split("**Conflicts not resolved by rename**", 1)[1]
    section = "\n\n".join(section.split("\n\n")[:2])
    assert DEGRADED_SOURCE in section, section


# ---------------------------------------------------------------------------
# 5. Names, never counts (PRD/C2)
# ---------------------------------------------------------------------------

def test_no_sentence_counts_the_conflicts():
    """Mutation: render `"2 conflicts remain: a.png, b.png"` — a vague "names
    both" assertion would accept this; a bare count nowhere in the document
    would not."""
    md = render_instructions_md([], _three_remedy_metadata(), {})
    assert not re.search(r"\d+\s+conflicts?\b", md, re.IGNORECASE), md


# ---------------------------------------------------------------------------
# 6. A run with no conflicts is unaffected
# ---------------------------------------------------------------------------

def test_no_conflicts_renders_no_new_block_at_all():
    """Already true on HEAD for the "## Skipped" heading itself; this pins
    that the new block adds nothing when there is nothing to report — not
    asserted alone, only alongside the other tests in this file."""
    metadata = {
        **BASE_METADATA,
        "skipped_daily": [{
            "action": "update_tracker", "daily_note_path": "Daily/2026-09-27.md",
            "field": "steps",
        }],
    }
    md = render_instructions_md([], metadata, {})
    assert "Conflicts not resolved by rename" not in md
    assert "conflict" not in md.lower()


def test_no_conflicts_and_no_other_skips_opens_no_skipped_heading():
    md = render_instructions_md([], BASE_METADATA, {})
    assert "## Skipped" not in md


# ---------------------------------------------------------------------------
# 7. Owner ruling 2026-09-27: the two blocks answer different questions in
#    the rendered TEXT too, not only by design — no sentence appears twice
# ---------------------------------------------------------------------------

def _bullet_sentences(line: str) -> set[str]:
    """The clause(s) after the leading `` `source` — `` of one rendered
    bullet, as a set of trimmed sentences. Splitting on ". " (rather than
    diffing whole lines) is what lets this catch a REPEATED CLAUSE inside a
    longer line, not just two identical lines — "Attachment not filed"
    always carries two clauses (reason + remedy) where "Conflict remains"
    carries one, so a whole-line comparison would never find the overlap
    this section is built to prevent."""
    detail = line.split(" — ", 1)[1]
    return {s.strip().rstrip(".") for s in detail.split(". ") if s.strip()}


def test_conflict_remains_never_repeats_attachment_not_filed():
    """A `vault_collision_held` source (KEEP_SOURCE here) renders under BOTH
    "Attachment not filed" and "Conflicts not resolved by rename" by design
    (docs/tomo/scripts/lib/render_md.md:384-402) — that duplication of WHICH
    sources are named is intentional. What must NOT happen is the two
    bullets stating the same sentence: pre-ruling, "Conflict remains" used
    `entry.get("reason")` verbatim, which is exactly "Attachment not filed"'s
    own first clause.

    Mutation: in `_render_unresolved_conflict_bullet`, replace the
    `vault_collision_held` branch's `detail` with `entry.get("reason")` (the
    pre-ruling code) — this test goes red because `sentences_remains` then
    contains the exact clause `sentences_filed` already carries.
    """
    md = render_instructions_md([], _three_remedy_metadata(), {})
    lines = md.splitlines()
    filed_lines = [ln for ln in lines if ln.startswith("- ⚠️ **Attachment not filed:**")]
    remains_lines = [ln for ln in lines if ln.startswith("- ⚠️ **Conflict remains:**")]
    # Counts, not just presence. The sentence-set comparison below unions
    # each block's lines with `|=`, so a bullet rendered TWICE contributes an
    # identical set and passes silently — the whole additive-duplication class
    # is invisible to a presence-only assertion. This fixture has exactly one
    # `vault_collision_held` entry and two unresolved conflicts (that entry
    # plus the `ignore`d one).
    # Mutation: append any `unresolved_conflicts` entry to the list twice in
    # `render_instructions_md`, or drop the `kind` filter so a `no_basename`
    # entry joins them — the set comparison stays green, this does not.
    assert len(filed_lines) == 1, f"expected exactly one filed bullet: {filed_lines}"
    assert len(remains_lines) == 2, f"expected exactly two remains bullets: {remains_lines}"

    sentences_filed: set[str] = set()
    for ln in filed_lines:
        sentences_filed |= _bullet_sentences(ln)
    sentences_remains: set[str] = set()
    for ln in remains_lines:
        sentences_remains |= _bullet_sentences(ln)

    overlap = sentences_filed & sentences_remains
    assert not overlap, f"a sentence appears in both blocks: {overlap}"

    # Neither bullet may lose the fact it alone carries: "Attachment not
    # filed" is the only place the remedy ("no action needed ...") is
    # stated, and "Conflict remains" is the only place naming the decision's
    # consequence for the KEEP_SOURCE entry without also restating the
    # remedy instruction.
    filed_line = next(ln for ln in filed_lines if KEEP_SOURCE in ln)
    remains_line = next(ln for ln in remains_lines if KEEP_SOURCE in ln)
    assert "No action needed" in filed_line, filed_line
    assert "No action needed" not in remains_line, remains_line
    assert "Atlas/keep.jpg" in remains_line, remains_line
