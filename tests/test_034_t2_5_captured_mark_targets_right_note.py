#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t2_5_captured_mark_targets_right_note.py — spec 034 T2.5.

`mark-captured.py` is the only place in spec 034 where a filename collision
mutates the user's vault: it drives `client.write_frontmatter` on every item
the run finished. It replayed `inbox-state.jsonl` last-wins per bare filename,
so once inbox discovery goes recursive, two notes that share a filename in
different subfolders collapse onto one state entry — one masks the other, and
the captured mark lands on the wrong note or on no note at all. Silently.

These tests pin the join key to `item_key` (the vault-relative path, verbatim
— ADR-1/ADR-2) and pin the decline branch: when an entry cannot be addressed
unambiguously, nothing is written (PRD Business Rule 7).

CON-7: the write path is exercised against a fake client only, never a live
vault.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "mark-captured.py"

sys.path.insert(0, str(SCRIPTS_DIR))

RUN_ID = "run-034-t25"


# mark-captured.py reaches lib.doc_frontmatter through several import hops, and
# some of them need the real module. Bind it here, at collection time, so a
# stand-in registered by another test module can never shadow it.
import lib.doc_frontmatter  # noqa: E402,F401


def _load_script_module():
    spec = importlib.util.spec_from_file_location("mark_captured", SCRIPT_PATH)
    assert spec and spec.loader, f"Cannot load module from {SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeKado:
    """Records every path this run touched, per Kado operation (CON-7)."""

    def __init__(self) -> None:
        self.frontmatter_reads: list[str] = []
        self.frontmatter_writes: list[dict] = []
        self.note_reads: list[str] = []

    def read_frontmatter(self, path: str) -> dict:
        self.frontmatter_reads.append(path)
        return {"modified": 1}

    def write_frontmatter(
        self, path: str, frontmatter: dict, mode: str = "merge", expected_modified=None
    ) -> dict:
        self.frontmatter_writes.append(
            {"path": path, "frontmatter": frontmatter, "mode": mode}
        )
        return {"path": path, "modified": 2}

    def read_note(self, path: str) -> dict:
        self.note_reads.append(path)
        return {"content": ""}

    @property
    def written_paths(self) -> list[str]:
        return [w["path"] for w in self.frontmatter_writes]

    @property
    def touched_paths(self) -> list[str]:
        """Every path handed to Kado in any capacity — read or write."""
        return self.frontmatter_reads + self.written_paths + self.note_reads


def _entry(item_key: str, status: str, run_id: str = RUN_ID, **over) -> dict:
    """A state-file line, shaped per schemas/state-entry.schema.json."""
    entry = {
        "run_id": run_id,
        "stem": item_key.rsplit("/", 1)[-1].removesuffix(".md"),
        "item_key": item_key,
        "path": item_key,
        "status": status,
        "attempts": 1,
    }
    entry.update(over)
    return entry


