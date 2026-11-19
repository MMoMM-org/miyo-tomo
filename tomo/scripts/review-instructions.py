#!/usr/bin/env python3
# review-instructions.py — Pass 2 of /review: preview the section, deliver the set resumably, drop it, name the state.
# version: 0.6.0
"""Pass 2 of /review: preview the section, deliver the set resumably, drop it, name the state.

``preview`` builds the plan from the approved document and the target note as they are now and prints it; nothing is
written. ``deliver`` writes the new note (``new-note`` mode only), ``<stem>_instructions.json`` and
``<stem>_instructions.md`` to the inbox, then marks the document delivered; ``meta.json`` records every step, so a
failed delivery resumes without a duplicate. ``drop`` withdraws a begun delivery. ``status`` names the review's
state.

Usage (cwd = instance root):
    python3 scripts/review-instructions.py preview --stem <period>_review [--place-anchor H] [CHOICES]
    python3 scripts/review-instructions.py deliver --stem <period>_review [--place-anchor H] [CHOICES]
        CHOICES: [--section-choice <key>=skip|review ...] [--confirm-moved <key> ...] — answers to section stops
    python3 scripts/review-instructions.py drop    --stem <period>_review
    python3 scripts/review-instructions.py status  --stem <period>_review
        [--config config/vault-config.yaml] [--profiles-dir profiles] [--tmp tomo-tmp/review]

Output: one JSON object on stdout, ASCII-escaped.
    preview: status ok, stem, doc_path, mode insert|replace|new-note, target, target_moved?, duplicates?,
             target_appeared?, place {anchor, placement, level}, section_md, escaped_lines, templater_hint,
             variant_missing?, template_unmergeable?, unlanded?, problems [refusing], notices, headings?,
             set_exists, set_applied, resume; mapped: SECTIONS = sections [{key, mode, placement, notices, scope_level?, stop?,
             choices?, block_at?, lines (preview only)}], dropped [{key, added}], empty [key], choices_invalid?
    deliver: status delivered|resumed, stem, step "", paths {set_json, set_md, note?}, next hashi-or-by-hand,
             mode, target, place, notices, target_appeared?, SECTIONS
           | status refused, stem, problems [<refusing>|set-exists|set-withdrawn|replan-differs|anchor-needed|
             choices-needed|name-taken], exists_path?, step?, headings? (anchor-needed only), SECTIONS?
           | status stopped, stem, step, failed_step, paths, problems [doc-changed|kado-write-failed],
             reason? open-unsaved|changed-since-read|unknown (doc-changed only)
    drop:    status withdrawn, stem, paths {set_json, set_md, note?} | status dropped, stem, removed
           | status refused, stem, problems [already-applied]
           | status stopped, stem, problems [set-changed|kado-write-failed], error {kind}
    status:  state (one of lib/review_state.STATES, or null for a withdrawn review), stem
    every subcommand: status not-found, stem, doc_path? | status refused, stem, problems [setup-missing|
             setup-invalid|inbox-not-configured], errors? | status stopped, stem, error {kind, detail}

Rules: a refusing problem means nothing is written; a second set for the stem is refused (set-exists) unless
    an action of the set at the path is applied — then deliver writes over it, the set JSON under the modified
    the probe read (Kado's CONFLICT there is kado-write-failed, resumable); an emptied set on a begun delivery is
    a drop that did not finish (set-withdrawn, before set-exists) — drop completes it, deliver never resumes over
    it; done steps are skipped on resume, a step in flight is compared or uploaded; the document mark is last — a
    refused guard (Kado's CONFLICT, or KadoConcurrencyError) is doc-changed with failed_step doc_mark, any other
    write failure kado-write-failed, both resumable; reason names why: open-unsaved (Kado's dirty-editor
    message), changed-since-read (the guard's message, or KadoConcurrencyError), unknown — never Kado's message;
    a resumed output reports the recorded delivered_plan (mode, target, place; target_appeared against the
    recorded mode), the rebuilt plan without a record; on a delivery still open (begun, doc_mark undone, not
    withdrawn, no set-withdrawn, no set-exists) whose stage holds payloads.json the undone steps upload the stored
    payloads and nothing of the rebuilt plan refuses (output problems [], notices []) except an Approved box
    unticked since (not-approved / approved-line-missing); deliver and status first remove payloads.json of a
    finished or withdrawn record; without payloads.json a record with anchor_picked needs --place-anchor (anchor-needed, with headings),
    one with choices_given needs choices (choices-needed), then a record with an undone step of its own (note for
    a new-note record, set_json, set_md) refuses replan-differs when the rebuilt mode, target, place.placement,
    place.level, place.anchor (when recorded) or sections (keys and modes, when recorded) differ — before the
    rebuilt plan's own problems; a finished or withdrawn delivery keeps set-exists or set-withdrawn.
    A stop of a section whose block holds lines refuses until a choice answers it; a choice no plan took refuses
    choice-invalid; a malformed or doubled choice exits 2; a plan without an action is nothing-to-deliver.
    drop refuses already-applied on any applied action (no partial withdrawal); its set read answers absent only
    on NOT_FOUND, any other Kado failure stops the run; a refused guard on the set write is set-changed.
    Nothing of the document or a note reaches stdout except preview's section_md and sections.lines, a moved
    block's sections.block_at.heading and the headings list; stderr names problem classes only.

Exit codes:
    0 — output usable (every status)
    1 — unexpected exception; stderr carries the exception class name only
    2 — bad invocation (unknown subcommand or flag, missing argument, unsafe --stem)

Design notes: docs/tomo/scripts/review-instructions.md
"""
from __future__ import annotations

