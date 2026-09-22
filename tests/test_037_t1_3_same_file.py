#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t1_3_same_file.py — spec 037 T1.3.

`detect_attachment_conflicts` (spec 037 T1.2) already flags an attachment
whose computed vault destination is taken, but the document never said
whether the occupant IS the incoming file or a different one. The
2026-09-15 live pair — two 69-byte PNGs, same size, different pictures — is
why that distinction cannot be a size check: this file pins `same_file`,
the content comparison that decides it, and the `content_reader` parameter
`detect_attachment_conflicts` now takes to make that comparison.

  1. Byte-identical source/destination set `same_file: true`; differing
     content sets `false` `[ref: PRD/S1-AC1]` `[ref: PRD/S1-AC2]`.
  2. Two files of IDENTICAL SIZE and different content set `false` — the
     live 2026-09-15 pair, and the regression a size check would fail
     `[ref: SDD/Complex Logic]`.
  3. A raising read sets `null` for ITS conflict only; a second, unrelated
     conflict in the same run keeps its own computed true/false — not
     null, not omitted `[ref: PRD/S1-AC3]`.
  4. No `content_reader` (no Kado client) still produces the conflict, with
     `same_file: null` — a missing comparison is not a missing conflict.
  5. A destination occupied by a folder is UNREACHABLE through
     `detect_attachment_conflicts` as wired in `main()` today — see
     `test_folder_occupied_destination_never_becomes_a_conflict`'s
     docstring for why the SDD/Error-Handling row for this case cannot be
     exercised as a `same_file` case, and what is pinned instead in its
     place `[ref: SDD/Error Handling]`.
  6. Reads are bounded by COLLISIONS, not attachments: N attachments with K
     colliding call `content_reader` at most 2*K times, never for the N-K
     that do not collide; K=0 performs none `[ref: SDD/Cost]`.
  7. A destination shared by several owning notes is still ONE comparison:
     two notes embedding one attachment cost at most two reads, not one
     per owner `[ref: SDD/Cost]`.
  8. The `main()` wiring itself threads a real `read_file_bytes` through
     end to end (integration-level, complementing T1.2's updated test that
     pins the `getattr` degrade-to-`None` path for a client that lacks it).

FALSIFICATION — named per test in its own docstring/inline comment.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_reducer():
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer_t037_t1_3", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t037_t1_3"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()

from lib.item_key import to_filename  # noqa: E402

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"  # DEFAULT_ASSET_FOLDER
ITEM_KEY_A = "100 Inbox/A/note-a.md"
ITEM_KEY_B = "100 Inbox/B/note-b.md"
SOURCE_A = "100 Inbox/A/karte.png"
SOURCE_B = "100 Inbox/B/foto.png"
SOURCE_FREE = "100 Inbox/C/free.png"
DEST_A = f"{ASSET_FOLDER}karte.png"
DEST_B = f"{ASSET_FOLDER}foto.png"


def _owner_actions(attachments: list[str], *, suppressed: bool = False) -> list[dict]:
    return [{
        "kind": "create_atomic_note",
        "suppressed": suppressed,
        "attachments": attachments,
    }]


def _occupied(*names: str) -> dict:
    return {f"{ASSET_FOLDER}{name}".casefold(): f"{ASSET_FOLDER}{name}" for name in names}


class RecordingReader:
    """A `content_reader` that records every path it is asked to read, in
    call order, and returns canned bytes — or raises — per path."""

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
# 1. Byte-identical vs differing content (S1-AC1 / S1-AC2)
# ---------------------------------------------------------------------------

def test_byte_identical_files_set_same_file_true():
    """Mutation: hard-code `_same_file` to return `False` (or anything other
    than the actual byte comparison) once both reads succeed — this is the
    only test asserting `true`, so it alone catches an always-`False` (or
    always-`None`-when-no-exception) stand-in for the comparison."""
    reader = RecordingReader({SOURCE_A: b"same bytes", DEST_A: b"same bytes"})
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"), reader,
    )
    assert result == [{
        "source": SOURCE_A, "destination": DEST_A,
        "same_file": True, "owner_source_items": [ITEM_KEY_A],
    }]
    assert reader.calls == [SOURCE_A, DEST_A], (
        "source is read before destination — the documented order this "
        "spec relies on for the raising-source-read case below"
    )


