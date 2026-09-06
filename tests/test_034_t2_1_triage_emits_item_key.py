#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t2_1_triage_emits_item_key.py — inbox-triage emits item_key per item.

Covers T2.1 (XDD 034 Phase 2): the only routing-plan.schema.json array that
requires item_key today is force_atomic_items (Phase 1, T1.2) — the two
construction sites are _extract_fan_items (markdown path) and
_extract_fan_items_from_wire (ADR-026 edited-wire path), both threaded through
read_approval_state/discover into build_routing_plan unchanged.

ADR-1: item_key IS the vault-relative path, verbatim — no slug, no lowercase,
no normalisation. Every case below uses a path with a subfolder, a space and
mixed case so a normalising implementation fails loudly.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate as json_validate  # noqa: E402

# A path with a subfolder, a space and mixed case — a normalising, lowercasing
# or slugging implementation collapses this into something else (ADR-1 trap).
SUBFOLDER_SPACE_MIXED_CASE = "100 Inbox/Places/2026-05-22_1432_Suggestions.md"


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
    schema_path = REPO_ROOT / "tomo" / "schemas" / "routing-plan.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixtures shared with test_inbox_triage.py / test_018_pipeline.py conventions
# ---------------------------------------------------------------------------

INBOX_PATH = "100 Inbox/"


class FakeKadoClient:
    """Minimal KadoClient replacement (mirrors test_inbox_triage.py's fake)."""

    def __init__(
        self,
        *,
        listdir_items=None,
        frontmatter_responses=None,
        read_note_responses=None,
    ):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        return self._listdir_items

    def list_notes(self, path: str, *, fields=None, depth=None, limit: int = 500):
        return []

    def search_by_frontmatter(
        self, query: str, *, path_prefix=None, limit: int = 500,
        modified_after=None,
    ) -> list:
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        return self._read_note_responses.get(path, {"content": "", "modified": 0})

    def read_frontmatter(self, path: str) -> dict:
        return {"content": {}}

    def read_file_bytes(self, path: str) -> bytes:
        from lib.kado_client import KadoError

        raise KadoError(f"not found: {path}")


def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


def _fm_hit(path: str, doc_type: str, state: str) -> dict:
    return {
        "path": path,
        "modified": 1716300000000,
        "frontmatter": {
            "tomo": {
                "doc_type": doc_type,
                "state": state,
                "run_id": "test-run",
                "updated_at": "2026-05-21T12:00:00Z",
            }
        },
    }


def _empty_frontmatter() -> dict:
    return {
        "tomo.state=pending-approval": [],
        "tomo.state=pending-accept": [],
        "tomo.state=captured": [],
        "tomo.doc_type=instructions": [],
    }


def _suggestions_body(approved: bool, fan_items: list[str] | None = None) -> str:
    """Build a minimal suggestions doc body (mirrors test_inbox_triage.py)."""
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


# ---------------------------------------------------------------------------
# 1. Unit level: _extract_fan_items carries item_key, verbatim
# ---------------------------------------------------------------------------

class TestExtractFanItemsCarriesItemKey:
    def test_item_key_equals_source_path_verbatim(self):
        mod = _load_module()
        body = _suggestions_body(approved=True, fan_items=["Furano"])

        items = mod._extract_fan_items(body, SUBFOLDER_SPACE_MIXED_CASE)

        assert len(items) == 1
        assert items[0]["item_key"] == SUBFOLDER_SPACE_MIXED_CASE
        # stem keeps its own, unrelated, unaffected meaning.
        assert items[0]["stem"] == "Furano"
        assert items[0]["source_path"] == SUBFOLDER_SPACE_MIXED_CASE

    def test_item_key_not_normalised_lowercased_or_slugged(self):
        """ADR-1: no slug, no lowercase, no normalisation — the trap test."""
        mod = _load_module()
        body = _suggestions_body(approved=True, fan_items=["Niseko"])

        items = mod._extract_fan_items(body, SUBFOLDER_SPACE_MIXED_CASE)

        item_key = items[0]["item_key"]
        # A normalising/slugging implementation would strip the space, fold
        # case, or collapse the subfolder — none of that may happen.
        assert " " in item_key, "space was stripped — item_key was normalised"
        assert "/" in item_key, "subfolder separator lost"
        assert item_key != item_key.lower(), "item_key was lowercased"
        assert item_key == SUBFOLDER_SPACE_MIXED_CASE

    def test_multiple_fan_items_each_carry_item_key(self):
        """Two FAN checkboxes in one suggestions doc — both carry item_key."""
        mod = _load_module()
        body = _suggestions_body(approved=True, fan_items=["Furano", "Niseko"])

        items = mod._extract_fan_items(body, SUBFOLDER_SPACE_MIXED_CASE)

        assert len(items) == 2
        for item in items:
            assert item["item_key"] == SUBFOLDER_SPACE_MIXED_CASE


