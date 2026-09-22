#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t1_4_folder_occupied_destination.py — spec 037 T1.4.

T1.3's review found `requirements.md` Edge Case Scenario 7 unmet: "The
destination is occupied by a folder -> Expected: conflict, rename remains
the sensible default." `_VaultFolderLookup._map` (T1.1) drops every listing
entry whose `type` is not `"file"` before either `notes()` or `assets()`
sees it, so a folder holding an attachment's destination name was invisible
to `detect_attachment_conflicts` — no conflict at all, weaker than the
SDD's documented fallback. The owner decided the code gives way, not the
PRD. This file pins the fix: `_VaultFolderLookup.occupied_by_folder()`, a
new sibling to `notes()`/`assets()` (additive — neither of those changes
signature or result), and `detect_attachment_conflicts`'s new
`folder_listing` parameter, which sets `same_file: false` for a
folder-occupied destination from `entry.get("type")` alone, never a read.

FALSIFICATION — named per test in its own docstring/inline comment.

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
        "suggestions_reducer_t037_t1_4", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t037_t1_4"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"  # DEFAULT_ASSET_FOLDER
ITEM_KEY_A = "100 Inbox/A/note-a.md"
ITEM_KEY_B = "100 Inbox/B/note-b.md"
SOURCE_A = "100 Inbox/A/karte.png"
SOURCE_B = "100 Inbox/B/foto.png"
DEST_A = f"{ASSET_FOLDER}karte.png"
DEST_B = f"{ASSET_FOLDER}foto.png"


def _owner_actions(attachments: list[str], *, suppressed: bool = False) -> list[dict]:
    return [{
        "kind": "create_atomic_note",
        "suppressed": suppressed,
        "attachments": attachments,
    }]


class FakeKado:
    """`list_dir` over a fixed set of entries — same shape as spec 037
    T1.1's own `FakeKado`. No `call_count` attribute, so `observed_call_count`
    returns `None` and the `+= 1` cache-miss fallback is what runs.
    """

    def __init__(self, entries: list[dict]):
        self.entries = entries
        self.probed: list[str] = []

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500) -> list:
        self.probed.append(path)
        return list(self.entries)


class RaisingRecorder:
    """A `content_reader` stand-in that records every path it is asked to
    read, then always raises — a folder path is not readable as bytes.
    Used to prove the folder verdict is decided from `entry.get("type")`
    alone: if `detect_attachment_conflicts` ever dispatched a folder
    destination through `_same_file`, this reader's `calls` would be
    non-empty even though the run's OUTPUT could still look right (see the
    module-level case 2 test below for why the read count is what exposes
    the mutation, not the value)."""

    def __init__(self):
        self.calls: list[str] = []

    def __call__(self, path: str) -> bytes:
        self.calls.append(path)
        raise RuntimeError(f"folders are not readable as files: {path}")


class RecordingReader:
    """A `content_reader` that records every path it is asked to read, in
    call order, and returns canned bytes — or raises — per path. Same shape
    as spec 037 T1.3's own `RecordingReader`."""

    def __init__(self, content: dict[str, bytes] | None = None, raise_for: set | None = None):
        self.content = content or {}
        self.raise_for = raise_for or set()
        self.calls: list[str] = []

    def __call__(self, path: str) -> bytes:
        self.calls.append(path)
        if path in self.raise_for:
            raise RuntimeError(f"simulated read failure: {path}")
        return self.content.get(path, b"")


# ---------------------------------------------------------------------------
# 1 + 2. A folder occupying the destination is one conflict, same_file:
#    false, and costs ZERO content reads — asserted on the SAME fixture and
#    entry, not as two separate tests, so a call-count-only assertion cannot
#    pass by accident on an implementation that never inspects same_file.
# ---------------------------------------------------------------------------

def test_folder_occupied_destination_is_one_conflict_with_zero_reads():
    """[ref: PRD/Edge Case Scenario 7] [ref: SDD/Error Handling]

    Mutation A (no conflict at all): restore the unconditional
    `entry.get("type") != "file"` drop with no `occupied_by_folder`
    counterpart consulted by `detect_attachment_conflicts` — the folder
    entry never surfaces as occupied, `dest_key not in vault_assets` stays
    true, and `result == []`. This is the pre-T1.4 shipped behaviour; the
    `assert len(result) == 1` below turns red under it.

    Mutation B (right shape, wrong source of truth): decide the verdict by
    calling `content_reader` for the folder destination and catching any
    exception as `false`, instead of reading `entry.get("type")` directly.
    A folder cannot be byte-identical to a file, so `same_file` still comes
    back `False` — every VALUE assertion below stays green under this
    mutation. Only `reader.calls == []` catches it: the mutated code must
    call `content_reader` at least once (for the source, or both sides) to
    reach its except-branch, so `reader.calls` would be non-empty.
    """
    kado = FakeKado([
        {"path": DEST_A, "type": "folder", "modified": 1, "size": 0},
    ])
    lookup = REDUCER._VaultFolderLookup(kado)
    reader = RaisingRecorder()

    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A]))],
        ASSET_FOLDER, lookup.assets, reader, lookup.occupied_by_folder,
    )

    assert result == [{
        "source": SOURCE_A, "destination": DEST_A,
        "same_file": False, "owner_source_items": [ITEM_KEY_A],
    }]
    assert reader.calls == [], (
        "the folder verdict must be decided from entry.get('type') alone — "
        "content_reader must never be consulted for it"
    )


