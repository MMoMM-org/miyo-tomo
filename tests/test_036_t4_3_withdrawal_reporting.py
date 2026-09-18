#!/usr/bin/env python3
# version: 0.3.0
"""test_036_t4_3_withdrawal_reporting.py — spec 036 / T4.3 withdrawal reporting.

Covers the T4.3 join and its three report surfaces (plan/phase-4.md T4.3;
SDD "System-Wide Patterns / Logging-Auditing"; PRD F2-AC4, F6-AC1, F6-AC2):

  - `attribute_withdrawal_causes` / `describe_withdrawal_cause` /
    `build_delete_withdrawal_reports` (`tomo/scripts/lib/render_helpers.py`)
    — the pure join from a `withdraw_unjustified_deletes` record to the guard
    that dropped its missing id(s).
  - stderr (`instruction-render.py`'s withdrawal print block).
  - the `tomo.delete_withdrawals` key in `instructions.json` — a TOP-LEVEL
    key holding full records, deliberately distinct from the existing
    NESTED `withdrawn_deletes` key (a list of paths, inside a
    destination_clashes/attachment_suppressions entry, read by
    `instructions-diff.py`'s coverage join). Same name at a different level
    with a different shape is exactly the drift spec 036 T2.2 already
    declined once — see docs/tomo/scripts/lib/render_helpers.md.
  - the "## Skipped — un-appliable actions" section in `instructions.md`,
    including the F2-AC4 structural-adjacency requirement: a withheld daily
    action and the delete it withdrew must read as grouped, not merely
    co-occurring.

Tests are RED against current code (no `attribute_withdrawal_causes` /
`describe_withdrawal_cause` / `build_delete_withdrawal_reports` in
lib/render_helpers.py; no `tomo.delete_withdrawals` key; no adjacency in the
markdown renderer) and GREEN after T4.3.

instructions-diff.py finding (T4.3 gate, recorded rather than left implied):
NOT wired to the new key. `derive_expected`'s daily-only and tag-handler
`expected_deletions` are built from the SUGGESTIONS document alone (Pass 1),
independent of what the renderer later withdrew, and no existing
`_subtract_*` reads `skipped_daily`/`skipped_rel`/`unresolvable_moc_links` to
prune `expected_deletions` the way `_subtract_withheld_moves` prunes it for
`destination_clashes`/`attachment_suppressions`. So a live daily-note-missing
or unresolvable-tag-handler-group run can still show a coverage mismatch in
`instructions-diff.py` after this task — a real, PRE-EXISTING gap this task
did not create and whose fix is not among T4.3's success criteria (all four
are about the three report surfaces, not the coverage audit). Logged in
docs/XDD/backlog.md rather than silently left for the next reader to
rediscover.

Spec: docs/XDD/specs/036-delete-outlives-its-justification/ Phase 4, T4.3.

Follow-up (spec 035 T-delete-reaches-user, live run 2026-09-18): the markdown
and stderr surfaces described above turned out to be the WRONG pair to share
one wording function. `describe_withdrawal_cause` stayed technical for stderr;
`render_md.py` now calls `describe_withdrawal_cause_for_user`, its plain-
language sibling (no action id, no wire action name, no guard function name —
ADR-11, "no executor internals in the rendered text"). The three
`TestMarkdownSkippedSection` tests that asserted the OLD technical wording
(`D1`, `delete_source`, `I05`, `filter_missing_daily_notes`) are rewritten
below to assert its ABSENCE instead, with a stable non-id anchor
("a delete was withheld:") replacing the "withdrawn: `D1`" positional
anchor. `instructions-diff.py` also gained `_subtract_withdrawn_deletes`
(tested separately, tests/test_036_t4_4_withdrawn_delete_coverage.py) so a
withdrawn delete no longer reads as a coverage mismatch, and
`render_instructions_md` now states a withdrawn delete under "## Source
Deletions" itself, not only cross-referenced from "## Skipped" — see the new
`TestSourceDeletionsWithdrawalNotice` class below.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_helpers import (  # noqa: E402
    WITHDRAWAL_GUARDS,
    attribute_withdrawal_causes,
    build_delete_withdrawal_reports,
    describe_withdrawal_cause,
    describe_withdrawal_cause_for_user,
)
from lib.render_md import _INLINE_WITHDRAWAL_GUARDS, render_instructions_md  # noqa: E402

_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render_t036_t43", SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_t036_t43"] = _ir
_ir_spec.loader.exec_module(_ir)

# Sourced from render_helpers.WITHDRAWAL_GUARDS (the documented SSoT),
# not re-typed, so this alias can never silently drift from it (code-quality
# review advisory: ALL_GUARDS used to be an independent hardcoded tuple).
ALL_GUARDS = WITHDRAWAL_GUARDS

CFG = {"concepts.inbox": "100 Inbox/", "profile": "miyo"}


# ── Fixtures ──────────────────────────────────────────────────────────────


def _withdrawal(
    id_="D1",
    source_path="100 Inbox/Origin.md",
    reason="Content fully captured in daily note.",
    missing=("I05",),
    declared=True,
):
    return {
        "id": id_,
        "source_path": source_path,
        "reason": reason,
        "missing_dependencies": list(missing) if declared else None,
        "depends_on_declared": declared,
    }


def _empty_drop_sources(**over):
    sources = {g: [] for g in ALL_GUARDS}
    sources.update(over)
    return sources


DAILY_ACTION = {
    "id": "I05",
    "action": "update_log_entry",
    "daily_note_path": "Calendar/301 Daily/2026-09-17.md",
    "date": "2026-09-17",
    "content": "Logged in daily.",
    "applied": False,
}

WITHDRAWN_DELETE = {
    "id": "D1",
    "action": "delete_source",
    "source_path": "100 Inbox/Origin.md",
    "reason": "Content fully captured in daily note.",
    "depends_on": ["I05"],
    "applied": False,
}


# ── 1-2, part of 5. attribute_withdrawal_causes — one guard per test ───────


class TestAttributeWithdrawalCauses:
    """Unit coverage of the pure join. All five guards covered (task text:
    "the three report shapes mean a join tested against one shape proves
    nothing about the others")."""

    @pytest.mark.parametrize("guard", ALL_GUARDS)
    def test_missing_id_attributed_to_the_guard_that_dropped_it(self, guard):
        drop_sources = _empty_drop_sources(**{guard: ["I05"]})
        causes = attribute_withdrawal_causes(_withdrawal(missing=["I05"]), drop_sources)
        assert causes == [{"missing_id": "I05", "guard": guard}]

    def test_three_of_the_five_report_shapes_flow_through_one_join(self):
        """The five guards report in three distinct shapes at the
        instruction-render.py call site (a `dropped` list nested in a
        clash/suppression record for two of them; a flat skipped-action list
        for the other three) — this proves the CALLER's normalisation into
        `drop_sources` id-lists is what the join actually needs, by feeding
        the join two guards' worth of ids at once and checking neither
        collides with the other."""
        drop_sources = _empty_drop_sources(
            validate_destinations=["M01"],
            filter_missing_daily_notes=["I05"],
        )
        assert attribute_withdrawal_causes(
            _withdrawal(missing=["M01"]), drop_sources
        ) == [{"missing_id": "M01", "guard": "validate_destinations"}]
        assert attribute_withdrawal_causes(
            _withdrawal(missing=["I05"]), drop_sources
        ) == [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}]


