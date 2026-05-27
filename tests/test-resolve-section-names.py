#!/usr/bin/env python3
# version: 0.2.0
"""test-resolve-section-names.py — Unit tests for resolve_section_names + paired delete_source.

Covers:

  1. resolve_section_names tiers (post-2026-04-30 contract: populates
     anchor.value on callout-typed link_to_moc actions instead of the
     removed section_name string field).

       a. Tier-1: live MOC read via Kado succeeds and yields an editable
          callout.
       b. Tier-2: live MOC read fails because the MOC is being created in
          the same instruction set; fall back to reading the create_moc's
          template and scanning that for an editable callout.
       c. Both tiers fail (no template, or template read fails) →
          anchor.value stays null.
       d. Tier-2 cache: a single template body is read at most once.
       e. Pre-set anchor.value preserved without I/O.
       f. Heading/line anchor types are skipped by the resolver (anchor
          values for those types are populated upstream, not here).

  2. _build_delete_source_actions third source (post-2026-04-30 contract):
       a. Default-pair: confirmed item with non-null origin_inbox_item AND
          keep_origin=False → paired delete_source emitted.
       b. Keep-origin: confirmed item with keep_origin=True → no paired
          delete_source emitted for that origin.
       c. Idempotence: skipped[]'s explicit Delete-source flag still works
          (existing behaviour).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

from kado_client import KadoNotFoundError  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ir)


# ──────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ──────────────────────────────────────────────────────────────────────────────

T_MOC_TOMO_BODY = """\
---
UUID: {{uuid}}
title: {{title}}
---

> [!connect] Your way around
> up:: {{up}}
> related:: {{related}}

# [[{{title}}]]

---
> [!anchor] Overview

{{body}}

> [!blocks] Key Concepts

> [!video] Action Items
"""

EXISTING_MOC_BODY = """\
---
title: Japan (MOC)
---

> [!connect] Your way around
> up:: [[2700 - Art & Recreation]]

# [[Japan (MOC)]]

> [!blocks] Key Concepts
> - [[Sapporo — Hauptstadt]]

