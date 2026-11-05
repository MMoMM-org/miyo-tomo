#!/usr/bin/env python3
# version: 0.2.0
"""test_note_privacy.py — No user text in the output of the /note scripts (spec 044 T2.7).

CON-3 / F5-AC8: script stdout and stderr carry paths, states and counts only.
One walk runs every new script the way the /note skill does — session start,
process mode, outline, process files (also broken ones and one whose outline
lost a required point), new, stage, the filled-note check, a failed delivery,
session start with that kept draft, a taken and a clean deliver, drop — on a
fake vault whose request, source, template body and answers each carry their
own marker string. A second list runs one bad invocation per script family with
a marker in its arguments; neither stream may echo it.

USER_TEXT_FIELDS names every output field that carries user text by design,
which marker kinds it may carry and why. The walk then asserts:
- no marker on stderr, ever;
- no marker in stdout once the named fields are taken out;
- a named field carries only its own kinds;
- every named field really carried its marker once (no stale entry, and the
  fixture reaches every field it claims to cover).

Runs in tmp_path; scripts are loaded in-process with KadoClient replaced by
tests/note_fake_vault.NoteFakeVault. Never a live vault.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import note_fake_vault as nfv  # noqa: E402
from lib import note_meta  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402

# One marker per kind of user text; lowercase and `_` so it is also a valid token name.
MARKERS = {
    "request": "zzpriv_req_7f3a",
    "source": "zzpriv_src_7f3a",
    "template": "zzpriv_tpl_7f3a",
    "answer": "zzpriv_ans_7f3a",
}
KIND_OF = {"req": "request", "src": "source", "tpl": "template", "ans": "answer"}
MARKER_RE = re.compile(r"zzpriv_(req|src|tpl|ans)_7f3a")
REQ, SRC, TPL, ANS = (MARKERS[k] for k in ("request", "source", "template", "answer"))

# (script, subcommand, field) -> (marker kinds it may carry, why).
# Field syntax: dotted keys, `[]` walks a list; "EXISTS:" is the plain stdout line.
USER_TEXT_FIELDS = {
    ("note-session", "start", "process_template"):
        ({"request"}, "in --process mode the request text is the template stem"),
    ("note-session", "start", "kept_drafts[].title"):
        ({"answer"}, "the skill offers each kept draft by its title (SDD start output)"),
    ("template-outline", "-", "headings[].text"):
        ({"template"}, "the skill asks one question per heading"),
    ("template-outline", "-", "tokens[].name"):
        ({"template"}, "the skill fills each token by name"),
    ("template-outline", "-", "templater[].text"):
        ({"template"}, "the skill replaces each Templater span by its text"),
    ("note-process", "read", "required"):
        ({"template"}, "required points are heading names the user chose"),
    ("note-process", "read", "guidance"):
        ({"answer"}, "the skill shows the saved guidance before asking"),
    ("note-process", "read", "destination"):
        ({"answer"}, "the saved destination folder is a vault path"),
    ("note-process", "read", "missing_required[]"):
        ({"template"}, "names the saved heading the template's outline no longer has"),
    ("note-process", "write", "rejected_required"):
        ({"answer"}, "names the point the user typed that the outline lacks"),
    ("note-instructions", "new", "default_destination"):
        ({"answer"}, "the process file's destination folder, a vault path"),
    ("note-instructions", "stage", "title"):
        ({"answer"}, "the staged title is echoed for confirmation"),
    ("note-instructions", "stage", "inbox_file"):
        ({"answer"}, "the inbox path is built from the title"),
    ("note-instructions", "stage", "destination_file"):
        ({"answer"}, "destination folder plus title, a vault path"),
    ("note-instructions", "stage", "check.findings[].detail"):
        ({"template"}, "the filled-note check names each token left in the draft"),
    ("note-instructions", "deliver", "note_path"):
        ({"answer"}, "the delivered note's inbox path is built from the title"),
    ("note-instructions", "deliver", "exists_path"):
        ({"answer"}, "the taken inbox path is built from the title"),
    ("note-instructions", "deliver", "EXISTS:"):
        ({"answer"}, "the EXISTS line names the taken inbox path"),
    ("template-doctor", "filled-note", "findings[].detail"):
        ({"template"}, "the filled-note check names each token left in the note"),
}

TEMPLATE = "Templates/t_meeting.md"
OTHER_TEMPLATE = "Templates/t_problem.md"
SOURCE = "100 Inbox/Meeting raw.md"
TITLE = f"Review {ANS}"
DESTINATION = f"Atlas/{ANS}"
TEMPLATE_TEXT = f"""\
---
title: {{{{title}}}}
status: draft {TPL}
---
# Agenda {TPL}
A paragraph of template prose {TPL}.
{{{{{TPL}}}}}
<% tp.date.now("YYYY") + "{TPL}" %>
{{{{source_link}}}}
"""
SOURCE_TEXT = f"---\ntags: [x]\n---\nraw meeting notes {SRC}\n"
BAD_DRAFT = f"---\ntitle: {ANS}\n---\n# Agenda {TPL}\n{ANS} said yes\n{{{{{TPL}}}}}\n"
GOOD_DRAFT = f"---\ntitle: {ANS}\n---\n# Agenda {TPL}\n{ANS} said yes\n{{{{source_link}}}}\n"
CONFIG = {
    "profile": "miyo",
    "concepts": {"inbox": "100 Inbox/", "atomic_note": {"path": "Atlas/202 Notes/"}},
    "templates": {"base_path": "Templates/", "note_include": ["t_*"],
                  "mapping": {"daily": "t_day.md"}},
}
SCRIPTS = ("note-session", "template-outline", "note-process", "note-instructions",
           "template-doctor")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"),
                                                  SCRIPTS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── output handling ──────────────────────────────────────────────────────


def _take(node, parts: list[str]) -> list:
    """Return the values at a field path and blank them in place."""
    if not parts or not isinstance(node, dict):
        return []
    key, many = parts[0].removesuffix("[]"), parts[0].endswith("[]")
    if key not in node:
        return []
    if len(parts) == 1:
        value = node[key]
        node[key] = [] if many else ""
        return list(value) if many else [value]
    children = node[key] if many else [node[key]]
    return [v for child in children for v in _take(child, parts[1:])]


def _kinds(text: str) -> set[str]:
    return {KIND_OF[m] for m in MARKER_RE.findall(text)}


def _split_stdout(out: str) -> tuple[str | None, dict]:
    lines = out.splitlines()
    exists = lines.pop(0) if lines and lines[0].startswith("EXISTS:") else None
    return exists, json.loads("\n".join(lines))


class Walk:
    """Runs the scripts in-process and keeps every call's output."""

    def __init__(self, capsys, mods):
        self.capsys, self.mods, self.calls, self.bad_calls = capsys, mods, [], []

    def _call(self, script: str, argv: list[str]) -> dict:
        try:
            rc = self.mods[script].main(argv)
        except SystemExit as exc:
            rc = exc.code
        out, err = self.capsys.readouterr()
        return {"script": script, "argv": argv, "rc": rc, "stdout": out, "stderr": err}

    def run(self, script: str, sub: str, argv: list[str]) -> tuple[int, dict]:
        call = self._call(script, argv if sub == "-" else [sub, *argv])
        call["sub"] = sub
        self.calls.append(call)
        return call["rc"], _split_stdout(call["stdout"])[1]

    def run_bad(self, script: str, sub: str, argv: list[str]) -> int:
        """Run a bad invocation; its stdout is not JSON, so it is kept apart."""
        call = self._call(script, argv)
        call["sub"] = sub
        self.bad_calls.append(call)
        return call["rc"]


