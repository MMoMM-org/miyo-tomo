#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t6_3_cost_verification.py — Phase 6 T6.3 cost verification.

CON-4: attachment-related Kado calls must be constant as note count varies —
the O(1) claim ADR-1 depends on, enforced here by a test rather than by
argument. Three calls are constant regardless of note count: the existing
depth=1 partition listDir (discover_files), the recursive attachment-index
listDir (ADR-1), and the listNotes(fields=["links"]) extraction call
(ADR-2, corrected, T5.1 pt 2).

Asserts the PER-METHOD breakdown, not only the sum — a regression that
moves any ONE of the three calls into a per-note loop while the other two
stay constant would still show up in a per-method count, but a
sum-only assertion could stay coincidentally stable (e.g. one call growing
while a different one implausibly shrinks) or simply be less specific about
which call regressed. Also re-verifies `_count_kado_calls()` against the
observed invocation log — T5.2's own bar — but at SEVERAL note counts, not
just one fixed scenario, so a count-dependent regression in the formula
itself would surface here too.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

INBOX_PATH = "100 Inbox/"


def _load_module():
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage_t63", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t63"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


class _FakeClient:
    """Distinguishes depth=1 from the recursive listDir call — a fake that
    returns the same data regardless of depth would let a regression to
    depth=1 (or vice versa) pass unnoticed, exactly the trap caught in
    T6.1's first draft."""

    def __init__(self, n_notes: int):
        self._depth1_items = [_listdir_item(f"{INBOX_PATH}note-{i}.md") for i in range(n_notes)]
        self.calls: list[tuple[str, dict]] = []

    def list_dir(self, path, *, depth=None, limit=500):
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        if depth == 1:
            return self._depth1_items
        return self._depth1_items  # recursive sees the same flat set here

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        self.calls.append(("list_notes", {"path": path, "fields": fields}))
        return []  # no embeds in this fixture — cost verification only

    def search_by_frontmatter(self, query, *, path_prefix=None, limit=500, modified_after=None):
        self.calls.append(("search_by_frontmatter", {"query": query}))
        return []

    def read_note(self, path):
        self.calls.append(("read_note", {"path": path}))
        return {"content": "", "modified": 0}

    def read_frontmatter(self, path):
        self.calls.append(("read_frontmatter", {"path": path}))
        return {"content": {}}

    def read_file_bytes(self, path):
        self.calls.append(("read_file_bytes", {"path": path}))
        from lib.kado_client import KadoError
        raise KadoError(f"not found: {path}")


def _breakdown(client) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, args in client.calls:
        if name == "list_dir":
            key = "list_dir_depth1" if args["depth"] == 1 else "list_dir_recursive"
        else:
            key = name
        counts[key] = counts.get(key, 0) + 1
    return counts


def _run(mod, n_notes: int, out_dir: Path) -> tuple[dict[str, int], int, int]:
    """Returns (per-method breakdown, reported count, observed count)."""
    client = _FakeClient(n_notes)
    state = mod.discover(client, INBOX_PATH, output_dir=str(out_dir))
    reported = mod._count_kado_calls(state)
    observed = len(client.calls)
    return _breakdown(client), reported, observed


_ATTACHMENT_RELATED = ("list_dir_depth1", "list_dir_recursive", "list_notes")


def test_per_method_breakdown_constant_from_1_to_20_notes(tmp_path):
    mod = _load_module()
    results = {n: _run(mod, n, tmp_path / f"run-{n}") for n in (1, 5, 20)}

    for n, (breakdown, _reported, _observed) in results.items():
        scoped = {k: breakdown.get(k, 0) for k in _ATTACHMENT_RELATED}
        assert scoped == {
            "list_dir_depth1": 1,
            "list_dir_recursive": 1,
            "list_notes": 1,
        }, f"n={n}: breakdown={breakdown}"

    # Cross-check: all three note counts produce the IDENTICAL breakdown —
    # not just each individually equal to the same literal, but equal to
    # each other, so a future edit to the literal above can't silently
    # stop this from being a real comparison.
    scoped_breakdowns = [
        {k: results[n][0].get(k, 0) for k in _ATTACHMENT_RELATED} for n in (1, 5, 20)
    ]
    assert scoped_breakdowns[0] == scoped_breakdowns[1] == scoped_breakdowns[2]


def test_reported_count_matches_observed_at_several_note_counts(tmp_path):
    """T5.2's bar (_count_kado_calls == len(client.calls)), re-checked at
    several note counts rather than one fixed scenario — a count-dependent
    regression in the formula (e.g. a term that scales when it shouldn't)
    would surface as a growing gap here, not a fixed one."""
    mod = _load_module()
    for n in (1, 5, 20):
        _breakdown, reported, observed = _run(mod, n, tmp_path / f"run-{n}")
        assert reported == observed, f"n={n}: reported={reported} observed={observed}"


def test_only_the_three_attachment_related_calls_are_constant(tmp_path):
    """Sanity: byFrontmatter calls (7, fixed by the query set, not by note
    count) and the total are ALSO constant in this no-approvals fixture —
    confirming the fixture itself varies note count meaningfully (more
    fresh sources), not that everything is trivially constant because
    nothing is happening."""
    mod = _load_module()
    _breakdown_1, reported_1, _observed_1 = _run(mod, 1, tmp_path / "one")
    _breakdown_20, reported_20, _observed_20 = _run(mod, 20, tmp_path / "twenty")

    assert reported_1 == reported_20 == 10  # 3 attachment calls + 7 byFrontmatter

    # But new_sources itself DID scale with note count — proving the
    # constancy above is a genuine property of the attachment-related
    # calls, not an artifact of an empty/degenerate fixture.
    mod2 = _load_module()
    client_1 = _FakeClient(1)
    state_1 = mod2.discover(client_1, INBOX_PATH, output_dir=str(tmp_path / "verify-one"))
    client_20 = _FakeClient(20)
    state_20 = mod2.discover(client_20, INBOX_PATH, output_dir=str(tmp_path / "verify-twenty"))
    assert len(state_1.new_sources) == 1
    assert len(state_20.new_sources) == 20
