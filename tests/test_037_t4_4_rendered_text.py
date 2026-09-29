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


# ---------------------------------------------------------------------------
# 5. Neither document may assert an outcome it cannot know (owner catch)
# ---------------------------------------------------------------------------
#
# Owner, 2026-09-28: "das sollte MIGHT fail lesen (vielleicht hat der nutzer ja
# das ziel gelöscht wenn er das ignorieren will)". Exactly right, and it applied
# to TWO sites, not one. Occupancy is observed in Pass 1 and re-checked nowhere
# — `path_exists` appears in neither `instruction-render.py` nor
# `render_actions.py` — so between Pass 1 and the apply the owner may well have
# freed the name, which is itself a plausible reason to choose `ignore`. In that
# case the move succeeds, and BOTH halves of "will fail — the attachment stays
# in the inbox" are wrong.
#
# Same family as defects 1-4 above: the document asserting something it is not
# in a position to know.

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer_t037_t4_4", SCRIPTS_DIR / "suggestions-reducer.py")
REDUCER = importlib.util.module_from_spec(_spec)
sys.modules["suggestions_reducer_t037_t4_4"] = REDUCER
_spec.loader.exec_module(REDUCER)

_pspec = importlib.util.spec_from_file_location(
    "suggestion_parser_t037_t4_4", SCRIPTS_DIR / "suggestion-parser.py")
PARSER = importlib.util.module_from_spec(_pspec)
sys.modules["suggestion_parser_t037_t4_4"] = PARSER
_pspec.loader.exec_module(PARSER)

LEGACY_IGNORE_LINE = (
    "- [x] Ignore (the move is sent as-is and will fail — "
    "the attachment stays in the inbox)"
)


def test_the_pass1_ignore_label_does_not_promise_a_failure():
    """Mutation: restore "the move is sent as-is and will fail — the attachment
    stays in the inbox" as the Ignore checkbox label."""
    md = REDUCER.render_attachment_conflicts_block(
        [{
            "source": HELD,
            "destination": f"{ASSET_FOLDER}karte.png",
            "same_file": False,
            "owner_source_items": ["100 Inbox/Dresden.md"],
            "proposed_name": "karte (2).png",
        }],
        ASSET_FOLDER, {},
    )
    ignore_line = next(ln for ln in md.splitlines()
                       if ln.strip().lower().startswith("- [ ] ignore"))
    assert "will fail" not in ignore_line, ignore_line
    assert "if the name is still taken" in ignore_line, ignore_line


def test_the_pass2_ignore_bullet_does_not_promise_a_refusal():
    """Mutation: restore "it will be refused when the run is applied" in
    `_render_unresolved_conflict_bullet`'s `else` branch.

    Distinct from the test above: that one covers the Pass-1 suggestions
    document, this one the Pass-2 instruction document. Both made the claim and
    fixing one would have left the other.
    """
    md = render_instructions_md([], {
        **BASE_METADATA,
        "attachment_conflict_remedies": [
            {"source": HELD, "remedy": "ignore", "proposed_name": None},
        ],
    }, {})
    bullet = next(ln for ln in md.splitlines()
                  if ln.startswith("- ⚠️ **Conflict remains:**"))
    assert "unless that name has since been freed" in bullet, bullet
    assert "will be refused when the run is applied" not in bullet, bullet


def test_a_document_rendered_before_the_wording_changed_still_parses():
    """A suggestions document rendered by reducer 1.57.2 can be sitting
    unapplied in the vault right now. The parser keys on the label PREFIX
    (`label.startswith("ignore")`), not on the parenthetical, so the old
    wording still resolves.

    Mutation: `elif label == "ignore":`.

    The fixture ticks RENAME **and** the legacy Ignore line, and that is the
    whole point. A document ticking only Ignore cannot test this at all: an
    unseen tick leaves all four flags False, and `_resolve_attachment_remedy`
    resolves zero ticks to `ignore` by Rule 3 — the same answer a working
    matcher gives, so the mutation is invisible. Measured 2026-09-28: the
    single-tick version of this test stayed GREEN under the mutation.

    With two ticks the outcomes diverge. Seen: two ticks, Rule 4, `ignore`.
    Not seen: one tick on rename, Rule 2, `rename` — and the owner's override
    is silently discarded, which is the actual failure this guards.
    """
    text = (
        "## Attachment Conflicts\n"
        "\n"
        f"### `{HELD}`\n"
        "\n"
        "**Remedy — choose one:**\n"
        "- [x] Rename to `x.png`\n"
        "- [ ] Keep in inbox\n"
        f"{LEGACY_IGNORE_LINE}\n"
    )
    assert PARSER.parse_attachment_conflict_remedies(text) == [
        {"source": HELD, "remedy": "ignore"},
    ], "the legacy Ignore label was not recognised, so the rename tick won"


# ---------------------------------------------------------------------------
# 6. An ignored conflict is annotated at its own action (owner request)
# ---------------------------------------------------------------------------
#
# Owner, 2026-09-28: "können wir bei conflict remains auf den entsprechenden
# IXX verweisen? oder vielleicht sogar bei IXX das anmerken und nicht am ende
# des dokumentes?" — the second form, because the end-of-document bullet
# renders for THREE routes and only `ignore` has an action to point at:
# keep_in_inbox and a degraded rename withhold the move entirely. A reference
# in the bullet would therefore be present sometimes and absent otherwise; an
# annotation on the action exists exactly where an action does.

