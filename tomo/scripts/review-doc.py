#!/usr/bin/env python3
# review-doc.py — The review document of /review in the inbox: write it, parse it back, replace it.
# version: 0.5.0
"""The review document of /review: write (Pass 1), parse (Pass 2), replace (start over) (spec 045 T3.6/T3.7, PRD F4-F6).

After the period was read (``read.json``) and the model wrote its proposals
(``proposals.json``), ``write`` checks the proposals against the period,
computes the habits from the tracker values, probes the target note, renders
``<period> Review.md`` and writes it to the inbox through Kado — the only
vault write of Pass 1. The Pass 1 counts and the source-link stems per Tomo
item (``pass1_links``, nothing text-derived) go to ``meta.json`` of the
stem; ``read.json`` and ``proposals.json`` are deleted once the document is
written (ADR-9). ``parse`` reads the edited document back through Kado and
prints counts and ids only; it writes no file — the document is the source
of truth and Phase 4 reads it fresh. ``replace`` is the confirmed
start-over: it writes a new document over Tomo's own from the files
``write`` kept on ``review-exists``; ``--abort`` discards those files
instead.

Usage (cwd = instance root):
    python3 scripts/review-doc.py write --stem <period>_review --proposals <json>
        [--run-id R] [--tmp tomo-tmp/review] [--config config/vault-config.yaml]
        [--profiles-dir profiles]
    python3 scripts/review-doc.py parse --stem <period>_review [--doc-path P]
    python3 scripts/review-doc.py replace --stem <period>_review [--confirm | --abort]
        [--proposals <json>] [--run-id R]

Output: one JSON object on stdout, ASCII-escaped.
    write: status written, stem, doc_path, target, target_exists, target_found_elsewhere?,
           counts {group: n}, rejected [{group, index, reason}], calls
         | status refused, problems [proposals-invalid | doc-name-taken | review-exists | read-missing |
           read-invalid | setup-missing | setup-invalid | inbox-not-configured], errors? [pointers]
         | status stopped, problems [kado-write-failed] or error {kind kado-unreachable|kado-auth, detail}
    parse: status ok, stem, doc_path, approved, nothing_to_deliver,
           items {group: [{id?, origin tomo|user, kept, edited}]},
           counts {kept, unticked, deleted, added},
           warnings [approved-line-missing | unknown-group | item-outside-group | duplicate-group |
                     frontmatter-broken]
         | status not-found, stem, doc_path?        (no meta.json and no --doc-path, or nothing at the path)
         | status stopped, error {kind kado-unreachable|kado-auth, detail}
    replace: status needs-confirm, stem, doc_path   (neither flag: nothing written, no Kado call)
           | --confirm: as write, with status replaced instead of written
           | --abort: status aborted, stem

Rules:
    The proposals are validated before any Kado call. The target is the first
    of the period's note paths (flat, then the year subfolder) that exists;
    when neither does, one byName search finds a note of that exact name the
    user moved, and the document targets it there. ``write`` never
    overwrites: a ``<period> Review.md`` that is not Tomo's review document
    gives ``doc-name-taken``, Tomo's own review of the period gives
    ``review-exists`` with its ``doc_path``; only ``replace --confirm``
    writes over it, from the kept files, and resets ``meta.json``. A refused
    or failed write keeps ``read.json``, ``proposals.json`` and ``meta.json``
    as they were. ``replace --abort`` deletes ``read.json`` and
    ``proposals.json`` and touches neither the document nor ``meta.json``.
    ``parse`` reads the document at ``--doc-path`` or at the ``doc_path`` of
    ``meta.json`` through ``lib/review_doc_read`` (shared with
    ``review-instructions.py``) and writes nothing; ``edited`` per Tomo item
    is whether its link stems differ from ``pass1_links`` (an id the map
    lacks is never edited). Nothing of a proposal, a daily or the document
    reaches stdout or stderr.

Exit codes:
    0 — output usable (every status)
    1 — unexpected exception; stderr carries the exception class name only
    2 — bad invocation (unknown subcommand or flag, missing argument, a --stem that is
        empty, ".", "..", or carries / or \\ — lib/review_state.safe_stem)

Design notes: docs/tomo/scripts/review-doc.md
"""
from __future__ import annotations