def test_differing_content_sets_same_file_false():
    """Different content, different lengths. Mutation: `return True`
    whenever both reads succeed without exception (ignoring content
    entirely) — this test's bytes differ, so that stand-in reads false here
    as true."""
    reader = RecordingReader({SOURCE_A: b"short", DEST_A: b"a longer payload"})
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"), reader,
    )
    assert result[0]["same_file"] is False


# ---------------------------------------------------------------------------
# 2. Equal size, different content — the size-check regression (SDD/Complex
#    Logic). This is the test that actually falsifies a SIZE comparison; see
#    the module docstring's bullet 2 and the implementer's report.
# ---------------------------------------------------------------------------

def test_equal_size_different_content_sets_same_file_false():
    """The 2026-09-15 live pair: two 69-byte PNGs, same size, different
    pictures. Mutation: compare `len(source_bytes) == len(destination_bytes)`
    instead of the bytes themselves — both payloads below are exactly 69
    bytes, so a size comparison reads `true` where content says `false`.
    This is the one test in this file that a size-based `same_file` would
    get WRONG rather than merely under-test."""
    same_size_a = b"\x89PNG-fixture-A-" + bytes(range(54))  # 69 bytes
    same_size_b = b"\x89PNG-fixture-B-" + bytes(range(53, -1, -1))  # 69 bytes
    assert len(same_size_a) == len(same_size_b) == 69
    assert same_size_a != same_size_b
    reader = RecordingReader({SOURCE_A: same_size_a, DEST_A: same_size_b})
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"), reader,
    )
    assert result[0]["same_file"] is False, (
        "content differs despite identical size — a size check would have "
        "said true here, which is exactly the regression this spec exists "
        "to prevent"
    )


# ---------------------------------------------------------------------------
# 3. A raising read sets null for ITS conflict, leaves the others intact
#    (PRD/S1-AC3)
# ---------------------------------------------------------------------------

def test_raising_read_sets_null_for_its_conflict_and_leaves_the_other_intact():
    """Two colliding destinations in one run. `content_reader` raises only
    for `SOURCE_B` (the source side of the SECOND conflict); the first
    conflict's reader calls succeed normally. Mutation: let the exception
    propagate out of `detect_attachment_conflicts` instead of being caught
    per-entry — the whole call would raise and BOTH conflicts would be lost,
    not just conflict B's `same_file`. A single-conflict version of this
    test cannot distinguish "caught the exception" from "aborted the run
    and lost every conflict" `[ref: task T1.3 step 2]`."""
    reader = RecordingReader(
        content={SOURCE_A: b"identical", DEST_A: b"identical"},
        raise_for={SOURCE_B},
    )
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([SOURCE_A])),
            (ITEM_KEY_B, _owner_actions([SOURCE_B])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png", "foto.png"), reader,
    )
    by_dest = {entry["destination"]: entry for entry in result}
    assert set(by_dest) == {DEST_A, DEST_B}, (
        "both conflicts must be present — a caught exception must not "
        "abandon the rest of the run"
    )
    assert by_dest[DEST_A]["same_file"] is True, (
        "the unaffected conflict keeps its own computed verdict"
    )
    assert by_dest[DEST_B]["same_file"] is None, (
        "the conflict whose read raised gets null, not omitted, not false"
    )
    assert "same_file" in by_dest[DEST_B]


# ---------------------------------------------------------------------------
# 4. No content_reader still produces the conflict, with same_file: null
# ---------------------------------------------------------------------------

def test_no_content_reader_produces_the_conflict_with_same_file_null():
    """Mutation: fold `content_reader is None` into the existing
    `asset_listing is None` short-circuit (returning `[]` instead of the
    conflict list) — a missing comparison CAPABILITY must not be treated as
    a missing conflict; the conflict itself is unaffected by whether it can
    be compared."""
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"), None,
    )
    assert result == [{
        "source": SOURCE_A, "destination": DEST_A,
        "same_file": None, "owner_source_items": [ITEM_KEY_A],
    }]


