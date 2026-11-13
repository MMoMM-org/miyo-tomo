#!/usr/bin/env python3
# version: 0.3.3
"""test_review_privacy.py — No journal content in the output of the /review scripts (spec 045 T5.4).

PRD F7-AC1 / SDD ADR-9: Tomo's own records — stdout, stderr and the files under
tomo-tmp/review/ that outlive a step — carry paths, dates, counts and states only.
One walk runs every review script and every subcommand of it, in-process, on
one fake vault (tests/review_privacy_fixture.py: the markers, the config, the
vault and the proposals) whose daily text, journal answers, tracker values,
weekly-note text and the model's proposals each carry their own marker string,
plus one readable tracker value (`READABLE`) the habits do count: session start (a
period, `setup`, the open reviews), `match` and `setup-input` for both kinds,
the week read, the document write, parse, preview with a place problem,
preview and deliver with a `--place-anchor` that is a marker-bearing heading
of the target — the delivery stopped at the set MD, resumed without the pick
(refused `anchor-needed`, the headings named again, the pick never in
meta.json) and then with it — status, a second deliver (set-exists), drop
after a complete delivery; the month read, a write refused by `review-exists`, `replace`
without a flag, `--confirm` and `--abort`, a new-note preview, a delivery
that fails at the set MD, drop after it. One forced exception per script,
raised while a marker-bearing text is being parsed, must leave only the
class name on stderr. A list of bad invocations puts a marker into the
arguments; neither stream may echo it.

USER_TEXT_FIELDS names every stdout field that carries user text by design,
which marker kinds it may carry and why. The walk then asserts:
- every subcommand the real parsers know ran (a new one without privacy
  coverage fails here);
- no marker on stderr, ever — the bad invocations and the forced exceptions
  included;
- no marker in stdout once the named fields are taken out;
- a named field carries only its own kinds, and every named field really
  carried its marker (no stale entry);
- no marker in any file under tomo-tmp/review/ that a step leaves behind;
- the readable tracker value reaches read.json and the document's habits
  line, and nothing else of Tomo's: not stderr, not stdout outside the named
  fields, no working file but read.json;
- every marker kind really reached the scripts: the daily text, the journal
  answer and the tracker values were in read.json before the write deleted
  it, the tracker marker's days are named unreadable in the habits line;
- read.json and proposals.json are gone after `write`, `replace --confirm`
  and `replace --abort`, and kept after a refused or failed write.

Runs in tmp_path; the scripts are loaded in-process with KadoClient replaced
by tests/review_fake_vault.ReviewFakeVault. All data is synthetic. Never a
live vault.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_privacy_fixture import (  # noqa: E402
    ANCHOR, ANS, CONFIG, DAY, INBOX, KIND_OF, MARKER_RE, PRP, READABLE, TRK, WKL, build_vault, proposals,
)
from lib import review_day as rday  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402

# (script, subcommand, field) -> (marker kinds it may carry, why).
# Field syntax: dotted keys, `[]` walks a list.
USER_TEXT_FIELDS = {
    ("review-session", "match", "anchor_candidates[]"):
        ({"weekly"}, "without a template heading to propose the place from, the headings of the two most recent "
                     "periodic notes are offered for the anchor pick (F1-AC7, Phase 6 live-walk fix)"),
    ("review-session", "match", "proposal.place.anchor"):
        ({"weekly"}, "--anchor echoes the heading the user picked from anchor_candidates[] or typed: the periodic "
                     "note's own text, the same rule as --place-anchor (fix round 1 of the live-walk fix)"),
    ("review-instructions", "preview", "section_md"):
        ({"proposal"}, "the preview prints the section as it will land, so the user reads it before Deliver (F5-AC2)"),
    ("review-instructions", "preview", "headings[]"):
        ({"weekly"}, "a place problem names the target note's headings, so the user can choose one (F5-AC7)"),
    ("review-instructions", "preview", "place.anchor"):
        ({"weekly"}, "--place-anchor echoes the heading the user picked from headings[]: the target's own text"),
    ("review-instructions", "deliver", "place.anchor"):
        ({"weekly"}, "--place-anchor echoes the heading the user picked from headings[]: the target's own text"),
    ("review-instructions", "deliver", "headings[]"):
        ({"weekly"}, "a resume of a delivery begun with --place-anchor and run without it (anchor-needed) names the "
                     "target note's headings again, so the user can choose one; the pick itself never enters "
                     "meta.json (fix #258)"),
}

TODAY = "2026-11-11"
WEEK_STEM, MONTH_STEM = "2026-W13_review", "2026-03_review"
WEEK_DOC, MONTH_DOC = f"{INBOX}2026-W13 Review.md", f"{INBOX}2026-03 Review.md"
WEEK_SET_MD, MONTH_SET_MD = f"{INBOX}{WEEK_STEM}_instructions.md", f"{INBOX}{MONTH_STEM}_instructions.md"
SCRIPTS = ("review-session", "review-read", "review-doc", "review-instructions")


# ── loading and running ──────────────────────────────────────────────────


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"review_privacy_{name.replace('-', '_')}",
                                                  SCRIPTS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # the scripts' dataclasses resolve their module here
    spec.loader.exec_module(mod)
    return mod


def _subcommands(mod) -> set[str]:
    """What the script's real parser accepts; `-` for a script without subcommands."""
    subs = [a for a in mod.build_parser()._actions if isinstance(a, argparse._SubParsersAction)]
    return set(subs[0].choices) if subs else {"-"}


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