import argparse
import json
import posixpath
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import review_config as rc  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from lib import review_habits as rh  # noqa: E402
from lib.kado_client import KadoAuthError, KadoClient, KadoError, KadoNotFoundError  # noqa: E402
from lib.note_io import ConfigError, atomic_write_text, load_vault_config  # noqa: E402
from lib.period import Period, render_name  # noqa: E402
from lib.review_doc_read import doc_path_of, read_document  # noqa: E402
from lib.review_state import META_FILE, read_meta, safe_stem  # noqa: E402
from lib.review_vault import Stopped, Vault  # noqa: E402
from lib.run_id import generate as generate_run_id  # noqa: E402

DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
DEFAULT_TMP = "tomo-tmp/review"
READ_FILE = "read.json"
PROPOSALS_FILE = "proposals.json"


class Refused(Exception):
    """``write`` cannot go on; ``problem`` names why, ``extra`` joins the output."""

    def __init__(self, problem: str, **extra):
        super().__init__(problem)
        self.problem = problem
        self.extra = extra


# ---------------------------------------------------------------- Kado probes

def _probe(vault: Vault, path: str) -> bool:
    """Whether ``path`` exists; ``Stopped`` when Kado cannot answer."""
    try:
        vault.client.read_frontmatter(path)
    except KadoNotFoundError:
        return False
    except KadoAuthError as exc:
        raise Stopped("kado-auth", str(exc)) from None
    except KadoError as exc:
        raise Stopped("kado-unreachable", str(exc)) from None
    return True


def find_target(vault: Vault, candidates: List[str], name: str) -> Tuple[str, bool, Optional[str]]:
    """``(target, exists, found_elsewhere)``: the first candidate that exists, else a moved note of that name."""
    for path in candidates:
        if _probe(vault, path):
            return path, True, None
    try:
        hits = vault.client.search_by_name(f"{name}.md")
    except KadoAuthError as exc:
        raise Stopped("kado-auth", str(exc)) from None
    except KadoError as exc:
        raise Stopped("kado-unreachable", str(exc)) from None
    moved = sorted(str(h.get("path")) for h in hits
                   if isinstance(h, dict) and posixpath.basename(str(h.get("path") or "")) == f"{name}.md")
    if moved:
        return moved[0], True, moved[0]
    return candidates[0], False, None


ABSENT, NOT_TOMO, TOMO_REVIEW = "absent", "not-tomo", "tomo-review"


def doc_state(vault: Vault, doc_path: str) -> str:
    """What sits at ``doc_path``: ``ABSENT``, ``NOT_TOMO`` (a file that is not Tomo's review) or ``TOMO_REVIEW``."""
    try:
        content = vault.client.read_frontmatter(doc_path).get("content")
    except KadoNotFoundError:
        return ABSENT
    except KadoAuthError as exc:
        raise Stopped("kado-auth", str(exc)) from None
    except KadoError as exc:
        raise Stopped("kado-unreachable", str(exc)) from None
    tomo = content.get("tomo") if isinstance(content, dict) else None
    return TOMO_REVIEW if isinstance(tomo, dict) and tomo.get("doc_type") == rd.DOC_TYPE else NOT_TOMO


# ---------------------------------------------------------------- write

def _load_read(stage: Path) -> dict:
    try:
        data = json.loads((stage / READ_FILE).read_text(encoding="utf-8"))
    except OSError:
        raise Refused("read-missing") from None
    except ValueError:
        raise Refused("read-invalid") from None
    if not isinstance(data, dict):
        raise Refused("read-invalid")
    return data


def _setup(args: argparse.Namespace, kind: str, today: date) -> Tuple[dict, rc.ReviewSetup]:
    try:
        config = load_vault_config(args.config)
    except ConfigError:
        config = {}
    profile = rc.load_profile(Path(args.profiles_dir), config)
    try:
        setup = rc.review_setup(config, profile, kind, today=today)
    except rc.SetupInvalid as invalid:
        raise Refused("setup-invalid", errors=invalid.pointers) from None
    except ValueError:
        raise Refused("read-invalid") from None
    if setup is None:
        raise Refused("setup-missing")
    return config, setup


