#!/usr/bin/env python3
# version: 0.2.2
"""test_review_deliver.py — review-instructions.py preview, deliver, drop, status (spec 045 T4.2, T4.3, T4.4;
PRD F5-AC1, F5-AC2, F5-AC8 to F5-AC11, F6-AC2, F6-AC4; SDD Internal API Changes, Error Handling,
ADR-3, ADR-11, ADR-13) and the shared document reader lib/review_doc_read.py.

The document and meta.json are produced the way production produces them — `review-doc.py write`
on tests/review_fake_vault — then the Approved box is ticked in the fake vault and the script under
test runs against the same fake. Pinned, as `test_cli_*`, `test_deliver_*`, `test_drop_*`:
`parse`, `preview` and `deliver` parse through one reader that hands `meta.pass1_links` to the
parser; every problem name is classified as refusing or as a notice (`lib/review_delivery`), the
notices never refuse; `preview` returns mode, target, place, section_md, the escaped count, the
Templater hint, the problems and the note's headings for a place problem; `deliver` refuses an
unapproved document, any refusing problem and a second set for the same stem with nothing
written; writes (note,) `<stem>_instructions.json`, `<stem>_instructions.md` in that order through
`inbox_path()` and marks the document `approved` with "delivered" on its first line as the LAST
step, guarded by `expected_modified`; a guard refusal — the plain `KadoToolError` production sees,
carrying Kado's `{"code":"CONFLICT",...}` payload, or the client's `KadoConcurrencyError` — is
`doc-changed` with `failed_step: doc_mark`, while a tool error of another code is
`kado-write-failed` even when its message says "mismatch"; a failed Kado write is
`kado-write-failed`; a delivery interrupted at any step (a Kado error, a kill, a landed-but-unrecorded
upload) resumes without a duplicate write; a target that appeared since Pass 1 turns new-note into
insert; `--place-anchor` lands at the user's heading; `drop` after any started delivery — a partial
set, or only the new note landed — rewrites the set with an empty `actions` list (schema-valid) and
marks the MD withdrawn naming every file left, before any step removes only the stage; the set validates against both
schema copies and the MD peer carries `### I01 —` and `- [ ] Applied`; stderr names problem
classes only; an unexpected exception is exit 1 with the class name. T4.3: `status` and
`review-session.py start` classify a stem through the one `review_state.stem_state` with the same
inputs (recorded) and agree on delivered, move-refused, applied (reported once by `start`, still
answered by `status`), target-missing and withdrawn (`state: null`, never listed); a refused set
probe stops `status`. T4.4: `drop` reads the set JSON first (one `read_file`) and refuses
`already-applied` when any action carries `applied: true` — nothing written, meta and set unchanged;
an absent set (NOT_FOUND) or an unreadable one withdraws; a failed read stops by kind; the set JSON is
rewritten under `expected_modified` from that read, and Kado's CONFLICT on it is `set-changed`,
resumable by a second `drop`. All data is synthetic.
"""
from __future__ import annotations

import copy
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

from review_fake_vault import ReviewFakeVault, split_frontmatter  # noqa: E402
from note_fake_vault import Killed  # noqa: E402
from lib import review_actions as ra  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from lib import review_doc_read as rdr  # noqa: E402
from lib import review_state as rs  # noqa: E402
from lib.kado_client import (  # noqa: E402
    KadoAuthError, KadoConcurrencyError, KadoConnectionError, KadoError, KadoToolError,
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


# ---------------------------------------------------------------- one reader

def test_cli_parse_preview_and_deliver_parse_through_one_reader_with_pass1_links(
        doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    expected = meta_of(instance)["pass1_links"]
    assert expected and all(isinstance(v, list) for v in expected.values())
    seen: list = []
    real = rdp.parse_document

    def spy(text, pass1_links=None, pass1_total=None):
        seen.append(pass1_links)
        return real(text, pass1_links=pass1_links, pass1_total=pass1_total)

    monkeypatch.setattr(rdp, "parse_document", spy)
    monkeypatch.setattr(doc_mod, "KadoClient", fake)
    assert doc_mod.main(["--profiles-dir", "profiles", "parse", "--stem", STEM]) == 0
    capsys.readouterr()
    assert run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)[1]["status"] == "ok"
    assert run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)[1]["status"] == "delivered"
    assert seen == [expected, expected, expected]
    # the reader is the lib's, not a private copy in either script
    assert not hasattr(doc_mod, "_read_document")
    assert doc_mod.read_document is rdr.read_document and ins.read_document is rdr.read_document


def test_cli_reader_answers_not_found_and_stops_on_kado(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    del fake.files[DOC]
    assert run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)[1] == {
        "status": "not-found", "stem": STEM, "doc_path": DOC}
    assert run(ins, monkeypatch, capsys, ["preview", "--stem", "2026-W14_review"], fake)[1] == {
        "status": "not-found", "stem": "2026-W14_review"}
    fake.connection_error = KadoConnectionError("refused")
    code, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert code == 0 and out["status"] == "stopped" and out["error"]["kind"] == "kado-unreachable"


# ---------------------------------------------------------------- classification