import argparse
import json
import posixpath
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import review_delivery as rdl  # noqa: E402
from lib import review_instructions_args as rargs  # noqa: E402
from lib import review_instructions_deliver as rid  # noqa: E402
from lib import review_instructions_run as rir  # noqa: E402
from lib import review_kado_conflict as rkc  # noqa: E402
from lib import review_state as rs  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.review_doc_read import doc_path_of, read_document  # noqa: E402
from lib.review_instructions_run import NotFound, Refused, Run  # noqa: E402
from lib.review_vault import Stopped, Vault  # noqa: E402
from lib import review_config as rc  # noqa: E402

DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
DEFAULT_TMP = "tomo-tmp/review"
KADO_WRITE_FAILED, SET_CHANGED = rid.KADO_WRITE_FAILED, "set-changed"


def load_run(args: argparse.Namespace) -> Run:
    """Read the document, then everything ``lib/review_instructions_run.build_run`` reads; build the plan."""
    meta_data = rs.read_meta(Path(args.tmp), args.stem)
    doc_path = doc_path_of(meta_data)
    if doc_path is None:
        raise NotFound()
    meta = rdl.ReviewMeta(meta_data or {})
    vault = Vault(KadoClient)
    read = read_document(vault, doc_path, meta.data)
    if read is None:
        raise NotFound(doc_path)
    return rir.build_run(args, Path(args.tmp) / args.stem, meta, vault, read)


# ---------------------------------------------------------------- preview

def preview(args: argparse.Namespace) -> dict:
    run = load_run(args)
    return run.output(section=True, status="ok", set_exists=run.set_exists, set_applied=run.set_applied,
                      resume=run.meta.started())


# ---------------------------------------------------------------- deliver

def deliver(args: argparse.Namespace) -> dict:
    rdl.clear_closed_payloads(Path(args.tmp) / args.stem, rs.read_meta(Path(args.tmp), args.stem))
    return rid.deliver_run(load_run(args))


# ---------------------------------------------------------------- drop

def _remove_stage(stage: Path) -> bool:
    if not stage.is_dir():
        return False
    shutil.rmtree(stage)
    return True