def _write_meta(stage: Path, inp: rd.DocInput, counts: dict, doc_path: str, text: str) -> None:
    meta = {
        "stem": inp.stem, "period": inp.period_name, "kind": inp.kind, "doc_path": doc_path,
        "target": inp.target, "target_exists": inp.target_exists,
        "mode": "insert" if inp.target_exists else "new-note", "run_id": inp.run_id,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pass1_counts": counts, "pass1_links": rdp.link_stems(text),
        "steps_done": [], "failed_step": "", "withdrawn": False,
    }
    atomic_write_text(stage / META_FILE, json.dumps(meta, ensure_ascii=True, indent=2) + "\n")


def _resolve(args: argparse.Namespace, read: dict) -> Tuple[dict, rc.ReviewSetup, Period, str]:
    """``(config, setup, period, doc_path)`` of the stem's ``read.json``, without a Kado call."""
    kind = str((read.get("period") or {}).get("kind"))
    config, setup = _setup(args, kind, args.today)
    try:
        period = rd.period_of(read, setup.rule)
    except rd.ReadInvalid:
        raise Refused("read-invalid") from None
    try:
        doc_path = setup.inbox_path(rd.doc_name(period.name))
    except rc.UnsafePath:
        raise Refused("inbox-not-configured") from None
    return config, setup, period, doc_path


def render_and_write(args: argparse.Namespace, *, allow_overwrite_review: bool) -> dict:
    """Check, render and write the document; over Tomo's own review only when the flag says so."""
    stage = Path(args.tmp) / args.stem
    read = _load_read(stage)
    proposals_path = Path(args.proposals) if args.proposals else stage / PROPOSALS_FILE
    proposals, problems = rd.load_proposals(proposals_path)
    if proposals is None:
        raise Refused("proposals-invalid", errors=problems)
    config, setup, period, doc_path = _resolve(args, read)

    accepted, rejected = rd.check_items(proposals, read)
    habits = rh.habits(rh.tracker_defs(config), read.get("days") or [], period.days(), setup.language)
    accepted[rd.HABITS] = [{"text": item["text"], "links": []} for item in habits]

    vault = Vault(KadoClient)
    target, exists, elsewhere = find_target(vault, period.note_paths(setup.folder, setup.format),
                                            render_name(period, setup.format))
    result = {"stem": args.stem, "doc_path": doc_path, "target": target, "target_exists": exists}
    if elsewhere:
        result["target_found_elsewhere"] = elsewhere
    state = doc_state(vault, doc_path)
    if state == NOT_TOMO:
        return {"status": "refused", **result, "problems": ["doc-name-taken"]}
    if state == TOMO_REVIEW and not allow_overwrite_review:
        return {"status": "refused", **result, "problems": ["review-exists"]}

    inp = rd.DocInput(
        period_name=period.name, kind=period.kind, language=setup.language, stem=args.stem,
        run_id=args.run_id or generate_run_id(), target=target, target_exists=exists,
        target_found_elsewhere=elsewhere, anchor=setup.anchor, placement=setup.placement,
        not_read=[str(p) for p in read.get("not_read") or []],
        partly_read=[str(d.get("date")) for d in read.get("days") or [] if d.get("partly_read")],
        month_groups=rd.WEEKLY_ONLY in accepted, groups=accepted,
    )
    text, counts = rd.render_document(inp)
    try:
        vault.client.write_note(doc_path, text)
    except KadoError as exc:
        return {"status": "stopped", "stem": args.stem, "target": target, "target_exists": exists,
                "problems": ["kado-write-failed"], "error": {"kind": type(exc).__name__},
                "calls": vault.client.call_count}
    _write_meta(stage, inp, counts, doc_path, text)
    for path in (stage / READ_FILE, proposals_path):
        path.unlink(missing_ok=True)
    return {"status": "written", **result, "counts": counts, "rejected": rejected,
            "calls": vault.client.call_count}


def write_document(args: argparse.Namespace) -> dict:
    """The ``write`` subcommand: never over Tomo's own review document."""
    return render_and_write(args, allow_overwrite_review=False)


