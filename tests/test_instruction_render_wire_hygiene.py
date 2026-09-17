# version: 0.5.0
"""test_instruction_render_wire_hygiene.py — apply-blocker fixes (#68/#69/#70/#64).

Covers the producer-side hygiene that makes a Tomo instruction set appliable by
Hashi without hand-patching:

  #68 — new_section is stripped from link_to_moc before the wire (Hashi's
        link_to_moc schema is additionalProperties:false and rejects it).
  #64 — fit_confidence is lifted to a top-level action field (for telemetry) and
        likewise stripped before the wire.
  #69 — forbidden filename chars (\\ / : * ? " < > |) in a suggested title are
        sanitised in the destination basename AND in every wikilink that targets
        the renamed note (alias preserves the original title for display).
  #70 — two notes assigned the same (target_moc, new_section) merge into ONE
        heading with multiple bullets instead of duplicate `## <section>` blocks.

Plus a cross-repo parity guard: Tomo's link_to_moc/move_note allowed-properties
must match Hashi's schema (MiYo Constitution L2 — coordinated public interface).
That guard, and the rest of the cross-repo wire-schema parity machinery
(TestHashiSchemaParity, TestUpstreamFetchSkip, TestSnapshotParityReport,
TestVendoredCopies, and their shared fetch/report helpers), moved to
`tests/test_wire_snapshot_parity.py` (code-quality review, 2026-09-11): it
grew into a self-contained concern needing nothing from the fixtures below,
the same "does not belong inside a module written for something else"
reasoning that put `snapshot_parity_delta`/`render_snapshot_parity_report`
into `tomo/scripts/lib/wire_snapshot_parity.py` one step earlier. See that
file's module docstring for the full ADR-7 / T2.4 / T4.2 history.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render", _SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render"] = _ir
_ir_spec.loader.exec_module(_ir)

from lib.render_actions import assert_no_dangling_dependencies  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"


@pytest.fixture(scope="module")
def instructions_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "instructions.schema.json").read_text(encoding="utf-8"))


def _link_action(**over) -> dict:
    base = {
        "id": "I01",
        "action": "link_to_moc",
        "target_moc": "Japan (MOC)",
        "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
        "anchor": {"type": "callout", "value": "[!blocks] Key Concepts"},
        "placement": "after",
        "line_to_add": "- [[Note]]",
        "source_note_title": "Note",
        "new_section": None,
        "fit_confidence": None,
        "applied": False,
    }
    base.update(over)
    return base


# ── #68 — new_section / fit_confidence no-leak ──────────────────────────────


class TestInternalFieldStrip:
    def test_strip_removes_new_section_and_fit_confidence(self):
        actions = [_link_action(new_section="Hokkaido", fit_confidence=0.82)]
        removed = _ir._strip_internal_link_fields(actions)
        assert removed == 2
        assert "new_section" not in actions[0]
        assert "fit_confidence" not in actions[0]

    def test_strip_is_idempotent(self):
        actions = [_link_action(new_section="X", fit_confidence=0.5)]
        _ir._strip_internal_link_fields(actions)
        assert _ir._strip_internal_link_fields(actions) == 0

    def test_strip_ignores_non_link_actions(self):
        actions = [{"action": "move_note", "new_section": "leftover"}]
        assert _ir._strip_internal_link_fields(actions) == 0
        assert actions[0]["new_section"] == "leftover"

    def test_serialize_then_strip_bakes_heading_and_drops_field(self):
        actions = [_link_action(new_section="Hokkaido", line_to_add="- [[Furano]]")]
        _ir._serialize_new_sections(actions)
        _ir._strip_internal_link_fields(actions)
        assert actions[0]["line_to_add"] == "## Hokkaido\n\n- [[Furano]]\n"
        assert "new_section" not in actions[0]

    def test_stripped_link_validates_against_tomo_schema(self, instructions_schema):
        action = _link_action(new_section="Hokkaido", fit_confidence=0.9,
                              line_to_add="- [[Furano]]")
        _ir._serialize_new_sections([action])
        _ir._strip_internal_link_fields([action])
        doc = {
            "schema_version": "3",
            "type": "tomo-instructions",
            "generated": "2026-06-17T00:00:00Z",
            "profile": "miyo",
            "actions": [action],
        }
        validate(instance=doc, schema=instructions_schema)  # must not raise

    def test_unstripped_new_section_would_fail_tomo_schema(self, instructions_schema):
        """Regression guard: new_section on the wire is now schema-invalid
        (mirrors Hashi's additionalProperties:false rejection)."""
        from jsonschema import ValidationError
        action = _link_action(new_section="Hokkaido")
        del action["fit_confidence"]
        # type MUST be the valid const "tomo-instructions" AND the correct
        # schema_version so the ValidationError fires on the unstripped
        # new_section (additionalProperties:false), NOT on a top-level mismatch —
        # otherwise the test would pass even if the new_section rejection regressed
        # (review H9).
        doc = {
            "schema_version": "3", "type": "tomo-instructions",
            "generated": "2026-06-17T00:00:00Z", "profile": "miyo",
            "actions": [action],
        }
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=instructions_schema)


