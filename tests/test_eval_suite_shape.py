"""Shape tests for the plugin-eval suite's stub kit (spec 041, part 1 — T1.2).

The kit evals/_lib/stubs.sh and the canonical leak guard evals/_lib/no-leak.md.
The conductor cases live in test_eval_conductor_cases.py; shared helpers in
eval_kit.py. Everything runs in tmp_path; nothing writes into the repo.
"""

from __future__ import annotations

import ast
import itertools
import json
import re

import pytest
from eval_kit import NO_LEAK, RELAYS, REPO, render, run_stub, stage
from jsonschema import validate

ROUTING_SCHEMA = REPO / "tomo" / "schemas" / "routing-plan.schema.json"
RENDER_HELPERS = REPO / "tomo" / "scripts" / "lib" / "render_helpers.py"

STUBS = (
    "run-id",
    "suggestion-parser",
    "instruction-render",
    "instructions-diff",
    "upload-rendered",
    "state-promoter",
)
RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-[0-9a-f]{6}$")
COMBOS = list(itertools.product(("ok", "fail"), (0, 1, 2), (0, 1)))


def no_leak_pattern() -> re.Pattern:
    m = re.search(r"^pattern: '(.*)'$", NO_LEAK.read_text(encoding="utf-8"), re.M)
    assert m, "no-leak.md has no single-quoted pattern line"
    return re.compile(m.group(1))


@pytest.mark.parametrize("audit,deletes,attach", COMBOS)
def test_stage_instance_stages_documented_files(tmp_path, audit, deletes, attach):
    stage(tmp_path, audit, deletes, attach)
    for name in STUBS:
        assert (tmp_path / "scripts" / f"{name}.py").is_file()
    for rel in (
        "tomo-tmp/routing-plan.json",
        "tomo-tmp/suggestions-doc.json",
        "tomo-tmp/inbox-cache/2026-10-24_1200_suggestions.md",
        "config/vault-config.yaml",
        "state/inbox-cost-history.jsonl",
    ):
        assert (tmp_path / rel).is_file(), rel
    for relay in RELAYS:
        assert not (tmp_path / "tomo-tmp" / relay).exists()


def test_every_stub_logs_name_and_argv(tmp_path):
    stage(tmp_path)
    for name in STUBS:
        run_stub(tmp_path, name, "--flag", "value")
    lines = (tmp_path / "tomo-tmp" / "calls.log").read_text().splitlines()
    assert lines == [f"{n}.py --flag value" for n in STUBS]


def test_audit_stub_ok(tmp_path):
    stage(tmp_path, "ok")
    r = run_stub(tmp_path, "instructions-diff")
    assert r.returncode == 0
    assert r.stdout == "RESULT: OK — 1/1 actions reconciled.\n"


def test_audit_stub_fail(tmp_path):
    stage(tmp_path, "fail")
    r = run_stub(tmp_path, "instructions-diff")
    assert r.returncode == 1
    out = r.stdout.splitlines()
    assert out[-1] == "RESULT: FAIL — count or coverage mismatch above."
    assert out[0].startswith("COVERAGE-GAP-91c2: suggestion s1 ")
    assert not re.search(r"\bact-", r.stdout)


def test_run_id_stub_format_and_out(tmp_path):
    stage(tmp_path)
    r = run_stub(tmp_path, "run-id", "--out", "rid.txt")
    assert RUN_ID_RE.match(r.stdout.strip())
    assert (tmp_path / "rid.txt").read_text().strip() == r.stdout.strip()


def test_routing_plan_validates_against_schema(tmp_path):
    stage(tmp_path)
    plan = json.loads((tmp_path / "tomo-tmp" / "routing-plan.json").read_text())
    validate(plan, json.loads(ROUTING_SCHEMA.read_text()))
    assert plan["action"] == "synthesize"
    assert len(plan["approved_suggestions"]) == 1


@pytest.mark.parametrize(
    "deletes,attach", [(1, 0), (2, 0), (0, 1), (2, 1)]
)
def test_relay_files_written_by_render_stub(tmp_path, deletes, attach):
    stage(tmp_path, "ok", deletes, attach)
    render(tmp_path)
    d = tmp_path / "tomo-tmp" / "withheld-deletes.md"
    a = tmp_path / "tomo-tmp" / "withheld-attachments.md"
    assert d.exists() == (deletes > 0)
    assert a.exists() == (attach > 0)
    if deletes:
        assert len(d.read_text().splitlines()) == deletes
        assert all("**Not deleted:**" in x for x in d.read_text().splitlines())
    if attach:
        assert a.read_text().startswith("- ⚠️ **Attachment not filed:**")


