#!/usr/bin/env python3
# version: 0.1.0
"""test_036_t3_3_phase_validation.py — spec 036 / T3.3 Phase 3 validation.

Phase 3 ("Withhold — the tag-handler blast radius", solution.md) claims Bug B
stops happening: a tag-handler group with an unresolved `target_path` used to
emit zero `insert_under_marker` and ONE `delete_source` per source note — a
single unresolved target losing every note in the group, deleted via
`vault.trash` where the user configured permanent deletion.

This file proves that claim end to end through the real pipeline functions —
`annotate_tag_handler_group_guards` -> `render_tag_handler_updates_block` ->
`parse_tag_handler_groups` -> `build_actions` — exactly as instruction-
render.py runs them, not through a hand-built approved-ids list.

Two gates close Bug B (both shipped before this task; this task only proves
them):
  - T3.1: `_tag_handler_group_has_resolvable_target(group)` in
    `lib.render_actions`, called by BOTH `_build_insert_under_marker_actions`
    and the site-4 delete loop in `_build_delete_source_actions`.
  - T3.2: `annotate_tag_handler_group_guards` sets guard="target_unresolved"
    for a null-target group; `render_tag_handler_group` returns before
    appending any Approve box, so `parse_tag_handler_groups` never yields the
    group id and Pass-2 emits nothing for it (the real-world path).

Test B additionally proves T3.1 is an INDEPENDENT second gate, not decorative
scaffolding behind T3.2: `build_actions` has exactly one production caller
(instruction-render.py:541), which takes `approved_tag_handler_group_ids`
from a JSON file on disk (the confirmed suggestions doc, parsed at
suggestion-parser.py:2817). A suggestions doc confirmed BEFORE T3.2 landed
can still carry an approved id for a now-unresolved group — replaying it
bypasses the render/parse gate entirely and reaches `build_actions` with the
id already "approved". T3.1's in-builder gate is what defends against that
stale-replay case, independent of whatever the renderer/parser did.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    """Load a hyphenated top-level script as a module — house pattern."""
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_group_mod = _load("tag_handler_group", "tag-handler-group.py")
_reducer_mod = _load("suggestions_reducer", "suggestions-reducer.py")
_parser_mod = _load("suggestion_parser", "suggestion-parser.py")

import lib.render_actions as _render_actions_mod  # noqa: E402

group_id = _group_mod.group_id
annotate_tag_handler_group_guards = _reducer_mod.annotate_tag_handler_group_guards
render_tag_handler_updates_block = _reducer_mod.render_tag_handler_updates_block
parse_tag_handler_groups = _parser_mod.parse_tag_handler_groups
build_actions = _render_actions_mod.build_actions

# Minimal config for build_actions (mirrors tests/test_tag_handler_group_
# instruction_linkage.py's _CFG).
_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


def _group(
    *,
    handler: str = "tsukai",
    target_path: str | None = "Efforts/400 On/Tomo Dev Log.md",
    marker: str = "## Captures",
    composed_block: str = "### 2026-06-23\n\n- Shipped X (feature)",
    source_paths: list[str] | None = None,
) -> dict:
    """Minimal valid tag-handler-group result fixture (schema: tag-handler-group.schema.json)."""
    g: dict[str, Any] = {
        "schema_version": "1",
        "handler": handler,
        "target_path": target_path,
        "marker": marker,
        "composed_block": composed_block,
        "source_paths": source_paths or ["100 Inbox/MiYo-Tsukai-Tomo-cap-1.md"],
        "placement": "inside",
        "compose_mode": "llm_directive",
    }
    return g


def _inserts(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "insert_under_marker"]


def _deletes(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "delete_source"]


# ---------------------------------------------------------------------------
# Test A — the phase closes Bug B through the real Pass-2 gate.
# ---------------------------------------------------------------------------

def test_a_unresolved_group_through_real_gate_emits_nothing():
    """Null-target group, THREE source_paths (not one — Bug B's damage is one
    delete per source; a single-source fixture would hide the shape of it).

    Runs the real chain: annotate guards -> render -> parse -> build_actions.
    Asserts the parser yields no approved id for this group (T3.2's job), and
    that build_actions — even if somehow fed that empty approved-id list —
    emits zero insert_under_marker and zero delete_source (T3.1's job, since
    the group is not even in the approved set here).
    """
    g = _group(target_path=None, source_paths=[
        "100 Inbox/cap-1.md", "100 Inbox/cap-2.md", "100 Inbox/cap-3.md",
    ])
    annotate_tag_handler_group_guards([g], None)
    assert g["guard"] == "target_unresolved", (
        f"expected guard='target_unresolved' for a null target_path; got {g.get('guard')!r}"
    )

    rendered = render_tag_handler_updates_block([g])
    approved_ids = parse_tag_handler_groups(rendered)
    assert approved_ids == [], (
        f"a target_unresolved group must render with no Approve box, so the "
        f"parser must extract no id for it; got {approved_ids}"
    )

    actions, _skipped_assets = build_actions(
        [], [], [], [], _CFG, kado_client=None,
        tag_handler_groups=[g],
        approved_tag_handler_group_ids=approved_ids,
    )
    inserts = _inserts(actions)
    deletes = _deletes(actions)
    assert inserts == [], (
        f"Bug B must not reproduce: expected zero insert_under_marker for an "
        f"unresolved-target group reached via the real approval gate; got {inserts}"
    )
    assert deletes == [], (
        f"Bug B must not reproduce: expected zero delete_source for an "
        f"unresolved-target group's 3 sources reached via the real approval "
        f"gate (pre-fix this was one delete per source — 3 here); got {deletes}"
    )


# ---------------------------------------------------------------------------
# Test B — T3.1 is an independent second gate, not decorative. The "before"
# reproduction of Bug B.
# ---------------------------------------------------------------------------

def test_b_t3_1_gate_is_independent_of_the_render_parse_gate():
    """Simulates a caller that bypasses the render/parse gate entirely — e.g.
    a suggestions doc confirmed BEFORE T3.2 landed, replayed against today's
    build_actions with the stale approved id still in it. The group id is
    passed to `approved_tag_handler_group_ids` DIRECTLY, never through
    `parse_tag_handler_groups`.

    With the real, unpatched `_tag_handler_group_has_resolvable_target`:
    still 0 inserts / 0 deletes — T3.1 alone stops Bug B even when T3.2's
    render/parse gate is bypassed.

    Then the predicate is monkeypatched to always return True (module object
    `lib.render_actions`, the bare name both builders resolve at call time —
    NOT a re-export through instruction-render.py, which would silently
    no-op).

    Verified against the T3.1 commit (4efcc03) itself: pre-fix, the insert
    builder had its OWN standalone `if not target_path: continue` check,
    independent of anything the delete loop did — that standalone check is
    what produced Bug B's asymmetry (0 inserts / N deletes). T3.1 REPLACED
    that standalone check with a call to the new shared predicate (it did
    not add the predicate alongside the original check) — see the diff:
    `- if not target_path:` / `+ if not tag_handler_group_is_appliable(group):`.
    So today, both loops are gated by the SAME predicate and nothing else;
    forcing that one predicate open reopens BOTH sites, not just the delete
    site. Re-running with the patch live therefore reproduces exactly 3
    delete_source (one per source_path — the N-deletes half of Bug B) AND 1
    insert_under_marker carrying `target_path: None` (a path-less, unappliable
    instruction — the emission T3.1's gate exists to prevent on the insert
    side too). This is the live proof that T3.1 is one shared gate covering
    both sites, not two independent ones that happen to agree: forcing it
    open breaks both symmetrically. It also proves the patch binding is
    live — a no-op patch would keep showing 0/0.
    """
    g = _group(target_path=None, source_paths=[
        "100 Inbox/cap-1.md", "100 Inbox/cap-2.md", "100 Inbox/cap-3.md",
    ])
    gid = group_id(g)

    # Real predicate, bypassed gate: still safe.
    actions, _skipped_assets = build_actions(
        [], [], [], [], _CFG, kado_client=None,
        tag_handler_groups=[g],
        approved_tag_handler_group_ids=[gid],
    )
    assert _inserts(actions) == [], (
        f"with the real predicate, a bypassed-approval-gate replay must still "
        f"emit zero insert_under_marker; got {_inserts(actions)}"
    )
    assert _deletes(actions) == [], (
        f"with the real predicate, a bypassed-approval-gate replay must still "
        f"emit zero delete_source; got {_deletes(actions)}"
    )

    return_value_holder: dict[str, Any] = {}

    def _fake_has_resolvable_target(group: dict) -> bool:
        return_value_holder["called"] = True
        return True

    orig = _render_actions_mod._tag_handler_group_has_resolvable_target
    _render_actions_mod._tag_handler_group_has_resolvable_target = _fake_has_resolvable_target
    try:
        patched_actions, _skipped_assets = build_actions(
            [], [], [], [], _CFG, kado_client=None,
            tag_handler_groups=[g],
            approved_tag_handler_group_ids=[gid],
        )
    finally:
        _render_actions_mod._tag_handler_group_has_resolvable_target = orig

    assert return_value_holder.get("called"), (
        "the patched predicate was never invoked — the patch binding is not "
        "live (check module attribute vs. re-export)"
    )
    patched_inserts = _inserts(patched_actions)
    patched_deletes = _deletes(patched_actions)
    assert len(patched_deletes) == 3, (
        f"expected the historical Bug B N-deletes shape to reappear once "
        f"T3.1's shared gate is forced open: exactly 3 delete_source (one "
        f"per source_path); got {len(patched_deletes)} deletes: {patched_deletes}"
    )
    deleted_paths = {d["source_path"] for d in patched_deletes}
    assert deleted_paths == {"100 Inbox/cap-1.md", "100 Inbox/cap-2.md", "100 Inbox/cap-3.md"}, (
        f"expected exactly the group's 3 source_paths to be deleted; got {deleted_paths}"
    )
    # The insert side reopens too (see docstring: T3.1 replaced the insert
    # builder's own standalone null-target check with this same shared
    # predicate, it did not keep both) — forcing the predicate open emits a
    # path-less insert_under_marker instead of withholding it. This is the
    # live proof that both sites now hang off ONE gate, not two independent
    # ones: break it once, both sites break.
    assert len(patched_inserts) == 1, (
        f"expected the shared-gate bypass to also reopen the insert side "
        f"(one path-less insert_under_marker), proving both sites hang off "
        f"the same predicate; got {patched_inserts}"
    )
    assert patched_inserts[0]["target_path"] is None, (
        f"expected the reopened insert to carry the group's unresolved "
        f"target_path (None) verbatim — the predicate bypass does not "
        f"repair the data, only removes the gate; got {patched_inserts[0]}"
    )


# ---------------------------------------------------------------------------
# Test C — the consent half: no Approve control, reason present.
# ---------------------------------------------------------------------------

def test_c_rendered_block_has_no_approve_control_and_carries_reason():
    """Reuses Test A's render (a target_unresolved group renders with no
    Approve checkbox of either state, and states why)."""
    g = _group(target_path=None, source_paths=["100 Inbox/cap-1.md"])
    annotate_tag_handler_group_guards([g], None)
    rendered = render_tag_handler_updates_block([g])

    assert "- [x] Approve" not in rendered, (
        f"a target_unresolved group must not render a ticked Approve box; "
        f"got block:\n{rendered}"
    )
    assert "- [ ] Approve" not in rendered, (
        f"a target_unresolved group must not render an unticked Approve box "
        f"either — no Approve control of any kind; got block:\n{rendered}"
    )
    assert "Target unresolved" in rendered, (
        f"the block must carry the target_unresolved reason text; got "
        f"block:\n{rendered}"
    )


# ---------------------------------------------------------------------------
# Test D — the parser gate: healthy group yielded, unresolved group withheld.
# ---------------------------------------------------------------------------

def test_d_parser_yields_healthy_withholds_unresolved():
    healthy = _group(handler="tsukai", target_path="Efforts/400 On/Tomo Dev Log.md")
    unresolved = _group(handler="reading-log", target_path=None)
    annotate_tag_handler_group_guards([healthy, unresolved], None)
    # client=None fail-open leaves a resolvable-target group's "guard" key
    # unset entirely (the Kado-dependent loop that would set "ok" never
    # runs); render_tag_handler_group treats an absent guard as "ok" via
    # `group.get("guard") or "ok"`. The null-target annotation, by contrast,
    # runs unconditionally of `client` and always sets the key explicitly.
    assert healthy.get("guard") in (None, "ok"), (
        f"a resolvable-target group must not be hard-guarded; got "
        f"guard={healthy.get('guard')!r}"
    )
    assert unresolved["guard"] == "target_unresolved"

    rendered = render_tag_handler_updates_block([healthy, unresolved])
    approved_ids = parse_tag_handler_groups(rendered)
    assert approved_ids == [group_id(healthy)], (
        f"expected only the healthy group's id; got {approved_ids} "
        f"(healthy={group_id(healthy)!r}, unresolved={group_id(unresolved)!r})"
    )


# ---------------------------------------------------------------------------
# Test E — positive control: a resolvable, approved, marker-present group
# still emits exactly one insert and one delete per source.
# ---------------------------------------------------------------------------

def test_e_positive_control_healthy_group_emits_insert_and_deletes():
    g = _group(source_paths=["100 Inbox/cap-1.md", "100 Inbox/cap-2.md"])
    annotate_tag_handler_group_guards([g], None)
    assert g.get("guard") in (None, "ok"), (
        f"a resolvable-target group must not be hard-guarded; got "
        f"guard={g.get('guard')!r}"
    )
    rendered = render_tag_handler_updates_block([g])
    approved_ids = parse_tag_handler_groups(rendered)
    assert approved_ids == [group_id(g)]

    actions, _skipped_assets = build_actions(
        [], [], [], [], _CFG, kado_client=None,
        tag_handler_groups=[g],
        approved_tag_handler_group_ids=approved_ids,
    )
    inserts = _inserts(actions)
    deletes = _deletes(actions)
    assert len(inserts) == 1, f"expected exactly one insert_under_marker; got {inserts}"
    assert len(deletes) == 2, (
        f"expected exactly one delete_source per source_path (2); got {deletes}"
    )
    assert deletes[0]["depends_on"] == [inserts[0]["id"]]
    assert deletes[1]["depends_on"] == [inserts[0]["id"]]


# ---------------------------------------------------------------------------
# Test F — mixed run: no cross-group leak in shared bookkeeping.
# ---------------------------------------------------------------------------

def test_f_mixed_run_no_leak_between_unresolved_and_healthy_groups():
    """One target_unresolved group (3 sources) and one healthy group (2
    sources) in ONE tag_handler_groups list, ONE build_actions call, with
    approved_ids parsed from both rendered blocks together. Both groups run
    through the same `for group in (tag_handler_groups or [])` loop with
    shared bookkeeping (approved_groups/kept_groups/insert_action_ids_by_group/
    emitted) — this is the leak check that the unresolved group's 3 sources
    do not bleed into the count."""
    unresolved = _group(
        handler="reading-log", target_path=None,
        source_paths=["100 Inbox/u1.md", "100 Inbox/u2.md", "100 Inbox/u3.md"],
    )
    healthy = _group(
        handler="tsukai", target_path="Efforts/400 On/Tomo Dev Log.md",
        source_paths=["100 Inbox/h1.md", "100 Inbox/h2.md"],
    )
    annotate_tag_handler_group_guards([unresolved, healthy], None)
    rendered = render_tag_handler_updates_block([unresolved, healthy])
    approved_ids = parse_tag_handler_groups(rendered)
    assert approved_ids == [group_id(healthy)], (
        f"only the healthy group should be approved out of the mixed render; "
        f"got {approved_ids}"
    )

    actions, _skipped_assets = build_actions(
        [], [], [], [], _CFG, kado_client=None,
        tag_handler_groups=[unresolved, healthy],
        approved_tag_handler_group_ids=approved_ids,
    )
    inserts = _inserts(actions)
    deletes = _deletes(actions)
    assert len(inserts) == 1, (
        f"expected exactly 1 insert_under_marker (the healthy group only); "
        f"got {inserts}"
    )
    assert inserts[0]["target_path"] == "Efforts/400 On/Tomo Dev Log.md", (
        f"the one insert must belong to the healthy group; got {inserts[0]}"
    )
    assert len(deletes) == 2, (
        f"expected exactly 2 delete_source (healthy group's 2 sources only, "
        f"none of the unresolved group's 3 leaking in); got {len(deletes)} "
        f"deletes: {deletes}"
    )
    deleted_paths = {d["source_path"] for d in deletes}
    assert deleted_paths == {"100 Inbox/h1.md", "100 Inbox/h2.md"}, (
        f"expected exactly the healthy group's source_paths deleted, no "
        f"unresolved-group sources; got {deleted_paths}"
    )
