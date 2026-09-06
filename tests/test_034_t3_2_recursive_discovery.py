#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t3_2_recursive_discovery.py — XDD 034 T3.2 recursive discovery.

ADR-3: one recursive listing feeds BOTH discovery and the attachment index.
Before this task `discover_files` asked for `depth=1` and `build_attachment_index`
made a second, independent recursive call — so a note in a subfolder was never
an item, and every run paid for two listings.

Two invariants this file pins, because a green suite cannot state them:

  - **Recursion changes WHERE files are found, never WHAT counts as an item.**
    The `#93` partition is by suffix: a `.png` in a subfolder must be classified
    exactly as a root-level `.png` is — an attachment candidate, not an item.
    Asserted for both in the SAME run, so the test states the invariant rather
    than two separate facts; the flat-inbox case supplies the independent
    ground truth that root-level classification is itself still correct.
  - **The listing count is observed, not calculated.** The fake client records
    its own calls and every count here reads that record. `_count_kado_calls`
    is the thing under test elsewhere, so it can never also be the evidence.

ADR-1: an item's key is its vault-relative path, verbatim — subfolder notes
produce keys like `100 Inbox/Places/Dresden.md`, never a bare basename.
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
    spec = importlib.util.spec_from_file_location("inbox_triage_t32", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t32"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _entry(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


class _RecordingClient:
    """Fake Kado client that records every call it receives.

    `list_dir` honours `depth` the way Kado does — `depth=1` returns direct
    children only, `depth=None` returns the whole subtree. A fake that ignored
    `depth` would let a lingering `depth=1` pass unnoticed, which is precisely
    the regression this task exists to remove.
    """

    def __init__(self, subtree: list[dict]):
        self.calls: list[tuple[str, dict]] = []
        self._subtree = subtree

    def _direct_children(self) -> list[dict]:
        prefix = INBOX_PATH
        return [
            item for item in self._subtree
            if "/" not in item["path"][len(prefix):]
        ]

    def list_dir(self, path, *, depth=None, limit=500):
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        if depth == 1:
            return self._direct_children()
        return list(self._subtree)

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        self.calls.append(("list_notes", {"path": path, "fields": fields}))
        return []

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


# A subtree with a root level, one nested level, two nested levels, and a
# four-deep branch — plus a `.png` at the root AND a `.png` in a subfolder,
# so the #93 partition can be compared against itself in a single run.
NESTED_SUBTREE = [
    _entry(INBOX_PATH + "Places", "folder"),
    _entry(INBOX_PATH + "Places/Saxony", "folder"),
    _entry(INBOX_PATH + "A", "folder"),
    _entry(INBOX_PATH + "A/B", "folder"),
    _entry(INBOX_PATH + "A/B/C", "folder"),
    _entry(INBOX_PATH + "root-note.md"),
    _entry(INBOX_PATH + "root-photo.png"),
    _entry(INBOX_PATH + "Places/Dresden.md"),
    _entry(INBOX_PATH + "Places/sub-photo.png"),
    _entry(INBOX_PATH + "Places/Saxony/Meissen.md"),
    _entry(INBOX_PATH + "A/B/C/Deep.md"),
]

FLAT_SUBTREE = [
    _entry(INBOX_PATH + "alpha.md"),
    _entry(INBOX_PATH + "beta.md"),
    _entry(INBOX_PATH + "memo.m4a"),
    _entry(INBOX_PATH + "photo.png"),
    _entry(INBOX_PATH + "sheet.pdf"),
    _entry(INBOX_PATH + "board.canvas"),
]


def _run(mod, subtree, tmp_path) -> tuple[object, _RecordingClient]:
    client = _RecordingClient(subtree)
    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))
    return state, client


def _item_paths(state) -> set[str]:
    """Every file the run partitioned as an item (audio or markdown)."""
    return {f["path"] for f in state.md_files} | {f["path"] for f in state.audio_files}


# ---------------------------------------------------------------------------
# Feature 1 — a subfolder note is an item
# ---------------------------------------------------------------------------

def test_subfolder_note_becomes_an_item(tmp_path):
    """`[ref: PRD/AC Feature 1]` — a note one level down is triaged."""
    mod = _load_module()
    state, _client = _run(mod, NESTED_SUBTREE, tmp_path)

    assert INBOX_PATH + "Places/Dresden.md" in {f["path"] for f in state.md_files}
    # And it reaches the pipeline as a fresh source, not merely the listing.
    assert INBOX_PATH + "Places/Dresden.md" in {f["path"] for f in state.new_sources}


def test_deeply_nested_notes_are_discovered_no_depth_limit(tmp_path):
    """Two levels down, and four — the plan states no depth limit anywhere."""
    mod = _load_module()
    state, _client = _run(mod, NESTED_SUBTREE, tmp_path)

    md_paths = {f["path"] for f in state.md_files}
    assert INBOX_PATH + "Places/Saxony/Meissen.md" in md_paths
    assert INBOX_PATH + "A/B/C/Deep.md" in md_paths
    # Every markdown file in the subtree, at every depth, and nothing else.
    assert md_paths == {
        INBOX_PATH + "root-note.md",
        INBOX_PATH + "Places/Dresden.md",
        INBOX_PATH + "Places/Saxony/Meissen.md",
        INBOX_PATH + "A/B/C/Deep.md",
    }


