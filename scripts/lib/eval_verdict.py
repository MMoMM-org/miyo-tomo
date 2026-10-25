#!/usr/bin/env python3
# version: 0.1.1
"""Turn a `claude plugin eval` aggregate-result.json into one verdict line.

Why this exists: the CLI's own `passed`/`score` are not a merge gate (a case with one
failed grader in one of three runs still scores 0.944). The gate rule is stricter:
GREEN only if every grader of every run passed. Everything else is RED (a grader
failed) or NOT GRADED (the result cannot support a verdict: partial, errored, EPERM,
skipped graders, unknown schema, missing or malformed file). One ungraded run
poisons the whole suite. No input can produce GREEN unless that rule holds.

Usage:
  eval_verdict.py <aggregate-result.json> [--partial-suite] [--tree dirty|clean]
                  [--mutation <name> | --rev <rev>]
  eval_verdict.py --compare <a.json> <b.json>

stdout: the verdict line (also written to verdict.txt beside the result).
stderr: one detail line per failure / ungraded run.
exit:   0 GREEN, 1 RED, 2 NOT GRADED. (REFUSED, exit 3, belongs to the runner.)

Observed result keys: schemaVersion, partial, costUsd, durationSeconds, claudeVersion,
cases[].arms.with[].{score, passed, error, skippedPaidGraders, graders[]}; per grader
{name, passed, scored, withOnly}. `partialReason` and `aborted` are read when present.
A grader with scored=false is not a pass.
"""
import argparse
import json
import sys
from pathlib import Path

SANDBOX_HINT = "run outside Claude Code's Bash sandbox (see evals/README.md)"
PARTIAL_PREFIX = "PARTIAL SUITE — does not satisfy the merge rule"


class NotGraded(Exception):
    pass


def load(path):
    try:
        text = Path(path).read_text()
    except OSError as e:
        raise NotGraded(f"no result: {e.strerror or e}")
    except UnicodeDecodeError:
        raise NotGraded("no result: file is not valid UTF-8")
    if not text.strip():
        raise NotGraded("no result: file is empty")
    try:
        data = json.loads(text)
    except ValueError as e:
        raise NotGraded(f"no result: invalid JSON ({e})")
    if not isinstance(data, dict):
        raise NotGraded("no result: not a JSON object")
    if data.get("schemaVersion") != 1:
        raise NotGraded(f"unknown result schema: {data.get('schemaVersion')!r}")
    return data


def _runs(case):
    runs = case["arms"]["with"]
    if not isinstance(runs, list):
        raise TypeError("arms.with is not a list")
    return runs


def derive(data):
    """Return (cases_passed, cases_total, runs, failures, not_graded)."""
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise NotGraded("malformed result: cases is not a list")
    failures, not_graded = [], []
    if data.get("partial"):
        not_graded.append(f"partial run ({data.get('partialReason') or 'partial'})")
    if data.get("aborted"):
        not_graded.append("aborted run")
    if not cases:
        not_graded.append("no cases")
    runs_total = 0
    bad_cases = set()
    for case in cases:
        name = case["name"]
        runs = _runs(case)
        if not runs:
            not_graded.append(f"{name}: no runs")
            bad_cases.add(name)
        for i, run in enumerate(runs):
            runs_total += 1
            reason = None
            if run.get("error"):
                reason = str(run["error"])
                if "EPERM" in reason:
                    reason += f" — {SANDBOX_HINT}"
            elif run.get("aborted"):
                reason = "aborted"
            elif run.get("skippedPaidGraders"):
                reason = "paid graders skipped"
            elif not run.get("graders"):
                reason = "no graders ran"
            if reason is None:
                for g in run["graders"]:
                    if g.get("scored") is False:
                        reason = f"grader {g.get('name')} not scored"
                        break
                    if g.get("passed") is not True and g.get("passed") is not False:
                        reason = f"grader {g.get('name')} has no verdict"
                        break
            if reason is not None:
                not_graded.append(f"({name}, run {i}): {reason}")
                bad_cases.add(name)
                continue
            # run-level passed/score from the CLI are deliberately ignored: GREEN is derived per grader
            for g in run["graders"]:
                if g["passed"] is False:
                    failures.append((name, g["name"], i))
                    bad_cases.add(name)
    total = len(cases)
    return total - len(bad_cases), total, runs_total, failures, not_graded


