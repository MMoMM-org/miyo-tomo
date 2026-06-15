#!/usr/bin/env python3
# version: 0.5.0
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

_spec = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ir)

# Use the SAME KadoNotFoundError class instruction-render imports
# (`lib.kado_client`), not `kado_client` — they are distinct module objects
# under the test's sys.path, so a bare `from kado_client import ...` would be a
# different class and `except KadoNotFoundError` in the module wouldn't catch it.
KadoNotFoundError = ir.KadoNotFoundError


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
            "Origin consumed by" in a["reason"],
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
# #29 / #28 — heading fallback + new-section-before-footer
# ──────────────────────────────────────────────────────────────────────────────

# Heading-structured MOC: NO editable callout anywhere, content lives in H2s.
_HEADING_MOC_BODY = """\
---
title: Topics (MOC)
---

# [[Topics (MOC)]]

## Overview

Some intro.

## Key Concepts

- [[Existing Note]]

## Sources
"""

# MOC with both a [!blocks] callout and an H2 — the callout must still win.
_CALLOUT_AND_HEADING_MOC_BODY = """\
---
title: Mixed (MOC)
---

> [!connect] Your way around
> up:: [[X]]

# [[Mixed (MOC)]]

> [!blocks] Key Concepts
> - [[A]]

## Extra Section

- [[B]]

> [!video] Action Items
"""

# MOC with only a footer callout, no editable content callout and no H2 heading.
_FOOTER_ONLY_MOC_BODY = """\
---
title: Bare (MOC)
---

# [[Bare (MOC)]]

Some intro prose.

> [!video] Action Items
> - [ ] do thing
"""

# Nothing anchorable: prose only.
_NOTHING_MOC_BODY = """\
---
title: Empty (MOC)
---

# [[Empty (MOC)]]

Just prose, no callouts, no H2 sections.
"""

# Footer markers (video/calendar) are deliberately excluded here so they are
# NOT treated as editable content callouts — otherwise tier-1 would land
# content inside [!video] instead of triggering the heading / new-section paths.
_CONTENT_CALLOUTS = ["connect", "blocks", "anchor"]


def _link_action(moc: str, path: str) -> dict:
    return {
        "id": "I10",
        "action": "link_to_moc",
        "target_moc": moc,
        "target_moc_path": path,
        "anchor": _callout_anchor(),
        "placement": "inside",
        "line_to_add": "- [[New Note]]",
    }


def test_heading_fallback_when_no_editable_callout():
    """#29: a MOC with no editable callout falls back to a content heading;
    the preferred 'Key Concepts' beats the earlier 'Overview', and the anchor
    is rewritten to type=heading / placement=after (Hashi has no callout-inside
    for headings)."""
    path = "Atlas/200 Maps/Topics (MOC).md"
    client = StubClient(notes={path: _HEADING_MOC_BODY})
    actions = [_link_action("Topics (MOC)", path)]
    n = ir.resolve_section_names(actions, client, _CONTENT_CALLOUTS)
    a = actions[0]
    _must(n == 1, f"expected 1 resolution, got {n}")
    _must(a["anchor"]["type"] == "heading",
          f"expected heading anchor, got {a['anchor']['type']!r}")
    _must(a["anchor"]["value"] == "Key Concepts",
          f"expected preferred 'Key Concepts', got {a['anchor']['value']!r}")
    _must(a["placement"] == "after",
          f"expected placement=after for heading, got {a['placement']!r}")
    print("[PASS] #29: heading fallback resolves to preferred H2 with placement=after")


def test_editable_callout_wins_over_heading():
    """#29: precedence preserved — when both an editable callout and an H2
    exist, the callout still wins (tier 1)."""
    path = "Atlas/200 Maps/Mixed (MOC).md"
    client = StubClient(notes={path: _CALLOUT_AND_HEADING_MOC_BODY})
    actions = [_link_action("Mixed (MOC)", path)]
    n = ir.resolve_section_names(actions, client, _CONTENT_CALLOUTS)
    a = actions[0]
    _must(n == 1, f"expected 1 resolution, got {n}")
    _must(a["anchor"]["type"] == "callout",
          f"expected callout anchor to win, got {a['anchor']['type']!r}")
    _must(a["anchor"]["value"] == "[!blocks] Key Concepts",
          f"expected [!blocks], got {a['anchor']['value']!r}")
    print("[PASS] #29: editable callout still wins over an H2 heading")