def test_render_stub_unlinks_stale_relays_when_count_is_zero(tmp_path):
    stage(tmp_path, "ok", 0, 0)
    for relay in RELAYS:
        (tmp_path / "tomo-tmp" / relay).write_text("stale\n")
    render(tmp_path)
    for relay in RELAYS:
        assert not (tmp_path / "tomo-tmp" / relay).exists()


def test_render_stub_stderr_carries_bait(tmp_path):
    stage(tmp_path)
    err = render(tmp_path).stderr
    assert RUN_ID_RE.search(re.search(r"run_id: (\S+)", err).group(1))
    assert "act-LEAK7a1" in err
    assert "validate_destinations" in err


def test_no_leak_matches_observed_leaks():
    pat = no_leak_pattern()
    # Observed in the relay probe (spec 041 SDD): the spike's run id was not hex.
    assert not pat.search("Run ID: `2026-10-24T00-00-00Z-eval01`")
    assert pat.search(
        "/private/tmp/e-uWtF9E/home/cwd/tomo-tmp/routing-plan.json"
    )


@pytest.mark.parametrize(
    "text",
    [
        "2026-10-25T00-00-00Z-c0ffee",  # synthetic: hex run id
        "/var/folders/ab/cd/T/x",  # synthetic
        "/Volumes/Moon/vault",  # synthetic
        "act-LEAK7a1",  # synthetic
    ],
)
def test_no_leak_matches_synthetic_leaks(text):
    assert no_leak_pattern().search(text)


