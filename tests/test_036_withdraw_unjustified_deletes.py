#!/usr/bin/env python3
# version: 0.1.0
"""test_036_withdraw_unjustified_deletes.py — spec 036 / T2.1 enforcement pass.

Covers `withdraw_unjustified_deletes(actions) -> (kept, withdrawn)` in
`tomo/scripts/lib/render_actions.py` — the pure pass that runs once, after
every drop site, and withdraws any `delete_source` whose `depends_on` names
an id that is no longer in the action set.

Contract under test (docs/XDD/specs/036-delete-outlives-its-justification/
plan/phase-2.md T2.1):

- Pure: no I/O, does not mutate its input.
- Only `delete_source` actions are governed; every other action passes
  through untouched, even one carrying a `depends_on` naming a missing id.
- AND semantics: withdrawn if ANY named id is absent; kept only if ALL are
  present.
- `depends_on: []` is a positive assertion ("nothing conditions this
  delete") — never withdrawn.
- A missing `depends_on` key reads as `[]` — kept. Unreachable from the
  builder since Phase 1 (schema-required), but reachable from a hand-built
  dict or an older artifact — the defensive reading is deliberate.
- Each withdrawal record carries id, source_path, reason, and
  missing_dependencies.

Tests are RED against current code (no `withdraw_unjustified_deletes` in
lib/render_actions.py) and GREEN after T2.1.

Spec: docs/XDD/specs/036-delete-outlives-its-justification/ Phase 2, T2.1.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, rel: str):
    """Load a hyphenated top-level script or lib module — house pattern
    (see tests/test_036_depends_on_emission.py, tests/test_tag_handler_group_instruction_linkage.py)."""
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


render_actions = _load("render_actions_t036_withdraw", "lib/render_actions.py")

INBOX = "100 Inbox/"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _delete(id_, source_path="Origin.md", depends_on=(), reason="Source consolidated.", with_key=True):
    """A minimal delete_source action. with_key=False omits `depends_on`
    entirely (test 6)."""
    d = {
        "id": id_,
        "action": "delete_source",
        "source_path": source_path,
        "reason": reason,
    }
    if with_key:
        d["depends_on"] = list(depends_on)
    return d


def _move(id_, depends_on=None):
    """A minimal non-delete action. Optionally carries `depends_on` itself
    (test 8) — that field must be irrelevant for anything but a delete."""
    d = {
        "id": id_,
        "action": "move_note",
        "source": f"100 Inbox/rendered-{id_}.md",
        "destination": f"200 Notes/{id_}.md",
    }
    if depends_on is not None:
        d["depends_on"] = list(depends_on)
    return d


# ── 1-2. Basic withdrawal / keep on presence of the named id ────────────────


def test_delete_naming_a_dropped_action_is_withdrawn():
    """A delete depending on an id that never made it into the action set
    (the action it justified itself was dropped upstream) is withdrawn."""
    d1 = _delete("D1", depends_on=["A1"])  # A1 is not in the action set at all

    kept, withdrawn = render_actions.withdraw_unjustified_deletes([d1])

    assert kept == [], f"expected D1 withdrawn, not kept; got {kept!r}"
    assert [w["id"] for w in withdrawn] == ["D1"]


def test_delete_naming_a_surviving_action_is_kept():
    """A delete depending on an id that IS present in the action set is kept."""
    a1 = _move("A1")
    d1 = _delete("D1", depends_on=["A1"])

    kept, withdrawn = render_actions.withdraw_unjustified_deletes([a1, d1])

    assert [a["id"] for a in kept] == ["A1", "D1"]
    assert withdrawn == []


# ── 3. depends_on: [] is a positive assertion, never withdrawn ──────────────


@pytest.mark.parametrize(
    "surrounding",
    [
        pytest.param([], id="no_other_actions"),
        pytest.param([_move("A1")], id="a_surviving_action_present"),
        pytest.param([_delete("D2", depends_on=["MISSING"])], id="another_delete_gets_withdrawn"),
        pytest.param(
            [_move("A1"), _delete("D2", depends_on=["A1"])],
            id="mixed_surviving_action_and_kept_delete",
        ),
    ],
)
def test_empty_depends_on_is_kept(surrounding):
    """`depends_on: []` asserts 'nothing conditions this delete' — it must
    never be withdrawn, regardless of what else the guard finds withdrawable
    or keepable around it."""
    d1 = _delete("D1", depends_on=[])
    actions = surrounding + [d1]

    kept, withdrawn = render_actions.withdraw_unjustified_deletes(actions)

    kept_ids = [a["id"] for a in kept]
    withdrawn_ids = [w["id"] for w in withdrawn]
    assert "D1" in kept_ids, f"D1 (depends_on=[]) must be kept; kept={kept_ids!r}"
    assert "D1" not in withdrawn_ids, f"D1 (depends_on=[]) must never be withdrawn; withdrawn={withdrawn_ids!r}"


# ── 4-5. AND semantics, not OR ───────────────────────────────────────────────


def test_one_missing_of_three_withdraws():
    """Three named ids, two present, one absent → withdrawn. This is what
    falsifies OR-instead-of-AND: a single-id test cannot, because most real
    cases carry exactly one id — with three ids, an OR-based implementation
    would need only one hit to keep the delete, while AND correctly demands
    all three."""
    a1 = _move("A1")
    a2 = _move("A2")
    d1 = _delete("D1", depends_on=["A1", "A2", "A3"])  # A3 absent

    kept, withdrawn = render_actions.withdraw_unjustified_deletes([a1, a2, d1])

    assert [a["id"] for a in kept] == ["A1", "A2"]
    assert [w["id"] for w in withdrawn] == ["D1"]
    assert withdrawn[0]["missing_dependencies"] == ["A3"]


def test_all_three_present_is_kept():
    """The AND counterpart to test 4 — with all three ids present, D1 must
    be kept, so test 4 cannot pass by an implementation that simply
    withdraws every multi-id delete."""
    a1 = _move("A1")
    a2 = _move("A2")
    a3 = _move("A3")
    d1 = _delete("D1", depends_on=["A1", "A2", "A3"])

    kept, withdrawn = render_actions.withdraw_unjustified_deletes([a1, a2, a3, d1])

    assert [a["id"] for a in kept] == ["A1", "A2", "A3", "D1"]
    assert withdrawn == []


# ── 6. Missing depends_on key reads as [] ────────────────────────────────────


def test_delete_with_no_depends_on_key_is_kept():
    """A delete missing the `depends_on` key entirely (unreachable from the
    builder since Phase 1, but reachable from a hand-built dict or an older
    artifact) is read defensively as `[]` — kept, not withdrawn."""
    d1 = _delete("D1", with_key=False)
    assert "depends_on" not in d1

    kept, withdrawn = render_actions.withdraw_unjustified_deletes([d1])

    assert [a["id"] for a in kept] == ["D1"]
    assert withdrawn == []


# ── 7. Purity — input list and its dicts are not mutated ────────────────────


def test_input_list_is_not_mutated():
    a1 = _move("A1")
    d1 = _delete("D1", depends_on=["A1"])
    d2 = _delete("D2", depends_on=["MISSING"])
    actions = [a1, d1, d2]

    before_len = len(actions)
    before_ids = [a["id"] for a in actions]
    before_identities = [id(a) for a in actions]
    before_snapshot = [dict(a) for a in actions]  # deep-enough copy for comparison

    render_actions.withdraw_unjustified_deletes(actions)

    assert len(actions) == before_len
    assert [a["id"] for a in actions] == before_ids
    assert [id(a) for a in actions] == before_identities, "input list's dict objects must not be replaced"
    assert actions == before_snapshot, "input dicts must not be mutated in place"


# ── 8. Non-delete actions pass through untouched, even a misleading one ────


def test_non_delete_actions_are_never_touched():
    """A non-delete action carrying a `depends_on` that names a missing id
    must still survive untouched — only `delete_source` is governed."""
    m1 = _move("M1", depends_on=["MISSING"])

    kept, withdrawn = render_actions.withdraw_unjustified_deletes([m1])

    assert kept == [m1]
    assert withdrawn == []


# ── 9. Withdrawal record shape ───────────────────────────────────────────────


def test_withdrawal_record_carries_missing_id_source_path_and_reason():
    a1 = _move("A1")
    d1 = _delete(
        "D1",
        source_path="100 Inbox/Origin.md",
        depends_on=["A1", "A2"],  # A2 absent
        reason="Content fully captured in daily note.",
    )

    _kept, withdrawn = render_actions.withdraw_unjustified_deletes([a1, d1])

    assert len(withdrawn) == 1
    record = withdrawn[0]
    assert record["id"] == "D1"
    assert record["source_path"] == "100 Inbox/Origin.md"
    assert record["reason"] == "Content fully captured in daily note."
    assert record["missing_dependencies"] == ["A2"]


# ── 10. Single-pass semantics — no cascade ───────────────────────────────────


def test_no_cascade_needed_single_pass_semantics():
    """Synthetic chain: D1 depends on action A (already dropped upstream —
    A is not in the input at all). D2 depends on D1. The pass runs ONCE:
    D1 is withdrawn (A is missing), but D2 is KEPT, because `surviving` is
    computed from the INPUT action set before anything is withdrawn — D1's
    id is still present in that input set even though D1 itself ends up
    withdrawn.

    Keeping D2 here is correct ONLY under the precondition proven by test 11
    (test_nothing_declares_a_dependency_on_a_delete): in real build_actions
    output, nothing ever names a delete's id in `depends_on`. This test is a
    tripwire, not an endorsement of delete-depends-on-delete chains — if a
    delete ever legitimately depends on another delete, THIS test is the one
    that must change (to demand a cascading/fixed-point pass instead).
    """
    d1 = _delete("D1", source_path="A.md", depends_on=["A"])  # "A" was already dropped
    d2 = _delete("D2", source_path="B.md", depends_on=["D1"])  # D1 IS in the input set

    kept, withdrawn = render_actions.withdraw_unjustified_deletes([d1, d2])

    kept_ids = [a["id"] for a in kept]
    withdrawn_ids = [w["id"] for w in withdrawn]
    assert withdrawn_ids == ["D1"], f"expected only D1 withdrawn; got {withdrawn_ids!r}"
    assert kept_ids == ["D2"], f"expected D2 kept (single pass, no cascade); got {kept_ids!r}"


# ── 11. Precondition — nothing depends on a delete, in real builder output ──


def _real_scenario_actions() -> list[dict]:
    """Exercise several real delete_source sites via the real builders
    (site 1: user-requested; site 3: move_note origin; site 4: tag-handler
    group) and return the full action list build_actions() produces.

    Mirrors the fixture patterns in tests/test-008-phase1.py (manifest +
    confirmed + skipped) and tests/test_tag_handler_group_instruction_linkage.py
    (_group / group_id), assembled minimally here to keep this test
    self-contained.
    """
    manifest = [
        {
            "id": "A1",
            "action": None,
            "title": "Some Note",
            "source_path": "some-note.md",
            "template": "t_note_tomo",
            "rendered_file": "2026-04-21_1200_some-note.md",
            "rendered_path": "/tmp/rendered/2026-04-21_1200_some-note.md",
            "destination": "Atlas/202 Notes/",
            "parent_moc": "",
            "parent_mocs": [],
            "tags": [],
        },
    ]
    confirmed = [
        {
            "id": "A1",
            "source_path": "some-note.md",
            "action": None,
            "title": "Some Note",
            "tags": [],
            "parent_moc": "",
            "parent_mocs": [],
        },
    ]
    skipped = [
        {"id": "B1", "source_path": "trash.md", "disposition": "delete_source"},
    ]
    group = {
        "schema_version": "1",
        "handler": "tsukai",
        "target_path": "Efforts/Tomo Dev Log.md",
        "marker": "## Captures",
        "composed_block": "### 2026-04-21\n\n- Did a thing",
        "source_paths": ["100 Inbox/captured.md"],
        "placement": "inside",
        "compose_mode": "llm_directive",
    }
    group_id = render_actions.group_id(group)

    actions, _skipped_assets = render_actions.build_actions(
        manifest, confirmed, [], skipped, CFG,
        tag_handler_groups=[group],
        approved_tag_handler_group_ids=[group_id],
    )
    return actions


def test_nothing_declares_a_dependency_on_a_delete():
    """The precondition test 10's tripwire depends on: in real build_actions
    output, no action's `depends_on` names the id of a `delete_source`
    action — deletes are always the leaves of the dependency graph.

    Built against REAL build_actions output (not a hand-built list) across
    the sites that actually declare depends_on: site 1 (user-requested
    delete), site 3 (move_note origin), and site 4 (tag-handler group).
    Site 2 (daily-only origins) is not separately exercised here; it uses
    the same depends_on-population mechanism as sites 1/3/4 and adds no new
    risk of a delete-depending-on-delete edge.
    """
    actions = _real_scenario_actions()
    delete_ids = {a["id"] for a in actions if a.get("action") == "delete_source"}
    assert delete_ids, "scenario must actually produce delete_source actions to test anything"

    for a in actions:
        for dep in a.get("depends_on", []) or []:
            assert dep not in delete_ids, (
                f"action {a.get('id')!r} ({a.get('action')!r}) depends on "
                f"delete {dep!r} — the no-cascade precondition is violated"
            )
