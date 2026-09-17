#!/usr/bin/env python3
# version: 0.1.0
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
    attribute_withdrawal_causes,
    build_delete_withdrawal_reports,
    describe_withdrawal_cause,
)
from lib.render_md import render_instructions_md  # noqa: E402

_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render_t036_t43", SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_t036_t43"] = _ir
_ir_spec.loader.exec_module(_ir)

ALL_GUARDS = (
    "validate_destinations",
    "suppress_moves_for_unfiled_attachments",
    "filter_unresolvable_moc_links",
    "filter_missing_daily_notes",
    "filter_unappliable_relationships",
)

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
        # Not a NEW top-level section: exactly one "## " heading in the
        # whole document (no actions, no other metadata keys set here).
        assert md.count("\n## ") == 1
        assert "D1" in md and "delete_source" in md
        assert "100 Inbox/Origin.md" in md
        assert "I05" in md
        assert "filter_missing_daily_notes" in md

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
            i for i, line in enumerate(lines) if "withdrawn: `D1`" in line
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
        assert "withdrawn: `D2`" in md
        assert "no dependency was ever declared" in md
