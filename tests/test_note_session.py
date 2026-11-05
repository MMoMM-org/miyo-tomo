#!/usr/bin/env python3
# version: 0.1.2
"""test_note_session.py — Behavioural tests for note-session.py (spec 044 T2.3).

Covers the deterministic /note session start:
- start: --process mode and process_template_path whatever note_include says,
  unknown stem -> empty path; free text -> note mode, never echoed (CON-3)
- start: kept drafts (started deliveries) vs stale stages from lib.note_meta
- start: note_include absent -> include_configured false and no Kado listing
- match: the SDD pattern preview table, daily stripped of .md and always excluded
- listing failure -> folder_listed 0, listing_error set, exit 0
- match: empty glob list -> exit 2
- argument parser boundaries, unreadable config, transport errors, ASCII-safe stdout
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "note-session.py"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_meta  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402

BASE = "Templates/"
LISTING = ["t_meeting.md", "t_problem.md", "t_day_privat.md", "i_alias.md", "a_archive.md"]
MARKER = "SECRET-MARKER-7f3a diagnosis for client Zyx"


class FakeKado:
    def __init__(self, files=None, error: Exception | None = None):
        self.files = files if files is not None else [BASE + n for n in LISTING]
        self.error = error
        self.calls: list[tuple] = []

    def list_dir(self, path="/", *, depth=None, limit=500):
        self.calls.append((path, depth))
        if self.error:
            raise self.error
        items = [{"path": p, "type": "file"} for p in self.files]
        return items + [{"path": BASE + "scripts", "type": "folder"}]


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("note_session", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    return tmp_path


def _config(instance: Path, *, include=None, daily="t_day_privat.md", base=BASE):
    templates = {"base_path": base, "mapping": {"daily": daily}}
    if include is not None:
        templates["note_include"] = include
    cfg = {"concepts": {"inbox": "100 Inbox/"}, "templates": templates}
    (instance / "config" / "vault-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")


def _run(mod, monkeypatch, capsys, argv, fake: FakeKado | None = None):
    fake = fake or FakeKado()
    monkeypatch.setattr(mod, "KadoClient", lambda *a, **k: fake)
    code = mod.main(argv)
    out, err = capsys.readouterr()
    return code, (json.loads(out) if code == 0 else None), out, err, fake


def _stage(instance: Path, stem: str, **overrides) -> None:
    stage = note_meta.stage_dir(instance, stem)
    stage.mkdir(parents=True)
    meta = note_meta.new_meta(
        stem=stem, run_id="r", created="2026-11-04T10:15:00Z", generated="g",
        template="Templates/t_meeting.md", template_stem="t_meeting", source_path=None,
        inbox="100 Inbox", title="Design review", destination="Atlas/",
        default_destination="Atlas/",
    )
    for key, value in overrides.items():
        setattr(meta, key, value)
    note_meta.write_meta(stage, meta)


# ---------------------------------------------------------------- start: mode

@pytest.mark.parametrize("include", [None, ["i_*"]])
def test_process_mode_reports_path_whatever_note_include_says(
        mod, instance, monkeypatch, capsys, include):
    _config(instance, include=include)
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=--process t_meeting"])
    assert code == 0
    assert out["mode"] == "process"
    assert out["process_template"] == "t_meeting"
    assert out["process_template_path"] == "Templates/t_meeting.md"


def test_process_mode_unknown_stem_gives_empty_path(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=--process t_nope"])
    assert code == 0
    assert out["mode"] == "process" and out["process_template_path"] == ""


def test_process_mode_takes_the_rest_as_stem_with_spaces(mod, instance, monkeypatch, capsys):
    _config(instance, include=["*"])
    fake = FakeKado(files=["Templates/Meeting Notes.md", "Templates/Meeting.md"])
    code, out, *_ = _run(mod, monkeypatch, capsys,
                         ["start", '--args=--process "Meeting Notes"'], fake)
    assert out["process_template"] == "Meeting Notes"
    assert out["process_template_path"] == "Templates/Meeting Notes.md"


def test_process_without_stem_is_process_mode_with_empty_path(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=--process"])
    assert code == 0
    assert out["mode"] == "process"
    assert out["process_template"] == "" and out["process_template_path"] == ""


def test_free_text_is_note_mode_and_never_echoed(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    code, out, raw, err, _ = _run(mod, monkeypatch, capsys, ["start", "--args", MARKER])
    assert code == 0
    assert out["mode"] == "note"
    assert out["process_template"] == "" and out["process_template_path"] == ""
    assert "SECRET-MARKER" not in raw and "Zyx" not in raw
    assert "SECRET-MARKER" not in err and "Zyx" not in err


def test_marker_never_echoed_on_listing_error(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    fake = FakeKado(error=KadoError("kado-search: Path not found: Templates/"))
    code, out, raw, err, _ = _run(mod, monkeypatch, capsys, ["start", "--args", MARKER], fake)
    assert code == 0
    assert "SECRET-MARKER" not in raw + err


def test_missing_args_is_bad_invocation(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    with pytest.raises(SystemExit) as exc:
        mod.main(["start"])
    assert exc.value.code == 2


@pytest.mark.parametrize("text, mode, stem", [
    ("--processor x", "note", ""),
    ("--process 'Meeting Notes'", "process", "Meeting Notes"),
    ('--process "  padded  "', "process", "padded"),
    ("  --process   --foo ", "process", "--foo"),
    ("--process \u00c4nder", "process", "\u00c4nder"),
    ("x --process y", "note", ""),
    ("--process t_meeting.md", "process", "t_meeting"),
])
def test_args_text_parser_boundaries(mod, instance, monkeypatch, capsys, text, mode, stem):
    _config(instance, include=["t_*"])
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", f"--args={text}"])
    assert code == 0
    assert (out["mode"], out["process_template"]) == (mode, stem)


def test_process_stem_with_md_suffix_finds_the_template(mod, instance, monkeypatch, capsys):
    _config(instance, include=None)
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=--process t_meeting.md"])
    assert out["process_template_path"] == "Templates/t_meeting.md"


@pytest.mark.parametrize("text", ["--process", "--process ''", "--process .md"])
def test_empty_process_stem_skips_listing(mod, instance, monkeypatch, capsys, text):
    _config(instance, include=["t_*"])
    code, out, _, _, fake = _run(mod, monkeypatch, capsys, ["start", f"--args={text}"])
    assert code == 0 and out["mode"] == "process"
    assert out["process_template_path"] == "" and fake.calls == []


def test_non_ascii_stdout_never_fails(mod, instance, monkeypatch):
    _config(instance, include=None)
    monkeypatch.setattr(mod, "KadoClient", lambda *a, **k: FakeKado())
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="ascii"))
    assert mod.main(["start", "--args=--process \u00c4nder \udcff"]) == 0
    sys.stdout.flush()
    assert json.loads(raw.getvalue().decode("ascii"))["process_template"] == "\u00c4nder \udcff"


# ---------------------------------------------------------------- start: stages

def test_kept_drafts_vs_stale_stages(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    _stage(instance, "2026-11-04_100000", failed_step="instructions_json", steps_done=["note"])
    _stage(instance, "2026-11-04_110000", steps_done=["note"])          # killed between steps
    _stage(instance, "2026-11-04_120000")                                # interrupted dialogue
    broken = note_meta.stage_dir(instance, "2026-11-04_130000")
    broken.mkdir(parents=True)
    (broken / "meta.json").write_text("{not json", encoding="utf-8")
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert code == 0
    assert [d["stem"] for d in out["kept_drafts"]] == ["2026-11-04_100000", "2026-11-04_110000"]
    assert out["kept_drafts"][0] == {
        "stem": "2026-11-04_100000", "title": "Design review",
        "template": "Templates/t_meeting.md", "created": "2026-11-04T10:15:00Z",
        "failed_step": "instructions_json",
    }
    assert out["kept_drafts"][1]["failed_step"] == ""
    assert out["stale_stages"] == ["2026-11-04_120000", "2026-11-04_130000"]


def test_no_stage_root_gives_empty_lists(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert out["kept_drafts"] == [] and out["stale_stages"] == []


# ---------------------------------------------------------------- start: include

def test_note_include_absent_skips_listing(mod, instance, monkeypatch, capsys):
    _config(instance, include=None)
    code, out, _, _, fake = _run(mod, monkeypatch, capsys, ["start", "--args=meeting notes"])
    assert code == 0
    assert out["include_configured"] is False
    assert out["note_include"] == [] and out["candidates"] == []
    assert out["folder_listed"] == 0 and out["listing_error"] == ""
    assert fake.calls == []


@pytest.mark.parametrize("bad", [[], "t_*", [""], [1]])
def test_unusable_note_include_counts_as_absent(mod, instance, monkeypatch, capsys, bad):
    _config(instance, include=bad)
    code, out, _, _, fake = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert out["include_configured"] is False and fake.calls == []


def test_missing_config_reads_as_not_configured(mod, instance, monkeypatch, capsys):
    code, out, _, err, fake = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert code == 0 and out["include_configured"] is False and fake.calls == []


def test_binary_config_reads_as_empty_with_class_only(mod, instance, monkeypatch, capsys):
    (instance / "config" / "vault-config.yaml").write_bytes(b"\xff\xfe\x00templates: \x9c")
    code, out, _, err, fake = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert code == 0 and out["include_configured"] is False and fake.calls == []
    assert err == "note-session: config unusable (UnicodeDecodeError)\n"


@pytest.mark.parametrize("config, expected_err", [
    ("", ""),
    ("- t_*\n- i_*\n", ""),
    ("templates: [unclosed\n", "note-session: config unusable (ParserError)\n"),
])
def test_unusable_config_policy_is_empty_and_warns_only_when_unreadable(
        mod, instance, monkeypatch, capsys, config, expected_err):
    """Empty / list read as not configured silently; invalid YAML adds one class-only line."""
    (instance / "config" / "vault-config.yaml").write_text(config, encoding="utf-8")
    code, out, _, err, fake = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert code == 0 and out["include_configured"] is False and fake.calls == []
    assert err == expected_err


def test_candidates_match_include_and_drop_daily(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    code, out, _, _, fake = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert out["include_configured"] is True and out["note_include"] == ["t_*"]
    assert out["candidates"] == [
        {"path": "Templates/t_meeting.md", "stem": "t_meeting"},
        {"path": "Templates/t_problem.md", "stem": "t_problem"},
    ]
    assert out["folder_listed"] == 5
    assert fake.calls == [(BASE, 1)]


def test_candidates_ignore_non_md_and_folders(mod, instance, monkeypatch, capsys):
    _config(instance, include=["*"])
    fake = FakeKado(files=["Templates/t_meeting.md", "Templates/t_img.png", "Templates/T_x.MD"])
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=x"], fake)
    assert out["folder_listed"] == 1
    assert [c["stem"] for c in out["candidates"]] == ["t_meeting"]


def test_start_listing_error_reported_exit_0(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])
    fake = FakeKado(error=KadoError("kado-search: Path not found: Templates/"))
    code, out, *_ = _run(mod, monkeypatch, capsys, ["start", "--args=x"], fake)
    assert code == 0
    assert out["folder_listed"] == 0 and out["candidates"] == []
    assert out["listing_error"] == "kado-search: Path not found: Templates/"


@pytest.mark.parametrize("error, expected", [
    (OSError("Connection reset by peer"), "OSError: Connection reset by peer"),
    (TimeoutError("timed out"), "TimeoutError: timed out"),
])
def test_start_transport_error_is_listing_error(
        mod, instance, monkeypatch, capsys, error, expected):
    _config(instance, include=["t_*"])
    code, out, raw, err, _ = _run(mod, monkeypatch, capsys, ["start", "--args", MARKER],
                                  FakeKado(error=error))
    assert code == 0
    assert out["folder_listed"] == 0 and out["listing_error"] == expected
    assert "SECRET-MARKER" not in raw + err


def test_start_without_base_path_reports_error_without_call(mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"], base=None)
    code, out, _, _, fake = _run(mod, monkeypatch, capsys, ["start", "--args=x"])
    assert code == 0 and fake.calls == []
    assert out["folder_listed"] == 0 and out["listing_error"] != ""


def test_start_kado_client_construction_failure_is_listing_error(
        mod, instance, monkeypatch, capsys):
    _config(instance, include=["t_*"])

    def boom(*_a, **_k):
        raise KadoError("Kado token not found.")

    monkeypatch.setattr(mod, "KadoClient", boom)
    assert mod.main(["start", "--args=x"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["folder_listed"] == 0 and out["listing_error"] == "Kado token not found."


# ---------------------------------------------------------------- match

@pytest.mark.parametrize("globs, matched, unmatched", [
    ("t_*", ["t_meeting", "t_problem"], ["i_alias", "a_archive"]),
    ("t_meeting,t_problem", ["t_meeting", "t_problem"], ["i_alias", "a_archive"]),
    ("*", ["t_meeting", "t_problem", "i_alias", "a_archive"], []),
])
@pytest.mark.parametrize("daily", ["t_day_privat.md", "t_day_privat"])
def test_match_pattern_preview_table(mod, instance, monkeypatch, capsys,
                                     globs, matched, unmatched, daily):
    _config(instance, include=None, daily=daily)
    code, out, *_ = _run(mod, monkeypatch, capsys, ["match", "--globs", globs])
    assert code == 0
    assert out == {"matched": matched, "unmatched": unmatched,
                   "excluded_daily": "t_day_privat", "folder_listed": 5, "listing_error": ""}


def test_match_is_case_sensitive(mod, instance, monkeypatch, capsys):
    _config(instance, include=None)
    code, out, *_ = _run(mod, monkeypatch, capsys, ["match", "--globs", "T_*"])
    assert out["matched"] == []


def test_match_strips_glob_padding(mod, instance, monkeypatch, capsys):
    _config(instance, include=None)
    code, out, *_ = _run(mod, monkeypatch, capsys, ["match", "--globs", " t_meeting , t_problem "])
    assert out["matched"] == ["t_meeting", "t_problem"]


def test_match_daily_not_listed_gives_empty_excluded(mod, instance, monkeypatch, capsys):
    _config(instance, include=None)
    fake = FakeKado(files=["Templates/t_meeting.md"])
    code, out, *_ = _run(mod, monkeypatch, capsys, ["match", "--globs", "*"], fake)
    assert out["excluded_daily"] == "" and out["matched"] == ["t_meeting"]


def test_match_listing_error_reported_exit_0(mod, instance, monkeypatch, capsys):
    _config(instance, include=None)
    fake = FakeKado(error=KadoError("HTTP 403 from Kado: Forbidden"))
    code, out, *_ = _run(mod, monkeypatch, capsys, ["match", "--globs", "t_*"], fake)
    assert code == 0
    assert out == {"matched": [], "unmatched": [], "excluded_daily": "",
                   "folder_listed": 0, "listing_error": "HTTP 403 from Kado: Forbidden"}


@pytest.mark.parametrize("globs", ["", " , ,"])
def test_match_empty_glob_list_exits_2(mod, instance, monkeypatch, capsys, globs):
    _config(instance, include=None)
    code, _, raw, _, fake = _run(mod, monkeypatch, capsys, ["match", "--globs", globs])
    assert code == 2 and raw == "" and fake.calls == []


def test_unknown_subcommand_exits_2(mod, instance):
    with pytest.raises(SystemExit) as exc:
        mod.main(["nope"])
    assert exc.value.code == 2