# ---------------------------------------------------------------------------
# 3. A folder name differing only in case is still recognised as occupied
#    [ref: PRD/F1-AC4] — mirrors T1.1's case-fold pin for notes().
# ---------------------------------------------------------------------------

def test_folder_name_differing_only_in_case_is_recognised_as_occupied():
    """Mutation: drop `.casefold()` from `occupied_by_folder`'s key (or
    compare raw names) — `KARTE.PNG` (the vault folder) and `karte.png`
    (the computed destination) would then be treated as different keys and
    no conflict would be found; `_map`'s casefold is shared and
    unconditional, so this should follow for free, but this phase pins it
    rather than inferring it from shared code."""
    kado = FakeKado([
        {"path": f"{ASSET_FOLDER}KARTE.PNG", "type": "folder", "modified": 1, "size": 0},
    ])
    lookup = REDUCER._VaultFolderLookup(kado)
    reader = RaisingRecorder()

    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A]))],
        ASSET_FOLDER, lookup.assets, reader, lookup.occupied_by_folder,
    )

    assert len(result) == 1, "a case-differing folder name must still be recognised as occupied"
    assert result[0]["same_file"] is False
    assert reader.calls == []


# ---------------------------------------------------------------------------
# 4. A .md note in the asset folder is still NOT an attachment collision —
#    regression pin on T1.1's decision.
# ---------------------------------------------------------------------------

def test_md_note_in_asset_folder_is_still_not_an_attachment_collision():
    """Mutation: widen the new folder-admitting path to admit every
    non-file entry AND `.md` files (instead of only non-file entries) — a
    note sharing the attachment folder would then look like an attachment
    clash, which `assets()`'s file_predicate has always excluded."""
    md_source = "100 Inbox/A/note.md"
    dest = f"{ASSET_FOLDER}note.md"
    kado = FakeKado([
        {"path": dest, "type": "file", "modified": 1, "size": 1},
    ])
    lookup = REDUCER._VaultFolderLookup(kado)
    reader = RaisingRecorder()

    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([md_source]))],
        ASSET_FOLDER, lookup.assets, reader, lookup.occupied_by_folder,
    )

    assert result == [], "a .md FILE entry must never register as an attachment collision"
    assert reader.calls == []


# ---------------------------------------------------------------------------
# 5. notes() is unaffected: a subfolder in a note destination folder does
#    not become a note clash.
# ---------------------------------------------------------------------------

def test_notes_is_unaffected_by_folder_occupied_detection():
    """Mutation: implement T1.4 by widening `_map`'s shared
    `entry.get("type") != "file"` guard itself (instead of adding the
    separate `occupied_by_folder` method) — that would leak
    folder-admission into `notes()` too, corrupting spec 034 T5.2's
    note-destination-clash proposal for any note sharing a folder's stem.

    **The fixture folder is named `Dresden.md`, and the suffix is
    load-bearing.** `notes()` filters on BOTH the entry type and a
    `.md` extension. A folder named plainly `Dresden` is excluded by the
    extension predicate no matter what the type guard does, so it cannot
    detect the mutation — this test passed under it, measured, before the
    fixture was corrected (2026-09-22, code-quality review of `f1eb257`).
    Only a folder named like a note leaves the type guard as the single
    thing standing between it and `notes()`'s map."""
    folder = "100 Inbox/Places/"
    kado = FakeKado([
        {"path": f"{folder}Dresden.md", "type": "folder", "modified": 1, "size": 0},
    ])
    lookup = REDUCER._VaultFolderLookup(kado)

    assert lookup.notes(folder) == {}, (
        "a folder entry must not appear in notes()'s map — notes() is unchanged by T1.4"
    )


# ---------------------------------------------------------------------------
# 6. Mixed run: one folder-occupied and one file-occupied destination.
# ---------------------------------------------------------------------------

def test_mixed_run_folder_and_file_occupied_destinations():
    """One destination occupied by a folder, another by a file, in one run.

    Mutation: drop the file/folder kind check and send every occupied
    destination through `_same_file` unconditionally. The file entry still
    comes out right (`True`), so only the folder entry exposes it: reading
    `SOURCE_A` (the real incoming file) succeeds, then reading `DEST_A`
    (the vault folder) raises — `_same_file` catches that and returns
    `None`, not `False`, and the read count for this run becomes four
    (both sides of both entries attempted) instead of two (the file entry
    only)."""
    kado = FakeKado([
        {"path": DEST_A, "type": "folder", "modified": 1, "size": 0},
        {"path": DEST_B, "type": "file", "modified": 1, "size": 1},
    ])
    lookup = REDUCER._VaultFolderLookup(kado)
    reader = RecordingReader(
        content={SOURCE_A: b"incoming bytes", SOURCE_B: b"same", DEST_B: b"same"},
        raise_for={DEST_A},
    )

    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A])), (ITEM_KEY_B, _owner_actions([SOURCE_B]))],
        ASSET_FOLDER, lookup.assets, reader, lookup.occupied_by_folder,
    )

    by_dest = {entry["destination"]: entry for entry in result}
    assert set(by_dest) == {DEST_A, DEST_B}
    assert by_dest[DEST_A]["same_file"] is False, "the folder entry's verdict"
    assert by_dest[DEST_B]["same_file"] is True, "the file entry's verdict, unaffected"
    assert reader.calls == [SOURCE_B, DEST_B], (
        f"only the file entry may cost reads — the folder entry must cost none: {reader.calls}"
    )
