#!/usr/bin/env python3
# version: 0.2.10
"""test_note_instructions.py — Behavioural tests for note-instructions.py (spec 044 T2.5, T2.6).

deliver (T2.6): order note → JSON → MD → source mark, a failure stops every
later step; keep-source frozen once instructions_json landed or is in flight,
title and destination once the first upload is in flight; every output carries
frozen; a killed run is a kept draft; resume compares (identical = done, other text = exit 3 EXISTS:);
destination clash and guard-cut sets refused; filled-note check gate; a
failed stamp is step ""; a missing Kado config is step kado_config, a kept draft
that resume delivers from scratch;
byte-identical rebuilds; stamps; stage dir removed only on success; one shared
no-overwrite contract test with kado-write-file.py; the MD carries no Templater hint; a
recorded step whose target is gone is not written again.

The source mark: a source gone before it is delivered unmarked; any other Kado
error, or a read without a modified time, fails the step; the merge is guarded
by the modified time just read. A resume after the mark was recorded reads the
source and reports source_marked true only for this draft's tomo: block (state
captured, this run id); a Kado error other than not-found fails the step.

Covers the draft lifecycle subcommands new, stage and drop:
- new draws a YYYY-MM-DD_HHMMSS stem, a run id and generated; reads the inbox,
  the atomic-note path (scalar, path or first of paths), the profile and the
  process destination; stages source.md; a Kado error leaves nothing on disk
- stage records title, destination, keep-source; refuses frozen changes with
  frozen: true and meta.json unchanged; reports the filled-note check
- new stores the config profile in meta.json
- stage writes note.md = draft.md with {{source_link}} resolved from
  keep_source (draft.md untouched, so a later flip re-resolves); the check
  runs on note.md
- drop removes the stage directory
- vault_folder validates every folder (--destination, process file,
  concepts.atomic_note, concepts.inbox): no absolute form (/, ~, drive
  letter), no backslash, no segment that is blank or starts with a dot, no
  template syntax, no unsafe character (Cc, Cf, Zl, Zp except the joiners
  U+200C and U+200D, which title and folder accept); the Unicode form is
  kept; an unsafe process destination falls back with one stderr line, the
  process file error read_process reports; an unsafe atomic path or inbox
  exits 2 with a fixed message; a write failure in new leaves no stage
- vault_note validates --template and --source the same way plus .md, before
  Kado is asked; --source must lie inside the inbox
- stage trims the title, strips trailing dots, rejects unsafe characters, a
  leading dot and template syntax
- no user text (source body, draft body, title) in stdout or stderr

Runs in tmp_path with a fake KadoClient; never a live vault.
"""
from __future__ import annotations

import http.client
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

import pytest
import yaml

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


def test_new_stores_the_profile_in_meta(inst, capsys):
    stem = _new(capsys)["stem"]
    assert _meta(inst, stem).profile == "miyo"


def test_new_without_profile_stores_null(inst, capsys):
    (inst / "config" / "vault-config.yaml").write_text(
        'concepts:\n  inbox: "In/"\n  atomic_note: "N/"\n', encoding="utf-8")
    stem = _new(capsys)["stem"]
    assert _meta(inst, stem).profile is None


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


@pytest.mark.parametrize("config, message", [
    ("concepts: [unclosed\n", "vault-config.yaml unreadable (ParserError)"),
    ("a: 2026-13-45\n", "vault-config.yaml unreadable (ValueError)"),
    ("- a\n- b\n", "vault-config.yaml is not a mapping"),
    ("", "vault-config.yaml is not a mapping"),
])
def test_new_unusable_config_exits_2_naming_the_failure(inst, capsys, config, message):
    (inst / "config" / "vault-config.yaml").write_text(config, encoding="utf-8")
    rc, out, err = _run(["new", "--template", TEMPLATE], capsys)
    assert rc == 2 and out == ""
    assert err == f"note-instructions: {message}\n"
    assert not note_meta.stage_root(inst).exists()


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


# The /note skill treats an exit 2 as refused, user-fixable input only when stderr
# starts with one of these prefixes (SKILL.md Rules); these tests pin that contract.
USER_FIXABLE_PREFIXES = ("note-instructions: --title", "note-instructions: --destination",
                         "note-instructions: --source")


@pytest.mark.parametrize(("extra", "prefix"), [
    (["--title", "   "], "note-instructions: --title"),
    (["--title", ".hidden"], "note-instructions: --title"),
    (["--title", "Design​review"], "note-instructions: --title"),
    (["--title", "Design {{date}}"], "note-instructions: --title"),
    (["--title", "Design <% tp.date %>"], "note-instructions: --title"),
    (["--destination", "/abs/"], "note-instructions: --destination"),
], ids=["blank", "dot-leading", "invisible", "double-brace", "templater", "absolute-destination"])
def test_stage_refused_input_starts_with_the_skill_prefix(inst, capsys, extra, prefix):
    stem = _staged(inst, capsys)
    rc, out, err = _stage(capsys, stem, *extra)
    assert rc == 2 and out == ""
    assert err.startswith(prefix), err


def test_new_source_outside_the_inbox_starts_with_the_skill_prefix(inst, capsys):
    rc, out, err = _run(["new", "--template", TEMPLATE, "--source", "Atlas/202 Notes/Filed.md"], capsys)
    assert rc == 2 and out == ""
    assert err.startswith("note-instructions: --source"), err


def test_non_fixable_exit_2_starts_with_no_skill_prefix(inst, capsys):
    rc, _, err = _stage(capsys, "2026-01-01_000000", "--title", "T")
    assert rc == 2 and err.startswith("note-instructions: unknown stem"), err
    assert not err.startswith(USER_FIXABLE_PREFIXES), err
    stem = _staged(inst, capsys)
    rc, _, err = _run(["deliver", "--stem", stem], capsys)
    assert rc == 2 and err.startswith("note-instructions: no title staged"), err
    assert not err.startswith(USER_FIXABLE_PREFIXES), err


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


# ── stage: source_link ───────────────────────────────────────────────────

SOURCE_STEM = SOURCE.rsplit("/", 1)[-1][:-3]
LINK_DRAFT = ("---\ntitle: x\nsource: \"{{source_link}}\"\n---\n# Notes\n"
              "From {{source_link}} " + MARKER + "\n")


def _note(inst, stem) -> str:
    return (note_meta.stage_dir(inst, stem) / "note.md").read_text(encoding="utf-8")


def _draft(inst, stem) -> str:
    return (note_meta.stage_dir(inst, stem) / "draft.md").read_text(encoding="utf-8")


def test_stage_resolves_source_link_to_wikilink_when_kept(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT)
    res = _json(_stage(capsys, stem, "--title", "T", "--keep-source", "true")[1])
    assert _note(inst, stem) == LINK_DRAFT.replace("{{source_link}}", f"[[{SOURCE_STEM}]]")
    assert res["check"]["ok"] is True


def test_stage_resolves_source_link_to_empty_when_deleted(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT)
    res = _json(_stage(capsys, stem, "--title", "T", "--keep-source", "false")[1])
    assert _note(inst, stem) == LINK_DRAFT.replace("{{source_link}}", "")
    assert res["check"]["ok"] is True


def test_stage_resolves_source_link_to_empty_without_source(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT, source_path=None, keep_source=True)
    res = _json(_stage(capsys, stem, "--title", "T")[1])
    assert _note(inst, stem) == LINK_DRAFT.replace("{{source_link}}", "")
    assert res["check"]["ok"] is True


