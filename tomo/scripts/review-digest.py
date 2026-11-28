#!/usr/bin/env python3
# review-digest.py — Plan and check the condensing jobs of a /review read: digesters, carryover, the proposer's inputs.
# version: 0.3.0
"""The condensing step of /review (spec 047 T4.3; PRD F1-AC6, F6-AC1, F6-AC2, F6-AC4, F6-AC8; ADR-4, ADR-8).

After ``review-read.py`` wrote the stage ``tomo-tmp/review/<stem>/``, ``plan``
lists the agent jobs still to run and ``check`` judges the files the agents
wrote. Both keep the job state in ``condensed.json`` (written only here).

Usage (cwd = instance root):
    python3 scripts/review-digest.py plan --stem 2026-03_review [--tmp tomo-tmp/review]
    python3 scripts/review-digest.py check --stem 2026-03_review [--tmp tomo-tmp/review]

Output: one JSON object on stdout, ASCII-escaped. Paths are stage-relative.
    plan ok:   status ok, stem, read_id, read_at, ready,
               rounds [[job]] (≤ MAX_PARALLEL jobs per round; [] when nothing is left to run),
               done [units passed], not_condensed [{unit, days}], carryover_state none|pending|retry|passed|failed,
               proposer {inputs [paths in read order], out "proposals.json", carried}
        job:   {agent review-digester, unit, days, day_files, weekly_note, sections,
                section_files [the context file(s) holding sections; [] when sections is false], out, cap_bytes}
               {agent review-carryover, previous_files, out "carryover.json", cap_bytes 12288}
    check ok:  status ok, stem, units {<unit>: {state, errors?}},
               carryover {state, notes [{path, state, items}], errors?}, retry [{agent, unit?, errors}],
               not_condensed [{unit, days}], carry_failed, ready, proposer
    stopped:   status stopped, stem, problems [nothing-condensed], not_condensed [every unit]
    refused:   status refused, stem, problems [stage-missing | stage-invalid | read-stale]

Rules:
    plan: a job failed in an earlier run is pending again with 0 attempts; every open job's present file is
    checked without counting an attempt; a proposals.json is deleted. check: every open job spends one
    attempt — 1st failure retry, 2nd failed; a carryover passing with one note's items invalid has those
    items removed from carryover.json, after condensed.json recorded the failed note; a passed carryover
    whose file still holds invalid items is settled again. Only taking-part units and
    their taking-part days are dispatched.

Exit codes:
    0 — output usable (ok, stopped, refused)
    1 — unexpected exception; stderr carries the exception class name only
    2 — bad invocation (missing argument, a --stem that is empty, ".", or carries /, \\ or ..)

Design notes: docs/tomo/scripts/review-digest.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import review_digest as rd  # noqa: E402
from lib import review_stage  # noqa: E402
from lib.note_io import atomic_write_text  # noqa: E402
from lib.period import MONTH, WEEK  # noqa: E402
from lib.review_period import CHILD  # noqa: E402
from lib.review_stage_codec import compact, encode  # noqa: E402
from lib.review_state import safe_stem  # noqa: E402

DEFAULT_TMP = "tomo-tmp/review"
MAX_PARALLEL = 16
DIGESTER, CARRIER = "review-digester", "review-carryover"
PROPOSALS = "proposals.json"
CHILD_LABEL = {WEEK: "weekly", MONTH: "monthly"}
STAGE_MISSING, STAGE_INVALID, READ_STALE = "stage-missing", "stage-invalid", "read-stale"
NOTHING_CONDENSED = "nothing-condensed"


class Refused(Exception):
    def __init__(self, problem: str):
        super().__init__(problem)
        self.problem = problem


# ---------------------------------------------------------------- arguments

def _stem_arg(text: str) -> str:
    if not safe_stem(text):
        raise argparse.ArgumentTypeError("--stem must name a plain folder")
    return text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Plan and check the /review condensing jobs.")
    sub = p.add_subparsers(dest="command", required=True)
    for name, text in (("plan", "List the jobs still to run and the proposer's inputs"),
                       ("check", "Check the files the agents wrote; one attempt per open job")):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--stem", required=True, type=_stem_arg, help="Stage folder under --tmp")
        cmd.add_argument("--tmp", default=DEFAULT_TMP, help="Where tomo-tmp/review/<stem>/ lives")
    return p


# ---------------------------------------------------------------- the stage

class Stage:
    """The loaded read, its manifest, its weeks.json units and the job state."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.read = review_stage.load(path)
            self.manifest = review_stage.manifest(path)
            self.weeks = json.loads((path / review_stage.WEEKS).read_text(encoding="utf-8"))
            self.units: List[dict] = list(self.weeks["units"])
            self.cap = int(self.weeks["digest_cap_bytes"])
        except review_stage.StageMissing:
            raise Refused(STAGE_MISSING) from None
        except review_stage.StageStale:
            raise Refused(READ_STALE) from None
        except (review_stage.StageInvalid, OSError, KeyError, TypeError, ValueError):
            raise Refused(STAGE_INVALID) from None
        self.read_id: str = self.manifest["read_id"]
        found = [n for n in self.manifest["files"].get("previous", [])
                 if any(p.get("state") == "found" and p.get("path") and f"{p['kind']}-{p['name']}.json" == n
                        for p in self.read["previous"])]
        self.previous_files = [f"{review_stage.PREVIOUS}/{n}" for n in found]
        self.state = self._state()
        self._section_files: Optional[List[str]] = None

    def _state(self) -> dict:
        fresh = rd.new_state(self.read_id, self.units, carryover=bool(self.previous_files))
        stored = self.read.get("condensed")
        if not stored:
            return fresh
        units = {u: dict((stored.get("units") or {}).get(u) or job) for u, job in fresh["units"].items()}
        return {"read_id": self.read_id, "units": units, "carryover": dict(stored.get("carryover") or
                                                                          fresh["carryover"])}

    def text(self, name: str) -> Optional[str]:
        path = self.path / name
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def save(self) -> None:
        atomic_write_text(self.path / review_stage.CONDENSED, compact(self.state))

    def taking_part(self) -> List[dict]:
        return [u for u in self.units if u["unit"] in self.state["units"]]

    def unit_errors(self, unit: dict) -> List[str]:
        return rd.check_digest(self.text(_digest(unit)), unit, self.read, read_id=self.read_id, cap_bytes=self.cap)

    def section_files(self) -> List[str]:
        """The context files (``context.json`` and its spilled parts, manifest order) holding a non-empty
        ``sections`` list."""
        if self._section_files is None:
            names = self.manifest["files"].get("context") or [review_stage.CONTEXT]
            self._section_files = [n for n in names if json.loads(self.text(n) or "{}").get("sections")]
        return self._section_files

    def carry_check(self) -> rd.CarryoverCheck:
        return rd.check_carryover(self.text(review_stage.CARRYOVER), self.read, read_id=self.read_id)