def test_cli_every_problem_name_is_pinned_to_refusing_or_notice():
    assert set(rdl.REFUSING) == {"not-approved", "approved-line-missing", "nothing-to-deliver", "place-missing",
                                 "place-too-deep", "user-heading-collision", "set-exists", "already-applied"}
    assert set(rdl.NOTICES) == {"heading-renamed", "unlanded-items", "variant_missing", "templater_hint",
                                "template_unmergeable"}
    assert not set(rdl.REFUSING) & set(rdl.NOTICES)
    emitted = {ra.NOT_APPROVED, rdp.APPROVED_MISSING, ra.NOTHING_TO_DELIVER, ra.UNLANDED_ITEMS, ra.PLACE_MISSING,
               ra.PLACE_TOO_DEEP, ra.HEADING_RENAMED, ra.HEADING_COLLISION}
    assert emitted <= set(rdl.REFUSING) | set(rdl.NOTICES)
    plan = ra.ReviewPlan("insert", TARGET, False, [], {}, problems=["heading-renamed", "place-too-deep",
                                                                  "unlanded-items", "zz-unknown"],
                         templater_hint=True, variant_missing=True, template_unmergeable="tomo key")
    assert rdl.classify(plan) == (["place-too-deep", "zz-unknown"],
                                  ["heading-renamed", "unlanded-items", "templater_hint", "variant_missing",
                                   "template_unmergeable"])


def test_cli_notices_are_shown_and_delivery_proceeds(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(RENAMED))
    _, out, _ = cli("preview", "--stem", STEM)
    assert out["mode"] == "replace" and out["problems"] == [] and out["notices"] == ["heading-renamed"]
    assert out["place"] == {"anchor": "Rückblick", "placement": "replace", "level": 2}
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "delivered" and out["notices"] == ["heading-renamed"]
    assert set_json_of(fake)["actions"][0]["action"] == "replace_section"


# ---------------------------------------------------------------- preview

def test_cli_preview_returns_mode_target_place_section_and_counts(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    code, out, _ = cli("preview", "--stem", STEM)
    assert code == 0
    assert out["status"] == "ok" and out["stem"] == STEM and out["doc_path"] == DOC
    assert out["mode"] == "insert" and out["target"] == TARGET
    assert out["place"] == {"anchor": OWN, "placement": "before", "level": 2}
    assert out["section_md"].split("\n")[:3] == ["## Tomo Review", REVIEW_MARKER, "### Erledigt"]
    assert MARKER in out["section_md"] and "%%t" not in out["section_md"]
    assert out["escaped_lines"] == 0 and out["templater_hint"] is False
    assert out["problems"] == [] and out["notices"] == [] and out["set_exists"] is False
    assert "headings" not in out
    assert writes(fake) == []


@pytest.mark.parametrize("anchor, problem", [("Nirgends", "place-missing"), ("Woche", "place-too-deep")])
def test_cli_preview_place_problems_name_the_notes_headings(doc_mod, ins, instance, monkeypatch, capsys,
                                                           anchor, problem):
    deep = NOTE.replace("## Woche", "##### Woche")
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(deep))
    cfg_path = instance / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["review"]["weekly"]["place"] = {"anchor": anchor, "placement": "inside"}
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    _, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert out["problems"] == [problem] and out["headings"] == ["2026-W13", "Woche", OWN]
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["problems"] == [problem] and writes(fake) == []


def test_cli_preview_gate_problems(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(), approve=False)
    assert run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)[1]["problems"] == ["not-approved"]
    fake.files[DOC] = fake.files[DOC].replace("- [ ] Approved\n", "", 1)
    assert run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)[1]["problems"] == [
        "approved-line-missing"]
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    fake.files[DOC] = fake.files[DOC].replace("- [x] ", "- [ ] ").replace("- [ ] Approved", "- [x] Approved", 1)
    _, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert out["problems"] == ["nothing-to-deliver"] and out["section_md"] == ""


def test_cli_preview_user_heading_collision_and_set_exists(doc_mod, ins, instance, monkeypatch, capsys):
    collision = NOTE.replace("## Woche", "## Tomo Review")
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(collision))
    assert run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)[1]["problems"] == [
        "user-heading-collision"]
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(**{SET_JSON: b"{}"}))
    _, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert out["set_exists"] is True and out["problems"] == ["set-exists"]


