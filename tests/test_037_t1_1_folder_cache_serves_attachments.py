#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t1_1_folder_cache_serves_attachments.py — spec 037 T1.1.

`_vault_folder_notes` (spec 034 T5.2) caches one `list_dir(location, depth=1)`
per destination folder and derives a `.md`-only `{destination: path}` map from
it. Spec 037 needs the same cache to answer an attachment lookup too. This
file pins the generalised, module-level replacement: `_VaultFolderLookup`.

FALSIFICATION — the mutation that must turn `test_a_folder_primed_by_notes_
serves_the_attachment_caller_from_one_listing` red: cache the CALLER-DERIVED
map (keyed on folder) instead of the raw `list_dir` listing. Under that
mutation, `notes(FOLDER)` populates the folder-keyed cache with a `.md`-only
dict; `assets(FOLDER)` then reuses that same cached dict — built by and for
the note predicate — and finds nothing, silently: no exception, no second
`list_dir` call to notice. Demonstrated live in a disposable git worktree
(see the T1.1 report): also red under that mutation are
`test_the_attachment_caller_first_also_serves_the_note_caller_from_one_listing`
and `test_a_name_differing_only_in_case_is_found` (both call two callers on
one folder, same trap); `test_the_note_path_matches_the_pre_change_hardcoded_
body` and `test_the_asset_path_ignores_md_entries` stay green under that same
mutation, because each of them exercises only one caller against a fresh
folder and so never observes the wrong branch.

CON-7: fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_reducer():
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer_t037_t1_1", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t037_t1_1"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()

FOLDER = "100 Inbox/Places/"


class FakeKado:
    """`list_dir` over a fixed set of entries.

    No `call_count` attribute, matching spec 034 T5.2's own `FakeKado` — so
    `observed_call_count` returns `None` and the generalised helper's
    per-cache-miss fallback (`+= 1`) is what these tests exercise.
    """

    def __init__(self, entries: list[dict]):
        self.entries = entries
        self.probed: list[str] = []

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500) -> list:
        self.probed.append(path)
        return list(self.entries)


ENTRIES = [
    {"path": f"{FOLDER}Dresden.md", "type": "file", "modified": 1, "size": 1},
    {"path": f"{FOLDER}scan.pdf", "type": "file", "modified": 1, "size": 1},
    # Not a file — must be ignored by both callers, exactly as the
    # pre-generalisation body ignored it.
    {"path": f"{FOLDER}Subfolder", "type": "folder", "modified": 1, "size": 0},
]


def _pre_change_notes(entries: list[dict], folder: str) -> dict[str, str]:
    """The exact body of the pre-generalisation `_vault_folder_notes`
    (`suggestions-reducer.py` @ 039b8e4, lines 2013-2020) — the concrete
    anchor for "the note path is unchanged", reproduced rather than asserted.
    """
    found: dict[str, str] = {}
    for entry in entries:
        path = entry.get("path") or ""
        name = path.rsplit("/", 1)[-1]
        if entry.get("type") != "file" or not name.lower().endswith(".md"):
            continue
        found[REDUCER._dest_join(folder, name[:-3]).casefold()] = path
    return found


# ---------------------------------------------------------------------------
# 1. The cache-reuse sequence — the test, not a detail (see module docstring)
# ---------------------------------------------------------------------------

def test_a_folder_primed_by_notes_serves_the_attachment_caller_from_one_listing():
    kado = FakeKado(ENTRIES)
    lookup = REDUCER._VaultFolderLookup(kado)

    # Prime the folder through the NOTE caller first — its map holds only
    # the .md entry.
    notes = lookup.notes(FOLDER)
    assert notes == {REDUCER._dest_join(FOLDER, "Dresden").casefold(): f"{FOLDER}Dresden.md"}

    # The SAME folder, looked up through the ATTACHMENT caller.
    assets = lookup.assets(FOLDER)
    assert assets == {
        REDUCER._asset_dest_join(FOLDER, "scan.pdf").casefold(): f"{FOLDER}scan.pdf"
    }, "the attachment caller found nothing — served from a .md-only cached map"

    assert kado.probed == [FOLDER], "more than one list_dir call for one folder"
    assert lookup.folder_listing_calls == 1


def test_the_attachment_caller_first_also_serves_the_note_caller_from_one_listing():
    """Order independence: the sequence above is not order-dependent luck."""
    kado = FakeKado(ENTRIES)
    lookup = REDUCER._VaultFolderLookup(kado)

    assets = lookup.assets(FOLDER)
    assert assets == {
        REDUCER._asset_dest_join(FOLDER, "scan.pdf").casefold(): f"{FOLDER}scan.pdf"
    }

    notes = lookup.notes(FOLDER)
    assert notes == {REDUCER._dest_join(FOLDER, "Dresden").casefold(): f"{FOLDER}Dresden.md"}

    assert kado.probed == [FOLDER]
    assert lookup.folder_listing_calls == 1


# ---------------------------------------------------------------------------
# 2. A name differing only in case is found
# ---------------------------------------------------------------------------

def test_a_name_differing_only_in_case_is_found():
    kado = FakeKado([
        {"path": f"{FOLDER}DRESDEN.md", "type": "file", "modified": 1, "size": 1},
        {"path": f"{FOLDER}SCAN.PDF", "type": "file", "modified": 1, "size": 1},
    ])
    lookup = REDUCER._VaultFolderLookup(kado)

    assert REDUCER._dest_join(FOLDER, "dresden").casefold() in lookup.notes(FOLDER)
    assert REDUCER._asset_dest_join(FOLDER, "scan.pdf").casefold() in lookup.assets(FOLDER)


# ---------------------------------------------------------------------------
# 3. The note path, unchanged — against a concrete anchor
# ---------------------------------------------------------------------------

def test_the_note_path_matches_the_pre_change_hardcoded_body():
    kado = FakeKado(ENTRIES)
    lookup = REDUCER._VaultFolderLookup(kado)

    assert lookup.notes(FOLDER) == _pre_change_notes(ENTRIES, FOLDER)


def test_the_asset_path_ignores_md_entries():
    kado = FakeKado(ENTRIES)
    lookup = REDUCER._VaultFolderLookup(kado)

    assets = lookup.assets(FOLDER)
    assert f"{FOLDER}Dresden.md" not in assets.values()
    assert list(assets.values()) == [f"{FOLDER}scan.pdf"]
