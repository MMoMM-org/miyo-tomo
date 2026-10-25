"""Shape tests for the plugin-eval suite under evals/ (spec 041).

Part 1 (T1.2): the stub kit evals/_lib/stubs.sh and the canonical leak guard
evals/_lib/no-leak.md. Part 2 (cases) is appended below by later tasks.
Everything runs in tmp_path; nothing writes into the repo.
"""

from __future__ import annotations

import itertools
import json
import re
import subprocess
from pathlib import Path

import pytest
from jsonschema import validate

REPO = Path(__file__).resolve().parent.parent
KIT = REPO / "evals" / "_lib" / "stubs.sh"
NO_LEAK = REPO / "evals" / "_lib" / "no-leak.md"
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


RELAYS = ("withheld-deletes.md", "withheld-attachments.md")


def stage(
    ws: Path, audit: str = "ok", deletes: int | str = 0, attach: int | str = 0,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Source the kit the way a case scaffold does, with cwd = the workspace."""
    ws.mkdir(parents=True, exist_ok=True)
    script = (
        f"set -e\nAUDIT_RESULT={audit}\nWITHHELD_DELETES={deletes}\n"
        f"WITHHELD_ATTACH={attach}\n. '{KIT}'\nstage_instance\n"
    )
    return subprocess.run(
        ["/bin/bash", "-c", script], cwd=ws, check=check,
        capture_output=True, text=True,
    )


def run_stub(ws: Path, name: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", f"scripts/{name}.py", *argv],
        cwd=ws, capture_output=True, text=True, check=False,
    )


def render(ws: Path) -> subprocess.CompletedProcess:
    return run_stub(
        ws, "instruction-render", "--output-dir", "tomo-tmp/rendered",
        "--run-id", "x",
    )


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


def test_untested_stub_stdout_lines(tmp_path):
    stage(tmp_path)
    assert run_stub(tmp_path, "upload-rendered").stdout == (
        "upload-rendered: uploaded=1 failed=0\n"
    )
    assert run_stub(tmp_path, "state-promoter").stdout == (
        "state-promoter: flipped pending-approval -> approved\n"
    )
    assert run_stub(tmp_path, "suggestion-parser").stdout == (
        '{"suggestions": [{"id": "s1", "kind": "create_atomic_note", "title": "Example"}]}\n'
    )
    assert render(tmp_path).stdout == "instruction-render: rendered=1 skipped=0\n"
