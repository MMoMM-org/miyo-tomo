#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t1_5_one_entry_one_file.py — spec 037 T1.5.

`detect_attachment_conflicts` (T1.2) grouped conflict entries by the
case-folded DESTINATION. Two DIFFERENT inbox attachments sharing a basename
— `100 Inbox/A/karte.png` and `100 Inbox/B/karte.png` — compute the
identical destination through `_asset_dest_join` (asset folder + source
basename), and spec 034 shipped recursive inbox discovery, so this is
reachable. Destination-keyed dedup folded both into ONE entry: `source` kept
whichever path was seen first, and `owner_source_items` accumulated the
owners of both. Harmless for detection (the destination genuinely is
occupied) but not downstream: Phase 3 applies a rename with an embed
rewrite, so the second file's owning note would be told its embed was
retargeted to a file it never owned — a note the owner never approved gets
modified. This file pins the fix: grouping moved to the exact SOURCE path;
occupancy stays decided on the case-folded destination.

  1. Two different sources sharing a basename yield TWO entries, each naming
     only its own owners, both carrying the same `destination`
     `[ref: PRD/F2-AC1]`.
  2. One attachment embedded by three notes still yields ONE entry with
     three owners `[ref: PRD/F2-AC3]` — ALREADY TRUE of shipped code (both
     the old and new key agree when the source path is literally the same),
     so this is a regression pin against a wrong redesign the key change
     newly makes possible, not evidence the owner-mixing defect is fixed
     (bullets 1 and 3 carry that).
  3. Occupancy stays decided case-folded on the DESTINATION while grouping
     is exact on the SOURCE: two sources whose full paths differ only in
     case both collide with the one vault file and still yield two entries.
  4. The cost bound is restated, not silently broken: two sources colliding
     on one destination read that destination TWICE — the exact count is
     asserted. This is a real, deliberate increase over the pre-T1.5 bound.
     A third test pins the same bound at N=3 (six reads, three per-source
     reads of the shared destination) so the bound is proven to scale with
     N, not just hold at N=2.
  5. An entry's field set is exactly `source`, `destination`, `same_file`,
     `owner_source_items` — no grouping key leaks onto it.
  6. Entry order follows first occurrence in the owners list, pinned against
     a fixture that interleaves two independent destination collisions with
     a two-source split — the shape Phase 2's T2.1 renders straight into
     document order.
  7. A zero-conflict run still emits no `attachment_conflicts` key at all —
     regression pin on T1.2's settled decision (absent, not `[]`).

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
        "suggestions_reducer_t037_t1_5", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t037_t1_5"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()

from lib.item_key import to_filename  # noqa: E402

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"  # DEFAULT_ASSET_FOLDER
ITEM_KEY_A = "100 Inbox/A/note-a.md"
ITEM_KEY_B = "100 Inbox/B/note-b.md"
ITEM_KEY_C = "100 Inbox/C/note-c.md"

SOURCE_A = "100 Inbox/A/karte.png"
SOURCE_B = "100 Inbox/B/karte.png"  # different folder, same basename as SOURCE_A
DEST_SHARED = f"{ASSET_FOLDER}karte.png"


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
    call order, and returns canned bytes per path. Same shape as spec 037
    T1.3's own `RecordingReader`."""

    def __init__(self, content: dict[str, bytes] | None = None):
        self.content = content or {}
        self.calls: list[str] = []

    def __call__(self, path: str) -> bytes:
        self.calls.append(path)
        return self.content.get(path, b"")


# ---------------------------------------------------------------------------
# 1. Two different sources sharing a basename yield TWO entries (F2-AC1)
# ---------------------------------------------------------------------------

def test_two_different_sources_sharing_a_basename_yield_two_entries():
    """Mutation: restore the case-folded DESTINATION as the grouping key —
    both sources compute `DEST_SHARED`, so they fold into ONE entry: the
    first-seen source (`SOURCE_A`) is kept, and `owner_source_items`
    accumulates BOTH owners — silently attributing `ITEM_KEY_B`'s ownership
    to `SOURCE_A`, the exact defect this task exists to remove."""
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([SOURCE_A])),
            (ITEM_KEY_B, _owner_actions([SOURCE_B])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"),
    )
    assert len(result) == 2, f"two different sources must yield two entries: {result}"
    by_source = {entry["source"]: entry for entry in result}
    assert set(by_source) == {SOURCE_A, SOURCE_B}
    assert by_source[SOURCE_A]["destination"] == DEST_SHARED
    assert by_source[SOURCE_B]["destination"] == DEST_SHARED
    assert by_source[SOURCE_A]["owner_source_items"] == [ITEM_KEY_A], (
        "SOURCE_A's entry must name only its own owner"
    )
    assert by_source[SOURCE_B]["owner_source_items"] == [ITEM_KEY_B], (
        "SOURCE_B's entry must name only its own owner, never ITEM_KEY_A"
    )


