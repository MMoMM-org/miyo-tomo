#!/usr/bin/env python3
# version: 0.1.0
"""test_note_instructions.py — Behavioural tests for note-instructions.py (spec 044 T2.5).

Covers the draft lifecycle subcommands new, stage and drop:
- new draws a YYYY-MM-DD_HHMMSS stem, a run id and generated; reads the inbox,
  the atomic-note path (scalar, path or first of paths), the profile and the
  process destination; stages source.md; a Kado error leaves nothing on disk
- stage records title, destination, keep-source; refuses frozen changes with
  frozen: true and meta.json unchanged; reports the filled-note check
- drop removes the stage directory
- no user text (source body, draft body) in stdout or stderr

Runs in tmp_path with a fake KadoClient; never a live vault.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "note-instructions.py"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_meta  # noqa: E402
from lib.kado_client import KadoError, KadoNotFoundError  # noqa: E402

MARKER = "ZZ-PRIVATE-MARKER-7f3a"
TEMPLATE = "Templates/t_meeting.md"
SOURCE = "100 Inbox/Meeting raw.md"


def _load():
    spec = importlib.util.spec_from_file_location("note_instructions", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ni = _load()


class FakeKado:
    files: dict = {}
    reads: list = []

    def read_note(self, path):
        FakeKado.reads.append(path)
        if path not in FakeKado.files:
            raise KadoNotFoundError("not found")
        return {"content": FakeKado.files[path]}


class FailingKado:
    def read_note(self, path):
        raise KadoError("503 after retries")


class NoKado:
    def __init__(self):
        raise AssertionError("text-in-call must not contact Kado")


CONFIG = """\
profile: "miyo"
concepts:
  inbox: "100 Inbox/"
  atomic_note:
{atomic}
"""


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """An instance root with a vault-config and a fake Kado holding the source."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    _config(tmp_path, '    path: "Atlas/202 Notes/"')
    FakeKado.files = {SOURCE: f"raw meeting text {MARKER}\n"}
    FakeKado.reads = []
    monkeypatch.setattr(ni, "KadoClient", FakeKado)
    return tmp_path


def _config(root: Path, atomic: str) -> None:
    (root / "config" / "vault-config.yaml").write_text(
        CONFIG.format(atomic=atomic), encoding="utf-8")


def _run(argv, capsys):
    try:
        rc = ni.main(argv)
    except SystemExit as exc:
        rc = exc.code
    out, err = capsys.readouterr()
    return rc, out, err


def _json(out: str) -> dict:
    return json.loads(out)


def _new(capsys, *extra):
    rc, out, err = _run(["new", "--template", TEMPLATE, *extra], capsys)
    assert rc == 0, err
    return _json(out)


def _meta(root: Path, stem: str):
    return note_meta.read_meta(note_meta.stage_dir(root, stem))


# ── new ──────────────────────────────────────────────────────────────────


def test_new_output_keys_and_stem_format(inst, capsys):
    out = _new(capsys, "--source", SOURCE)
    assert set(out) == {"stem", "run_id", "default_destination", "inbox"}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}", out["stem"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-[0-9a-f]{6}", out["run_id"])
    assert out["inbox"] == "100 Inbox/"
    assert out["default_destination"] == "Atlas/202 Notes/"


