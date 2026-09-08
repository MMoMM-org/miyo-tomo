#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_0_case_folded_destination_keys.py — spec 034 T6.0.

Phase 5 folded case into three destination comparisons and left three more.
CON-6 records this filesystem as case-insensitive, so each of the three is a
live data-loss path today. This module pins all three, plus the pair that makes
the third one safe.

What each block pins:

  1. `_build_create_moc_actions`'s `by_dest` — `Travel (MOC)` and
     `travel (MOC)` in one folder are one destination. Without the fold the
     second create_moc overwrites the first on apply, dropping the first's
     children: the `#67` failure that guard was written for.
  2. `resolve_section_names`'s `create_moc_by_dest` — the paired consumer of
     (1). A `link_to_moc` whose `target_moc_path` differs only in case from an
     in-set `create_moc`'s destination must still find that create_moc's
     template for the anchor fallback. Folded together with (1) deliberately:
     a fold on one without the other re-creates the emitter/consumer divergence
     T5.0b/T5.0c already paid for.
  3. `_build_move_asset_actions`'s `claimed` — `Reise/Ufer.jpg` and
     `Bilder/ufer.jpg` compose one destination. The fold is not the point; the
     recorded skip is. T5.4's `suppress_moves_for_unfiled_attachments` triggers
     on a recorded skip, so without the fold the second attachment is
     overwritten AND its note is filed away from it, with nothing reported.
  4. The `seen` / `claimed` pair. `seen` keys the SOURCE path and stays exact:
     folding it would collapse two genuinely distinct files on a case-sensitive
     filesystem and drop one with no skip recorded at all — the exact silence
     T5.4 exists to break, re-created one layer up. Leaving it exact is only
     safe because `claimed` folds: the second sighting then meets a claimed
     destination and is reported. This block pins that no path is dropped
     without either a move or a skip.
  5. Nothing folded is ever displayed. `_CASE_NOTE` promises the user always
     reads the real spelling; folding is for comparison keys only.

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
    _build_create_moc_actions,
    _build_move_asset_actions,
    build_actions,
    suppress_moves_for_unfiled_attachments,
)
from lib.render_resolve import (  # noqa: E402
    resolve_section_names,
    resolve_target_moc_paths,
)

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
INBOX = "100 Inbox/"
MOC_FOLDER = "Atlas/200 Maps/"
EDITABLE_CALLOUTS = ["connect", "blocks", "anchor"]

CFG = {
    "concepts.inbox": INBOX,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}

TEMPLATE_BODY = "\n".join([
    "# {{title}}",
    "",
    "> [!blocks] Key Concepts",
    "> ",
    "",
])


class StubClient:
    """Minimal Kado-shaped stub. `read_note` raises for anything not in
    `notes`, which is how the live-MOC tier is made to miss so the
    template-body fallback is the only path that can resolve the anchor."""

    def __init__(self, notes: dict[str, str] | None = None) -> None:
        self.notes = notes or {}
        self.read_calls: list[str] = []

    def read_note(self, path: str) -> dict:
        self.read_calls.append(path)
        if path in self.notes:
            return {"content": self.notes[path]}
        raise FileNotFoundError(f"stub: not found: {path}")

    def search_by_name(self, stem: str) -> list[dict]:
        return []


def _moc_entry(title: str, rendered_file: str, supporting_items) -> dict:
    return {
        "id": "S01",
        "action": "create_moc",
        "title": title,
        "rendered_file": rendered_file,
        "destination": MOC_FOLDER,
        "parent_moc": "",
        "template": "t_moc_tomo",
        "tags": [],
        "supporting_items": supporting_items,
    }


def _manifest_entry(*, source_path, rendered_file, attachments=None, **overrides) -> dict:
    entry = {
        "id": "S01",
        "action": None,
        "title": "Some Note",
        "source_path": source_path,
        "rendered_file": rendered_file,
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
    }
    if attachments is not None:
        entry["attachments"] = attachments
    entry.update(overrides)
    return entry


def _confirmed_entry(**overrides) -> dict:
    entry = {
        "id": "S01",
        "action": None,
        "title": "Some Note",
        "source_path": "some-note.md",
        "parent_mocs": [],
        "tags": [],
        "candidate_mocs": [],
    }
    entry.update(overrides)
    return entry


# ──────────────────────────────────────────────────────────────────────────
# 1. by_dest — two MOC proposals differing only in case are one destination
# ──────────────────────────────────────────────────────────────────────────

