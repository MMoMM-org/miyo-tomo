#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t5_1_attachment_index.py — spec 031 T5.1 inbox attachment index.

Covers `build_attachment_index` (inbox-triage.py) and its wiring into
`discover()`:
  - the recursive listDir is requested exactly once per run, independent of
    note count (CON-4 / PRD business rule 9)
  - the recursive call targets the inbox path, not the vault root (PRD
    business rule 3 — only inbox paths can ever appear in the index)
  - a KadoError on the recursive call degrades to an empty index and the run
    continues (no exception escapes) — PRD business rule 10
  - the index is stored on TriageState and persisted to
    <output_dir>/attachment-index.json for a later, separate process
    (suggestions-reducer.py's resolution step) to consume without its own
    recursive listDir call
  - a subtree of 600+ entries is fully indexed, none dropped
  - the existing depth=1 partition (`discover_files`, the #93 decision) is
    untouched by adding the second, recursive call
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
    spec = importlib.util.spec_from_file_location("inbox_triage_t51", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t51"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


class _FakeClient:
    """Minimal fake covering every Kado method discover() may call.

    depth1_items and recursive_items are independently configurable so tests
    can distinguish the existing depth=1 partition call from the new
    recursive call. recursive_error, when set, is raised ONLY on the
    depth=None (recursive) call — the depth=1 call always succeeds, proving
    a recursive-call failure cannot take the existing partition down with it.
    """

    def __init__(self, depth1_items=None, recursive_items=None, recursive_error=None):
        self.calls: list[tuple[str, dict]] = []
        self._depth1_items = depth1_items or []
        self._recursive_items = (
            recursive_items if recursive_items is not None else list(self._depth1_items)
        )
        self._recursive_error = recursive_error

    def list_dir(self, path, *, depth=None, limit=500):
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        if depth is None:
            if self._recursive_error is not None:
                raise self._recursive_error
            return self._recursive_items
        return self._depth1_items

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


def _list_dir_calls(client) -> list[dict]:
    return [args for name, args in client.calls if name == "list_dir"]


# ---------------------------------------------------------------------------
# Constant cost (CON-4 / business rule 9)
# ---------------------------------------------------------------------------

def test_recursive_listing_requested_exactly_once_per_run(tmp_path):
    mod = _load_module()
    client = _FakeClient(depth1_items=[_listdir_item(INBOX_PATH + "note.md")])

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    recursive_calls = [c for c in _list_dir_calls(client) if c["depth"] is None]
    assert len(recursive_calls) == 1, (
        f"expected exactly 1 recursive list_dir call, got {len(recursive_calls)}: "
        f"{_list_dir_calls(client)}"
    )


def test_recursive_listing_count_independent_of_note_count(tmp_path):
    """The defining CON-4 guard: 1 note and 20 notes issue the SAME number of
    recursive list_dir calls (one)."""
    mod = _load_module()

    def _run(n_notes: int, out: Path) -> int:
        items = [_listdir_item(f"{INBOX_PATH}note-{i}.md") for i in range(n_notes)]
        client = _FakeClient(depth1_items=items)
        mod.discover(client, INBOX_PATH, output_dir=str(out))
        return len([c for c in _list_dir_calls(client) if c["depth"] is None])

    one_note_calls = _run(1, tmp_path / "one")
    twenty_note_calls = _run(20, tmp_path / "twenty")
    assert one_note_calls == 1
    assert twenty_note_calls == 1
    assert one_note_calls == twenty_note_calls


def test_recursive_call_targets_inbox_path_not_vault_root(tmp_path):
    """Business rule 3 — only inbox paths can be resolved. Guards against a
    future `client.list_dir()` call that defaults to the vault root."""
    mod = _load_module()
    client = _FakeClient(depth1_items=[])

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    recursive_calls = [c for c in _list_dir_calls(client) if c["depth"] is None]
    assert len(recursive_calls) == 1
    assert recursive_calls[0]["path"] == INBOX_PATH


# ---------------------------------------------------------------------------
# Fail open (PRD business rule 10)
# ---------------------------------------------------------------------------

def test_kado_error_on_recursive_call_yields_empty_index(tmp_path):
    from lib.kado_client import KadoError

    mod = _load_module()
    client = _FakeClient(
        depth1_items=[_listdir_item(INBOX_PATH + "note.md")],
        recursive_error=KadoError("recursive listDir unavailable"),
    )

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert state.attachment_index == {}


def test_kado_error_on_recursive_call_does_not_abort_the_run(tmp_path):
    """The run continues past the failure — no exception escapes, and the
    depth=1 partition (which happens first) is completely unaffected."""
    from lib.kado_client import KadoError

    mod = _load_module()
    client = _FakeClient(
        depth1_items=[_listdir_item(INBOX_PATH + "note.md")],
        recursive_error=KadoError("recursive listDir unavailable"),
    )

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    # No exception escaped discover() (implicit — reaching this line proves
    # it), AND the run produced normal, non-degraded triage output.
    assert [f["path"] for f in state.md_files] == [INBOX_PATH + "note.md"]
    assert state.attachment_index == {}


# ---------------------------------------------------------------------------
# Index construction + persistence for downstream resolution
# ---------------------------------------------------------------------------

def test_index_is_built_from_the_recursive_listing(tmp_path):
    mod = _load_module()
    items = [
        _listdir_item(INBOX_PATH + "Places/Dresden.md"),
        _listdir_item(INBOX_PATH + "Images/karte.jpg"),
        _listdir_item(INBOX_PATH + "Scans/karte.jpg"),
        _listdir_item(INBOX_PATH + "Places", "folder"),
    ]
    client = _FakeClient(depth1_items=[], recursive_items=items)

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert state.attachment_index["Dresden.md"] == [INBOX_PATH + "Places/Dresden.md"]
    assert set(state.attachment_index["karte.jpg"]) == {
        INBOX_PATH + "Images/karte.jpg", INBOX_PATH + "Scans/karte.jpg",
    }
    # Folder entries never enter the index.
    assert "Places" not in state.attachment_index


def test_index_is_written_for_downstream_resolution(tmp_path):
    """Persisted as a sibling artifact, not folded into the schema-locked
    routing-plan.json (additionalProperties:false) — a later, separate
    process (the resolution step, spec 031 Phase 5 strand B) reads this file
    rather than making its own recursive listDir call."""
    mod = _load_module()
    items = [_listdir_item(INBOX_PATH + "Images/karte.jpg")]
    client = _FakeClient(depth1_items=[], recursive_items=items)

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    index_path = tmp_path / "attachment-index.json"
    assert index_path.exists(), "attachment-index.json must be written to output_dir"
    on_disk = json.loads(index_path.read_text(encoding="utf-8"))
    assert on_disk["karte.jpg"] == [INBOX_PATH + "Images/karte.jpg"]


# ---------------------------------------------------------------------------
# Pagination / scale (kado_client.py:597-617 assembles pages transparently;
# this proves OUR indexing code handles the fully-assembled result without
# dropping anything)
# ---------------------------------------------------------------------------

def test_large_subtree_is_fully_indexed(tmp_path):
    mod = _load_module()
    n = 600
    items = [_listdir_item(f"{INBOX_PATH}Images/photo-{i}.jpg") for i in range(n)]
    client = _FakeClient(depth1_items=[], recursive_items=items)

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert len(state.attachment_index) == n
    assert state.attachment_index["photo-0.jpg"] == [INBOX_PATH + "Images/photo-0.jpg"]
    assert state.attachment_index[f"photo-{n - 1}.jpg"] == [
        INBOX_PATH + f"Images/photo-{n - 1}.jpg"
    ]


# ---------------------------------------------------------------------------
# #93 partition regression guard — the existing depth=1 call is untouched
# ---------------------------------------------------------------------------

def test_93_partition_unchanged_by_the_new_recursive_call(tmp_path):
    """A .png at the inbox root is still not partitioned as an item (#93),
    even though the SAME recursive call now also sees it and indexes it as
    an attachment candidate — two independent concerns over the same file."""
    mod = _load_module()
    items = [
        _listdir_item(INBOX_PATH + "note.md"),
        _listdir_item(INBOX_PATH + "photo.png"),
    ]
    client = _FakeClient(depth1_items=items, recursive_items=items)

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    all_partitioned = {f["path"] for f in state.md_files} | {
        f["path"] for f in state.audio_files
    }
    assert INBOX_PATH + "photo.png" not in all_partitioned
    assert INBOX_PATH + "note.md" in {f["path"] for f in state.md_files}
    # The attachment index, meanwhile, DOES see the .png — the two mechanisms
    # are independent (index build must not feed back into partitioning).
    assert "photo.png" in state.attachment_index