def test_cli_preview_new_note_names_the_templater_hint(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    _, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert out["mode"] == "new-note" and out["target"] == TARGET
    assert out["templater_hint"] is True and out["notices"] == ["templater_hint"] and out["problems"] == []
    assert out["place"] == {"anchor": OWN, "placement": "before", "level": 2}


UNMERGEABLE_TEMPLATE = "---\ntomo: mine\n---\n# <% tp.file.title %>\n\n## Woche\n\n## In my own words\n\n"


@pytest.mark.parametrize("notice", ["unlanded-items", "variant_missing", "template_unmergeable"])
def test_cli_each_notice_is_shown_without_refusing_and_deliver_lands(doc_mod, ins, instance, monkeypatch, capsys,
                                                                     notice):
    """Falsifies a notice that refuses, or one the plan never raises: an item the user added under a heading
    of their own, a configured variant file the vault lacks, and a template whose frontmatter already holds
    ``tomo:`` each name their notice in ``notices`` (never in ``problems``) on ``preview``, and ``deliver``
    proceeds to ``delivered`` naming it again."""
    if notice == "unlanded-items":
        fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
        fake.files[DOC] += "\n## Eigene Rubrik\n- [x] mein eigener Punkt\n"
        fake.modified[DOC] += 1
    elif notice == "variant_missing":
        cfg_path = instance / "config" / "vault-config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        cfg["review"]["weekly"]["template_variant"] = "t_week_tomo.md"          # not in the fake vault
        cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    else:
        fake = prepared(doc_mod, instance, monkeypatch, capsys,
                        vault(None, **{"Templates/t_week.md": UNMERGEABLE_TEMPLATE}))
    _, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert out["status"] == "ok" and out["problems"] == [] and notice in out["notices"]
    if notice == "unlanded-items":
        assert out["unlanded"] == 1 and out["mode"] == "insert"
    elif notice == "variant_missing":
        assert out["variant_missing"] is True and out["mode"] == "new-note"
    else:
        assert "tomo" in out["template_unmergeable"] and out["templater_hint"] is False
    assert writes(fake) == []
    _, out, err = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "delivered" and notice in out["notices"] and err == ""
    assert out["paths"]["set_json"] == SET_JSON and len(set_json_of(fake)["actions"]) == 1
    assert split_frontmatter(fake.text(DOC))[0]["tomo"]["state"] == "approved"
    if notice == "unlanded-items":          # the user's item under the unknown heading did not land
        [action] = set_json_of(fake)["actions"]
        assert MARKER in action["content"] and "mein eigener Punkt" not in action["content"]
    else:
        assert out["mode"] == "new-note" and NEW_NOTE in fake.files
    if notice == "template_unmergeable":
        front, body = split_frontmatter(fake.text(NEW_NOTE))
        assert front["tomo"]["doc_type"] == "rendered-note" and "mine" not in str(front) and "<%" not in body


# ---------------------------------------------------------------- deliver

def test_deliver_writes_the_set_in_order_and_marks_the_document_last(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    code, out, err = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert code == 0 and err == ""
    assert out["status"] == "delivered" and out["step"] == "" and out["next"] == "hashi-or-by-hand"
    assert out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD}
    assert out["mode"] == "insert" and out["target"] == TARGET and out["place"]["anchor"] == OWN
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD), ("write_note", DOC)]
    meta = meta_of(instance)
    assert meta["steps_done"] == ["set_json", "set_md", "doc_mark"] and meta["failed_step"] == ""
    assert meta["withdrawn"] is False and meta["run_id"] == "r-test"
    doc = set_json_of(fake)
    assert doc["md_peer"] == f"{STEM}_instructions" and doc["generated"] == meta["generated"]
    assert doc["profile"] == "miyo" and len(doc["actions"]) == 1
    [action] = doc["actions"]
    assert action["action"] == "insert_under_marker" and action["target_path"] == TARGET
    assert action["anchor"] == {"type": "heading", "value": OWN} and action["placement"] == "before"
    assert action["content"].startswith("## Tomo Review\n" + REVIEW_MARKER + "\n") and MARKER in action["content"]
    for schema in SCHEMAS + ([HASHI_VENDORED] if HASHI_VENDORED.exists() else []):
        assert schema_errors(doc, schema) == [], schema.name
    front, body = split_frontmatter(fake.text(SET_MD))
    assert front["tomo"] == {"doc_type": "instructions", "state": "pending-apply", "run_id": "r-test",
                             "updated_at": meta["generated"]}
    assert "### I01 — " in body and "- [ ] Applied" in body and f"`{OWN}`" in body
    assert "```" in body and REVIEW_MARKER in body
    front, body = split_frontmatter(fake.text(DOC))
    assert front["tomo"]["state"] == "approved" and front["tomo"]["run_id"] == "r-test"
    assert front["review_period"] == "2026-W13" and front["review_stem"] == STEM
    assert body.split("\n")[0] == "# 2026-W13 Review — geliefert"
    assert "- [x] Approved" in body and MARKER in body


def test_deliver_new_note_writes_the_note_first_and_moves_it(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "delivered" and out["mode"] == "new-note"
    assert out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD, "note": NEW_NOTE}
    assert writes(fake) == [("write_note", NEW_NOTE), ("write_file", SET_JSON), ("write_note", SET_MD),
                            ("write_note", DOC)]
    assert meta_of(instance)["steps_done"] == ["note", "set_json", "set_md", "doc_mark"]
    front, body = split_frontmatter(fake.text(NEW_NOTE))
    assert front["tomo"]["doc_type"] == "rendered-note" and front["tomo"]["state"] == "pending-move"
    assert front["tags"] == "weekly" and "<% tp.file.title %>" in body and REVIEW_MARKER in body
    [action] = set_json_of(fake)["actions"]
    assert action["action"] == "move_note" and action["source"] == NEW_NOTE and action["destination"] == TARGET
    md = fake.text(SET_MD)
    assert "### I01 — Move note: 2026-W13" in md and "- [ ] Applied" in md and "Templater" in md
    assert f"- **From:** `{NEW_NOTE}`" in md and f"- **To:** `{TARGET}`" in md      # the move's destination is named


def test_deliver_refuses_an_unapproved_document_and_writes_nothing(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(), approve=False)
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["problems"] == ["not-approved"] and "paths" not in out
    assert writes(fake) == [] and not (instance / "tomo-tmp" / "review" / STEM / "meta.json").read_text().count(
        '"failed_step": "set')
    assert meta_of(instance)["steps_done"] == []


@pytest.mark.parametrize("problem", ["nothing-to-deliver", "user-heading-collision", "approved-line-missing"])
def test_deliver_refuses_each_refusing_problem_and_writes_nothing(doc_mod, ins, instance, monkeypatch, capsys,
                                                                  problem):
    """Falsifies a refusing problem that still writes, or one that is not named: every item unticked, a note
    heading with Tomo's text and no marker, and a document without its Approved line each refuse the
    delivery by name, with no vault write, no step recorded and the document still pending."""
    if problem == "user-heading-collision":
        fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(NOTE.replace("## Woche", "## Tomo Review")))
    else:
        fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
        if problem == "nothing-to-deliver":
            fake.files[DOC] = fake.files[DOC].replace("- [x] ", "- [ ] ").replace("- [ ] Approved", "- [x] Approved", 1)
        else:
            fake.files[DOC] = fake.files[DOC].replace("- [x] Approved\n", "", 1)
        fake.modified[DOC] += 1
    _, out, err = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["stem"] == STEM and out["problems"] == [problem]
    assert "paths" not in out and err == ""
    assert writes(fake) == [] and fake.writes == []
    assert SET_JSON not in fake.files and SET_MD not in fake.files and NEW_NOTE not in fake.files
    assert split_frontmatter(fake.text(DOC))[0]["tomo"]["state"] == "pending-approval"
    assert meta_of(instance)["steps_done"] == [] and meta_of(instance)["failed_step"] == ""