# ── 3. depends_on_declared: False — distinct wording, no guard ─────────────


class TestUndeclaredDependency:
    def test_undeclared_dependency_attributed_to_no_guard(self):
        causes = attribute_withdrawal_causes(_withdrawal(declared=False), {})
        assert causes == [{"missing_id": None, "guard": None}]

    def test_undeclared_wording_is_distinct_from_unresolved_join(self):
        undeclared = describe_withdrawal_cause({"missing_id": None, "guard": None})
        unattributed = describe_withdrawal_cause(
            {"missing_id": "GHOST", "guard": "unattributed"}
        )
        assert undeclared != unattributed
        assert "declared" in undeclared
        assert "unattributed" not in undeclared
        assert "unattributed" in unattributed


# ── 4. missing id in no drop list — explicit "unattributed", tripwire ──────


class TestUnattributedTripwire:
    def test_missing_id_in_no_drop_list_is_unattributed_not_silent(self):
        """Structurally unreachable through the real pipeline today:
        `withdraw_unjustified_deletes` runs after all five guards (SDD
        ADR-2), so every id it can name was either dropped by one of them or
        never existed in the set at all. This is a tripwire against a future
        sixth drop site that removes an action without reporting what it
        removed — a withdrawal must never go silently unexplained, and this
        function must never crash on it either."""
        drop_sources = _empty_drop_sources(filter_missing_daily_notes=["SOME_OTHER_ID"])
        causes = attribute_withdrawal_causes(
            _withdrawal(missing=["GHOST_UNKNOWN"]), drop_sources
        )
        assert causes == [{"missing_id": "GHOST_UNKNOWN", "guard": "unattributed"}]

    def test_unattributed_does_not_crash_on_empty_drop_sources(self):
        causes = attribute_withdrawal_causes(_withdrawal(missing=["X"]), {})
        assert causes == [{"missing_id": "X", "guard": "unattributed"}]