def _write_state(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "inbox-state.jsonl"
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return path


def _run(mod, monkeypatch, state_path: Path, client: FakeKado, run_id: str = RUN_ID) -> int:
    monkeypatch.setattr(mod, "KadoClient", lambda: client)
    monkeypatch.setattr(
        sys,
        "argv",
        ["mark-captured.py", "--state", str(state_path), "--run-id", run_id],
    )
    return mod.main()


APPROVED = "100 Inbox/Places/Dresden.md"
NAMESAKE = "100 Inbox/Trips/Dresden.md"


# ---------------------------------------------------------------------------
# 1 — collision, one approved: the mark lands on the approved note only
# ---------------------------------------------------------------------------


def test_collision_marks_the_approved_note_and_leaves_the_namesake_untouched(
    tmp_path, monkeypatch
):
    """Two notes named `Dresden.md` in different subfolders; only one finished.

    Under the old bare-filename replay the namesake's `failed` line masks the
    approved note's `done` line — the approved note drops out of the work list
    and never gets its mark. PRD/AC Feature 3.
    """
    mod = _load_script_module()
    state_path = _write_state(
        tmp_path,
        [
            _entry(APPROVED, "done"),
            _entry(NAMESAKE, "failed"),
        ],
    )
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert rc == 0, f"expected exit 0, got {rc}"
    assert client.written_paths == [APPROVED], (
        f"the approved note must be marked exactly once; got {client.written_paths}"
    )
    assert NAMESAKE not in client.touched_paths, (
        f"the namesake must not be touched at all; Kado saw {client.touched_paths}"
    )


def test_collision_with_both_done_marks_each_note_at_its_own_path(tmp_path, monkeypatch):
    """Both same-named notes finished — each gets its own mark, at its own path.

    The old replay kept one entry per bare filename, so one of the two was
    silently dropped and its source note stayed unmarked (and would be
    re-discovered as new on the next run).
    """
    mod = _load_script_module()
    state_path = _write_state(
        tmp_path,
        [
            _entry(APPROVED, "done"),
            _entry(NAMESAKE, "done"),
        ],
    )
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert rc == 0, f"expected exit 0, got {rc}"
    assert sorted(client.written_paths) == sorted([APPROVED, NAMESAKE]), (
        f"both same-named notes must be marked; got {client.written_paths}"
    )


def test_collision_replay_keeps_the_last_line_per_item_key_not_per_filename(
    tmp_path, monkeypatch
):
    """A later line for ONE item supersedes only that item's earlier line.

    `running` → `done` for the approved note, interleaved with the namesake's
    own transitions. Keyed on the filename, the namesake's trailing `failed`
    line wins for both.
    """
    mod = _load_script_module()
    state_path = _write_state(
        tmp_path,
        [
            _entry(APPROVED, "running"),
            _entry(NAMESAKE, "running"),
            _entry(APPROVED, "done"),
            _entry(NAMESAKE, "failed"),
        ],
    )
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert rc == 0, f"expected exit 0, got {rc}"
    assert client.written_paths == [APPROVED], (
        f"only the finished item may be marked; got {client.written_paths}"
    )
    assert NAMESAKE not in client.touched_paths, (
        f"the failed namesake must not be touched; Kado saw {client.touched_paths}"
    )


# ---------------------------------------------------------------------------
# 2 — decline rather than guess: nothing is written (PRD Business Rule 7)
# ---------------------------------------------------------------------------


def test_entry_without_item_key_is_never_written(tmp_path, monkeypatch):
    """An entry carrying no `item_key` cannot be addressed — nothing is written.

    `item_key` is required by state-entry.schema.json. Falling back to `stem`
    would reintroduce the collision this task removes, so the entry is declined
    outright: zero writes, and zero Kado calls of any kind.
    """
    mod = _load_script_module()
    keyless = _entry(APPROVED, "done")
    keyless.pop("item_key")
    state_path = _write_state(tmp_path, [keyless])
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert client.frontmatter_writes == [], (
        f"an unaddressable entry must produce no write; got {client.frontmatter_writes}"
    )
    assert client.touched_paths == [], (
        f"an unaddressable entry must produce no Kado call; got {client.touched_paths}"
    )
    assert rc == 0, f"declining is not a failure; expected exit 0, got {rc}"


def test_entry_without_path_is_declined_and_reported(tmp_path, monkeypatch, capsys):
    """An addressable entry with no vault path is declined, and said out loud.

    Nothing is written, and the run reports the decline rather than passing
    over it in silence.
    """
    mod = _load_script_module()
    pathless = _entry(APPROVED, "done")
    pathless["path"] = ""
    state_path = _write_state(tmp_path, [pathless])
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert client.frontmatter_writes == [], (
        f"an entry with no path must produce no write; got {client.frontmatter_writes}"
    )
    assert client.touched_paths == [], (
        f"an entry with no path must produce no Kado call; got {client.touched_paths}"
    )
    assert rc == 0, f"declining is not a failure; expected exit 0, got {rc}"

    err = capsys.readouterr().err
    assert "declined" in err, f"the decline must be reported on stderr; got:\n{err}"
    assert APPROVED in err or "Dresden" in err, (
        f"the decline must name the item it skipped; got:\n{err}"
    )


def test_collision_where_the_namesake_belongs_to_another_run_writes_nothing_wrong(
    tmp_path, monkeypatch
):
    """A prior run's namesake must not divert this run's mark.

    Filename-keyed, the prior run's trailing `done` line masks this run's
    approved item; the run_id filter then drops the survivor and the approved
    note is never marked — while the stale path is the only one still in view.
    """
    mod = _load_script_module()
    state_path = _write_state(
        tmp_path,
        [
            _entry(APPROVED, "done"),
            _entry(NAMESAKE, "done", run_id="run-OLD"),
        ],
    )
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert rc == 0, f"expected exit 0, got {rc}"
    assert client.written_paths == [APPROVED], (
        f"only this run's approved note may be marked; got {client.written_paths}"
    )
    assert NAMESAKE not in client.touched_paths, (
        f"the prior run's namesake must not be touched; Kado saw {client.touched_paths}"
    )


# ---------------------------------------------------------------------------
# 3 — the existing single-note path is unchanged
# ---------------------------------------------------------------------------


def test_single_note_path_is_unchanged(tmp_path, monkeypatch):
    """One done markdown item: one merge write, at its own stored path."""
    mod = _load_script_module()
    state_path = _write_state(tmp_path, [_entry("100 Inbox/Asahikawa.md", "done")])
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert rc == 0, f"expected exit 0, got {rc}"
    assert len(client.frontmatter_writes) == 1
    write = client.frontmatter_writes[0]
    assert write["path"] == "100 Inbox/Asahikawa.md"
    assert write["mode"] == "merge"
    block = write["frontmatter"]["tomo"]
    assert block["doc_type"] == "source"
    assert block["state"] == "captured"
    assert block["run_id"] == RUN_ID


def test_non_markdown_item_is_still_skipped(tmp_path, monkeypatch):
    """Non-markdown items carry no frontmatter and are skipped before Kado."""
    mod = _load_script_module()
    state_path = _write_state(
        tmp_path,
        [
            _entry("100 Inbox/Asahikawa.md", "done"),
            _entry("100 Inbox/Voice/memo.m4a", "done"),
        ],
    )
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert rc == 0, f"expected exit 0, got {rc}"
    assert client.written_paths == ["100 Inbox/Asahikawa.md"]
    assert "100 Inbox/Voice/memo.m4a" not in client.touched_paths


def test_stem_stays_display_only(tmp_path, monkeypatch):
    """A wrong or missing `stem` cannot redirect the write (ADR-2).

    The write target comes from the entry's own stored `path`, never from a
    path reconstructed out of the display stem.
    """
    mod = _load_script_module()
    misleading = _entry(APPROVED, "done")
    misleading["stem"] = "SomethingElse"
    state_path = _write_state(tmp_path, [misleading])
    client = FakeKado()

    rc = _run(mod, monkeypatch, state_path, client)

    assert rc == 0, f"expected exit 0, got {rc}"
    assert client.written_paths == [APPROVED], (
        f"the write must target the stored path, not the stem; got {client.written_paths}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
