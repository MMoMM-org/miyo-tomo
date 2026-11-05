#!/usr/bin/env python3
# version: 0.1.2
"""test_template_outline.py — template-outline.py lists one template's points.

Spec 044 T2.1 (PRD F3; SDD F3-AC1, Internal API Changes): every heading,
frontmatter key and non-prefilled token is a point; --stage writes template.md
with the prefilled tokens resolved and outline.json; --out writes the outline;
frontmatter_ok false still exits 0; an unreadable template exits 1 without
template text in the error. Runs main() in process against a fake Kado and a
tmp_path working directory (the instance root).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import KadoError, KadoNotFoundError  # noqa: E402
from lib.note_meta import NoteDraftMeta, stage_dir, write_meta  # noqa: E402


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "template_outline", SCRIPTS_DIR / "template-outline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


outline_script = _load_script()

TEMPLATE_PATH = "Templates/t_meeting.md"
STEM = "2026-11-04_173005"
NOW = datetime(2026, 11, 4, 17, 30, 5, tzinfo=timezone.utc)

TEMPLATE = """---
UUID: {{uuid}}
DateStamp: {{datestamp}}
locale: {{locale}}
title: "{{title}}"
source: {{source_link}}
tags:
  - type/note/meeting
Summary:
---

# [[{{title}}]]

## Attendees

## Notes
{{body}} from {{source_path}}

```
{{uuid}}
```
<% tp.date.now("YYYY") %>
"""

CONFIG = """profile: miyo
frontmatter:
  optional:
    - { key: "locale", token: "locale", default: "de" }
