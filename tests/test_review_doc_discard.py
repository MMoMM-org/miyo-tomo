#!/usr/bin/env python3
# version: 0.1.0
"""test_review_doc_discard.py — review-doc.py discard: an open review is marked, never deleted (spec 047 walk F-R5-2).

On tests/note_fake_vault (Kado's write guard and frontmatter merge) with a stage built by lib/review_stage.write:
- discarded: one frontmatter read, then one merge of ``tomo.state: discarded`` with the read's ``modified`` as
  ``expected_modified``; the exact call list is those two; the file stays, its body and every other key unchanged;
  the stage content and proposals.json are gone, meta.json and payloads.json stay (as replace --abort)
- stopped doc-missing: no document at the path (or no path known); nothing written, the stage kept
- stopped not-a-review: the note at the path is not Tomo's review document; nothing written, the stage kept
- stopped doc-changed: a stale ``modified`` (the fake's own guard), KadoConcurrencyError, or Kado's dirty-editor
  CONFLICT; ``conflict`` names the reason; the stage kept
- stopped kado-failed: any other Kado failure on the read or the merge; ``error`` is the class name (and Kado's
  code), never the message; the stage kept
- discard of a stem that fails safe_stem is a usage error (exit 2)

RED before F-R5-2: review-doc.py had no ``discard`` subcommand (argparse exit 2 on every test).
All data is synthetic.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from note_fake_vault import NoteFakeVault, split_frontmatter  # noqa: E402
import test_review_doc as trd  # noqa: E402
from lib.kado_client import KadoAuthError, KadoConcurrencyError, KadoToolError  # noqa: E402

INBOX, MARKER = trd.INBOX, trd.MARKER

STEM = "2026-W13_review"
DOC = f"{INBOX}2026-W13 Review.md"
BODY = f"\n# 2026-W13 Review\n\n- [ ] Approved\n\n## Done\n\n- [ ] edited by the user {MARKER} %%t1%%\n"
DOC_TEXT = ("---\ntomo:\n  doc_type: review\n  state: pending-approval\n  run_id: r1\n  updated_at: x\n"
            "review_period: 2026-W13\nreview_kind: week\nreview_stem: 2026-W13_review\n---\n" + BODY)
EDITOR_CONFLICT = ('kado-write returned an error: {"code":"CONFLICT","message":"The note is open in the editor '
                   'with unsaved changes."}')


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_doc_discard_script", trd.SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    trd._config(tmp_path)
    return tmp_path


def _staged(instance: Path, *, doc_path=DOC) -> Path:
    """A stage holding a read and proposals.json (an open entry with new_read), meta.json and payloads.json."""
    trd.stage(instance, trd.week_read(), trd.GOOD)
    folder = instance / "tomo-tmp" / "review" / STEM
    meta = {"stem": STEM} if doc_path is None else {"stem": STEM, "doc_path": doc_path}
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (folder / "payloads.json").write_text("{}\n", encoding="utf-8")
    return folder


def _discard(mod, monkeypatch, capsys, fake, *extra):
    return trd._run(mod, monkeypatch, capsys, ["discard", "--stem", STEM, *extra], fake)


def _kept(folder: Path) -> None:
    assert (folder / "manifest.json").is_file() and (folder / "proposals.json").is_file()
    assert (folder / "days").is_dir()


def test_discard_marks_the_document_keeps_the_file_and_clears_the_stage(mod, instance, monkeypatch, capsys):
    folder = _staged(instance)
    fake = NoteFakeVault({DOC: DOC_TEXT})
    fake.modified[DOC] = 41
    code, out, err = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and err == ""
    assert out == {"status": "discarded", "stem": STEM, "doc_path": DOC}
    assert fake.events == [("read_frontmatter", DOC), ("write_frontmatter", DOC)]
    assert fake.merges == [{"path": DOC, "frontmatter": {"tomo": {"state": "discarded"}}, "mode": "merge",
                            "expected_modified": 41}]
    assert fake.writes == [] and DOC in fake.files
    front, body = split_frontmatter(fake.text(DOC))
    assert body == BODY
    assert front["tomo"] == {"doc_type": "review", "state": "discarded", "run_id": "r1", "updated_at": "x"}
    assert front["review_period"] == "2026-W13" and front["review_stem"] == STEM
    assert sorted(p.name for p in folder.iterdir()) == ["meta.json", "payloads.json"]


def test_discard_takes_the_doc_path_flag_over_meta(mod, instance, monkeypatch, capsys):
    folder = _staged(instance, doc_path=None)
    fake = NoteFakeVault({DOC: DOC_TEXT})
    code, out, _ = _discard(mod, monkeypatch, capsys, fake, "--doc-path", DOC)
    assert code == 0 and out == {"status": "discarded", "stem": STEM, "doc_path": DOC}
    assert sorted(p.name for p in folder.iterdir()) == ["meta.json", "payloads.json"]


def test_discard_stops_on_a_missing_document_and_keeps_the_stage(mod, instance, monkeypatch, capsys):
    folder = _staged(instance)
    fake = NoteFakeVault({})
    code, out, _ = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and out == {"status": "stopped", "stem": STEM, "doc_path": DOC, "reason": "doc-missing"}
    assert fake.events == [("read_frontmatter", DOC)] and fake.merges == []
    _kept(folder)


def test_discard_without_a_known_path_is_doc_missing_without_a_kado_call(mod, instance, monkeypatch, capsys):
    folder = _staged(instance, doc_path=None)
    fake = NoteFakeVault({DOC: DOC_TEXT})
    code, out, _ = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and out == {"status": "stopped", "stem": STEM, "reason": "doc-missing"}
    assert fake.call_count == 0
    _kept(folder)


def test_discard_stops_on_a_note_that_is_not_tomos_review(mod, instance, monkeypatch, capsys):
    folder = _staged(instance)
    fake = NoteFakeVault({DOC: "---\ntitle: mine\n---\n# My own review\n"})
    code, out, _ = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and out == {"status": "stopped", "stem": STEM, "doc_path": DOC, "reason": "not-a-review"}
    assert fake.merges == [] and fake.text(DOC) == "---\ntitle: mine\n---\n# My own review\n"
    _kept(folder)


class _ChangedAfterRead(NoteFakeVault):
    """The user saves the document between Tomo's read and its merge: the read's ``modified`` goes stale."""

    def read_frontmatter(self, path):
        found = super().read_frontmatter(path)
        self._bump(path)
        return found


def test_discard_stops_on_a_stale_modified_and_keeps_the_stage(mod, instance, monkeypatch, capsys):
    folder = _staged(instance)
    fake = _ChangedAfterRead({DOC: DOC_TEXT})
    code, out, _ = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and out == {"status": "stopped", "stem": STEM, "doc_path": DOC, "reason": "doc-changed",
                                 "conflict": "changed-since-read"}
    assert fake.merges == [] and fake.text(DOC) == DOC_TEXT
    _kept(folder)


@pytest.mark.parametrize("exc,conflict", [
    (KadoConcurrencyError("kado-write returned an error: expectedModified mismatch"), "changed-since-read"),
    (KadoToolError(EDITOR_CONFLICT), "open-unsaved"),
], ids=["concurrency", "dirty-editor"])
def test_discard_stops_on_a_kado_conflict_and_keeps_the_stage(mod, instance, monkeypatch, capsys, exc, conflict):
    folder = _staged(instance)
    fake = NoteFakeVault({DOC: DOC_TEXT})
    fake.fail[("write_frontmatter", DOC)] = exc
    code, out, _ = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and out == {"status": "stopped", "stem": STEM, "doc_path": DOC, "reason": "doc-changed",
                                 "conflict": conflict}
    assert fake.text(DOC) == DOC_TEXT
    _kept(folder)


@pytest.mark.parametrize("method,exc,error", [
    ("read_frontmatter", KadoAuthError("401 private-detail"), {"kind": "KadoAuthError"}),
    ("write_frontmatter", KadoToolError('kado-write returned an error: {"code":"FORBIDDEN","message":"private"}'),
     {"kind": "KadoToolError", "code": "FORBIDDEN"}),
], ids=["read-auth", "merge-denied"])
def test_discard_stops_on_another_kado_failure_and_keeps_the_stage(mod, instance, monkeypatch, capsys,
                                                                  method, exc, error):
    folder = _staged(instance)
    fake = NoteFakeVault({DOC: DOC_TEXT})
    fake.fail[(method, DOC)] = exc
    code, out, _ = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and out == {"status": "stopped", "stem": STEM, "doc_path": DOC, "reason": "kado-failed",
                                 "error": error}
    assert "private" not in json.dumps(out)
    assert fake.text(DOC) == DOC_TEXT
    _kept(folder)


def test_discard_refuses_an_unsafe_stem(mod, instance, monkeypatch, capsys):
    with pytest.raises(SystemExit) as stop:
        mod.main(["discard", "--stem", "../x"])
    assert stop.value.code == 2


def test_discard_never_merges_unguarded_when_the_read_reports_no_modified(mod, instance, monkeypatch, capsys):
    folder = _staged(instance)
    fake = NoteFakeVault({DOC: DOC_TEXT})
    fake.modified[DOC] = None
    code, out, _ = _discard(mod, monkeypatch, capsys, fake)
    assert code == 0 and out == {"status": "stopped", "stem": STEM, "doc_path": DOC, "reason": "kado-failed",
                                 "error": {"kind": "modified-missing"}}
    assert fake.events == [("read_frontmatter", DOC)] and fake.text(DOC) == DOC_TEXT
    _kept(folder)