def test_create_moc_by_dest_folds_case():
    """`Travel (MOC)` and `travel (MOC)` in one folder emit ONE create_moc,
    and the survivor carries both proposals' supporting_items.

    Fails with the exact-string key: two create_moc at the same destination
    reach Hashi, and the second overwrites the first on apply — dropping the
    first's children (#67)."""
    manifest = [
        _moc_entry("Travel (MOC)", "2026-01-01_0900_travel-moc.md", ["Dresden"]),
        _moc_entry("travel (MOC)", "2026-01-01_0901_travel-moc.md", ["Kyoto"]),
    ]
    actions = _build_create_moc_actions(manifest, INBOX, [0])
    assert len(actions) == 1, (
        "two proposals differing only in case claim one destination on a "
        f"case-insensitive filesystem (CON-6): {actions}"
    )
    assert actions[0]["supporting_items"] == ["Dresden", "Kyoto"], (
        "the survivor must carry the merged proposal's children, not drop "
        f"them: {actions[0]['supporting_items']}"
    )


def test_create_moc_survivor_keeps_the_spelling_its_author_wrote():
    """Folding is for comparison keys only. Nothing folded may reach a
    `destination`, a `title`, or a `source` — `_CASE_NOTE` promises the user
    always reads the real spelling."""
    manifest = [
        _moc_entry("Travel (MOC)", "2026-01-01_0900_travel-moc.md", ["Dresden"]),
        _moc_entry("travel (MOC)", "2026-01-01_0901_travel-moc.md", ["Kyoto"]),
    ]
    actions = _build_create_moc_actions(manifest, INBOX, [0])
    assert actions[0]["destination"] == "Atlas/200 Maps/Travel (MOC).md"
    assert actions[0]["title"] == "Travel (MOC)"
    assert actions[0]["source"] == "100 Inbox/2026-01-01_0900_travel-moc.md"


def test_create_moc_distinct_destinations_are_not_folded_together():
    """The fold must not swallow genuinely different names — a guard that
    merges everything would pass the two tests above."""
    manifest = [
        _moc_entry("Travel (MOC)", "2026-01-01_0900_travel-moc.md", ["Dresden"]),
        _moc_entry("Cooking (MOC)", "2026-01-01_0901_cooking-moc.md", ["Kyoto"]),
    ]
    actions = _build_create_moc_actions(manifest, INBOX, [0])
    assert len(actions) == 2
    assert [a["title"] for a in actions] == ["Travel (MOC)", "Cooking (MOC)"]


# ──────────────────────────────────────────────────────────────────────────
# 2. create_moc_by_dest — the paired consumer must fold with (1)
# ──────────────────────────────────────────────────────────────────────────

def test_link_to_moc_finds_its_in_set_create_moc_across_case():
    """A `link_to_moc` targeting `.../travel (MOC).md` must find the in-set
    `create_moc` landing at `.../Travel (MOC).md` and resolve its anchor from
    that create_moc's template.

    The live MOC does not exist in the stub, so the template-body fallback is
    the only tier that can resolve — which makes the lookup, not the anchor
    picker, what this asserts. Fails with the exact-string key and lookup: the
    anchor stays unpopulated and Hashi is handed an unplaceable bullet."""
    client = StubClient(notes={"Atlas/900 Templates/t_moc_tomo.md": TEMPLATE_BODY})
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "destination": "Atlas/200 Maps/Travel (MOC).md",
            "title": "Travel (MOC)",
            "template": "Atlas/900 Templates/t_moc_tomo.md",
        },
        {
            "id": "I02",
            "action": "link_to_moc",
            "target_moc": "travel (MOC)",
            "target_moc_path": "Atlas/200 Maps/travel (MOC).md",
            "anchor": {"type": "callout", "value": None},
            "placement": "inside",
            "line_to_add": "- [[Dresden]]",
        },
    ]
    resolved = resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    assert resolved == 1, (
        "the create_moc index keys the same composed destination by exact "
        f"string, so the template fallback found nothing: {actions[1]['anchor']}"
    )
    assert actions[1]["anchor"]["value"] == "[!blocks] Key Concepts"