def test_stage_leaves_fenced_and_escaped_source_link_alone(inst, capsys):
    draft = ("---\ntitle: x\n---\n```\n{{source_link}}\n```\n"
             "Escaped \\{{source_link}} and real {{source_link}}\n")
    stem = _staged(inst, capsys, draft=draft)
    _stage(capsys, stem, "--title", "T", "--keep-source", "true")
    assert _note(inst, stem) == draft.replace(
        "real {{source_link}}", f"real [[{SOURCE_STEM}]]")


def test_stage_never_rewrites_draft_md(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT)
    _stage(capsys, stem, "--title", "T", "--keep-source", "true")
    assert _draft(inst, stem) == LINK_DRAFT


def test_stage_re_resolves_after_keep_source_flips(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT)
    _stage(capsys, stem, "--title", "T", "--keep-source", "false")
    _stage(capsys, stem, "--keep-source", "true")
    assert _note(inst, stem) == LINK_DRAFT.replace("{{source_link}}", f"[[{SOURCE_STEM}]]")
    _stage(capsys, stem, "--keep-source", "false")
    assert _note(inst, stem) == LINK_DRAFT.replace("{{source_link}}", "")


def test_stage_frozen_keep_source_resolves_from_the_recorded_value(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT, keep_source=True,
                   steps_done=["note", "instructions_json"])
    res = _json(_stage(capsys, stem, "--keep-source", "false")[1])
    assert res["frozen"] is True
    assert _note(inst, stem) == LINK_DRAFT.replace("{{source_link}}", f"[[{SOURCE_STEM}]]")


def test_stage_still_fails_other_leftover_tokens(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT + "{{uuid}}\n")
    check = _json(_stage(capsys, stem, "--title", "T", "--keep-source", "true")[1])["check"]
    assert check["ok"] is False
    detail = next(f["detail"] for f in check["findings"] if f["check"] == "no_tokens")
    assert "uuid" in detail and "source_link" not in detail


def test_stage_missing_draft_removes_a_stale_note(inst, capsys):
    stem = _staged(inst, capsys, draft=LINK_DRAFT)
    _stage(capsys, stem, "--title", "T")
    (note_meta.stage_dir(inst, stem) / "draft.md").unlink()
    _stage(capsys, stem)
    assert not (note_meta.stage_dir(inst, stem) / "note.md").exists()


def test_resolve_source_link_is_pure(inst):
    meta = note_meta.new_meta(
        stem="2026-11-05_101500", inbox="In/", title="T", destination="A/",
        default_destination="A/", run_id="r", created="c", generated="g",
        template="T/t.md", template_stem="t", source_path="In/Sub/My note.md")
    meta.keep_source = True
    assert ni.resolve_source_link("a {{source_link}} b", meta) == "a [[My note]] b"


# ── destination validator ────────────────────────────────────────────────

VALID_FOLDERS = [("Atlas/Meetings", "Atlas/Meetings/"), ("Atlas/Meetings/", "Atlas/Meetings/"),
                 ("  Notes  ", "Notes/"), ("+", "+/"), ("A b/C d", "A b/C d/"),
                 ("v1.2/a~b", "v1.2/a~b/")]
INVALID_FOLDERS = ["", "   ", "/", "/abs/", " /abs", "Atlas/../x/", "a/ ../b", "a\\b",
                   "a/\n/b", "a\tb", "./a", "a/./b", "a//b", "a//", "..", None, 7,
                   # absolute: home tilde, drive letter
                   "~", "~/Notes", "~Archive", "C:", "C:/Users", "d:Notes",
                   # a segment led by a dot: hidden from Kado and Obsidian
                   ".obsidian", "Atlas/.trash", "a/ .x/b", "...",
                   # template syntax
                   "{{folder}}", "Meetings/<% tp.date.now() %>",
                   # invisible: Cf (zero-width space, BOM, bidi override), Zl, Zp
                   "a\u200bb", "\ufeffNotes", "a\u202eb", "a\u2028b", "a\u2029b"]


@pytest.mark.parametrize("value, expected", VALID_FOLDERS)
def test_vault_folder_accepts_relative_folders(value, expected):
    assert ni.vault_folder(value) == expected


@pytest.mark.parametrize("value", INVALID_FOLDERS)
def test_vault_folder_rejects_absolute_traversing_or_odd_paths(value):
    assert ni.vault_folder(value) is None


def test_vault_folder_keeps_the_unicode_form():
    nfc, nfd = (unicodedata.normalize(form, "Atlas/Größe") for form in ("NFC", "NFD"))
    assert nfc != nfd
    assert ni.vault_folder(nfc) == nfc + "/"
    assert ni.vault_folder(nfd) == nfd + "/"


@pytest.mark.parametrize("dest", [" /abs", "a/ ../b", "a\\b", "a/\n/b", "./a", "~/Atlas",
                                  "C:/Atlas", ".obsidian", "Atlas/.hidden", "{{dest}}",
                                  "\u200bAtlas", "At\u2028las"])