# ---------------------------------------------------------------------------
# 2. Unit level: _extract_fan_items_from_wire carries item_key (ADR-026)
# ---------------------------------------------------------------------------

class TestExtractFanItemsFromWireCarriesItemKey:
    def test_item_key_equals_source_path_verbatim(self):
        mod = _load_module()
        wire = {
            "schema_version": "1",
            "suggestions": [
                {"id": "S01", "stem": "Asahikawa", "suppressed": True, "force_atomic": True},
            ],
            "daily_updates": [],
        }

        items = mod._extract_fan_items_from_wire(wire, SUBFOLDER_SPACE_MIXED_CASE)

        assert len(items) == 1
        assert items[0]["item_key"] == SUBFOLDER_SPACE_MIXED_CASE
        assert items[0]["stem"] == "Asahikawa"
        assert items[0]["source_path"] == SUBFOLDER_SPACE_MIXED_CASE

    def test_item_key_not_normalised(self):
        mod = _load_module()
        wire = {
            "schema_version": "1",
            "suggestions": [],
            "daily_updates": [
                {"date": "2026-04-17", "log_entries": [
                    {"source_stem": "Sapporo", "force_atomic_note": True},
                ]},
            ],
        }

        items = mod._extract_fan_items_from_wire(wire, SUBFOLDER_SPACE_MIXED_CASE)

        assert len(items) == 1
        assert items[0]["item_key"] == SUBFOLDER_SPACE_MIXED_CASE
        assert items[0]["item_key"] != items[0]["item_key"].lower()


# ---------------------------------------------------------------------------
# 3. discover() level: end-to-end, flat inbox is unchanged plus the new field
# ---------------------------------------------------------------------------

class TestDiscoverFlatInboxAddsItemKeyOnly:
    def test_flat_inbox_force_atomic_items_carry_item_key(self, tmp_path):
        """A flat-inbox run produces the same items as before, plus item_key."""
        mod = _load_module()
        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        body = _suggestions_body(approved=True, fan_items=["Furano", "Niseko"])

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                **_empty_frontmatter(),
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.force_atomic_items) == 2
        stems = {item["stem"] for item in state.force_atomic_items}
        assert stems == {"Furano", "Niseko"}
        for item in state.force_atomic_items:
            # Unchanged fields, exactly as before this task.
            assert item["source_path"] == sugg_path
            # New field, additive.
            assert item["item_key"] == sugg_path

    def test_subfolder_suggestions_doc_item_key_is_its_own_path(self, tmp_path):
        """A suggestions doc discovered under a subfolder keeps its full path
        as item_key — no reconstruction from a bare stem."""
        mod = _load_module()
        sugg_path = SUBFOLDER_SPACE_MIXED_CASE
        body = _suggestions_body(approved=True, fan_items=["Dresden"])

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                **_empty_frontmatter(),
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.force_atomic_items) == 1
        assert state.force_atomic_items[0]["item_key"] == SUBFOLDER_SPACE_MIXED_CASE


# ---------------------------------------------------------------------------
# 4. Full pipeline: routing-plan.json validates against the Phase-1 schema
# ---------------------------------------------------------------------------

class TestRoutingPlanValidatesWithItemKey:
    def test_fan_resolve_plan_validates_against_schema(self, tmp_path):
        mod = _load_module()
        sugg_path = SUBFOLDER_SPACE_MIXED_CASE
        body = _suggestions_body(approved=True, fan_items=["Furano", "Niseko"])

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                **_empty_frontmatter(),
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        rc = mod.main(
            ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
            client_factory=lambda: client,
        )
        assert rc == 0

        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        schema = _load_schema()

        assert plan["action"] == "fan-resolve"
        assert len(plan["force_atomic_items"]) == 2
        for item in plan["force_atomic_items"]:
            assert item["item_key"] == SUBFOLDER_SPACE_MIXED_CASE
        json_validate(instance=plan, schema=schema)
