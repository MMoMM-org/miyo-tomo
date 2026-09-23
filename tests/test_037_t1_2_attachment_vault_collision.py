#!/usr/bin/env python3
# version: 0.3.0
"""test_037_t1_2_attachment_vault_collision.py — spec 037 T1.2.

An attachment's computed destination (`_asset_dest_join` — the same helper
Pass 2's `_build_move_asset_actions` uses) can already be occupied in the
vault. Until this task nothing checked: the collision travelled unmentioned
to Hashi, which refused it at apply time (PRD, 2026-09-15 live run). This
file pins `detect_attachment_conflicts` — the Pass-1 detector — and its wiring
into `main()` as `attachment_conflicts[]` in the suggestions-doc.

  1. A free destination leaves the emitted document unchanged, anchored
     against `tests/fixtures/037-t1-2/pre-change-free-doc.json` — captured by
     running the reducer AT `16f64de` (the commit before this task) in a
     disposable git worktree, against the exact same fixture input used here
     `[ref: PRD/F1-AC1]`.
  2. An occupied destination produces one conflict naming source, destination
     and every owning note `[ref: PRD/F1-AC2]`.
  3. Dedup is by DESTINATION, not by path: one attachment embedded by three
     notes yields ONE conflict carrying three owners.
  4. No Kado client, and a listing that raises, each produce no conflicts and
     no error `[ref: PRD/F1-AC5]` — regression pins, both properties already
     true of shipped code (`_vault_folder_lookup` is `None` without a client;
     `_VaultFolderLookup._entries` fails open, T1.1). These pin that wiring
     `.assets()` into the NEW attachment path did not reintroduce either
     failure.

FALSIFICATION — named per test, and demonstrated live (see the T1.2 report
for the disposable-mutation output) for the two that matter:

  - `test_dedup_is_by_destination_not_by_path`: red under "accumulate per
    (item_key, path) instead of per case-folded destination" — the plausible
    wrong implementation that emits three one-owner conflicts instead of one
    three-owner conflict.
  - `test_no_kado_client_produces_no_conflicts_and_no_error`: red under
    "call `asset_listing(asset_folder)` unconditionally, without the `is
    None` guard" — `asset_listing` is `None` when there is no Kado client, so
    an unconditional call raises `TypeError: 'NoneType' object is not
    callable`.
  - `test_a_listing_that_raises_produces_no_conflicts_and_no_error`: red
    under "let `_VaultFolderLookup._entries` propagate instead of returning
    `[]`" (a T1.1-era mutation, exercised here THROUGH the new attachment
    path rather than restated as T1.1 coverage).
  - `test_an_occupied_destination_names_source_destination_and_owner`: red
    under "never call `_asset_dest_join`" (destination stays unset) or under
    "check `path in vault_assets` instead of `_asset_dest_join(...).casefold()
    in vault_assets`" (folded case never matches).
  - `test_a_free_destination_leaves_the_emitted_document_unchanged`: red
    under "emit `attachment_conflicts: []` unconditionally" — the anchored
    fixture has no such key, so an always-present empty list fails the
    equality check even though it carries zero entries.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
# Regeneration recipe for `tests/fixtures/037-t1-2/pre-change-free-doc.json`
# (the "captured AT `16f64de`" fixture named in bullet 1 above): check out
# that commit in a disposable worktree, copy THIS file's harness into it
# (`_reduce`/`_atomic_result`/`FakeKado` are unchanged since — they only
# drive `main()`, they never call `detect_attachment_conflicts` directly),
# and run it against the OLD `suggestions-reducer.py`:
#
#   git worktree add /tmp/tomo-16f64de 16f64de
#   cp tests/test_037_t1_2_attachment_vault_collision.py \
#       /tmp/tomo-16f64de/tests/_fixture_capture.py
#   cd /tmp/tomo-16f64de && ./venv/bin/python -c "
#       import sys, json, tempfile
#       sys.path.insert(0, 'tests')
#       from pathlib import Path
#       from _fixture_capture import _reduce, _atomic_result, FakeKado, ITEM_KEY, ASSET_SOURCE
#       with tempfile.TemporaryDirectory() as tmp:
#           doc = _reduce(
#               Path(tmp),
#               {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, 'Karte')},
#               't037-t1-2-fixture',
#               {ITEM_KEY: {'attachments': [ASSET_SOURCE], 'unresolved_embeds': []}},
#               kado=FakeKado(occupied=set()),
#           )
#           print(json.dumps(doc, ensure_ascii=False, indent=2))
#   " > /tmp/tomo-16f64de-fixture.json
#   cp /tmp/tomo-16f64de-fixture.json tests/fixtures/037-t1-2/pre-change-free-doc.json  # from repo root
#   git worktree remove /tmp/tomo-16f64de
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
FIXTURE_DIR = TESTS_DIR / "fixtures" / "037-t1-2"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_reducer():
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer_t037_t1_2", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t037_t1_2"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()

from lib.item_key import to_filename  # noqa: E402

ITEM_KEY = "100 Inbox/Scans/karte.md"
ASSET_SOURCE = "100 Inbox/Scans/karte.png"
NOTES = "Atlas/202 Notes/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"  # DEFAULT_ASSET_FOLDER


class FakeKado:
    """Same shape as spec 034 T5.2's own FakeKado — `list_dir` over a fixed
    `occupied` set of vault paths, `raises` for the unreachable-Kado shape."""

    def __init__(self, occupied: set[str] | None = None, raises: bool = False):
        self.occupied = occupied or set()
        self.raises = raises
        self.probed: list[str] = []

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500) -> list:
        self.probed.append(path)
        if self.raises:
            raise RuntimeError("kado unreachable")
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
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": Path(item_key).stem,
                "suggested_title": title,
                "template": "Atomic Note.md",
                "location": NOTES,
                "candidate_mocs": [],
                "tags_to_add": [],
                "atomic_note_worthiness": 0.85,
                "classification": None,
                "force_atomic": False,
            },
        ],
    }


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _reduce(
    work: Path,
    results: dict[str, dict],
    run_id: str,
    resolved_attachments: dict[str, dict],
    *,
    kado: FakeKado | None = None,
) -> dict:
    """Drive the real reducer in-process (so `KadoClient` can be swapped for a
    fake) and return the parsed suggestions-doc JSON. `kado=None` means
    `--no-kado`, the degraded run."""
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    for item_key, result in results.items():
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
        json.dumps(resolved_attachments, ensure_ascii=False, indent=2), encoding="utf-8"
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
    if kado is None:
        argv.append("--no-kado")

    real_client = REDUCER.KadoClient
    real_argv = sys.argv
    try:
        sys.argv = argv
        if kado is not None:
            REDUCER.KadoClient = lambda *a, **k: kado
        assert REDUCER.main() == 0
    finally:
        REDUCER.KadoClient = real_client
        sys.argv = real_argv

    return json.loads(doc_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. A free destination leaves the emitted document unchanged (F1-AC1)
# ---------------------------------------------------------------------------

def test_a_free_destination_leaves_the_emitted_document_unchanged(tmp_path):
    """Anchored against `tests/fixtures/037-t1-2/pre-change-free-doc.json`,
    captured by running the reducer AT `16f64de` (the commit before this
    task) against this exact fixture input.

    `folder_listing_calls` / `distinct_destination_folders` are compared
    SEPARATELY and are EXPECTED to differ by exactly one: PRD F1-AC3 states
    the vault IS consulted once per run for the asset folder whenever
    attachments exist, so this is the documented cost delta `[ref: SDD/Cost]`,
    not a regression. Everything else — the rendered proposal, the item's
    `attachments` field, `attachments_preamble` — must be byte-identical:
    THAT is what "behaves exactly as it does today" (F1-AC1) means for a
    destination that turns out to be free.
    """
    doc = _reduce(
        tmp_path,
        {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, "Karte")},
        "t037-t1-2-free",
        {ITEM_KEY: {"attachments": [ASSET_SOURCE], "unresolved_embeds": []}},
        kado=FakeKado(occupied=set()),
    )
    doc.pop("generated", None)
    doc.pop("run_id", None)
    cost_fields = {
        k: doc.pop(k) for k in ("folder_listing_calls", "distinct_destination_folders")
    }

    expected = json.loads(
        (FIXTURE_DIR / "pre-change-free-doc.json").read_text(encoding="utf-8")
    )
    expected.pop("run_id", None)
    expected_cost_fields = {
        k: expected.pop(k) for k in ("folder_listing_calls", "distinct_destination_folders")
    }

    assert doc == expected, (
        "a run with a free attachment destination must render the SAME "
        "proposal as the pre-T1.2 reducer — attachment_conflicts must be "
        "ABSENT, not an empty list, or this equality fails by construction"
    )
    assert "attachment_conflicts" not in doc
    assert cost_fields == {
        k: v + 1 for k, v in expected_cost_fields.items()
    }, "one attachment folder listing is the documented cost of the check itself"


# ---------------------------------------------------------------------------
# 2. An occupied destination names source, destination, owner (F1-AC2)
# ---------------------------------------------------------------------------

def test_an_occupied_destination_names_source_destination_and_owner(tmp_path):
    """`same_file` is `null` here (spec 037 T1.3): `FakeKado` does not
    implement `read_file_bytes`, so `main()`'s `getattr(kado_client,
    "read_file_bytes", None)` wiring degrades to "no reader" rather than
    crashing — see test_037_t1_3_same_file.py for `same_file`'s own
    coverage (true/false/null, bounded reads)."""
    doc = _reduce(
        tmp_path,
        {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, "Karte")},
        "t037-t1-2-occupied",
        {ITEM_KEY: {"attachments": [ASSET_SOURCE], "unresolved_embeds": []}},
        kado=FakeKado(occupied={f"{ASSET_FOLDER}karte.png"}),
    )
    assert doc.get("attachment_conflicts") == [
        {
            "source": ASSET_SOURCE,
            "destination": f"{ASSET_FOLDER}karte.png",
            "same_file": None,
            "owner_source_items": [ITEM_KEY],
            "proposed_name": "karte (2).png",
        }
    ], doc.get("attachment_conflicts")


# ---------------------------------------------------------------------------
# 3. Dedup is by DESTINATION, not by path
# ---------------------------------------------------------------------------

def test_dedup_is_by_destination_not_by_path(tmp_path):
    """The SAME attachment, embedded by THREE notes, must produce ONE
    conflict entry carrying three owners — not three entries with one owner
    each. See module docstring for the named mutation this catches."""
    items = {
        "100 Inbox/A/note-a.md": _atomic_result(
            "100 Inbox/A/note-a.md", ASSET_SOURCE, "Note A"
        ),
        "100 Inbox/B/note-b.md": _atomic_result(
            "100 Inbox/B/note-b.md", ASSET_SOURCE, "Note B"
        ),
        "100 Inbox/C/note-c.md": _atomic_result(
            "100 Inbox/C/note-c.md", ASSET_SOURCE, "Note C"
        ),
    }
    resolved = {
        key: {"attachments": [ASSET_SOURCE], "unresolved_embeds": []}
        for key in items
    }
    doc = _reduce(
        tmp_path, items, "t037-t1-2-dedup", resolved,
        kado=FakeKado(occupied={f"{ASSET_FOLDER}karte.png"}),
    )
    conflicts = doc.get("attachment_conflicts") or []
    assert len(conflicts) == 1, (
        f"one attachment, three owners, must be ONE entry: {conflicts}"
    )
    assert sorted(conflicts[0]["owner_source_items"]) == sorted(items), (
        f"all three owning notes must be named: {conflicts[0]}"
    )


# ---------------------------------------------------------------------------
# 4. No Kado client / a listing that raises — regression pins (F1-AC5)
# ---------------------------------------------------------------------------

def test_no_kado_client_produces_no_conflicts_and_no_error(tmp_path):
    doc = _reduce(
        tmp_path,
        {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, "Karte")},
        "t037-t1-2-no-kado",
        {ITEM_KEY: {"attachments": [ASSET_SOURCE], "unresolved_embeds": []}},
        kado=None,
    )
    assert "attachment_conflicts" not in doc


def test_a_listing_that_raises_produces_no_conflicts_and_no_error(tmp_path):
    kado = FakeKado(occupied={f"{ASSET_FOLDER}karte.png"}, raises=True)
    doc = _reduce(
        tmp_path,
        {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, "Karte")},
        "t037-t1-2-raises",
        {ITEM_KEY: {"attachments": [ASSET_SOURCE], "unresolved_embeds": []}},
        kado=kado,
    )
    assert "attachment_conflicts" not in doc
    assert kado.probed, "the probe must have been attempted, not skipped"


# ---------------------------------------------------------------------------
# Unit-level coverage of detect_attachment_conflicts directly — faster and
# more surgical for the dedup/guard mutations than driving the whole reducer.
# ---------------------------------------------------------------------------

def test_unit_no_asset_listing_short_circuits_without_calling_it():
    """`asset_listing=None` must never be invoked. Mutation: drop the
    `asset_listing is None` short-circuit and call it unconditionally —
    `None(...)` raises `TypeError`."""
    actions = [{
        "kind": "create_atomic_note", "suppressed": False,
        "attachments": [ASSET_SOURCE],
    }]
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY, actions)], ASSET_FOLDER, None,
    )
    assert result == []


def test_unit_no_attachments_short_circuits_without_calling_listing():
    """`owners` empty (no attachments on the run's surviving actions) must
    short-circuit on `not owners` BEFORE `asset_listing` is even consulted —
    independently of the `asset_listing is None` guard exercised above, since
    `asset_listing` here is a real, non-None, call-recording callable.
    Mutation: weaken the guard from `if not owners or asset_listing is None`
    to `if asset_listing is None` (dropping the `not owners` half) — the
    listing below would then be invoked despite zero attachments in the run,
    and `calls` would be non-empty. `[ref: SDD/Cost]`.

    Added to close a code-quality finding that claimed this mutation "would
    pass all 8 tests unchanged". **That claim was measured and is false** —
    `test_unit_suppressed_atomics_claim_no_attachment` already fails under it,
    because a suppressed atomic leaves `owners` empty while a listing IS
    supplied, which is precisely the shape the finding said no test reached.
    So this test closed no hole. It earns its place for a different reason: it
    pins the guarantee directly, on the plainest input that expresses it,
    instead of leaving `[ref: SDD/Cost]` resting on a test whose subject is
    suppression. Do not delete it as redundant — and do not read it as the
    only thing holding the guard up either.
    """
    actions = [{
        "kind": "create_atomic_note", "suppressed": False,
        "attachments": [],
    }]
    calls: list[str] = []

    def listing(folder: str) -> dict:
        calls.append(folder)
        return {}

    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY, actions)], ASSET_FOLDER, listing,
    )
    assert result == []
    assert calls == [], "a run with zero attachments must never pay for a folder listing"


def test_unit_suppressed_atomics_claim_no_attachment():
    actions = [{
        "kind": "create_atomic_note", "suppressed": True,
        "attachments": [ASSET_SOURCE],
    }]
    calls: list[str] = []

    def listing(folder: str) -> dict:
        calls.append(folder)
        return {f"{ASSET_FOLDER}karte.png".casefold(): f"{ASSET_FOLDER}karte.png"}

    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY, actions)], ASSET_FOLDER, listing,
    )
    assert result == []
    assert calls == [], "a suppressed atomic's attachment must never reach the vault check"


def test_unit_dedup_by_destination_case_folded():
    actions_a = [{
        "kind": "create_atomic_note", "suppressed": False,
        "attachments": [ASSET_SOURCE],
    }]
    actions_b = [{
        "kind": "create_atomic_note", "suppressed": False,
        "attachments": [ASSET_SOURCE],
    }]
    listing = lambda folder: {  # noqa: E731
        f"{ASSET_FOLDER}karte.png".casefold(): f"{ASSET_FOLDER}karte.png"
    }
    result = REDUCER.detect_attachment_conflicts(
        [("100 Inbox/A/a.md", actions_a), ("100 Inbox/B/b.md", actions_b)],
        ASSET_FOLDER, listing,
    )
    assert len(result) == 1
    assert sorted(result[0]["owner_source_items"]) == [
        "100 Inbox/A/a.md", "100 Inbox/B/b.md",
    ]
