#!/usr/bin/env python3
# review-session.py — Deterministic session start and setup preview of /review.
# version: 0.6.5
"""Session start and setup preview of /review: the request, the open reviews, the setup.

/review reads a finished week or month and proposes a review section for its
periodic note. Before the first review of a kind the user confirms where those
notes live, how they are named, how weeks are counted, which template they
use, where the review goes and which daily sections count (spec 045 F1). This
script makes every start the same: ``start`` parses the argument under the
configured week rule and name formats, reports the setup per kind and lists
the open review documents of the inbox with their state (F2); ``match`` lists
the folder, matches the existing names against the proposed format, infers
the week rule from the notes' own dates (never from the Obsidian plugin
configuration), classifies the template — the mapping's, the ``--template``
one, or lists the candidates of the templates folder when neither names one —
and proposes heading, place, daily sections and language, marking a place
whose anchor it cannot propose unless ``--anchor`` names it; ``setup-input``
turns the confirmed proposal into the input of ``vault-config-writer.py
review``. Nothing is saved by any of them.

Usage (cwd = instance root):
    python3 scripts/review-session.py start --args='<raw $ARGUMENTS>'
        [--tmp tomo-tmp/review] [--today YYYY-MM-DD]
    python3 scripts/review-session.py match --kind week|month
        [--folder P] [--format F] [--first-day D --min-days N] [--template T|none] [--anchor H]
        [--template-frontmatter-ok T] [--today YYYY-MM-DD]
    python3 scripts/review-session.py setup-input --kind week|month --confirmed <json>
        [--output tomo-tmp/review/setup-<kind>.json] [--today YYYY-MM-DD]

Output: one JSON object on stdout, ASCII-escaped.
    start: status ok|stopped,
           request {kind week|month, period, year_inferred, source arg|at|default, start, end}
             | request {kind setup} + current {week, month: values | null | {invalid [pointers]}}
             | request null + request_withheld open-reviews (a blank argument while open_reviews
               is non-empty: no new period starts until the user names one)
             | error {kind invalid-period|unfinished-period|not-periodic-note|unknown-argument,
                      expected, example, last_finished?},
           setup {week present|missing, month present|missing},
           open_reviews [{period, kind, doc_path, stem, state}] ordered by period,
           skipped_review_docs [{doc_path, reason}], problems [inbox-not-configured]?,
           notices [applied-not-recorded]? (the applied flag could not be written),
           error {kind kado-unreachable|kado-auth, detail} when stopped
    match: status ok|stopped, kind,
           proposal {folder, format, first_day, min_days, template, template_kind
                     plain|templater|missing|unreadable, template_frontmatter true|false|null,
                     heading, place {anchor, placement}, own_sections, daily_sections, language},
           evidence {matched, unmatched, week_rule given|inferred|ambiguous|default,
                     notes_checked, folder_listing found|kado-none, format_problems,
                     template_headings},
           daily_path_fix {configured, found} (only when the other spelling exists),
           template_candidates [names below templates.base_path, without .md, only those holding the kind
             word (week/woche, month/monat, case-insensitive; lib/review_templates.py)] (only when neither
             the mapping nor --template names a template and --template is not none;
             [] without a base_path or for kado-none),
           needs_anchor true, anchor_candidates [headings of the two most recent periodic notes]
             (only when no anchor could be proposed: no --anchor, no configured anchor, no
             template heading),
           needs_template_ok true (only when template_frontmatter is false and
             --template-frontmatter-ok does not name the resolved template),
           hints [plain sentences for the skill],
           error {kind kado-unreachable|kado-auth|unsafe-format, detail?}
    setup-input: status ok, input_path, kind
               | status invalid, errors [json pointers], problems [{pointer, kind, example?}]

Rules:
    ``start`` parses the argument before any Kado call; an argument error
    returns with an empty listing and no call spent. The open reviews are the
    inbox documents with ``tomo.doc_type=review`` (one byFrontmatter query, one
    frontmatter read per hit), found also when renamed; their state comes from
    lib/review_state.stem_state — the function ``review-instructions.py status``
    uses for one stem — which reads ``<inbox>/<stem>_instructions.json`` for an
    approved document and probes the target and the inbox copy for a waiting
    set (ADR-6); a refused or failed probe stops the run, never reads as absent.
    A withdrawn review is not listed; an ``applied`` review is listed once —
    ``start`` writes ``applied_reported`` into its ``meta.json`` after listing it.
    A stage that cannot be written (``OSError``) keeps the listing and ``status
    ok`` and adds ``notices: [applied-not-recorded]``; the review is offered
    again on the next start.
    The listing is ordered by period start under the configured week rule and
    name formats (lib/review_config.configured_formats), the pair the argument
    was parsed with.
    A blank argument (whitespace only counts as blank) with a non-empty listing
    withholds the request: ``request`` is null and ``request_withheld`` says
    ``open-reviews``, whatever the states listed. A kind word (``month``,
    ``week``), a named period, an ``@`` note and ``setup`` keep their request
    beside the listing; a ``stopped`` output keeps the parsed request too.
    Flags win over the config, the config over the inference, the inference
    over the defaults (ISO weeks ``GGGG-[W]WW``, months ``YYYY-MM``).
    ``--first-day`` and ``--min-days`` come together or not at all (exit 2).
    ``evidence.week_rule`` is ``given`` when ``--first-day`` was passed (the user's
    answer stands; the skill asks on ``ambiguous`` only), else what the notes showed.
    A ``found`` listing without a name that parses adds the "no notes to
    compare" hint; a ``kado-none`` listing gets the access hint instead.
    Up to 8 recent weekly notes are read for their dates (lib/week_rule_inference);
    a dated note is matched only when the proposal's format and rule reproduce
    its name on its start date. Two notes with the same name (folder and year
    subfolder) are both checked and both listed. No note text reaches stdout
    or stderr; the headings in ``anchor_candidates`` are the one note-derived
    field, by design.
    The template is ``--template`` (with or without ``.md``), else
    ``templates.mapping.<granularity>``; with neither, the templates folder is
    listed once (lib/review_templates) and nothing is read. ``--template none``
    is the user's "no template" answer: no mapping lookup, no listing, the
    plain note. The anchor is ``--anchor`` (trimmed), else the configured one,
    else proposed from the template's headings; with none of them,
    ``needs_anchor`` is set and two periodic notes are read for candidates.
    ``template_frontmatter`` is whether the template text read opens a
    frontmatter block at its first line and closes it (lib/review_templates
    .template_has_frontmatter, the rule of Pass 2's merge); null when no text
    was read (none, the candidate list, missing, unreadable). A false value
    sets ``needs_template_ok`` — the skill asks once whether to use the
    template as it is — unless ``--template-frontmatter-ok`` (the ``--template``
    syntax) names the resolved template: the answer is bound to the template
    it was given for, so a corrected template without a block is asked about
    again. The field stays false under the flag; only the question key goes.
    The skill repeats every answer on every rerun of ``match``.

Exit codes:
    0 — output usable (every status, every error object)
    1 — unexpected exception; stderr carries the exception class name only
    2 — bad invocation (unknown subcommand or flag, bad value, one week flag without
        the other, an unsafe --template or --template-frontmatter-ok name, a blank or
        multi-line --anchor, unreadable --confirmed file)

Design notes: docs/tomo/scripts/review-session.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import review_config as rc  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402
from lib.kado_client import KadoClient  # noqa: E402
from lib.note_io import ConfigError, atomic_write_text, load_vault_config  # noqa: E402
from lib.period import DAY_NAMES, ISO, KINDS, MONTH, SETUP, RequestError, parse_args  # noqa: E402
from lib.review_match import configured_rule, propose  # noqa: E402
from lib.review_state import APPLIED, APPLIED_REPORTED, OpenReview, open_reviews, read_meta  # noqa: E402
from lib.review_templates import anchor_text, template_choice  # noqa: E402
from lib.review_vault import Stopped, Vault  # noqa: E402

DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
DEFAULT_TMP = "tomo-tmp/review"
APPLIED_NOT_RECORDED = "applied-not-recorded"
REQUEST_WITHHELD = "open-reviews"


# ---------------------------------------------------------------- config

def load_config(path: str) -> dict:
    try:
        return load_vault_config(path)
    except ConfigError:
        return {}


# ---------------------------------------------------------------- start

def start(args: argparse.Namespace) -> dict:
    config = load_config(args.config)
    profile = rc.load_profile(Path(args.profiles_dir), config)
    rule = configured_rule(config) or ISO
    formats = rc.configured_formats(config)
    result: dict = {
        "status": "ok",
        "setup": {kind: "present" if rc.setup_present(config, kind) else "missing" for kind in KINDS},
        "open_reviews": [],
        "skipped_review_docs": [],
    }
    parsed = parse_args(args.args, today=args.today, rule=rule, formats=formats)
    if isinstance(parsed, RequestError):
        result["error"] = parsed.to_dict()
        return result
    result["request"] = rc.request_dict(parsed)
    if parsed.kind == SETUP:
        result["current"] = {kind: rc.current_setup(config, profile, kind, args.today) for kind in KINDS}

    inbox = rc.inbox_folder(config, profile)
    if inbox is None:
        result["problems"] = ["inbox-not-configured"]
        return result
    try:
        vault = Vault(KadoClient)
        docs = vault.review_documents(inbox)
        reviews, skipped = open_reviews(docs, Path(args.tmp), vault, inbox, rule=rule, formats=formats)
    except Stopped as stop:
        result["status"] = "stopped"
        result["error"] = {"kind": stop.kind, "detail": stop.detail}
        return result
    except rc.UnsafePath:
        result["problems"] = ["inbox-not-configured"]
        return result
    result["open_reviews"] = [review.to_dict() for review in reviews]
    result["skipped_review_docs"] = skipped
    if not _record_applied(Path(args.tmp), reviews):
        result["notices"] = [APPLIED_NOT_RECORDED]
    if reviews and not args.args.strip():
        # a bare /review names no period: while a review is listed there is no new request
        result["request"] = None
        result["request_withheld"] = REQUEST_WITHHELD
    return result


def _record_applied(root: Path, reviews: List[OpenReview]) -> bool:
    """Mark the meta of every review listed as ``applied``: the listing offers it once. False when
    a stage could not be written; the review is offered again on the next start."""
    recorded = True
    for review in reviews:
        if review.state != APPLIED:
            continue
        meta = read_meta(root, review.stem) or {"stem": review.stem}
        meta[APPLIED_REPORTED] = True
        stage = root / review.stem
        try:
            stage.mkdir(parents=True, exist_ok=True)
            rdl.save_meta(stage, rdl.ReviewMeta(meta))
        except OSError:
            recorded = False
    return recorded


# ---------------------------------------------------------------- the proposal

def match(args: argparse.Namespace) -> dict:
    config = load_config(args.config)
    profile = rc.load_profile(Path(args.profiles_dir), config)
    return propose(lambda: Vault(KadoClient), config, profile, args)



# ---------------------------------------------------------------- setup-input

_INPUT_KEYS = ("folder", "format", "first_day", "min_days", "template", "template_variant", "heading",
               "place", "own_sections", "daily_sections", "skip_sections", "task_notes",
               "max_chars_per_day", "language")


def writer_input(confirmed: dict, kind: str) -> dict:
    """The writer's shape from a confirmed proposal: the preview-only keys dropped."""
    data: dict = {"kind": confirmed.get("kind", kind)}
    for key in _INPUT_KEYS:
        if key in confirmed:
            data[key] = confirmed[key]
    if kind == MONTH:
        for key in ("first_day", "min_days"):
            if data.get(key) is None:
                data.pop(key, None)
    fix = confirmed.get("daily_path_fix")
    if isinstance(fix, dict):
        fix = fix.get("found")
    if fix is not None:
        data["daily_path_fix"] = fix
    return data