def test_link_to_moc_does_not_borrow_an_unrelated_create_mocs_template():
    """The lookup folds case; it must not match on anything looser."""
    client = StubClient(notes={"Atlas/900 Templates/t_moc_tomo.md": TEMPLATE_BODY})
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "destination": "Atlas/200 Maps/Cooking (MOC).md",
            "title": "Cooking (MOC)",
            "template": "Atlas/900 Templates/t_moc_tomo.md",
        },
        {
            "id": "I02",
            "action": "link_to_moc",
            "target_moc": "Travel (MOC)",
            "target_moc_path": "Atlas/200 Maps/Travel (MOC).md",
            "anchor": {"type": "callout", "value": None},
            "placement": "inside",
            "line_to_add": "- [[Dresden]]",
        },
    ]
    assert resolve_section_names(actions, client, EDITABLE_CALLOUTS) == 0
    assert actions[1]["anchor"]["value"] is None


# ──────────────────────────────────────────────────────────────────────────
# 3. claimed — the fold re-arms T5.4's guard
# ──────────────────────────────────────────────────────────────────────────

def test_case_only_attachment_collision_records_a_skip(capsys):
    """`Reise/Ufer.jpg` and `Bilder/ufer.jpg` compose one destination on a
    case-insensitive filesystem (CON-6). One move_asset is emitted and the
    refused file IS recorded as a collision skip naming its owning note.

    Fails with the exact-string key: both are emitted, the second overwrites
    the first in the asset folder, and `skipped` is empty — so nothing
    downstream can report or compensate."""
    manifest = [
        _manifest_entry(
            source_path="reise.md", rendered_file="2026-01-01_0900_reise.md",
            attachments=["100 Inbox/Reise/Ufer.jpg"],
        ),
        _manifest_entry(
            source_path="bilder.md", rendered_file="2026-01-01_0901_bilder.md",
            attachments=["100 Inbox/Bilder/ufer.jpg"],
        ),
    ]
    actions, skipped = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Reise/Ufer.jpg"
    assert actions[0]["destination"] == "Atlas/290 Assets/295 Attachments/Ufer.jpg", (
        "the surviving destination keeps the basename verbatim — a folded "
        "string must never reach a destination"
    )
    assert len(skipped) == 1, f"no skip recorded, so T5.4 has no trigger: {skipped}"
    assert skipped[0]["kind"] == "collision"
    assert skipped[0]["source"] == "100 Inbox/Bilder/ufer.jpg"
    assert skipped[0]["owner_source_items"] == ["100 Inbox/bilder.md"]
    # The user reads both spellings as their authors wrote them.
    assert "100 Inbox/Bilder/ufer.jpg" in skipped[0]["reason"]
    assert "100 Inbox/Reise/Ufer.jpg" in skipped[0]["reason"]
    assert "collision" in capsys.readouterr().err.lower()


def test_case_only_attachment_collision_suppresses_the_second_notes_move():
    """The point is the re-armed guard, not the fold. Feeding the recorded
    skip to T5.4's suppression must keep the second note in the inbox with the
    file it embeds — the first note, whose attachment was filed, still moves."""
    manifest = [
        _manifest_entry(
            source_path="reise.md", rendered_file="2026-01-01_0900_reise.md",
            attachments=["100 Inbox/Reise/Ufer.jpg"],
        ),
        _manifest_entry(
            source_path="bilder.md", rendered_file="2026-01-01_0901_bilder.md",
            attachments=["100 Inbox/Bilder/ufer.jpg"],
        ),
    ]
    confirmed = [
        _confirmed_entry(source_path="reise.md"),
        _confirmed_entry(source_path="bilder.md"),
    ]
    actions, skipped_assets = build_actions(manifest, confirmed, [], [], CFG)
    kept, suppressions = suppress_moves_for_unfiled_attachments(actions, skipped_assets)
    move_notes = [a for a in kept if a["action"] == "move_note"]
    assert [m["source_inbox_item"] for m in move_notes] == ["100 Inbox/reise.md"], (
        "bilder.md's attachment was refused, so bilder.md stays in the inbox "
        f"with it: {move_notes}"
    )
    assert [d["source_inbox_item"] for d in suppressions[0]["dropped"]] == [
        "100 Inbox/bilder.md",
    ]


# ──────────────────────────────────────────────────────────────────────────
# 4. the seen / claimed pair — `seen` stays exact
# ──────────────────────────────────────────────────────────────────────────

