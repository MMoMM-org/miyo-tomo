#!/usr/bin/env python3
# version: 0.1.0
"""review_deliver_helpers.py — the shared fixtures, constants and helpers of the review-instructions delivery tests.

Moved out of test_review_deliver.py (#260) so test_review_deliver.py, test_review_deliver_report.py,
test_review_deliver_resume.py, test_review_deliver_rerun.py and review_e2e_walk.py import them from one place
instead of from a test module. Holds the guarded fake vault (Kado's write guard as production refuses it), the
``ins``/``doc_mod``/``instance`` fixtures, the synthetic week and the helpers that run Pass 1 and the CLI against
the fake. Importing it puts tomo/scripts and tests/ on ``sys.path``. All data is synthetic.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
SCRIPTS_DIR = REPO / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from lib.kado_client import (  # noqa: E402
    KadoToolError,
)
from test_review_doc import INBOX, MARKER, WEEKLY, _config, item, proposals, stage, week_read  # noqa: E402

DOC_SCRIPT = SCRIPTS_DIR / "review-doc.py"
INS_SCRIPT = SCRIPTS_DIR / "review-instructions.py"
SCHEMAS = [REPO / "tomo" / "schemas" / "instructions.schema.json",
           REPO / "tomo" / "schemas" / "hashi-instructions.schema.json"]
HASHI_VENDORED = Path("/Volumes/Moon/Coding/MiYo/Hashi/src/schema/instructions.schema.json")

STEM = "2026-W13_review"
DOC = f"{INBOX}2026-W13 Review.md"
SET_JSON = f"{INBOX}{STEM}_instructions.json"
SET_MD = f"{INBOX}{STEM}_instructions.md"
NEW_NOTE = f"{INBOX}2026-W13.md"
TARGET = f"{WEEKLY}2026-W13.md"
OWN = "In my own words"
# the live refusal of Kado's write guard, as KadoClient.write_note raises it (a plain KadoToolError)
GUARD_REFUSED = ('kado-write returned an error: {"code":"CONFLICT",'
                 '"message":"File was updated in the background. Re-read before retrying."}')
NOTE = f"# 2026-W13\n\n## Woche\ntext der Woche\n\n## {OWN}\nmeine Worte\n"
REVIEW_MARKER = "%% tomo-review 2026-W13 %%"
LANDED = f"# 2026-W13\n\n## Tomo Review\n{REVIEW_MARKER}\n### Erledigt\n- alt\n\n## {OWN}\nmeine Worte\n"
RENAMED = LANDED.replace("## Tomo Review", "## Rückblick")
TEMPLATE = "---\ntags: weekly\n---\n# <% tp.file.title %>\n\n## Woche\n\n## In my own words\n\n"
PROPS = proposals(done=[item(f"Woche aufgeräumt {MARKER}", "2026-03-24", "2026-03-26")],
                  open=[item("Steuer offen", "2026-03-27")])


# ---------------------------------------------------------------- fakes and fixtures

class GuardedVault(ReviewFakeVault):
    """The fake plus Kado's guard on a note write (refused exactly as production sees it) and a hook
    run after a write lands."""

    def __init__(self, files=None):
        super().__init__(files)
        self.after_write: dict = {}
        self.guards: list = []                  # every write_file as (path, expected_modified)

    def write_note(self, path, content, expected_modified=None):
        if expected_modified is not None and path in self.files and expected_modified != self.modified.get(path):
            self._call("write_note", path)
            raise KadoToolError(GUARD_REFUSED)
        out = super().write_note(path, content, expected_modified)
        self._after(path)
        return out

    def write_file(self, path, data, expected_modified=None):
        self.guards.append((path, expected_modified))
        if expected_modified is not None and path in self.files and expected_modified != self.modified.get(path):
            self._call("write_file", path)
            raise KadoToolError(GUARD_REFUSED)
        out = super().write_file(path, data, expected_modified)
        self._after(path)
        return out

    def _after(self, path):
        hook = self.after_write.pop(path, None)
        if hook is not None:
            hook()


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ins():
    return _load(INS_SCRIPT, "review_instructions_script")


@pytest.fixture
def doc_mod():
    return _load(DOC_SCRIPT, "review_doc_script_t42")


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    _config(tmp_path)
    cfg_path = tmp_path / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["profile"] = "miyo"
    cfg["templates"] = {"base_path": "Templates/", "mapping": {"weekly": "t_week.md"}}
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return tmp_path


def vault(target: str | None = NOTE, **files) -> GuardedVault:
    held = {"Templates/t_week.md": TEMPLATE, **files}
    if target is not None:
        held[TARGET] = target
    return GuardedVault(held)


def prepared(doc_mod, instance, monkeypatch, capsys, fake, props=PROPS, *, approve=True) -> GuardedVault:
    """Pass 1 as production runs it, then the user ticks Approved in Obsidian."""
    stem, path = stage(instance, week_read(), props)
    monkeypatch.setattr(doc_mod, "KadoClient", fake)
    assert doc_mod.main(["--profiles-dir", "profiles", "write", "--stem", stem, "--proposals", str(path),
                         "--run-id", "r-test"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "written", out
    if approve:
        fake.files[DOC] = fake.files[DOC].replace("- [ ] Approved", "- [x] Approved", 1)
        fake.modified[DOC] += 1
    fake.events.clear()
    fake.writes.clear()
    return fake


def run(ins, monkeypatch, capsys, argv, fake):
    monkeypatch.setattr(ins, "KadoClient", fake)
    code = ins.main(["--profiles-dir", "profiles", *argv])
    out, err = capsys.readouterr()
    assert MARKER not in err, "item text leaked to stderr"
    if argv[0] != "preview":
        assert MARKER not in out, "item text leaked to stdout"
    return code, (json.loads(out) if out else None), err


def ready(doc_mod, ins, instance, monkeypatch, capsys, fake, props=PROPS, **kw):
    """``(cli, fake)``: ``cli(*argv)`` runs the script against the prepared fake."""
    prepared(doc_mod, instance, monkeypatch, capsys, fake, props, **kw)
    return (lambda *argv: run(ins, monkeypatch, capsys, list(argv), fake)), fake


def writes(fake) -> list:
    return [e for e in fake.events if e[0] in ("write_note", "write_file")]


def meta_of(instance) -> dict:
    return json.loads((instance / "tomo-tmp" / "review" / STEM / "meta.json").read_text(encoding="utf-8"))


def schema_errors(doc: dict, path: Path) -> list[str]:
    validator = jsonschema.Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))
    return [e.message for e in validator.iter_errors(doc)]


def set_json_of(fake) -> dict:
    return json.loads(fake.text(SET_JSON))