def test_deliver_refuses_a_second_set_for_the_same_stem(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    assert run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)[1]["status"] == "delivered"
    landed = dict(fake.files)
    fake.events.clear()
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["problems"] == ["set-exists"]
    assert writes(fake) == [] and fake.files == landed
    # a set at the path that this delivery did not write is a second set too
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(**{SET_JSON: b'{"actions": []}'}))
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["problems"] == ["set-exists"] and writes(fake) == []
    assert meta_of(instance)["steps_done"] == [] and meta_of(instance)["failed_step"] == ""


def test_deliver_switches_from_new_note_to_insert_when_the_target_appeared(doc_mod, ins, instance, monkeypatch,
                                                                            capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    assert meta_of(instance)["mode"] == "new-note"
    fake.files[TARGET] = NOTE
    fake.modified[TARGET] = 1
    _, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert out["mode"] == "insert" and out["target_appeared"] is True
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "delivered" and out["mode"] == "insert" and out["target_appeared"] is True
    assert "note" not in out["paths"] and NEW_NOTE not in fake.files
    assert set_json_of(fake)["actions"][0]["action"] == "insert_under_marker"


STEP_WRITES = {"note": ("write_note", NEW_NOTE), "set_json": ("write_file", SET_JSON),
               "set_md": ("write_note", SET_MD), "doc_mark": ("write_note", DOC)}


def landed(fake, step: str) -> bool:
    """Whether the step's upload reached the vault: the file for a payload, the mark for the document."""
    path = STEP_WRITES[step][1]
    if step == "doc_mark":
        return split_frontmatter(fake.text(DOC))[0]["tomo"]["state"] == "approved"
    return path in fake.files


@pytest.mark.parametrize("fault", ["kado-error", "killed", "landed-unrecorded"])
@pytest.mark.parametrize("step", list(STEP_WRITES))
def test_deliver_interrupted_at_any_step_resumes_without_duplicates(doc_mod, ins, instance, monkeypatch, capsys,
                                                                     step, fault):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    method, path = STEP_WRITES[step]
    if fault == "kado-error":
        fake.fail[(method, path)] = KadoError("503 after retries")
        _, out, err = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
        assert out["status"] == "stopped" and out["failed_step"] == step and out["step"] == step
        assert out["problems"] == ["kado-write-failed"]
        assert err == f"review-instructions: delivery failed at {step} (KadoError)\n"
        assert not landed(fake, step)
    elif fault == "killed":
        fake.fail[(method, path)] = Killed()
        monkeypatch.setattr(ins, "KadoClient", fake)
        with pytest.raises(Killed):
            ins.main(["--profiles-dir", "profiles", "deliver", "--stem", STEM])
        capsys.readouterr()
        assert not landed(fake, step)
    else:
        def die():
            raise Killed()
        fake.after_write[path] = die
        monkeypatch.setattr(ins, "KadoClient", fake)
        with pytest.raises(Killed):
            ins.main(["--profiles-dir", "profiles", "deliver", "--stem", STEM])
        capsys.readouterr()
        assert landed(fake, step)
    meta = meta_of(instance)
    assert meta["failed_step"] == step and step not in meta["steps_done"]
    assert run(ins, monkeypatch, capsys, ["status", "--stem", STEM], fake)[1]["state"] == "failed-delivery"
    fake.fail.clear()
    _, out, err = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "resumed" and err == "", err
    assert meta_of(instance)["steps_done"] == list(STEP_WRITES) and meta_of(instance)["failed_step"] == ""
    for _, path in STEP_WRITES.values():
        assert fake.writes.count(path) == 1, (path, fake.writes)      # landed once, over both runs
    assert [a["action"] for a in set_json_of(fake)["actions"]] == ["move_note"]
    assert split_frontmatter(fake.text(DOC))[1].startswith("# 2026-W13 Review — geliefert\n")
    assert split_frontmatter(fake.text(DOC))[0]["tomo"]["state"] == "approved"


def test_deliver_doc_changed_stops_at_doc_mark_and_resumes_after_saving(doc_mod, ins, instance, monkeypatch,
                                                                        capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    fake.after_write[SET_MD] = lambda: fake._bump(DOC)      # the user saves during the delivery
    _, out, err = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "stopped" and out["problems"] == ["doc-changed"] and out["failed_step"] == "doc_mark"
    assert err == "review-instructions: delivery failed at doc_mark (KadoToolError)\n"
    assert split_frontmatter(fake.text(DOC))[0]["tomo"]["state"] == "pending-approval"
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md"]
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "resumed"
    assert [e for e in writes(fake) if e[1] != DOC] == [("write_file", SET_JSON), ("write_note", SET_MD)]
    front, body = split_frontmatter(fake.text(DOC))
    assert front["tomo"]["state"] == "approved" and body.startswith("# 2026-W13 Review — geliefert\n")
    # the guard is the modified time the reader saw: every doc write carries it
    marks = [e for e in fake.events if e == ("write_note", DOC)]
    assert len(marks) == 2


CONFLICT_REFUSALS = {
    "kado-conflict-json": (KadoToolError(GUARD_REFUSED), "doc-changed"),
    "kado-conflict-in-prose": (KadoToolError('kado-write returned an error: refused: {"code":"CONFLICT",'
                                             '"message":"File was updated in the background."} (see log)'),
                               "doc-changed"),
    "client-concurrency-error": (KadoConcurrencyError("kado-write returned an error: expectedModified mismatch"),
                                 "doc-changed"),
    "validation-error-saying-mismatch": (KadoToolError('kado-write returned an error: {"code":"VALIDATION_ERROR",'
                                                       '"message":"frontmatter mismatch: expected a mapping"}'),
                                         "kado-write-failed"),
    "conflict-named-in-the-message-only": (KadoToolError('kado-write returned an error: {"code":"IO_ERROR",'
                                                         '"message":"CONFLICT while writing"}'),
                                           "kado-write-failed"),
}


@pytest.mark.parametrize("refusal", list(CONFLICT_REFUSALS))
def test_deliver_doc_mark_refusal_is_doc_changed_only_for_kados_conflict_code(doc_mod, ins, instance, monkeypatch,
                                                                              capsys, refusal):
    """Falsifies a substring match: a VALIDATION_ERROR saying "mismatch", or an IO_ERROR whose message says
    CONFLICT, is kado-write-failed; only code CONFLICT (JSON or the exact token) and the client's
    KadoConcurrencyError are doc-changed. Every outcome is resumable."""
    exc, problem = CONFLICT_REFUSALS[refusal]
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    fake.fail[("write_note", DOC)] = exc
    _, out, err = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "stopped" and out["problems"] == [problem] and out["failed_step"] == "doc_mark"
    assert out["step"] == "doc_mark" and out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD}
    assert err == f"review-instructions: delivery failed at doc_mark ({type(exc).__name__})\n"
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md"] and meta_of(instance)["failed_step"] == "doc_mark"
    assert split_frontmatter(fake.text(DOC))[0]["tomo"]["state"] == "pending-approval"
    fake.fail.clear()
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "resumed" and meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]
    assert split_frontmatter(fake.text(DOC))[0]["tomo"]["state"] == "approved"


