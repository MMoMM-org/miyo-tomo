"""Runtime contract between the eval stubs and the real scripts (#228).

The eval cases grade the conductors against stubs. These tests run each stub and
the script it stands in for on the same input and compare what a conductor can
see: exit code, stdout, stderr and the files written. Where the static fragment
checks in test_pass1_stub_kit.py and test_eval_suite_shape.py pin a printed string,
these pin behaviour, so a script that changes while its strings stay fails here.

Real scripts run in a subprocess with cwd = a workspace under tmp_path. Kado is
never reached: FAKE_KADO_LAUNCHER replaces KadoClient with an in-memory fake, or,
for the failure path, keeps the real client and fails urlopen with HTTP 503, so
the failure text is the client's own. No paid run, nothing under ~/.tomo.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import eval_kit
from eval_kit import REPO, run_stub
from test_pass1_stub_kit import RENDER_ARGV, REDUCER_ARGV, RUN_ID, PATHS
from test_pass1_stub_kit import stage as stage_pass1

SCRIPTS = REPO / "tomo" / "scripts"
TIMESTAMP_RE = re.compile(r"^\s*updated_at: '.*'$", re.M)
RUN_ID_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-[0-9a-f]{6}")

# Runs one real script with Kado replaced. argv[1] = fake mode, argv[2] = script.
FAKE_KADO_LAUNCHER = r"""
import io, json, os, runpy, sys, time, urllib.error, urllib.request
mode, script = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.dirname(script))
import lib.kado_client as kc

MODIFIED = 1790000000000

class FakeKado:
    def read_note(self, path):
        raise kc.KadoNotFoundError(path)
    read_file = read_note
    def read_frontmatter(self, path):
        return {"content": {}, "modified": MODIFIED}
    def write_note(self, path, content, expected_modified=None):
        return {"path": path, "modified": MODIFIED}
    def write_file(self, path, data, expected_modified=None):
        return {"path": path, "modified": MODIFIED}
    def write_frontmatter(self, path, frontmatter, mode="merge", expected_modified=None):
        return {"path": path, "modified": MODIFIED}

time.sleep = lambda _s: None
if mode == "ok":
    kc.KadoClient = FakeKado
else:
    os.environ.update(KADO_URL="http://127.0.0.1:9/mcp", KADO_API_KEY="contract-test")
    os.environ.update(KADO_TOKEN="contract-test")
    def refuse(req, *a, **k):
        raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, io.BytesIO(b""))
    urllib.request.urlopen = refuse