def test_no_depth_argument_is_sent_on_the_listing(tmp_path):
    """A depth ceiling anywhere in the call path would silently cap discovery."""
    mod = _load_module()
    _state, client = _run(mod, NESTED_SUBTREE, tmp_path)

    list_dir_calls = [args for name, args in client.calls if name == "list_dir"]
    assert all(args["depth"] is None for args in list_dir_calls), list_dir_calls


# ---------------------------------------------------------------------------
# #93 — recursion changes WHERE files are found, not WHAT counts as an item
# ---------------------------------------------------------------------------

def test_subfolder_png_is_classified_exactly_as_a_root_png(tmp_path):
    """The `#93` partition is by suffix. A `.png` in a subfolder must land on
    the same side of it as a root-level `.png`, asserted in ONE run so the
    statement is the invariant, not two coincidentally equal facts."""
    mod = _load_module()
    state, _client = _run(mod, NESTED_SUBTREE, tmp_path)

    items = _item_paths(state)
    root_png_is_item = (INBOX_PATH + "root-photo.png") in items
    sub_png_is_item = (INBOX_PATH + "Places/sub-photo.png") in items

    assert sub_png_is_item == root_png_is_item
    assert root_png_is_item is False  # ...and that shared side is "not an item"

    # Both are still attachment candidates — the index and the partition are
    # two independent readings of the same listing.
    assert "root-photo.png" in state.attachment_index
    assert "sub-photo.png" in state.attachment_index
    assert state.attachment_index["sub-photo.png"] == [
        INBOX_PATH + "Places/sub-photo.png"
    ]


def test_folder_entries_are_never_items(tmp_path):
    """Recursion returns folders too — none of them may be partitioned."""
    mod = _load_module()
    state, _client = _run(mod, NESTED_SUBTREE, tmp_path)

    items = _item_paths(state)
    for folder in (INBOX_PATH + "Places", INBOX_PATH + "A/B/C"):
        assert folder not in items


# ---------------------------------------------------------------------------
# Feature 9 — one listing per run, read off the fake's own record
# ---------------------------------------------------------------------------

def test_exactly_one_listing_call_per_run(tmp_path):
    """`[ref: PRD/AC Feature 9]` — ADR-3's shared listing. Counted from the
    fake client's recorded calls; no hand-derived expectation, and never the
    estimator's own arithmetic."""
    mod = _load_module()
    _state, client = _run(mod, NESTED_SUBTREE, tmp_path)

    list_dir_calls = [args for name, args in client.calls if name == "list_dir"]
    assert len(list_dir_calls) == 1, client.calls
    assert list_dir_calls[0]["path"] == INBOX_PATH


def test_base_calls_are_two(tmp_path):
    """`[ref: PRD/AC Feature 9]` — base calls fall 3 → 2: one listing plus the
    listNotes embed extraction. Observed, in order, from the call record."""
    mod = _load_module()
    _state, client = _run(mod, NESTED_SUBTREE, tmp_path)

    base = [name for name, _args in client.calls if name in ("list_dir", "list_notes")]
    assert base == ["list_dir", "list_notes"], client.calls


def test_one_listing_regardless_of_note_count(tmp_path):
    """The listing is per-run, not per-item — proven across two note counts."""
    mod = _load_module()

    def listings(n: int, out: Path) -> int:
        subtree = [_entry(f"{INBOX_PATH}Deep/n-{i}.md") for i in range(n)]
        _state, client = _run(mod, subtree, out)
        return len([1 for name, _args in client.calls if name == "list_dir"])

    assert listings(1, tmp_path / "one") == listings(25, tmp_path / "many") == 1


# ---------------------------------------------------------------------------
# No regression for the flat inbox — the guarantee for every user with no
# subfolders. Expected lists are stated literally, not derived from the run.
# ---------------------------------------------------------------------------

def test_flat_inbox_yields_the_same_items_as_before(tmp_path):
    mod = _load_module()
    state, _client = _run(mod, FLAT_SUBTREE, tmp_path)

    assert [f["path"] for f in state.md_files] == [
        INBOX_PATH + "alpha.md",
        INBOX_PATH + "beta.md",
    ]
    assert [f["path"] for f in state.audio_files] == [INBOX_PATH + "memo.m4a"]
    assert [f["path"] for f in state.new_sources] == [
        INBOX_PATH + "alpha.md",
        INBOX_PATH + "beta.md",
    ]
    # #93 at the root, unchanged: image, PDF and canvas are not items.
    assert _item_paths(state) == {
        INBOX_PATH + "alpha.md",
        INBOX_PATH + "beta.md",
        INBOX_PATH + "memo.m4a",
    }
    # ...but every file, item or not, is an attachment candidate.
    assert set(state.attachment_index) == {
        "alpha.md", "beta.md", "memo.m4a", "photo.png", "sheet.pdf", "board.canvas",
    }
