"""Shape tests for the plugin-eval suite's stub kit (spec 041, part 1 — T1.2).

The kit evals/_lib/stubs.sh and the canonical leak guard evals/_lib/no-leak.md.
The conductor cases live in test_eval_conductor_cases.py; shared helpers in
eval_kit.py. Everything runs in tmp_path; nothing writes into the repo.
"""

from __future__ import annotations

import itertools
import json
import re

import pytest
from eval_kit import NO_LEAK, RELAYS, REPO, render, run_stub, stage
from jsonschema import validate

ROUTING_SCHEMA = REPO / "tomo" / "schemas" / "routing-plan.schema.json"

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
        "validate_destinations",
        "suppress_moves_for_unfiled_attachments",
        "filter_unresolvable_moc_links",
        "filter_missing_daily_notes",
        "filter_unappliable_relationships",
        "act-LEAK7a1",  # synthetic
    ],
)
def test_no_leak_matches_synthetic_leaks(text):
    assert no_leak_pattern().search(text)


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
# still in that source, so a change to the real format turns this test red.
SCRIPTS = REPO / "tomo" / "scripts"


def real_format(script: str, *fragments: str) -> re.Pattern:
    """Assert each f-string fragment is in tomo/scripts/<script>; return a
    regex for the line(s) they print, with every {field} matching any text."""
    source = (SCRIPTS / script).read_text(encoding="utf-8")
    for frag in fragments:
        assert f'f"{frag}"' in source, f"{script} no longer prints {frag!r}"
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
    # state-promoter.py:_cli_flip — success returns 0 and prints nothing.
    source = (SCRIPTS / "state-promoter.py").read_text(encoding="utf-8")
    flip = source.split("def _cli_flip", 1)[1].split("\ndef ", 1)[0]
    assert "return 0 if success else 1" in flip
    r = run_stub(
        tmp_path, "state-promoter", "flip", "100 Inbox/2026-10-24_1200_suggestions.md",
        "suggestions", "approved", "applied", "rid", "1792800000000",
    )
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