def _num(data, key):
    v = data.get(key)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def tail(data, path, tree, mutation, rev):
    parts = []
    cost = _num(data, "costUsd") if data else None
    dur = _num(data, "durationSeconds") if data else None
    if cost is not None:
        parts.append(f"${cost:.2f}")
    if dur is not None:
        parts.append(f"{dur:.0f} s")
    if data and data.get("claudeVersion"):
        parts.append(f"claude {data['claudeVersion']}")
    parts.append(f"tree {tree}")
    if mutation:
        parts.append(f"mutation {mutation}")
    if rev:
        parts.append(f"rev {rev}")
    parts.append(str(Path(path).resolve().parent))
    return " · ".join(parts)


def verdict(path, partial_suite=False, tree="unknown", mutation=None, rev=None):
    """Return (exit_code, line, detail_lines)."""
    data = None
    try:
        data = load(path)
        passed, total, runs, failures, not_graded = derive(data)
    except NotGraded as e:
        return 2, f"NOT GRADED · {e} · " + tail(data, path, tree, mutation, rev), []
    except (KeyError, TypeError, AttributeError, IndexError) as e:
        return 2, f"NOT GRADED · malformed result ({type(e).__name__}: {e}) · " + tail(data, path, tree, mutation, rev), []
    prefix_ps = f" ({PARTIAL_PREFIX})" if partial_suite else ""
    t = tail(data, path, tree, mutation, rev)
    if not_graded:
        detail = [f"NOT GRADED {n}" for n in not_graded]
        return 2, f"NOT GRADED{prefix_ps} · {not_graded[0]} · " + t, detail
    if failures:
        detail = [f"FAIL ({c}, {g}, run {r})" for c, g, r in failures]
        names = ", ".join(f"{c}: {g} (run {r})" for c, g, r in failures)
        return 1, f"RED{prefix_ps} {passed}/{total} cases · {names} · runs {runs} · " + t, detail
    return 0, f"GREEN{prefix_ps} {passed}/{total} cases · runs {runs} · " + t, []


def rates(path):
    data = load(path)
    out = {}
    for case in data["cases"]:
        for run in _runs(case):
            for g in run.get("graders") or []:
                p, n = out.get((case["name"], g["name"]), (0, 0))
                out[(case["name"], g["name"])] = (p + (g.get("passed") is True), n + 1)
    return out


def compare(a, b):
    ra, rb = rates(a), rates(b)
    lines = []
    for key in sorted(set(ra) | set(rb)):
        x, y = ra.get(key), rb.get(key)
        if x is None or y is None or x[0] * y[1] != y[0] * x[1]:
            fx = f"{x[0]}/{x[1]}" if x else "absent"
            fy = f"{y[0]}/{y[1]}" if y else "absent"
            lines.append(f"{key[0]}: {key[1]}: {fx} -> {fy}")
    return lines


def _oneline(e):
    return f"{type(e).__name__}: {e}".replace("\n", " ")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("result", nargs="?")
    ap.add_argument("--partial-suite", action="store_true")
    ap.add_argument("--tree", choices=["clean", "dirty"], default="unknown")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--mutation")
    g.add_argument("--rev")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = ap.parse_args(argv)
    if args.compare:
        try:
            for ln in compare(*args.compare):
                print(ln)
        except Exception as e:  # a crash must never share exit 1 with RED
            print(f"NOT GRADED · cannot compare: {_oneline(e)}")
            return 2
        return 0
    if not args.result:
        ap.error("result path required")
    try:
        code, line, detail = verdict(args.result, args.partial_suite, args.tree, args.mutation, args.rev)
    except Exception as e:  # a crash must never share exit 1 with RED
        code, line, detail = 2, f"NOT GRADED · unexpected error ({_oneline(e)})", []
    print(line)
    for d in detail:
        print(d, file=sys.stderr)
    if code == 2 and not detail:
        print(line, file=sys.stderr)
    parent = Path(args.result).resolve().parent
    if parent.is_dir():
        try:
            (parent / "verdict.txt").write_text(line + "\n")
        except OSError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