def test_deliver_mark_is_idempotent_when_the_write_landed_unrecorded(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())

    def die():
        raise Killed()
    fake.after_write[DOC] = die
    monkeypatch.setattr(ins, "KadoClient", fake)
    with pytest.raises(Killed):
        ins.main(["--profiles-dir", "profiles", "deliver", "--stem", STEM])
    capsys.readouterr()
    marked = fake.text(DOC)
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "resumed" and fake.text(DOC) == marked
    assert writes(fake).count(("write_note", DOC)) == 1
    assert marked.count("geliefert") == 1


def test_deliver_place_anchor_uses_the_users_heading(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(NOTE.replace(f"## {OWN}", "## Meins")))
    _, out, _ = run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)
    assert out["problems"] == ["place-missing"] and out["headings"] == ["2026-W13", "Woche", "Meins"]
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM, "--place-anchor", "Woche"], fake)
    assert out["status"] == "delivered" and out["place"] == {"anchor": "Woche", "placement": "before", "level": 2}
    assert set_json_of(fake)["actions"][0]["anchor"]["value"] == "Woche"


def test_deliver_name_taken_for_the_new_note_refuses_before_any_write(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None, **{NEW_NOTE: "the user's own note\n"}))
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["problems"] == ["name-taken"] and out["exists_path"] == NEW_NOTE
    assert writes(fake) == [] and meta_of(instance)["steps_done"] == []


# ---------------------------------------------------------------- drop

def test_drop_after_a_partial_delivery_withdraws_the_set(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    fake.fail[("write_note", SET_MD)] = KadoError("503")
    assert run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)[1]["status"] == "stopped"
    fake.fail.clear()
    fake.events.clear()
    code, out, err = run(ins, monkeypatch, capsys, ["drop", "--stem", STEM], fake)
    assert code == 0 and err == "" and out["status"] == "withdrawn" and out["stem"] == STEM
    assert out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD, "note": NEW_NOTE}
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD)]
    doc = set_json_of(fake)
    assert doc["actions"] == [] and doc["md_peer"] == f"{STEM}_instructions" and doc["type"] == "tomo-instructions"
    for schema in SCHEMAS + ([HASHI_VENDORED] if HASHI_VENDORED.exists() else []):
        assert schema_errors(doc, schema) == [], schema.name
    front, body = split_frontmatter(fake.text(SET_MD))
    assert front["tomo"]["doc_type"] == "instructions" and front["action_count"] == 0
    assert "withdrawn" in body.lower() and "delete these files" in body
    assert f"`{SET_JSON}`" in body and f"`{SET_MD}`" in body and f"`{NEW_NOTE}`" in body
    assert "- [ ] Applied" not in body
    meta = meta_of(instance)
    assert meta["withdrawn"] is True and meta["failed_step"] == ""
    assert (instance / "tomo-tmp" / "review" / STEM / "meta.json").exists()
    # a second deliver after the drop is refused: the withdrawn set sits at the path
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["problems"] == ["set-exists"]


def test_drop_before_any_step_removes_only_the_stage(doc_mod, ins, instance, monkeypatch, capsys):
    """A delivery that never began (here: refused on an unapproved document) left nothing to neutralise."""
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None), approve=False)
    assert run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)[1]["status"] == "refused"
    assert meta_of(instance)["steps_done"] == [] and meta_of(instance)["failed_step"] == ""
    fake.events.clear()
    _, out, _ = run(ins, monkeypatch, capsys, ["drop", "--stem", STEM], fake)
    assert out == {"status": "dropped", "stem": STEM, "removed": True}
    assert fake.events == [] and not (instance / "tomo-tmp" / "review" / STEM).exists()
    assert DOC in fake.files
    _, out, _ = run(ins, monkeypatch, capsys, ["drop", "--stem", STEM], fake)
    assert out == {"status": "dropped", "stem": STEM, "removed": False}


@pytest.mark.parametrize("fault", ["killed-after-the-note-landed", "killed-after-the-note-was-recorded",
                                   "kado-error-on-the-note"])
