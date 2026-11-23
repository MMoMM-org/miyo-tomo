#!/usr/bin/env python3
# review-read.py — Read one finished period for /review: the stage for the agents, the report on stdout.
# version: 0.5.0
"""The reading step of /review (spec 045 T3.4; PRD F3-AC8..F3-AC13; spec 046 T3.3; spec 047 T2.4).

After ``review-session.py start`` named a finished period and the setup of
its kind is confirmed, this script reads the period through Kado under the
pacer — the dailies of every day, the day after, the same-day linked notes,
the task notes, a month's weekly notes, a quarter's weekly and monthly notes
and the vault growth (lib/review_period.py) — writes what it read as the
stage ``tomo-tmp/review/<stem>/`` (lib/review_stage.py: day, growth, child
and context files, weeks.json, manifest.json last) and prints the report:
per day which dailies were found and in what state, which linked notes were
read or missing, the pacing summary (calls, retried, waited_s, not_read,
advice) and what Kado answered with nothing. A stored read of the same
period, kind and section mapping is continued without any Kado call. No
note text reaches stdout or stderr.

Usage (cwd = instance root):
    python3 scripts/review-read.py --period 2026-W13 --kind week|month|quarter [--stem 2026-W13_review]
        [--fresh] [--measure] [--tmp tomo-tmp/review] [--config config/vault-config.yaml] [--profiles-dir DIR]
    Period names: 2026-W13 (week), 2026-03 (month), 2026-Q1 (quarter).

Output: one JSON object on stdout, ASCII-escaped.
    new read:  status ok, stem, period {kind, name, start, end}, continued false, read_id, read_at,
               stage "tomo-tmp/review/<stem>", units (count of weeks.json units), report, nothing_to_review false,
               discarded? fresh | sections-changed | stage-invalid (a stored read was thrown away first)
    report {days [{date, dailies [{path, state found|empty|partly-read|failed}], duplicate,
                   linked [{name, path, state read|missing|failed}]}],
            day_after {date, dailies [{path, state read|failed}]}, task_notes [{path, state}],
            weekly_status? found|none-found|kado-empty|not-read|not-configured, weekly_notes? [{week, path, state}],
            monthly_status? (quarter, same values), monthly_notes? [{month, path, state}],
            growth {created, mocs_changed, mocs_linked_by_new, moc_folders, kado_none},
            previous [{kind week|month|quarter, name, role previous-week|previous-month|previous-quarter, path,
                       state found|empty|missing|not-set-up|not-read, cause? refused|failed|kado-none,
                       partly_read}] (the previous review notes, read in the same paced pass; no text),
            calls, retried, waited_s, not_read [paths], kado_empty [sources],
            advice [raise-kado-limit | check-key-access]}
    continued: status ok, stem, period, continued true, read_id, read_at (of the stored read), stage, units,
               report (stored), nothing_to_review false
    nothing to review: status ok, stem, period, continued false, report, nothing_to_review true, discarded?
    stopped:   error {kind kado-unreachable|kado-auth, detail} when stopped by Kado,
               problems [setup-missing | setup-invalid | daily-not-configured | dailies-not-read] when stopped
               before or without a usable read (errors [pointers] with setup-invalid);
               a stopped output never carries nothing_to_review
    --measure (status ok): status, stem, period, nothing_to_review and
        measure {calls, retried, waited_s, not_read (count), bytes {<stage-relative file>: n} (every file the run
                 would write, the manifest last), units [{unit, bytes}], over_ceiling [files], over_budget [units]}
        only; no file is written, no stored read continued or discarded

Rules:
    One KadoClient per run, built before the first call and wrapped by one
    ReviewPacer, so the summary's counters cover the whole run and nothing
    else; a continued read builds none. The period name is resolved under
    the configured week rule. Without --fresh a stored read continues when
    its manifest names layout 1, this period and kind and the current
    section digest and every stage file loads. Every other run discards the
    stage content (meta.json and payloads.json kept) before its first Kado
    call. No daily with content → nothing_to_review true, nothing written;
    the check-key-access advice comes from the folder listings alone
    (kado_empty, lib/review_period), never from the empty period. The daily
    folder listing still in not_read after the end pass → status stopped,
    dailies-not-read, nothing written. Kado unreachable or a refused key →
    status stopped, nothing written.

Exit codes:
    0 — output usable (every status, every error object)
    1 — unexpected exception; stderr carries the exception class name only
    2 — bad invocation (missing argument, bad --kind, a period name that does
        not fit the kind, a --stem that is empty, ".", or carries /, \\ or ..)

Design notes: docs/tomo/scripts/review-read.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import review_config as rc  # noqa: E402
from lib.kado_client import KadoAuthError, KadoClient, KadoConnectionError  # noqa: E402
from lib.note_io import ConfigError, load_vault_config  # noqa: E402
from lib.period import MONTH, QUARTER, WEEK, InvalidPeriod, Period, WeekRule, build  # noqa: E402
from lib import review_stage  # noqa: E402
from lib import review_weeks  # noqa: E402
from lib.review_stage_codec import compact, size  # noqa: E402
from lib.review_day import day_settings  # noqa: E402
from lib.review_pacer import ADVICE_RAISE_LIMIT, ReviewPacer  # noqa: E402
from lib.review_period import read_period, sources_from_config  # noqa: E402
from lib.review_sections import REVIEW as ANALYSIS_PLACEMENT  # noqa: E402
from lib.review_state import STEM_SUFFIX, safe_stem  # noqa: E402

DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
DEFAULT_TMP = "tomo-tmp/review"
_PERIOD_RE = {
    WEEK: re.compile(r"^(\d{4})-W(\d{2})$"),
    MONTH: re.compile(r"^(\d{4})-(\d{2})$"),
    QUARTER: re.compile(r"^(\d{4})-Q([1-4])$"),
}
DEFINITION_FIELDS = ("heading", "level", "parent", "description", "keywords", "groups", "cap")
DISCARD_FRESH, DISCARD_SECTIONS, DISCARD_INVALID = "fresh", "sections-changed", "stage-invalid"


class Stopped(Exception):
    """The run cannot go on; ``payload`` joins the output next to ``status: stopped``."""

    def __init__(self, **payload):
        super().__init__(json.dumps(sorted(payload)))
        self.payload = payload


# ---------------------------------------------------------------- arguments

def period_from(name: str, kind: str, rule: WeekRule) -> Optional[Period]:
    """The ``Period`` a canonical name (``2026-W13``, ``2026-03``, ``2026-Q1``) denotes under ``rule``; None if not."""
    match = _PERIOD_RE[kind].match(name.strip())
    if match is None:
        return None
    year, number = int(match.group(1)), int(match.group(2))
    try:
        return build(kind, year, number, rule)
    except InvalidPeriod:
        return None


def _stem_arg(text: str) -> str:
    if not safe_stem(text):
        raise argparse.ArgumentTypeError("a plain folder name, not empty, . or .., without / or \\")
    return text


def _date_arg(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read one finished period for /review.")
    p.add_argument("--period", required=True, help="Canonical period name: 2026-W13, 2026-03 or 2026-Q1")
    p.add_argument("--kind", required=True, choices=tuple(_PERIOD_RE))
    p.add_argument("--stem", type=_stem_arg, help="Stage folder under --tmp (default: <period>_review)")
    p.add_argument("--fresh", action="store_true", help="Discard a stored read of the stem and read anew")
    p.add_argument("--measure", action="store_true", help="Print calls, waits and bytes; write no file")
    p.add_argument("--tmp", default=DEFAULT_TMP, help="Where tomo-tmp/review/<stem>/ lives")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR), help="framework profiles directory")
    p.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)
    return p


# ---------------------------------------------------------------- the run

def _setup(args: argparse.Namespace):
    try:
        config = load_vault_config(args.config)
    except ConfigError:
        config = {}
    profile = rc.load_profile(Path(args.profiles_dir), config)
    try:
        setup = rc.review_setup(config, profile, args.kind, today=args.today)
    except rc.SetupInvalid as invalid:
        raise Stopped(problems=["setup-invalid"], errors=invalid.pointers) from None
    if setup is None:
        raise Stopped(problems=["setup-missing"])
    return config, profile, setup


def _read(period: Period, sources, settings: dict) -> dict:
    """One client, one pacer, every read of the run between them; Kado stops map to the SDD error kinds."""
    try:
        client = KadoClient()
        with ReviewPacer(client) as pacer:
            result = read_period(period, sources, settings, client, pacer)
            summary = pacer.summary(result["not_read"])
    except KadoAuthError as exc:
        raise Stopped(error={"kind": "kado-auth", "detail": str(exc)}) from None
    except KadoConnectionError as exc:
        raise Stopped(error={"kind": "kado-unreachable", "detail": str(exc)}) from None
    report = result["report"]
    advice: List[str] = list(report.get("advice") or [])
    advice += [a for a in summary.pop("advice") if a not in advice]
    report.update(summary)
    report["advice"] = advice
    return result


def section_definitions(setup) -> List[dict]:
    """The SectionDefinition of each mapped row: ``key`` is the row ``id``; where a row lands is not the model's,
    only an analysis row says it is one (``analysis: true``)."""
    return [{"key": row["id"], **{name: row[name] for name in DEFINITION_FIELDS},
             **({"analysis": True} if row.get("placement") == ANALYSIS_PLACEMENT else {})} for row in setup.sections]


def _measure(report: dict, files: dict, manifest: dict) -> dict:
    """Counts and bytes only (CON-3): the pacing counters, each stage file's size, the units and what is over."""
    units = [{"unit": u["unit"], "bytes": u["bytes"]}
             for u in json.loads(files[review_stage.WEEKS])["units"]]
    sizes = {name: size(text) for name, text in files.items()}
    sizes[review_stage.MANIFEST] = size(compact(manifest))
    return {"calls": report["calls"], "retried": report["retried"], "waited_s": report["waited_s"],
            "not_read": len(report["not_read"]), "bytes": sizes, "units": units,
            "over_ceiling": manifest["over_ceiling"], "over_budget": review_weeks.over_budget(units)}


