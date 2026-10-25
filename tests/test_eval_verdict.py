"""Tests for scripts/lib/eval_verdict.py (spec 041, T1.1).

The reader is run as a subprocess, the way the eval runner calls it. Fixtures are
copied to tmp_path first so verdict.txt never lands in tests/fixtures.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "lib" / "eval_verdict.py"
FIXTURES = ROOT / "tests" / "fixtures" / "eval_results"


def run(path, *flags):
    p = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *flags],
        capture_output=True, text=True,
    )
    return p.returncode, p.stdout, p.stderr


def stage(tmp_path, name, subdir=None):
    d = tmp_path / (subdir or name)
    d.mkdir()
    dest = d / "aggregate-result.json"
    shutil.copy(FIXTURES / f"{name}.json", dest)
    return dest


def load(tmp_path, name, subdir):
    path = stage(tmp_path, name, subdir)
    return path, json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data))


def test_green_3x(tmp_path):
    path = stage(tmp_path, "green-3x")
    code, out, err = run(path, "--tree", "clean")
    assert code == 0
    assert out.startswith("GREEN ")
    assert "2/2 cases" in out
    assert "runs 6" in out
    assert "$0.31" in out
    assert "83 s" in out
    assert "claude 2.1.310" in out
    assert "tree clean" in out
    assert str(path.parent) in out
    assert (path.parent / "verdict.txt").read_text().strip() == out.strip()


def test_relay_red_one_run_is_red_despite_cli_score(tmp_path):
    code, out, err = run(stage(tmp_path, "relay-red"))
    assert code == 1
    assert out.startswith("RED ")
    assert "(withheld-notices-relayed, 4-deletes-before-attachments-and-last, run 0)" in err
    assert "0.944" not in out + err


def test_pre_4350ddd_names_both_ordering_graders(tmp_path):
    code, out, err = run(stage(tmp_path, "pre-4350ddd-red"))
    assert code == 1
    assert out.startswith("RED ")
    assert "1-audit-before-upload" in err
    assert "2-audit-before-state-flip" in err


def test_cost_cap_partial_not_graded_though_runs_passed(tmp_path):
    path = stage(tmp_path, "cost-cap-partial")
    data = json.loads(path.read_text())
    assert data["cases"][0]["arms"]["with"][0]["passed"] is True
    code, out, err = run(path)
    assert code == 2
    assert out.startswith("NOT GRADED")
    assert "cost_ceiling" in out


def test_partial_without_reason_still_not_graded(tmp_path):
    path, data = load(tmp_path, "green-3x", "p")
    data["partial"] = True
    save(path, data)
    code, out, _ = run(path)
    assert code == 2
    assert out.startswith("NOT GRADED")
    assert "partial run" in out


def test_eperm_in_sandbox_hint(tmp_path):
    code, out, err = run(stage(tmp_path, "eperm-in-sandbox"))
    assert code == 2
    assert out.startswith("NOT GRADED")
    assert "outside Claude Code's Bash sandbox (see evals/README.md)" in out + err


def test_run_error_rate_limit_not_graded(tmp_path):
    path, data = load(tmp_path, "green-3x", "rl")
    data["cases"][0]["arms"]["with"][0]["error"] = "429 rate limit exceeded"
    save(path, data)
    code, out, err = run(path)
    assert code == 2
    assert out.startswith("NOT GRADED")
    assert "rate limit" in out + err


def test_run_aborted_not_graded(tmp_path):
    path, data = load(tmp_path, "green-3x", "ab")
    data["cases"][0]["arms"]["with"][0]["aborted"] = True
    save(path, data)
    code, out, _ = run(path)
    assert code == 2


def test_skipped_paid_graders_not_graded(tmp_path):
    path, data = load(tmp_path, "green-3x", "sk")
    data["cases"][0]["arms"]["with"][0]["skippedPaidGraders"] = True
    save(path, data)
    code, out, _ = run(path)
    assert code == 2
    assert out.startswith("NOT GRADED")


def test_unscored_grader_is_not_a_pass(tmp_path):
    path, data = load(tmp_path, "green-3x", "us")
    data["cases"][0]["arms"]["with"][0]["graders"][0]["scored"] = False
    save(path, data)
    code, _, _ = run(path)
    assert code == 2


def test_run_without_graders_not_graded(tmp_path):
    path, data = load(tmp_path, "green-3x", "ng")
    data["cases"][0]["arms"]["with"][0]["graders"] = []
    save(path, data)
    code, _, _ = run(path)
    assert code == 2


def test_not_graded_beats_red(tmp_path):
    path, data = load(tmp_path, "relay-red", "mix")
    data["cases"][0]["arms"]["with"][1]["error"] = "boom"
    save(path, data)
    code, out, _ = run(path)
    assert code == 2
    assert out.startswith("NOT GRADED")


def test_no_cases_not_graded(tmp_path):
    path, data = load(tmp_path, "green-3x", "nc")
    data["cases"] = []
    save(path, data)
    code, out, _ = run(path)
    assert code == 2
    assert "no cases" in out


def test_missing_file(tmp_path):
    code, out, err = run(tmp_path / "nope.json")
    assert code == 2
    assert "no result" in out + err
    assert "Traceback" not in err


def test_empty_file(tmp_path):
    p = tmp_path / "aggregate-result.json"
    p.write_text("")
    code, out, err = run(p)
    assert code == 2
    assert "Traceback" not in err


def test_invalid_json(tmp_path):
    p = tmp_path / "aggregate-result.json"
    p.write_text("{not json")
    code, out, err = run(p)
    assert code == 2
    assert "Traceback" not in err


@pytest.mark.parametrize("body", ["[]", "null", '{"schemaVersion": 1}',
                                  '{"schemaVersion": 1, "cases": [{"arms": 3}]}'])
def test_malformed_shapes_never_traceback(tmp_path, body):
    p = tmp_path / "aggregate-result.json"
    p.write_text(body)
    code, out, err = run(p)
    assert code == 2
    assert "Traceback" not in err


def test_schema_version_2_refused(tmp_path):
    path, data = load(tmp_path, "green-3x", "sv")
    data["schemaVersion"] = 2
    save(path, data)
    code, out, err = run(path)
    assert code == 2
    assert "unknown result schema" in out + err
    assert not out.startswith("GREEN")


def test_partial_suite_prefix(tmp_path):
    code, out, _ = run(stage(tmp_path, "green-3x"), "--partial-suite")
    assert code == 0
    assert out.startswith("GREEN (PARTIAL SUITE — does not satisfy the merge rule)")


def test_mutation_and_rev_echoed(tmp_path):
    _, out, _ = run(stage(tmp_path, "green-3x"), "--mutation", "drop-gate")
    assert "drop-gate" in out
    d = tmp_path / "second"
    d.mkdir()
    shutil.copy(FIXTURES / "green-3x.json", d / "aggregate-result.json")
    _, out, _ = run(d / "aggregate-result.json", "--rev", "abc1234")
    assert "abc1234" in out


def test_tree_dirty(tmp_path):
    _, out, _ = run(stage(tmp_path, "green-3x"), "--tree", "dirty")
    assert "tree dirty" in out


def test_compare_lists_only_differing_pairs(tmp_path):
    a = stage(tmp_path, "green-3x")
    b_dir = tmp_path / "b"
    b_dir.mkdir()
    # same case/grader names with differing rates: relay-red vs a green copy of it
    relay = json.loads((FIXTURES / "relay-red.json").read_text())
    green = json.loads((FIXTURES / "relay-red.json").read_text())
    for r in green["cases"][0]["arms"]["with"]:
        for g in r["graders"]:
            g["passed"] = True
    (b_dir / "a.json").write_text(json.dumps(green))
    (b_dir / "b.json").write_text(json.dumps(relay))
    p = subprocess.run([sys.executable, str(SCRIPT), "--compare", str(b_dir / "a.json"), str(b_dir / "b.json")],
                       capture_output=True, text=True)
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "withheld-notices-relayed" in lines[0]
    assert "4-deletes-before-attachments-and-last" in lines[0]
    assert p.returncode == 0
    del a


def test_compare_identical_prints_nothing(tmp_path):
    f = FIXTURES / "green-3x.json"
    p = subprocess.run([sys.executable, str(SCRIPT), "--compare", str(f), str(f)],
                       capture_output=True, text=True)
    assert p.stdout.strip() == ""
    assert p.returncode == 0


def test_never_writes_into_fixtures():
    assert not list(FIXTURES.glob("verdict.txt"))