> [!compass] Something to look at perhaps...
"""

EDITABLE_CALLOUTS = ["connect", "blocks", "anchor", "compass", "video"]


def _callout_anchor() -> dict:
    return {"type": "callout", "value": None}


# ──────────────────────────────────────────────────────────────────────────────
# Stub Kado client
# ──────────────────────────────────────────────────────────────────────────────

class StubClient:
    """Minimal Kado-shaped stub. Fails read_note for paths NOT in `notes`,
    fails search_by_name for stems NOT in `names`. Counts read_note calls
    so we can assert template-cache behaviour."""

    def __init__(
        self,
        notes: dict[str, str] | None = None,
        names: dict[str, str] | None = None,
    ) -> None:
        self.notes = notes or {}
        self.names = names or {}
        self.read_calls: list[str] = []
        self.search_calls: list[str] = []

    def read_note(self, path: str) -> dict:
        self.read_calls.append(path)
        if path in self.notes:
            return {"content": self.notes[path]}
        raise KadoNotFoundError(f"stub: not found: {path}")

    def search_by_name(self, stem: str) -> list[dict]:
        self.search_calls.append(stem)
        if stem in self.names:
            return [{"path": self.names[stem]}]
        return []


def _must(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# resolve_section_names tests (anchor.value population)
# ──────────────────────────────────────────────────────────────────────────────

def test_tier1_existing_moc_resolves_to_blocks():
    """Live MOC has both [!connect] and [!blocks] — `blocks` wins (score 3).
    The resolver populates anchor.value, not the removed section_name field."""
    client = StubClient(
        notes={"Atlas/200 Maps/Japan (MOC).md": EXISTING_MOC_BODY},
    )
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Japan (MOC)",
            "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
            "anchor": _callout_anchor(),
            "placement": "inside",
            "line_to_add": "- [[Asahikawa]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 1, f"expected 1 resolution, got {n}")
    _must(
        actions[0]["anchor"]["value"] == "[!blocks] Key Concepts",
        f"expected blocks callout in anchor.value, got {actions[0]['anchor']['value']!r}",
    )
    print("[PASS] tier-1: existing MOC resolves to [!blocks] Key Concepts")


def test_tier2_in_set_create_moc_falls_back_to_template():
    """Live MOC read fails (in-set create_moc destination, doesn't exist
    yet); fallback reads the template and scans IT for an editable callout."""
    client = StubClient(
        notes={"Atlas/900 Templates/t_moc_tomo.md": T_MOC_TOMO_BODY},
        names={"t_moc_tomo.md": "Atlas/900 Templates/t_moc_tomo.md"},
    )
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "title": "Brettspiele (MOC)",
            "destination": "Atlas/200 Maps/Brettspiele (MOC).md",
            "template": "t_moc_tomo.md",
        },
        {
            "id": "I11",
            "action": "link_to_moc",
            "target_moc": "Brettspiele (MOC)",
            "target_moc_path": "Atlas/200 Maps/Brettspiele (MOC).md",
            "anchor": _callout_anchor(),
            "placement": "inside",
            "line_to_add": "- [[Catan Strategy]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 1, f"expected 1 resolution, got {n}")
    _must(
        actions[1]["anchor"]["value"] == "[!blocks] Key Concepts",
        f"expected template-derived blocks callout, "
        f"got {actions[1]['anchor']['value']!r}",
    )
    _must(
        "Atlas/200 Maps/Brettspiele (MOC).md" in client.read_calls,
        "expected tier-1 read attempt on MOC destination",
    )
    _must(
        "Atlas/900 Templates/t_moc_tomo.md" in client.read_calls,
        "expected tier-2 read attempt on template",
    )
    print("[PASS] tier-2: in-set create_moc falls back to template's [!blocks]")


def test_tier2_cache_reads_template_once_for_many_links():
    """Many link_to_mocs targeting the same in-set new MOC must read the
    template at most once."""
    client = StubClient(
        notes={"Atlas/900 Templates/t_moc_tomo.md": T_MOC_TOMO_BODY},
        names={"t_moc_tomo.md": "Atlas/900 Templates/t_moc_tomo.md"},
    )
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "title": "Brettspiele (MOC)",
            "destination": "Atlas/200 Maps/Brettspiele (MOC).md",
            "template": "t_moc_tomo.md",
        },
    ]
    for i, stem in enumerate(("Catan", "Splendor", "Wingspan"), start=11):
        actions.append({
            "id": f"I{i:02d}",
            "action": "link_to_moc",
            "target_moc": "Brettspiele (MOC)",
            "target_moc_path": "Atlas/200 Maps/Brettspiele (MOC).md",
            "anchor": _callout_anchor(),
            "placement": "inside",
            "line_to_add": f"- [[{stem}]]",
        })
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 3, f"expected 3 resolutions, got {n}")
    for a in actions[1:]:
        _must(
            a["anchor"]["value"] == "[!blocks] Key Concepts",
            f"all link actions should resolve to blocks, "
            f"got {a['anchor']['value']!r} on {a['id']}",
        )
    template_reads = [p for p in client.read_calls
                      if p == "Atlas/900 Templates/t_moc_tomo.md"]
    _must(
        len(template_reads) == 1,
        f"template should be read once, got {len(template_reads)} reads",
    )
    print("[PASS] tier-2 cache: template read once across 3 sibling links")


def test_no_template_no_fallback_stays_null():
    """In-set create_moc with no `template` field → tier-2 unavailable,
    anchor.value stays null."""
    client = StubClient(notes={})
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "title": "Foo (MOC)",
            "destination": "Atlas/200 Maps/Foo (MOC).md",
        },
        {
            "id": "I11",
            "action": "link_to_moc",
            "target_moc": "Foo (MOC)",
            "target_moc_path": "Atlas/200 Maps/Foo (MOC).md",
            "anchor": _callout_anchor(),
            "placement": "inside",
            "line_to_add": "- [[Bar]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 0, f"expected 0 resolutions, got {n}")
    _must(
        actions[1]["anchor"]["value"] is None,
        f"expected null anchor.value, got {actions[1]['anchor']['value']!r}",
    )
    print("[PASS] no template → no tier-2 fallback, anchor.value stays null")


def test_no_in_set_create_moc_stays_null():
    """target_moc_path that is NOT a same-set create_moc destination AND
    not readable via Kado → both tiers fail, anchor.value stays null."""
    client = StubClient(notes={})
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Stale (MOC)",
            "target_moc_path": "Atlas/200 Maps/Stale (MOC).md",
            "anchor": _callout_anchor(),
            "placement": "inside",
            "line_to_add": "- [[Whatever]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 0, f"expected 0 resolutions, got {n}")
    _must(
        actions[0]["anchor"]["value"] is None,
        f"expected null anchor.value, got {actions[0]['anchor']['value']!r}",
    )
    print("[PASS] no in-set create_moc → no tier-2, anchor.value stays null")


def test_pre_set_anchor_value_is_preserved():
    """If anchor.value is already set on a link_to_moc, neither tier runs."""
    client = StubClient(notes={"Atlas/200 Maps/Japan (MOC).md": EXISTING_MOC_BODY})
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Japan (MOC)",
            "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
            "anchor": {"type": "callout", "value": "[!compass] Something to look at perhaps..."},
            "placement": "after",
            "line_to_add": "- [[X]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 0, f"already-set anchor.value should not count as resolution, got {n}")
    _must(
        actions[0]["anchor"]["value"] == "[!compass] Something to look at perhaps...",
        "pre-set anchor.value must be preserved verbatim",
    )
    _must(
        client.read_calls == [],
        f"no Kado reads should have happened, got {client.read_calls}",
    )
    print("[PASS] pre-set anchor.value preserved without I/O")


def test_heading_anchor_skipped_by_resolver():
    """Heading and line anchors are populated upstream, not by resolve_section_names."""
    client = StubClient(notes={"Atlas/200 Maps/Japan (MOC).md": EXISTING_MOC_BODY})
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Japan (MOC)",
            "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
            "anchor": {"type": "heading", "value": None},
            "placement": "after",
            "line_to_add": "- [[X]]",
        },
        {
            "id": "I11",
            "action": "link_to_moc",
            "target_moc": "Japan (MOC)",
            "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
            "anchor": {"type": "line", "value": None},
            "placement": "after",
            "line_to_add": "- [[Y]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 0, f"resolver should skip heading/line anchors, got {n} resolutions")
    _must(
        actions[0]["anchor"]["value"] is None and actions[1]["anchor"]["value"] is None,
        "heading and line anchor values must remain untouched",
    )
    print("[PASS] resolver skips heading/line anchors (callout-only)")


# ──────────────────────────────────────────────────────────────────────────────
# _build_delete_source_actions tests (paired delete for move_note origins)
# ──────────────────────────────────────────────────────────────────────────────

def test_paired_delete_default_emits_for_each_origin():
    """Confirmed items with non-null origin and keep_origin=False produce
    one paired delete_source per move_note."""
    confirmed = [
        {"id": "S01", "source_path": "Asahikawa.md", "approved": True,
         "keep_origin": False},
        {"id": "S02", "source_path": "Furano.md", "approved": True,
         "keep_origin": False},
    ]
    move_notes = [
        {"id": "I01", "action": "move_note",
         "origin_inbox_item": "100 Inbox/Asahikawa.md"},
        {"id": "I02", "action": "move_note",
         "origin_inbox_item": "100 Inbox/Furano.md"},
    ]
    counter = [0]
    out = ir._build_delete_source_actions(
        confirmed=confirmed,
        move_notes=move_notes,
        daily_updates=[],
        skipped=[],
        inbox_path="100 Inbox/",
        counter=counter,
    )
    paired = [a for a in out if a["action"] == "delete_source"]
    _must(len(paired) == 2, f"expected 2 paired deletes, got {len(paired)}")
    paths = sorted(a["source_path"] for a in paired)
    _must(
        paths == ["100 Inbox/Asahikawa.md", "100 Inbox/Furano.md"],
        f"unexpected origin paths: {paths}",
    )
    for a in paired:
        _must(
            "Origin consumed by move_note" in a["reason"],
            f"unexpected reason: {a['reason']!r}",
        )
    print("[PASS] paired delete_source emitted by default for each move_note origin")


def test_keep_origin_suppresses_paired_delete():
    """Confirmed items with keep_origin=True must NOT produce a paired
    delete_source."""
    confirmed = [
        {"id": "S01", "source_path": "Asahikawa.md", "approved": True,
         "keep_origin": False},
        {"id": "S02", "source_path": "Furano.md", "approved": True,
         "keep_origin": True},  # ← user opted out
    ]
    move_notes = [
        {"id": "I01", "action": "move_note",
         "origin_inbox_item": "100 Inbox/Asahikawa.md"},
        {"id": "I02", "action": "move_note",
         "origin_inbox_item": "100 Inbox/Furano.md"},
    ]
    counter = [0]
    out = ir._build_delete_source_actions(
        confirmed=confirmed,
        move_notes=move_notes,
        daily_updates=[],
        skipped=[],
        inbox_path="100 Inbox/",
        counter=counter,
    )
    paths = sorted(a["source_path"] for a in out if a["action"] == "delete_source")
    _must(
        paths == ["100 Inbox/Asahikawa.md"],
        f"only Asahikawa should be paired-deleted, got {paths}",
    )
    print("[PASS] keep_origin=True suppresses paired delete_source for that origin")


def test_skipped_delete_source_still_works():
    """Skipped items with disposition=delete_source still emit deletes
    (existing behaviour, not regressed by the new third source)."""
    confirmed = []
    move_notes = []
    skipped = [
        {"id": "S03", "source_path": "Junk.md", "disposition": "delete_source"},
    ]
    counter = [0]
    out = ir._build_delete_source_actions(
        confirmed=confirmed,
        move_notes=move_notes,
        daily_updates=[],
        skipped=skipped,
        inbox_path="100 Inbox/",
        counter=counter,
    )
    deletes = [a for a in out if a["action"] == "delete_source"]
    _must(len(deletes) == 1, f"expected 1 skipped-source delete, got {len(deletes)}")
    _must(
        deletes[0]["source_path"] == "100 Inbox/Junk.md",
        f"unexpected source_path: {deletes[0]['source_path']!r}",
    )
    _must(
        "User marked source for deletion" in deletes[0]["reason"],
        f"unexpected reason: {deletes[0]['reason']!r}",
    )
    print("[PASS] explicit Delete-source on skipped items still emits")


def test_audio_peer_is_not_paired_deleted_via_origin():
    """Audio + transcript peer pairs are independent — peer files do not
    appear as origin_inbox_item on move_note, so they don't get paired-
    deleted via the third source. This guards the 2026-04-30 peer-files
    contract from regressing."""
    confirmed = [
        {"id": "S01", "source_path": "Memo.m4a.md", "approved": True,
         "keep_origin": False},
    ]
    # The transcript's move_note has origin_inbox_item pointing back at
    # the transcript markdown — NOT at the audio peer .m4a file.
    move_notes = [
        {"id": "I01", "action": "move_note",
         "origin_inbox_item": "100 Inbox/Memo.m4a.md"},
    ]
    counter = [0]
    out = ir._build_delete_source_actions(
        confirmed=confirmed,
        move_notes=move_notes,
        daily_updates=[],
        skipped=[],
        inbox_path="100 Inbox/",
        counter=counter,
    )
    paths = [a["source_path"] for a in out if a["action"] == "delete_source"]
    _must(
        paths == ["100 Inbox/Memo.m4a.md"],
        f"only the transcript should be paired-deleted, got {paths}",
    )
    _must(
        not any(p.endswith(".m4a") for p in paths),
        f"audio peer must not appear in deletes, got {paths}",
    )
    print("[PASS] audio peer (.m4a) not paired-deleted; only the transcript origin")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    test_tier1_existing_moc_resolves_to_blocks()
    test_tier2_in_set_create_moc_falls_back_to_template()
    test_tier2_cache_reads_template_once_for_many_links()
    test_no_template_no_fallback_stays_null()
    test_no_in_set_create_moc_stays_null()
    test_pre_set_anchor_value_is_preserved()
    test_heading_anchor_skipped_by_resolver()
    test_paired_delete_default_emits_for_each_origin()
    test_keep_origin_suppresses_paired_delete()
    test_skipped_delete_source_still_works()
    test_audio_peer_is_not_paired_deleted_via_origin()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