def test_drop_after_the_note_step_began_withdraws_and_names_the_note(doc_mod, ins, instance, monkeypatch, capsys,
                                                                     fault):
    """Falsifies `drop` withdrawing only when set_json was reached: a kill after the note landed (in flight),
    a kill after it was recorded (set_json never started) and a failed note write all leave a started
    delivery, and the user is told through the withdrawn MD which files to delete — the note among them."""
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    monkeypatch.setattr(ins, "KadoClient", fake)

    def die():
        raise Killed()
    if fault == "kado-error-on-the-note":
        fake.fail[("write_note", NEW_NOTE)] = KadoError("503")
        assert run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)[1]["failed_step"] == "note"
        fake.fail.clear()
        assert NEW_NOTE not in fake.files
    else:
        save_meta = rdl.save_meta

        def save_then_die(stage, meta):       # the kill between record(note) and set_json's in-flight mark
            save_meta(stage, meta)
            if meta.steps_done == ["note"] and meta.failed_step == "":
                die()
        if fault == "killed-after-the-note-landed":
            fake.after_write[NEW_NOTE] = die
        else:
            monkeypatch.setattr(rdl, "save_meta", save_then_die)
        with pytest.raises(Killed):
            ins.main(["--profiles-dir", "profiles", "deliver", "--stem", STEM])
        capsys.readouterr()
        monkeypatch.setattr(rdl, "save_meta", save_meta)
        assert NEW_NOTE in fake.files
    meta = meta_of(instance)
    assert "set_json" not in meta["steps_done"] and meta["failed_step"] != "set_json"
    assert (meta["steps_done"], meta["failed_step"]) == ((["note"], "") if fault == "killed-after-the-note-was-recorded"
                                                         else ([], "note"))
    fake.events.clear()
    code, out, err = run(ins, monkeypatch, capsys, ["drop", "--stem", STEM], fake)
    assert code == 0 and err == "" and out["status"] == "withdrawn"
    assert out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD, "note": NEW_NOTE}
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD)]
    assert set_json_of(fake)["actions"] == []
    body = split_frontmatter(fake.text(SET_MD))[1]
    assert "delete these files" in body and f"`{NEW_NOTE}`" in body and f"`{SET_JSON}`" in body
    meta = meta_of(instance)
    assert meta["withdrawn"] is True and meta["failed_step"] == ""
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "refused" and out["problems"] == ["set-exists"]


def test_drop_kado_failure_is_stopped_and_keeps_the_stage(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    fake.fail[("write_note", SET_MD)] = KadoError("503")
    run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    fake.fail.clear()
    fake.fail[("write_file", SET_JSON)] = KadoError("503")
    _, out, err = run(ins, monkeypatch, capsys, ["drop", "--stem", STEM], fake)
    assert out["status"] == "stopped" and out["problems"] == ["kado-write-failed"]
    assert err == "" and meta_of(instance)["withdrawn"] is False


# ---------------------------------------------------------------- drop against what Hashi left (T4.4)

def delivered(doc_mod, ins, instance, monkeypatch, capsys):
    """``(cli, fake)`` after a complete delivery in new-note mode (one ``move_note``), events cleared."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    assert cli("deliver", "--stem", STEM)[1]["status"] == "delivered"
    assert meta_of(instance)["steps_done"] == ["note", "set_json", "set_md", "doc_mark"]
    fake.events.clear()
    fake.writes.clear()
    fake.guards.clear()
    return cli, fake


def store_set(fake, doc: dict) -> bytes:
    """Hashi's rewrite of the set: the file is replaced and its ``modified`` moves on."""
    fake.files[SET_JSON] = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    fake._bump(SET_JSON)
    return fake.files[SET_JSON]


def untouched(instance, fake, meta_before: dict, set_before: bytes) -> None:
    assert writes(fake) == [] and fake.writes == []
    assert meta_of(instance) == meta_before and fake.files[SET_JSON] == set_before
    assert (instance / "tomo-tmp" / "review" / STEM / "meta.json").exists()


@pytest.mark.parametrize("marked", ["the-one-action", "one-of-two"])
def test_drop_refuses_a_set_hashi_already_applied_and_writes_nothing(doc_mod, ins, instance, monkeypatch, capsys,
                                                                    marked):
    """Falsifies a `drop` that rewrites the set blind: one action Hashi marked `applied: true` — the set's
    only action, or one of two with the other still waiting — refuses the withdrawal by name, with no vault
    write, the set JSON byte-identical, meta.json unchanged and the stage kept; `status` still answers from
    the set as Hashi left it."""
    cli, fake = delivered(doc_mod, ins, instance, monkeypatch, capsys)
    doc = set_json_of(fake)
    if marked == "one-of-two":
        waiting = copy.deepcopy(doc["actions"][0])
        waiting["id"] = "I02"
        doc["actions"].append(waiting)
    doc["actions"][0]["applied"] = True
    set_before = store_set(fake, doc)
    meta_before = meta_of(instance)
    code, out, err = cli("drop", "--stem", STEM)
    assert code == 0 and err == ""
    assert out == {"status": "refused", "stem": STEM, "problems": ["already-applied"]}
    untouched(instance, fake, meta_before, set_before)
    assert [e for e in fake.events if e[0].startswith("read")] == [("read_file", SET_JSON)]
    assert cli("status", "--stem", STEM)[1]["state"] == ("applied" if marked == "the-one-action" else "delivered")


def test_drop_withdraws_a_set_no_action_of_which_is_applied_with_the_reads_guard(doc_mod, ins, instance, monkeypatch,
                                                                                capsys):
    """The set as delivered (`applied` absent, or `false`) withdraws as before, and the set JSON is written
    with the `modified` the read returned as its guard."""
    cli, fake = delivered(doc_mod, ins, instance, monkeypatch, capsys)
    doc = set_json_of(fake)
    doc["actions"][0]["applied"] = False
    store_set(fake, doc)
    seen = fake.modified[SET_JSON]
    _, out, err = cli("drop", "--stem", STEM)
    assert err == "" and out["status"] == "withdrawn"
    assert out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD, "note": NEW_NOTE}
    assert fake.events[:1] == [("read_file", SET_JSON)]
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD)]
    assert fake.guards == [(SET_JSON, seen)]
    assert set_json_of(fake)["actions"] == [] and meta_of(instance)["withdrawn"] is True
    assert cli("status", "--stem", STEM)[1]["state"] is None


