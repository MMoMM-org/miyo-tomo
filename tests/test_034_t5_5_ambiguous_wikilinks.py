#!/usr/bin/env python3
# version: 1.0.0
"""test_034_t5_5_ambiguous_wikilinks.py — spec 034 T5.5.

T5.1's defect at two sites T5.1's scope did not cover. It qualified source
links in the **suggestions** document; these are in the **instructions**
document, which is the one carrying irreversible actions and the one whose
output is written into the vault.

  1. `**Source:** [[Dresden]]` on a `delete_source`, with three Dresden notes
     in the run. The action itself is correct — `source_path` is the resolved
     `100 Inbox/Quellen/Dresden.md` and T5.0b's addressing holds — but under
     CON-2 the user approves on what the document SAYS, and here they tick an
     irreversible delete unable to tell which of three notes it removes. The
     same bare display is rendered for a `move_note`'s source reference and a
     `skip`, which is the same sentence at two more sites.
  2. `line_to_add: "- [[Dresden]]"` on a `link_to_moc`. This one is written
     into a MOC permanently. It resolves today because only one Dresden
     survives the destination guard; it stops resolving the moment the user
     renames one withheld claimant and re-runs, because the OTHER withheld
     claimant then files as `Atlas/202 Notes/Dresden.md`. The ambiguity
     arrives after the instruction is applied, in a note nobody revisits.

Both use T5.1's `[[<path>|<display>]]` form and T5.1's collision-only rule, so
a run without namesakes renders byte-identically — the two goldens pin that.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import (  # noqa: E402
    build_actions,
    contested_note_names,
    qualify_contested_moc_links,
    validate_destinations,
)
from lib.render_md import render_instructions_md  # noqa: E402
from lib.source_link import colliding_names, qualified_target  # noqa: E402

NOTES = "Atlas/202 Notes/"
SOURCES = "Atlas/203 Sources/"
INBOX = "100 Inbox/"
TRAVEL = "Travel (MOC)"

DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
DRESDEN_QUELLEN = "100 Inbox/Quellen/Dresden.md"
ROOT_NOTE = "100 Inbox/Root Note.md"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


def _atomic(item_key: str, title: str, *, idx: int, parents: list[str] | None = None,
            location: str = NOTES) -> tuple[dict, dict]:
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-07_10{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": location,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "tags": [],
        "attachments": [],
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "attachments": [],
    }
    return manifest, confirmed


def _build(pairs, **kw):
    return build_actions(
        [m for m, _ in pairs], [c for _, c in pairs],
        kw.pop("daily_updates", []), kw.pop("skipped", []),
        CFG, kado_client=None,
    )


def _render(actions, **kw) -> str:
    return render_instructions_md(
        actions,
        {
            "run_id": "t5-5",
            "generated": "2026-09-07T14:04:49Z",
            "profile": "miyo",
            "sources": [{"path": "100 Inbox/_suggestions.md"}],
            "destination_clashes": [],
            "attachment_suppressions": [],
            **kw,
        },
        CFG,
    )


def _field(md: str, label: str) -> list[str]:
    prefix = f"- **{label}:** "
    return [ln[len(prefix):] for ln in md.splitlines() if ln.startswith(prefix)]


def _bullets(actions) -> list[str]:
    return [
        a.get("line_to_add") for a in actions if a.get("action") == "link_to_moc"
    ]


# Three notes named Dresden: two claim `Atlas/202 Notes/Dresden.md` (and are
# withheld by the destination guard), one files to `Atlas/203 Sources/`.
THREE_DRESDENS = [
    _atomic(DRESDEN_PLACES, "Dresden", idx=1, parents=[TRAVEL]),
    _atomic(DRESDEN_REISE, "Dresden", idx=2, parents=[TRAVEL]),
    _atomic(DRESDEN_QUELLEN, "Dresden", idx=3, parents=[TRAVEL], location=SOURCES),
    _atomic(ROOT_NOTE, "Root note takeaway", idx=4, parents=[TRAVEL]),
]


# ---------------------------------------------------------------------------
# The shared primitives (extracted from T5.1)
# ---------------------------------------------------------------------------

def test_one_note_named_twice_in_a_document_is_not_a_collision():
    """A `move_note`'s source reference and its `delete_source` name the same
    origin. Counting occurrences would qualify a link that is not ambiguous."""
    assert colliding_names([
        ("Root Note", ROOT_NOTE), ("Root Note", ROOT_NOTE),
    ]) == set()


def test_two_paths_under_one_name_collide():
    assert colliding_names([
        ("Dresden", DRESDEN_PLACES), ("Dresden", DRESDEN_REISE),
        ("Root Note", ROOT_NOTE),
    ]) == {"Dresden"}


def test_the_qualified_target_drops_md_and_keeps_the_display():
    assert qualified_target(DRESDEN_PLACES, "Dresden") == (
        "100 Inbox/Places/Dresden|Dresden"
    )


# ---------------------------------------------------------------------------
# 1. The instruction document says WHICH note it is about
# ---------------------------------------------------------------------------

def test_a_delete_names_which_of_three_namesakes_it_removes():
    actions, _ = _build(THREE_DRESDENS)
    kept, clashes = validate_destinations(actions)
    sources = _field(_render(kept, destination_clashes=clashes), "Source")
    assert f"[[{DRESDEN_QUELLEN[:-3]}|Dresden]]" in sources, (
        "an irreversible delete the user approves on this document may not "
        f"leave them guessing which of three Dresden notes it removes: {sources}"
    )
    assert "[[Dresden]]" not in sources, sources


def test_a_move_names_which_namesake_it_files():
    actions, _ = _build(THREE_DRESDENS)
    kept, clashes = validate_destinations(actions)
    refs = _field(_render(kept, destination_clashes=clashes), "Source (reference)")
    assert f"[[{DRESDEN_QUELLEN[:-3]}|Dresden]]" in refs, (
        f"the same bare display, one action kind over: {refs}"
    )
    assert "[[Root Note]]" in refs, ("and the unique one stays bare: {refs}".format(refs=refs))


def test_a_skip_names_which_namesake_stays_behind():
    skipped = [
        {"source_path": "Dresden", "item_key": DRESDEN_PLACES,
         "disposition": "skip", "reason": "Not actionable."},
        {"source_path": "Dresden", "item_key": DRESDEN_REISE,
         "disposition": "skip", "reason": "Not actionable."},
    ]
    actions, _ = _build([], skipped=skipped)
    sources = _field(_render(actions), "Source")
    assert sorted(sources) == [
        f"[[{DRESDEN_PLACES[:-3]}|Dresden]]",
        f"[[{DRESDEN_REISE[:-3]}|Dresden]]",
    ], sources


def test_a_unique_filename_still_renders_a_bare_link():
    actions, _ = _build([_atomic(ROOT_NOTE, "Root note takeaway", idx=1)])
    md = _render(actions)
    assert "[[Root Note]]" in md, md
    assert "|Root Note]]" not in md, (
        "qualification is collision-only; a run without namesakes must render "
        f"byte-identically:\n{md}"
    )


def test_the_delete_heading_still_names_the_bare_note():
    """The heading is an index entry, not a link — a path in it would make the
    section unscannable, and the `**Source:**` line beneath carries the path."""
    actions, _ = _build(THREE_DRESDENS)
    kept, clashes = validate_destinations(actions)
    headings = [
        ln for ln in _render(kept, destination_clashes=clashes).splitlines()
        if ln.startswith("### ") and "Delete source note" in ln
    ]
    assert any(ln.endswith("Delete source note: Dresden") for ln in headings), headings


# ---------------------------------------------------------------------------
# 2. The bullet written into the MOC says WHICH note, permanently
# ---------------------------------------------------------------------------

def _guarded(pairs):
    """The pipeline order: build, capture the claim set, withhold, qualify."""
    actions, _skipped = _build(pairs)
    contested = contested_note_names(actions)
    kept, clashes = validate_destinations(actions)
    qualify_contested_moc_links(kept, contested)
    return kept, clashes


def test_the_moc_bullet_names_the_path_when_the_run_claims_the_name_twice():
    kept, _clashes = _guarded(THREE_DRESDENS)
    bullets = _bullets(kept)
    assert f"- [[{SOURCES}Dresden|Dresden]]" in bullets, (
        "this bullet is written into a MOC permanently; a bare [[Dresden]] "
        "stops resolving as soon as a withheld claimant is renamed and "
        f"re-filed: {bullets}"
    )


def test_the_claim_set_includes_the_withheld_claimants():
    """Run-scope is only sufficient if it is taken BEFORE the withholding —
    the withheld twin is exactly the note that comes back."""
    kept, clashes = _guarded(THREE_DRESDENS)
    assert len(clashes) == 1 and len(clashes[0]["dropped"]) == 2, clashes
    assert f"- [[{SOURCES}Dresden|Dresden]]" in _bullets(kept), _bullets(kept)


def test_a_bullet_for_a_unique_title_stays_bare():
    kept, _clashes = _guarded(THREE_DRESDENS)
    assert "- [[Root note takeaway]]" in _bullets(kept), _bullets(kept)


def test_the_coverage_audit_still_credits_a_qualified_bullet():
    """`_bullet_titles` reads the alias; the audit keys per-item coverage on
    it, so a qualified bullet must still credit its note."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "instructions_diff_ambig", SCRIPTS_DIR / "instructions-diff.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["instructions_diff_ambig"] = mod
    spec.loader.exec_module(mod)
    kept, _clashes = _guarded(THREE_DRESDENS)
    summary = mod.summarize_actual({"actions": kept})
    assert "Dresden" in summary["links_by_source"], summary["links_by_source"]


