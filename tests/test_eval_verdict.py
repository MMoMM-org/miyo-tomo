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


def test_model_override_green(tmp_path):
    code, out, _ = run(stage(tmp_path, "model-override-green"))
    assert code == 0
    assert out.startswith("GREEN ")
    assert "1/1 cases" in out
    assert "runs 1" in out


def test_cli_run_level_passed_and_score_are_ignored(tmp_path):
    path, data = load(tmp_path, "green-3x", "rl-score")
    for case in data["cases"]:
        for r in case["arms"]["with"]:
            r["passed"], r["score"] = False, 0.5
    save(path, data)
    code, out, _ = run(path)
    assert code == 0
    assert out.startswith("GREEN ")


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
    assert out.startswith("NOT GRADED · cost cap reached after 1 graded run ·"), out


def test_cost_cap_names_the_cap_when_given(tmp_path):
    code, out, _ = run(stage(tmp_path, "cost-cap-partial"), "--cost-cap", "5")
    assert code == 2
    assert out.startswith("NOT GRADED · cost cap $5 reached after 1 graded run ·"), out


def test_cost_cap_counts_runs_plural(tmp_path):
    path, data = load(tmp_path, "green-3x", "cp")
    data["partial"] = True
    data["partialReason"] = "cost_ceiling"
    save(path, data)
    code, out, _ = run(path)
    assert code == 2
    assert out.startswith("NOT GRADED · cost cap reached after 6 graded runs ·"), out


def test_other_partial_reason_keeps_generic_wording(tmp_path):
    path, data = load(tmp_path, "green-3x", "pr")
    data["partial"] = True
    data["partialReason"] = "rate_limit"
    save(path, data)
    code, out, _ = run(path)
    assert code == 2
    assert out.startswith("NOT GRADED · partial run (rate_limit) ·"), out


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


def _bad_run(mutate):
    data = json.loads((FIXTURES / "green-3x.json").read_text())
    mutate(data["cases"][0]["arms"])
    return json.dumps(data).encode()


MALFORMED = {
    "array": b"[]",
    "null": b"null",
    "no-cases": b'{"schemaVersion": 1}',
    "arms-int": b'{"schemaVersion": 1, "cases": [{"arms": 3}]}',
    "invalid-utf8": b"\xff\xfe",
    "graders-string": _bad_run(lambda a: a["with"][0].update(graders="x")),
    "run-is-string": _bad_run(lambda a: a.update({"with": ["x"]})),
    "grader-without-passed": _bad_run(lambda a: a["with"][0]["graders"][0].pop("passed")),
}


@pytest.mark.parametrize("body", MALFORMED.values(), ids=MALFORMED.keys())
def test_malformed_shapes_never_traceback(tmp_path, body):
    p = tmp_path / "aggregate-result.json"
    p.write_bytes(body)
    code, out, err = run(p)
    assert code == 2
    assert "Traceback" not in err
    assert out.startswith("NOT GRADED")


def test_unexpected_crash_is_not_graded_never_red(monkeypatch, capsys, tmp_path):
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import eval_verdict
    finally:
        sys.path.remove(str(SCRIPT.parent))

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(eval_verdict, "derive", boom)
    path = stage(tmp_path, "green-3x")
    assert eval_verdict.main([str(path)]) == 2
    out = capsys.readouterr()
    assert out.out.startswith("NOT GRADED")
    assert "Traceback" not in out.out + out.err
    monkeypatch.setattr(eval_verdict, "compare", boom)
    assert eval_verdict.main(["--compare", str(path), str(path)]) == 2


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
    _, out, _ = run(stage(tmp_path, "green-3x", "second"), "--rev", "abc1234")
    assert "abc1234" in out


def test_tree_dirty(tmp_path):
    _, out, _ = run(stage(tmp_path, "green-3x"), "--tree", "dirty")
    assert "tree dirty" in out


def test_compare_lists_only_differing_pairs(tmp_path):
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