def test_stage_rejects_unsafe_destination_and_keeps_meta(inst, capsys, dest):
    stem = _staged(inst, capsys)
    before = (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes()
    rc, out, err = _stage(capsys, stem, "--destination", dest)
    assert rc == 2 and out == ""
    assert dest.strip() not in err
    assert (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes() == before


@pytest.mark.parametrize("dest", ["/etc", "Atlas/../../x", "' /etc'", "./Atlas", "'~/etc'",
                                  "'C:/etc'", "'.etc'", "'Atlas/{{etc}}'", '"At\\u200blas"'])
def test_new_unsafe_process_destination_falls_back_to_atomic_path(inst, capsys, dest):
    proc = inst / "config" / "note-processes"
    proc.mkdir()
    (proc / "t_meeting.md").write_text(f"---\ndestination: {dest}\n---\n", encoding="utf-8")
    rc, out, err = _run(["new", "--template", TEMPLATE], capsys)
    assert rc == 0
    res = _json(out)
    assert res["default_destination"] == "Atlas/202 Notes/"
    assert _meta(inst, res["stem"]).destination == "Atlas/202 Notes/"
    lines = [ln for ln in err.splitlines() if ln]
    assert len(lines) == 1 and "destination" in lines[0]
    assert "etc" not in err and "Atlas" not in err


PROCESS_DEST_ERR = ("note-instructions: process file ignored: destination is not a relative"
                    " vault folder\n")


# read_process refuses the destination and reports it as error; new prints that one line.
@pytest.mark.parametrize("dest", ["'../../x'", "'/'", "'a//b\\c'"])
def test_new_refused_process_destination_reports_the_process_file_error_once(inst, capsys, dest):
    proc = inst / "config" / "note-processes"
    proc.mkdir()
    (proc / "t_meeting.md").write_text(f"---\ndestination: {dest}\n---\n", encoding="utf-8")
    rc, out, err = _run(["new", "--template", TEMPLATE], capsys)
    assert rc == 0
    res = _json(out)
    assert res["default_destination"] == "Atlas/202 Notes/"
    assert _meta(inst, res["stem"]).destination == "Atlas/202 Notes/"
    assert err == PROCESS_DEST_ERR


@pytest.mark.parametrize("atomic", ['    path: "/abs/Notes"', '    path: "Atlas/../x"',
                                    '    path: "a\\\\b"', "    paths: []", '    path: "~/abs"',
                                    '    path: "C:/abs"', '    path: ".abs"',
                                    '    path: "N\\u200babs"'])
def test_new_invalid_atomic_path_exits_2_with_nothing_on_disk(inst, capsys, atomic):
    _config(inst, atomic)
    rc, out, err = _run(["new", "--template", TEMPLATE], capsys)
    assert rc == 2 and out == ""
    assert "atomic_note" in err and "abs" not in err
    assert not note_meta.stage_root(inst).exists()


def test_atomic_path_with_empty_paths_list_is_none():
    assert ni._atomic_path({"paths": []}) is None


# ── inbox validator ──────────────────────────────────────────────────────

INBOX_ERR = ("note-instructions: vault-config.yaml concepts.inbox is not a relative"
             " vault folder\n")
# YAML scalars written as concepts.inbox; None leaves the key out.
INVALID_INBOXES = ['"/abs"', '"../x"', '" In/../.."', '"Inbox\\\\x"', '"In\\nbox"',
                   '"In\\u200bbox"', '"In\\u2028box"', '"~/Inbox"', '"C:/Inbox"',
                   '".inbox"', '"In/{{x}}"', '""', "[]", None]


def _config_inbox(root: Path, inbox: str | None) -> None:
    line = "" if inbox is None else f"  inbox: {inbox}\n"
    (root / "config" / "vault-config.yaml").write_text(
        f'profile: "miyo"\nconcepts:\n{line}  atomic_note: "Atlas/202 Notes/"\n',
        encoding="utf-8")


@pytest.mark.parametrize("inbox", INVALID_INBOXES)
def test_new_invalid_inbox_exits_2_with_nothing_on_disk(inst, capsys, inbox):
    _config_inbox(inst, inbox)
    rc, out, err = _run(["new", "--template", TEMPLATE], capsys)
    assert rc == 2 and out == ""
    assert err == INBOX_ERR
    assert not note_meta.stage_root(inst).exists()


@pytest.mark.parametrize("inbox, expected", [('"100 Inbox"', "100 Inbox/"),
                                             ('"  100 Inbox/  "', "100 Inbox/")])
def test_config_reader_normalises_the_inbox(inst, inbox, expected):
    _config_inbox(inst, inbox)
    assert ni.read_note_config(Path("config/vault-config.yaml"))["inbox"] == expected


# ── note paths: --template and --source ─────────────────────────────────

VALID_NOTES = [("100 Inbox/Meeting raw.md", "100 Inbox/Meeting raw.md"), ("x.md", "x.md"),
               ("  In/v1.2 notes.md\n", "In/v1.2 notes.md"), ("In/Größe.md", "In/Größe.md")]
UNSAFE_NOTES = ["/abs/x.md", " /abs/x.md", "~/x.md", "C:/x.md", "../x.md", "In/../x.md",
                "./x.md", "In\\x.md", "In//x.md", "In/\nx.md", "In/x\u200b.md",
                "In/x\u2029y.md", ".obsidian/x.md", "In/.hidden.md", "In/.md",
                "In/{{x}}.md", "In/x.txt", "In/x.md/", "", None]


@pytest.mark.parametrize("value, expected", VALID_NOTES)
def test_vault_note_accepts_relative_md_paths(value, expected):
    assert ni.vault_note(value) == expected


@pytest.mark.parametrize("value", UNSAFE_NOTES)
def test_vault_note_rejects_unsafe_paths(value):
    assert ni.vault_note(value) is None


# Relative probes sit under the inbox, so the inbox check cannot mask the shape rule.
UNSAFE_NOTE_ARGS = ["/abs/x.md", " /abs/x.md", "~/x.md", "C:/x.md", "100 Inbox/../x.md",
                    "100 Inbox/./x.md", "100 Inbox\\x.md", "100 Inbox//x.md",
                    "100 Inbox/\nx.md", "100 Inbox/x\u200b.md", "100 Inbox/x\u2029y.md",
                    "100 Inbox/.hidden/x.md", "100 Inbox/.x.md", "100 Inbox/.md",
                    "100 Inbox/{{x}}.md", "100 Inbox/x.txt", "100 Inbox/x.md/"]


@pytest.mark.parametrize("flag", ["--template", "--source"])
@pytest.mark.parametrize("path", UNSAFE_NOTE_ARGS)
def test_new_rejects_unsafe_note_path_before_kado(inst, capsys, flag, path):
    argv = ["new", "--template", TEMPLATE, "--source", SOURCE]
    argv[argv.index(flag) + 1] = path
    rc, out, err = _run(argv, capsys)
    assert rc == 2 and out == ""
    assert f"{flag} must be a relative vault path" in err and path.strip() not in err
    assert FakeKado.reads == []
    assert not note_meta.stage_root(inst).exists()


def test_new_stores_stripped_note_paths(inst, capsys):
    rc, out, err = _run(["new", "--template", f" {TEMPLATE} ", "--source", f"{SOURCE}\n"],
                        capsys)
    assert rc == 0, err
    meta = _meta(inst, _json(out)["stem"])
    assert (meta.template, meta.template_stem, meta.source_path) == (
        TEMPLATE, "t_meeting", SOURCE)
    assert FakeKado.reads == [SOURCE]


@pytest.mark.parametrize("source", ["Atlas/202 Notes/Filed.md", "100 Inbox Archive/x.md",
                                    "100 Inbox.md", "x.md"])
def test_new_source_outside_the_inbox_exits_2_before_kado(inst, capsys, source):
    FakeKado.files[source] = "filed note\n"
    rc, out, err = _run(["new", "--template", TEMPLATE, "--source", source], capsys)
    assert rc == 2 and out == ""
    assert "--source" in err and "concepts.inbox" in err and source not in err
    assert FakeKado.reads == []
    assert not note_meta.stage_root(inst).exists()


@pytest.mark.parametrize("source", ["100 Inbox/Sub/Meeting raw.md", "100 inbox/Meeting raw.md"])
def test_new_accepts_a_source_anywhere_inside_the_inbox(inst, capsys, source):
    FakeKado.files[source] = "raw\n"
    out = _new(capsys, "--source", source)
    assert _meta(inst, out["stem"]).source_path == source


def test_new_source_inside_inbox_compares_unicode_forms(inst, capsys):
    _config_inbox(inst, '"Eingänge/"')
    source = unicodedata.normalize("NFD", "Eingänge/Notiz.md")
    FakeKado.files[source] = "raw\n"
    out = _new(capsys, "--source", source)
    assert _meta(inst, out["stem"]).source_path == source


# ── new: no half-made stage ──────────────────────────────────────────────


def _raise_oserror(*_a, **_k):
    raise OSError("disk full")


@pytest.mark.parametrize("target", ["write_meta", "atomic_write_text"])
def test_new_write_failure_removes_the_stage(inst, capsys, monkeypatch, target):
    monkeypatch.setattr(ni, target, _raise_oserror)
    rc, out, err = _run(["new", "--template", TEMPLATE, "--source", SOURCE], capsys)
    assert rc == 2 and out == ""
    root = note_meta.stage_root(inst)
    assert not root.exists() or not any(root.iterdir())


def test_new_writes_source_atomically(inst, capsys):
    stem = _new(capsys, "--source", SOURCE)["stem"]
    names = sorted(p.name for p in note_meta.stage_dir(inst, stem).iterdir())
    assert names == ["meta.json", "source.md"]


# ── stage: title ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw, expected", [
    ("  Design review  ", "Design review"), ("foo.", "foo"), ("foo . .", "foo"),
    ("v1.2 notes", "v1.2 notes"), ("Größe – ok", "Größe – ok"),
])
def test_stage_trims_title_and_trailing_dots(inst, capsys, raw, expected):
    stem = _staged(inst, capsys)
    res = _json(_stage(capsys, stem, "--title", raw)[1])
    assert res["title"] == expected
    assert res["inbox_file"] == f"100 Inbox/{stem}_{expected}.md"
    assert _meta(inst, stem).title == expected