def test_new_writes_meta_with_identity_and_generated(inst, capsys):
    out = _new(capsys, "--source", SOURCE)
    meta = _meta(inst, out["stem"])
    assert meta.run_id == out["run_id"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", meta.generated)
    assert meta.template == TEMPLATE and meta.template_stem == "t_meeting"
    assert meta.source_path == SOURCE
    assert meta.destination == meta.default_destination == "Atlas/202 Notes/"
    assert meta.keep_source is False and meta.steps_done == [] and meta.failed_step == ""
    assert meta.inbox_file.startswith("100 Inbox/" + out["stem"])


def test_new_stages_the_source_body(inst, capsys):
    out = _new(capsys, "--source", SOURCE)
    staged = note_meta.stage_dir(inst, out["stem"]) / "source.md"
    assert staged.read_text(encoding="utf-8") == FakeKado.files[SOURCE]
    assert FakeKado.reads == [SOURCE]


def test_new_takes_first_of_atomic_paths(inst, capsys):
    _config(inst, '    paths:\n      - "Atlas/First/"\n      - "Atlas/Second/"')
    assert _new(capsys)["default_destination"] == "Atlas/First/"


def test_new_takes_scalar_atomic_path(inst, capsys):
    (inst / "config" / "vault-config.yaml").write_text(
        'profile: "lyt"\nconcepts:\n  inbox: "+"\n  atomic_note: "Notes"\n', encoding="utf-8")
    out = _new(capsys)
    assert out["default_destination"] == "Notes/"
    assert out["inbox"] == "+/"


def test_new_process_destination_wins(inst, capsys):
    proc = inst / "config" / "note-processes"
    proc.mkdir()
    (proc / "t_meeting.md").write_text("---\ndestination: Atlas/Meetings\n---\n", encoding="utf-8")
    out = _new(capsys)
    assert out["default_destination"] == "Atlas/Meetings/"
    assert _meta(inst, out["stem"]).destination == "Atlas/Meetings/"


def test_new_broken_process_file_falls_back_to_atomic_path(inst, capsys):
    proc = inst / "config" / "note-processes"
    proc.mkdir()
    (proc / "t_meeting.md").write_text("---\ndestination: [unclosed\n", encoding="utf-8")
    assert _new(capsys)["default_destination"] == "Atlas/202 Notes/"


def test_config_reader_returns_profile(inst):
    cfg = ni.read_note_config(Path("config/vault-config.yaml"))
    assert cfg == {"inbox": "100 Inbox/", "atomic_path": "Atlas/202 Notes/", "profile": "miyo"}


def test_config_reader_profile_absent_is_none(inst):
    (inst / "config" / "vault-config.yaml").write_text(
        'concepts:\n  inbox: "In/"\n  atomic_note: "N/"\n', encoding="utf-8")
    assert ni.read_note_config(Path("config/vault-config.yaml"))["profile"] is None


def test_new_text_in_call_has_no_source_and_no_kado(inst, capsys, monkeypatch):
    monkeypatch.setattr(ni, "KadoClient", NoKado)
    out = _new(capsys)
    meta = _meta(inst, out["stem"])
    assert meta.source_path is None
    assert not (note_meta.stage_dir(inst, out["stem"]) / "source.md").exists()


def test_new_kado_error_exits_1_and_leaves_nothing(inst, capsys, monkeypatch):
    monkeypatch.setattr(ni, "KadoClient", FailingKado)
    rc, out, err = _run(["new", "--template", TEMPLATE, "--source", SOURCE], capsys)
    assert rc == 1
    assert not note_meta.stage_root(inst).exists() or not any(note_meta.stage_root(inst).iterdir())


def test_new_missing_source_exits_1(inst, capsys):
    rc, _, _ = _run(["new", "--template", TEMPLATE, "--source", "100 Inbox/gone.md"], capsys)
    assert rc == 1


def test_new_never_prints_source_text(inst, capsys):
    rc, out, err = _run(["new", "--template", TEMPLATE, "--source", SOURCE], capsys)
    assert rc == 0
    assert MARKER not in out and MARKER not in err


def test_new_two_drafts_get_distinct_stems(inst, capsys):
    assert _new(capsys)["stem"] != _new(capsys)["stem"]


@pytest.mark.parametrize("argv", [
    ["new"],
    ["new", "--template", ""],
    ["new", "--template", "Templates/t_meeting"],
    ["new", "--template", TEMPLATE, "--source", "100 Inbox/audio.m4a"],
    [],
])
def test_new_bad_invocation_exits_2(inst, capsys, argv):
    rc, _, _ = _run(argv, capsys)
    assert rc == 2


def test_new_missing_config_exits_2(inst, capsys):
    (inst / "config" / "vault-config.yaml").unlink()
    rc, _, _ = _run(["new", "--template", TEMPLATE], capsys)
    assert rc == 2


def test_new_config_without_inbox_exits_2(inst, capsys):
    (inst / "config" / "vault-config.yaml").write_text(
        'concepts:\n  atomic_note: "N/"\n', encoding="utf-8")
    rc, _, _ = _run(["new", "--template", TEMPLATE], capsys)
    assert rc == 2


# ── stage ────────────────────────────────────────────────────────────────


GOOD_DRAFT = "---\ntitle: Design review\n---\n# Notes\nAll fine " + MARKER + "\n"
BAD_DRAFT = "---\ntitle: x\n---\n# Notes\n{{summary}} " + MARKER + "\n"


def _staged(inst, capsys, draft=GOOD_DRAFT, **meta_changes):
    stem = _new(capsys, "--source", SOURCE)["stem"]
    stage = note_meta.stage_dir(inst, stem)
    if draft is not None:
        (stage / "draft.md").write_text(draft, encoding="utf-8")
    if meta_changes:
        meta = note_meta.read_meta(stage)
        for key, value in meta_changes.items():
            setattr(meta, key, value)
        note_meta.write_meta(stage, meta)
    return stem


def _stage(capsys, stem, *extra):
    rc, out, err = _run(["stage", "--stem", stem, *extra], capsys)
    return rc, out, err


def test_stage_records_title_destination_keep_source(inst, capsys):
    stem = _staged(inst, capsys)
    rc, out, _ = _stage(capsys, stem, "--title", "Design review",
                        "--destination", "Atlas/Meetings", "--keep-source", "true")
    assert rc == 0
    res = _json(out)
    assert set(res) == {"stem", "title", "inbox_file", "destination_file",
                        "keep_source", "frozen", "check"}
    assert res["title"] == "Design review"
    assert res["inbox_file"] == f"100 Inbox/{stem}_Design review.md"
    assert res["destination_file"] == "Atlas/Meetings/Design review.md"
    assert res["keep_source"] is True and res["frozen"] is False
    meta = _meta(inst, stem)
    assert (meta.title, meta.destination, meta.keep_source) == (
        "Design review", "Atlas/Meetings/", True)


def test_stage_without_title_reports_empty_names(inst, capsys):
    stem = _staged(inst, capsys)
    res = _json(_stage(capsys, stem)[1])
    assert res["title"] == "" and res["inbox_file"] == "" and res["destination_file"] == ""


@pytest.mark.parametrize("change", [
    ["--title", "Other"], ["--destination", "Elsewhere/"],
])
def test_stage_refuses_name_change_once_a_step_is_done(inst, capsys, change):
    stem = _staged(inst, capsys, title="Design review", steps_done=["note"])
    before = (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes()
    rc, out, _ = _stage(capsys, stem, *change)
    assert rc == 0
    assert _json(out)["frozen"] is True
    assert (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes() == before


def test_stage_accepts_keep_source_change_while_only_note_is_done(inst, capsys):
    stem = _staged(inst, capsys, title="Design review", steps_done=["note"])
    res = _json(_stage(capsys, stem, "--keep-source", "true")[1])
    assert res["frozen"] is False and res["keep_source"] is True
    assert _meta(inst, stem).keep_source is True


def test_stage_refuses_keep_source_change_once_instructions_json_is_done(inst, capsys):
    stem = _staged(inst, capsys, title="Design review",
                   steps_done=["note", "instructions_json"])
    res = _json(_stage(capsys, stem, "--keep-source", "true")[1])
    assert res["frozen"] is True and res["keep_source"] is False
    assert _meta(inst, stem).keep_source is False


def test_stage_restating_values_is_not_a_change(inst, capsys):
    stem = _staged(inst, capsys, title="Design review", steps_done=["note", "instructions_json"])
    res = _json(_stage(capsys, stem, "--title", "Design review",
                       "--destination", "Atlas/202 Notes/", "--keep-source", "false")[1])
    assert res["frozen"] is False


def test_stage_reports_passing_check(inst, capsys):
    stem = _staged(inst, capsys)
    check = _json(_stage(capsys, stem, "--title", "T")[1])["check"]
    assert check["ok"] is True
    assert check["findings"] and all(f["status"] != "FAIL" for f in check["findings"])


def test_stage_reports_failing_check(inst, capsys):
    stem = _staged(inst, capsys, draft=BAD_DRAFT)
    check = _json(_stage(capsys, stem, "--title", "T")[1])["check"]
    assert check["ok"] is False
    assert any(f["check"] == "no_tokens" and f["status"] == "FAIL" for f in check["findings"])


def test_stage_missing_draft_fails_the_check(inst, capsys):
    stem = _staged(inst, capsys, draft=None)
    rc, out, _ = _stage(capsys, stem, "--title", "T")
    assert rc == 0
    check = _json(out)["check"]
    assert check["ok"] is False
    assert [f["check"] for f in check["findings"]] == ["draft_present"]


def test_stage_never_prints_draft_or_source_text(inst, capsys):
    stem = _staged(inst, capsys, draft=BAD_DRAFT)
    _, out, err = _stage(capsys, stem, "--title", "T")
    assert MARKER not in out and MARKER not in err


@pytest.mark.parametrize("extra", [
    ["--title", ""], ["--title", "   "],
    ["--destination", ""], ["--destination", "/abs/"], ["--destination", "Atlas/../x/"],
    ["--keep-source", "maybe"],
])
def test_stage_bad_values_exit_2(inst, capsys, extra):
    stem = _staged(inst, capsys)
    rc, _, _ = _stage(capsys, stem, *extra)
    assert rc == 2


@pytest.mark.parametrize("stem", ["2026-01-01_000000", "../etc", "2026-01-01_0000"])
def test_stage_unknown_or_malformed_stem_exits_2(inst, capsys, stem):
    rc, _, _ = _stage(capsys, stem, "--title", "T")
    assert rc == 2


# ── drop ─────────────────────────────────────────────────────────────────


def test_drop_removes_stage_dir(inst, capsys):
    stem = _staged(inst, capsys)
    rc, out, _ = _run(["drop", "--stem", stem], capsys)
    assert rc == 0
    assert _json(out) == {"stem": stem, "removed": True}
    assert not note_meta.stage_dir(inst, stem).exists()


def test_drop_absent_stem_reports_not_removed(inst, capsys):
    rc, out, _ = _run(["drop", "--stem", "2026-01-01_000000"], capsys)
    assert rc == 0
    assert _json(out) == {"stem": "2026-01-01_000000", "removed": False}


def test_drop_malformed_stem_exits_2(inst, capsys):
    rc, _, _ = _run(["drop", "--stem", "../x"], capsys)
    assert rc == 2