def _named(call: dict) -> dict:
    return {f: kinds for (s, sub, f), (kinds, _) in USER_TEXT_FIELDS.items()
            if (s, sub) == (call["script"], call["sub"])}


def _audit(call: dict) -> tuple[dict, str]:
    """Return {field: kinds seen} and stdout with every named field taken out."""
    exists, payload = _split_stdout(call["stdout"])
    rest, seen = copy.deepcopy(payload), {}
    for field in _named(call):
        if field == "EXISTS:":
            values, exists = ([exists] if exists else []), None
        else:
            values = _take(rest, field.split("."))
        seen[field] = set().union(*(_kinds(str(v)) for v in values)) if values else set()
    leftover = (exists or "") + json.dumps(rest, ensure_ascii=False)
    return seen, leftover


# ── the walk ─────────────────────────────────────────────────────────────


@pytest.fixture
def walk(tmp_path, monkeypatch, capsys):
    """Run the whole /note flow once; return the Walk, the vault and the staged source."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "vault-config.yaml").write_text(yaml.safe_dump(CONFIG),
                                                           encoding="utf-8")
    vault = nfv.NoteFakeVault({TEMPLATE: TEMPLATE_TEXT, OTHER_TEMPLATE: "# x\n",
                               SOURCE: SOURCE_TEXT})
    mods = {name: _load(name) for name in SCRIPTS}
    for name in ("note-session", "template-outline", "note-instructions"):
        monkeypatch.setattr(mods[name], "KadoClient", vault)
    w = Walk(capsys, mods)
    _session(w)
    _process_mode(w, tmp_path)
    _broken_process_files(w, tmp_path)
    staged_source = _draft_and_deliver(w, tmp_path, vault)
    _drop(w)
    _bad_invocations(w)
    return w, vault, staged_source


def _session(w: Walk) -> None:
    assert w.run("note-session", "start", [f"--args={REQ} about the meeting"])[0] == 0
    assert w.run("note-session", "start", [f"--args=--process {REQ}"])[0] == 0
    assert w.run("note-session", "match", ["--globs", f"t_*,{ANS}*"])[0] == 0


def _process_mode(w: Walk, root: Path) -> None:
    outline = "tomo-tmp/note/process-outline.json"
    (root / "guidance.md").write_text(f"Ask about {ANS} first.\n", encoding="utf-8")
    assert w.run("template-outline", "-", ["--template", TEMPLATE, "--out", outline])[0] == 0
    assert w.run("note-process", "read", ["--template", "t_meeting", "--outline", outline])[0] == 0
    rc, _ = w.run("note-process", "write", ["--template", "t_meeting", "--outline", outline,
                                            "--required", f"Point {ANS}"])
    assert rc == 1
    rc, _ = w.run("note-process", "write", [
        "--template", "t_meeting", "--outline", outline, "--destination", DESTINATION,
        "--required", f"Agenda {TPL}", "--guidance-file", str(root / "guidance.md")])
    assert rc == 0
    assert w.run("note-process", "read", ["--template", "t_meeting", "--outline", outline])[0] == 0
    assert w.run("note-process", "decline", ["--template", "t_problem"])[0] == 0
    _required_point_gone(w)


def _required_point_gone(w: Walk) -> None:
    """The saved required point is no longer a heading: missing_required names it."""
    outline = "tomo-tmp/note/other-outline.json"
    assert w.run("template-outline", "-", ["--template", OTHER_TEMPLATE, "--out", outline])[0] == 0
    rc, out = w.run("note-process", "read", ["--template", "t_meeting", "--outline", outline])
    assert rc == 0 and out["missing_required"] == [f"Agenda {TPL}"]


# stem -> process file text; each one is broken and holds markers.
BROKEN_PROCESS_FILES = {
    "t_broken_fence": f"---\ndestination: Atlas/{ANS}\nrequired: [Agenda {TPL}]\n{ANS}\n",
    "t_broken_yaml": f"---\nrequired: [Agenda {TPL}\n{ANS}: : x\n---\nAsk {ANS}\n",
    "t_broken_destination": f"---\ndestination: ../{ANS}\n---\nAsk {ANS}\n",
    "t_broken_required": f"---\nrequired: Agenda {TPL}\n---\nAsk {ANS}\n",
}


def _broken_process_files(w: Walk, root: Path) -> None:
    folder = root / "config" / "note-processes"
    for stem, text in BROKEN_PROCESS_FILES.items():
        (folder / f"{stem}.md").write_text(text, encoding="utf-8")
        rc, out = w.run("note-process", "read", ["--template", stem])
        assert rc == 0 and out["exists"] is True and out["error"], stem


def _draft_and_deliver(w: Walk, root: Path, vault) -> str:
    rc, new = w.run("note-instructions", "new", ["--template", TEMPLATE, "--source", SOURCE])
    assert rc == 0
    stem = new["stem"]
    stage = note_meta.stage_dir(root, stem)
    staged_source = (stage / "source.md").read_text(encoding="utf-8")
    assert w.run("template-outline", "-", ["--template", TEMPLATE, "--stage", stem])[0] == 0
    assert w.run("note-process", "read", ["--template", "t_meeting", "--outline",
                                          str(stage / "outline.json")])[0] == 0
    (stage / "draft.md").write_text(BAD_DRAFT, encoding="utf-8")
    rc, staged = w.run("note-instructions", "stage", ["--stem", stem, "--title", TITLE,
                                                      "--keep-source", "true"])
    assert rc == 0 and staged["check"]["ok"] is False
    assert w.run("template-doctor", "filled-note", ["--note",
                                                    str(stage / "note.md")])[0] == 1
    (stage / "draft.md").write_text(GOOD_DRAFT, encoding="utf-8")
    rc, staged = w.run("note-instructions", "stage", ["--stem", stem])
    assert rc == 0 and staged["check"]["ok"] is True
    assert w.run("template-doctor", "filled-note", ["--note",
                                                    str(stage / "note.md")])[0] == 0
    _deliver_three_ways(w, vault, stem, staged["inbox_file"])
    return staged_source


def _deliver_three_ways(w: Walk, vault, stem: str, inbox_file: str) -> None:
    deliver = ["--stem", stem]
    vault.fail[("write_note", inbox_file)] = KadoError(f"503 {ANS}")
    assert w.run("note-instructions", "deliver", deliver)[0] == 1
    # The failed delivery is a started one: the next session start offers it as kept.
    rc, out = w.run("note-session", "start", ["--args="])
    assert rc == 0 and [d["stem"] for d in out["kept_drafts"]] == [stem]
    vault.fail.clear()
    vault.files[inbox_file] = f"another note {ANS}\n"
    assert w.run("note-instructions", "deliver", deliver)[0] == 3
    del vault.files[inbox_file]
    rc, out = w.run("note-instructions", "deliver", deliver)
    assert rc == 0 and out["status"] == "delivered"


def _drop(w: Walk) -> None:
    rc, new = w.run("note-instructions", "new", ["--template", TEMPLATE])
    assert rc == 0
    assert w.run("note-instructions", "drop", ["--stem", new["stem"]])[0] == 0


UNKNOWN_STEM = "2000-01-01_000000"


def _bad_invocations(w: Walk) -> None:
    """One bad invocation per script family, each with a marker in its arguments."""
    bad = [
        ("note-instructions", "stage", ["stage", "--stem", UNKNOWN_STEM, "--title", TITLE]),
        ("note-instructions", "stage", ["stage", "--stem", f"{UNKNOWN_STEM}{ANS}"]),
        ("note-instructions", "drop", ["drop", "--stem", f"{UNKNOWN_STEM}{ANS}"]),
        # An empty glob list has no room for a marker; the config path carries it.
        ("note-session", "match", ["--config", f"config/{REQ}.yaml", "match", "--globs", " , "]),
        ("note-process", "read", ["read", "--template", f"../{TPL}"]),
    ]
    for script, sub, argv in bad:
        assert w.run_bad(script, sub, argv) == 2, (script, sub, argv)


# ── assertions ───────────────────────────────────────────────────────────


def _label(call: dict) -> str:
    return f"{call['script']} {call['sub']} (exit {call['rc']})"


def test_every_script_ran_in_the_walk(walk):
    w, _, _ = walk
    assert {c["script"] for c in w.calls} == set(SCRIPTS)


def test_no_marker_on_stderr_of_any_script(walk):
    w, _, _ = walk
    leaks = [(_label(c), sorted(_kinds(c["stderr"]))) for c in w.calls if _kinds(c["stderr"])]
    assert leaks == []


def test_bad_invocations_echo_no_marker(walk):
    w, _, _ = walk
    assert {(c["script"], c["sub"]) for c in w.bad_calls} == {
        ("note-instructions", "stage"), ("note-instructions", "drop"),
        ("note-session", "match"), ("note-process", "read")}
    leaks = [(_label(c), c["argv"], sorted(_kinds(c["stdout"] + c["stderr"])))
             for c in w.bad_calls if _kinds(c["stdout"] + c["stderr"])]
    assert leaks == []


def test_no_marker_in_stdout_outside_the_named_fields(walk):
    w, _, _ = walk
    leaks = []
    for call in w.calls:
        _, leftover = _audit(call)
        if _kinds(leftover):
            leaks.append((_label(call), sorted(_kinds(leftover)), leftover))
    assert leaks == []


def test_named_fields_carry_only_their_own_kinds(walk):
    w, _, _ = walk
    wrong = []
    for call in w.calls:
        allowed = _named(call)
        for field, seen in _audit(call)[0].items():
            if seen - allowed[field]:
                wrong.append((_label(call), field, sorted(seen - allowed[field])))
    assert wrong == []


def test_every_named_field_carried_its_marker_once(walk):
    """A named field the walk never fills is either stale or untested: both fail."""
    w, _, _ = walk
    used = set()
    for call in w.calls:
        for field, seen in _audit(call)[0].items():
            if seen:
                used.add((call["script"], call["sub"], field))
    assert sorted(set(USER_TEXT_FIELDS) - used) == []


def test_every_marker_reached_the_scripts(walk):
    """The fixture is live: each kind was really read by a script, not just placed."""
    w, vault, staged_source = walk
    assert SRC in staged_source
    delivered = [p for p in vault.writes if p.endswith(".md") and "_instructions" not in p]
    assert any(ANS in vault.text(p) for p in delivered)
    assert any(TPL in json.dumps(_split_stdout(c["stdout"])[1]) for c in w.calls
               if c["script"] == "template-outline")
    assert any(REQ in c["stdout"] for c in w.calls if c["script"] == "note-session")


def test_user_text_fields_give_a_reason_each():
    assert all(kinds and reason.strip() for kinds, reason in USER_TEXT_FIELDS.values())
