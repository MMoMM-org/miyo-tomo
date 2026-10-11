#!/usr/bin/env python3
"""test_038_t4_3_refused_name_rewrites_no_embed.py — spec 038 T4.3.

T3.2 taught `_build_move_asset_actions` (`lib/render_actions.py`) to refuse an
owner-typed `proposed_name` and emit no `move_asset` for it. It did not touch
`rewrite_renamed_embeds` (`lib/embed_rewrite.py`), which runs EARLIER in
`instruction-render.py`'s per-item loop and gated only on `remedy == "rename"`
plus a truthy `proposed_name`. So the two halves disagreed on the same remedy
record: the body was rewritten to a name the move then refused, leaving the
attachment in the inbox under its old name while the note pointed elsewhere.
Measured on this branch 2026-10-03, before the fix, over one body containing
`![[karte.png]]` twice:

    case               verdict                     rewritten  move
    accepted           ok=True                     yes        actions=1
    refused separator  ok=False separator_present   YES        0, typed_name_refused
    refused pipe       ok=False forbidden_character YES        0, typed_name_refused
    refused blank      ok=False blank               YES        0, typed_name_refused

The three refusal classes do NOT fail alike, which is why each gets its own
test below rather than one representative case:

  - `Archive/karte-…png` produces a dangling embed that also hard-codes a path.
  - `karte|1938.png` produces `![[karte|1938.png]]`, which is NOT dangling:
    `|` is Obsidian's alias separator, so the body embeds a different note
    named `karte` displayed as `1938.png`. Nothing looks broken. (This test
    file asserts the byte-level body only; the rendering claim is Obsidian's
    documented alias syntax, not something exercised here.)
  - `"   "` produces `![[   ]]`, an embed of whitespace.

Coverage before this file was zero: `grep -c name_is_owner_supplied
tests/test_037_t3_3_embed_rewrite.py` → 0, and none of that file's cases
involves a typed name at all. That is how the gap survived T3.2.

The last test is the only one that can see the two gate conditions drifting
apart — `check_typed_name` is now called from two places that must keep
agreeing and nothing in the type system makes them. Neither per-half test can
catch that; drift is exactly how T3.2 produced this defect.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.embed_rewrite import rewrite_renamed_embeds  # noqa: E402
from lib.render_actions import _build_move_asset_actions  # noqa: E402
from lib.typed_name_check import check_typed_name  # noqa: E402

SOURCE = "100 Inbox/Scans/karte.png"
INBOX = "100 Inbox/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"

# One body, two embeds of the same attachment, the second carrying a `|300`
# size suffix — both shapes 037 already covers for a computed name, kept here
# so a refusal is proven not to touch either of them.
BODY = "Map: ![[karte.png]]\n\nAgain, sized: ![[karte.png|300]]\n"

# A name Obsidian would accept, used for the positive case.
ACCEPTED_TYPED_NAME = "karte-dresden-1938.png"

# The three refusal classes, each with the REFUSAL_REASONS code it must
# produce. A test that only asserted "body unchanged" could pass because the
# basename failed to match rather than because the gate fired, so each test
# pins the verdict too.
SEPARATOR_TYPED_NAME = "Archive/karte-dresden-1938.png"
FORBIDDEN_TYPED_NAME = "karte|1938.png"
BLANK_TYPED_NAME = "   "


def _remedy(proposed_name, *, name_is_owner_supplied=None, source=SOURCE) -> dict:
    entry = {
        "source": source,
        "remedy": "rename",
        "proposed_name": proposed_name,
    }
    if name_is_owner_supplied is not None:
        entry["name_is_owner_supplied"] = name_is_owner_supplied
    return entry


def _manifest_entry(sid, source_path, attachments) -> dict:
    return {
        "id": sid,
        "action": None,
        "title": "Karte",
        "source_path": source_path,
        "rendered_file": f"2026-01-01_0900_{sid}.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
        "attachments": attachments,
    }


# ---------------------------------------------------------------------------
# The three refusal classes, separately. Each leaves the body byte-identical.
# ---------------------------------------------------------------------------


def test_refused_separator_present_leaves_body_byte_identical():
    """A typed name carrying a path separator rewrites nothing.

    Mutation: delete the `check_typed_name` gate from the loop in
    `rewrite_renamed_embeds` that builds `renames`. The body then becomes
    `![[Archive/karte-dresden-1938.png]]` — dangling, and hard-coding a
    folder into the body, which this function's own docstring promises never
    to do.
    """
    verdict = check_typed_name(SEPARATOR_TYPED_NAME)
    assert verdict.ok is False
    assert verdict.reason == "separator_present"

    remedies = {SOURCE: _remedy(SEPARATOR_TYPED_NAME, name_is_owner_supplied=True)}
    assert rewrite_renamed_embeds(BODY, [SOURCE], remedies) == BODY


def test_refused_forbidden_character_leaves_body_byte_identical():
    """A typed name carrying `|` rewrites nothing — the quiet one.

    Mutation: delete the `check_typed_name` gate. The body then becomes
    `![[karte|1938.png]]` and `![[karte|1938.png|300]]`, which Obsidian
    reads as an embed of a note named `karte` aliased `1938.png` — not a
    dangling link that announces itself, but real content from the wrong
    file. This is the refusal class a single representative test would have
    hidden.
    """
    verdict = check_typed_name(FORBIDDEN_TYPED_NAME)
    assert verdict.ok is False
    assert verdict.reason == "forbidden_character"

    remedies = {SOURCE: _remedy(FORBIDDEN_TYPED_NAME, name_is_owner_supplied=True)}
    assert rewrite_renamed_embeds(BODY, [SOURCE], remedies) == BODY


def test_refused_blank_leaves_body_byte_identical():
    """A whitespace-only typed name rewrites nothing.

    `"   "` is truthy, so the existing falsy-`proposed_name` check does not
    stop it — only `check_typed_name`'s `blank` verdict does. Mutation:
    delete the gate and the body becomes `![[   ]]`, an embed of
    whitespace. A second mutation this also catches: gate on
    `proposed_name.strip()` being falsy instead of on the verdict, which
    would stop this case but neither of the two above.
    """
    verdict = check_typed_name(BLANK_TYPED_NAME)
    assert verdict.ok is False
    assert verdict.reason == "blank"

    remedies = {SOURCE: _remedy(BLANK_TYPED_NAME, name_is_owner_supplied=True)}
    assert rewrite_renamed_embeds(BODY, [SOURCE], remedies) == BODY


# ---------------------------------------------------------------------------
# The positive case, and the regression floor.
# ---------------------------------------------------------------------------


def test_accepted_typed_name_rewrites_every_embed_including_the_sized_one():
    """An accepted typed name still rewrites every embed, as 037 does for a
    computed name — both occurrences, and the `|300` suffix survives.

    Mutation: gate on `name_is_owner_supplied` alone and skip every typed
    name without consulting the verdict. That would refuse a usable name
    and strand the renamed file: F2 requires the owner's accepted edit to
    reach the body.
    """
    assert check_typed_name(ACCEPTED_TYPED_NAME).ok is True

    remedies = {SOURCE: _remedy(ACCEPTED_TYPED_NAME, name_is_owner_supplied=True)}
    assert rewrite_renamed_embeds(BODY, [SOURCE], remedies) == (
        "Map: ![[karte-dresden-1938.png]]\n"
        "\n"
        "Again, sized: ![[karte-dresden-1938.png|300]]\n"
    )


def test_computed_name_still_rewrites_when_flag_is_false():
    """The regression floor, unchanged from 037: a Tomo-computed name is
    never checked, so a basename `check_typed_name` would refuse still
    rewrites when the flag says the owner did not type it.

    `_propose_asset_name` (suggestions-reducer.py) sanitises nothing and can
    legally emit `foo*bar (2).png`; refusing it here would violate F3's
    ninth criterion ("this feature constrains typed names only"). Mutation:
    run the check unconditionally, or default a False flag to True.
    """
    computed = "foo*bar (2).png"
    assert check_typed_name(computed).ok is False  # would be refused if typed

    remedies = {SOURCE: _remedy(computed, name_is_owner_supplied=False)}
    assert rewrite_renamed_embeds(BODY, [SOURCE], remedies) == (
        "Map: ![[foo*bar (2).png]]\n\nAgain, sized: ![[foo*bar (2).png|300]]\n"
    )


def test_computed_name_still_rewrites_when_flag_is_absent():
    """A remedy record predating `name_is_owner_supplied` (the key absent
    entirely — an older or foreign producer) must behave like False, not
    like True.

    Mutation: read the flag with a truthy default instead of letting
    `.get(...)` return `None`. Every pre-038 remedy record would then stop
    rewriting bodies, silently regressing 037 T3.3.
    """
    computed = "foo*bar (2).png"
    remedies = {SOURCE: _remedy(computed)}  # no flag key at all
    assert rewrite_renamed_embeds(BODY, [SOURCE], remedies) == (
        "Map: ![[foo*bar (2).png]]\n\nAgain, sized: ![[foo*bar (2).png|300]]\n"
    )


# ---------------------------------------------------------------------------
# The agreement test. Do not fold this into another case.
# ---------------------------------------------------------------------------


def test_both_halves_refuse_the_same_typed_name():
    """One refused name, fed to BOTH halves: the move builder emits
    `typed_name_refused` AND the body comes back byte-identical.

    This is the only test that sees the two gate conditions drift apart.
    `check_typed_name` is now called from `rewrite_renamed_embeds` and from
    `_build_move_asset_actions` and nothing in the type system keeps them
    agreeing; T3.2 produced this defect precisely by changing one and not
    the other. Mutation: change either half's condition — gate the rewrite
    on `proposed_name` containing `/` instead of on the verdict, say, and
    this test fails on the `|` name while every per-half test still passes.
    """
    remedy = _remedy(FORBIDDEN_TYPED_NAME, name_is_owner_supplied=True)

    actions, skipped = _build_move_asset_actions(
        [_manifest_entry("S01", "karte.md", [SOURCE])],
        INBOX,
        ASSET_FOLDER,
        [0],
        attachment_conflict_remedies=[remedy],
    )
    assert actions == [], f"a refused typed name must emit no move: {actions}"
    assert len(skipped) == 1
    assert skipped[0]["source"] == SOURCE
    assert skipped[0]["kind"] == "typed_name_refused"
    assert skipped[0]["refusal_reason"] == "forbidden_character"

    assert rewrite_renamed_embeds(BODY, [SOURCE], {SOURCE: remedy}) == BODY


def test_both_halves_accept_the_same_typed_name():
    """The agreement test's other direction: an accepted typed name must
    produce a move whose destination basename is exactly what the rewritten
    embed now points at.

    Without this, a gate that refused everything would satisfy the refusal
    half of agreement trivially. Mutation: make either half's accept
    condition stricter than the other's — the destination basename and the
    embed target stop matching and this fails, while both refusal tests
    still pass.
    """
    remedy = _remedy(ACCEPTED_TYPED_NAME, name_is_owner_supplied=True)

    actions, skipped = _build_move_asset_actions(
        [_manifest_entry("S01", "karte.md", [SOURCE])],
        INBOX,
        ASSET_FOLDER,
        [0],
        attachment_conflict_remedies=[remedy],
    )
    assert skipped == [], f"an accepted typed name must be filed: {skipped}"
    assert len(actions) == 1
    assert actions[0]["destination"] == f"{ASSET_FOLDER}{ACCEPTED_TYPED_NAME}"

    rewritten = rewrite_renamed_embeds(BODY, [SOURCE], {SOURCE: remedy})
    assert rewritten == (
        "Map: ![[karte-dresden-1938.png]]\n"
        "\n"
        "Again, sized: ![[karte-dresden-1938.png|300]]\n"
    )
    # The body's new target and the move's destination basename are the same
    # string — the bare basename, never the full destination path.
    assert f"![[{actions[0]['destination'].rsplit('/', 1)[-1]}]]" in rewritten