def _kinds_and_readable(text: str) -> set[str]:
    return _kinds(text) | ({"readable"} if READABLE in text else set())


def _payload(out: str) -> dict:
    return json.loads(out) if out.strip() else {}


@contextmanager
def _patched(obj, name: str, value):
    original = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, original)


class Walk:
    """Runs the scripts in-process and keeps every call's output and Tomo's files after it."""

    def __init__(self, capsys, mods, root: Path, vault):
        self.capsys, self.mods, self.root, self.vault = capsys, mods, root, vault
        self.subcommands = {name: _subcommands(mod) for name, mod in mods.items()}
        self.calls, self.bad_calls, self.forced_calls = [], [], []
        self.stage_files: dict = {}
        self.read_files: dict = {}          # label -> read.json text, taken before the write deletes it

    def _call(self, script: str, argv: list[str]) -> dict:
        try:
            rc = self.mods[script].main(argv)
        except SystemExit as exc:
            rc = exc.code
        except Exception:  # noqa: BLE001 — what the interpreter would print at process exit
            sys.stderr.write(traceback.format_exc())
            rc = 1
        out, err = self.capsys.readouterr()
        return {"script": script, "argv": argv, "rc": rc, "stdout": out, "stderr": err,
                "tmp_leaks": self._tmp_leaks()}

    def _tmp_leaks(self) -> list:
        """Markers or the readable value in any file under tomo-tmp/review/ except the two the model
        reads and writes by design."""
        leaks = []
        for path in sorted((self.root / "tomo-tmp").rglob("*")):
            if path.is_file() and path.name not in ("read.json", "proposals.json"):
                kinds = _kinds_and_readable(path.read_text(encoding="utf-8", errors="replace"))
                if kinds:
                    leaks.append((str(path.relative_to(self.root)), sorted(kinds)))
        return leaks

    def _record(self, bucket: list, script: str, sub: str, argv: list[str]) -> dict:
        call = self._call(script, ["--profiles-dir", "profiles", *argv])
        call["sub"] = sub
        bucket.append(call)
        return call

    def run(self, script: str, sub: str, argv: list[str]) -> tuple[int, dict]:
        call = self._record(self.calls, script, sub, argv)
        return call["rc"], _payload(call["stdout"])

    def run_bad(self, script: str, sub: str, argv: list[str]) -> int:
        """A bad invocation: its stdout is not JSON, so it is kept apart."""
        return self._record(self.bad_calls, script, sub, argv)["rc"]

    def run_forced(self, script: str, sub: str, argv: list[str]) -> dict:
        """A run under a forced exception: judged on exit code and stderr only."""
        return self._record(self.forced_calls, script, sub, argv)

    # the stage of a stem
    def stage(self, stem: str) -> Path:
        return self.root / "tomo-tmp" / "review" / stem

    def write_proposals(self, stem: str, kind: str) -> Path:
        path = self.stage(stem) / "proposals.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposals(kind)), encoding="utf-8")
        return path

    def note_stage_files(self, label: str, stem: str) -> None:
        stage = self.stage(stem)
        self.stage_files[label] = ((stage / "read.json").exists(), (stage / "proposals.json").exists())

    def keep_read_file(self, label: str, read_path: str) -> None:
        self.read_files[label] = Path(read_path).read_text(encoding="utf-8")