def test_the_bullet_never_names_a_withheld_claimants_path():
    """The claim set is taken before the guard, the path after it. Naming the
    withheld claimant's destination would point the bullet at a note the guard
    just guaranteed will not exist — worse than the bare link it replaces."""
    kept, _clashes = _guarded(THREE_DRESDENS)
    assert f"- [[{NOTES}Dresden|Dresden]]" not in _bullets(kept), _bullets(kept)


def test_a_sanitised_title_keeps_its_alias_under_a_contested_filename():
    """`_wikilink` already uses the alias slot for a forbidden-char title. The
    path form uses the same slot, so the two must compose, not collide."""
    pairs = [
        _atomic("100 Inbox/A/Q.md", "Q: one", idx=1, parents=[TRAVEL]),
        _atomic("100 Inbox/B/Q.md", "Q: one", idx=2, parents=[TRAVEL],
                location=SOURCES),
    ]
    kept, _clashes = _guarded(pairs)
    bullets = _bullets(kept)
    assert len(bullets) == 1, bullets
    target, _, alias = bullets[0][len("- [["):-2].partition("|")
    assert alias == "Q: one", bullets
    # `_dest_join` stores the note under the sanitised stem, so the PATH ends
    # in it while the alias keeps the title the user wrote.
    assert target == f"{NOTES}Q- one", bullets


def test_a_contested_name_with_no_surviving_move_is_left_alone():
    """Both claimants withheld: there is no path to name the note by, and the
    bullet is withdrawn by the withholding pass anyway."""
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, parents=[TRAVEL]),
        _atomic(DRESDEN_REISE, "Dresden", idx=2, parents=[TRAVEL]),
    ]
    kept, clashes = _guarded(pairs)
    assert len(clashes) == 1, clashes
    assert _bullets(kept) == [], _bullets(kept)
