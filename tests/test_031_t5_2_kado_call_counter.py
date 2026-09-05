#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t5_2_kado_call_counter.py — spec 031 T5.2 corrected _count_kado_calls.

`_count_kado_calls` claimed "1 listDir + 7 byFrontmatter + N body reads" but
returned `5 + body_reads`, and ignored the per-item reads at
`enrich_instructions_frontmatter` (read_frontmatter, one per instructions
hit), `resolve_handlers` (read_frontmatter, one per new source when the
tag-handler registry is non-empty), and `_cache_wire_sibling`
(read_file_bytes, one per garden-audit doc seen PLUS one per approved
suggestions/suggestions-fan doc — four call sites in read_approval_state).

The base is 3, not 2: T5.1's recursive listDir (the attachment index) AND
its listNotes(fields=["links"]) call (ADR-2, corrected — embed extraction
reads Kado's own metadataCache, since inbox-triage never has a note body to
run a regex against) both landed in the same phase as this fix, so the
formula accounts for both from the start.

Every test here counts the corrected function's output against
`len(client.calls)` — the fake client's own observed invocation log — never
against a second, independently hand-computed expectation. A test that
compared two hand-derived numbers would pass with the same wrong arithmetic
on both sides, which is exactly how this counter came to be wrong.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

INBOX_PATH = "100 Inbox/"


def _load_module():
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage_t52", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t52"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


def _fm_hit(path: str, doc_type: str, state: str) -> dict:
    return {
        "path": path,
        "modified": 1716300000000,
        "frontmatter": {"tomo": {"doc_type": doc_type, "state": state}},
    }


class _FullFakeClient:
    """Fake covering every Kado method inbox-triage.py calls, with an
    accurate invocation log — the single source of truth every test here
    counts against."""

    def __init__(
        self,
        *,
        listdir_items=None,
        frontmatter_responses=None,
        read_note_responses=None,
        read_frontmatter_responses=None,
        read_file_responses=None,
        list_notes_responses=None,
    ):
        self.calls: list[tuple[str, dict]] = []
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}
        self._read_frontmatter_responses = read_frontmatter_responses or {}
        self._read_file_responses = read_file_responses or {}
        self._list_notes_responses = list_notes_responses or []

    def list_dir(self, path, *, depth=None, limit=500):
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        return self._listdir_items

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        self.calls.append(("list_notes", {"path": path, "fields": fields}))
        return self._list_notes_responses

    def search_by_frontmatter(self, query, *, path_prefix=None, limit=500, modified_after=None):
        self.calls.append(("search_by_frontmatter", {"query": query}))
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path):
        self.calls.append(("read_note", {"path": path}))
        return self._read_note_responses.get(path, {"content": "", "modified": 0})

    def read_frontmatter(self, path):
        self.calls.append(("read_frontmatter", {"path": path}))
        return self._read_frontmatter_responses.get(path, {"content": {}})

    def read_file_bytes(self, path):
        self.calls.append(("read_file_bytes", {"path": path}))
        if path in self._read_file_responses:
            return self._read_file_responses[path]
        from lib.kado_client import KadoError
        raise KadoError(f"not found: {path}")


def _write_registry(tmp_path: Path) -> Path:
    """A non-empty tag-handler registry that matches nothing in this
    fixture — enough to exercise resolve_handlers' per-source read without
    complicating the routing outcome."""
    reg_dir = tmp_path / "tag-handlers"
    reg_dir.mkdir(parents=True, exist_ok=True)
    handler = {
        "id": "tsukai",
        "enabled": True,
        "match": {"tag_prefix": "MiYo/Tsukai/", "capture_segments": ["repo"],
                   "read_fields": ["category"]},
        "action": "insert_under_marker",
        "target": {"by": "repo", "map": {"Tomo": "Efforts/Tomo Dev Log.md"}},
        "marker": "## Captures",
        "placement": "inside",
        "compose": "n/a",
    }
    (reg_dir / "tsukai.json").write_text(json.dumps(handler), encoding="utf-8")
    return reg_dir


def _suggestions_body(approved: bool) -> str:
    mark = "[x]" if approved else "[ ]"
    return f"---\ntype: tomo-suggestions\n---\n\n- {mark} Approved\n"


def _garden_audit_body(approved: bool) -> str:
    mark = "[x]" if approved else "[ ]"
    return f"---\ntype: tomo-garden-audit\n---\n\n- {mark} Approved\n"


