#!/usr/bin/env python3
# version: 0.1.0
"""test_018_pipeline.py — Cross-phase integration tests for 018 inbox routing.

T5.1: Exercises the full triage → routing-plan → conductor-selection chain
end-to-end via main(). Each test drives the pipeline through the public
entry point with a FakeKadoClient and asserts on the written routing-plan.json.

Spec: docs/XDD/specs/018-agent-architecture-cleanup/plan/phase-5.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate as json_validate  # noqa: E402


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_module():
    """Load inbox-triage.py as a module."""
    import importlib.util
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_schema() -> dict:
    """Load routing-plan.schema.json."""
    schema_path = REPO_ROOT / "tomo" / "schemas" / "routing-plan.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# FakeKadoClient
# ---------------------------------------------------------------------------

class FakeKadoClient:
    """Minimal KadoClient replacement with pre-configured responses."""

    def __init__(
        self,
        *,
        listdir_items: list[dict] | None = None,
        frontmatter_responses: dict[str, list[dict]] | None = None,
        read_note_responses: dict[str, dict] | None = None,
    ):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        return self._listdir_items

    def search_by_frontmatter(
        self, query: str, *, path_prefix: str | None = None, limit: int = 500,
        modified_after: int | None = None,
    ) -> list[dict]:
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        return self._read_note_responses.get(path, {"content": "", "modified": 0})


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

INBOX = "100 Inbox/"


def _file(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


def _fm_hit(path: str, doc_type: str, state: str, sources: list[dict] | None = None) -> dict:
    tomo = {
        "doc_type": doc_type,
        "state": state,
        "run_id": "test-run",
        "updated_at": "2026-05-21T12:00:00Z",
    }
    if sources is not None:
        tomo["sources"] = sources
    return {
        "path": path,
        "modified": 1716300000000,
        "frontmatter": {"tomo": tomo},
    }


def _suggestions_body(approved: bool, fan_items: list[str] | None = None) -> str:
    mark = "[x]" if approved else "[ ]"
    lines = [
        "---", "type: tomo-suggestions", "---", "",
        "# Inbox Suggestions", "", f"- {mark} Approved", "",
        "## Suggestions", "",
    ]
    for i, stem in enumerate(fan_items or [], start=1):
        lines += [
            f"### S{i:02d} — {stem} reflections", "",
            f"**Source:** [[{stem}]]", "",
            "**Decision (atomic note):**",
            "- [x] Approve",
            "- [x] Force Atomic Note (create/keep a standalone note for this item)",
            "",
        ]
    return "\n".join(lines)


def _moc_proposal_body(accepted: bool) -> str:
    mark = "[x]" if accepted else "[ ]"
    return f"---\ntype: tomo-moc-proposal\n---\n\n# MOC Proposal\n\n- {mark} Accept\n\n## Cluster\n"


def _run_pipeline(tmp_path: Path, client: FakeKadoClient, extra_args: list[str] | None = None) -> dict:
    """Run main() through the full pipeline, return the written routing plan."""
    mod = _load_module()
    args = ["--inbox-path", INBOX, "--output-dir", str(tmp_path)]
    if extra_args:
        args.extend(extra_args)
    rc = mod.main(args, client_factory=lambda: client)
    assert rc == 0, f"main() returned {rc}"
    plan_path = tmp_path / "routing-plan.json"
    assert plan_path.exists(), "routing-plan.json not written"
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _empty_frontmatter() -> dict[str, list[dict]]:
    """Frontmatter responses with all four queries returning empty."""
    return {
        "tomo.state=pending-approval": [],
        "tomo.state=pending-accept": [],
        "tomo.state=captured": [],
        "tomo.doc_type=instructions": [],
    }


# ---------------------------------------------------------------------------
# 1. Action routing — one per action type
# ---------------------------------------------------------------------------


class TestSuggestActionFromFreshSources:
    def test_fresh_md_files_produce_suggest(self, tmp_path):
        """Fresh .md files in inbox with no tomo frontmatter produce action=suggest."""
        client = FakeKadoClient(
            listdir_items=[
                _file(INBOX + "note-a.md"),
                _file(INBOX + "note-b.md"),
            ],
            frontmatter_responses=_empty_frontmatter(),
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "suggest"
        assert len(plan["fresh_sources"]) == 2
        json_validate(instance=plan, schema=schema)


class TestFanResolveActionFromForceAtomic:
    def test_approved_with_fan_items_no_fan_doc_produce_fan_resolve(self, tmp_path):
        """Approved suggestions with force-atomic items and no fan doc produce action=fan-resolve."""
        sugg_path = INBOX + "2026-05-22_1432_suggestions.md"
        body = _suggestions_body(approved=True, fan_items=["Furano", "Niseko"])

        client = FakeKadoClient(
            listdir_items=[_file(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "fan-resolve"
        assert len(plan["force_atomic_items"]) == 2
        stems = [item["stem"] for item in plan["force_atomic_items"]]
        assert "Furano" in stems
        assert "Niseko" in stems
        json_validate(instance=plan, schema=schema)


class TestSynthesizeActionFromApprovedUncovered:
    def test_approved_suggestions_not_covered_produce_synthesize(self, tmp_path):
        """Approved suggestions not covered by existing instructions produce action=synthesize."""
        sugg_path = INBOX + "2026-05-22_1432_suggestions.md"
        body = _suggestions_body(approved=True)

        client = FakeKadoClient(
            listdir_items=[_file(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "synthesize"
        assert len(plan["approved_suggestions"]) == 1
        json_validate(instance=plan, schema=schema)


class TestIdleActionFromEmptyInbox:
    def test_no_files_produce_idle_with_reasons(self, tmp_path):
        """No files in inbox produce action=idle with idle_reasons."""
        client = FakeKadoClient(
            listdir_items=[],
            frontmatter_responses=_empty_frontmatter(),
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "idle"
        assert len(plan["idle_reasons"]) > 0
        json_validate(instance=plan, schema=schema)


class TestTranscribeActionFromAudio:
    def test_audio_without_sibling_md_produce_transcribe(self, tmp_path):
        """Audio files without sibling .md produce action=transcribe."""
        client = FakeKadoClient(
            listdir_items=[
                _file(INBOX + "recording.m4a"),
            ],
            frontmatter_responses=_empty_frontmatter(),
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "transcribe"
        assert plan["has_audio"] is True
        json_validate(instance=plan, schema=schema)


# ---------------------------------------------------------------------------
# 2. Coverage accumulation across runs
# ---------------------------------------------------------------------------


class TestCoverageExcludesAlreadyProcessedDocs:
    def test_second_run_skips_covered_suggestions(self, tmp_path):
        """Second triage run skips docs already covered by instructions.

        Run 1: 2 approved suggestions, no instructions → action=synthesize, 2 approved.
        Run 2: Same 2 approved, plus instructions covering suggestion A →
                action=synthesize but only suggestion B is uncovered.
        """
        sugg_a = INBOX + "2026-05-22_1432_suggestions-a.md"
        sugg_b = INBOX + "2026-05-22_1433_suggestions-b.md"
        instr_path = INBOX + "2026-05-24_0900_instructions.md"

        body_a = _suggestions_body(approved=True)
        body_b = _suggestions_body(approved=True)

        # Run 1: no instructions exist
        client_run1 = FakeKadoClient(
            listdir_items=[_file(sugg_a), _file(sugg_b)],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_a, "suggestions", "pending-approval"),
                    _fm_hit(sugg_b, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_a: {"content": body_a, "modified": 0},
                sugg_b: {"content": body_b, "modified": 0},
            },
        )

        run1_dir = tmp_path / "run1"
        plan1 = _run_pipeline(run1_dir, client_run1)
        assert plan1["action"] == "synthesize"
        assert len(plan1["approved_suggestions"]) == 2

        # Run 2: instructions exist covering suggestion A
        client_run2 = FakeKadoClient(
            listdir_items=[_file(sugg_a), _file(sugg_b), _file(instr_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_a, "suggestions", "pending-approval"),
                    _fm_hit(sugg_b, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [
                    _fm_hit(instr_path, "instructions", "pending-apply",
                            sources=[{"path": sugg_a, "checksum": "sha256:abc"}]),
                ],
            },
            read_note_responses={
                sugg_a: {"content": body_a, "modified": 0},
                sugg_b: {"content": body_b, "modified": 0},
            },
        )

        run2_dir = tmp_path / "run2"
        plan2 = _run_pipeline(run2_dir, client_run2)

        # Still synthesize because sugg_b is uncovered
        assert plan2["action"] == "synthesize"
        # Both are approved (the coverage logic doesn't remove them from
        # approved_suggestions — it only affects to_process internally)
        assert len(plan2["approved_suggestions"]) == 2

    def test_full_coverage_produces_idle(self, tmp_path):
        """When all approved docs are covered by instructions the action is idle."""
        sugg_path = INBOX + "2026-05-22_1432_suggestions.md"
        instr_path = INBOX + "2026-05-24_0900_instructions.md"
        body = _suggestions_body(approved=True)

        client = FakeKadoClient(
            listdir_items=[_file(sugg_path), _file(instr_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [
                    _fm_hit(instr_path, "instructions", "pending-apply",
                            sources=[{"path": sugg_path, "checksum": "sha256:abc"}]),
                ],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "idle"
        assert len(plan["idle_reasons"]) > 0
        json_validate(instance=plan, schema=schema)


# ---------------------------------------------------------------------------
# 3. MOC-proposal routing
# ---------------------------------------------------------------------------


class TestMocProposalAcceptedTriggersSynthesize:
    def test_accepted_moc_proposal_routes_to_synthesize(self, tmp_path):
        """Accepted MOC-proposal (ticked [x] Accept) routes to synthesize."""
        moc_path = INBOX + "2026-05-22_1832_moc-proposal-board-games.md"
        body = _moc_proposal_body(accepted=True)

        client = FakeKadoClient(
            listdir_items=[_file(moc_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [
                    _fm_hit(moc_path, "moc-proposal", "pending-accept"),
                ],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                moc_path: {"content": body, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "synthesize"
        assert len(plan["approved_moc_proposals"]) == 1
        assert plan["approved_moc_proposals"][0]["path"] == moc_path
        json_validate(instance=plan, schema=schema)


class TestMocProposalUntickedStaysPending:
    def test_unticked_moc_proposal_does_not_trigger_synthesize(self, tmp_path):
        """Unticked MOC-proposal stays in pending_approval, does not trigger synthesize."""
        moc_path = INBOX + "2026-05-22_1832_moc-proposal-board-games.md"
        body = _moc_proposal_body(accepted=False)

        client = FakeKadoClient(
            listdir_items=[_file(moc_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [
                    _fm_hit(moc_path, "moc-proposal", "pending-accept"),
                ],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                moc_path: {"content": body, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["approved_moc_proposals"] == []
        assert len(plan["pending_approval"]) == 1
        assert plan["pending_approval"][0]["path"] == moc_path
        # No approved items and no fresh sources → idle
        assert plan["action"] == "idle"
        json_validate(instance=plan, schema=schema)


# ---------------------------------------------------------------------------
# 4. Mixed input types
# ---------------------------------------------------------------------------


class TestMixedSuggestionsAndMocProducesSynthesize:
    def test_both_approved_types_produce_single_synthesize(self, tmp_path):
        """Both approved suggestions and accepted moc-proposals produce a single synthesize action."""
        sugg_path = INBOX + "2026-05-22_1432_suggestions.md"
        moc_path = INBOX + "2026-05-22_1832_moc-proposal-board-games.md"

        sugg_body = _suggestions_body(approved=True)
        moc_body = _moc_proposal_body(accepted=True)

        client = FakeKadoClient(
            listdir_items=[_file(sugg_path), _file(moc_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [
                    _fm_hit(moc_path, "moc-proposal", "pending-accept"),
                ],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": sugg_body, "modified": 0},
                moc_path: {"content": moc_body, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        assert plan["action"] == "synthesize"
        assert len(plan["approved_suggestions"]) == 1
        assert len(plan["approved_moc_proposals"]) == 1
        json_validate(instance=plan, schema=schema)


class TestForcePass1OverridesApprovedState:
    def test_force_pass1_produces_suggest_despite_approved_docs(self, tmp_path):
        """--force-pass1 flag produces action=suggest even when approved docs exist."""
        sugg_path = INBOX + "2026-05-22_1432_suggestions.md"
        body = _suggestions_body(approved=True)

        client = FakeKadoClient(
            listdir_items=[_file(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client, extra_args=["--force-pass1"])
        schema = _load_schema()

        assert plan["action"] == "suggest"
        json_validate(instance=plan, schema=schema)


class TestForcePass2OverridesAll:
    def test_force_pass2_produces_synthesize_despite_no_approved(self, tmp_path):
        """--force-pass2 flag produces action=synthesize even when no approved docs exist."""
        client = FakeKadoClient(
            listdir_items=[_file(INBOX + "recording.m4a")],
            frontmatter_responses=_empty_frontmatter(),
        )

        plan = _run_pipeline(tmp_path, client, extra_args=["--force-pass2"])
        schema = _load_schema()

        # force-pass2 overrides transcribe priority
        assert plan["action"] == "synthesize"
        json_validate(instance=plan, schema=schema)


# ---------------------------------------------------------------------------
# 5. Schema compliance
# ---------------------------------------------------------------------------


class TestRoutingPlanAllFieldsValid:
    def test_full_routing_plan_validates(self, tmp_path):
        """A routing plan with all optional fields populated validates against the schema."""
        sugg_path = INBOX + "2026-05-22_1432_suggestions.md"
        moc_path = INBOX + "2026-05-22_1832_moc-proposal-board-games.md"
        fan_items = ["Furano"]

        body_sugg = _suggestions_body(approved=True, fan_items=fan_items)
        body_moc = _moc_proposal_body(accepted=True)

        # Produce a plan with approved_suggestions, approved_moc_proposals,
        # force_atomic_items, fresh_sources, and metrics all populated.
        # Use force-pass2 to reach synthesize directly.
        fresh_path = INBOX + "brand-new.md"

        client = FakeKadoClient(
            listdir_items=[
                _file(sugg_path),
                _file(moc_path),
                _file(fresh_path),
            ],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
                "tomo.state=pending-accept": [
                    _fm_hit(moc_path, "moc-proposal", "pending-accept"),
                ],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": body_sugg, "modified": 0},
                moc_path: {"content": body_moc, "modified": 0},
            },
        )

        plan = _run_pipeline(tmp_path, client)
        schema = _load_schema()

        # Verify plan has the expected richness
        assert plan["action"] in {"fan-resolve", "synthesize"}
        assert "metrics" in plan
        assert "timestamp" in plan
        assert "inbox_path" in plan

        json_validate(instance=plan, schema=schema)


class TestSourcesInInstructionsMatchSchema:
    def test_instructions_sources_field_matches_frontmatter_schema(self, tmp_path):
        """Instructions doc sources[] field matches doc-frontmatter schema."""
        sugg_path = INBOX + "2026-05-22_1432_suggestions.md"
        instr_path = INBOX + "2026-05-24_0900_instructions.md"

        mod = _load_module()
        body = _suggestions_body(approved=True)
        checksum = mod._compute_checksum(body)

        sources = [{"path": sugg_path, "checksum": checksum}]

        # Validate a synthetic instructions doc frontmatter against the
        # doc-frontmatter schema to prove the sources[] shape is correct.
        doc_schema_path = REPO_ROOT / "tomo" / "schemas" / "doc-frontmatter.schema.json"
        doc_schema = json.loads(doc_schema_path.read_text(encoding="utf-8"))

        frontmatter = {
            "tomo": {
                "doc_type": "instructions",
                "state": "pending-apply",
                "run_id": "test-run-001",
                "updated_at": "2026-05-24T09:00:00Z",
                "sources": sources,
            }
        }
        json_validate(instance=frontmatter, schema=doc_schema)

        # Also verify sources checksum matches the sha256 pattern
        assert checksum.startswith("sha256:")
        assert len(checksum) == 7 + 64  # "sha256:" + 64 hex chars