def _digest(unit: dict) -> str:
    return f"{review_stage.DIGESTS}/{unit['unit']}.json"


def _unit_out(job: dict, errors: Sequence[str] = ()) -> dict:
    return {"state": job["state"], **({"errors": list(errors)} if errors else {})}


def _open(job: dict) -> bool:
    return job["state"] in (rd.PENDING, rd.RETRY)


# ---------------------------------------------------------------- jobs and rounds

def rounds(jobs: Sequence[Any]) -> List[List[Any]]:
    """The jobs in rounds of at most ``MAX_PARALLEL``, in order."""
    return [list(jobs[i:i + MAX_PARALLEL]) for i in range(0, len(jobs), MAX_PARALLEL)]


def _digester_job(stage: Stage, unit: dict) -> dict:
    days = rd.taking_part_days(unit, stage.read)
    weekly = unit.get("weekly_note")
    sections = bool(stage.read.get("sections"))
    return {"agent": DIGESTER, "unit": unit["unit"], "days": days,
            "day_files": [f"{review_stage.DAYS}/{d}.json" for d in days],
            "weekly_note": f"{review_stage.CHILDREN}/{weekly}" if weekly else None,
            "sections": sections, "section_files": stage.section_files() if sections else [],
            "out": _digest(unit), "cap_bytes": stage.cap}


def _carrier_job(stage: Stage) -> dict:
    return {"agent": CARRIER, "previous_files": list(stage.previous_files), "out": review_stage.CARRYOVER,
            "cap_bytes": rd.CARRYOVER_CAP}


def _proposer(stage: Stage) -> dict:
    files = stage.manifest["files"]
    inputs = list(files.get("context") or [review_stage.CONTEXT])
    inputs += [_digest(u) for u in stage.taking_part() if stage.state["units"][u["unit"]]["state"] == rd.PASSED]
    carried = stage.state["carryover"]["state"] == rd.PASSED
    if carried:
        inputs.append(review_stage.CARRYOVER)
    label = CHILD_LABEL.get(CHILD.get(stage.manifest["period"]["kind"]))
    if label:
        inputs += [f"{review_stage.CHILDREN}/{n}" for n in files.get("children") or [] if n.startswith(f"{label}-")]
    return {"inputs": inputs, "out": PROPOSALS, "carried": carried}


# ---------------------------------------------------------------- plan

