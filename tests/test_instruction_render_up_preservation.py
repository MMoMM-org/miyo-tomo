#!/usr/bin/env python3
# version: 0.2.1
"""test_instruction_render_up_preservation.py — Rule 4.x existing-up:: preservation.

F-43 T4.2: Verifies that emit_up_preservation_actions produces correct
add_relationship action sequences for all Rule 4.x outcomes (PRD AC-4.1 …
AC-4.6) as defined in SDD Example 1.

Eight Rule 4.x tests, one per TDD-guardian-approved plan entry:
  1. test_rule_41_no_up_default
  2. test_rule_42_valid_up_default
  3. test_rule_43_broken_up_default
  4. test_rule_44_no_up_override
  5. test_rule_45_valid_up_override
  6. test_rule_46_per_child_individual_target
  7. test_self_link_skipped
  8. test_child_missing_at_render_time  ← CONVERTED: new contract (filtered, not wire error)

Filter tests (spec 024 follow-up):
  9. test_filter_unappliable_relationships_keeps_valid
  10. test_filter_unappliable_relationships_routes_error_to_skipped
  11. test_filter_unappliable_relationships_non_markdown_asset
  12. test_filter_unappliable_relationships_mixed
  13. test_wire_actions_have_no_error_field_on_child_missing
  14. test_wire_actions_have_no_error_field_on_non_markdown_asset
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)


# ── Fakes ───────────────────────────────────────────────────────────────────────


class _FakeKadoClient:
    """Controlled fake for render-time Kado reads in Rule 4.x tests.

    Implements the three interface methods used by emit_up_preservation_actions:
      - resolve_stem_to_path(stem) → path | raises KadoError(NOT_FOUND)
      - read_note(path) → {"content": str}
      - path_exists(stem_or_path) → bool

    Built from a dict of stem → (path, body) pairs.  Stems not registered
    trigger the NOT_FOUND path (test_child_missing_at_render_time).
    """

    def __init__(
        self,
        notes: dict[str, tuple[str, str]],
        existing_paths: set[str] | None = None,
    ) -> None:
        # notes: stem → (vault_path, body_content)
        self._notes = dict(notes)
        # existing_paths: set of stems/paths that kado considers "live"
        # (used for path_exists).  Defaults to all stems in notes.
        if existing_paths is None:
            self._existing: set[str] = set(self._notes.keys())
        else:
            self._existing = set(existing_paths)

    def resolve_stem_to_path(self, stem: str) -> str | None:
        if stem not in self._notes:
            if stem in self._existing:
                return f"{stem}.md"
            return None
        return self._notes[stem][0]

    def read_note(self, path: str) -> dict:
        # Reverse-lookup by path to find body
        for _stem, (p, body) in self._notes.items():
            if p == path:
                return {"content": body}
        raise ir.KadoError(f"NOT_FOUND path: {path!r}")

    def path_exists(self, target: str) -> bool:
        return target in self._existing


def _counter() -> list[int]:
    """Fresh action-ID counter starting at 0."""
    return [0]


def _action_markers(actions: list[dict]) -> list[tuple[str, str]]:
    """Extract (marker, line) pairs from a list of add_relationship actions."""
    return [(a["marker"], a["line"]) for a in actions]


# ── Rule 4.1 ───────────────────────────────────────────────────────────────────


def test_rule_41_no_up_default() -> None:
    """Override unchecked, no existing up:: → 1 action: up:: <newMOC>.

    PRD AC-4.1: WHEN Override is unchecked AND child has no existing up::,
    THE SYSTEM SHALL emit one add_relationship action with marker=up:: and
    the new MOC stem.
    """
    kado = _FakeKadoClient(
        notes={"zsh-aliases": ("Atlas/202 Notes/zsh-aliases.md", "# zsh aliases\n\nProse only.\n")},
        existing_paths=set(),
    )
    actions = ir.emit_up_preservation_actions(
        "zsh-aliases", "Shell & Terminal (MOC)", override_flag=False, kado_client=kado, counter=_counter()
    )
    assert len(actions) == 1, f"Expected 1 action, got {actions!r}"
    assert actions[0]["action"] == "add_relationship"
    assert actions[0]["marker"] == "up::"
    assert "Shell & Terminal (MOC)" in actions[0]["line"]


# ── Rule 4.2 ───────────────────────────────────────────────────────────────────


def test_rule_42_valid_up_default() -> None:
    """Override unchecked, valid existing up:: → 2 actions: up:: <newMOC> + related:: <X>.

    PRD AC-4.2: WHEN Override is unchecked AND child has a valid existing
    up:: <X>, THE SYSTEM SHALL emit two add_relationship actions.
    """
    body = "# oh-my-zsh\n\nup:: [[2600 - Applied Sciences]]\n\nProse.\n"
    kado = _FakeKadoClient(
        notes={"oh-my-zsh": ("Atlas/202 Notes/oh-my-zsh.md", body)},
        existing_paths={"2600 - Applied Sciences"},
    )
    actions = ir.emit_up_preservation_actions(
        "oh-my-zsh", "Shell & Terminal (MOC)", override_flag=False, kado_client=kado, counter=_counter()
    )
    assert len(actions) == 2, f"Expected 2 actions, got {actions!r}"
    markers = _action_markers(actions)
    assert markers[0][0] == "up::", f"First marker must be up::; got {markers[0][0]!r}"
    assert "Shell & Terminal (MOC)" in markers[0][1]
    assert markers[1][0] == "related::", f"Second marker must be related::; got {markers[1][0]!r}"
    assert "2600 - Applied Sciences" in markers[1][1]


# ── Rule 4.3 ───────────────────────────────────────────────────────────────────


def test_rule_43_broken_up_default() -> None:
    """Override unchecked, broken existing up:: → 1 action: up:: <newMOC> (no related).

    PRD AC-4.3: WHEN Override is unchecked AND child has a broken existing
    up::, THE SYSTEM SHALL emit only one add_relationship action (up:: <newMOC>).
    """
    body = "# tmux Setup\n\nup:: [[Old MOC No Longer Exists]]\n"
    kado = _FakeKadoClient(
        notes={"tmux-setup": ("Atlas/202 Notes/tmux-setup.md", body)},
        existing_paths=set(),  # broken — target not live
    )
    actions = ir.emit_up_preservation_actions(
        "tmux-setup", "Shell & Terminal (MOC)", override_flag=False, kado_client=kado, counter=_counter()
    )
    assert len(actions) == 1, f"Expected 1 action (broken→no related), got {actions!r}"
    assert actions[0]["marker"] == "up::"
    assert "Shell & Terminal (MOC)" in actions[0]["line"]


# ── Rule 4.4 ───────────────────────────────────────────────────────────────────


def test_rule_44_no_up_override() -> None:
    """Override checked, no existing up:: → 1 action: related:: <newMOC>.

    User chose "keep existing up::, new MOC as related::" — even when
    there's no existing up::, the intent is related:: for the new MOC.
    """
    kado = _FakeKadoClient(
        notes={"bash-vs-zsh": ("Atlas/202 Notes/bash-vs-zsh.md", "# Bash vs Zsh\n\nContent.\n")},
        existing_paths=set(),
    )
    actions = ir.emit_up_preservation_actions(
        "bash-vs-zsh", "Shell & Terminal (MOC)", override_flag=True, kado_client=kado, counter=_counter()
    )
    assert len(actions) == 1, f"Expected 1 action (related:: override), got {actions!r}"
    assert actions[0]["marker"] == "related::"
    assert "Shell & Terminal (MOC)" in actions[0]["line"]


# ── Rule 4.5 ───────────────────────────────────────────────────────────────────


def test_rule_45_valid_up_override() -> None:
    """Override checked, valid existing up:: → 1 action: related:: <newMOC> (existing up:: kept).

    PRD AC-4.4: WHEN Override is checked AND child has a valid existing up:: <X>,
    THE SYSTEM SHALL emit one add_relationship action (related:: <newMOC>) and
    not modify the existing up::.
    """
    body = "# iTerm Configuration\n\nup:: [[2600 - Applied Sciences]]\n\nProse.\n"
    kado = _FakeKadoClient(
        notes={"iterm-configuration": ("Atlas/202 Notes/iterm-configuration.md", body)},
        existing_paths={"2600 - Applied Sciences"},
    )
    actions = ir.emit_up_preservation_actions(
        "iterm-configuration", "Shell & Terminal (MOC)", override_flag=True, kado_client=kado, counter=_counter()
    )
    assert len(actions) == 1, f"Expected 1 action (related:: only), got {actions!r}"
    assert actions[0]["marker"] == "related::", f"Expected related::; got {actions[0]['marker']!r}"
    assert "Shell & Terminal (MOC)" in actions[0]["line"]


# ── Rule 4.6 ───────────────────────────────────────────────────────────────────


def test_rule_46_per_child_individual_target() -> None:
    """Multi-child cluster: each child's existing up:: preserved individually.

    PRD AC-4.6: WHILE a multi-child cluster is applied, THE SYSTEM SHALL
    preserve each child's existing up:: target individually; the group-level
    Override flag SHALL only flip the marker direction, not collapse children
    to a single target.

    Scenario (override=False):
      child-a: up:: [[MOC-A]]  (valid) → up:: <newMOC> + related:: [[MOC-A]]
      child-b: up:: [[MOC-B]]  (valid) → up:: <newMOC> + related:: [[MOC-B]]
      child-c: (no up::)                → up:: <newMOC>
    """
    kado = _FakeKadoClient(
        notes={
            "child-a": ("Atlas/202 Notes/child-a.md", "# A\n\nup:: [[MOC-A]]\n"),
            "child-b": ("Atlas/202 Notes/child-b.md", "# B\n\nup:: [[MOC-B]]\n"),
            "child-c": ("Atlas/202 Notes/child-c.md", "# C\n\nProse only.\n"),
        },
        existing_paths={"MOC-A", "MOC-B"},
    )
    new_moc = "New Cluster MOC"
    counter = _counter()

    actions_a = ir.emit_up_preservation_actions("child-a", new_moc, False, kado, counter)
    actions_b = ir.emit_up_preservation_actions("child-b", new_moc, False, kado, counter)
    actions_c = ir.emit_up_preservation_actions("child-c", new_moc, False, kado, counter)

    # child-a: 2 actions (up:: new + related:: MOC-A)
    assert len(actions_a) == 2, f"child-a: expected 2 actions; got {actions_a!r}"
    assert actions_a[0]["marker"] == "up::"
    assert "MOC-A" in actions_a[1]["line"], f"child-a: expected MOC-A in related::; got {actions_a[1]['line']!r}"

    # child-b: 2 actions (up:: new + related:: MOC-B) — DIFFERENT target, not MOC-A
    assert len(actions_b) == 2, f"child-b: expected 2 actions; got {actions_b!r}"
    assert actions_b[0]["marker"] == "up::"
    assert "MOC-B" in actions_b[1]["line"], f"child-b: expected MOC-B in related::; got {actions_b[1]['line']!r}"
    assert "MOC-A" not in actions_b[1]["line"], "child-b: must not reference MOC-A from child-a"

    # child-c: 1 action (up:: new only)
    assert len(actions_c) == 1, f"child-c: expected 1 action; got {actions_c!r}"
    assert actions_c[0]["marker"] == "up::"


# ── Self-link guard ─────────────────────────────────────────────────────────────


def test_self_link_skipped() -> None:
    """Existing up:: already targets the new MOC → no action emitted (no self-link).

    SDD edge case: if existing_up_target is itself the new MOC stem, emit nothing
    — do not add a redundant up:: or a circular related::.
    """
    new_moc = "Shell & Terminal (MOC)"
    # child already points up to the MOC being created
    body = f"# Some Note\n\nup:: [[{new_moc}]]\n"
    kado = _FakeKadoClient(
        notes={"some-note": ("Atlas/202 Notes/some-note.md", body)},
        existing_paths={new_moc},
    )
    actions = ir.emit_up_preservation_actions(
        "some-note", new_moc, override_flag=False, kado_client=kado, counter=_counter()
    )
    assert actions == [], f"Expected no actions for self-link; got {actions!r}"


# ── Child missing at render time ────────────────────────────────────────────────
# CONVERTED CONTRACT: emit_up_preservation_actions still returns the sentinel
# (so callers can route it to skipped), but the sentinel must NOT appear on the
# wire actions list — filter_unappliable_relationships removes it before emit.


def test_child_missing_at_render_time() -> None:
    """Kado raises NOT_FOUND → sentinel with applied=False, error=child-missing.

    emit_up_preservation_actions emits the sentinel so the filter can route it.
    The sentinel is NOT expected on the wire — filter_unappliable_relationships
    intercepts it. This test covers only the emit function contract, not the wire.
    """
    kado = _FakeKadoClient(notes={})
    actions = ir.emit_up_preservation_actions(
        "deleted-note", "Some MOC", override_flag=False, kado_client=kado, counter=_counter()
    )
    assert len(actions) == 1, f"Expected one sentinel action; got {actions!r}"
    sentinel = actions[0]
    assert sentinel.get("action") == "add_relationship"
    assert sentinel.get("applied") is False, f"applied must be False; got {sentinel!r}"
    assert sentinel.get("error") == "child-missing", f"error must be 'child-missing'; got {sentinel!r}"
    # Sentinel fields must be strings (not None) so the action is describable.
    assert isinstance(sentinel.get("target_moc_path"), str)
    assert isinstance(sentinel.get("marker"), str)
    assert isinstance(sentinel.get("line"), str)


# ── filter_unappliable_relationships ────────────────────────────────────────────
# New filter function (spec 024 follow-up): routes error-bearing add_relationship
# actions to the skipped bucket so they never reach the wire.


def test_filter_unappliable_relationships_keeps_valid() -> None:
    """Valid add_relationship actions (no error) pass through unchanged."""
    actions = [
        {"id": "I01", "action": "add_relationship", "target_moc_path": "Atlas/Note.md",
         "marker": "up::", "line": "up:: [[MOC]]", "applied": None},
        {"id": "I02", "action": "add_relationship", "target_moc_path": "Atlas/Other.md",
         "marker": "related::", "line": "related:: [[MOC]]", "applied": None},
    ]
    kept, skipped = ir.filter_unappliable_relationships(actions)
    assert len(kept) == 2, f"Both valid actions must be kept; got {kept!r}"
    assert skipped == [], f"No skipped expected; got {skipped!r}"


def test_filter_unappliable_relationships_routes_error_to_skipped() -> None:
    """add_relationship with error='child-missing' is routed to skipped, not kept."""
    valid = {"id": "I01", "action": "add_relationship", "target_moc_path": "Atlas/Note.md",
             "marker": "up::", "line": "up:: [[MOC]]", "applied": None}
    sentinel = {"id": "I02", "action": "add_relationship", "target_moc_path": "deleted-note",
                "marker": "up::", "line": "up:: [[Some MOC]]", "applied": False,
                "error": "child-missing"}
    kept, skipped = ir.filter_unappliable_relationships([valid, sentinel])
    assert kept == [valid], f"Only valid action should be kept; got {kept!r}"
    assert skipped == [sentinel], f"Sentinel must be skipped; got {skipped!r}"


def test_filter_unappliable_relationships_non_markdown_asset() -> None:
    """add_relationship with error='non-markdown-asset' is routed to skipped."""
    sentinel = {"id": "I01", "action": "add_relationship",
                "target_moc_path": "Attachments/image.png",
                "marker": "up::", "line": "up:: [[Some MOC]]", "applied": False,
                "error": "non-markdown-asset"}
    kept, skipped = ir.filter_unappliable_relationships([sentinel])
    assert kept == [], f"No kept expected; got {kept!r}"
    assert skipped == [sentinel], f"Sentinel must be skipped; got {skipped!r}"


def test_filter_unappliable_relationships_mixed() -> None:
    """Non-add_relationship actions and error-free add_relationships pass through."""
    move = {"id": "I01", "action": "move_note", "source": "100 Inbox/x.md",
            "destination": "Atlas/x.md", "title": "X"}
    valid_rel = {"id": "I02", "action": "add_relationship",
                 "target_moc_path": "Atlas/Note.md", "marker": "up::", "line": "up:: [[M]]"}
    bad_rel = {"id": "I03", "action": "add_relationship",
               "target_moc_path": "gone", "marker": "up::", "line": "up:: [[M]]",
               "applied": False, "error": "child-missing"}
    kept, skipped = ir.filter_unappliable_relationships([move, valid_rel, bad_rel])
    assert kept == [move, valid_rel], f"move + valid_rel must be kept; got {kept!r}"
    assert skipped == [bad_rel], f"bad_rel must be skipped; got {skipped!r}"


# ── Wire contract: no error-bearing actions on the wire ─────────────────────────
# These tests drive build_actions end-to-end and assert that error-bearing
# add_relationship sentinels never appear in the returned list.  The filter
# must be applied inside (or immediately after) build_actions or in main().
# The tests here verify the contract from the caller's perspective — via
# filter_unappliable_relationships applied to the output of build_actions.


def test_wire_actions_have_no_error_field_on_child_missing() -> None:
    """When a child is missing, no add_relationship with error reaches the wire.

    Scenario: one child is registered (present), one is missing.
    After applying filter_unappliable_relationships, the missing-child sentinel
    must not appear in the kept list.
    """
    kado = _FakeKadoClient(
        notes={"present-note": ("Atlas/202 Notes/present-note.md", "# Present\n\nProse.\n")},
        existing_paths=set(),
    )
    manifest = [{
        "id": "MOC01",
        "action": "create_moc",
        "title": "Some MOC",
        "rendered_file": "2026-06-24_0000_some-moc.md",
        "destination": "Atlas/200 Maps/",
        "parent_moc": None,
        "tags": [],
        "supporting_items": "present-note, missing-note",
        "override_preserve_existing_up": False,
    }]
    cfg = {
        "concepts.inbox": "100 Inbox",
        "concepts.calendar.granularities.daily.path": "Calendar/Daily",
        "daily_log.heading": "Daily Log",
        "daily_log.heading_level": 2,
        "callouts.editable": ["blocks"],
        "profile": "miyo",
    }
    raw_actions, _skipped_assets = ir.build_actions(
        manifest=manifest, confirmed=[], daily_updates=[], skipped=[], cfg=cfg, kado_client=kado,
    )
    wire_actions, skipped_rel = ir.filter_unappliable_relationships(raw_actions)

    # No action on the wire may carry an "error" key with a truthy value
    error_on_wire = [a for a in wire_actions if a.get("error")]
    assert error_on_wire == [], (
        f"error-bearing add_relationship actions must not reach wire; got {error_on_wire!r}"
    )
    # The missing-note sentinel must be in skipped
    assert len(skipped_rel) == 1, f"Expected 1 skipped (missing-note); got {skipped_rel!r}"
    assert skipped_rel[0].get("error") == "child-missing"
    # The valid present-note action must still be on the wire
    rel_actions = [a for a in wire_actions if a.get("action") == "add_relationship"]
    assert len(rel_actions) == 1, f"Expected 1 wire add_relationship; got {rel_actions!r}"
    assert rel_actions[0]["target_moc_path"] == "Atlas/202 Notes/present-note.md"


def test_wire_actions_have_no_error_field_on_non_markdown_asset() -> None:
    """When a child resolves to a non-markdown path, its sentinel is filtered.

    Simulate: resolve_stem_to_path returns a .png path (non-markdown asset).
    The sentinel must go to skipped, not to the wire.
    """
    class _NonMarkdownKado(_FakeKadoClient):
        """Returns a non-markdown path for 'image-asset' stem."""
        def resolve_stem_to_path(self, stem: str) -> str | None:
            if stem == "image-asset":
                return "Attachments/image-asset.png"
            return super().resolve_stem_to_path(stem)

    kado = _NonMarkdownKado(
        notes={"real-note": ("Atlas/202 Notes/real-note.md", "# Real\n\nProse.\n")},
        existing_paths=set(),
    )
    manifest = [{
        "id": "MOC01",
        "action": "create_moc",
        "title": "Some MOC",
        "rendered_file": "2026-06-24_0000_some-moc.md",
        "destination": "Atlas/200 Maps/",
        "parent_moc": None,
        "tags": [],
        "supporting_items": "real-note, image-asset",
        "override_preserve_existing_up": False,
    }]
    cfg = {
        "concepts.inbox": "100 Inbox",
        "concepts.calendar.granularities.daily.path": "Calendar/Daily",
        "daily_log.heading": "Daily Log",
        "daily_log.heading_level": 2,
        "callouts.editable": ["blocks"],
        "profile": "miyo",
    }
    raw_actions, _skipped_assets = ir.build_actions(
        manifest=manifest, confirmed=[], daily_updates=[], skipped=[], cfg=cfg, kado_client=kado,
    )
    wire_actions, skipped_rel = ir.filter_unappliable_relationships(raw_actions)

    error_on_wire = [a for a in wire_actions if a.get("error")]
    assert error_on_wire == [], (
        f"error-bearing add_relationship actions must not reach wire; got {error_on_wire!r}"
    )
    assert len(skipped_rel) == 1, f"Expected 1 skipped (non-markdown-asset); got {skipped_rel!r}"
    assert skipped_rel[0].get("error") == "non-markdown-asset"


# ── Fix 2: extract_first_up_marker ignores frontmatter ─────────────────────────


def test_extract_first_up_marker_ignores_frontmatter_up() -> None:
    """up:: in YAML frontmatter must NOT be returned; only body up:: counts.

    FIX 2: A note whose frontmatter contains ``up:: [[X]]`` should return None
    when there is no up:: line in the body.  Previously the regex scanned the
    full content including frontmatter, causing a false positive.
    """
    content = "---\nup:: [[FrontmatterMOC]]\ntags: [foo]\n---\n\n# Title\n\nBody text only.\n"
    result = ir.extract_first_up_marker(content)
    assert result is None, (
        f"Expected None (up:: in frontmatter only); got {result!r}"
    )


# ── Fix 1: assembler end-to-end wiring ─────────────────────────────────────────


def test_assembler_wires_up_preservation_for_moc_proposal() -> None:
    """build_actions emits add_relationship actions for each child in a MOC proposal.

    FIX 1: _build_up_preservation_actions must be called from build_actions
    for create_moc items that carry both supporting_items (child stems) and
    override_preserve_existing_up.  This test drives the assembler end-to-end
    with a minimal manifest + kado fake and asserts the expected actions appear.

    Scenario (override_flag=False, child has no existing up::):
      create_moc item: Shell & Terminal (MOC), children: [zsh-aliases, oh-my-zsh]
      Both children exist in Kado with no existing up:: line.
      Expected: 2 add_relationship actions (one per child), both marker=up::
    """
    kado = _FakeKadoClient(
        notes={
            "zsh-aliases": ("Atlas/202 Notes/zsh-aliases.md", "# zsh aliases\n\nProse only.\n"),
            "oh-my-zsh":   ("Atlas/202 Notes/oh-my-zsh.md",   "# oh-my-zsh\n\nProse only.\n"),
        },
        existing_paths=set(),
    )

    # Minimal manifest: one create_moc entry with supporting_items + override flag.
    manifest = [{
        "id": "MOC01",
        "action": "create_moc",
        "title": "Shell & Terminal (MOC)",
        "rendered_file": "2026-05-08_0000_shell-terminal-moc.md",
        "destination": "Atlas/200 Maps/",
        "parent_moc": None,
        "tags": [],
        "supporting_items": "zsh-aliases, oh-my-zsh",  # comma-joined child stems
        "override_preserve_existing_up": False,         # presence flag triggers the helper
    }]

    cfg = {
        "concepts.inbox": "100 Inbox",
        "concepts.calendar.granularities.daily.path": "Calendar/Daily",
        "daily_log.heading": "Daily Log",
        "daily_log.heading_level": 2,
        "callouts.editable": ["blocks"],
        "profile": "miyo",
    }

    actions, _skipped_assets = ir.build_actions(
        manifest=manifest,
        confirmed=[],
        daily_updates=[],
        skipped=[],
        cfg=cfg,
        kado_client=kado,
    )

    # Filter to add_relationship actions only
    rel_actions = [a for a in actions if a.get("action") == "add_relationship"]
    assert len(rel_actions) == 2, (
        f"Expected 2 add_relationship actions for 2 children; got {rel_actions!r}"
    )
    markers = {a["marker"] for a in rel_actions}
    assert markers == {"up::"}, f"Both children with no existing up:: → marker must be up::; got {markers!r}"
    # Each action targets the child note path, not the MOC
    paths = {a["target_moc_path"] for a in rel_actions}
    assert "Atlas/202 Notes/zsh-aliases.md" in paths
    assert "Atlas/202 Notes/oh-my-zsh.md" in paths
