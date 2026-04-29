#!/usr/bin/env python3
# version: 0.1.0
"""test-resolve-section-names.py — Unit tests for resolve_section_names.

Covers the two-tier resolution path in instruction-render.py:

  1. Tier-1: live MOC read via Kado succeeds and yields an editable callout.
  2. Tier-2 (NEW 2026-04-29): live MOC read fails because the MOC is being
     created in the same instruction set; fall back to reading the
     create_moc's template and scanning that for an editable callout. This
     prevents in-set create+link pairs from landing in the navigation
     callout (`[!connect]`) at execute time.
  3. Both tiers fail (no template, or template read fails) → section_name
     stays null.
  4. Tier-2 cache: a single template body is read at most once, even when
     many in-set create+link pairs share it.

Each test stubs a Kado client with a known content map, invokes
resolve_section_names directly, and asserts section_name on the resulting
actions.
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

# Bring KadoError into scope so the stub can raise it (mirrors what the
# real instruction-render code catches via `except Exception`).
from kado_client import KadoError, KadoNotFoundError  # noqa: E402

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
# Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_tier1_existing_moc_resolves_to_blocks():
    """Live MOC has both [!connect] and [!blocks] — `blocks` wins (score 3)."""
    client = StubClient(
        notes={"Atlas/200 Maps/Japan (MOC).md": EXISTING_MOC_BODY},
    )
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Japan (MOC)",
            "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
            "section_name": None,
            "line_to_add": "- [[Asahikawa]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 1, f"expected 1 resolution, got {n}")
    _must(
        actions[0]["section_name"] == "[!blocks] Key Concepts",
        f"expected blocks callout, got {actions[0]['section_name']!r}",
    )
    print("[PASS] tier-1: existing MOC resolves to [!blocks] Key Concepts")


def test_tier2_in_set_create_moc_falls_back_to_template():
    """Live MOC read fails (in-set create_moc destination, doesn't exist
    yet); fallback reads the template and scans IT for an editable callout."""
    # Templates are read via read_template → tries search_by_name first when
    # given a bare stem, then read_note on the resolved path.
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
            "section_name": None,
            "line_to_add": "- [[Catan Strategy]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 1, f"expected 1 resolution, got {n}")
    _must(
        actions[1]["section_name"] == "[!blocks] Key Concepts",
        f"expected template-derived blocks callout, "
        f"got {actions[1]['section_name']!r}",
    )
    # Sanity: tier-1 was attempted (read_note tried the MOC path and got
    # KadoNotFoundError), then tier-2 read the template.
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
    # Three sibling links to the same new MOC.
    for i, stem in enumerate(("Catan", "Splendor", "Wingspan"), start=11):
        actions.append({
            "id": f"I{i:02d}",
            "action": "link_to_moc",
            "target_moc": "Brettspiele (MOC)",
            "target_moc_path": "Atlas/200 Maps/Brettspiele (MOC).md",
            "section_name": None,
            "line_to_add": f"- [[{stem}]]",
        })
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 3, f"expected 3 resolutions, got {n}")
    for a in actions[1:]:
        _must(
            a["section_name"] == "[!blocks] Key Concepts",
            f"all link actions should resolve to blocks, "
            f"got {a['section_name']!r} on {a['id']}",
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
    section_name stays null."""
    client = StubClient(notes={})
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "title": "Foo (MOC)",
            "destination": "Atlas/200 Maps/Foo (MOC).md",
            # No template field — emulates a degraded create_moc emission.
        },
        {
            "id": "I11",
            "action": "link_to_moc",
            "target_moc": "Foo (MOC)",
            "target_moc_path": "Atlas/200 Maps/Foo (MOC).md",
            "section_name": None,
            "line_to_add": "- [[Bar]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 0, f"expected 0 resolutions, got {n}")
    _must(
        actions[1]["section_name"] is None,
        f"expected null section_name, got {actions[1]['section_name']!r}",
    )
    print("[PASS] no template → no tier-2 fallback, section_name stays null")


def test_no_in_set_create_moc_stays_null():
    """target_moc_path that is NOT a same-set create_moc destination AND
    not readable via Kado → both tiers fail, section_name stays null."""
    client = StubClient(notes={})  # nothing readable
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Stale (MOC)",
            "target_moc_path": "Atlas/200 Maps/Stale (MOC).md",
            "section_name": None,
            "line_to_add": "- [[Whatever]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 0, f"expected 0 resolutions, got {n}")
    _must(
        actions[0]["section_name"] is None,
        f"expected null section_name, got {actions[0]['section_name']!r}",
    )
    print("[PASS] no in-set create_moc → no tier-2, section_name stays null")


def test_pre_set_section_name_is_preserved():
    """If section_name is already set on a link_to_moc, neither tier runs."""
    client = StubClient(notes={"Atlas/200 Maps/Japan (MOC).md": EXISTING_MOC_BODY})
    actions = [
        {
            "id": "I10",
            "action": "link_to_moc",
            "target_moc": "Japan (MOC)",
            "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
            "section_name": "[!compass] Something to look at perhaps...",
            "line_to_add": "- [[X]]",
        },
    ]
    n = ir.resolve_section_names(actions, client, EDITABLE_CALLOUTS)
    _must(n == 0, f"already-set section_name should not count as resolution, got {n}")
    _must(
        actions[0]["section_name"] == "[!compass] Something to look at perhaps...",
        "pre-set section_name must be preserved verbatim",
    )
    _must(
        client.read_calls == [],
        f"no Kado reads should have happened, got {client.read_calls}",
    )
    print("[PASS] pre-set section_name preserved without I/O")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    test_tier1_existing_moc_resolves_to_blocks()
    test_tier2_in_set_create_moc_falls_back_to_template()
    test_tier2_cache_reads_template_once_for_many_links()
    test_no_template_no_fallback_stays_null()
    test_no_in_set_create_moc_stays_null()
    test_pre_set_section_name_is_preserved()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