def test_compare_disjoint_pair_reports_every_grader_of_both(capsys):
    p = subprocess.run([sys.executable, str(SCRIPT), "--compare",
                        str(FIXTURES / "green-3x.json"), str(FIXTURES / "relay-red.json")],
                       capture_output=True, text=True)
    assert p.returncode == 0
    assert p.stdout.splitlines() == [
        "audit-gates-delivery: 0-conductor-dispatched: 3/3 -> absent",
        "audit-gates-delivery: 1-audit-before-upload: 3/3 -> absent",
        "audit-gates-delivery: 2-audit-before-state-flip: 3/3 -> absent",
        "audit-mismatch-stops: 0-conductor-dispatched: 3/3 -> absent",
        "audit-mismatch-stops: 1-no-upload-after-mismatch: 3/3 -> absent",
        "audit-mismatch-stops: 2-no-state-flip-after-mismatch: 3/3 -> absent",
        "audit-mismatch-stops: 3-audit-ran: 3/3 -> absent",
        "audit-mismatch-stops: 4-diff-reported-verbatim: 3/3 -> absent",
        "withheld-notices-relayed: 0-conductor-dispatched: absent -> 3/3",
        "withheld-notices-relayed: 1-line-verbatim: absent -> 3/3",
        "withheld-notices-relayed: 2-line-verbatim: absent -> 3/3",
        "withheld-notices-relayed: 3-line-verbatim: absent -> 3/3",
        "withheld-notices-relayed: 4-deletes-before-attachments-and-last: absent -> 2/3",
        "withheld-notices-relayed: 5-no-leak: absent -> 3/3",
    ]


def test_compare_identical_prints_nothing(tmp_path):
    f = FIXTURES / "green-3x.json"
    p = subprocess.run([sys.executable, str(SCRIPT), "--compare", str(f), str(f)],
                       capture_output=True, text=True)
    assert p.stdout.strip() == ""
    assert p.returncode == 0


def test_never_writes_into_fixtures():
    assert not list(FIXTURES.glob("verdict.txt"))


# ── repo-relative results path, errored-run cap count, --compare on directories ──


def _tail_path(out):
    return out.strip().split(" · ")[-1]


def test_results_path_is_relative_to_the_given_root(tmp_path):
    path = stage(tmp_path, "green-3x", "seed")
    nested = tmp_path / "tomo-tmp" / "evals" / "2026-10-25T18-35-17Z"
    nested.mkdir(parents=True)
    dest = nested / "aggregate-result.json"
    shutil.copy(path, dest)
    code, out, _ = run(dest, "--root", str(tmp_path))
    assert code == 0
    assert _tail_path(out) == "tomo-tmp/evals/2026-10-25T18-35-17Z", out
    assert str(tmp_path) not in out


def test_results_path_outside_root_is_never_resolved_absolute(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    path = stage(tmp_path, "green-3x", "elsewhere")
    code, out, _ = run(path, "--root", str(root))
    assert code == 0
    assert _tail_path(out) == str(path.parent), out


def test_results_path_relative_input_stays_as_given(tmp_path):
    stage(tmp_path, "green-3x", "res")
    p = subprocess.run([sys.executable, str(SCRIPT), "res/aggregate-result.json"],
                       capture_output=True, text=True, cwd=tmp_path)
    assert _tail_path(p.stdout) == "res", p.stdout


def test_not_graded_line_path_is_relative_too(tmp_path):
    nested = tmp_path / "tomo-tmp" / "evals" / "T"
    nested.mkdir(parents=True)
    code, out, _ = run(nested / "missing.json", "--root", str(tmp_path))
    assert code == 2
    assert _tail_path(out) == "tomo-tmp/evals/T", out


def test_cost_cap_counts_only_runs_without_an_error(tmp_path):
    path, data = load(tmp_path, "green-3x", "cp2")
    data["partial"] = True
    data["partialReason"] = "cost_ceiling"
    runs = data["cases"][0]["arms"]["with"]
    runs[0]["error"] = "rate limited"
    total = sum(len(c["arms"]["with"]) for c in data["cases"])
    save(path, data)
    code, out, _ = run(path)
    assert code == 2
    assert out.startswith(f"NOT GRADED · cost cap reached after {total - 1} graded runs ·"), out


def test_compare_accepts_results_directories(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    shutil.copy(FIXTURES / "green-3x.json", a / "aggregate-result.json")
    shutil.copy(FIXTURES / "relay-red.json", b / "aggregate-result.json")
    p = subprocess.run([sys.executable, str(SCRIPT), "--compare", str(a), str(b)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "withheld-notices-relayed: 0-conductor-dispatched: absent -> 3/3" in p.stdout.splitlines()


def test_compare_directory_without_aggregate_is_a_clear_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    p = subprocess.run([sys.executable, str(SCRIPT), "--compare", str(empty), str(FIXTURES / "green-3x.json")],
                       capture_output=True, text=True)
    assert p.returncode == 2
    assert p.stdout.startswith("NOT GRADED · cannot compare:"), p.stdout
    assert "aggregate-result.json" in p.stdout
    assert "Traceback" not in p.stdout + p.stderr