IGNORED_MOVE = {
    "id": "I02", "action": "move_asset",
    "source": HELD, "destination": f"{ASSET_FOLDER}karte.png",
}
ANNOTATION = "- ⚠️ **Destination was occupied:**"


def _render_with_remedy(remedy):
    return render_instructions_md([IGNORED_MOVE], {
        **BASE_METADATA,
        "attachment_conflict_remedies": [
            {"source": HELD, "remedy": remedy, "proposed_name": None},
        ],
    }, {})


def _action_block(md):
    lines = md.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("### I02"))
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("### ") or lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def test_an_ignored_conflict_is_annotated_on_its_own_move_action():
    """Mutation: drop the `ignored_conflict_sources` argument from the
    `_render_action_md` call, so the annotation never renders."""
    block = _action_block(_render_with_remedy("ignore"))
    assert ANNOTATION in block, block
    assert "you chose Ignore" in block, block


def test_a_move_with_no_ignored_conflict_is_not_annotated():
    """Mutation: drop the `action.get("source") in ignored_conflict_sources`
    membership test, annotating every move_asset.

    Needed as its own test: the test above passes under that mutation, since
    its one move IS the ignored one. Without this, "annotate the right move"
    and "annotate every move" are indistinguishable.
    """
    md = render_instructions_md([IGNORED_MOVE], {
        **BASE_METADATA,
        "attachment_conflict_remedies": [
            {"source": "100 Inbox/Other/x.png", "remedy": "ignore",
             "proposed_name": None},
        ],
    }, {})
    assert ANNOTATION not in _action_block(md), md


def test_the_annotation_and_the_summary_bullet_share_no_sentence():
    """The owner ruling of 2026-09-27 — a source may appear in two places, but
    no SENTENCE may be repeated — applied to this third site.

    Mutation: give the annotation the summary bullet's own wording.
    """
    md = _render_with_remedy("ignore")
    block = _action_block(md)
    bullet = next(ln for ln in md.splitlines()
                  if ln.startswith("- ⚠️ **Conflict remains:**"))

    def sentences(text):
        return {s.strip().lower() for s in re.split(r"(?<=[.])\s+", text)
                if len(s.strip()) > 25}

    overlap = sentences(block) & sentences(bullet)
    assert not overlap, f"a sentence appears in both places: {overlap}"
    # The annotation must claim no OUTCOME — nothing re-checks the destination
    # between Pass 1 and the apply, which is the correction made 2026-09-28.
    assert "will be refused" not in block, block
    assert "will fail" not in block, block


def test_the_annotation_names_its_steps_in_a_followable_order():
    """Owner catch, 2026-09-29: the annotation read "Re-run `/inbox` and pick
    Rename or Keep in inbox", naming the steps in an order nobody can follow —
    the remedy is ticked in the SUGGESTIONS document, and only then is Pass 2
    re-synthesized from it.

    Mutation: restore "Re-run `/inbox` and pick Rename or Keep in inbox to
    resolve it instead."

    Also pins `--pass2 --force`. That form short-circuits the coverage check
    (`inbox-triage.py`'s `force_all or to_process`) and cannot go idle. A bare
    `/inbox` would most likely work too — the cache is re-read from the vault
    each run, so an edited checkbox changes the suggestions doc's checksum and
    drift routes it to synthesize — but that is a weaker guarantee to hand
    someone, and the annotation deliberately states no reason for the flags:
    a rationale that depends on run state is the defect this section has
    already been corrected for twice.
    """
    block = _action_block(_render_with_remedy("ignore"))
    tick_at = block.find("tick Rename or Keep in inbox")
    run_at = block.find("/inbox --pass2 --force")
    assert tick_at != -1, block
    assert run_at != -1, block
    assert tick_at < run_at, f"the steps are named out of order: {block}"
    assert "suggestions document" in block, block
    # The old form put the command first and named no document.
    assert "Re-run `/inbox` and pick" not in block, block


def test_the_held_remedy_covers_both_reading_moments():
    """Owner ruling, 2026-09-29: the `vault_collision_held` remedy named only
    the route for AFTER applying ("rename the file and re-run `/inbox`").

    This document is read BEFORE applying — every action carries an unticked
    "Applied" box — and at that moment the suggestions document is still live,
    so re-ticking is the cheap route and renaming a file on disk is not. Read
    after applying, the source note is gone and that document is spent, so
    renaming really is the remedy. Both are true at their own moment and
    neither is true at the other's, so the line names both.

    Mutation: restore "No action needed unless you change your mind; rename the
    file and re-run `/inbox` to file it after all."
    """
    _skipped, md = _all_three_kinds()
    ln = next(b for b in _filed_bullets(md) if f"`{HELD}`" in b)
    before_at = ln.find("before applying")
    after_at = ln.find("afterwards")
    assert before_at != -1, ln
    assert after_at != -1, ln
    assert before_at < after_at, f"the two moments are named out of order: {ln}"
    assert "/inbox --pass2 --force" in ln, ln
    # Same ordering rule as the ignore annotation: tick first, then run.
    tick_at = ln.find("tick Rename in the suggestions document")
    assert tick_at != -1 and tick_at < ln.find("/inbox --pass2 --force"), ln