@pytest.mark.parametrize("raw", ["a\nb", "line\n", "tab\there", "bell\x07", "...", " . ", "\x7f",
                                 "Design​review", "Design review", "﻿Title",
                                 "Design ", ".hidden", " .env", "{{title}}",
                                 "<% tp.file.title %>"])
def test_stage_rejects_unsafe_or_empty_titles(inst, capsys, raw):
    stem = _staged(inst, capsys)
    before = (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes()
    rc, out, _ = _stage(capsys, stem, "--title", raw)
    assert rc == 2 and out == ""
    assert (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes() == before


@pytest.mark.parametrize("raw", [f"{MARKER}​", f".{MARKER}", "{{" + MARKER + "}}"])
def test_stage_title_rejection_never_echoes_the_title(inst, capsys, raw):
    stem = _staged(inst, capsys)
    rc, out, err = _stage(capsys, stem, "--title", raw)
    assert rc == 2 and "--title" in err
    assert MARKER not in out and MARKER not in err


# ── joiners: owner decision 2026-11-05 ──────────────────────────────────

TECHNOLOGIST = "\U0001F469\u200d\U0001F4BB"          # woman technologist, joined by U+200D
ZWNJ_WORD = "می\u200cخواهم"  # Persian, U+200C inside


@pytest.mark.parametrize("name", [TECHNOLOGIST, ZWNJ_WORD])
def test_stage_accepts_joiners_in_title_and_destination(inst, capsys, name):
    stem = _staged(inst, capsys)
    rc, out, err = _stage(capsys, stem, "--title", f"{name} notes",
                          "--destination", f"Atlas/{name}")
    assert rc == 0, err
    meta = _meta(inst, stem)
    assert (meta.title, meta.destination) == (f"{name} notes", f"Atlas/{name}/")


@pytest.mark.parametrize("bad", ["\u200b", "\ufeff", "\u202e", "\u2028"])
@pytest.mark.parametrize("flag", ["--title", "--destination"])
def test_stage_still_rejects_other_invisible_characters(inst, capsys, bad, flag):
    stem = _staged(inst, capsys)
    rc, out, _ = _stage(capsys, stem, flag, f"At{bad}las")
    assert rc == 2 and out == ""


# ── deliver ──────────────────────────────────────────────────────────────

import note_fake_vault as nfv  # noqa: E402
from lib.doc_frontmatter import build_tomo_block  # noqa: E402
from lib.kado_client import KadoConcurrencyError  # noqa: E402

TITLE = "Design review"
DEST = "Atlas/Meetings"
WRITES = ("write_note", "write_file", "write_frontmatter")
STEP_CALL = {"note": "write_note", "instructions_json": "write_file",
             "instructions_md": "write_note", "source_mark": "write_frontmatter"}
DELIVER_KEYS = {"status", "step", "note_path", "instructions_json", "instructions_md",
                "source_marked", "steps_done", "frozen", "exists_path"}
HASHI_SCHEMA = SCRIPTS_DIR.parent / "schemas" / "hashi-instructions.schema.json"


@pytest.fixture
def vault(inst, monkeypatch):
    """A fake vault holding the source; note-instructions.py talks only to it."""
    fake = nfv.NoteFakeVault({SOURCE: f"raw meeting text {MARKER}\n"})
    monkeypatch.setattr(ni, "KadoClient", fake)
    return fake


def _ready(inst, capsys, vault, draft=GOOD_DRAFT, *extra, source=True):
    """A staged draft with title and destination; the vault's call log is cleared."""
    stem = _new(capsys, *(["--source", SOURCE] if source else []))["stem"]
    (note_meta.stage_dir(inst, stem) / "draft.md").write_text(draft, encoding="utf-8")
    rc, _, err = _stage(capsys, stem, "--title", TITLE, "--destination", DEST, *extra)
    assert rc == 0, err
    vault.events.clear()
    return stem


def _deliver(capsys, stem):
    """Return (rc, exists line or None, output dict, raw stdout, stderr)."""
    rc, out, err = _run(["deliver", "--stem", stem], capsys)
    lines = out.splitlines()
    exists = lines.pop(0) if lines and lines[0].startswith("EXISTS:") else None
    return rc, exists, (json.loads(lines[0]) if lines else None), out, err


def _paths(inst, stem):
    meta = _meta(inst, stem)
    pair = f"100 Inbox/{stem}_instructions"
    return meta, meta.inbox_file, pair + ".json", pair + ".md"


def _write_events(vault):
    return [e for e in vault.events if e[0] in WRITES]


def _tomo(vault, path):
    return nfv.split_frontmatter(vault.text(path))[0]["tomo"]


def test_deliver_writes_note_json_md_then_marks_source_in_order(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, note, js, md = _paths(inst, stem)
    rc, exists, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert exists is None and set(out) == DELIVER_KEYS
    assert out == {"status": "delivered", "step": "", "note_path": note,
                   "instructions_json": js, "instructions_md": md,
                   "source_marked": True, "steps_done": list(note_meta.STEPS),
                   "frozen": True, "exists_path": ""}
    assert _write_events(vault) == [("write_note", note), ("write_file", js),
                                    ("write_note", md), ("write_frontmatter", SOURCE)]


@pytest.mark.parametrize("index, step", list(enumerate(note_meta.STEPS)))
def test_deliver_failure_at_a_step_stops_every_later_step(inst, capsys, vault, index, step):
    stem = _ready(inst, capsys, vault)
    meta, note, js, md = _paths(inst, stem)
    target = [note, js, md, SOURCE][index]
    vault.fail[(STEP_CALL[step], target)] = KadoError("503 after retries")
    rc, exists, out, raw, err = _deliver(capsys, stem)
    assert rc == 1 and exists is None
    assert out["status"] == "failed" and out["step"] == step
    assert out["steps_done"] == list(note_meta.STEPS[:index])
    assert out["frozen"] is True
    assert out["source_marked"] is False and vault.merges == []
    assert _write_events(vault)[-1] == (STEP_CALL[step], target)
    assert len(_write_events(vault)) == index + 1
    after = _meta(inst, stem)
    assert after.steps_done == list(note_meta.STEPS[:index]) and after.failed_step == step
    assert MARKER not in raw + err and "503" not in raw


def test_deliver_failure_at_instructions_md_freezes_keep_source(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, _, _, md = _paths(inst, stem)
    vault.fail[("write_note", md)] = KadoError("503")
    assert _deliver(capsys, stem)[0] == 1
    res = _json(_stage(capsys, stem, "--keep-source", "true")[1])
    assert res["frozen"] is True and _meta(inst, stem).keep_source is False


def test_deliver_failure_at_instructions_json_freezes_keep_source(inst, capsys, vault):
    """The upload failed: Kado may have written the set before the error reached us."""
    stem = _ready(inst, capsys, vault)
    _, _, js, _ = _paths(inst, stem)
    vault.fail[("write_file", js)] = KadoError("503")
    assert _deliver(capsys, stem)[0] == 1
    res = _json(_stage(capsys, stem, "--keep-source", "true")[1])
    assert res["frozen"] is True and _meta(inst, stem).keep_source is False


def _session_start(capsys):
    spec = importlib.util.spec_from_file_location("note_session", SCRIPTS_DIR / "note-session.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["start", "--args=x"]) == 0
    return json.loads(capsys.readouterr()[0])


def test_deliver_killed_between_steps_is_a_kept_draft_not_a_stale_stage(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, _, js, _ = _paths(inst, stem)
    vault.fail[("write_file", js)] = nfv.Killed()
    with pytest.raises(nfv.Killed):
        ni.main(["deliver", "--stem", stem])
    capsys.readouterr()
    meta = _meta(inst, stem)
    assert meta.steps_done == ["note"] and meta.failed_step == "instructions_json"
    start = _session_start(capsys)
    assert [d["stem"] for d in start["kept_drafts"]] == [stem]
    assert stem not in start["stale_stages"]


def test_deliver_resume_identical_note_counts_as_done(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, note, js, md = _paths(inst, stem)
    vault.fail[("write_file", js)] = KadoError("503")
    assert _deliver(capsys, stem)[0] == 1
    landed = vault.text(note)
    vault.fail.clear()
    vault.events.clear()
    rc, _, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert out["status"] == "delivered" and out["source_marked"] is True
    assert _write_events(vault) == [("write_file", js), ("write_note", md),
                                    ("write_frontmatter", SOURCE)]
    assert vault.text(note) == landed


def test_deliver_resume_identical_unrecorded_note_counts_as_done(inst, capsys, vault):
    """A run that wrote the note and died before meta.json recorded it."""
    stem = _ready(inst, capsys, vault)
    _, note, js, _ = _paths(inst, stem)
    vault.fail[("write_file", js)] = nfv.Killed()
    with pytest.raises(nfv.Killed):
        ni.main(["deliver", "--stem", stem])
    capsys.readouterr()
    stage = note_meta.stage_dir(inst, stem)
    meta = note_meta.read_meta(stage)
    meta.steps_done = []
    note_meta.write_meta(stage, meta)
    vault.fail.clear()
    vault.events.clear()
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 0 and out["status"] == "delivered"
    assert ("write_note", note) not in _write_events(vault)


def test_deliver_first_step_landed_but_unrecorded_is_a_kept_draft_that_resumes(
        inst, capsys, vault, monkeypatch):
    """The note lands, then the meta.json write recording it fails: never a stale stage."""
    stem = _ready(inst, capsys, vault)
    _, note, js, md = _paths(inst, stem)
    real_write_meta = ni.write_meta

    def record_fails(stage, meta):
        if meta.steps_done == ["note"]:
            raise OSError("disk full")
        real_write_meta(stage, meta)

    monkeypatch.setattr(ni, "write_meta", record_fails)
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 2 and out is None
    assert _write_events(vault) == [("write_note", note)]
    monkeypatch.setattr(ni, "write_meta", real_write_meta)
    meta = _meta(inst, stem)
    assert meta.steps_done == [] and meta.failed_step == "note"
    start = _session_start(capsys)
    assert [d["stem"] for d in start["kept_drafts"]] == [stem]
    assert start["kept_drafts"][0]["frozen"] is True
    assert stem not in start["stale_stages"]
    before = (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes()
    res = _json(_stage(capsys, stem, "--title", "Other")[1])
    assert res["frozen"] is True and res["inbox_file"] == note
    assert (note_meta.stage_dir(inst, stem) / "meta.json").read_bytes() == before
    vault.events.clear()
    rc, _, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert out["status"] == "delivered"
    assert _write_events(vault) == [("write_file", js), ("write_note", md),
                                    ("write_frontmatter", SOURCE)]


def test_deliver_trailing_newline_alone_is_identical(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, note, js, _ = _paths(inst, stem)
    vault.fail[("write_file", js)] = KadoError("503")
    _deliver(capsys, stem)
    vault.files[note] = vault.text(note).rstrip("\n")
    vault.fail.clear()
    assert _deliver(capsys, stem)[0] == 0


@pytest.mark.parametrize("recorded", [True, False])
def test_deliver_resume_different_note_exits_3_and_changes_nothing(
        inst, capsys, vault, recorded):
    stem = _ready(inst, capsys, vault)
    _, note, js, _ = _paths(inst, stem)
    vault.fail[("write_file", js)] = KadoError("503")
    _deliver(capsys, stem)
    vault.files[note] = "other text"
    if not recorded:
        stage = note_meta.stage_dir(inst, stem)
        meta = note_meta.read_meta(stage)
        meta.steps_done = []
        note_meta.write_meta(stage, meta)
    before = _meta(inst, stem)
    vault.fail.clear()
    vault.events.clear()
    rc, exists, out, raw, _ = _deliver(capsys, stem)
    assert rc == 3 and raw.splitlines()[0] == f"EXISTS:{note}" and exists == f"EXISTS:{note}"
    assert out["status"] == "exists" and out["exists_path"] == note and out["step"] == "note"
    assert out["steps_done"] == (["note"] if recorded else [])
    assert vault.files[note] == "other text"
    assert _write_events(vault) == [] and vault.merges == []
    assert _meta(inst, stem) == before


def test_deliver_resume_taken_instruction_set_name_exits_3(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, note, js, _ = _paths(inst, stem)
    vault.fail[("write_file", js)] = KadoError("503")
    _deliver(capsys, stem)
    vault.files[js] = b"{}"
    vault.fail.clear()
    vault.events.clear()
    rc, exists, out, _, _ = _deliver(capsys, stem)
    assert rc == 3 and exists == f"EXISTS:{js}" and out["step"] == "instructions_json"
    assert out["steps_done"] == ["note"]
    assert vault.files[js] == b"{}" and _write_events(vault) == []


def test_deliver_destination_clash_exits_3_before_any_write(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    taken = f"{DEST}/{TITLE}.md"
    vault.files[taken] = "filed earlier"
    rc, exists, out, _, _ = _deliver(capsys, stem)
    assert rc == 3 and exists == f"EXISTS:{taken}"
    assert out["status"] == "exists" and out["exists_path"] == taken and out["step"] == ""
    assert out["steps_done"] == [] and out["frozen"] is False
    assert _write_events(vault) == []
    meta = _meta(inst, stem)
    assert meta.steps_done == [] and meta.failed_step == ""


def test_deliver_refuses_a_set_the_guards_cut(inst, capsys, vault, monkeypatch):
    real = ni.build_note_actions

    def unjustified(meta):
        actions = real(meta)
        actions[-1].pop("depends_on")
        return actions

    monkeypatch.setattr(ni, "build_note_actions", unjustified)
    stem = _ready(inst, capsys, vault)
    rc, exists, out, _, _ = _deliver(capsys, stem)
    assert rc == 1 and exists is None and out["status"] == "withdrawn"
    assert _write_events(vault) == []
    assert note_meta.stage_dir(inst, stem).is_dir()


@pytest.mark.parametrize("draft", [BAD_DRAFT, "---\ntitle: x\n# no close\n", None])
def test_deliver_refuses_a_failing_filled_note_check(inst, capsys, vault, draft):
    stem = _ready(inst, capsys, vault)
    path = note_meta.stage_dir(inst, stem) / "draft.md"
    if draft is None:
        path.unlink()
    else:
        path.write_text(draft, encoding="utf-8")
    rc, _, out, raw, err = _deliver(capsys, stem)
    assert rc == 1 and out["status"] == "failed" and out["step"] == ""
    assert vault.events == []
    assert MARKER not in raw + err
    assert _meta(inst, stem).failed_step == ""


def _unconfigured_kado(monkeypatch):
    """The real KadoClient with no URL or token resolvable: its constructor's only raise."""
    from lib import kado_client
    monkeypatch.setattr(kado_client, "_resolve_config", lambda url, token: (None, None))
    monkeypatch.setattr(ni, "KadoClient", kado_client.KadoClient)


def test_deliver_missing_kado_config_fails_at_kado_config_and_keeps_the_draft(
        inst, capsys, vault, monkeypatch):
    stem = _ready(inst, capsys, vault)
    _unconfigured_kado(monkeypatch)
    rc, exists, out, raw, err = _deliver(capsys, stem)
    assert rc == 1 and exists is None
    assert out["status"] == "failed" and out["step"] == note_meta.KADO_CONFIG == "kado_config"
    assert out["frozen"] is False
    assert "not configured" in err and "reach" not in err
    assert _write_events(vault) == [] and "KADO_TOKEN" not in raw
    meta = _meta(inst, stem)
    assert meta.steps_done == [] and meta.failed_step == "kado_config"
    start = _session_start(capsys)
    assert [d["stem"] for d in start["kept_drafts"]] == [stem]
    assert start["kept_drafts"][0]["failed_step"] == "kado_config"
    assert start["kept_drafts"][0]["frozen"] is False
    assert stem not in start["stale_stages"]
    res = _json(_stage(capsys, stem, "--title", "Other")[1])
    assert res["frozen"] is False and res["title"] == "Other"


@pytest.mark.parametrize("error", [TimeoutError("timed out"),
                                   http.client.IncompleteRead(b"", 10)],
                         ids=["TimeoutError", "IncompleteRead"])
def test_deliver_kado_transport_error_fails_at_note_and_keeps_the_draft(
        inst, capsys, vault, monkeypatch, error):
    """The real KadoClient over a transport that breaks mid-response: exit 1 step note, not exit 2."""
    from lib import kado_client
    stem = _ready(inst, capsys, vault)
    monkeypatch.setattr(kado_client, "_resolve_config", lambda url, token: ("http://kado.test", "t"))
    monkeypatch.setattr(ni, "KadoClient", kado_client.KadoClient)

    def broken_transport(*_a, **_k):
        raise error

    monkeypatch.setattr(kado_client.urllib.request, "urlopen", broken_transport)
    rc, exists, out, raw, err = _deliver(capsys, stem)
    assert rc == 1 and exists is None, err
    assert out["status"] == "failed" and out["step"] == "note"
    # Accepted trade-off: an outage at the first upload freezes the name, since the write may have landed.
    assert out["frozen"] is True
    assert "KadoConnectionError" in err and MARKER not in raw + err
    meta = _meta(inst, stem)
    assert meta.steps_done == [] and meta.failed_step == "note"


def test_deliver_resume_after_kado_config_delivers_from_scratch(
        inst, capsys, vault, monkeypatch):
    stem = _ready(inst, capsys, vault)
    _, note, js, md = _paths(inst, stem)
    _unconfigured_kado(monkeypatch)
    assert _deliver(capsys, stem)[0] == 1
    monkeypatch.setattr(ni, "KadoClient", vault)
    rc, _, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert out["status"] == "delivered" and out["step"] == "" and out["source_marked"] is True
    assert _write_events(vault) == [("write_note", note), ("write_file", js),
                                    ("write_note", md), ("write_frontmatter", SOURCE)]
    assert not note_meta.stage_dir(inst, stem).exists()


def test_deliver_stamp_failure_reports_an_empty_step(inst, capsys, vault, monkeypatch):
    def refuse(*_a, **_k):
        raise ni.FrontmatterMergeError("frontmatter is not a mapping")

    stem = _ready(inst, capsys, vault)
    monkeypatch.setattr(ni, "merge_tomo_block_into_markdown", refuse)
    rc, _, out, raw, err = _deliver(capsys, stem)
    assert rc == 1 and out["status"] == "failed" and out["step"] == ""
    assert vault.events == [] and MARKER not in raw + err
    assert _meta(inst, stem).failed_step == ""


def test_deliver_without_title_exits_2(inst, capsys, vault):
    stem = _new(capsys, "--source", SOURCE)["stem"]
    (note_meta.stage_dir(inst, stem) / "draft.md").write_text(GOOD_DRAFT, encoding="utf-8")
    vault.events.clear()
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 2 and vault.events == []


@pytest.mark.parametrize("stem", ["2026-01-01_000000", "../etc"])
def test_deliver_unknown_or_malformed_stem_exits_2(inst, capsys, vault, stem):
    assert _deliver(capsys, stem)[0] == 2


def _clock(monkeypatch, value):
    import lib.doc_frontmatter as dfm
    monkeypatch.setattr(dfm, "_utc_now", lambda: value)


def test_two_deliver_runs_produce_byte_identical_files(inst, capsys, vault, monkeypatch):
    stem = _ready(inst, capsys, vault)
    stage = note_meta.stage_dir(inst, stem)
    saved = {p.name: p.read_bytes() for p in stage.iterdir()}
    _, note, js, md = _paths(inst, stem)
    _clock(monkeypatch, "2030-01-01T00:00:00Z")
    assert _deliver(capsys, stem)[0] == 0
    first = {p: vault.files[p] for p in (note, js, md)}
    stage.mkdir(parents=True)
    for name, data in saved.items():
        (stage / name).write_bytes(data)
    second_vault = nfv.NoteFakeVault({SOURCE: "raw\n"})
    monkeypatch.setattr(ni, "KadoClient", second_vault)
    _clock(monkeypatch, "2031-06-06T06:06:06Z")
    assert _deliver(capsys, stem)[0] == 0
    assert {p: second_vault.files[p] for p in (note, js, md)} == first


def test_deliver_stamps_note_peer_and_source(inst, capsys, vault):
    import jsonschema
    stem = _ready(inst, capsys, vault)
    meta, note, js, md = _paths(inst, stem)
    assert _deliver(capsys, stem)[0] == 0
    note_block, md_block = _tomo(vault, note), _tomo(vault, md)
    assert (note_block["doc_type"], note_block["state"]) == ("rendered-note", "pending-move")
    assert (md_block["doc_type"], md_block["state"]) == ("instructions", "pending-apply")
    assert note_block["run_id"] == md_block["run_id"] == meta.run_id
    assert note_block["updated_at"] == md_block["updated_at"] == meta.generated
    [merge] = vault.merges
    expected = build_tomo_block("source", "captured", meta.run_id)
    block = merge["frontmatter"]["tomo"]
    assert set(merge["frontmatter"]) == {"tomo"} and merge["mode"] == "merge"
    assert {k: v for k, v in block.items() if k != "updated_at"} == \
        {k: v for k, v in expected.items() if k != "updated_at"}
    assert merge["expected_modified"] == 1
    doc = json.loads(vault.files[js].decode("utf-8"))
    jsonschema.validate(instance=doc, schema=json.loads(HASHI_SCHEMA.read_text(encoding="utf-8")))
    assert doc["md_peer"] == f"{stem}_instructions" and doc["generated"] == meta.generated
    assert [a["action"] for a in doc["actions"]] == ["move_note", "delete_source"]
    assert doc["actions"][1]["depends_on"] == ["I01"]


def test_deliver_uploads_the_draft_with_source_link_resolved(inst, capsys, vault):
    stem = _ready(inst, capsys, vault, LINK_DRAFT)
    _, note, _, _ = _paths(inst, stem)
    assert _deliver(capsys, stem)[0] == 0
    _, body = nfv.split_frontmatter(vault.text(note))
    assert "{{source_link}}" not in vault.text(note)
    assert body == LINK_DRAFT.split("---\n", 2)[2].replace("{{source_link}}", "")


def test_deliver_kept_source_has_no_delete_and_is_still_marked(inst, capsys, vault):
    stem = _ready(inst, capsys, vault, GOOD_DRAFT, "--keep-source", "true")
    _, _, js, _ = _paths(inst, stem)
    assert _deliver(capsys, stem)[0] == 0
    doc = json.loads(vault.files[js].decode("utf-8"))
    assert [a["action"] for a in doc["actions"]] == ["move_note"]
    assert len(vault.merges) == 1


def test_deliver_without_source_marks_nothing(inst, capsys, vault):
    stem = _ready(inst, capsys, vault, source=False)
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 0 and out["source_marked"] is False and vault.merges == []
    assert [e[0] for e in _write_events(vault)] == ["write_note", "write_file", "write_note"]


def test_deliver_source_changed_before_mark_fails_and_resume_retries(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    vault.fail[("write_frontmatter", SOURCE)] = KadoConcurrencyError("expectedModified mismatch")
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 1 and out["step"] == "source_mark"
    vault.fail.clear()
    vault.events.clear()
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 0 and out["source_marked"] is True
    assert _write_events(vault) == [("write_frontmatter", SOURCE)]


GONE_BEFORE_READ = "before_read"
GONE_AT_WRITE = "at_write"


def _source_gone_at(vault, where):
    """Delete the source before the mark reads it, or let Kado lose it at the write."""
    if where == GONE_BEFORE_READ:
        del vault.files[SOURCE]
    elif where == GONE_AT_WRITE:
        vault.fail[("write_frontmatter", SOURCE)] = KadoNotFoundError("Path not found")
    else:
        raise AssertionError(f"unknown case {where}")


def _assert_delivered_unmarked(inst, capsys, stem):
    rc, exists, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert exists is None and out["status"] == "delivered" and out["step"] == ""
    assert out["source_marked"] is False
    assert not note_meta.stage_dir(inst, stem).exists()


@pytest.mark.parametrize("where", [GONE_BEFORE_READ, GONE_AT_WRITE])
def test_deliver_source_gone_before_the_mark_is_delivered_unmarked(inst, capsys, vault, where):
    """Falsifies treating KadoNotFoundError on the mark as a failed step."""
    stem = _ready(inst, capsys, vault)
    _source_gone_at(vault, where)
    _assert_delivered_unmarked(inst, capsys, stem)
    assert vault.merges == []


def test_deliver_resume_after_mark_failure_with_source_gone_is_delivered(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    vault.fail[("write_frontmatter", SOURCE)] = KadoError("503")
    assert _deliver(capsys, stem)[0] == 1
    assert _meta(inst, stem).failed_step == "source_mark"
    vault.fail.clear()
    del vault.files[SOURCE]
    _assert_delivered_unmarked(inst, capsys, stem)


@pytest.mark.parametrize("method", ["read_frontmatter", "write_frontmatter"])
def test_deliver_other_kado_error_on_the_mark_still_fails(inst, capsys, vault, method):
    """Falsifies swallowing every KadoError on the mark, not only not-found."""
    from lib.kado_client import KadoToolError
    stem = _ready(inst, capsys, vault)
    vault.fail[(method, SOURCE)] = KadoToolError("VALIDATION_ERROR")
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 1 and out["status"] == "failed" and out["step"] == "source_mark"
    assert out["source_marked"] is False and vault.merges == []
    assert _meta(inst, stem).failed_step == "source_mark"


def test_deliver_mark_without_a_modified_time_fails_unwritten(inst, capsys, vault):
    """Falsifies an unguarded merge when read_frontmatter returns no modified."""
    stem = _ready(inst, capsys, vault)
    vault.modified[SOURCE] = None
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 1 and out["status"] == "failed" and out["step"] == "source_mark"
    assert ("write_frontmatter", SOURCE) not in vault.events and vault.merges == []
    assert note_meta.stage_dir(inst, stem).is_dir()


def test_deliver_mark_is_guarded_by_the_modified_time_it_read(inst, capsys, vault):
    """Falsifies guarding the merge with any value but the modified time just read."""
    stem = _ready(inst, capsys, vault)
    vault.modified[SOURCE] = 1762337100123
    rc, _, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert out["source_marked"] is True
    assert [m["expected_modified"] for m in vault.merges] == [1762337100123]


def _killed_before_stage_removal(inst, capsys, vault, monkeypatch, stem):
    def die(*_a, **_k):
        raise nfv.Killed()

    with monkeypatch.context() as m:
        m.setattr(ni, "remove_stage", die)
        with pytest.raises(nfv.Killed):
            ni.main(["deliver", "--stem", stem])
    capsys.readouterr()
    assert "source_mark" in _meta(inst, stem).steps_done


OTHER_RUN_ID = "2026-11-04T09-00-00Z-0a1b2c"


def _as_marked(vault):
    """Leave the source as the killed run's merge left it: this draft's source/captured."""


def _source_deleted(vault):
    del vault.files[SOURCE]


def _mark_changed(**changes):
    """Change fields of the killed run's own mark; the rest stays as the merge wrote it."""
    def rewrite(vault):
        frontmatter, body = nfv.split_frontmatter(vault.text(SOURCE))
        frontmatter["tomo"].update(changes)
        vault.files[SOURCE] = f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n{body}"
    return rewrite


def _frontmatter_replaced(yaml_text):
    """Replace the source's frontmatter with `yaml_text`; the body stays."""
    def rewrite(vault):
        _, body = nfv.split_frontmatter(vault.text(SOURCE))
        vault.files[SOURCE] = f"---\n{yaml_text}---\n{body}"
    return rewrite


# What the source holds when the resume reads it, and the source_marked it must report.
RECORDED_MARK_CASES = [
    pytest.param(_as_marked, True, id="this-run-captured"),
    pytest.param(_source_deleted, False, id="source-deleted"),
    pytest.param(_mark_changed(run_id=OTHER_RUN_ID), False, id="other-run-captured"),
    # applied: a real lifecycle state (doc-frontmatter.schema.json), not captured
    pytest.param(_mark_changed(state="applied"), False, id="this-run-applied"),
    pytest.param(_frontmatter_replaced("aliases: [Meeting raw]\n"), False, id="no-tomo-key"),
    pytest.param(_frontmatter_replaced("tomo: captured\n"), False, id="tomo-not-a-mapping"),
    pytest.param(_frontmatter_replaced("captured\n"), False, id="frontmatter-not-a-mapping"),
]


@pytest.mark.parametrize("rewrite, marked", RECORDED_MARK_CASES)
def test_deliver_resume_with_mark_recorded_reports_the_real_mark(
        inst, capsys, vault, monkeypatch, rewrite, marked):
    """A run killed after recording source_mark: the resume reports what the source carries.

    Only a tomo: mapping with state captured and this draft's run id counts.
    Falsifies dropping the run id check (other-run-captured), the state check
    (this-run-applied), the mapping check on the block (no-tomo-key,
    tomo-not-a-mapping) or on the frontmatter (frontmatter-not-a-mapping).
    """
    stem = _ready(inst, capsys, vault)
    _killed_before_stage_removal(inst, capsys, vault, monkeypatch, stem)
    rewrite(vault)
    held = vault.files.get(SOURCE)
    vault.events.clear()
    rc, _, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert out["status"] == "delivered" and out["source_marked"] is marked
    assert ("write_frontmatter", SOURCE) not in vault.events
    assert vault.files.get(SOURCE) == held
    assert not note_meta.stage_dir(inst, stem).exists()


def test_deliver_resume_with_mark_recorded_fails_on_another_kado_error(
        inst, capsys, vault, monkeypatch):
    """Falsifies reading every KadoError, not only not-found, as a source without the mark.

    Every file is delivered, yet the step fails until the read succeeds; that resume finishes.
    """
    stem = _ready(inst, capsys, vault)
    _killed_before_stage_removal(inst, capsys, vault, monkeypatch, stem)
    vault.fail[("read_frontmatter", SOURCE)] = KadoError("503 after retries")
    rc, _, out, _, _ = _deliver(capsys, stem)
    assert rc == 1 and out["status"] == "failed" and out["step"] == "source_mark"
    assert out["source_marked"] is False
    meta = _meta(inst, stem)
    assert meta.failed_step == "source_mark" and "source_mark" in meta.steps_done
    vault.fail.clear()
    vault.events.clear()
    rc, _, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert out["status"] == "delivered" and out["source_marked"] is True
    assert ("write_frontmatter", SOURCE) not in vault.events


def test_deliver_success_removes_the_stage_dir(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    assert _deliver(capsys, stem)[0] == 0
    assert not note_meta.stage_dir(inst, stem).exists()


def test_deliver_failure_keeps_the_stage_dir(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, note, _, _ = _paths(inst, stem)
    vault.fail[("write_note", note)] = KadoError("503")
    _deliver(capsys, stem)
    assert (note_meta.stage_dir(inst, stem) / "meta.json").is_file()


def test_deliver_prints_no_user_text(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, _, out, raw, err = _deliver(capsys, stem)
    assert MARKER not in raw + err and "raw meeting text" not in raw + err


def test_deliver_stays_within_the_kado_call_budget(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    assert _deliver(capsys, stem)[0] == 0
    assert len(vault.events) <= 16


# ── the no-overwrite probe exists twice (ADR-2): one contract ────────────


def _kado_write_file_no_overwrite(tmp_path, monkeypatch, capsys, vault, path):
    spec = importlib.util.spec_from_file_location(
        "kado_write_file", SCRIPTS_DIR / "kado-write-file.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    local = tmp_path / "payload.md"
    local.write_text("payload", encoding="utf-8")
    monkeypatch.setattr(mod, "KadoClient", vault)
    monkeypatch.setattr(sys, "argv", ["kado-write-file.py", "--no-overwrite",
                                      "--local", str(local), "--vault", path])
    rc = mod.main()
    return rc, capsys.readouterr()[0]


def _deliver_no_overwrite(inst, capsys, vault):
    stem = _ready(inst, capsys, vault)
    _, note, _, _ = _paths(inst, stem)
    vault.files[note] = "taken"
    rc, out, _ = _run(["deliver", "--stem", stem], capsys)
    return rc, out, note


@pytest.mark.parametrize("script", ["deliver", "kado-write-file"])
def test_both_no_overwrite_probes_share_exit_3_and_the_exists_line(
        inst, capsys, vault, monkeypatch, script):
    if script == "deliver":
        rc, out, path = _deliver_no_overwrite(inst, capsys, vault)
    else:
        path = "100 Inbox/taken.md"
        vault.files[path] = "taken"
        rc, out = _kado_write_file_no_overwrite(inst, monkeypatch, capsys, vault, path)
    assert rc == 3
    assert out.splitlines()[0] == f"EXISTS:{path}"
    assert vault.files[path] == "taken"
    assert [e for e in vault.events if e[0] in WRITES] == []


def test_deliver_instructions_md_carries_no_templater_hint(inst, capsys, vault):
    """A /note note has no template syntax left, so the MD must not ask for Templater."""
    stem = _ready(inst, capsys, vault)
    _, _, _, md = _paths(inst, stem)
    assert _deliver(capsys, stem)[0] == 0
    assert "Templater" not in vault.text(md)


def test_deliver_recorded_step_with_absent_target_is_not_rewritten(inst, capsys, vault):
    """Hashi may already have moved the note away; a second copy would be a duplicate."""
    stem = _ready(inst, capsys, vault)
    _, note, js, md = _paths(inst, stem)
    vault.fail[("write_file", js)] = KadoError("503")
    assert _deliver(capsys, stem)[0] == 1
    del vault.files[note]
    vault.fail.clear()
    vault.events.clear()
    rc, _, out, _, err = _deliver(capsys, stem)
    assert rc == 0, err
    assert out["status"] == "delivered"
    assert ("write_note", note) not in _write_events(vault)
    assert note not in vault.files


# ── the fake vault behaves like lib.kado_client.KadoClient ──────────────


def test_fake_write_frontmatter_on_an_absent_note_raises_not_found():
    fake = nfv.NoteFakeVault()
    with pytest.raises(KadoNotFoundError):
        fake.write_frontmatter("100 Inbox/gone.md", {"a": 1})
    assert fake.merges == [] and fake.files == {}


def test_fake_write_frontmatter_stale_modified_raises_concurrency():
    fake = nfv.NoteFakeVault({"n.md": "---\na: 1\n---\nbody\n"})
    with pytest.raises(KadoConcurrencyError):
        fake.write_frontmatter("n.md", {"b": 2}, expected_modified=7)
    assert fake.text("n.md") == "---\na: 1\n---\nbody\n" and fake.merges == []


def test_fake_write_frontmatter_honours_replace_and_rejects_other_modes():
    from lib.kado_client import KadoToolError
    fake = nfv.NoteFakeVault({"n.md": "---\na: 1\n---\nbody\n"})
    fake.write_frontmatter("n.md", {"b": 2}, mode="replace", expected_modified=1)
    assert nfv.split_frontmatter(fake.text("n.md")) == ({"b": 2}, "body\n")
    with pytest.raises(KadoToolError):
        fake.write_frontmatter("n.md", {"c": 3}, mode="append")


def test_fake_path_exists_routes_by_extension_like_the_client():
    fake = nfv.NoteFakeVault({"a.md": "x\n", "b.json": b"{}"})
    assert fake.path_exists("a.md") and fake.path_exists("b.json")
    assert not fake.path_exists("c.md") and not fake.path_exists("d.json")
    reads = [e for e in fake.events if e[0] != "path_exists"]
    assert reads == [("read_frontmatter", "a.md"), ("read_file", "b.json"),
                     ("read_frontmatter", "c.md"), ("read_file", "d.json")]


@pytest.mark.parametrize("method", ["read_note", "read_frontmatter"])
def test_fake_note_reads_reject_a_non_md_path(method):
    from lib.kado_client import KadoToolError
    fake = nfv.NoteFakeVault({"b.json": b"{}"})
    with pytest.raises(KadoToolError):
        getattr(fake, method)("b.json")