sys.argv = sys.argv[2:]
runpy.run_path(script, run_name="__main__")
"""


def run_real(ws: Path, script: str, *argv: str, fake: str = "ok") -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("KADO_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", FAKE_KADO_LAUNCHER, fake, str(SCRIPTS / script), *argv],
        cwd=ws, capture_output=True, text=True, env=env, timeout=60, check=False,
    )


def stub(ws: Path, script: str, *argv: str) -> subprocess.CompletedProcess:
    return run_stub(ws, script.removesuffix(".py"), *argv)


def assert_same_output(stubbed, real):
    assert (stubbed.returncode, stubbed.stdout, stubbed.stderr) == (
        real.returncode, real.stdout, real.stderr,
    )


def triaged(tmp_path: Path) -> Path:
    ws, _ = stage_pass1(tmp_path)
    assert stub(ws, "inbox-triage.py", "--pass1").returncode == 0
    return ws


def analysed(tmp_path: Path) -> Path:
    ws = triaged(tmp_path)
    for path in PATHS:
        assert stub(ws, "analyst-stub.py", path, path, RUN_ID).returncode == 0
    return ws


# ---- Pass 1: scripts that need no Kado ---------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ("--field", "inbox_path"),
        ("--field", "has_audio"),
        ("--field", "fresh_sources"),
        ("--field", "no_such_field"),
        ("--batch-count", "--size", "2"),
        ("--sources", "--batch", "1", "--size", "2"),
        ("--sources", "--batch", "2", "--size", "2"),
        ("--sources", "--batch", "9", "--size", "2"),
    ],
)
def test_read_routing_plan_matches(tmp_path, argv):
    ws = triaged(tmp_path)
    assert_same_output(stub(ws, "read-routing-plan.py", *argv), run_real(ws, "read-routing-plan.py", *argv))


@pytest.mark.parametrize(
    "argv",
    [
        ("--field", "profile"),
        ("--field", "tomo.suggestions.parallel"),
        ("--field", "no.such.field"),
        ("--field", "no.such.field", "--default", "7"),
    ],
)
def test_read_config_field_matches(tmp_path, argv):
    ws = triaged(tmp_path)
    assert_same_output(stub(ws, "read-config-field.py", *argv), run_real(ws, "read-config-field.py", *argv))


def test_run_id_writes_what_it_prints_in_the_real_format(tmp_path):
    ws = triaged(tmp_path)
    for run, name in ((stub, "stub"), (run_real, "real")):
        out = ws / "tomo-tmp" / f".run_id_{name}"
        r = run(ws, "run-id.py", "--out", str(out))
        assert r.returncode == 0 and r.stderr == ""
        assert RUN_ID_RE.fullmatch(r.stdout.strip()), r.stdout
        assert out.read_text(encoding="utf-8") == r.stdout


def test_state_line_of_the_analyst_stand_in_matches_state_update(tmp_path):
    ws = triaged(tmp_path)
    path, key = PATHS[1], PATHS[1]
    stubbed = stub(ws, "analyst-stub.py", path, key, RUN_ID)
    state = ws / "tomo-tmp" / "inbox-state.jsonl"
    stub_entry = json.loads(state.read_text(encoding="utf-8").splitlines()[-1])
    real_state = ws / "tomo-tmp" / "real-state.jsonl"
    real = run_real(
        ws, "state-update.py", "--state", str(real_state), "--item-key", key,
        "--stem", "Dresden", "--path", path, "--status", "done", "--run-id", RUN_ID,
        "--attempts", "1",
    )
    assert real.returncode == 0, real.stderr
    assert stubbed.stderr == real.stderr
    real_entry = json.loads(real_state.read_text(encoding="utf-8"))
    assert list(stub_entry) == list(real_entry)
    for field in ("run_id", "stem", "item_key", "path", "status", "attempts", "error"):
        assert stub_entry[field] == real_entry[field], field


@pytest.mark.parametrize("duplicates", ["0", "1"])
def test_suggestions_render_matches_on_the_reducer_stub_document(tmp_path, duplicates):
    ws, _ = stage_pass1(tmp_path, dups=duplicates)
    assert stub(ws, "inbox-triage.py", "--pass1").returncode == 0
    for path in PATHS:
        stub(ws, "analyst-stub.py", path, path, RUN_ID)
    assert stub(ws, "suggestions-reducer.py", *REDUCER_ARGV).returncode == 0

    def outputs(run, name):
        argv = list(RENDER_ARGV)
        argv[3], argv[5] = f"tomo-tmp/{name}.md", f"tomo-tmp/{name}.json"
        return run(ws, "suggestions-render.py", *argv), (ws / argv[3]), (ws / argv[5])

    s_run, s_md, s_json = outputs(stub, "same")
    s_md_text, s_json_text = s_md.read_text(encoding="utf-8"), s_json.read_text(encoding="utf-8")
    r_run, r_md, r_json = outputs(run_real, "same")
    assert_same_output(s_run, r_run)
    assert TIMESTAMP_RE.sub("", s_md_text) == TIMESTAMP_RE.sub("", r_md.read_text(encoding="utf-8"))
    assert json.loads(s_json_text) == json.loads(r_json.read_text(encoding="utf-8"))


# ---- Pass 1: scripts behind Kado ---------------------------------------------------


@pytest.mark.parametrize(
    "local,vault",
    [
        ("tomo-tmp/body.md", "100 Inbox/x_suggestions.md"),
        ("tomo-tmp/body.md", "100 Inbox/x_suggestions.json"),
        ("tomo-tmp/empty.md", "100 Inbox/x.md"),
        ("tomo-tmp/absent.md", "100 Inbox/x.md"),
    ],
)
def test_kado_write_file_matches(tmp_path, local, vault):
    ws = triaged(tmp_path)
    (ws / "tomo-tmp" / "body.md").write_text("# Body\n", encoding="utf-8")
    (ws / "tomo-tmp" / "empty.md").write_text("", encoding="utf-8")
    argv = ("--local", local, "--vault", vault)
    assert_same_output(stub(ws, "kado-write-file.py", *argv), run_real(ws, "kado-write-file.py", *argv))


def test_mark_captured_matches_after_a_full_run(tmp_path):
    ws = analysed(tmp_path)
    argv = ("--state", "tomo-tmp/inbox-state.jsonl", "--run-id", RUN_ID)
    stubbed, real = stub(ws, "mark-captured.py", *argv), run_real(ws, "mark-captured.py", *argv)
    # The real script walks items sorted by key, the stub in state order.
    assert stubbed.returncode == real.returncode == 0, real.stderr
    assert sorted(stubbed.stderr.splitlines()) == sorted(real.stderr.splitlines())


def test_mark_captured_matches_when_nothing_is_done(tmp_path):
    ws = triaged(tmp_path)
    state = ws / "tomo-tmp" / "inbox-state.jsonl"
    state.write_text(
        json.dumps({"run_id": "other", "stem": "A", "item_key": "A.md", "path": "A.md",
                    "status": "done"}) + "\n",
        encoding="utf-8",
    )
    argv = ("--state", str(state), "--run-id", RUN_ID)
    assert_same_output(stub(ws, "mark-captured.py", *argv), run_real(ws, "mark-captured.py", *argv))


# ---- Pass 2 ------------------------------------------------------------------------


def rendered_pass2(tmp_path: Path, upload=None, flip=None) -> Path:
    eval_kit.stage(tmp_path, upload=upload, flip=flip)
    assert eval_kit.render(tmp_path).returncode == 0
    return tmp_path


UPLOAD_ARGV = ("--rendered-dir", "tomo-tmp/rendered", "--inbox", "100 Inbox/", "--upload-delay", "0")


def test_upload_matches_on_success(tmp_path):
    ws = rendered_pass2(tmp_path)
    assert_same_output(stub(ws, "upload-rendered.py", *UPLOAD_ARGV), run_real(ws, "upload-rendered.py", *UPLOAD_ARGV))


def test_upload_matches_when_a_required_file_is_missing(tmp_path):
    ws = rendered_pass2(tmp_path)
    (ws / "tomo-tmp" / "rendered" / "instructions.md").unlink()
    assert_same_output(stub(ws, "upload-rendered.py", *UPLOAD_ARGV), run_real(ws, "upload-rendered.py", *UPLOAD_ARGV))


def test_upload_failure_keeps_the_real_shape_with_the_real_client_error(tmp_path):
    ws = rendered_pass2(tmp_path, upload="fail")
    stubbed = stub(ws, "upload-rendered.py", *UPLOAD_ARGV)
    real = run_real(ws, "upload-rendered.py", *UPLOAD_ARGV, fake="503")
    assert stubbed.returncode == real.returncode == 1
    assert stubbed.stdout == real.stdout == ""
    # Kado is down for every write in the real run; the stub's run lands the two
    # instruction artefacts. The note failure line and the frame must still agree.
    stub_note = [ln for ln in stubbed.stderr.splitlines() if ln.startswith("  - kado-write note")]
    assert len(stub_note) == 1
    assert stub_note[0] in real.stderr.splitlines()


def test_state_flip_is_silent_on_success_like_the_real_script(tmp_path):
    ws = rendered_pass2(tmp_path)
    argv = ("flip", "100 Inbox/x_suggestions.md", "suggestions", "pending-approval", "approved", RUN_ID, "1792800000000")
    assert_same_output(stub(ws, "state-promoter.py", *argv), run_real(ws, "state-promoter.py", *argv))


def test_state_flip_rejection_matches(tmp_path):
    ws = rendered_pass2(tmp_path, flip="fail")
    argv = ("flip", "100 Inbox/x_suggestions.md", "suggestions", "approved", "pending-approval", RUN_ID)
    assert_same_output(stub(ws, "state-promoter.py", *argv), run_real(ws, "state-promoter.py", *argv))


# ---- Scripts whose fixtures differ from the stub's: compare the shape -----------------


def shape(line: str) -> str:
    """A status line reduced to its key sequence, values dropped."""
    return " ".join(re.findall(r"\b(\w+)=", line))


def only_line(text: str, prefix: str) -> str:
    (line,) = [ln for ln in text.splitlines() if ln.startswith(prefix)]
    return line


def test_shared_ctx_keeps_its_warn_summary_and_context_keys(tmp_path):
    ws, _ = stage_pass1(tmp_path, warn="1")
    fields = [
        {"name": n, "type": "text", "syntax": "inline_field", "description": n}
        for n in ("mood", "sleep")
    ]
    cfg = {
        "profile": "miyo",
        "tags": {"prefixes": {}},
        "concepts": {
            "map_note": {"paths": ["Atlas/Maps/"]},
            "calendar": {"granularities": {"daily": {"enabled": True, "path": "Calendar/"}}},
        },
        "trackers": {
            "enabled": True,
            "daily_note_trackers": {"section": "Habit", "today_fields": fields},
        },
    }
    (ws / "real-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (ws / "real-cache.yaml").write_text(
        yaml.safe_dump({"map_notes": [
            {"path": "Atlas/Maps/Places MOC.md", "title": "Places MOC", "topics": ["places"]},
            {"path": "Atlas/Maps/Travel MOC.md", "title": "Travel MOC", "topics": ["travel"]},
        ]}),
        encoding="utf-8",
    )
    argv = ("--run-id", RUN_ID)
    stubbed = stub(
        ws, "shared-ctx-builder.py", *argv, "--cache", "config/discovery-cache.yaml",
        "--vault-config", "config/vault-config.yaml",
        "--profiles-dir", "profiles", "--output", "tomo-tmp/stub-ctx.json",
        "--warnings-out", "tomo-tmp/stub-w.txt",
    )
    real = run_real(
        ws, "shared-ctx-builder.py", *argv, "--cache", "real-cache.yaml",
        "--vault-config", "real-config.yaml",
        "--profiles-dir", str(REPO / "tomo" / "profiles"), "--output", "tomo-tmp/real-ctx.json",
        "--warnings-out", "tomo-tmp/real-w.txt", "--skip-reconcile",
    )
    assert stubbed.returncode == real.returncode == 0, real.stderr
    assert only_line(stubbed.stderr, "WARN:") == only_line(real.stderr, "WARN:")
    assert (ws / "tomo-tmp/stub-w.txt").read_text() == (ws / "tomo-tmp/real-w.txt").read_text()
    assert shape(only_line(stubbed.stderr, "mocs_total=")) == shape(only_line(real.stderr, "mocs_total="))
    stub_ctx = json.loads((ws / "tomo-tmp/stub-ctx.json").read_text(encoding="utf-8"))
    real_ctx = json.loads((ws / "tomo-tmp/real-ctx.json").read_text(encoding="utf-8"))
    assert set(stub_ctx) <= set(real_ctx)
    assert stub_ctx["schema_version"] == real_ctx["schema_version"]
    assert set(stub_ctx["mocs"][0]) <= set(real_ctx["mocs"][0])


def _real_item_result(path: str) -> dict:
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    action = {
        "kind": "create_atomic_note", "title": stem, "template": "Atomic Note.md", "atomic_note_worthiness": 0.9,
        "location": "Atlas/Notes/", "tags": ["topic/travel"],
        "candidate_mocs": [{"path": "Atlas/Maps/Travel MOC.md", "score": 0.9, "pre_check": True}],
        "summary": "A note.", "needs_new_moc": False, "proposed_moc_topic": None,
        "classification": {"category": "2600 - Applied Sciences", "confidence": 0.5},
        "tags_to_add": [],
    }
    return {
        "schema_version": "1", "stem": stem, "path": path, "item_key": path,
        "type": "fleeting_note", "type_confidence": 0.5, "force_atomic": False,
        "actions": [action], "candidate_mocs": action["candidate_mocs"],
        "classification": action["classification"], "needs_new_moc": False,
        "proposed_moc_topic": None, "tags_to_add": [], "atomic_note_worthiness": 0.9,
        "alternatives": [], "issues": [], "duration_ms": 0,
    }


def test_reducer_keeps_its_summary_and_document_keys(tmp_path):
    ws = analysed(tmp_path)
    assert stub(ws, "suggestions-reducer.py", *REDUCER_ARGV).returncode == 0
    stub_doc = json.loads((ws / "tomo-tmp/suggestions-doc.json").read_text(encoding="utf-8"))
    stub_summary = stub(ws, "suggestions-reducer.py", *REDUCER_ARGV).stderr

    real_items = ws / "real-items"
    real_items.mkdir()
    sys.path.insert(0, str(SCRIPTS))
    from lib.item_key import to_filename

    for path in PATHS:
        (real_items / to_filename(path)).write_text(json.dumps(_real_item_result(path)), encoding="utf-8")
    (ws / "real-ctx.json").write_text(
        json.dumps({
            "schema_version": "1", "run_id": RUN_ID, "mocs": [], "tag_prefixes": [],
            "classification_keywords": {},
        }),
        encoding="utf-8",
    )
    real = run_real(
        ws, "suggestions-reducer.py", "--state", "tomo-tmp/inbox-state.jsonl",
        "--items-dir", str(real_items), "--run-id", RUN_ID, "--profile", "miyo",
        "--shared-ctx", "real-ctx.json", "--no-kado", "--output", "real-doc.json",
    )
    assert real.returncode == 0, real.stderr
    assert shape(only_line(stub_summary, "suggestions-reducer:")) == shape(
        only_line(real.stderr, "suggestions-reducer:")
    )
    real_doc = json.loads((ws / "real-doc.json").read_text(encoding="utf-8"))
    assert real_doc["sections"], real.stderr
    assert set(stub_doc) <= set(real_doc)
    assert set(stub_doc["sections"][0]) <= set(real_doc["sections"][0])
    stub_action, real_action = stub_doc["sections"][0]["actions"][0], real_doc["sections"][0]["actions"][0]
    assert stub_action["kind"] == real_action["kind"]
    assert set(stub_action) <= set(real_action)


def test_triage_keeps_its_summary_and_plan_keys(tmp_path, capsys):
    from test_inbox_triage import FakeKadoClient, INBOX_PATH, _listdir_item, _load_module

    client = FakeKadoClient(
        listdir_items=[_listdir_item(INBOX_PATH + "note.md")],
        frontmatter_responses={
            "tomo.state=pending-approval": [], "tomo.state=pending-accept": [],
            "tomo.state=captured": [], "tomo.doc_type=instructions": [],
        },
    )
    rc = _load_module().main(
        ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path / "out"),
         "--cost-history", str(tmp_path / "cost.jsonl")],
        client_factory=lambda: client,
    )
    assert rc == 0
    real_err = capsys.readouterr().err
    real_plan = json.loads((tmp_path / "out" / "routing-plan.json").read_text(encoding="utf-8"))

    ws = triaged(tmp_path / "stub")
    stubbed = stub(ws, "inbox-triage.py", "--pass1")
    assert shape(only_line(stubbed.stderr, "[inbox-triage] suggest")) == shape(
        only_line(real_err, "[inbox-triage] suggest")
    )
    stub_plan = json.loads((ws / "tomo-tmp/routing-plan.json").read_text(encoding="utf-8"))
    assert stub_plan["action"] == real_plan["action"] == "suggest"
    assert set(stub_plan) <= set(real_plan)
    assert set(stub_plan["fresh_sources"][0]) <= set(real_plan["fresh_sources"][0])


def _withheld_lines(tmp_path: Path) -> tuple[list[str], list[str]]:
    eval_kit.stage(tmp_path, deletes=2, attach=1)
    eval_kit.render(tmp_path)
    return tuple(
        (tmp_path / "tomo-tmp" / name).read_text(encoding="utf-8").splitlines()
        for name in eval_kit.RELAYS
    )


def test_relay_notices_are_what_the_real_renderers_print(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    from lib.render_md import _render_skipped_asset_notice, _render_withdrawn_delete_notice

    deletes, attachments = _withheld_lines(tmp_path)
    assert deletes == [
        _render_withdrawn_delete_notice({
            "source_path": f"100 Inbox/{stem}.md", "causes": [{"guard": guard}],
        })
        for stem, guard in (
            ("Meeting Notes Q3", "validate_destinations"),
            ("Reading List", "filter_unappliable_relationships"),
        )
    ]
    destination = "Attachments/whiteboard.png"
    assert attachments == [
        _render_skipped_asset_notice({
            "source": "100 Inbox/whiteboard.png",
            "kind": "vault_collision_held",
            "destination": destination,
            "reason": (
                "kept in inbox: the owner chose not to file it over "
                f"the occupied destination `{destination}`"
            ),
        })
    ]


AUDIT_ACTION = {
    "id": "I-1", "action": "update_log_entry",
    "daily_note_path": "Calendar/2026-03-26.md", "date": "2026-03-26",
    "section": "Daily Log", "position": "after_last_line", "content": "x",
}
AUDIT_PARSED = {
    "confirmed_items": [], "skipped": [],
    "daily_updates": [{
        "date": "2026-03-26", "daily_note_path": "Calendar/2026-03-26.md",
        "trackers": [], "log_links": [],
        "log_entries": [{"content": "entry", "position": "after_last_line",
                         "source_stem": "", "accepted": True}],
    }],
}


@pytest.mark.parametrize("audit,actions", [("ok", [AUDIT_ACTION]), ("fail", [])])
def test_audit_verdict_line_and_exit_code_match(tmp_path, audit, actions):
    eval_kit.stage(tmp_path, audit=audit)
    parsed, instructions = tmp_path / "parsed.json", tmp_path / "instr.json"
    parsed.write_text(json.dumps(AUDIT_PARSED), encoding="utf-8")
    instructions.write_text(
        json.dumps({"action_count": len(actions), "actions": actions}), encoding="utf-8"
    )
    stubbed = stub(tmp_path, "instructions-diff.py")
    real = run_real(
        tmp_path, "instructions-diff.py", "--suggestions", str(parsed),
        "--instructions", str(instructions),
    )
    assert stubbed.returncode == real.returncode, real.stdout + real.stderr
    verdicts = [
        re.sub(r"\d+/\d+", "#/#", only_line(r.stdout, "RESULT:")) for r in (stubbed, real)
    ]
    assert verdicts[0] == verdicts[1]


def test_instruction_render_keeps_its_files_summary_and_stream(tmp_path):
    ws = tmp_path / "ws"
    eval_kit.stage(ws)
    assert eval_kit.render(ws).returncode == 0
    stub_files = {p.name for p in (ws / "tomo-tmp" / "rendered").iterdir()}
    stub_err = eval_kit.render(ws).stderr

    (ws / "parsed.json").write_text(
        json.dumps({"confirmed_items": [], "skipped": [{"stem": "x", "reason": "kept"}], "daily_updates": [],
                    "generated": "2026-10-24T00:00:00Z"}),
        encoding="utf-8",
    )
    real = run_real(
        ws, "instruction-render.py", "--suggestions", "parsed.json",
        "--output-dir", "real-out", "--run-id", "x",
    )
    assert real.returncode == 0, real.stderr
    assert real.stdout == ""
    assert shape(only_line(stub_err, "instruction-render:")) == shape(
        only_line(real.stderr, "instruction-render:")
    )
    for name in ("manifest", "instructions.json", "instructions.md"):
        assert shape(only_line(stub_err, f"  {name}=")) == shape(only_line(real.stderr, f"  {name}="))
    real_files = {p.name for p in (ws / "real-out").iterdir()}
    assert {"manifest.json", "instructions.json", "instructions.md"} <= real_files
    assert {"manifest.json", "instructions.json", "instructions.md"} <= stub_files