def _named(call: dict) -> dict:
    return {f: kinds for (s, sub, f), (kinds, _) in USER_TEXT_FIELDS.items()
            if (s, sub) == (call["script"], call["sub"])}


def _audit(call: dict) -> tuple[dict, str]:
    """Return {field: kinds seen} and stdout with every named field taken out."""
    rest, seen = copy.deepcopy(_payload(call["stdout"])), {}
    for field in _named(call):
        values = _take(rest, field.split("."))
        seen[field] = set().union(*(_kinds(str(v)) for v in values)) if values else set()
    return seen, json.dumps(rest, ensure_ascii=False)


# ── the walk ─────────────────────────────────────────────────────────────


@pytest.fixture
def walk(tmp_path, monkeypatch, capsys):
    """Run the whole /review flow once; return the Walk."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    (tmp_path / "config" / "vault-config.yaml").write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    vault = build_vault()
    mods = {name: _load(name) for name in SCRIPTS}
    for mod in mods.values():
        monkeypatch.setattr(mod, "KadoClient", vault)
    w = Walk(capsys, mods, tmp_path, vault)
    _session(w)
    _week(w)
    _month(w)
    _forced_exceptions(w)
    _bad_invocations(w)
    return w


def _approve(w: Walk, doc_path: str, user_line: str | None = None) -> None:
    """The user ticks Approved in Obsidian and may add a line of their own under Open."""
    text = w.vault.files[doc_path].replace("- [ ] Approved", "- [x] Approved", 1)
    if user_line is not None:
        text = text.replace("## Open\n", f"## Open\n{user_line}\n", 1)
    w.vault.files[doc_path] = text
    w.vault.modified[doc_path] += 1


def _session(w: Walk) -> None:
    for text in ("2026-W13", "setup", "month"):
        rc, out = w.run("review-session", "start", ["start", f"--args={text}", "--today", TODAY])
        assert rc == 0 and out["status"] == "ok" and out["request"]["kind"] in ("week", "month", "setup"), out
    for kind in ("week", "month"):
        rc, out = w.run("review-session", "match", ["match", "--kind", kind, "--today", TODAY])
        assert rc == 0 and out["status"] == "ok", out
        confirmed = w.root / f"confirmed-{kind}.json"
        confirmed.write_text(json.dumps({"kind": kind, **out["proposal"]}), encoding="utf-8")
        rc, out = w.run("review-session", "setup-input",
                        ["setup-input", "--kind", kind, "--confirmed", str(confirmed), "--today", TODAY])
        assert rc == 0 and out["status"] == "ok", out
    # no template mapped and no anchor configured: the candidates of the templates folder (names only) and the
    # recent weekly notes' headings (the marker-bearing field named above) reach stdout; a chosen template is read
    no_mapping = copy.deepcopy(CONFIG)
    no_mapping["templates"]["mapping"] = {"daily": "t_day.md"}
    no_mapping["review"] = {k: CONFIG["review"][k] for k in ("language", "week", "daily")}
    (w.root / "config" / "no-mapping.yaml").write_text(yaml.safe_dump(no_mapping), encoding="utf-8")
    rc, out = w.run("review-session", "match",
                    ["--config", "config/no-mapping.yaml", "match", "--kind", "week", "--today", TODAY])
    assert rc == 0 and out["template_candidates"] == ["t_week"] and out["needs_anchor"] is True, out
    assert any(WKL in h for h in out["anchor_candidates"]), "the recent weekly note's marker heading is a candidate"
    picked = next(h for h in out["anchor_candidates"] if WKL in h)
    rc, out = w.run("review-session", "match",
                    ["--config", "config/no-mapping.yaml", "match", "--kind", "week", "--template", "t_week",
                     "--today", TODAY])
    assert rc == 0 and out["proposal"]["template"] == "t_week.md" and "needs_anchor" not in out, out
    # `0 none` and the picked heading carried on a rerun: no candidates, no anchor question, the anchor echoed
    rc, out = w.run("review-session", "match",
                    ["--config", "config/no-mapping.yaml", "match", "--kind", "week", "--template", "none",
                     "--anchor", picked, "--today", TODAY])
    assert rc == 0 and "template_candidates" not in out and "needs_anchor" not in out, out
    assert out["proposal"]["template"] is None and out["proposal"]["place"]["anchor"] == picked, out


def _week(w: Walk) -> None:
    rc, out = w.run("review-read", "-", ["--period", "2026-W13", "--kind", "week", "--today", TODAY])
    assert rc == 0 and out["status"] == "ok" and out["nothing_to_review"] is False, out
    assert out["report"]["days"][2]["linked"][0]["state"] == "read"
    w.keep_read_file("week", out["read_path"])
    path = w.write_proposals(WEEK_STEM, "week")
    rc, out = w.run("review-doc", "write", ["write", "--stem", WEEK_STEM, "--proposals", str(path),
                                            "--run-id", "r-week", "--today", TODAY])
    assert rc == 0 and out["status"] == "written" and out["target_exists"] is True, out
    assert out["counts"]["habits"] >= 1, "the trackers were read: habits rendered"
    w.note_stage_files("week-written", WEEK_STEM)
    rc, out = w.run("review-session", "start", ["start", "--args=", "--today", TODAY])
    assert rc == 0 and [(r["stem"], r["state"]) for r in out["open_reviews"]] == [(WEEK_STEM, "open")], out
    rc, out = w.run("review-doc", "parse", ["parse", "--stem", WEEK_STEM])
    assert rc == 0 and out["status"] == "ok" and out["approved"] is False, out
    _approve(w, WEEK_DOC, user_line=f"- [x] user added {PRP}")
    rc, out = w.run("review-doc", "parse", ["parse", "--stem", WEEK_STEM])
    assert rc == 0 and out["approved"] is True and out["counts"]["added"] == 1, out
    rc, out = w.run("review-instructions", "preview", ["preview", "--stem", WEEK_STEM])
    assert rc == 0 and out["problems"] == ["place-missing"] and ANCHOR in out["headings"], out
    # the user picks a heading from that list: preview and deliver echo it as the place; the delivery stops at the
    # set MD, the listing's Resume (no pick) is refused with the headings, the resume with the pick lands
    rc, out = w.run("review-instructions", "preview", ["preview", "--stem", WEEK_STEM, "--place-anchor", ANCHOR])
    assert rc == 0 and out["problems"] == [] and out["place"]["anchor"] == ANCHOR, out
    w.vault.fail[("write_note", WEEK_SET_MD)] = KadoError(f"503 while writing {ANCHOR} {DAY}")
    rc, out = w.run("review-instructions", "deliver", ["deliver", "--stem", WEEK_STEM, "--place-anchor", ANCHOR])
    assert rc == 0 and out["status"] == "stopped" and out["failed_step"] == "set_md", out
    w.vault.fail.clear()
    rc, out = w.run("review-instructions", "deliver", ["deliver", "--stem", WEEK_STEM])
    assert rc == 0 and out["status"] == "refused" and out["problems"] == ["anchor-needed"], out
    assert ANCHOR in out["headings"], out
    rc, out = w.run("review-instructions", "deliver", ["deliver", "--stem", WEEK_STEM, "--place-anchor", ANCHOR])
    assert rc == 0 and out["status"] == "resumed" and out["place"]["anchor"] == ANCHOR, out
    rc, out = w.run("review-instructions", "status", ["status", "--stem", WEEK_STEM])
    assert rc == 0 and out == {"state": "delivered", "stem": WEEK_STEM}, out
    rc, out = w.run("review-session", "start", ["start", "--args=", "--today", TODAY])
    assert rc == 0 and [(r["stem"], r["state"]) for r in out["open_reviews"]] == [(WEEK_STEM, "delivered")], out
    rc, out = w.run("review-instructions", "deliver", ["deliver", "--stem", WEEK_STEM, "--place-anchor", ANCHOR])
    assert rc == 0 and out["status"] == "refused" and out["problems"] == ["set-exists"], out
    rc, out = w.run("review-instructions", "drop", ["drop", "--stem", WEEK_STEM])
    assert rc == 0 and out["status"] == "withdrawn", out
    rc, out = w.run("review-instructions", "status", ["status", "--stem", WEEK_STEM])
    assert rc == 0 and out == {"state": None, "stem": WEEK_STEM}, out


def _month_read(w: Walk) -> Path:
    rc, out = w.run("review-read", "-", ["--period", "2026-03", "--kind", "month", "--today", TODAY])
    assert rc == 0 and out["status"] == "ok" and out["report"]["weekly_status"] == "found", out
    w.keep_read_file("month", out["read_path"])
    return w.write_proposals(MONTH_STEM, "month")


def _month(w: Walk) -> None:
    path = _month_read(w)
    rc, out = w.run("review-doc", "write", ["write", "--stem", MONTH_STEM, "--proposals", str(path),
                                            "--run-id", "r-month", "--today", TODAY])
    assert rc == 0 and out["status"] == "written" and out["target_exists"] is False, out
    w.note_stage_files("month-written", MONTH_STEM)
    # start over: a second Pass 1 is refused, then replaced on confirmation
    path = _month_read(w)
    with _patched(rd, "check_items", _raise_with(lambda proposals, read: json.dumps(proposals))):
        call = w.run_forced("review-doc", "write", ["write", "--stem", MONTH_STEM, "--proposals", str(path),
                                                    "--today", TODAY])
    assert call["rc"] == 1
    w.note_stage_files("month-write-raised", MONTH_STEM)
    rc, out = w.run("review-doc", "write", ["write", "--stem", MONTH_STEM, "--proposals", str(path),
                                            "--run-id", "r-month-2", "--today", TODAY])
    assert rc == 0 and out["status"] == "refused" and out["problems"] == ["review-exists"], out
    w.note_stage_files("month-refused", MONTH_STEM)
    rc, out = w.run("review-doc", "replace", ["replace", "--stem", MONTH_STEM, "--today", TODAY])
    assert rc == 0 and out["status"] == "needs-confirm", out
    rc, out = w.run("review-doc", "replace", ["replace", "--stem", MONTH_STEM, "--confirm", "--run-id", "r-month-3",
                                              "--today", TODAY])
    assert rc == 0 and out["status"] == "replaced", out
    w.note_stage_files("month-replaced", MONTH_STEM)
    _month_read(w)
    rc, out = w.run("review-doc", "replace", ["replace", "--stem", MONTH_STEM, "--abort", "--today", TODAY])
    assert rc == 0 and out["status"] == "aborted", out
    w.note_stage_files("month-aborted", MONTH_STEM)
    # Pass 2 in new-note mode, failing at the set MD, then dropped
    rc, out = w.run("review-doc", "parse", ["parse", "--stem", MONTH_STEM])
    assert rc == 0 and out["status"] == "ok", out
    _approve(w, MONTH_DOC)
    rc, out = w.run("review-instructions", "preview", ["preview", "--stem", MONTH_STEM])
    assert rc == 0 and out["mode"] == "new-note" and out["problems"] == [] and "templater_hint" in out["notices"], out
    w.vault.fail[("write_note", MONTH_SET_MD)] = KadoError(f"503 while writing {DAY} {ANS} {PRP}")
    rc, out = w.run("review-instructions", "deliver", ["deliver", "--stem", MONTH_STEM])
    assert rc == 0 and out["status"] == "stopped" and out["failed_step"] == "set_md", out
    w.vault.fail.clear()
    rc, out = w.run("review-session", "start", ["start", "--args=", "--today", TODAY])
    assert rc == 0 and (MONTH_STEM, "failed-delivery") in [(r["stem"], r["state"]) for r in out["open_reviews"]], out
    rc, out = w.run("review-instructions", "drop", ["drop", "--stem", MONTH_STEM])
    assert rc == 0 and out["status"] == "withdrawn" and "note" in out["paths"], out
    rc, out = w.run("review-instructions", "status", ["status", "--stem", MONTH_STEM])
    assert rc == 0 and out == {"state": None, "stem": MONTH_STEM}, out


def _raise_with(message_of):
    """A replacement that raises with the marker-bearing text it was handed in the message."""
    def boom(*args, **kwargs):
        raise RuntimeError(f"cannot parse: {message_of(*args, **kwargs)}")
    return boom


_REAL_FIELDS = rday._fields


def _fields_raising_on_a_marker_line(lines):
    """The daily field parser, failing on the first line that carries a marker — with that line."""
    lines = list(lines)
    hit = next((line for line in lines if MARKER_RE.search(line)), None)
    if hit is not None:
        raise ValueError(f"cannot parse the line {hit!r}")
    return _REAL_FIELDS(lines)


def _forced_exceptions(w: Walk) -> None:
    """One unexpected exception per script, raised while marker-bearing text is in hand."""
    with _patched(rday, "_fields", _fields_raising_on_a_marker_line):
        w.run_forced("review-read", "-", ["--period", "2026-W13", "--kind", "week", "--today", TODAY])
    with _patched(rdp, "parse_document", _raise_with(lambda text, **kw: text)):
        w.run_forced("review-doc", "parse", ["parse", "--stem", WEEK_STEM])
        w.run_forced("review-instructions", "preview", ["preview", "--stem", WEEK_STEM])
    with _patched(w.mods["review-session"], "open_reviews",
                  _raise_with(lambda docs, *a, **kw: f"{DAY} {ANS} {TRK} {PRP} {WKL} {docs}")):
        w.run_forced("review-session", "start", ["start", "--args=", "--today", TODAY])


def _bad_invocations(w: Walk) -> None:
    """One bad invocation per script family, each with a marker in its arguments."""
    bad = [
        ("review-doc", "parse", ["parse", "--stem", f"../{PRP}"]),
        ("review-instructions", "preview", ["preview", "--stem", f"../{DAY}"]),
        ("review-read", "-", ["--period", DAY, "--kind", "week", "--today", TODAY]),
        ("review-session", "setup-input", ["setup-input", "--kind", "week", "--confirmed", f"{ANS}.json"]),
        ("review-session", "match", ["match", "--kind", "week", "--format", WKL, "--first-day", "monday"]),
    ]
    for script, sub, argv in bad:
        assert w.run_bad(script, sub, argv) == 2, (script, sub, argv)


# ── assertions ───────────────────────────────────────────────────────────


def _label(call: dict) -> str:
    return f"{call['script']} {call['sub']} (exit {call['rc']})"


def test_every_script_and_every_subcommand_ran_in_the_walk(walk):
    """Enumerated from the real parsers: a new subcommand without privacy coverage fails here."""
    expected = {(script, sub) for script in SCRIPTS for sub in walk.subcommands[script]}
    assert expected >= {("review-session", "start"), ("review-read", "-"), ("review-doc", "replace"),
                        ("review-instructions", "drop")}
    assert {(c["script"], c["sub"]) for c in walk.calls} == expected


def test_no_marker_on_stderr_of_any_script(walk):
    calls = walk.calls + walk.bad_calls + walk.forced_calls
    leaks = [(_label(c), sorted(_kinds(c["stderr"]))) for c in calls if _kinds(c["stderr"])]
    assert leaks == []


def test_a_forced_exception_leaves_only_its_class_name_on_stderr(walk):
    assert {(c["script"], c["sub"]) for c in walk.forced_calls} == {
        ("review-read", "-"), ("review-doc", "parse"), ("review-doc", "write"),
        ("review-instructions", "preview"), ("review-session", "start")}
    for call in walk.forced_calls:
        assert call["rc"] == 1 and call["stdout"] == "", _label(call)
        assert call["stderr"] in ("ValueError\n", "RuntimeError\n"), (_label(call), call["stderr"])


def test_bad_invocations_echo_no_marker(walk):
    assert {(c["script"], c["sub"]) for c in walk.bad_calls} == {
        ("review-doc", "parse"), ("review-instructions", "preview"), ("review-read", "-"),
        ("review-session", "setup-input"), ("review-session", "match")}
    leaks = [(_label(c), c["argv"], sorted(_kinds(c["stdout"] + c["stderr"])))
             for c in walk.bad_calls if _kinds(c["stdout"] + c["stderr"])]
    assert leaks == []


def test_no_marker_in_stdout_outside_the_named_fields(walk):
    leaks = []
    for call in walk.calls:
        _, leftover = _audit(call)
        if _kinds(leftover):
            leaks.append((_label(call), sorted(_kinds(leftover)), leftover))
    assert leaks == []


def test_named_fields_carry_only_their_own_kinds(walk):
    wrong = []
    for call in walk.calls:
        allowed = _named(call)
        for field, seen in _audit(call)[0].items():
            if seen - allowed[field]:
                wrong.append((_label(call), field, sorted(seen - allowed[field])))
    assert wrong == []


def test_every_named_field_carried_its_marker_once(walk):
    """A named field the walk never fills is either stale or untested: both fail."""
    used = set()
    for call in walk.calls:
        for field, seen in _audit(call)[0].items():
            if seen:
                used.add((call["script"], call["sub"], field))
    assert sorted(set(USER_TEXT_FIELDS) - used) == []


def test_user_text_fields_give_a_reason_each():
    assert all(kinds and reason.strip() for kinds, reason in USER_TEXT_FIELDS.values())


def test_no_marker_in_tomos_working_files_after_any_step(walk):
    """meta.json, the setup inputs and whatever else a step leaves under tomo-tmp/review/ are content-free."""
    calls = walk.calls + walk.bad_calls + walk.forced_calls
    leaks = [(_label(c), c["tmp_leaks"]) for c in calls if c["tmp_leaks"]]
    assert leaks == []


def test_a_readable_tracker_value_stays_in_read_json_and_the_document(walk):
    """The value the habits count is in read.json and the habits line; the averages must not carry it
    anywhere else of Tomo's: stderr, stdout outside the named fields, a working file."""
    assert READABLE in walk.read_files["week"] and READABLE in walk.read_files["month"]
    assert f"Energy: average {READABLE}.0 over 1 days" in walk.vault.text(WEEK_DOC), "the habits counted it"
    calls = walk.calls + walk.bad_calls + walk.forced_calls
    assert [_label(c) for c in calls if READABLE in c["stderr"]] == []
    assert [_label(c) for c in walk.calls if READABLE in _audit(c)[1]] == []
    assert [_label(c) for c in walk.bad_calls + walk.forced_calls if READABLE in c["stdout"]] == []
    assert [(_label(c), c["tmp_leaks"]) for c in calls if any("readable" in k for _, k in c["tmp_leaks"])] == []