# ── #74 — optional top-level tomo block in instructions.json ────────────────


class TestInstructionsJsonTomoBlock:
    """#74: the machine doc carries an optional top-level tomo block (state +
    sources) so it is self-describing, matching the .md frontmatter. Hashi
    ≥ v0.11.0 accepts and ignores it."""

    def test_top_level_tomo_block_validates(self, instructions_schema):
        block = _ir._build_tomo_block_for_instructions({
            "upstream_type": "suggestions",
            "upstream_path": "100 Inbox/2026-06-20_1432_suggestions.md",
            "upstream_body_path": None,
            "run_id": "pass2-run-001",
        })
        assert block is not None
        assert block["sources"][0]["path"].endswith("_suggestions.md")
        doc = {
            "schema_version": "3", "type": "tomo-instructions",
            "generated": "2026-06-20T12:00:00Z", "profile": "miyo",
            "actions": [], "tomo": block,
        }
        validate(instance=doc, schema=instructions_schema)  # must not raise

    def test_doc_without_tomo_block_still_validates(self, instructions_schema):
        """Backward-compat: tomo is not in required — omitting it stays valid."""
        doc = {
            "schema_version": "3", "type": "tomo-instructions",
            "generated": "2026-06-20T12:00:00Z", "profile": "miyo", "actions": [],
        }
        validate(instance=doc, schema=instructions_schema)  # must not raise

    def test_tomo_block_omitted_when_no_run_id(self):
        """No run_id → builder returns None → key never emitted (never null)."""
        block = _ir._build_tomo_block_for_instructions({
            "upstream_type": "suggestions", "upstream_path": "x.md",
            "upstream_body_path": None, "run_id": None,
        })
        assert block is None

    def test_strip_before_serialize_drops_heading(self):
        """Order regression (review M15): _serialize_new_sections MUST run before
        _strip_internal_link_fields. If strip runs first it consumes new_section
        and serialize has nothing to bake → the `## <section>` heading is silently
        omitted from line_to_add."""
        action = _link_action(new_section="Hokkaido", line_to_add="- [[Furano]]")
        # Wrong order: strip first, then serialize.
        _ir._strip_internal_link_fields([action])
        _ir._serialize_new_sections([action])
        assert not action["line_to_add"].startswith("## "), (
            "strip-before-serialize must NOT produce a heading (proves the "
            "ordering dependency)"
        )


# ── FOOTER_CALLOUTS cross-file sync (review M8) ─────────────────────────────


def test_footer_callouts_match_across_modules():
    """instruction-render.py and moc-tree-builder.py each hardcode FOOTER_CALLOUTS
    (the lib deliberately never hardcodes it — footer_set is caller-supplied per
    spec 022/#35/F-55). The two copies carry a "mirrors exactly" comment with no
    enforcement; this test is the enforcement (review M8)."""
    _mtb_spec = importlib.util.spec_from_file_location(
        "moc_tree_builder", _SCRIPTS_DIR / "moc-tree-builder.py"
    )
    _mtb = importlib.util.module_from_spec(_mtb_spec)
    assert _mtb_spec.loader is not None
    _mtb_spec.loader.exec_module(_mtb)
    assert set(_ir.FOOTER_CALLOUTS) == set(_mtb.FOOTER_CALLOUTS)