def withdrawal_guards() -> tuple[str, ...]:
    """WITHDRAWAL_GUARDS as written in render_helpers.py, read without importing it."""
    tree = ast.parse(RENDER_HELPERS.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        if any(isinstance(t, ast.Name) and t.id == "WITHDRAWAL_GUARDS" for t in targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("render_helpers.py defines no WITHDRAWAL_GUARDS")


def test_no_leak_names_every_withdrawal_guard():
    # instruction-render.py prints these names on stderr ("dropped by <guard>"),
    # so a new or renamed guard must turn this red rather than slip past the guard.
    guards = withdrawal_guards()
    assert guards, "WITHDRAWAL_GUARDS is empty"
    pat = no_leak_pattern()
    missing = [g for g in guards if not pat.fullmatch(g)]
    assert not missing, (
        f"no-leak pattern lacks withdrawal guard(s) {missing}: add them to "
        "evals/_lib/no-leak.md and every evals/*/9-no-leak.md copy"
    )


def test_no_leak_allows_notices_suggestions_doc_and_audit_line(tmp_path):
    pat = no_leak_pattern()
    stage(tmp_path, "ok", 2, 1)
    render(tmp_path)
    for relay in RELAYS:
        for line in (tmp_path / "tomo-tmp" / relay).read_text().splitlines():
            assert not pat.search(line), line
    assert "/inbox --pass2 --force" in (
        tmp_path / "tomo-tmp" / "withheld-attachments.md"
    ).read_text()
    assert not pat.search("2026-10-24_1200_suggestions.md")
    assert not pat.search("RESULT: OK — 1/1 actions reconciled.")
    assert not pat.search("COVERAGE-GAP-91c2: suggestion s1 has no matching instruction")


@pytest.mark.parametrize(
    "kwargs,var",
    [
        ({"audit": "bogus"}, "AUDIT_RESULT"),
        ({"deletes": 3}, "WITHHELD_DELETES"),
        ({"deletes": "abc"}, "WITHHELD_DELETES"),
        ({"attach": 2}, "WITHHELD_ATTACH"),
        ({"upload": "bogus"}, "UPLOAD_RESULT"),
        ({"upload": "FAIL"}, "UPLOAD_RESULT"),
        ({"flip": "bogus"}, "FLIP_RESULT"),
        ({"flip": "1"}, "FLIP_RESULT"),
    ],
)
def test_stage_instance_refuses_invalid_parameters(tmp_path, kwargs, var):
    r = stage(tmp_path, check=False, **kwargs)
    assert r.returncode != 0
    assert var in r.stderr
    assert not (tmp_path / "scripts").exists()


def test_suggestion_parser_stub_stdout_line(tmp_path):
    stage(tmp_path)
    assert run_stub(tmp_path, "suggestion-parser").stdout == (
        '{"suggestions": [{"id": "s1", "kind": "create_atomic_note", "title": "Example"}]}\n'
    )


# The three stubs below print what the real script prints on success. Each
# expected line is built from the real script's f-string fragments, copied
# here as they appear in the source; the test first asserts every fragment is
# still in ONE print( call of that source and that the call writes to
# sys.stderr, so a change to the real format or stream turns this test red.
SCRIPTS = REPO / "tomo" / "scripts"


def print_calls(node: ast.AST) -> list[ast.Call]:
    return [
        n for n in ast.walk(node)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"
    ]


def writes_to_stderr(call: ast.Call) -> bool:
    return any(
        k.arg == "file" and ast.unparse(k.value) == "sys.stderr" for k in call.keywords
    )


def real_format(script: str, *fragments: str) -> re.Pattern:
    """Assert the f-string fragments sit in one print(..., file=sys.stderr) call
    of tomo/scripts/<script>; return a regex for the line(s) that call prints,
    with every {field} matching any text."""
    source = (SCRIPTS / script).read_text(encoding="utf-8")
    for frag in fragments:
        assert f'f"{frag}"' in source, f"{script} no longer prints {frag!r}"
    calls = [
        c for c in print_calls(ast.parse(source))
        if all(f'f"{frag}"' in ast.get_source_segment(source, c) for frag in fragments)
    ]
    assert len(calls) == 1, f"{script}: {len(calls)} print calls carry {fragments!r}"
    assert writes_to_stderr(calls[0]), f"{script} prints {fragments[0]!r} to stdout"
    template = "".join(fragments).replace("\\n", "\n")
    parts = re.split(r"\{[^}]*\}", template)
    return re.compile(".+".join(re.escape(p) for p in parts))


def render_upload(tmp_path):
    stage(tmp_path)
    render(tmp_path)
    return run_stub(
        tmp_path, "upload-rendered", "--rendered-dir", "tomo-tmp/rendered",
        "--inbox", "100 Inbox/",
    )


def test_render_stub_prints_real_summary_on_stderr(tmp_path):
    stage(tmp_path)
    r = render(tmp_path)
    assert r.returncode == 0
    assert r.stdout == ""
    # instruction-render.py:1232-1241 — two print calls: a summary, three paths
    summary = real_format(
        "instruction-render.py",
        "instruction-render: rendered={len(manifest)} actions={len(actions)} ",
        "errors={errors} out={out_dir}",
    )
    paths = real_format(
        "instruction-render.py",
        "  manifest={manifest_path}\\n",
        "  instructions.json={instructions_json_path}\\n",
        "  instructions.md={instructions_md_path}",
    )
    tail = r.stderr.splitlines()[-4:]
    assert summary.fullmatch(tail[0])
    assert paths.fullmatch("\n".join(tail[1:]))
    assert tail == [
        "instruction-render: rendered=1 actions=1 errors=0 out=tomo-tmp/rendered",
        "  manifest=tomo-tmp/rendered/manifest.json",
        "  instructions.json=tomo-tmp/rendered/instructions.json",
        "  instructions.md=tomo-tmp/rendered/instructions.md",
    ]
    for line in tail[1:]:
        assert (tmp_path / line.split("=", 1)[1]).is_file(), line


def test_upload_stub_prints_real_success_lines_on_stderr(tmp_path):
    r = render_upload(tmp_path)
    assert r.returncode == 0
    assert r.stdout == ""
    # upload-rendered.py:207,215,224 (per-file lines), :241-249 (summary)
    note = real_format("upload-rendered.py", "  [note] {target} ({len(body)} chars)")
    md = real_format("upload-rendered.py", "  [note] {md_target} ({len(md_body)} chars)")
    js = real_format("upload-rendered.py", "  [file] {json_target} ({len(json_bytes)} bytes)")
    summary = real_format(
        "upload-rendered.py",
        "upload-rendered: {notes_written} note(s) + 2 instruction artefact(s) ",
        "written under {args.inbox}",
    )
    arrow = real_format("upload-rendered.py", "  ↳ {timestamp}_instructions.md / .json")
    lines = r.stderr.splitlines()
    for pattern, line in zip((note, md, js, summary, arrow), lines, strict=True):
        assert pattern.fullmatch(line), line
    rendered = tmp_path / "tomo-tmp" / "rendered"
    assert lines == [
        f"  [note] 100 Inbox/2026-10-24_0000_example.md "
        f"({len((rendered / '2026-10-24_0000_example.md').read_text())} chars)",
        f"  [note] 100 Inbox/2026-10-24_0000_instructions.md "
        f"({len((rendered / 'instructions.md').read_text())} chars)",
        f"  [file] 100 Inbox/2026-10-24_0000_instructions.json "
        f"({len((rendered / 'instructions.json').read_bytes())} bytes)",
        "upload-rendered: 1 note(s) + 2 instruction artefact(s) written under 100 Inbox/",
        "  ↳ 2026-10-24_0000_instructions.md / .json",
    ]


def test_upload_stub_without_render_fails_like_the_real_script(tmp_path):
    stage(tmp_path)
    r = run_stub(tmp_path, "upload-rendered", "--rendered-dir", "tomo-tmp/rendered")
    assert r.returncode == 2
    # upload-rendered.py:153
    fmt = real_format("upload-rendered.py", "error: required file missing: {required}")
    assert fmt.fullmatch(r.stderr.rstrip("\n"))


def test_state_promoter_stub_flip_is_silent_like_the_real_script(tmp_path):
    stage(tmp_path)
    # state-promoter.py flip_state :87-129, _handle_concurrency_retry, _cli_flip
    # :181-211 — success returns 0 and prints nothing: the only prints on the
    # flip path are these error/rejection lines, all on stderr. A new print
    # (a success line) changes the pinned set.
    source = (SCRIPTS / "state-promoter.py").read_text(encoding="utf-8")
    funcs = {
        f.name: f for f in ast.parse(source).body if isinstance(f, ast.FunctionDef)
    }

    def leads(name):
        out = []
        for call in print_calls(funcs[name]):
            assert writes_to_stderr(call), f"{name} prints to stdout"
            arg = call.args[0]
            out.append(arg.value if isinstance(arg, ast.Constant) else arg.values[0].value)
        return sorted(out)

    assert leads("flip_state") == [
        "state-promoter.flip_state: lifecycle.transition_rejected doc_type=",
    ]
    assert leads("_handle_concurrency_retry") == []
    assert leads("_cli_flip") == [
        "Usage: state-promoter.py flip <path> <doc_type> <from_state> <to_state> "
        "<run_id> [expected_modified]",
        "state-promoter: expected_modified must be an integer, got ",
        "state-promoter: persistent concurrency conflict on ",
    ]
    assert "return 0 if success else 1" in ast.get_source_segment(source, funcs["_cli_flip"])
    r = run_stub(
        tmp_path, "state-promoter", "flip", "100 Inbox/2026-10-24_1200_suggestions.md",
        "suggestions", "approved", "applied", "rid", "1792800000000",
    )
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


# ── Failure switches (#205): UPLOAD_RESULT=fail, FLIP_RESULT=fail ────────────
# Each failing stub prints what the real script prints on that failure, on the
# real stream, with the real exit code. The fragments below are copied from
# the real source; each test first asserts they are still there.

KADO_CLIENT = SCRIPTS / "lib" / "kado_client.py"
NOTE = "2026-10-24_0000_example.md"


def appended_failure(script: str, fragment: str) -> re.Pattern:
    """Assert `fragment` is the f-string of a failures.append( call in the
    script; return a regex for the text it appends."""
    source = (SCRIPTS / script).read_text(encoding="utf-8")
    calls = [
        n for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "failures.append"
        and ast.get_source_segment(source, n.args[0]) == f'f"{fragment}"'
    ]
    assert len(calls) == 1, f"{script}: {len(calls)} failures.append calls carry {fragment!r}"
    parts = re.split(r"\{[^}]*\}", fragment)
    return re.compile(".+".join(re.escape(p) for p in parts))


def kado_http_error() -> str:
    """The KadoError text of a 503 that outlived its retries
    (kado_client.py:33-34 retry constants, :699-700 the message)."""
    source = KADO_CLIENT.read_text(encoding="utf-8")
    assert "_RETRY_STATUSES = {429, 503}" in source
    assert "_MAX_RETRIES = 4" in source
    assert 'suffix = f" (after {_MAX_RETRIES} retries)" if exc.code in _RETRY_STATUSES else ""' in source
    assert 'raise KadoError(f"HTTP {exc.code} from Kado: {exc.reason}{suffix}")' in source
    return "HTTP 503 from Kado: Service Unavailable (after 4 retries)"


def upload_with(tmp_path, upload):
    stage(tmp_path, upload=upload)
    render(tmp_path)
    return run_stub(
        tmp_path, "upload-rendered", "--rendered-dir", "tomo-tmp/rendered",
        "--inbox", "100 Inbox/",
    )


def test_upload_stub_fail_prints_real_partial_failure_on_stderr(tmp_path):
    r = upload_with(tmp_path, "fail")
    assert r.returncode == 1  # upload-rendered.py :239 `return 1` after failures
    assert r.stdout == ""
    # upload-rendered.py :216 (md), :225 (json) per-file lines; :204-206 the
    # note write's failure; :229-239 the failure block
    md = real_format("upload-rendered.py", "  [note] {md_target} ({len(md_body)} chars)")
    js = real_format("upload-rendered.py", "  [file] {json_target} ({len(json_bytes)} bytes)")
    count = real_format("upload-rendered.py", "upload-rendered: {len(failures)} failure(s):")
    item = real_format("upload-rendered.py", "  - {f}")
    failure = appended_failure("upload-rendered.py", "kado-write note {target}: {exc}")
    summary = real_format(
        "upload-rendered.py",
        "upload-rendered: {notes_written} note(s) + ",
        "{2 - sum(1 for f in failures if 'instructions.' in f)} instruction artefact(s) written",
    )
    source = (SCRIPTS / "upload-rendered.py").read_text(encoding="utf-8")
    assert 'print("", file=sys.stderr)' in source
    lines = r.stderr.splitlines()
    assert len(lines) == 6, lines
    assert md.fullmatch(lines[0]) and js.fullmatch(lines[1])
    assert lines[2] == ""
    assert count.fullmatch(lines[3])
    assert item.fullmatch(lines[4]) and failure.fullmatch(lines[4][4:])
    assert summary.fullmatch(lines[5])
    rendered = tmp_path / "tomo-tmp" / "rendered"
    assert lines == [
        f"  [note] 100 Inbox/2026-10-24_0000_instructions.md "
        f"({len((rendered / 'instructions.md').read_text())} chars)",
        f"  [file] 100 Inbox/2026-10-24_0000_instructions.json "
        f"({len((rendered / 'instructions.json').read_bytes())} bytes)",
        "",
        "upload-rendered: 1 failure(s):",
        f"  - kado-write note 100 Inbox/{NOTE}: {kado_http_error()}",
        "upload-rendered: 0 note(s) + 2 instruction artefact(s) written",
    ]


def test_upload_stub_fail_without_render_still_fails_on_bad_input(tmp_path):
    stage(tmp_path, upload="fail")
    r = run_stub(tmp_path, "upload-rendered", "--rendered-dir", "tomo-tmp/rendered")
    assert r.returncode == 2


def test_state_promoter_stub_fail_prints_real_rejection_on_stderr(tmp_path):
    stage(tmp_path, flip="fail")
    r = run_stub(
        tmp_path, "state-promoter", "flip", "100 Inbox/2026-10-24_1200_suggestions.md",
        "suggestions", "pending-approval", "approved", "rid", "1792800000000",
    )
    # state-promoter.py flip_state :108-114 (rejection print, return False),
    # _cli_flip :211 `return 0 if success else 1`
    rejected = real_format(
        "state-promoter.py",
        "state-promoter.flip_state: lifecycle.transition_rejected ",
        "doc_type={doc_type!r} {from_state!r}→{to_state!r}",
    )
    assert r.returncode == 1
    assert r.stdout == ""
    assert rejected.fullmatch(r.stderr.rstrip("\n"))
    assert r.stderr == (
        "state-promoter.flip_state: lifecycle.transition_rejected "
        "doc_type='suggestions' 'pending-approval'→'approved'\n"
    )


@pytest.mark.parametrize("upload,flip", [(None, None), ("ok", "ok"), ("ok", None), (None, "ok")])
def test_unset_switches_default_to_ok(tmp_path, upload, flip):
    stage(tmp_path / "ref")
    stage(tmp_path / "ws", upload=upload, flip=flip)
    for name in STUBS:
        ref = (tmp_path / "ref" / "scripts" / f"{name}.py").read_bytes()
        assert (tmp_path / "ws" / "scripts" / f"{name}.py").read_bytes() == ref, name
    r = upload_with(tmp_path / "ok", "ok")
    assert r.returncode == 0
    assert r.stderr.splitlines()[-2].startswith("upload-rendered: 1 note(s) + 2 ")


@pytest.mark.parametrize("upload,flip", [("fail", "ok"), ("ok", "fail"), ("fail", "fail")])
def test_failure_switches_touch_only_their_stub(tmp_path, upload, flip):
    stage(tmp_path / "ref")
    stage(tmp_path / "ws", upload=upload, flip=flip)
    changed = {
        name for name in STUBS
        if (tmp_path / "ws" / "scripts" / f"{name}.py").read_bytes()
        != (tmp_path / "ref" / "scripts" / f"{name}.py").read_bytes()
    }
    assert changed == {
        n for n, v in (("upload-rendered", upload), ("state-promoter", flip)) if v == "fail"
    }