# ---------------------------------------------------------------------------
# 5. A destination occupied by a folder — the row this task cannot honour
# ---------------------------------------------------------------------------

def test_folder_occupied_destination_never_becomes_a_conflict():
    """SDD/Error Handling states a destination occupied by a folder should
    still raise a conflict (with rename remaining the default remedy). It
    cannot, given how `detect_attachment_conflicts` is actually wired in
    `main()`: `_VaultFolderLookup._map` (spec 037 T1.1) filters
    `entry.get("type") != "file"` BEFORE building the {destination: path}
    map this function consults — a folder entry never survives into
    `vault_assets`, so `dest_key not in vault_assets` is true for it and no
    conflict is created at all. There is no exception to catch and no
    message to avoid sniffing: `detect_attachment_conflicts` is never even
    told the name is occupied. Fabricating an `asset_listing` that includes
    a folder entry (something the real `_VaultFolderLookup.assets` never
    produces) would only prove this function's ALREADY-covered raising-read
    behaviour again, under a label ("folder") the function has no way to
    attach meaning to — so this test pins the real cause, through the real
    `_VaultFolderLookup`, instead.

    Mutation: drop the `entry.get("type") != "file"` half of
    `_VaultFolderLookup._map`'s guard — the folder would then appear in
    `vault_assets` and this test would see a (spurious, type-blind) conflict
    where today there is none.
    """
    class FolderOccupiedKado:
        def list_dir(self, path, *, depth=None, limit=500):
            return [
                {"path": DEST_A, "type": "folder", "modified": 0, "size": 0},
            ]

    lookup = REDUCER._VaultFolderLookup(FolderOccupiedKado())
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A]))],
        ASSET_FOLDER, lookup.assets, RecordingReader(),
    )
    assert result == [], (
        "a destination occupied only by a folder is invisible to "
        "detect_attachment_conflicts given the current asset_listing "
        "contract — see this test's docstring"
    )


# ---------------------------------------------------------------------------
# 6. Reads bounded by collisions, not attachments (SDD/Cost)
# ---------------------------------------------------------------------------

def test_reads_bounded_by_collisions_not_attachments():
    """3 attachments, 2 collide (K=2), 1 does not. Mutation: call
    `content_reader` for every attachment regardless of whether its
    destination is occupied (e.g. moving the `_same_file` call above the
    `dest_key not in vault_assets` guard) — `SOURCE_FREE` would then appear
    in `reader.calls`, and the call count would be 6 (2*N) instead of 4
    (2*K)."""
    reader = RecordingReader({
        SOURCE_A: b"a", DEST_A: b"a-vault",
        SOURCE_B: b"b", DEST_B: b"b-vault",
    })
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_A, SOURCE_B, SOURCE_FREE]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.png", "foto.png"), reader,
    )
    assert len(result) == 2
    assert len(reader.calls) == 4, reader.calls
    assert SOURCE_FREE not in reader.calls, (
        "the non-colliding attachment's own path must never be read"
    )


def test_zero_collisions_performs_zero_reads():
    """K=0. Mutation: same as above — any unconditional read attempt would
    show up here as a non-empty `reader.calls` even though nothing
    collided."""
    reader = RecordingReader()
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([SOURCE_FREE]))],
        ASSET_FOLDER, lambda folder: {}, reader,
    )
    assert result == []
    assert reader.calls == []


# ---------------------------------------------------------------------------
# 7. A destination shared by several owning notes is still one comparison
#    (SDD/Cost)
# ---------------------------------------------------------------------------

def test_shared_destination_across_owners_is_one_comparison():
    """Two notes embed the SAME attachment (same destination). Mutation:
    compute `same_file` inside the `if item_key not in
    entry["owner_source_items"]` branch, or anywhere re-entered per owner,
    instead of only at entry-creation time — `reader.calls` would then grow
    with the number of owners instead of staying at 2."""
    reader = RecordingReader({SOURCE_A: b"x", DEST_A: b"x"})
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([SOURCE_A])),
            (ITEM_KEY_B, _owner_actions([SOURCE_A])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"), reader,
    )
    assert len(result) == 1
    assert sorted(result[0]["owner_source_items"]) == [ITEM_KEY_A, ITEM_KEY_B]
    assert len(reader.calls) == 2, (
        f"one comparison for two owners, not one per owner: {reader.calls}"
    )