def test_drop_withdraws_when_the_set_json_is_absent(doc_mod, ins, instance, monkeypatch, capsys):
    """NOT_FOUND on the set read means nothing landed (or the user deleted it): the withdrawal proceeds,
    the set JSON written without a guard."""
    cli, fake = delivered(doc_mod, ins, instance, monkeypatch, capsys)
    del fake.files[SET_JSON]
    _, out, err = cli("drop", "--stem", STEM)
    assert err == "" and out["status"] == "withdrawn"
    assert fake.events[:1] == [("read_file", SET_JSON)]
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD)]
    assert fake.guards == [(SET_JSON, None)]
    assert set_json_of(fake)["actions"] == [] and meta_of(instance)["withdrawn"] is True


@pytest.mark.parametrize("broken", [b"not json at all", b'{"actions": "I01"}', b'[{"applied": true}]'])
def test_drop_withdraws_over_an_unreadable_set(doc_mod, ins, instance, monkeypatch, capsys, broken):
    """A file that is not a JSON object, or whose `actions` is not a list of objects, is not proof of
    applied: the withdrawal proceeds as before, guarded by the read's `modified`."""
    cli, fake = delivered(doc_mod, ins, instance, monkeypatch, capsys)
    fake.files[SET_JSON] = broken
    fake._bump(SET_JSON)
    seen = fake.modified[SET_JSON]
    _, out, err = cli("drop", "--stem", STEM)
    assert err == "" and out["status"] == "withdrawn"
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD)]
    assert fake.guards == [(SET_JSON, seen)]
    assert set_json_of(fake)["actions"] == []


@pytest.mark.parametrize("failure, kind", [(KadoAuthError("401"), "kado-auth"),
                                           (KadoToolError("kado-read returned an error: FORBIDDEN"),
                                            "kado-unreachable")])
def test_drop_stops_on_a_failed_set_read_and_writes_nothing(doc_mod, ins, instance, monkeypatch, capsys,
                                                            failure, kind):
    """Falsifies a failed read taken as absent: a refused key or any other Kado failure on the set read
    stops the run by its kind — nothing written, the stage and meta unchanged, the set JSON as it was."""
    cli, fake = delivered(doc_mod, ins, instance, monkeypatch, capsys)
    set_before = fake.files[SET_JSON]
    meta_before = meta_of(instance)
    fake.fail[("read_file", SET_JSON)] = failure
    code, out, err = cli("drop", "--stem", STEM)
    assert code == 0 and err == ""
    assert out["status"] == "stopped" and out["stem"] == STEM and out["error"]["kind"] == kind
    assert "problems" not in out
    untouched(instance, fake, meta_before, set_before)


def hashi_writes_after_the_read(fake, mutate) -> None:
    """Hashi rewrites the set between `drop`'s read and its write: `mutate(doc)` is applied once, right
    after the first read of the set JSON, and the file's `modified` moves on."""
    real = fake.read_file

    def read_then_hashi(path):
        out = real(path)
        if path == SET_JSON:
            fake.read_file = real
            doc = set_json_of(fake)
            mutate(doc)
            store_set(fake, doc)
        return out
    fake.read_file = read_then_hashi


def _apply(doc):
    doc["actions"][0]["applied"] = True


def _patch_without_applying(doc):
    doc["actions"][0]["destination"] = TARGET            # the fixer rewrote a field; nothing applied


@pytest.mark.parametrize("between, second", [(_apply, "refused"), (_patch_without_applying, "withdrawn")])
def test_drop_set_changed_under_the_guard_is_stopped_and_resumable(doc_mod, ins, instance, monkeypatch, capsys,
                                                                   between, second):
    """Falsifies an unguarded set write: Hashi writing the set between the read and the write refuses the
    guard (Kado's CONFLICT, as production sees it) — `set-changed`, nothing written, the stage kept. A
    second `drop` reads the set as it is now: refused `already-applied` when Hashi applied, withdrawn when
    it only patched."""
    cli, fake = delivered(doc_mod, ins, instance, monkeypatch, capsys)
    meta_before = meta_of(instance)
    seen = fake.modified[SET_JSON]
    hashi_writes_after_the_read(fake, between)
    code, out, err = cli("drop", "--stem", STEM)
    assert code == 0 and err == ""
    assert out["status"] == "stopped" and out["stem"] == STEM and out["problems"] == ["set-changed"]
    assert fake.guards == [(SET_JSON, seen)] and fake.writes == []
    assert [e for e in fake.events if e[0] == "write_note"] == []
    assert meta_of(instance) == meta_before and meta_before["withdrawn"] is False
    assert set_json_of(fake)["actions"][0].get("applied", False) is (between is _apply)
    fake.events.clear()
    fake.guards.clear()
    _, out, _ = cli("drop", "--stem", STEM)
    assert out["status"] == second
    if second == "refused":
        assert out["problems"] == ["already-applied"] and fake.writes == []
        assert meta_of(instance) == meta_before and set_json_of(fake)["actions"][0]["applied"] is True
    else:
        assert fake.guards == [(SET_JSON, fake.modified[SET_JSON] - 1)]
        assert set_json_of(fake)["actions"] == [] and meta_of(instance)["withdrawn"] is True


# ---------------------------------------------------------------- status and the CLI contract

def test_cli_status_names_the_state(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(), approve=False)
    assert run(ins, monkeypatch, capsys, ["status", "--stem", STEM], fake)[1] == {"state": "open", "stem": STEM}
    assert run(ins, monkeypatch, capsys, ["status", "--stem", "2026-W14_review"], fake)[1] == {
        "status": "not-found", "stem": "2026-W14_review"}