# ---------------------------------------------------------------- parse

def parse_document(args: argparse.Namespace) -> dict:
    """The ``parse`` subcommand: the edited document → counts and ids on stdout, nothing written."""
    meta = read_meta(Path(args.tmp), args.stem) or {}
    doc_path = doc_path_of(meta, args.doc_path)
    if doc_path is None:
        return {"status": "not-found", "stem": args.stem}
    read = read_document(Vault(KadoClient), doc_path, meta)
    if read is None:
        return {"status": "not-found", "stem": args.stem, "doc_path": doc_path}
    parsed = read.parsed
    return {"status": "ok", "stem": args.stem, "doc_path": doc_path, "approved": parsed.approved,
            "nothing_to_deliver": parsed.nothing_to_deliver(), "items": parsed.public_items(),
            "counts": parsed.counts(), "warnings": parsed.warnings}


# ---------------------------------------------------------------- replace

def replace_document(args: argparse.Namespace) -> dict:
    """The ``replace`` subcommand: ask (``needs-confirm``), start over (``--confirm``) or give up (``--abort``)."""
    stage = Path(args.tmp) / args.stem
    if args.abort:
        for path in (stage / READ_FILE, stage / PROPOSALS_FILE):
            path.unlink(missing_ok=True)
        return {"status": "aborted", "stem": args.stem}
    if not args.confirm:
        _, _, _, doc_path = _resolve(args, _load_read(stage))
        return {"status": "needs-confirm", "stem": args.stem, "doc_path": doc_path}
    result = render_and_write(args, allow_overwrite_review=True)
    if result.get("status") == "written":
        result["status"] = "replaced"
    return result


# ---------------------------------------------------------------- main

def _date_arg(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from None


def _stem_arg(text: str) -> str:
    if not safe_stem(text):
        raise argparse.ArgumentTypeError("expected a plain stem like 2026-W13_review (not empty, . or .., no / or \\)")
    return text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="The review document of /review: write it to the inbox.")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR), help="framework profiles directory")
    p.add_argument("--tmp", default=DEFAULT_TMP, help="Where tomo-tmp/review/<stem>/ lives")
    sub = p.add_subparsers(dest="command", required=True)

    w = sub.add_parser("write", help="Check the proposals, render the document and write it to the inbox")
    w.add_argument("--stem", required=True, type=_stem_arg, help="<period>_review, the tomo-tmp/review/ folder")
    w.add_argument("--proposals", required=True, help="The model's proposals.json")
    w.add_argument("--run-id", help="Run id for the document's tomo: block (default: a fresh one)")
    w.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)

    r = sub.add_parser("parse", help="Read the edited document back: counts and ids on stdout, nothing written")
    r.add_argument("--stem", required=True, type=_stem_arg, help="<period>_review, the tomo-tmp/review/ folder")
    r.add_argument("--doc-path", help="The document's vault path (default: doc_path of meta.json)")

    x = sub.add_parser("replace", help="Start over: write a new document over Tomo's own (asks without --confirm)")
    x.add_argument("--stem", required=True, type=_stem_arg, help="<period>_review, the tomo-tmp/review/ folder")
    choice = x.add_mutually_exclusive_group()
    choice.add_argument("--confirm", action="store_true", help="The user confirmed: replace the document")
    choice.add_argument("--abort", action="store_true", help="The user declined: delete read.json and proposals.json")
    x.add_argument("--proposals", help="The kept proposals.json (default: the stage copy)")
    x.add_argument("--run-id", help="Run id for the new document's tomo: block (default: a fresh one)")
    x.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        try:
            commands = {"write": write_document, "parse": parse_document, "replace": replace_document}
            result = commands[args.command](args)
        except Refused as refused:
            result = {"status": "refused", "stem": args.stem, "problems": [refused.problem], **refused.extra}
        except Stopped as stop:
            result = {"status": "stopped", "stem": args.stem, "error": {"kind": stop.kind, "detail": stop.detail}}
    except Exception as exc:  # noqa: BLE001 — the contract: class name only, exit 1
        print(type(exc).__name__, file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
