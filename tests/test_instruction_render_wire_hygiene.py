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

test_snapshot_matches_upstream_hashi requires network access — it skips
automatically when the upstream GitHub URL is unreachable (offline runs).
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from pathlib import Path

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

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
# Committed verbatim copy of Hashi's instructions.schema.json. The parity test
# runs UNCONDITIONALLY against this snapshot so it never silently skips in CI /
# containers without a co-located Hashi checkout. A separate network drift check
# (test_snapshot_matches_upstream_hashi) pulls the live schema from GitHub and
# verifies the snapshot is current — skips offline automatically.
HASHI_SCHEMA_SNAPSHOT = SCHEMAS_DIR / "hashi-instructions.schema.json"

# Public GitHub raw URL for Hashi's live schema — no local checkout required.
# test_snapshot_matches_upstream_hashi fetches this; all other tests use HASHI_SCHEMA_SNAPSHOT.
_HASHI_UPSTREAM_URL = (
    "https://raw.githubusercontent.com/MMoMM-org/miyo-tomo-hashi/main/"
    "src/schema/instructions.schema.json"
)


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
            "schema_version": "1",
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
        # type MUST be the valid const "tomo-instructions" so the ValidationError
        # fires on the unstripped new_section (additionalProperties:false), NOT on
        # a top-level type mismatch — otherwise the test would pass even if the
        # new_section rejection regressed (review H9).
        doc = {
            "schema_version": "1", "type": "tomo-instructions",
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
            "schema_version": "1", "type": "tomo-instructions",
            "generated": "2026-06-20T12:00:00Z", "profile": "miyo",
            "actions": [], "tomo": block,
        }
        validate(instance=doc, schema=instructions_schema)  # must not raise

    def test_doc_without_tomo_block_still_validates(self, instructions_schema):
        """Backward-compat: tomo is not in required — omitting it stays valid."""
        doc = {
            "schema_version": "1", "type": "tomo-instructions",
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


# ── Cross-repo parity (Constitution L2) ─────────────────────────────────────


def _props(schema: dict, defname: str) -> set:
    return set(schema["$defs"][defname]["properties"].keys())


class TestHashiSchemaParity:
    """Parity guard against the COMMITTED Hashi snapshot — runs unconditionally so
    CI / containers without a co-located Hashi checkout still exercise it. The
    snapshot is a verbatim copy of Hashi's instructions.schema.json; a separate
    drift check (below) catches the snapshot falling behind the live Hashi schema."""

    @pytest.fixture(scope="class")
    def hashi_snapshot(self) -> dict:
        return json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))

    def test_link_to_moc_props_match_snapshot(self, instructions_schema, hashi_snapshot):
        assert _props(instructions_schema, "link_to_moc") == _props(hashi_snapshot, "link_to_moc")

    def test_move_note_props_match_snapshot(self, instructions_schema, hashi_snapshot):
        assert _props(instructions_schema, "move_note") == _props(hashi_snapshot, "move_note")

    def test_snapshot_carries_tomo_block(self, hashi_snapshot, instructions_schema):
        """Snapshot refreshed from Hashi v0.11.0 — the optional top-level tomo
        block must be present in both Hashi's snapshot and Tomo's own schema (#74)."""
        assert "tomo" in hashi_snapshot["properties"]
        assert "tomo" in instructions_schema["properties"]

    def test_snapshot_matches_upstream_hashi(self, hashi_snapshot):
        """Network drift guard: the committed snapshot must match the live Hashi
        schema published on GitHub for every action $def (not just link_to_moc/
        move_note — catches insert_under_marker-style whole-action drift too).

        Skips automatically when the upstream URL is unreachable so offline runs
        and CI without network still pass. When network is available this test RUNS
        and verifies no action def has drifted required fields or property names.

        A failure here means the snapshot is stale — refresh
        tomo/schemas/hashi-instructions.schema.json from upstream Hashi.
        """
        try:
            req = urllib.request.Request(
                _HASHI_UPSTREAM_URL,
                headers={"User-Agent": "miyo-tomo-test/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    pytest.skip(
                        f"upstream Hashi schema unreachable — HTTP {resp.status} — offline"
                    )
                live = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError):
            pytest.skip("upstream Hashi schema unreachable — offline")

        # Compare every action def's required fields and property names.
        def _action_defs(schema: dict) -> set[str]:
            return {
                name
                for name, defn in schema.get("$defs", {}).items()
                if "properties" in defn and "action" in defn["properties"]
            }

        snap_defs = _action_defs(hashi_snapshot)
        live_defs = _action_defs(live)
        only_in_snap = snap_defs - live_defs
        only_in_live = live_defs - snap_defs

        assert not only_in_snap and not only_in_live, (
            "Action set differs between snapshot and upstream Hashi.\n"
            f"  Only in snapshot: {sorted(only_in_snap)}\n"
            f"  Only in upstream: {sorted(only_in_live)}\n"
            "Fix: refresh tomo/schemas/hashi-instructions.schema.json from upstream Hashi."
        )

        mismatches: list[str] = []
        for defname in sorted(snap_defs & live_defs):
            snap_req = frozenset(hashi_snapshot["$defs"][defname].get("required", []))
            live_req = frozenset(live["$defs"][defname].get("required", []))
            snap_props = _props(hashi_snapshot, defname)
            live_props = _props(live, defname)
            if snap_req != live_req:
                mismatches.append(
                    f"  {defname}: required mismatch\n"
                    f"    snap only:  {sorted(snap_req - live_req)}\n"
                    f"    live only:  {sorted(live_req - snap_req)}"
                )
            if snap_props != live_props:
                mismatches.append(
                    f"  {defname}: property-name mismatch\n"
                    f"    snap only:  {sorted(snap_props - live_props)}\n"
                    f"    live only:  {sorted(live_props - snap_props)}"
                )

        assert not mismatches, (
            "Action $def structure drifted from upstream Hashi:\n"
            + "\n".join(mismatches)
            + "\nFix: refresh tomo/schemas/hashi-instructions.schema.json from upstream Hashi."
        )


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
        assert link["source_note_title"] == SAFE_STEM
        from lib.obsidian_filename import is_obsidian_safe
        assert is_obsidian_safe(link["source_note_title"])


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