# ── #69 — filename sanitisation + resolvable references ─────────────────────

COLON_TITLE = "Oxygen Not Included — Knowledge Progression: From Knowing Things"
SAFE_STEM = "Oxygen Not Included — Knowledge Progression- From Knowing Things"


class TestFilenameSanitisation:
    def test_dest_join_sanitizes_colon(self):
        dest = _ir._dest_join("Atlas/202 Notes", COLON_TITLE)
        assert dest == f"Atlas/202 Notes/{SAFE_STEM}.md"
        assert ":" not in dest

    def test_wikilink_aliases_forbidden_char_title(self):
        link = _ir._wikilink(COLON_TITLE)
        assert link == f"[[{SAFE_STEM}|{COLON_TITLE}]]"

    def test_wikilink_safe_title_no_alias(self):
        assert _ir._wikilink("Plain Title") == "[[Plain Title]]"

    def test_move_note_destination_is_obsidian_safe(self):
        from lib.obsidian_filename import is_obsidian_safe
        manifest = [{
            "action": "create_atomic_note", "title": COLON_TITLE,
            "destination": "Atlas/202 Notes/", "source_path": "src.md",
            "rendered_file": "rendered.md", "parent_mocs": [],
        }]
        actions = _ir._build_move_note_actions(manifest, "100 Inbox/", [0])
        basename = actions[0]["destination"].rsplit("/", 1)[-1]
        assert is_obsidian_safe(basename)

    def test_link_to_moc_refs_resolve_to_safe_stem(self):
        confirmed = [{
            "id": "S01", "action": "create_atomic_note", "title": COLON_TITLE,
            "parent_mocs": ["Japan (MOC)"],
            "candidate_mocs": [],
        }]
        actions = _ir._build_link_to_moc_actions(confirmed, [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        assert link["line_to_add"] == f"- [[{SAFE_STEM}|{COLON_TITLE}]]"
        # Spec 034 T6.4b inverted the field these two assertions were written
        # against. The safe stem is still carried and still safe — it just has
        # its own field now, because source_note_title is DISPLAY text under
        # ADR-2 and the coverage audit joins on the raw title. Putting the
        # filename there made instructions-diff hard-fail every correct run
        # whose title held a forbidden character; found live, T6.4 run.
        assert link["source_note_stem"] == SAFE_STEM
        assert link["source_note_title"] == COLON_TITLE
        from lib.obsidian_filename import is_obsidian_safe
        assert is_obsidian_safe(link["source_note_stem"])


# ── #70 — same-section merge ────────────────────────────────────────────────


class TestNewSectionMerge:
    def test_two_notes_same_section_merge_into_one(self):
        actions = [
            _link_action(id="I01", new_section="Hokkaido", line_to_add="- [[Furano]]"),
            _link_action(id="I02", new_section="Hokkaido", line_to_add="- [[Hakodate]]"),
        ]
        removed = _ir._merge_new_section_links(actions)
        assert removed == 1
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert len(links) == 1
        assert links[0]["line_to_add"] == "- [[Furano]]\n- [[Hakodate]]"

    def test_distinct_sections_not_merged(self):
        actions = [
            _link_action(id="I01", new_section="Hokkaido", line_to_add="- [[Furano]]"),
            _link_action(id="I02", new_section="Kansai", line_to_add="- [[Osaka]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 0
        assert len([a for a in actions if a["action"] == "link_to_moc"]) == 2

    def test_same_moc_different_reference_form_merges(self):
        """Review M9: two actions targeting the SAME MOC by different reference
        forms (bare stem vs full path) and the same new_section must merge — the
        merge key normalises target_moc through _moc_stem()."""
        actions = [
            _link_action(id="I01", target_moc="Japan (MOC)", new_section="Hokkaido",
                         line_to_add="- [[Furano]]"),
            _link_action(id="I02", target_moc="Atlas/200 Maps/Japan (MOC).md",
                         new_section="Hokkaido", line_to_add="- [[Hakodate]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 1
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert len(links) == 1
        assert links[0]["line_to_add"] == "- [[Furano]]\n- [[Hakodate]]"

    def test_same_section_different_moc_not_merged(self):
        actions = [
            _link_action(id="I01", target_moc="Japan (MOC)", new_section="Maps",
                         line_to_add="- [[A]]"),
            _link_action(id="I02", target_moc="Europe (MOC)", new_section="Maps",
                         line_to_add="- [[B]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 0

    def test_links_without_new_section_untouched(self):
        actions = [
            _link_action(id="I01", line_to_add="- [[A]]"),
            _link_action(id="I02", line_to_add="- [[B]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 0

    def test_merged_then_serialized_is_one_section(self):
        actions = [
            _link_action(id="I01", new_section="Hokkaido", line_to_add="- [[Furano]]"),
            _link_action(id="I02", new_section="Hokkaido", line_to_add="- [[Hakodate]]"),
        ]
        _ir._merge_new_section_links(actions)
        _ir._serialize_new_sections(actions)
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert links[0]["line_to_add"] == "## Hokkaido\n\n- [[Furano]]\n- [[Hakodate]]\n"


# ── #64 — individual fit_confidence telemetry ───────────────────────────────


class TestFitConfidenceTelemetry:
    def _telemetry(self, actions) -> str:
        buf = io.StringIO()
        with redirect_stderr(buf):
            _ir._emit_resolution_telemetry(actions)
        return buf.getvalue()

    def test_individual_values_appended(self):
        actions = [
            _link_action(id="I01", anchor={"type": "heading", "value": "Concepts"},
                         fit_confidence=0.85),
            _link_action(id="I02", anchor={"type": "heading", "value": "Methods"},
                         fit_confidence=0.72),
        ]
        line = self._telemetry(actions)
        assert "fit_confidence=[0.85, 0.72]" in line

    def test_no_values_no_field(self):
        actions = [_link_action(anchor={"type": "callout", "value": "[!blocks] X"})]
        assert "fit_confidence=[" not in self._telemetry(actions)

    def test_subthreshold_confidence_still_recorded_gate_is_prompt_only(self):
        """The 0.6 fit_confidence gate (tier-1 heading vs tier-2 new-section) is
        enforced UPSTREAM by the inbox-analyst LLM prompt — there is NO Python
        code that branches on 0.6. This test pins that reality (review H10): a
        heading anchor with sub-0.6 confidence is still recorded in the telemetry
        and counted as tier1_confident (the resolver does not re-gate it). If a
        future change adds code-level gating, this test should be updated
        deliberately alongside it."""
        actions = [
            _link_action(id="I01", anchor={"type": "heading", "value": "Concepts"},
                         fit_confidence=0.59),
        ]
        line = self._telemetry(actions)
        assert "fit_confidence=[0.59]" in line
        assert "tier1_confident=1" in line

    def test_emit_lifts_fit_confidence_to_top_level(self):
        confirmed = [{
            "id": "S01", "action": "create_atomic_note", "title": "Note",
            "parent_mocs": ["Japan (MOC)"],
            "candidate_mocs": [{
                "path": "Atlas/200 Maps/Japan (MOC).md",
                "anchor": {"type": "heading", "value": "Concepts", "fit_confidence": 0.9},
            }],
        }]
        actions = _ir._build_link_to_moc_actions(confirmed, [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        assert link["fit_confidence"] == 0.9
        # anchor no-leak: the wire anchor stays {type, value}
        assert set(link["anchor"].keys()) == {"type", "value"}


# ── T4.2 — the dangling-id audit (spec 036 Phase 4, PRD F5-AC4) ─────────────
#
# Producer-side tripwire matching `_validate_action_paths`' abort shape: every
# id a `delete_source` names in `depends_on` must exist in the same action
# set. Scoped to `delete_source` only (settled ruling 1). Both failure modes
# this audits are UNREACHABLE through the real pipeline — `withdraw_unjustified_
# deletes` already withdraws a delete whose justification did not survive —
# so a violation here means an unknown-shaped bug (ADR-6), and the test
# construction below (a patched pipeline that lets a dangling delete through,
# PLUS a control run proving the patch target is live) is the whole task.


def _delete_action(**over) -> dict:
    base = {
        "id": "D01",
        "action": "delete_source",
        "source_path": "100 Inbox/note.md",
        "reason": "moved",
        "depends_on": ["M01"],
        "applied": False,
    }
    base.update(over)
    return base


class TestAssertNoDanglingDependencies:
    """Unit coverage — calls the audit directly on hand-built action sets."""

    def test_every_named_id_present_is_vacuous(self):
        actions = [
            _delete_action(id="D01", depends_on=["M01"]),
            {"id": "M01", "action": "move_note", "destination": "x"},
        ]
        assert assert_no_dangling_dependencies(actions) == []

    def test_one_dangling_id_produces_one_violation_naming_both_ids(self):
        actions = [_delete_action(id="D01", depends_on=["GHOST01"])]
        violations = assert_no_dangling_dependencies(actions)
        assert len(violations) == 1
        assert "D01" in violations[0]
        assert "GHOST01" in violations[0]

    def test_missing_depends_on_key_is_a_violation_distinct_from_dangling_id(self):
        """No `depends_on` key at all is a fault of equal severity to a
        dangling id, but a different fault — the wording must not collide."""
        action = _delete_action(id="D02")
        del action["depends_on"]
        violations = assert_no_dangling_dependencies([action])
        assert len(violations) == 1
        assert "D02" in violations[0]
        assert "missing" in violations[0]
        assert "unknown id" not in violations[0]

    def test_empty_depends_on_list_is_not_a_violation(self):
        """`depends_on: []` is a positive assertion ("nothing conditions this
        delete") — never conflated with the missing-key case."""
        actions = [_delete_action(id="D03", depends_on=[])]
        assert assert_no_dangling_dependencies(actions) == []

    def test_multiple_offending_deletes_all_reported(self):
        actions = [
            _delete_action(id="D04", depends_on=["GHOST04"]),
            _delete_action(id="D05", depends_on=["GHOST05"]),
        ]
        violations = assert_no_dangling_dependencies(actions)
        assert len(violations) == 2
        joined = "\n".join(violations)
        assert "D04" in joined and "GHOST04" in joined
        assert "D05" in joined and "GHOST05" in joined

    def test_non_delete_action_with_dangling_depends_on_is_out_of_scope(self):
        """The audit is delete_source-scoped (settled ruling 1) — an
        add_relationship's own (irrelevant) depends_on is never checked."""
        actions = [{
            "id": "R01", "action": "add_relationship", "depends_on": ["GHOST06"],
        }]
        assert assert_no_dangling_dependencies(actions) == []

    def test_delete_naming_its_own_id_is_not_a_violation(self):
        """Existence only, not well-formedness — a self-referencing depends_on
        is a semantic oddity this audit deliberately does not flag (settled
        ruling 2: no cycle/well-formedness check)."""
        actions = [_delete_action(id="D06", depends_on=["D06"])]
        assert assert_no_dangling_dependencies(actions) == []

    def test_duplicate_missing_id_in_one_depends_on_yields_one_violation(self):
        actions = [_delete_action(id="D07", depends_on=["GHOST07", "GHOST07"])]
        violations = assert_no_dangling_dependencies(actions)
        assert len(violations) == 1
        assert "GHOST07" in violations[0]


def _dangling_audit_suggestions() -> dict:
    # daily_updates non-empty only to clear main()'s "nothing to do" early
    # return (instruction-render.py ~line 322) — content is never read,
    # build_actions is stubbed below and ignores it.
    return {"confirmed_items": [], "daily_updates": [{"id": "dummy"}], "skipped": []}


def _stub_dangling_audit_pipeline(monkeypatch, base_dir: Path, fixture_actions: list[dict]) -> Path:
    """Stub every dependency so main() exercises only the T4.2 audit + write path.

    Mirrors the `_stub_pipeline` pattern in
    test_instruction_render_rendered_note_stamp.py: confirmed_items stays
    empty so no KadoClient connection is attempted, and build_actions is
    replaced outright so *fixture_actions* reaches withdraw_unjustified_deletes
    (real or patched, per the calling test) unchanged — every filter pass
    between build_actions and withdraw_unjustified_deletes is kind-scoped
    (move_note/create_moc destinations, link_to_moc, daily-note, add_relationship)
    and passes delete_source/move_note actions through untouched.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    suggestions_file = base_dir / "suggestions.json"
    suggestions_file.write_text(json.dumps(_dangling_audit_suggestions()), encoding="utf-8")
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
    monkeypatch.setattr(_ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(_ir, "build_actions", lambda *_a, **_kw: (fixture_actions, []))
    monkeypatch.setattr(_ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(_ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(_ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(_ir, "render_instructions_md", lambda *_a, **_kw: "")
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


class TestAssertNoDanglingDependenciesIntegration:
    """At the `_ir` module seam (`main()`).

    `_ir.withdraw_unjustified_deletes` is the live binding — instruction-
    render.py does `from lib.render_actions import (..., withdraw_unjustified_
    deletes)`, so the caller re-resolves the name in ITS OWN module namespace,
    never `lib.render_actions`'s (settled ruling 4). Patching the latter would
    silently no-op.
    """

    def test_dangling_id_aborts_exit_2_no_file_with_unpatched_control(self, monkeypatch, tmp_path):
        actions = [_delete_action(id="D_INT01", depends_on=["GHOST_INT01"])]

        # Control FIRST, completely unpatched: withdraw_unjustified_deletes
        # withdraws the dangling delete_source before the audit ever sees it
        # (this failure mode is unreachable through the real pipeline —
        # settled ruling 3), so this run must succeed. If it didn't, the
        # patched assertion below would prove nothing about the patch target
        # being live rather than about something else in the stub.
        control_out = _stub_dangling_audit_pipeline(monkeypatch, tmp_path / "control", actions)
        assert _ir.main() == 0
        assert (control_out / "instructions.json").exists()

        # Patched: withdraw_unjustified_deletes replaced with a pass-through,
        # so the dangling delete_source survives to reach the new audit.
        patched_out = _stub_dangling_audit_pipeline(monkeypatch, tmp_path / "patched", actions)
        monkeypatch.setattr(_ir, "withdraw_unjustified_deletes", lambda a: (a, []))
        assert _ir.main() == 2
        assert not (patched_out / "instructions.json").exists()

    def test_missing_depends_on_key_aborts_exit_2_no_file_with_unpatched_control(self, monkeypatch, tmp_path):
        action = _delete_action(id="D_INT02")
        del action["depends_on"]

        control_out = _stub_dangling_audit_pipeline(monkeypatch, tmp_path / "control", [action])
        assert _ir.main() == 0
        assert (control_out / "instructions.json").exists()

        patched_out = _stub_dangling_audit_pipeline(monkeypatch, tmp_path / "patched", [action])
        monkeypatch.setattr(_ir, "withdraw_unjustified_deletes", lambda a: (a, []))
        assert _ir.main() == 2
        assert not (patched_out / "instructions.json").exists()

    def test_healthy_run_through_real_unpatched_pipeline_exits_0_and_writes_file(self, monkeypatch, tmp_path):
        actions = [
            _delete_action(id="D_INT03", depends_on=["M_INT03"]),
            {
                "id": "M_INT03", "action": "move_note", "destination": "200 Notes/x.md",
                "source_path": "100 Inbox/x.md", "applied": False,
            },
        ]
        out_dir = _stub_dangling_audit_pipeline(monkeypatch, tmp_path, actions)

        assert _ir.main() == 0
        assert (out_dir / "instructions.json").exists()