def drop(args: argparse.Namespace) -> dict:
    stage = Path(args.tmp) / args.stem
    meta_data = rs.read_meta(Path(args.tmp), args.stem)
    meta = rdl.ReviewMeta(meta_data) if meta_data is not None else None
    if meta is None or not meta.started():
        return {"status": "dropped", "stem": args.stem, "removed": _remove_stage(stage)}
    setup, profile = rir.setup_of(args, str(meta.data.get("kind")))
    paths = rir.set_paths_of(setup, args.stem)
    if rdl.NOTE in meta.steps_done or meta.failed_step == rdl.NOTE:
        target = str(meta.data.get("target") or "")
        paths[rdl.NOTE] = setup.inbox_path(posixpath.basename(target))
    files = [paths[k] for k in (rdl.SET_JSON, rdl.SET_MD, rdl.NOTE) if k in paths]
    vault = Vault(KadoClient)
    held = rs.read_set(vault, paths[rdl.SET_JSON])
    if held is not None and rs.any_applied(held.data):
        return {"status": "refused", "stem": args.stem, "problems": [rdl.ALREADY_APPLIED]}
    set_bytes = (json.dumps(rdl.withdrawn_set(args.stem, meta, profile), indent=2,
                            ensure_ascii=False) + "\n").encode("utf-8")
    try:
        vault.client.write_file(paths[rdl.SET_JSON], set_bytes,
                                expected_modified=held.modified if held is not None else None)
    except KadoError as exc:
        return {"status": "stopped", "stem": args.stem,
                "problems": [SET_CHANGED if rkc.is_conflict(exc) else KADO_WRITE_FAILED],
                "error": {"kind": type(exc).__name__}}
    try:
        vault.client.write_note(paths[rdl.SET_MD], rdl.withdrawn_md(args.stem, meta, profile, files))
    except KadoError as exc:
        return {"status": "stopped", "stem": args.stem, "problems": [KADO_WRITE_FAILED],
                "error": {"kind": type(exc).__name__}}
    meta.data["withdrawn"] = True
    meta.failed_step = ""
    rdl.save_meta(stage, meta)
    rdl.remove_payloads(stage)
    return {"status": "withdrawn", "stem": args.stem, "paths": rdl.public_paths(paths)}


# ---------------------------------------------------------------- status

def status(args: argparse.Namespace) -> dict:
    meta = rs.read_meta(Path(args.tmp), args.stem)
    rdl.clear_closed_payloads(Path(args.tmp) / args.stem, meta)
    doc_path = doc_path_of(meta)
    if doc_path is None:
        raise NotFound()
    config, profile = rir.config_and_profile(args)
    inbox = rc.inbox_folder(config, profile)
    if inbox is None:
        raise Refused("inbox-not-configured")
    vault = Vault(KadoClient)
    front = vault.frontmatter(doc_path)
    if front is None:
        raise NotFound(doc_path)
    try:
        state = rs.stem_state(vault, front, meta, args.stem, inbox)
    except rc.UnsafePath:
        raise Refused("inbox-not-configured") from None
    return {"state": state, "stem": args.stem}


# ---------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pass 2 of /review: preview, deliver, drop, status.")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR), help="framework profiles directory")
    p.add_argument("--tmp", default=DEFAULT_TMP, help="Where tomo-tmp/review/<stem>/ lives")
    p.add_argument("--today", type=date.fromisoformat, default=date.today(), help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)
    for name, text in (("preview", "Show the section as it will land; nothing written"),
                       ("deliver", "Write the set (and the new note), then mark the document"),
                       ("drop", "Withdraw a delivered set or remove the stage"),
                       ("status", "Name the review's state")):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--stem", required=True, type=rargs.stem_arg,
                         help="<period>_review, the tomo-tmp/review/ folder")
        if name in ("preview", "deliver"):
            rargs.add_plan_flags(cmd)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        try:
            result = {"preview": preview, "deliver": deliver, "drop": drop, "status": status}[args.command](args)
        except NotFound as missing:
            result = {"status": "not-found", "stem": args.stem}
            if missing.doc_path:
                result["doc_path"] = missing.doc_path
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