# 5. NOT a test: an id present in two guards' dropped-id lists is
# structurally impossible. The five guards govern disjoint action kinds —
# validate_destinations and suppress_moves_for_unfiled_attachments drop
# move_note/create_moc ids, filter_unresolvable_moc_links drops link_to_moc
# ids, filter_missing_daily_notes drops daily-action ids, and filter_
# unappliable_relationships drops add_relationship ids — so one id cannot
# appear in two guards' lists in the same run. `attribute_withdrawal_causes`'
# `setdefault` (first match wins) exists for defensive determinism only, not
# because a collision is reachable.


# ── 9-10. describe_withdrawal_cause_for_user vs. its technical sibling ─────


class TestUserFacingWithdrawalWording:
    """spec 035 T-delete-reaches-user: the markdown surface must lose the
    internals (ADR-11) while stderr stays technical — tests 9/10 of that
    task's plan, proving the two functions now genuinely differ."""

    @pytest.mark.parametrize("guard", ALL_GUARDS)
    def test_user_facing_wording_names_no_guard_or_id(self, guard):
        cause = {"missing_id": "I05", "guard": guard}
        text = describe_withdrawal_cause_for_user(cause)
        assert guard not in text
        assert "I05" not in text
        assert "missing id" not in text

    def test_user_facing_wording_covers_undeclared_and_unattributed_too(self):
        undeclared = describe_withdrawal_cause_for_user({"missing_id": None, "guard": None})
        unattributed = describe_withdrawal_cause_for_user(
            {"missing_id": "GHOST", "guard": "unattributed"}
        )
        assert "GHOST" not in unattributed
        assert "unattributed" not in unattributed
        assert undeclared != unattributed

    def test_technical_sibling_is_unchanged_and_still_carries_the_guard_name(self):
        """describe_withdrawal_cause (stderr) must stay exactly as it was —
        this is the sibling test_daily_withdrawal_reports_missing_id_and_
        guard_on_stderr already pins end-to-end; this pins the unit directly."""
        cause = {"missing_id": "I05", "guard": "filter_missing_daily_notes"}
        assert describe_withdrawal_cause(cause) == (
            "missing id I05 (dropped by filter_missing_daily_notes)"
        )


# ── build_delete_withdrawal_reports — reason threaded verbatim ─────────────


class TestBuildDeleteWithdrawalReports:
    def test_reason_is_the_withdrawal_records_own_field_not_reworded(self):
        w = _withdrawal(reason="Origin consumed by 1 atomic.")
        reports = build_delete_withdrawal_reports([w], _empty_drop_sources())
        assert reports[0]["reason"] == "Origin consumed by 1 atomic."
        assert reports[0]["id"] == "D1"
        assert reports[0]["action"] == "delete_source"
        assert reports[0]["source_path"] == "100 Inbox/Origin.md"