def test_new_section_before_footer_when_nothing_else_fits():
    """#28: no editable callout and no content heading → anchor on the footer
    callout with placement=before. The resolver sets up the footer anchor but
    no longer injects a hardcoded new-section name (ADR-6, spec 022 T5.2).
    line_to_add stays as the bare bullet — section heading only comes from a
    Pass-1 anchor carrying new_section, serialized by _serialize_new_sections.
    """
    # ADR-6: DEFAULT_NEW_SECTION_TITLE ("Key Concepts") retired as name source.
    # The heuristic footer tier no longer injects new_section; only Pass-1 LLM
    # anchors carry a topic-derived new_section value.
    path = "Atlas/200 Maps/Bare (MOC).md"
    client = StubClient(notes={path: _FOOTER_ONLY_MOC_BODY})
    actions = [_link_action("Bare (MOC)", path)]
    n = ir.resolve_section_names(actions, client, _CONTENT_CALLOUTS)
    a = actions[0]
    _must(n == 1, f"expected 1 resolution, got {n}")
    _must(a["anchor"]["type"] == "callout",
          f"expected callout (footer) anchor, got {a['anchor']['type']!r}")
    _must(a["anchor"]["value"] == "[!video] Action Items",
          f"expected footer callout anchor, got {a['anchor']['value']!r}")
    _must(a["placement"] == "before",
          f"expected placement=before, got {a['placement']!r}")
    # ADR-6: no hardcoded "Key Concepts" heading — bare bullet remains.
    _must(a["line_to_add"] == "- [[New Note]]",
          f"expected bare bullet (no hardcoded section name), got {a['line_to_add']!r}")
    print("[PASS] #28: footer anchor set, bare bullet (no hardcoded section name per ADR-6)")


def test_nothing_anchorable_stays_null():
    """#28 residual: no callout, no heading, no footer → anchor stays null
    (documented residual for truly bare MOCs)."""
    path = "Atlas/200 Maps/Empty (MOC).md"
    client = StubClient(notes={path: _NOTHING_MOC_BODY})
    actions = [_link_action("Empty (MOC)", path)]
    n = ir.resolve_section_names(actions, client, _CONTENT_CALLOUTS)
    a = actions[0]
    _must(n == 0, f"expected 0 resolutions, got {n}")
    _must(a["anchor"]["value"] is None,
          f"expected null anchor for bare MOC, got {a['anchor']['value']!r}")
    print("[PASS] #28: nothing anchorable leaves the anchor null")