"""


class FakeKado:
    files: dict = {}
    reads: list = []

    def __init__(self, *args, **kwargs):
        pass

    def read_note(self, path):
        FakeKado.reads.append(path)
        if path not in FakeKado.files:
            raise KadoNotFoundError(f"NOT_FOUND: {path}")
        return {"content": FakeKado.files[path], "modified": 1}


class DeniedKado(FakeKado):
    def read_note(self, path):
        raise KadoError("FORBIDDEN: key has no read access")


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "vault-config.yaml").write_text(CONFIG, encoding="utf-8")
    FakeKado.files = {TEMPLATE_PATH: TEMPLATE}
    FakeKado.reads = []
    monkeypatch.setattr(outline_script, "KadoClient", FakeKado)
    monkeypatch.setattr(outline_script, "_now", lambda: NOW)
    return tmp_path


def _stage(base: Path, source_path: str | None) -> Path:
    stage = stage_dir(base, STEM)
    stage.mkdir(parents=True)
    write_meta(stage, NoteDraftMeta(
        stem=STEM, run_id="r", created="c", generated="g", template=TEMPLATE_PATH,
        template_stem="t_meeting", source_path=source_path, title="", inbox_file="",
        destination="Atlas/", default_destination="Atlas/"))
    return stage


def _run(capsys, *argv):
    code = outline_script.main(list(argv))
    out = capsys.readouterr()
    return code, (json.loads(out.out) if out.out.strip() else None), out.err


def _points(outline):
    return ({f["key"] for f in outline["frontmatter"]},
            [h["text"] for h in outline["headings"]],
            sorted({t["name"] for t in outline["tokens"] if not t["prefilled"]}))


def test_outline_lists_every_heading_key_and_open_token(instance, capsys):
    code, outline, _ = _run(capsys, "--template", TEMPLATE_PATH)
    assert code == 0
    assert set(outline) == {"template", "frontmatter", "headings", "tokens",
                            "templater", "frontmatter_ok"}
    keys, heads, open_tokens = _points(outline)
    assert keys == {"UUID", "DateStamp", "locale", "title", "source", "tags", "Summary"}
    assert heads == ["[[{{title}}]]", "Attendees", "Notes"]
    assert open_tokens == ["body", "source_link", "source_path", "title"]
    assert outline["template"] == TEMPLATE_PATH
    assert outline["frontmatter_ok"] is True
    assert FakeKado.reads == [TEMPLATE_PATH]


def test_outline_marks_prefilled_tokens_per_table(instance, capsys):
    _, outline, _ = _run(capsys, "--template", TEMPLATE_PATH)
    prefilled = {t["name"] for t in outline["tokens"] if t["prefilled"]}
    assert prefilled == {"uuid", "datestamp", "locale"}
    assert {"line": 22, "text": '<% tp.date.now("YYYY") %>'} in outline["templater"]
    summary = next(f for f in outline["frontmatter"] if f["key"] == "Summary")
    assert summary == {"key": "Summary", "has_value": False, "line": 9}


def test_stage_with_source_writes_resolved_template_and_outline(instance, capsys):
    stage = _stage(instance, "100 Inbox/Meeting raw.md")
    code, outline, _ = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM)
    assert code == 0
    _, _, open_tokens = _points(outline)
    assert open_tokens == ["body", "title"]
    staged = (stage / "template.md").read_text(encoding="utf-8")
    assert "UUID: " + NOW.astimezone().strftime("%Y%m%d%H%M%S") + "\n" in staged
    assert "DateStamp: " + NOW.astimezone().strftime("%Y-%m-%d") + "\n" in staged
    assert "locale: de\n" in staged
    assert "source: {{source_link}}\n" in staged
    assert "{{body}} from 100 Inbox/Meeting raw.md\n" in staged
    assert '"{{title}}"' in staged and "```\n{{uuid}}\n```" in staged
    assert json.loads((stage / "outline.json").read_text(encoding="utf-8")) == outline


def test_stage_without_source_keeps_source_tokens_as_points(instance, capsys):
    stage = _stage(instance, None)
    _, outline, _ = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM)
    assert "source_link" in _points(outline)[2]
    staged = (stage / "template.md").read_text(encoding="utf-8")
    assert "source: {{source_link}}" in staged and "{{source_path}}" in staged


def test_stage_without_config_blanks_config_tokens(instance, capsys):
    (instance / "config" / "vault-config.yaml").unlink()
    stage = _stage(instance, None)
    code, _, _ = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM)
    assert code == 0
    assert "locale: \n" in (stage / "template.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("config, expected_err", [
    (None, ""),
    ("", ""),
    ("- a\n- b\n", ""),
    ("frontmatter: [unclosed\n", "warning: vault-config.yaml unusable (ParserError)\n"),
])
def test_unusable_config_policy_blanks_tokens_and_warns_only_when_unreadable(
        instance, capsys, config, expected_err):
    """Missing / empty / list are silent; invalid YAML warns with the class only."""
    path = instance / "config" / "vault-config.yaml"
    if config is None:
        path.unlink()
    else:
        path.write_text(config, encoding="utf-8")
    stage = _stage(instance, None)
    code, _, err = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM)
    assert code == 0
    assert "locale: \n" in (stage / "template.md").read_text(encoding="utf-8")
    assert err == expected_err


def test_out_writes_outline_to_given_file(instance, capsys):
    target = instance / "tomo-tmp" / "note" / "process-outline.json"
    code, outline, _ = _run(capsys, "--template", TEMPLATE_PATH, "--out", str(target))
    assert code == 0
    assert json.loads(target.read_text(encoding="utf-8")) == outline
    assert not (instance / "tomo-tmp" / "note" / STEM).exists()


def test_missing_frontmatter_is_usable_and_exits_0(instance, capsys):
    FakeKado.files[TEMPLATE_PATH] = '<% tp.file.include("[[x_fm]]") %>\n# Title\n{{body}}\n'
    code, outline, _ = _run(capsys, "--template", TEMPLATE_PATH)
    assert code == 0
    assert outline["frontmatter_ok"] is False
    assert outline["frontmatter"] == []
    assert [h["text"] for h in outline["headings"]] == ["Title"]


def test_unclosed_frontmatter_is_usable_and_exits_0(instance, capsys):
    FakeKado.files[TEMPLATE_PATH] = "---\ntitle: {{title}}\n# H\n"
    code, outline, _ = _run(capsys, "--template", TEMPLATE_PATH)
    assert code == 0 and outline["frontmatter_ok"] is False


def test_template_not_found_exits_1_without_template_text(instance, capsys):
    del FakeKado.files[TEMPLATE_PATH]
    code, out, err = _run(capsys, "--template", TEMPLATE_PATH)
    assert code == 1
    assert out["template"] == TEMPLATE_PATH and out["error"]
    assert "frontmatter" not in out


def test_template_denied_exits_1_and_names_the_kado_error(instance, monkeypatch, capsys):
    monkeypatch.setattr(outline_script, "KadoClient", DeniedKado)
    code, out, err = _run(capsys, "--template", TEMPLATE_PATH)
    assert code == 1
    assert "FORBIDDEN" in out["error"]


def test_unreadable_error_never_carries_template_body(instance, monkeypatch, capsys):
    class BodyLeakKado(FakeKado):
        def read_note(self, path):
            return {"content": None}
    monkeypatch.setattr(outline_script, "KadoClient", BodyLeakKado)
    code, out, err = _run(capsys, "--template", TEMPLATE_PATH)
    assert code == 1 and out["error"]
    assert "Attendees" not in json.dumps(out) + err


def test_local_reads_a_file_without_kado(instance, monkeypatch, capsys):
    monkeypatch.setattr(outline_script, "KadoClient", DeniedKado)
    local = instance / "t.md"
    local.write_text(TEMPLATE, encoding="utf-8")
    code, outline, _ = _run(capsys, "--local", str(local))
    assert code == 0
    assert outline["template"] == str(local)
    assert [h["text"] for h in outline["headings"]] == ["[[{{title}}]]", "Attendees", "Notes"]


def test_local_missing_file_exits_1(instance, capsys):
    code, out, _ = _run(capsys, "--local", str(instance / "absent.md"))
    assert code == 1 and out["error"]


def test_stage_with_unusable_meta_exits_2(instance, capsys):
    stage_dir(instance, STEM).mkdir(parents=True)
    code, out, _ = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM)
    assert code == 2 and out["error"]
    assert not (stage_dir(instance, STEM) / "template.md").exists()


@pytest.mark.parametrize("argv", [
    [],
    ["--template", TEMPLATE_PATH, "--local", "t.md"],
    ["--template", "Templates/t_meeting.canvas"],
    ["--template", TEMPLATE_PATH, "--stage", "../escape"],
])
def test_bad_invocation_exits_2(instance, capsys, argv):
    with pytest.raises(SystemExit) as exc:
        outline_script.main(argv)
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""


def _failing_nth_write(fail_on: int):
    """Path.write_text that raises OSError on the n-th call (a full disk mid-stage)."""
    real, calls = Path.write_text, []

    def write_text(path, *args, **kwargs):
        calls.append(path)
        if len(calls) == fail_on:
            raise OSError("disk full")
        return real(path, *args, **kwargs)
    return write_text


def _stage_files(stage: Path) -> list[str]:
    return sorted(p.name for p in stage.iterdir() if p.name != "meta.json")


def test_stage_failed_second_write_leaves_no_staged_file(instance, monkeypatch, capsys):
    stage = _stage(instance, "100 Inbox/Meeting raw.md")
    monkeypatch.setattr(Path, "write_text", _failing_nth_write(2))
    code, out, _ = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM)
    assert code == 2 and "OSError" in out["error"]
    assert _stage_files(stage) == []


def test_stage_failed_out_write_leaves_no_staged_file(instance, capsys):
    stage = _stage(instance, None)
    (instance / "blocker").write_text("a file, not a folder", encoding="utf-8")
    code, out, _ = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM,
                        "--out", str(instance / "blocker" / "outline.json"))
    assert code == 2 and out["error"]
    assert _stage_files(stage) == []


def test_stage_with_out_writes_all_three_files_and_no_temp(instance, capsys):
    stage = _stage(instance, None)
    target = instance / "tomo-tmp" / "note" / "process-outline.json"
    code, outline, _ = _run(capsys, "--template", TEMPLATE_PATH, "--stage", STEM,
                            "--out", str(target))
    assert code == 0
    assert _stage_files(stage) == ["outline.json", "template.md"]
    assert json.loads(target.read_text(encoding="utf-8")) == outline
    assert sorted(p.name for p in target.parent.iterdir()
                  if p.name.endswith(".tmp")) == []
