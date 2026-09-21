#!/usr/bin/env python3
# version: 0.1.0
"""test_036_t2_2_orphaned_moc_link_target.py — spec 036, T2.2 code-quality finding.

T2.2 widened `validate_destinations`' claimant filter to `{move_note,
create_moc}` (`tomo/scripts/lib/render_actions.py`), so a `create_moc` can now
be dropped for contesting a destination — that is the point of the task. What
was not widened with it: `_drop_moves_with_paired_deletes` only withdraws a
`link_to_moc` bullet when its **author** was dropped (`_orphaned_link_titles`,
keyed on `source_note_stem`). Nothing checks the bullet's `target_moc`, so a
dropped `create_moc` can leave a surviving `link_to_moc` that instructs Hashi
to insert a bullet into a MOC note that will never exist — the exact failure
`filter_unresolvable_moc_links` (`render_resolve.py`) was written to prevent,
reached by a different path.

This file pins the fix: withdraw a `link_to_moc` whose `target_moc` names a
dropped `create_moc`'s title, alongside the existing author-keyed withdrawal
(`_orphaned_link_titles`, spec 034 T5.5 — untouched by this file).

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
    make_folder_listing,
    validate_destinations,
)

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"

DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
ELBE = "100 Inbox/Elbe.md"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


class FakeKado:
    """`list_dir` only — the one call the vault half of the guard makes."""

    def __init__(self, occupied: set[str] | None = None):
        self.occupied = occupied or set()

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500):
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]


def _atomic(item_key: str, title: str, *, idx: int,
            parents: list[str] | None = None,
            location: str = NOTES) -> tuple[dict, dict]:
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-16_10{idx:02d}_{title.lower().replace(' ', '-')}.md",
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
    }
    return manifest, confirmed


def _moc(title: str, *, idx: int, location: str = NOTES) -> tuple[dict, dict]:
    """A `create_moc` manifest entry — mirrors `_moc` in
    test_034_t5_3_destination_validation.py. `create_moc` has no confirmed-item
    counterpart, so the confirmed half is empty."""
    manifest = {
        "action": "create_moc",
        "title": title,
        "rendered_file": f"2026-09-16_20{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": location,
        "parent_moc": None,
        "template": None,
        "tags": [],
        "supporting_items": None,
    }
    return manifest, {}


def _build(pairs: list[tuple[dict, dict]], **kw) -> tuple[list[dict], list[dict]]:
    return build_actions(
        [m for m, _ in pairs], [c for _, c in pairs],
        kw.pop("daily_updates", []), kw.pop("skipped", []),
        CFG, kado_client=None,
    )


def _links(actions: list[dict]) -> list[tuple[str, str]]:
    return [
        (a.get("source_note_title") or "", a.get("target_moc") or "")
        for a in actions if a.get("action") == "link_to_moc"
    ]


# ---------------------------------------------------------------------------
# 1. Vault-collision drop of a create_moc orphans a surviving link_to_moc.
#    "The cleanest reachable case" per the finding — a lone create_moc whose
#    destination is already occupied in the vault (T2.2 made this reachable,
#    pinned separately by
#    test_a_moc_destination_occupied_in_the_vault_is_dropped).
# ---------------------------------------------------------------------------

def test_a_vault_collision_dropped_create_moc_orphans_a_surviving_link_to_moc():
    kado = FakeKado(occupied={f"{NOTES}Travel.md"})
    pairs = [
        _moc("Travel", idx=1),
        _atomic(ELBE, "Elbe", idx=2, parents=["Travel"]),
    ]
    actions, _skipped = _build(pairs)
    kept, clashes = validate_destinations(actions, make_folder_listing(kado))
    assert len(clashes) == 1 and clashes[0]["kind"] == "vault_collision", clashes
    assert _links(kept) == [], (
        "the create_moc that would have created `Travel` was dropped; a "
        "bullet naming it as target_moc has nowhere to land and must not "
        f"survive: {_links(kept)}"
    )


# ---------------------------------------------------------------------------
# 2. Run-collision drop of a create_moc (contesting a move_note on the same
#    destination) orphans a surviving link_to_moc naming it.
# ---------------------------------------------------------------------------

def test_a_run_collision_dropped_create_moc_orphans_a_surviving_link_to_moc():
    pairs = [
        _atomic(DRESDEN_PLACES, "Travel", idx=1),
        _moc("Travel", idx=2),
        _atomic(ELBE, "Elbe", idx=3, parents=["Travel"]),
    ]
    actions, _skipped = _build(pairs)
    kept, clashes = validate_destinations(actions)
    assert len(clashes) == 1 and clashes[0]["kind"] == "run_collision", clashes
    assert _links(kept) == [], (
        "both the move_note and create_moc claiming `Travel` were dropped; "
        f"the surviving Elbe bullet naming Travel must go with them: {_links(kept)}"
    )


# ---------------------------------------------------------------------------
# 3. Two INDEPENDENT clashes in the same run can each claim the same bullet —
#    one drops the bullet's author (_orphaned_link_titles), the other drops
#    its target MOC (_orphaned_link_targets). The bullet must be withdrawn
#    exactly once across the whole clash list, not once per clash that could
#    claim it. Reproduces the code-quality finding on e456030.
# ---------------------------------------------------------------------------

def test_a_bullet_orphaned_two_ways_is_withdrawn_by_exactly_one_clash():
    ELBE_1 = "100 Inbox/Elbe-1.md"
    ELBE_2 = "100 Inbox/Elbe-2.md"
    kado = FakeKado(occupied={f"{NOTES}Travel.md"})
    pairs = [
        # Run collision: two atomics named "Elbe" contest Elbe.md — both
        # dropped, both authoring the one deduped "Elbe" -> "Travel" bullet.
        _atomic(ELBE_1, "Elbe", idx=1, parents=["Travel"]),
        _atomic(ELBE_2, "Elbe", idx=2, parents=["Travel"]),
        # Vault collision: the lone create_moc "Travel" is dropped because
        # `Travel.md` already exists in the vault — the same bullet's
        # target_moc.
        _moc("Travel", idx=3),
    ]
    actions, _skipped = _build(pairs)
    kept, clashes = validate_destinations(actions, make_folder_listing(kado))
    assert _links(kept) == [], "the orphaned bullet must not survive either way"

    kinds = {c["kind"] for c in clashes}
    assert kinds == {"run_collision", "vault_collision"}, (
        f"expected exactly one clash of each kind, got: {clashes}"
    )

    all_withdrawn = [
        link for c in clashes for link in c["withdrawn_moc_links"]
    ]
    assert all_withdrawn == [{"source_note_title": "Elbe", "target_moc": "Travel"}], (
        f"the bullet must be withdrawn once, not zero or twice: {all_withdrawn}"
    )
    per_clash_counts = {c["kind"]: len(c["withdrawn_moc_links"]) for c in clashes}
    assert sorted(per_clash_counts.values()) == [0, 1], (
        "exactly one clash should carry the withdrawal, the other none: "
        f"{per_clash_counts}"
    )