def setup_input(args: argparse.Namespace) -> dict:
    kind = args.kind
    try:
        confirmed = json.loads(Path(args.confirmed).read_text(encoding="utf-8"))
    except ValueError:
        confirmed = None
    if not isinstance(confirmed, dict):
        return {"status": "invalid", "kind": kind, "errors": ["/"],
                "problems": [{"pointer": "/", "kind": "not-an-object"}]}
    data = writer_input(confirmed, kind)
    if data["kind"] != kind:
        return {"status": "invalid", "kind": kind, "errors": ["/kind"],
                "problems": [{"pointer": "/kind", "kind": "kind-mismatch"}]}
    problems = rc.input_problems(data, today=args.today)
    if problems:
        return {"status": "invalid", "kind": kind, "errors": [p.pointer for p in problems],
                "problems": [p.to_dict() for p in problems]}
    output = Path(args.output or f"tomo-tmp/review/setup-{kind}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(data, ensure_ascii=True, indent=2) + "\n")
    return {"status": "ok", "kind": kind, "input_path": str(output)}


# ---------------------------------------------------------------- main

def _date_arg(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from None


def _min_days_arg(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected an integer 1..7") from None
    if not 1 <= value <= 7:
        raise argparse.ArgumentTypeError("expected an integer 1..7")
    return value


def _typed(convert):
    """An argparse type over a lib rule that raises ``ValueError`` with the expectation as its message."""
    def typed(text: str):
        try:
            return convert(text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"expected {exc}") from None
    return typed


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Session start and setup preview for /review.")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR), help="framework profiles directory")
    sub = p.add_subparsers(dest="command", required=True)

    st = sub.add_parser("start", help="The request, the setup per kind and the open reviews")
    st.add_argument("--args", required=True, help="$ARGUMENTS verbatim (use --args=<text>)")
    st.add_argument("--tmp", default=DEFAULT_TMP, help="Where tomo-tmp/review/<stem>/meta.json lives")
    st.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)

    m = sub.add_parser("match", help="Preview the setup of one period kind against the existing notes")
    m.add_argument("--kind", required=True, choices=KINDS)
    m.add_argument("--folder", help="Folder of the periodic notes (default: config, then profile)")
    m.add_argument("--format", help="Name format (default: config, then inferred)")
    m.add_argument("--first-day", choices=DAY_NAMES,
                   help="First day of the week (default: config, then inferred; needs --min-days)")
    m.add_argument("--min-days", type=_min_days_arg,
                   help="Days week 1 must hold in the new year (default: config, then inferred; needs --first-day)")
    m.add_argument("--template", type=_typed(template_choice),
                   help="The chosen template, a name below templates.base_path, or none for no template "
                        "(default: the mapping; with neither, the candidates are listed)")
    m.add_argument("--anchor", type=_typed(anchor_text),
                   help="The chosen heading for the review section's place (default: the configured anchor, "
                        "then the template's headings; with none, needs_anchor is set)")
    m.add_argument("--template-frontmatter-ok", type=_typed(template_choice),
                   help="The template the user agreed to use without a frontmatter block (the --template syntax); "
                        "needs_template_ok is then not set for it")
    m.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)

    s = sub.add_parser("setup-input", help="Build the vault-config-writer review input from a confirmed proposal")
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--confirmed", required=True, help="JSON file with the confirmed proposal")
    s.add_argument("--output", help="Where to write the writer input (default: tomo-tmp/review/setup-<kind>.json)")
    s.add_argument("--today", type=_date_arg, default=date.today(), help=argparse.SUPPRESS)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "match" and (args.first_day is None) != (args.min_days is None):
        parser.error("--first-day and --min-days are given together or not at all")
    try:
        if args.command == "setup-input" and not Path(args.confirmed).is_file():
            print("review-session: --confirmed file not readable (FileNotFoundError)", file=sys.stderr)
            return 2
        result = {"start": start, "match": match, "setup-input": setup_input}[args.command](args)
    except Exception as exc:  # noqa: BLE001 — the contract: class name only, exit 1
        print(type(exc).__name__, file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