# ---------------------------------------------------------------------------
# 8. main()'s wiring threads a real read_file_bytes through, end to end
# ---------------------------------------------------------------------------

class FakeKadoWithContent:
    """`list_dir` over a fixed `occupied` set (same shape as T1.2's
    FakeKado), plus `read_file_bytes` over a fixed `{path: bytes}` map —
    unlike T1.2's FakeKado, which deliberately does not implement
    `read_file_bytes` to pin the `getattr`-degrades-to-None path."""

    def __init__(self, occupied: set, content: dict):
        self.occupied = occupied
        self.content = content
        self.read_calls: list[str] = []

    def list_dir(self, path, *, depth=None, limit=500):
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]

    def read_file_bytes(self, path):
        self.read_calls.append(path)
        return self.content[path]


def _atomic_result(item_key: str, source: str, title: str) -> dict:
    return {
        "schema_version": "1",
        "stem": Path(item_key).stem,
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "issues": [],
        "force_atomic": False,
        "actions": [{
            "kind": "create_atomic_note",
            "source_stem": Path(item_key).stem,
            "suggested_title": title,
            "template": "Atomic Note.md",
            "location": "Atlas/202 Notes/",
            "candidate_mocs": [],
            "tags_to_add": [],
            "atomic_note_worthiness": 0.85,
            "classification": None,
            "force_atomic": False,
        }],
    }


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _reduce(work: Path, item_key: str, result: dict, run_id: str,
            resolved_attachments: dict, kado) -> dict:
    """Drives the real reducer in-process, same shape as T1.2's harness."""
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    for status in ("pending", "running", "done"):
        _run([
            sys.executable, str(SCRIPTS_DIR / "state-update.py"),
            "--state", str(state_path),
            "--item-key", item_key,
            "--stem", result["stem"],
            "--path", item_key,
            "--status", status,
            "--run-id", run_id,
        ])
    (items_dir / to_filename(item_key)).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    resolved_path = work / "resolved-attachments.json"
    resolved_path.write_text(
        json.dumps({item_key: resolved_attachments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    doc_path = work / "suggestions-doc.json"
    argv = [
        "suggestions-reducer.py",
        "--state", str(state_path), "--items-dir", str(items_dir),
        "--run-id", run_id, "--profile", "miyo", "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(resolved_path),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1",
    ]

    real_client = REDUCER.KadoClient
    real_argv = sys.argv
    try:
        sys.argv = argv
        REDUCER.KadoClient = lambda *a, **k: kado
        assert REDUCER.main() == 0
    finally:
        REDUCER.KadoClient = real_client
        sys.argv = real_argv

    return json.loads(doc_path.read_text(encoding="utf-8"))


def test_wiring_threads_a_real_read_file_bytes_through_main(tmp_path):
    """Mutation: revert the `main()` wiring to omit the fourth argument (or
    pass `None` unconditionally) — `same_file` would come back `null` even
    though this `FakeKadoWithContent` DOES implement `read_file_bytes` and
    the two payloads below are byte-identical."""
    item_key = "100 Inbox/Scans/karte.md"
    source = "100 Inbox/Scans/karte.png"
    dest = f"{ASSET_FOLDER}karte.png"
    kado = FakeKadoWithContent(
        occupied={dest}, content={source: b"same payload", dest: b"same payload"},
    )
    doc = _reduce(
        tmp_path, item_key, _atomic_result(item_key, source, "Karte"),
        "t037-t1-3-wiring", {"attachments": [source], "unresolved_embeds": []},
        kado,
    )
    assert doc.get("attachment_conflicts") == [{
        "source": source, "destination": dest,
        "same_file": True, "owner_source_items": [item_key],
    }]
    assert kado.read_calls == [source, dest]