def plan(stage: Stage) -> dict:
    state = stage.state
    for unit in stage.taking_part():
        job = state["units"][unit["unit"]]
        if job["state"] == rd.FAILED:
            job = {"state": rd.PENDING, "attempts": 0}
        if _open(job) and stage.text(_digest(unit)) is not None:
            job = rd.advance(job, stage.unit_errors(unit), count=False)
        state["units"][unit["unit"]] = job
    carry = state["carryover"]
    if carry["state"] == rd.FAILED:
        carry = {"state": rd.PENDING, "attempts": 0, "notes": {}}
    if _open(carry) and stage.text(review_stage.CARRYOVER) is not None:
        carry = rd.advance_carryover(carry, stage.carry_check(), count=False)
    state["carryover"] = carry
    (stage.path / PROPOSALS).unlink(missing_ok=True)
    stage.save()
    jobs = [_digester_job(stage, u) for u in stage.taking_part() if _open(state["units"][u["unit"]])]
    if _open(carry):
        jobs.append(_carrier_job(stage))
    return {"status": "ok", "read_id": stage.read_id, "read_at": stage.manifest.get("read_at"),
            "ready": rd.ready(state), "rounds": rounds(jobs),
            "done": [u["unit"] for u in stage.taking_part() if state["units"][u["unit"]]["state"] == rd.PASSED],
            "not_condensed": rd.not_condensed(state, stage.units), "carryover_state": carry["state"],
            "proposer": _proposer(stage)}


# ---------------------------------------------------------------- check

def _check_carryover(stage: Stage, retry: List[dict]) -> List[str]:
    """One counted attempt for an open carryover; returns the check's errors (``[]`` when not checked)."""
    job = stage.state["carryover"]
    if not _open(job):
        return []
    check = stage.carry_check()
    job = rd.advance_carryover(job, check, count=True)
    stage.state["carryover"] = job
    if job["state"] == rd.RETRY:
        retry.append({"agent": CARRIER, "errors": list(check.errors)})
    return list(check.errors)


def _settle_carryover(stage: Stage) -> None:
    """A passed carryover.json without its invalid items and the other items of their notes; written only
    when that changes it, so it runs again after a crash at no cost."""
    if stage.state["carryover"]["state"] != rd.PASSED or stage.text(review_stage.CARRYOVER) is None:
        return
    check = stage.carry_check()
    if not check.bad_items:
        return
    data = json.loads(stage.text(review_stage.CARRYOVER) or "")
    settled = rd.settle_carryover(data, check)
    if settled != data:
        atomic_write_text(stage.path / review_stage.CARRYOVER, encode(settled))


def _carry_notes(stage: Stage, job: dict) -> List[dict]:
    """``[{path, state, items}]`` of the carryover's notes; items counted in carryover.json as it stands."""
    notes: Dict[str, str] = job.get("notes") or {}
    if not notes:
        return []
    counts: Dict[str, int] = {}
    if job["state"] == rd.PASSED:
        data = json.loads(stage.text(review_stage.CARRYOVER) or "")
        counts = {n["path"]: n["items"] for n in rd.settle_carryover(data, rd.CarryoverCheck())["notes"]}
    return [{"path": path, "state": state, "items": counts.get(path, 0)} for path, state in notes.items()]


def check(stage: Stage) -> dict:
    state, retry, units = stage.state, [], {}
    for unit in stage.taking_part():
        name, job = unit["unit"], state["units"][unit["unit"]]
        if not _open(job):
            units[name] = _unit_out(job)
            continue
        errors = stage.unit_errors(unit)
        job = rd.advance(job, errors, count=True)
        state["units"][name] = job
        units[name] = _unit_out(job, errors)
        if job["state"] == rd.RETRY:
            retry.append({"agent": DIGESTER, "unit": name, "errors": errors})
    carry_errors = _check_carryover(stage, retry)
    stage.save()                      # the settled job state first: a crash after it loses no failed note
    _settle_carryover(stage)
    job = stage.state["carryover"]
    carryover = {"state": job["state"], "notes": _carry_notes(stage, job),
                 **({"errors": carry_errors} if carry_errors else {})}
    if rd.nothing_condensed(state):
        return {"status": "stopped", "problems": [NOTHING_CONDENSED],
                "not_condensed": rd.not_condensed(state, stage.units)}
    return {"status": "ok", "units": units, "carryover": carryover, "retry": retry,
            "not_condensed": rd.not_condensed(state, stage.units),
            "carry_failed": state["carryover"]["state"] == rd.FAILED, "ready": rd.ready(state),
            "proposer": _proposer(stage)}


# ---------------------------------------------------------------- main

def run(args: argparse.Namespace) -> dict:
    head = {"stem": args.stem}
    try:
        stage = Stage(Path(args.tmp) / args.stem)
    except Refused as refusal:
        return {"status": "refused", **head, "problems": [refusal.problem]}
    out = (plan if args.command == "plan" else check)(stage)
    return {"status": out.pop("status"), **head, **out}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Exception as exc:  # noqa: BLE001 — the contract: class name only, exit 1
        print(type(exc).__name__, file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