# ── Full-pipeline harness (mirrors TestAssertNoDanglingDependenciesIntegration
#    in test_instruction_render_wire_hygiene.py) ────────────────────────────


def _suggestions_payload():
    # confirmed_items carries one template-less, source_path-less item so
    # `if confirmed:` is True (KadoClient() gets constructed) while filter_
    # missing_source_notes and the render loop both no-op on it (#116 keeps
    # items without a template or source_path unconditionally). daily_updates
    # is non-empty only to clear main()'s "nothing to do" early return —
    # build_actions is stubbed below and never reads its content.
    return {
        "confirmed_items": [{"id": "C0"}],
        "daily_updates": [{"id": "dummy"}],
        "skipped": [],
    }


def _stub_pipeline(monkeypatch, base_dir: Path, fixture_actions: list[dict], client) -> Path:
    """Stub only the I/O boundary. `validate_destinations`, `suppress_moves_
    for_unfiled_attachments`, `filter_unresolvable_moc_links`, `filter_
    missing_daily_notes`, `filter_unappliable_relationships`, `withdraw_
    unjustified_deletes`, `assert_no_dangling_dependencies` and `render_
    instructions_md` all run for real, over *fixture_actions* unchanged —
    build_actions is replaced outright, matching the pattern in test_
    instruction_render_wire_hygiene.py's `_stub_dangling_audit_pipeline`.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    suggestions_file = base_dir / "suggestions.json"
    suggestions_file.write_text(json.dumps(_suggestions_payload()), encoding="utf-8")
    cfg_file = base_dir / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        _ir, "load_config",
        lambda _path: {
            "concepts.inbox": "100 Inbox",
            "profile": "miyo",
            "callouts.editable": ["NOTE", "IDEAS"],
        },
    )
    monkeypatch.setattr(_ir, "KadoClient", lambda: client)
    monkeypatch.setattr(_ir, "build_actions", lambda *_a, **_kw: (fixture_actions, []))
    monkeypatch.setattr(_ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(_ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(_ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(_ir, "backfill_supporting_items_parents", lambda _items: None)

    out_dir = base_dir / "out"
    monkeypatch.setattr(
        sys, "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_file),
            "--output-dir", str(out_dir),
            "--config", str(cfg_file),
        ],
    )
    return out_dir


def _client(note_exists: bool) -> MagicMock:
    client = MagicMock()
    client.note_exists.return_value = note_exists
    return client


# ── Code-quality review advisory: WITHDRAWAL_GUARDS is the documented SSoT
#    for the five guard names, but nothing previously imported or validated
#    against it — a sixth guard added to one copy would be caught by none of
#    the others. Three call sites now validate: this file's ALL_GUARDS alias
#    (see import above), render_md.py's module-level subset assertion, and
#    instruction-render.py's module-level equality assertion. ───────────────


class TestWithdrawalGuardsStaySynced:
    def test_inline_withdrawal_guards_is_a_proper_subset_of_withdrawal_guards(self):
        """`_INLINE_WITHDRAWAL_GUARDS` (render_md.py) is legitimately a
        SUBSET, not the full set — only the three guards whose own report
        already renders a bullet inside "## Skipped" nest inline;
        `validate_destinations` and `suppress_moves_for_unfiled_attachments`
        render under their own "## Not filed" headings and are deliberately
        excluded, so the relation is subset, not equality."""
        assert _INLINE_WITHDRAWAL_GUARDS <= set(WITHDRAWAL_GUARDS)
        assert _INLINE_WITHDRAWAL_GUARDS < set(WITHDRAWAL_GUARDS)

    def test_drop_sources_keys_match_withdrawal_guards_exactly(self, monkeypatch, tmp_path):
        """`drop_sources` (instruction-render.py, built inside `main`) must
        cover every guard in `WITHDRAWAL_GUARDS` and no others — unlike
        `_INLINE_WITHDRAWAL_GUARDS`'s subset, every one of the five guards'
        drops must be attributable, so the relation is equality.
        `main()` only returns 0 here (rather than raising) if
        instruction-render.py's own `assert set(drop_sources) ==
        set(WITHDRAWAL_GUARDS)` held — this test names that invariant
        directly rather than leaving it implied by "nothing crashed"."""
        actions = [dict(DAILY_ACTION), dict(WITHDRAWN_DELETE)]
        _stub_pipeline(monkeypatch, tmp_path, actions, _client(note_exists=False))
        assert _ir.main() == 0


# ── 6-7. stderr ──────────────────────────────────────────────────────────


class TestStderrReporting:
    def test_daily_withdrawal_reports_missing_id_and_guard_on_stderr(
        self, monkeypatch, tmp_path, capsys
    ):
        actions = [dict(DAILY_ACTION), dict(WITHDRAWN_DELETE)]
        _stub_pipeline(monkeypatch, tmp_path, actions, _client(note_exists=False))
        assert _ir.main() == 0
        err = capsys.readouterr().err
        assert "1 delete_source action(s) withdrawn" in err
        assert "D1" in err
        assert "100 Inbox/Origin.md" in err
        assert "I05" in err
        assert "filter_missing_daily_notes" in err

    def test_no_withdrawal_run_emits_no_withdrawal_block_on_stderr(
        self, monkeypatch, tmp_path, capsys
    ):
        """Regression guard: no withdrawal record -> `delete_withdrawals` is
        empty -> the `if delete_withdrawals:` block never prints. True before
        T4.3 (the old block guarded on `withdrawn_deletes` the same way) and
        drives no new code — kept explicit rather than assumed."""
        actions = [dict(DAILY_ACTION), dict(WITHDRAWN_DELETE)]
        _stub_pipeline(monkeypatch, tmp_path, actions, _client(note_exists=True))
        assert _ir.main() == 0
        err = capsys.readouterr().err
        assert "withdrawn" not in err


# ── 11-12. tomo block in instructions.json ─────────────────────────────────


class TestTomoBlockDeleteWithdrawals:
    def test_withdrawal_writes_tomo_block_delete_withdrawals(self, monkeypatch, tmp_path):
        actions = [dict(DAILY_ACTION), dict(WITHDRAWN_DELETE)]
        out_dir = _stub_pipeline(monkeypatch, tmp_path, actions, _client(note_exists=False))
        assert _ir.main() == 0
        doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
        withdrawals = doc["tomo"]["delete_withdrawals"]
        assert len(withdrawals) == 1
        w = withdrawals[0]
        assert w["id"] == "D1"
        assert w["source_path"] == "100 Inbox/Origin.md"
        assert w["causes"] == [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}]

    def test_no_withdrawal_omits_key_never_an_empty_list(self, monkeypatch, tmp_path):
        actions = [dict(DAILY_ACTION), dict(WITHDRAWN_DELETE)]
        out_dir = _stub_pipeline(monkeypatch, tmp_path, actions, _client(note_exists=True))
        assert _ir.main() == 0
        doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
        tomo_block = doc.get("tomo") or {}
        assert "delete_withdrawals" not in tomo_block


# ── 13-14. Constitution L2 — metadata only, reason threaded verbatim ───────


class TestConstitutionL2MetadataOnly:
    SENTINEL = "ZzQ7-PRIVATE-NOTE-BODY-SENTINEL-9f2c"

    def test_note_content_never_reaches_any_surface(self, monkeypatch, tmp_path, capsys):
        """`body` is not a field any of the three report surfaces reads —
        proves the report threads NAMED fields (id/source_path/reason/
        causes), never the whole action dict, which is how note content
        would leak by accident."""
        delete_action = dict(WITHDRAWN_DELETE)
        delete_action["body"] = self.SENTINEL
        actions = [dict(DAILY_ACTION), delete_action]
        out_dir = _stub_pipeline(monkeypatch, tmp_path, actions, _client(note_exists=False))
        assert _ir.main() == 0

        err = capsys.readouterr().err
        assert self.SENTINEL not in err

        md = (out_dir / "instructions.md").read_text(encoding="utf-8")
        assert self.SENTINEL not in md

        doc_text = (out_dir / "instructions.json").read_text(encoding="utf-8")
        assert self.SENTINEL not in doc_text

    def test_reason_threaded_verbatim_is_the_builder_template(self, monkeypatch, tmp_path):
        template_reason = "Content fully captured in daily note."
        delete_action = dict(WITHDRAWN_DELETE)
        delete_action["reason"] = template_reason
        actions = [dict(DAILY_ACTION), delete_action]
        out_dir = _stub_pipeline(monkeypatch, tmp_path, actions, _client(note_exists=False))
        assert _ir.main() == 0
        doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
        assert doc["tomo"]["delete_withdrawals"][0]["reason"] == template_reason


# ── 8-10. markdown — direct render_instructions_md calls ───────────────────


def _md_metadata(**over):
    base = {"generated": "2026-09-17T00:00:00Z", "profile": "miyo"}
    base.update(over)
    return base


class TestMarkdownSkippedSection:
    def test_withdrawal_renders_inside_existing_skipped_heading(self):
        """Inverted 2026-09-18 (spec 035 T-delete-reaches-user): the markdown
        must lose the internals ADR-11 forbids — no action id, no wire action
        name, no guard function name. Two headings now, not one:
        "## Skipped" (this withdrawal's cross-reference under its matching
        daily bullet) AND "## Source Deletions" (the same withdrawal's own
        visible statement, Change 3b) — the latter is asserted by
        TestSourceDeletionsWithdrawalNotice below in more detail; here it is
        only the heading count that must account for it.
        """
        delete_withdrawals = [{
            "id": "D1", "action": "delete_source",
            "source_path": "100 Inbox/Origin.md",
            "reason": "Content fully captured in daily note.",
            "causes": [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}],
        }]
        md = render_instructions_md([], _md_metadata(
            skipped_daily=[{
                "id": "I05", "action": "update_log_entry",
                "daily_note_path": "Calendar/301 Daily/2026-09-17.md",
            }],
            delete_withdrawals=delete_withdrawals,
        ), CFG)
        assert "## Skipped — un-appliable actions" in md
        assert "## Source Deletions" in md
        assert md.count("\n## ") == 2
        assert "D1" not in md
        assert "delete_source" not in md
        assert "I05" not in md
        assert "filter_missing_daily_notes" not in md
        assert "100 Inbox/Origin.md" not in md
        assert "[[Origin]]" in md
        assert "its daily note does not exist" in md

    def test_f2_ac4_daily_skip_and_delete_withdrawal_are_structurally_grouped(self):
        """PRD F2-AC4: the withheld daily action and the delete it withdrew
        read as belonging together, not merely both present. `assert "I05"
        in md` twice would pass on the defect this test is written against —
        the daily-skip bullet and an UNRELATED skip bullet (skipped_rel,
        sharing no id) are included specifically so a renderer that puts the
        withdrawal in a floating, unrelated sub-block fails this test even
        though every string still appears somewhere in the document.
        """
        lines = render_instructions_md([], _md_metadata(
            skipped_daily=[{
                "id": "I05", "action": "update_log_entry",
                "daily_note_path": "Calendar/301 Daily/2026-09-17.md",
            }],
            skipped_rel=[{
                "id": "R99", "action": "add_relationship",
                "target_moc_path": "Atlas/200 Maps/Somewhere (MOC).md",
                "error": "child-missing",
            }],
            delete_withdrawals=[{
                "id": "D1", "action": "delete_source",
                "source_path": "100 Inbox/Origin.md",
                "reason": "Content fully captured in daily note.",
                "causes": [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}],
            }],
        ), CFG).splitlines()

        daily_idx = next(
            i for i, line in enumerate(lines) if line.startswith("- `update_log_entry`")
        )
        withdrawal_idx = next(
            i for i, line in enumerate(lines) if "a delete was withheld:" in line
        )
        rel_idx = next(
            i for i, line in enumerate(lines) if line.startswith("- `add_relationship`")
        )

        assert withdrawal_idx == daily_idx + 1, (
            "the withdrawal must sit immediately under the daily-skip bullet "
            "sharing its missing id (I05), not floated elsewhere:\n"
            + "\n".join(lines)
        )
        assert abs(withdrawal_idx - rel_idx) > 1, (
            "the withdrawal must not read as adjacent to an unrelated skip "
            "bullet that happens to share no id with it"
        )

    def test_multi_cause_same_guard_withdrawal_renders_under_both_daily_bullets(self):
        """Code-quality review Warning: a withdrawal whose `causes` name two
        missing ids from the SAME guard — reachable today via
        `_build_daily_update_actions`'s `ids_by_origin` accumulating one
        origin's daily-action ids across two different missing daily notes
        (`tomo/scripts/lib/render_actions.py`) — must nest under BOTH
        matching skip bullets, not just `causes[0]`'s. A user whose note
        survived because two daily notes were missing must see that fact at
        both bullets. Positional, mirroring
        `test_f2_ac4_daily_skip_and_delete_withdrawal_are_structurally_grouped`.
        """
        lines = render_instructions_md([], _md_metadata(
            skipped_daily=[
                {
                    "id": "I05", "action": "update_log_entry",
                    "daily_note_path": "Calendar/301 Daily/2026-09-17.md",
                },
                {
                    "id": "I06", "action": "update_tracker",
                    "daily_note_path": "Calendar/301 Daily/2026-09-18.md",
                },
            ],
            delete_withdrawals=[{
                "id": "D1", "action": "delete_source",
                "source_path": "100 Inbox/Origin.md",
                "reason": "Content fully captured in daily note.",
                "causes": [
                    {"missing_id": "I05", "guard": "filter_missing_daily_notes"},
                    {"missing_id": "I06", "guard": "filter_missing_daily_notes"},
                ],
            }],
        ), CFG).splitlines()

        first_daily_idx = next(
            i for i, line in enumerate(lines) if line.startswith("- `update_log_entry`")
        )
        second_daily_idx = next(
            i for i, line in enumerate(lines) if line.startswith("- `update_tracker`")
        )
        withdrawal_idxs = [
            i for i, line in enumerate(lines) if "a delete was withheld:" in line
        ]

        assert len(withdrawal_idxs) == 2, (
            "a withdrawal whose causes span two missing daily notes (same "
            "guard) must appear at BOTH skip bullets, not just the first "
            "cause's:\n" + "\n".join(lines)
        )
        assert first_daily_idx + 1 in withdrawal_idxs, (
            "withdrawal must sit immediately under the FIRST daily bullet "
            "sharing its missing id (I05):\n" + "\n".join(lines)
        )
        assert second_daily_idx + 1 in withdrawal_idxs, (
            "withdrawal must sit immediately under the SECOND daily bullet "
            "sharing its missing id (I06) — not shown only at the first:\n"
            + "\n".join(lines)
        )

    def test_single_cause_withdrawal_still_renders_exactly_once(self):
        """No-regression guard for the multi-cause fix above: a withdrawal
        with exactly one cause must still render exactly once, not
        duplicated by the same-missing-id dedup logic."""
        md = render_instructions_md([], _md_metadata(
            skipped_daily=[{
                "id": "I05", "action": "update_log_entry",
                "daily_note_path": "Calendar/301 Daily/2026-09-17.md",
            }],
            delete_withdrawals=[{
                "id": "D1", "action": "delete_source",
                "source_path": "100 Inbox/Origin.md",
                "reason": "Content fully captured in daily note.",
                "causes": [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}],
            }],
        ), CFG)
        assert md.count("a delete was withheld:") == 1

    def test_no_withdrawal_produces_no_withdrawal_subblock(self):
        """Regression guard: `delete_withdrawals` defaults to `[]`, so
        neither the inline nested bullet nor the catch-all block renders.
        True before T4.3 (the section simply had no such key to read) —
        kept explicit rather than assumed."""
        md = render_instructions_md([], _md_metadata(
            skipped_daily=[{
                "id": "I05", "action": "update_log_entry",
                "daily_note_path": "Calendar/301 Daily/2026-09-17.md",
            }],
        ), CFG)
        assert "withdrawn:" not in md
        assert "Delete withdrawn" not in md

    def test_withdrawn_only_run_still_renders_skipped_heading(self):
        """Every OTHER skip key is empty; delete_withdrawals alone must
        still open "## Skipped — un-appliable actions" (F6-AC1) — exercises
        the leftover/catch-all path (undeclared dependency, no guard to nest
        under)."""
        md = render_instructions_md([], _md_metadata(
            delete_withdrawals=[{
                "id": "D2", "action": "delete_source",
                "source_path": "100 Inbox/Other.md",
                "reason": "Origin consumed by 1 atomic.",
                "causes": [{"missing_id": None, "guard": None}],
            }],
        ), CFG)
        assert "## Skipped — un-appliable actions" in md
        assert "a delete was withheld:" in md
        assert "no reason was ever recorded for this delete" in md
        assert "D2" not in md
        # "## Source Deletions" is created solely to carry this withdrawal's
        # own notice too (Change 3b) — no delete_source action survived.
        assert "## Source Deletions" in md
        assert "[[Other]] was **not** deleted" in md


# ── 12-13. "## Source Deletions" carries a visible statement (Change 3b) ──


def _delete_action(source_path="100 Inbox/Kept.md"):
    return {
        "id": "D9", "action": "delete_source", "source_path": source_path,
        "reason": "Origin consumed by 1 atomic.",
    }


class TestSourceDeletionsWithdrawalNotice:
    """spec 035 T-delete-reaches-user, test-plan items 12-13: a ticked delete
    the run withheld must never be silent under "## Source Deletions" — its
    own section, not only the "## Skipped" cross-reference."""

    def test_heading_already_open_appends_the_notice(self):
        """One delete_source action survives (heading already renders) and a
        second delete was withdrawn — the notice appends after the surviving
        entry, in the SAME section, not a duplicate heading."""
        md = render_instructions_md(
            [_delete_action()],
            _md_metadata(delete_withdrawals=[{
                "id": "D1", "action": "delete_source",
                "source_path": "100 Inbox/Origin.md",
                "reason": "Content fully captured in daily note.",
                "causes": [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}],
            }]),
            CFG,
        )
        assert md.count("## Source Deletions") == 1
        assert "### D9 — Delete source note: Kept" in md
        assert "[[Origin]] was **not** deleted — its daily note does not exist" in md
        # The surviving entry's own block precedes the notice.
        assert md.index("### D9") < md.index("[[Origin]] was **not** deleted")

    def test_heading_created_solely_to_carry_the_notice(self):
        """No delete_source action survived this run at all — the heading
        does not exist yet in `by_section`, and must be created from nothing
        just to carry the withdrawn-delete statement."""
        md = render_instructions_md(
            [],
            _md_metadata(delete_withdrawals=[{
                "id": "D1", "action": "delete_source",
                "source_path": "100 Inbox/Origin.md",
                "reason": "Content fully captured in daily note.",
                "causes": [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}],
            }]),
            CFG,
        )
        assert "## Source Deletions" in md
        assert "[[Origin]] was **not** deleted — its daily note does not exist" in md
        assert "### D9" not in md

    def test_no_withdrawals_source_deletions_byte_identical(self):
        """No `delete_withdrawals` at all — "## Source Deletions" must render
        exactly as it did before Change 3b: the surviving action's own block,
        nothing appended."""
        md = render_instructions_md([_delete_action()], _md_metadata(), CFG)
        expected = (
            "## Source Deletions\n\n"
            "### D9 — Delete source note: Kept\n"
            "- [ ] Applied\n"
            "- **Source:** [[Kept]]\n"
            "- **Action:** Delete the note from the inbox — Origin consumed by 1 atomic."
        )
        assert expected in md
        assert "was **not** deleted" not in md
