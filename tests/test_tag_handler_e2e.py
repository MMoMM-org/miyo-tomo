#!/usr/bin/env python3
# version: 0.1.0
"""test_tag_handler_e2e.py — T6.1 (spec 024 Phase 6): Tomo-side E2E seam tests.

Proves the full Tomo-side path for the tag-handler framework with NO cross-repo
dependency. Tests AC-1 through AC-5 as specified in PRD §7 and solution.md §5-6.

LLM/compose boundary: the compose step (interpreter SKILL) is deliberately NOT
invoked. The deterministic seams are tested:
  - triage handled[] population       → AC-1 (deterministic, inbox-triage)
  - grouping is one group of three    → AC-3 (routing-plan: all three under one handler+target)
  - render fixture → instruction       → AC-2 path (instruction-render with fixture composed_block)
  - guards                             → AC-4 (target_missing / marker_missing)
  - empty registry byte-identity      → AC-5 (re-invokes the existing invariant)

Schema SSoT: hashi-instructions.schema.json is the live Hashi contract. The
older instructions.schema.json lacks insert_under_marker but is NOT used as a
validation gate for tag-handler instructions (instruction-render.py only runs
_validate_action_paths, not jsonschema-against-instructions.schema.json). The
emitted insert_under_marker validates against hashi-instructions.schema.json.
Spec: docs/XDD/specs/024-tag-handler-framework/solution.md §5-6; requirements AC-1..AC-5.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_DIR = REPO_ROOT / "tomo" / "schemas"

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

sys.path.insert(0, str(SCRIPTS_DIR))

from jsonschema import validate as _validate  # noqa: E402

HASHI_SCHEMA = json.loads(
    (SCHEMA_DIR / "hashi-instructions.schema.json").read_text(encoding="utf-8")
)

INBOX_PATH = "100 Inbox/"


# ── Module loaders ─────────────────────────────────────────────────────────────


def _load(mod_name: str, filename: str):
    """Load a hyphenated top-level script as a module — house pattern."""
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_triage():
    return _load("inbox_triage", "inbox-triage.py")


_group_mod = _load("tag_handler_group", "tag-handler-group.py")
_reducer_mod = _load("suggestions_reducer", "suggestions-reducer.py")
_parser_mod = _load("suggestion_parser", "suggestion-parser.py")
_render_mod = _load("instruction_render", "instruction-render.py")
_writer_mod = _load("tag_handler_writer", "tag-handler-writer.py")

group_id = _group_mod.group_id
annotate_tag_handler_group_guards = _reducer_mod.annotate_tag_handler_group_guards
render_tag_handler_updates_block = _reducer_mod.render_tag_handler_updates_block
parse_tag_handler_groups = _parser_mod.parse_tag_handler_groups
_build_insert_under_marker_actions = _render_mod._build_insert_under_marker_actions
write_handler = _writer_mod.write_handler

from lib.kado_client import KadoNotFoundError  # noqa: E402


# ── Fake Kado for triage ───────────────────────────────────────────────────────


class FakeKadoClient:
    """Minimal KadoClient replacement that returns pre-configured responses.
    Mirrors the pattern in tests/test_inbox_triage.py."""

    def __init__(
        self,
        *,
        listdir_items: list[dict] | None = None,
        frontmatter_responses: dict[str, list[dict]] | None = None,
        read_note_responses: dict[str, dict] | None = None,
        read_frontmatter_responses: dict[str, dict] | None = None,
    ):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}
        self._read_frontmatter_responses = read_frontmatter_responses or {}
        self.calls: list[tuple[str, dict]] = []

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        return self._listdir_items

    def search_by_frontmatter(
        self, query: str, *, path_prefix: str | None = None, limit: int = 500,
        modified_after: int | None = None,
    ) -> list[dict]:
        self.calls.append(("search_by_frontmatter", {"query": query}))
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        self.calls.append(("read_note", {"path": path}))
        # Intentional: raises on unmapped paths — this fake is triage-only here; no
        # silent-stub read_note is expected (unlike the same-named fake in test_inbox_triage.py).
        if path not in self._read_note_responses:
            raise KadoNotFoundError(f"not found: {path}")
        return self._read_note_responses[path]

    def read_frontmatter(self, path: str) -> dict:
        self.calls.append(("read_frontmatter", {"path": path}))
        return self._read_frontmatter_responses.get(path, {"content": {}})


# ── Fake Kado for guard annotation (simulates vault read) ─────────────────────


class FakeVaultKado:
    """Simulates note reads for annotate_tag_handler_group_guards."""

    def __init__(self, notes: dict[str, str]):
        self._notes = notes

    def read_note(self, path: str) -> dict:
        if path not in self._notes:
            raise KadoNotFoundError(f"not found: {path}")
        return {"content": self._notes[path]}


# ── Registry helpers ───────────────────────────────────────────────────────────


def _tsukai_handler(target_path: str = "Efforts/400 On/Tomo Dev Log.md") -> dict:
    """A USER-AUTHORED handler JSON for Tsukai captures (AC-2).
    Written via tag-handler-writer.py interface — this fixture represents that output.
    """
    return {
        "id": "tsukai",
        "enabled": True,
        "match": {
            "tag_prefix": "MiYo/Tsukai/",
            "capture_segments": ["repo"],
            "read_fields": ["category"],
        },
        "action": "insert_under_marker",
        "target": {
            "by": "repo",
            "map": {"Tomo": target_path},
        },
        "marker": "## Captures",
        "placement": "inside",
        "compose": "Synthesize the batch captures into one dated status update.",
    }


def _write_registry(tmp_path: Path, *handlers: dict) -> Path:
    """Write handler configs into a temp registry dir; return its path."""
    reg_dir = tmp_path / "tag-handlers"
    reg_dir.mkdir(parents=True, exist_ok=True)
    for h in handlers:
        (reg_dir / f"{h['id']}.json").write_text(
            json.dumps(h), encoding="utf-8"
        )
    return reg_dir


def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


def _fm_content(tags: list[str] | None = None, **extra) -> dict:
    """Simulate a read_frontmatter response body."""
    fm: dict = {}
    if tags is not None:
        fm["tags"] = tags
    fm.update(extra)
    return {"content": fm, "modified": 1716300000000}


_EMPTY_FM_RESPONSES = {
    "tomo.state=pending-approval": [],
    "tomo.state=pending-accept": [],
    "tomo.state=captured": [],
    "tomo.doc_type=instructions": [],
    "tomo.state=approved": [],
    "tomo.state=accepted": [],
}


# ── Group fixture builder ──────────────────────────────────────────────────────


def _group(
    *,
    handler: str = "tsukai",
    target_path: str | None = "Efforts/400 On/Tomo Dev Log.md",
    marker: str = "## Captures",
    composed_block: str = "### 2026-06-23\n\n- Shipped X (feature)\n- Decided Y (architecture)",
    source_paths: list[str] | None = None,
    placement: str | None = "inside",
    compose_mode: str | None = "llm_directive",
    guard: str | None = None,
) -> dict:
    """Build a minimal valid tag-handler-group result fixture."""
    g: dict[str, Any] = {
        "schema_version": "1",
        "handler": handler,
        "target_path": target_path,
        "marker": marker,
        "composed_block": composed_block,
        "source_paths": source_paths or ["100 Inbox/MiYo-Tsukai-Tomo-cap-1.md"],
    }
    if placement is not None:
        g["placement"] = placement
    if compose_mode is not None:
        g["compose_mode"] = compose_mode
    if guard is not None:
        g["guard"] = guard
    return g


def _wrap_instructions(actions: list[dict]) -> dict:
    """Wrap actions in a minimal valid tomo-instructions doc for schema validation."""
    return {
        "schema_version": "2",
        "type": "tomo-instructions",
        "generated": "2026-06-23T12:00:00Z",
        "profile": "miyo",
        "actions": actions,
    }


# ── AC-1: three tagged captures → all three in handled[] ──────────────────────


class TestAC1ThreeCapturesAllHandled:
    """AC-1: 3 MiYo/Tsukai/<repo>-tagged captures (same repo) → triage marks
    all three in routing-plan.json handled[]."""

    def test_three_tagged_captures_all_in_handled(self, tmp_path):
        mod = _load_triage()

        cap1 = INBOX_PATH + "cap-tsukai-1.md"
        cap2 = INBOX_PATH + "cap-tsukai-2.md"
        cap3 = INBOX_PATH + "cap-tsukai-3.md"
        reg_dir = _write_registry(tmp_path, _tsukai_handler())

        client = FakeKadoClient(
            listdir_items=[
                _listdir_item(cap1),
                _listdir_item(cap2),
                _listdir_item(cap3),
            ],
            frontmatter_responses=_EMPTY_FM_RESPONSES,
            read_frontmatter_responses={
                cap1: _fm_content(tags=["MiYo/Tsukai/Tomo"], category="feature"),
                cap2: _fm_content(tags=["MiYo/Tsukai/Tomo"], category="architecture"),
                cap3: _fm_content(tags=["MiYo/Tsukai/Tomo"], category="fix"),
            },
        )

        rc = mod.main(
            [
                "--inbox-path", INBOX_PATH,
                "--output-dir", str(tmp_path),
                "--registry-dir", str(reg_dir),
            ],
            client_factory=lambda: client,
        )

        assert rc == 0
        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        assert "handled" in plan, "handled key must be present when items matched"
        handled_paths = {e["path"] for e in plan["handled"]}
        assert handled_paths == {cap1, cap2, cap3}, (
            f"Expected all three captures in handled; got {handled_paths}"
        )
        # All are excluded from the generic suggest lane
        fresh_paths = {s["path"] for s in plan.get("fresh_sources", [])}
        assert not handled_paths.intersection(fresh_paths), (
            "Handled items must be absent from fresh_sources"
        )

    def test_all_handled_entries_have_correct_handler_and_action(self, tmp_path):
        """Each handled entry names the user-authored handler and the v1 action."""
        mod = _load_triage()

        caps = [INBOX_PATH + f"cap-{i}.md" for i in range(1, 4)]
        reg_dir = _write_registry(tmp_path, _tsukai_handler())

        client = FakeKadoClient(
            listdir_items=[_listdir_item(p) for p in caps],
            frontmatter_responses=_EMPTY_FM_RESPONSES,
            read_frontmatter_responses={
                p: _fm_content(tags=["MiYo/Tsukai/Tomo"]) for p in caps
            },
        )

        rc = mod.main(
            [
                "--inbox-path", INBOX_PATH,
                "--output-dir", str(tmp_path),
                "--registry-dir", str(reg_dir),
            ],
            client_factory=lambda: client,
        )

        assert rc == 0
        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        for entry in plan["handled"]:
            assert entry["handler"] == "tsukai"
            assert entry["action"] == "insert_under_marker"
            assert entry["vars"] == {"repo": "Tomo"}


# ── AC-2: user-authored handler (via tag-handler-writer shape) drives detection ─


class TestAC2UserAuthoredHandler:
    """AC-2: a USER-AUTHORED handler (written into a temp registry via the
    tag-handler-writer.py contract) drives detection and handling — the handler
    dict is NOT hardcoded; the test writes it into a tmp dir as a JSON file."""

    def test_user_authored_handler_written_to_registry(self, tmp_path):
        """The handler is authored via tag-handler-writer.py (schema-validated,
        atomic write) — only this handler config drives the match, not hardcoded data.
        Exercises the real writer contract: schema validation + atomic write (FR-13)."""
        mod = _load_triage()

        # Author the handler via the real tag-handler-writer.py write_handler()
        # function — the same path the tomo-tag-handler-wizard skill uses (FR-13).
        # This exercises schema validation + atomic write, not a raw json.dumps.
        handler = _tsukai_handler()
        reg_dir = tmp_path / "tag-handlers"
        reg_dir.mkdir(parents=True, exist_ok=True)
        written_path = write_handler(handler, reg_dir)
        written_json = json.loads(written_path.read_text(encoding="utf-8"))
        assert written_json["id"] == "tsukai"  # authored file is readable

        cap = INBOX_PATH + "tsukai-capture.md"
        client = FakeKadoClient(
            listdir_items=[_listdir_item(cap)],
            frontmatter_responses=_EMPTY_FM_RESPONSES,
            read_frontmatter_responses={
                cap: _fm_content(tags=["MiYo/Tsukai/Tomo"], category="feature"),
            },
        )

        rc = mod.main(
            [
                "--inbox-path", INBOX_PATH,
                "--output-dir", str(tmp_path),
                "--registry-dir", str(reg_dir),
            ],
            client_factory=lambda: client,
        )

        assert rc == 0
        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        assert "handled" in plan
        assert plan["handled"][0]["handler"] == "tsukai"
        assert plan["handled"][0]["target_path"] == "Efforts/400 On/Tomo Dev Log.md"

    def test_render_from_user_authored_group_validates_schema(self):
        """An approved group with a fixture composed_block → one insert_under_marker
        that validates against hashi-instructions.schema.json (AC-2 render path)."""
        g = _group(guard="ok")
        approved_ids = [group_id(g)]
        counter = [0]
        actions = _build_insert_under_marker_actions([g], approved_ids, counter)

        assert len(actions) == 1
        doc = _wrap_instructions(actions)
        _validate(instance=doc, schema=HASHI_SCHEMA)  # must not raise


# ── AC-3: three captures for one repo → exactly ONE group ─────────────────────


class TestAC3ThreeCapturesOneGroup:
    """AC-3: three Tsukai captures for one repo in a batch → exactly ONE merged
    suggestion targeting the repo-mapped note under ## Captures.

    The grouping by (handler, target_path) happens in the tag-handler-interpreter
    SKILL (LLM step). The DETERMINISTIC contract tested here is that triage marks
    all three in handled[] with the SAME handler and target_path — which is the
    input contract the interpreter receives, guaranteeing FR-7/FR-8: one group,
    one compose call. We also assert the render contract: given a pre-composed
    group (fixture composed_block), exactly ONE insert_under_marker is emitted.
    """

    def test_three_captures_same_handler_and_target_in_routing_plan(self, tmp_path):
        """All three captures share (handler='tsukai', target_path=…Dev Log) in
        routing-plan.json — this is the grouping input that guarantees one group."""
        mod = _load_triage()

        caps = [INBOX_PATH + f"cap-tsukai-{i}.md" for i in range(1, 4)]
        reg_dir = _write_registry(tmp_path, _tsukai_handler())

        client = FakeKadoClient(
            listdir_items=[_listdir_item(p) for p in caps],
            frontmatter_responses=_EMPTY_FM_RESPONSES,
            read_frontmatter_responses={
                caps[0]: _fm_content(tags=["MiYo/Tsukai/Tomo"], category="feature"),
                caps[1]: _fm_content(tags=["MiYo/Tsukai/Tomo"], category="architecture"),
                caps[2]: _fm_content(tags=["MiYo/Tsukai/Tomo"], category="fix"),
            },
        )

        rc = mod.main(
            [
                "--inbox-path", INBOX_PATH,
                "--output-dir", str(tmp_path),
                "--registry-dir", str(reg_dir),
            ],
            client_factory=lambda: client,
        )

        assert rc == 0
        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        entries = plan["handled"]
        assert len(entries) == 3

        # All three share the same (handler, target_path) — this is the
        # grouping key that interpreter uses to produce exactly ONE group (FR-7).
        handlers = {e["handler"] for e in entries}
        targets = {e["target_path"] for e in entries}
        assert handlers == {"tsukai"}, f"Expected single handler; got {handlers}"
        assert len(targets) == 1, f"Expected single target; got {targets}"

    def test_three_captures_one_group_renders_one_instruction(self):
        """Given a pre-composed group merging three source_paths → exactly ONE
        insert_under_marker action (the render-side AC-3 contract)."""
        composed = "### 2026-06-23\n\n- Cap 1 (feature)\n- Cap 2 (architecture)\n- Cap 3 (fix)"
        g = _group(
            source_paths=[
                "100 Inbox/cap-tsukai-1.md",
                "100 Inbox/cap-tsukai-2.md",
                "100 Inbox/cap-tsukai-3.md",
            ],
            composed_block=composed,
            guard="ok",
        )
        approved_ids = [group_id(g)]
        counter = [0]
        actions = _build_insert_under_marker_actions([g], approved_ids, counter)

        assert len(actions) == 1, (
            f"Expected exactly ONE instruction for the merged group; got {len(actions)}"
        )
        action = actions[0]
        assert action["action"] == "insert_under_marker"
        assert action["content"] == composed
        assert action["anchor"]["value"] == "Captures"


# ── AC-4: guards — missing target + missing marker ────────────────────────────


class TestAC4Guards:
    """AC-4: missing target note → 'create it first' guard item (no instruction);
    missing marker in an existing target → error item (no instruction).

    These guards are checked via annotate_tag_handler_group_guards and the
    render→parse→build chain. Constitution L1: filesystem paths must have denial
    path coverage."""

    def test_missing_target_guard_blocks_instruction(self):
        """FR-11: target_path note absent → guard=target_missing → NO instruction."""
        g = _group()
        fake_vault = FakeVaultKado({})  # empty vault — read_note raises NotFound
        annotate_tag_handler_group_guards([g], fake_vault)
        assert g["guard"] == "target_missing"

        # Run the render→parse→build chain
        md = render_tag_handler_updates_block([g])
        approved = parse_tag_handler_groups(md)
        actions = _build_insert_under_marker_actions([g], approved, [0])

        assert actions == [], "No instruction must be emitted for target_missing guard"

    def test_missing_marker_guard_blocks_instruction(self):
        """FR-12: target exists but marker heading absent → guard=marker_missing →
        NO instruction (error item surfaces in the suggestions block instead)."""
        note_without_marker = (
            "---\ntype: dev-log\n---\n\n"
            "# Tomo Dev Log\n\n"
            "## Notes\n\n"
            "- something else\n"
        )
        g = _group()
        fake_vault = FakeVaultKado({
            "Efforts/400 On/Tomo Dev Log.md": note_without_marker,
        })
        annotate_tag_handler_group_guards([g], fake_vault)
        assert g["guard"] == "marker_missing"

        # Render → parse → build: guard=marker_missing means no Approve box →
        # parser never extracts this group → no action
        md = render_tag_handler_updates_block([g])
        approved = parse_tag_handler_groups(md)
        actions = _build_insert_under_marker_actions([g], approved, [0])

        assert actions == [], "No instruction must be emitted for marker_missing guard"

    def test_guard_item_body_contains_user_signal(self):
        """The rendered block for a guarded group carries the user-visible signal
        ('Create it first' for target_missing; 'Marker not found' for marker_missing)."""
        g_target = _group(guard="target_missing")
        block_target = render_tag_handler_updates_block([g_target])
        assert "Create it first" in block_target
        assert "- [x] Approve" not in block_target

        g_marker = _group(handler="tsukai", target_path="Efforts/400 On/Other.md", guard="marker_missing")
        block_marker = render_tag_handler_updates_block([g_marker])
        assert "Marker not found" in block_marker
        assert "- [x] Approve" not in block_marker

    def test_ok_group_emits_single_instruction(self):
        """Positive control: a group with guard=ok → exactly ONE insert_under_marker."""
        note_with_marker = (
            "---\ntype: dev-log\n---\n\n"
            "# Tomo Dev Log\n\n"
            "## Captures\n\n"
            "- 2026-06-20 — earlier entry\n"
        )
        g = _group()
        fake_vault = FakeVaultKado({
            "Efforts/400 On/Tomo Dev Log.md": note_with_marker,
        })
        annotate_tag_handler_group_guards([g], fake_vault)
        assert g["guard"] == "ok"

        md = render_tag_handler_updates_block([g])
        approved = parse_tag_handler_groups(md)
        actions = _build_insert_under_marker_actions([g], approved, [0])
        assert len(actions) == 1
        assert actions[0]["action"] == "insert_under_marker"


# ── AC-5: empty registry → byte-identical to today's routing-plan ─────────────


class TestAC5EmptyRegistry:
    """AC-5: a run with NO registered handlers is byte-identical to current
    behaviour. Re-invokes and extends the existing invariant from
    tests/test_inbox_triage.py::TestTagHandlerResolution::test_empty_registry_byte_identity.

    This test is independent — it re-asserts the invariant from the E2E perspective
    so T6.1 does not depend on the T2.1 test passing to cover AC-5.
    """

    def test_empty_registry_no_handled_key_no_extra_kado_calls(self, tmp_path):
        """No registry → no handled key in routing-plan; zero extra Kado calls."""
        mod = _load_triage()

        src = INBOX_PATH + "fresh-note.md"

        def _make_client():
            return FakeKadoClient(
                listdir_items=[_listdir_item(src)],
                frontmatter_responses=_EMPTY_FM_RESPONSES,
            )

        # Baseline: default registry path (does not exist → empty registry)
        baseline_client = _make_client()
        rc0 = mod.main(
            ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path / "base")],
            client_factory=lambda: baseline_client,
        )
        assert rc0 == 0
        baseline_plan = json.loads(
            (tmp_path / "base" / "routing-plan.json").read_text(encoding="utf-8")
        )
        baseline_calls = len(baseline_client.calls)

        # Explicit empty registry dir
        empty_reg = tmp_path / "tag-handlers"
        empty_reg.mkdir(parents=True, exist_ok=True)

        client = _make_client()
        rc = mod.main(
            [
                "--inbox-path", INBOX_PATH,
                "--output-dir", str(tmp_path / "run"),
                "--registry-dir", str(empty_reg),
            ],
            client_factory=lambda: client,
        )
        assert rc == 0
        plan = json.loads(
            (tmp_path / "run" / "routing-plan.json").read_text(encoding="utf-8")
        )

        # (a) No handled key
        assert "handled" not in plan, "Empty registry must not emit handled key"
        # (b) fresh_sources identical to baseline
        assert plan["fresh_sources"] == baseline_plan["fresh_sources"]
        # (b2) Absolute invariant: the source note must appear in fresh_sources
        assert {s["path"] for s in plan["fresh_sources"]} == {src}, (
            "fresh_sources must contain the source note path"
        )
        # (c) No extra Kado calls vs baseline
        assert len(client.calls) == baseline_calls


# ── Approved group → schema-validated insert_under_marker (AC-2 render path) ──


class TestRenderToHashiSchema:
    """An approved group renders to exactly ONE insert_under_marker that
    validates against hashi-instructions.schema.json (the verbatim Hashi contract).
    This is the AC-2 render path: user-authored handler → fixture group → instruction."""

    def test_approved_group_validates_against_hashi_schema(self):
        g = _group(guard="ok")
        approved_ids = [group_id(g)]
        counter = [0]
        actions = _build_insert_under_marker_actions([g], approved_ids, counter)

        assert len(actions) == 1
        action = actions[0]
        assert action["action"] == "insert_under_marker"
        assert action["target_path"] == g["target_path"]
        assert action["anchor"] == {"type": "heading", "value": "Captures"}
        assert action["placement"] == "inside"
        assert action["content"] == g["composed_block"]

        doc = _wrap_instructions(actions)
        _validate(instance=doc, schema=HASHI_SCHEMA)

    def test_anchor_value_marker_stripped(self):
        """'## Captures' → 'Captures' in the emitted anchor (SDD §5 transform)."""
        g = _group(marker="## Captures", guard="ok")
        actions = _build_insert_under_marker_actions([g], [group_id(g)], [0])
        assert actions[0]["anchor"]["value"] == "Captures"

    def test_content_is_composed_block_verbatim(self):
        """content equals composed_block exactly — embedded newlines preserved."""
        composed = "### 2026-06-23\n\n- Line one\n- Line two\n\n- After blank"
        g = _group(composed_block=composed, guard="ok")
        actions = _build_insert_under_marker_actions([g], [group_id(g)], [0])
        assert actions[0]["content"] == composed
        assert "\n" in actions[0]["content"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