def test_case_differing_sources_in_one_folder_are_each_accounted_for(capsys):
    """`100 Inbox/Ufer.jpg` and `100 Inbox/ufer.jpg` differ only in case in the
    SAME folder — one file seen twice on this filesystem, two distinct files on
    a case-sensitive one.

    `seen` keys the source and stays exact, so the second is examined; it then
    meets a folded `claimed` and is recorded as a collision skip. Every path is
    accounted for by either a move or a skip.

    Fails if `seen` is ALSO folded: the second path is never examined, so it
    gets neither a move nor a skip and vanishes with nothing reported — the
    silence T5.4's guard exists to break."""
    manifest = [
        _manifest_entry(
            source_path="a.md", rendered_file="2026-01-01_0900_a.md",
            attachments=["100 Inbox/Ufer.jpg"],
        ),
        _manifest_entry(
            source_path="b.md", rendered_file="2026-01-01_0901_b.md",
            attachments=["100 Inbox/ufer.jpg"],
        ),
    ]
    actions, skipped = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    capsys.readouterr()
    assert len(actions) == 1
    assert len(skipped) == 1

    every_path = {p for m in manifest for p in m["attachments"]}
    accounted = {a["source"] for a in actions} | {s["source"] for s in skipped}
    assert accounted == every_path, (
        "every attachment path must leave this pass with either a move or a "
        f"skip; unaccounted: {every_path - accounted}"
    )


def test_one_file_embedded_by_two_notes_is_still_a_dedup_not_a_collision(capsys):
    """The exact-`seen` dedup is untouched: the same path embedded twice is
    filed once and reported as nothing."""
    manifest = [
        _manifest_entry(
            source_path="a.md", rendered_file="2026-01-01_0900_a.md",
            attachments=["100 Inbox/Reise/Ufer.jpg"],
        ),
        _manifest_entry(
            source_path="b.md", rendered_file="2026-01-01_0901_b.md",
            attachments=["100 Inbox/Reise/Ufer.jpg"],
        ),
    ]
    actions, skipped = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    assert skipped == []
    assert "collision" not in capsys.readouterr().err.lower()


# ──────────────────────────────────────────────────────────────────────────
# 2b. resolve_target_moc_paths' in_set — the OTHER paired consumer of (1)
# ──────────────────────────────────────────────────────────────────────────

def test_link_to_moc_resolves_its_path_from_the_surviving_create_moc():
    """`resolve_target_moc_paths` indexes in-set create_moc actions by title
    stem, and runs BEFORE `resolve_section_names` in `instruction-render.py`.

    Folding `by_dest` means the proposal titled `travel (MOC)` no longer emits
    a create_moc — its children were unioned into `Travel (MOC)`. A
    `link_to_moc` minted against `travel (MOC)` must still find where that MOC
    will actually land. Without this fold it misses tier 1, misses tier 2 (the
    MOC does not exist yet), keeps `target_moc_path: null`, and is dropped by
    `filter_unappliable_relationships` — so folding (1) would silently cost the
    note its bullet in the MOC.

    This is the same emitter/consumer divergence the task warns about, at a
    consumer the task's three sites do not name."""
    client = StubClient()
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "destination": "Atlas/200 Maps/Travel (MOC).md",
            "title": "Travel (MOC)",
        },
        {
            "id": "I02",
            "action": "link_to_moc",
            "target_moc": "travel (MOC)",
            "target_moc_path": None,
            "line_to_add": "- [[Dresden]]",
        },
    ]
    resolved = resolve_target_moc_paths(actions, client)
    assert resolved == 1, (
        "the in-set index keys the title stem by exact string, so the link "
        f"lost the MOC the fold merged it into: {actions[1]['target_moc_path']}"
    )
    assert actions[1]["target_moc_path"] == "Atlas/200 Maps/Travel (MOC).md", (
        "the resolved path is the survivor's own spelling — nothing folded is "
        "ever written back into an action"
    )


def test_link_to_moc_does_not_resolve_against_an_unrelated_in_set_moc():
    """The in-set fold matches case, nothing looser."""
    client = StubClient()
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "destination": "Atlas/200 Maps/Cooking (MOC).md",
            "title": "Cooking (MOC)",
        },
        {
            "id": "I02",
            "action": "link_to_moc",
            "target_moc": "Travel (MOC)",
            "target_moc_path": None,
            "line_to_add": "- [[Dresden]]",
        },
    ]
    assert resolve_target_moc_paths(actions, client) == 0
    assert actions[1]["target_moc_path"] is None