def test_read_and_proposal_files_are_gone_after_write_and_abort_and_kept_after_a_refusal(walk):
    gone, kept = (False, False), (True, True)
    assert walk.stage_files == {
        "week-written": gone, "month-written": gone, "month-write-raised": kept, "month-refused": kept,
        "month-replaced": gone, "month-aborted": gone,
    }


def test_every_marker_reached_the_scripts(walk):
    """The fixture is live: each kind was really read, not just placed in the vault."""
    delivered = [p for p in walk.vault.writes if p.endswith(" Review.md")]
    assert any(PRP in walk.vault.text(p) for p in delivered), "the proposals reached a document"
    preview = [c for c in walk.calls if (c["script"], c["sub"]) == ("review-instructions", "preview")]
    assert any(WKL in json.dumps(_payload(c["stdout"]).get("headings", [])) for c in preview)
    forced = {(c["script"], c["sub"]): c for c in walk.forced_calls}
    assert forced[("review-read", "-")]["stderr"] == "ValueError\n", "the daily field parser saw a marker line"
    # read.json held the daily text, the journal answers and the tracker values before the write deleted it
    reads = [c for c in walk.calls if c["script"] == "review-read" and _payload(c["stdout"]).get("read_path")]
    assert reads and all(not Path(_payload(c["stdout"])["read_path"]).exists() for c in reads)
    assert _payload(reads[0]["stdout"])["report"]["days"][2]["linked"][0]["name"] == "5J-2026-03-25"
    for label in ("week", "month"):
        assert _kinds(walk.read_files[label]) >= {"daily", "answer", "tracker"}, label
        assert f"Answer {ANS} in journal" in walk.read_files[label], f"the 5-year journal note was read ({label})"
    # the tracker marker reached the habits: its two days are named unreadable in the document
    doc = walk.vault.text(WEEK_DOC)
    assert "Sleep:" in doc and "unreadable: 2026-03-24" in doc, "Sleep:: TRK on 2026-03-24"
    assert "Sport:" in doc and "unreadable: 2026-03-25" in doc, "Sport:: TRK on 2026-03-25"