def _build_comprehensive_fixture(tmp_path: Path):
    """One fixture exercising every call site the original formula omitted:

      - the T5.1 recursive listDir (+1)
      - enrich_instructions_frontmatter: 2 instructions hits -> 2 reads
      - resolve_handlers: 1 fresh, unmatched source, non-empty registry -> 1 read
      - _cache_wire_sibling, all three read_approval_state (non-force_pass2)
        call sites: approved suggestions (1), approved suggestions-fan (1),
        garden-audit pre-check on an UNAPPROVED doc (1) — this last one is
        the case the OLD body_reads-based approximation could never see,
        since an unapproved garden-audit doc never lands in
        approved_garden_audits.

    Returns (client, registry_dir).
    """
    fresh_path = INBOX_PATH + "fresh-note.md"
    sugg_path = INBOX_PATH + "2026-05-22_1200_alpha_suggestions.md"
    fan_path = INBOX_PATH + "2026-05-22_1201_beta_suggestions-fan.md"
    garden_path = INBOX_PATH + "2026-05-22_1202_gamma_garden-audit.md"
    instr_path_1 = INBOX_PATH + "2026-05-20_0900_old_instructions.md"
    instr_path_2 = INBOX_PATH + "2026-05-21_0900_older_instructions.md"

    client = _FullFakeClient(
        listdir_items=[_listdir_item(fresh_path)],
        frontmatter_responses={
            "tomo.state=pending-approval": [
                _fm_hit(sugg_path, "suggestions", "pending-approval"),
                _fm_hit(fan_path, "suggestions-fan", "pending-approval"),
            ],
            "tomo.state=pending-accept": [
                _fm_hit(garden_path, "garden-audit", "pending-accept"),
            ],
            "tomo.state=captured": [],
            "tomo.doc_type=instructions": [
                _fm_hit(instr_path_1, "instructions", "pending-move"),
                _fm_hit(instr_path_2, "instructions", "pending-move"),
            ],
            "tomo.state=approved": [],
            "tomo.state=accepted": [],
            "tomo.state=pending-move": [],
        },
        read_note_responses={
            sugg_path: {"content": _suggestions_body(approved=True), "modified": 0},
            fan_path: {"content": _suggestions_body(approved=True), "modified": 0},
            garden_path: {"content": _garden_audit_body(approved=False), "modified": 0},
        },
        read_frontmatter_responses={
            fresh_path: {"content": {"tags": []}},
        },
        read_file_responses={
            sugg_path[:-3] + ".json": b"{}",
            fan_path[:-3] + ".json": b"{}",
            # garden_path's wire sibling is deliberately unconfigured — the
            # call is still made (and counted) even though it fails.
        },
    )
    registry_dir = _write_registry(tmp_path)
    return client, registry_dir


def test_corrected_counter_matches_observed_call_log(tmp_path):
    mod = _load_module()
    client, registry_dir = _build_comprehensive_fixture(tmp_path)

    state = mod.discover(
        client, INBOX_PATH, output_dir=str(tmp_path), registry_dir=registry_dir,
    )

    reported = mod._count_kado_calls(state)
    observed = len(client.calls)
    assert reported == observed, (
        f"_count_kado_calls reported {reported} but the client actually made "
        f"{observed} calls: {client.calls}"
    )


def test_current_formula_would_have_undercounted(tmp_path):
    """RED-documentation: the pre-fix formula (5 + body_reads) on this exact
    fixture undercounts badly. Recomputed independently here (not by calling
    the old code, which no longer exists) so this test keeps demonstrating
    the gap the fix closed, without needing the buggy implementation kept
    around."""
    mod = _load_module()
    client, registry_dir = _build_comprehensive_fixture(tmp_path)

    state = mod.discover(
        client, INBOX_PATH, output_dir=str(tmp_path), registry_dir=registry_dir,
    )

    body_reads = (
        len(state.approved_suggestions)
        + len(state.approved_fan)
        + len(state.approved_moc_proposals)
        + len(state.approved_garden_audits)
        + len(state.pending_approval)
    )
    old_formula_result = 5 + body_reads
    observed = len(client.calls)
    assert old_formula_result != observed, (
        "fixture no longer demonstrates the historical undercount — "
        f"old formula={old_formula_result} observed={observed}"
    )


def test_wire_sibling_reads_force_pass2_terminal_approved_site_counted(tmp_path):
    """The 4th _cache_wire_sibling call site — force_pass2's terminal-approved
    loop — is also counted, not just the three in the primary loop."""
    mod = _load_module()
    terminal_path = INBOX_PATH + "2026-05-19_0800_delta_suggestions.md"

    client = _FullFakeClient(
        listdir_items=[],
        frontmatter_responses={
            "tomo.state=pending-approval": [],
            "tomo.state=pending-accept": [],
            "tomo.state=captured": [],
            "tomo.doc_type=instructions": [],
            "tomo.state=approved": [
                _fm_hit(terminal_path, "suggestions", "approved"),
            ],
            "tomo.state=accepted": [],
            "tomo.state=pending-move": [],
        },
        read_note_responses={
            terminal_path: {"content": _suggestions_body(approved=True), "modified": 0},
        },
        read_file_responses={
            terminal_path[:-3] + ".json": b"{}",
        },
    )

    state = mod.discover(
        client, INBOX_PATH, output_dir=str(tmp_path), force_pass2=True,
    )

    reported = mod._count_kado_calls(state)
    observed = len(client.calls)
    assert reported == observed, (
        f"reported={reported} observed={observed} calls={client.calls}"
    )
    # Sanity: the wire-sibling call for the force_pass2 site actually happened.
    assert ("read_file_bytes", {"path": terminal_path[:-3] + ".json"}) in client.calls


def test_t5_1_calls_are_included_in_the_base(tmp_path):
    """The base count reflects ALL THREE T5.1 calls: the existing depth=1
    listDir, the recursive attachment-index listDir, and the listNotes
    embed-extraction call (ADR-2, corrected) — not just the original one."""
    mod = _load_module()
    client = _FullFakeClient(
        listdir_items=[],
        frontmatter_responses={
            "tomo.state=pending-approval": [],
            "tomo.state=pending-accept": [],
            "tomo.state=captured": [],
            "tomo.doc_type=instructions": [],
            "tomo.state=approved": [],
            "tomo.state=accepted": [],
            "tomo.state=pending-move": [],
        },
    )

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    list_dir_calls = [c for name, c in client.calls if name == "list_dir"]
    list_notes_calls = [c for name, c in client.calls if name == "list_notes"]
    assert len(list_dir_calls) == 2
    assert len(list_notes_calls) == 1
    assert mod._count_kado_calls(state) == len(client.calls) == 10