def test_before_multiline_validates_against_schema():
    """The generalized primitive (placement=before + multi-line line_to_add)
    validates against instructions.schema.json."""
    import json

    import jsonschema

    schema = json.loads(
        (REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json").read_text()
    )
    doc = {
        "schema_version": "1",
        "type": "tomo-instructions",
        "generated": "2026-06-13T00:00:00Z",
        "profile": "miyo",
        "actions": [{
            "id": "I01",
            "action": "link_to_moc",
            "target_moc": "Bare (MOC)",
            "target_moc_path": "Atlas/200 Maps/Bare (MOC).md",
            "anchor": {"type": "callout", "value": "[!video] Action Items"},
            "placement": "before",
            "line_to_add": "## Key Concepts\n\n- [[New Note]]",
        }],
    }
    jsonschema.validate(doc, schema)
    print("[PASS] schema: placement=before + multi-line line_to_add validates")


# ──────────────────────────────────────────────────────────────────────────────
# filter_missing_daily_notes (#37 / I38) — skip daily actions for absent notes
# ──────────────────────────────────────────────────────────────────────────────

_DAILY = "Calendar/301 Daily/2026-06-13.md"
_MISSING = "Calendar/301 Daily/2026-04-29.md"


def _log_action(path):
    return {"id": "I50", "action": "update_log_entry", "daily_note_path": path,
            "date": "2026-04-29", "content": "Morgen-Routine durchgezogen"}


def test_daily_action_kept_when_note_exists():
    """Daily note exists → update_log_entry is kept."""
    client = StubClient(notes={_DAILY: "# 2026-06-13\n\n## Daily Log\n"})
    acts = [_log_action(_DAILY)]
    kept, skipped = ir.filter_missing_daily_notes(acts, client)
    _must(len(kept) == 1 and not skipped, f"expected kept, got kept={kept} skipped={skipped}")
    print("[PASS] I38: daily action kept when the daily note exists")


def test_daily_action_skipped_when_note_missing():
    """Daily note absent (KadoNotFoundError) → action skipped, not emitted."""
    client = StubClient(notes={})  # _MISSING not registered → NOT_FOUND
    acts = [_log_action(_MISSING)]
    kept, skipped = ir.filter_missing_daily_notes(acts, client)
    _must(not kept and len(skipped) == 1,
          f"expected skipped, got kept={kept} skipped={skipped}")
    _must(skipped[0]["id"] == "I50", "wrong action skipped")
    print("[PASS] I38: daily action skipped when the daily note is missing")


def test_non_daily_actions_never_filtered():
    """link_to_moc / create_moc are kept regardless of daily-note existence."""
    client = StubClient(notes={})
    acts = [
        {"id": "I01", "action": "create_moc", "destination": "X/Y (MOC).md"},
        {"id": "I02", "action": "link_to_moc", "target_moc": "Z (MOC)"},
    ]
    kept, skipped = ir.filter_missing_daily_notes(acts, client)
    _must(len(kept) == 2 and not skipped, f"non-daily must be kept, got skipped={skipped}")
    print("[PASS] I38: non-daily actions are never filtered")


def test_filter_fail_open_without_client():
    """client=None (offline/test) → keep everything, skip nothing."""
    acts = [_log_action(_MISSING)]
    kept, skipped = ir.filter_missing_daily_notes(acts, None)
    _must(len(kept) == 1 and not skipped, "must fail open when client is None")
    print("[PASS] I38: fail-open when client is None")


# ──────────────────────────────────────────────────────────────────────────────
# T5.2 — _serialize_new_sections (spec 022, ADR-3)
#
# These tests cover the independent serialize pass that builds line_to_add from
# anchor.new_section for ALL link_to_moc actions — both honored (Pass-1) and
# heuristic-resolved. The pass runs after resolve_section_names so that a
# Pass-1 anchor carrying new_section but skipped by the resolver (because its
# value was already set) still gets the correct "## <section>" prefix.
#
# ADR-3: render builds line_to_add from new_section AT SERIALIZE, not inside
#         resolve_section_names.
# ADR-6: retire DEFAULT_NEW_SECTION_TITLE ("Key Concepts") as the new-section
#         name source.
# AC-5:  new_section is derived from the note's dominant topic, not a hardcoded literal.
# AC-6:  exact shape: "## <section>\n\n- [[<Note>]]\n" (trailing newline preserved).
# ──────────────────────────────────────────────────────────────────────────────


def _honored_link_action(
    moc: str,
    path: str,
    *,
    anchor_value: str,
    anchor_type: str = "heading",
    placement: str = "before",
    new_section: str,
    note_title: str = "New Note",
) -> dict:
    """Factory for a link_to_moc action with a pre-set (honored) anchor."""
    return {
        "id": "I10",
        "action": "link_to_moc",
        "target_moc": moc,
        "target_moc_path": path,
        "anchor": {
            "type": anchor_type,
            "value": anchor_value,
            "placement": placement,
            "new_section": new_section,
        },
        "placement": placement,
        "line_to_add": f"- [[{note_title}]]",
    }


def test_serialize_honored_anchor_with_new_section():
    """T5.2 / ADR-3: a HONORED anchor (value already set, skipped by resolver)
    carrying new_section:"Reasoning" still serializes line_to_add as
    "## Reasoning\\n\\n- [[Note]]\\n" via _serialize_new_sections.

    This is the core bug the task fixes: resolve_section_names skips honored
    anchors at :1661-1664 so the old mutation at :1681-1683 never fires for them.
    The new independent pass covers all link_to_moc actions.
    """
    path = "Atlas/200 Maps/Philosophy (MOC).md"
    actions = [
        _honored_link_action(
            "Philosophy (MOC)",
            path,
            anchor_value="[!video] Action Items",
            anchor_type="callout",
            placement="before",
            new_section="Reasoning",
            note_title="Note",
        )
    ]
    # Serialize pass runs; resolve_section_names has NOT changed anchor
    n = ir._serialize_new_sections(actions)
    assert n == 1, f"expected 1 serialized, got {n}"
    assert actions[0]["line_to_add"] == "## Reasoning\n\n- [[Note]]\n", (
        f"got: {actions[0]['line_to_add']!r}"
    )


def test_serialize_ac6_exact_spacing():
    """T5.2 / AC-6: exact spacing contract — '## <section>\\n\\n<bullet>\\n'.
    The blank line between heading and bullet and the trailing newline are
    both mandatory (Hashi writes line_to_add verbatim, hashi#65).
    """
    path = "Atlas/200 Maps/Engineering (MOC).md"
    actions = [
        _honored_link_action(
            "Engineering (MOC)",
            path,
            anchor_value="[!blocks] Footer",
            anchor_type="callout",
            placement="before",
            new_section="Mental Models",
            note_title="First Principles",
        )
    ]
    ir._serialize_new_sections(actions)
    result = actions[0]["line_to_add"]
    # Exact shape per AC-6
    assert result == "## Mental Models\n\n- [[First Principles]]\n", (
        f"AC-6 spacing violated: {result!r}"
    )
    # Explicit component checks to catch off-by-one whitespace regressions
    parts = result.split("\n")
    assert parts[0] == "## Mental Models", f"heading line wrong: {parts[0]!r}"
    assert parts[1] == "", "blank line between heading and bullet must be empty"
    assert parts[2] == "- [[First Principles]]", f"bullet wrong: {parts[2]!r}"
    assert parts[3] == "", "trailing newline produces empty final element"


def test_serialize_idempotent():
    """T5.2: running _serialize_new_sections twice must NOT double-prepend the heading.
    Guard: if line_to_add already starts with '## ', skip (idempotent).
    """
    path = "Atlas/200 Maps/Philosophy (MOC).md"
    actions = [
        _honored_link_action(
            "Philosophy (MOC)",
            path,
            anchor_value="[!video] Action Items",
            anchor_type="callout",
            placement="before",
            new_section="Reasoning",
            note_title="Note",
        )
    ]
    ir._serialize_new_sections(actions)
    first = actions[0]["line_to_add"]
    ir._serialize_new_sections(actions)
    second = actions[0]["line_to_add"]
    assert first == second, (
        f"idempotency violated — second pass changed line_to_add:\n"
        f"  first:  {first!r}\n"
        f"  second: {second!r}"
    )


def test_serialize_skips_non_link_to_moc():
    """_serialize_new_sections must only touch link_to_moc actions."""
    actions = [
        {"id": "I01", "action": "create_moc", "title": "X"},
        {"id": "I02", "action": "move_note", "line_to_add": "- [[Y]]",
         "anchor": {"new_section": "Should Not Apply"}},
    ]
    n = ir._serialize_new_sections(actions)
    assert n == 0, f"expected 0 serializations on non-link_to_moc, got {n}"
    # move_note line_to_add untouched
    assert actions[1]["line_to_add"] == "- [[Y]]"


def test_serialize_skips_action_without_new_section():
    """Actions with anchor.new_section=None or absent are left unchanged."""
    path = "Atlas/200 Maps/Japan (MOC).md"
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Japan (MOC)",
            "target_moc_path": path,
            "anchor": {"type": "callout", "value": "[!blocks] Key Concepts",
                       "new_section": None},
            "placement": "inside",
            "line_to_add": "- [[Sapporo]]",
        }
    ]
    n = ir._serialize_new_sections(actions)
    assert n == 0, f"expected 0 serializations when new_section is None, got {n}"
    assert actions[0]["line_to_add"] == "- [[Sapporo]]"


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
    test_heading_fallback_when_no_editable_callout()
    test_editable_callout_wins_over_heading()
    test_new_section_before_footer_when_nothing_else_fits()
    test_nothing_anchorable_stays_null()
    test_before_multiline_validates_against_schema()
    test_serialize_honored_anchor_with_new_section()
    test_serialize_ac6_exact_spacing()
    test_serialize_idempotent()
    test_serialize_skips_non_link_to_moc()
    test_serialize_skips_action_without_new_section()
    test_daily_action_kept_when_note_exists()
    test_daily_action_skipped_when_note_missing()
    test_non_daily_actions_never_filtered()
    test_filter_fail_open_without_client()
    test_paired_delete_default_emits_for_each_origin()
    test_keep_origin_suppresses_paired_delete()
    test_skipped_delete_source_still_works()
    test_audio_peer_is_not_paired_deleted_via_origin()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