# ---------------------------------------------------------------- status and start: one function (T4.3)

SES_SCRIPT = SCRIPTS_DIR / "review-session.py"


@pytest.fixture
def ses():
    return _load(SES_SCRIPT, "review_session_script_t43")


def start_listing(ses, monkeypatch, capsys, fake) -> list:
    monkeypatch.setattr(ses, "KadoClient", fake)
    assert ses.main(["--profiles-dir", "profiles", "start", "--args=", "--today", "2026-11-12"]) == 0
    out, err = capsys.readouterr()
    assert MARKER not in out and err == ""
    out = json.loads(out)
    assert out["status"] == "ok", out
    return [(r["stem"], r["state"]) for r in out["open_reviews"]]


def set_applied(fake) -> None:
    doc = set_json_of(fake)
    for action in doc["actions"]:
        action["applied"] = True
    fake.files[SET_JSON] = (json.dumps(doc, indent=2) + "\n").encode("utf-8")


def test_cli_status_and_start_classify_a_stem_through_one_function_with_the_same_inputs(
        doc_mod, ins, ses, instance, monkeypatch, capsys):
    """Falsifies a `status` that classifies on its own (T4.2's interim `review_state(front, meta)`):
    both scripts must reach `review_state.stem_state` with the same document, meta, stem and inbox."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    assert cli("deliver", "--stem", STEM)[1]["status"] == "delivered"
    calls: list = []
    real = rs.stem_state

    def recording(vault_, doc, meta, stem, inbox):
        calls.append((vault_.client, copy.deepcopy(doc), copy.deepcopy(meta), stem, inbox))
        return real(vault_, doc, meta, stem, inbox)
    monkeypatch.setattr(rs, "stem_state", recording)
    assert cli("status", "--stem", STEM)[1] == {"state": "delivered", "stem": STEM}
    assert start_listing(ses, monkeypatch, capsys, fake) == [(STEM, "delivered")]
    assert len(calls) == 2 and calls[0] == calls[1]
    assert calls[0][0] is fake and calls[0][3:] == (STEM, INBOX)
    assert calls[0][1]["tomo"]["state"] == "approved" and calls[0][2]["steps_done"][-1] == "doc_mark"


def test_cli_status_and_start_agree_on_delivered_move_refused_applied_and_withdrawn(
        doc_mod, ins, ses, instance, monkeypatch, capsys):
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))        # new-note: a move_note
    assert cli("deliver", "--stem", STEM)[1]["status"] == "delivered"

    def both():
        return cli("status", "--stem", STEM)[1]["state"], start_listing(ses, monkeypatch, capsys, fake)
    assert both() == ("delivered", [(STEM, "delivered")])
    fake.files[TARGET] = NOTE                                 # the destination appeared: Hashi refuses the move
    assert both() == ("move-refused", [(STEM, "move-refused")])
    del fake.files[TARGET]
    del fake.files[NEW_NOTE]                                  # the copy moved by hand: nothing refused
    assert both() == ("delivered", [(STEM, "delivered")])
    set_applied(fake)                                         # Hashi wrote applied: reported once
    assert both() == ("applied", [(STEM, "applied")])
    assert meta_of(instance)["applied_reported"] is True
    assert both() == ("applied", [])                          # status still answers; the listing offered it once
    assert cli("drop", "--stem", STEM)[1] == {"status": "refused", "stem": STEM, "problems": ["already-applied"]}
    assert both() == ("applied", [])                          # the applied record survived the drop
    unapplied = set_json_of(fake)                             # a set Hashi never ran (test-only reset)
    for action in unapplied["actions"]:
        del action["applied"]
    fake.files[SET_JSON] = (json.dumps(unapplied, indent=2) + "\n").encode("utf-8")
    assert cli("drop", "--stem", STEM)[1]["status"] == "withdrawn"
    assert both() == (None, [])                               # withdrawn: never listed


def test_cli_status_and_start_agree_on_target_missing(doc_mod, ins, ses, instance, monkeypatch, capsys):
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())             # insert mode
    assert cli("deliver", "--stem", STEM)[1]["mode"] == "insert"
    assert (cli("status", "--stem", STEM)[1]["state"], start_listing(ses, monkeypatch, capsys, fake)) == (
        "delivered", [(STEM, "delivered")])
    del fake.files[TARGET]
    assert (cli("status", "--stem", STEM)[1]["state"], start_listing(ses, monkeypatch, capsys, fake)) == (
        "target-missing", [(STEM, "target-missing")])


def test_cli_status_stops_on_a_refused_set_probe(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    assert cli("deliver", "--stem", STEM)[1]["status"] == "delivered"
    fake.fail[("read_file", SET_JSON)] = KadoToolError("kado-read returned an error: FORBIDDEN")
    _, out, _ = cli("status", "--stem", STEM)
    assert out["status"] == "stopped" and out["error"]["kind"] == "kado-unreachable"


def test_cli_exit_codes_and_a_bare_class_name_on_stderr(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    for argv in (["preview", "--stem", "../x"], ["drop", "--stem", "."], ["nope", "--stem", STEM], ["preview"]):
        with pytest.raises(SystemExit) as exc:
            ins.main(["--profiles-dir", "profiles", *argv])
        assert exc.value.code == 2
    capsys.readouterr()

    def boom(*_args, **_kw):
        raise RuntimeError(f"secret {MARKER}")
    monkeypatch.setattr(ins, "read_document", boom)
    monkeypatch.setattr(ins, "KadoClient", fake)
    assert ins.main(["--profiles-dir", "profiles", "deliver", "--stem", STEM]) == 1
    out, err = capsys.readouterr()
    assert out == "" and err == "RuntimeError\n"