def _period_dict(period: Period) -> dict:
    return {"kind": period.kind, "name": period.name, "start": period.start.isoformat(),
            "end": period.end.isoformat()}


def _stored(stage: Path, period: Period, digest: str, fresh: bool):
    """``(manifest, unit count)`` of the read to continue and None, or ``(None, None, why it is discarded or None)``."""
    try:
        manifest = review_stage.manifest(stage)
    except review_stage.StageMissing:
        return None, None, None
    except review_stage.StageInvalid:
        return None, None, DISCARD_INVALID
    if fresh:
        return None, None, DISCARD_FRESH
    if not review_stage.can_continue(stage, period, digest):
        same_read = manifest.get("layout") == review_stage.LAYOUT and manifest.get("period") == _period_dict(period)
        return None, None, (DISCARD_SECTIONS if same_read else DISCARD_INVALID)
    try:
        review_stage.load(stage)
        units = _units(stage)
    except (review_stage.StageMissing, review_stage.StageInvalid, review_stage.StageStale,
            KeyError, TypeError, ValueError):
        return None, None, DISCARD_INVALID
    return manifest, units, None


def _units(stage: Path) -> int:
    return len(json.loads((stage / review_stage.WEEKS).read_text(encoding="utf-8"))["units"])


def run(args: argparse.Namespace) -> dict:
    config, profile, setup = _setup(args)
    period = period_from(args.period, args.kind, setup.rule)
    if period is None:
        raise argparse.ArgumentTypeError("--period does not name a period of this kind")
    stem = args.stem or f"{period.name}{STEM_SUFFIX}"
    stage = Path(args.tmp) / stem
    sources = sources_from_config(config, profile)
    if not sources.daily_folder:
        raise Stopped(problems=["daily-not-configured"])
    definitions = section_definitions(setup) if setup.sections else None
    digest = review_stage.sections_digest(definitions)
    discarded = None
    if not args.measure:
        stored, units, discarded = _stored(stage, period, digest, args.fresh)
        if stored is not None:
            return {"status": "ok", "stem": stem, "period": stored["period"], "continued": True,
                    "read_id": stored["read_id"], "read_at": stored["read_at"], "stage": str(stage),
                    "units": units, "report": stored["report"], "nothing_to_review": False}
        review_stage.discard(stage)
    try:
        result = _read(period, sources, day_settings(setup, config))
    except Stopped as stop:
        stop.payload.setdefault("stem", stem)
        raise
    report = result["report"]
    out: dict = {"status": "ok", "stem": stem, "period": result["period"]}
    if sources.daily_folder in result["not_read"]:
        # the listing failed for the whole run: no daily was read; a review without its dailies is never built
        if ADVICE_RAISE_LIMIT not in report["advice"]:
            report["advice"].append(ADVICE_RAISE_LIMIT)
        raise Stopped(problems=["dailies-not-read"], report=report, **out)
    # only a read period is empty or not: a stopped output never carries the flag; the access advice is the
    # listings' (kado_empty), never the empty period's
    nothing = not any(d.get("has_content") for d in result["days"])
    if definitions:
        result["sections"] = definitions
    if args.measure:
        files, manifest = review_stage.render(result, stem=stem, rule=setup.rule, sections_digest=digest)
        return {**out, "nothing_to_review": nothing, "measure": _measure(report, files, manifest)}
    out["continued"] = False
    if not nothing:
        manifest = review_stage.write(stage, result, stem=stem, rule=setup.rule, sections_digest=digest)
        out.update(read_id=manifest["read_id"], read_at=manifest["read_at"], stage=str(stage), units=_units(stage))
    out.update(report=report, nothing_to_review=nothing)
    if discarded:
        out["discarded"] = discarded
    return out


# ---------------------------------------------------------------- main

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        try:
            result = run(args)
        except Stopped as stop:
            result = {**stop.payload, "status": "stopped"}
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — the contract: class name only, exit 1
        print(type(exc).__name__, file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