# ---------------------------------------------------------------------------
# 2. One attachment, three owners, still ONE entry (F2-AC3) — regression pin
# ---------------------------------------------------------------------------

def test_one_attachment_three_owners_still_one_entry():
    """ALREADY TRUE of shipped code: the old (destination) key and the new
    (source) key agree whenever the source path is literally the same
    string, so this fixture passed before T1.5 touched anything. It is NOT
    evidence the owner-mixing defect is fixed — bullets 1 and 3 carry that.
    Kept as a regression pin against a plausible wrong redesign: grouping by
    `(source, item_key)` instead of `source` alone. Mutation: make that
    change — three entries with one owner each, breaking the criterion the
    destination key was originally chosen to satisfy."""
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([SOURCE_A])),
            (ITEM_KEY_B, _owner_actions([SOURCE_A])),
            (ITEM_KEY_C, _owner_actions([SOURCE_A])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"),
    )
    assert len(result) == 1, f"one shared source, three owners, must be ONE entry: {result}"
    assert sorted(result[0]["owner_source_items"]) == [ITEM_KEY_A, ITEM_KEY_B, ITEM_KEY_C]


# ---------------------------------------------------------------------------
# 3. Occupancy is case-folded on the DESTINATION; grouping is exact on the
#    SOURCE.
# ---------------------------------------------------------------------------

def test_occupancy_stays_case_folded_while_grouping_is_exact_on_source():
    """Same folder, basenames differing only in case: `karte.png` vs
    `KARTE.PNG`. Both must still be recognised as occupying the one vault
    file (occupancy stays case-folded), and must still yield two entries
    (grouping stays exact). Mutation: casefold the SOURCE for grouping — the
    two paths become identical once folded, they merge back into one entry,
    and the defect returns in a narrower, case-only form."""
    source_lower = "100 Inbox/A/karte.png"
    source_upper = "100 Inbox/A/KARTE.PNG"
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([source_lower])),
            (ITEM_KEY_B, _owner_actions([source_upper])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"),
    )
    assert len(result) == 2, (
        f"case-differing sources colliding with the same vault file must "
        f"still yield two entries: {result}"
    )
    assert {entry["source"] for entry in result} == {source_lower, source_upper}


# ---------------------------------------------------------------------------
# 4. Cost bound restated: two sources colliding on one destination read it
#    TWICE (SDD/Cost, amended).
# ---------------------------------------------------------------------------

def test_two_sources_colliding_on_one_destination_read_it_twice():
    """Mutation: compute `same_file` once per DESTINATION and reuse it
    across the entries that share it (a destination-side cache) — the read
    count would drop from 4 to 3, and the two different sources would be
    handed one shared verdict instead of each getting its own comparison."""
    reader = RecordingReader({
        SOURCE_A: b"source A bytes",
        SOURCE_B: b"source B bytes",
        DEST_SHARED: b"vault bytes",
    })
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([SOURCE_A])),
            (ITEM_KEY_B, _owner_actions([SOURCE_B])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"), reader,
    )
    assert len(result) == 2
    assert len(reader.calls) == 4, reader.calls
    assert reader.calls.count(DEST_SHARED) == 2, (
        f"the shared destination must be read once per colliding source: {reader.calls}"
    )


def test_three_sources_colliding_on_one_destination_read_it_three_times():
    """N=3, not N=2 (SDD/Cost, amended again): the two-source case above
    could not distinguish "reads scale with N" from "reads are always 2" —
    a third distinct source colliding on the same destination is what
    actually proves the bound is 2N. Mutation: reuse one `same_file`
    verdict across entries sharing a destination — the count drops to 2
    and three different files are handed one verdict."""
    source_c = "100 Inbox/C/karte.png"
    reader = RecordingReader({
        SOURCE_A: b"source A bytes",
        SOURCE_B: b"source B bytes",
        source_c: b"source C bytes",
        DEST_SHARED: b"vault bytes",
    })
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([SOURCE_A])),
            (ITEM_KEY_B, _owner_actions([SOURCE_B])),
            (ITEM_KEY_C, _owner_actions([source_c])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"), reader,
    )
    assert len(result) == 3
    assert len(reader.calls) == 6, reader.calls
    assert reader.calls.count(DEST_SHARED) == 3, (
        f"the shared destination must be read once per colliding source: {reader.calls}"
    )


# ---------------------------------------------------------------------------
# 5. An entry's field set is exactly the four the schema requires.
# ---------------------------------------------------------------------------

def test_entry_field_set_is_exactly_the_schema_four():
    """Mutation: leave the grouping key (`dest_key`, or a new source key) on
    the entry dict for convenience — every other T1.5 assertion still
    passes; only this one, and later `additionalProperties: false` in the
    schema, catch it."""
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([SOURCE_A])),
            (ITEM_KEY_B, _owner_actions([SOURCE_B])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"),
    )
    assert len(result) == 2
    for entry in result:
        assert set(entry.keys()) == {
            "source", "destination", "same_file", "owner_source_items",
        }, entry


# ---------------------------------------------------------------------------
# 6. Entry order follows first occurrence in the owners list.
# ---------------------------------------------------------------------------

def test_entry_order_follows_first_occurrence():
    """Two independent destination collisions (`einzel1.png`, `einzel2.png`)
    interleaved with a two-source split (`foto.png`, embedded by two
    different sources under the same item). Mutation: sort the returned
    list by case-folded destination before returning it — Phase 2's T2.1
    renders `attachment_conflicts[]` straight into document order, so an
    ordering slip here becomes an unstated contract there.

    Measured, not assumed: the mutation this docstring previously named —
    "build the entries by iterating a grouping dict at the end instead of
    appending at first occurrence in the owners list" — was applied by hand
    in a disposable copy and left this test GREEN (8 passed). Python dict
    insertion order already equals first-occurrence order here (the
    grouping dict is only ever appended to, never reordered), so swapping
    the append-based build for `list(by_source.values())` is observationally
    identical to the shipped code — it does not exercise the property this
    test claims to pin. The sort-based mutation above was verified in the
    same way: it turns exactly this test red (1 failed, 7 passed) and
    leaves every other test in this file green."""
    source_d1 = "100 Inbox/X/einzel1.png"
    source_d2_a = "100 Inbox/Y/foto.png"
    source_d2_b = "100 Inbox/Z/foto.png"
    source_d3 = "100 Inbox/W/einzel2.png"

    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([source_d1])),
            (ITEM_KEY_B, _owner_actions([source_d2_a, source_d2_b])),
            (ITEM_KEY_C, _owner_actions([source_d3])),
        ],
        ASSET_FOLDER,
        lambda folder: _occupied("einzel1.png", "foto.png", "einzel2.png"),
    )
    assert [entry["source"] for entry in result] == [
        source_d1, source_d2_a, source_d2_b, source_d3,
    ], result


# ---------------------------------------------------------------------------
# 7. A zero-conflict run still emits no `attachment_conflicts` key at all —
#    regression pin on T1.2's settled decision, exercised through main().
# ---------------------------------------------------------------------------

class FakeKado:
    """`list_dir` over a fixed `occupied` set. Same shape as spec 037 T1.2's
    own `FakeKado`."""

    def __init__(self, occupied: set[str] | None = None):
        self.occupied = occupied or set()

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500) -> list:
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]


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
    """Drives the real reducer in-process, same shape as T1.2/T1.3's harness."""
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


def test_zero_conflict_run_still_emits_no_attachment_conflicts_key(tmp_path):
    """Mutation: emit an unconditional `attachment_conflicts: []` — the key
    would be present with an empty list instead of absent."""
    item_key = "100 Inbox/Scans/free.md"
    source = "100 Inbox/Scans/free.png"
    doc = _reduce(
        tmp_path, item_key, _atomic_result(item_key, source, "Free"),
        "t037-t1-5-zero-conflict",
        {"attachments": [source], "unresolved_embeds": []},
        FakeKado(occupied=set()),
    )
    assert "attachment_conflicts" not in doc
