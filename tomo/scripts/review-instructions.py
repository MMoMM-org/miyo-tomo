#!/usr/bin/env python3
# review-instructions.py — Pass 2 of /review: preview the section, deliver the set resumably, drop it, name the state.
# version: 0.4.0
"""Pass 2 of /review (spec 045; PRD F5-AC1, F5-AC2, F5-AC8 to F5-AC11, F6-AC2, F6-AC4; ADR-3, ADR-6, ADR-11,
ADR-13; spec 046 ADR-12: section stops, choices).

``preview`` reads the approved document fresh through Kado, builds the plan (``lib/review_actions``) against the
target note as it is now, and prints the section as it will land, its target and place, the refusing problems and
the notices — nothing is written. ``deliver`` builds the same plan and writes, in this order, the new note
(``new-note`` mode only), ``<stem>_instructions.json`` and ``<stem>_instructions.md`` to the inbox through
``lib/staged_delivery``, then marks the document delivered with one write guarded by the ``modified`` the reader
saw; ``meta.json`` records every step so a failed delivery resumes without a duplicate, and the plan the delivery
writes (``delivered_plan``: mode, target, place, ``anchor_picked`` when ``--place-anchor`` was given — never the
heading), recorded with the first step, so a resume reports what was written rather than the plan rebuilt against
the vault now; the undone steps write the rebuilt payloads, so a resume with an undone set step whose rebuilt plan
differs from the record refuses ``replan-differs``, and a resume of a picked-anchor record without
``--place-anchor`` refuses ``anchor-needed`` with the ``headings`` of the pick (nothing written either way). A set
at the stem's path that this delivery did not write refuses ``set-exists`` while no action in it is applied; once
any is (``lib/review_state.any_applied``: an earlier run's finished or partly applied set, spec 046 ADR-12)
``deliver`` writes the new set JSON over it, guarded by the ``modified`` the probe read, and the new MD over the old
one, and keeps ``set_replaced`` in ``meta.json`` so a resume overwrites the old MD too and never rewrites the set it
landed itself. ``drop`` withdraws any delivery that began — a step done or in flight — by writing the set with an
empty ``actions`` list and an MD that names every file the delivery left (the new note among them); it reads the set
JSON first (``lib/review_state.read_set``) and refuses when Hashi marked any action ``applied`` (nothing written,
nothing changed), withdraws over an absent or unreadable set, and writes the set JSON guarded by the ``modified``
that read returned; before any step it removes the stage. It marks ``meta.json`` withdrawn last, so a drop that
failed on the MD write is listed again by the next ``/review``. ``status`` names the review's state through
``lib/review_state.stem_state`` — the function ``review-session.py start`` uses per listed document — which reads
the set JSON for an approved document and probes the target and the inbox copy for a waiting set (ADR-6).

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
    withdrawn, no set-withdrawn) a record with anchor_picked needs --place-anchor (anchor-needed, with headings),
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

The target reads are ``lib/review_target_read``'s, the flags ``lib/review_instructions_args``'s, Kado's refused
guard is read by ``lib/review_kado_conflict``.

Design notes: docs/tomo/scripts/review-instructions.md
"""
from __future__ import annotations

import argparse
import json
import posixpath
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import review_actions as ra  # noqa: E402
from lib import review_config as rc  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_instructions_args as rargs  # noqa: E402
from lib import review_kado_conflict as rkc  # noqa: E402
from lib import review_target_read as rtr  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.note_io import ConfigError, load_vault_config  # noqa: E402
from lib import review_state as rs  # noqa: E402
from lib.review_doc_read import DocRead, doc_path_of, read_document  # noqa: E402
from lib.review_vault import Stopped, Vault  # noqa: E402
from lib.staged_delivery import DeliveryStop, StagedDelivery  # noqa: E402

DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
DEFAULT_TMP = "tomo-tmp/review"
SCRIPT = "review-instructions"
NEXT = "hashi-or-by-hand"
DOC_CHANGED, KADO_WRITE_FAILED, NAME_TAKEN = "doc-changed", "kado-write-failed", "name-taken"
SET_CHANGED = "set-changed"
SET_REPLACED = "set_replaced"                           # meta.json: this delivery writes over an earlier run's applied set


class Refused(Exception):
    def __init__(self, problem: str, **extra):
        super().__init__(problem)
        self.problem, self.extra = problem, extra


class NotFound(Exception):
    def __init__(self, doc_path: Optional[str] = None):
        super().__init__("not-found")
        self.doc_path = doc_path


# ---------------------------------------------------------------- the context of one run

@dataclass
class Run:
    stem: str
    stage: Path
    meta: rdl.ReviewMeta
    setup: rc.ReviewSetup
    profile: Optional[str]
    vault: Vault
    read: DocRead
    paths: Dict[str, str]
    held: Optional[rs.SetRead]
    replaces_set: bool
    plan: ra.ReviewPlan
    problems: List[str]
    notices: List[str]
    anchor_picked: bool                        # --place-anchor was given on this call
    pick_headings: List[str]                   # what a heading pick chooses from, refusal or not
    choices: Dict[str, str]                    # --section-choice / --confirm-moved, key -> choice
    counts: Dict[str, dict]                    # the parsed document's section_counts

    @property
    def set_exists(self) -> bool:
        return self.held is not None

    @property
    def set_applied(self) -> bool:
        return self.held is not None and rs.all_applied(self.held.data)

    def output(self, *, section: bool, **extra) -> dict:
        """The plan's preview shape; ``section_md`` only when ``section`` (the preview prints it on purpose)."""
        out: Dict[str, object] = {"stem": self.stem, "doc_path": self.read.doc_path, **self.plan.preview()}
        if not section:
            del out["section_md"]
        out["problems"], out["notices"] = list(self.problems), list(self.notices)
        if self.meta.data.get("mode") == ra.NEW_NOTE and self.plan.mode != ra.NEW_NOTE:
            out["target_appeared"] = True
        out.update(self.sections(lines=section), **extra)
        return out

    def sections(self, *, lines: bool) -> dict:
        return rdl.section_report(self.plan, self.counts, self.choices, lines=lines)


def _config_and_profile(args: argparse.Namespace) -> tuple:
    try:
        config = load_vault_config(args.config)
    except ConfigError:
        config = {}
    return config, rc.load_profile(Path(args.profiles_dir), config)


def _setup(args: argparse.Namespace, kind: str) -> tuple:
    config, profile = _config_and_profile(args)
    try:
        setup = rc.review_setup(config, profile, kind, today=args.today)
    except rc.SetupInvalid as invalid:
        raise Refused("setup-invalid", errors=invalid.pointers) from None
    except ValueError:
        raise Refused("setup-invalid", errors=["/review_kind"]) from None
    if setup is None:
        raise Refused("setup-missing")
    name = config.get("profile")
    return setup, (name if isinstance(name, str) else None)


def load_run(args: argparse.Namespace) -> Run:
    """Read the document, the set at the stem's path, the target and the template; build the plan; classify its
    problems."""
    stage = Path(args.tmp) / args.stem
    meta_data = rs.read_meta(Path(args.tmp), args.stem)
    doc_path = doc_path_of(meta_data)
    if doc_path is None:
        raise NotFound()
    meta = rdl.ReviewMeta(meta_data or {})
    vault = Vault(KadoClient)
    read = read_document(vault, doc_path, meta.data)
    if read is None:
        raise NotFound(doc_path)
    front = read.parsed.frontmatter
    kind = front.get("review_kind") if isinstance(front.get("review_kind"), str) else str(meta.data.get("kind"))
    period_name = front.get("review_period") if isinstance(front.get("review_period"), str) else meta.data.get("period")
    setup, profile = _setup(args, kind)
    try:
        paths = rdl.set_paths(setup, args.stem)
    except rc.UnsafePath:
        raise Refused("inbox-not-configured") from None
    held = rs.read_set(vault, paths[rdl.SET_JSON])     # before the note, never after it (T6.2)
    target = rtr.locate(vault, setup, str(period_name or ""))
    if target is None:
        raise Refused("setup-invalid", errors=[f"/naming/calendar_patterns/{rc.GRANULARITY[setup.kind]}"])
    template = rtr.template(vault, setup, target)
    anchor, choices = getattr(args, "place_anchor", None), getattr(args, "choices", None) or {}
    plan = ra.build_review_plan(read.parsed.approved_review(), setup, target, template, anchor=anchor,
                                choices=choices, run_id=meta.run_id, generated=meta.generated)
    # a set with any action applied is written over: a partly applied set never gets stuck (spec 046 ADR-12)
    set_exists, applied_any = held is not None, held is not None and rs.any_applied(held.data)
    if set_exists and meta.started() and not meta.withdrawn() and rs.is_emptied_set(held.data):
        extra = [rdl.SET_WITHDRAWN]                                    # a drop that did not finish: never resumed over
    else:
        extra = [rdl.SET_EXISTS] if meta.second_set(set_exists, applied_any) else []
    counts = read.parsed.section_counts()
    problems, notices = rdl.classify(plan, extra, counts, choices)
    # the finished set of an earlier run is written over; the flag outlives the first write for the resume
    replaces_set = not problems and (applied_any or meta.data.get(SET_REPLACED) is True)
    return Run(args.stem, stage, meta, setup, profile, vault, read, paths, held, replaces_set, plan, problems, notices,
               anchor is not None, ra.pick_headings(setup, target, template), choices, counts)


# ---------------------------------------------------------------- preview

def preview(args: argparse.Namespace) -> dict:
    run = load_run(args)
    return run.output(section=True, status="ok", set_exists=run.set_exists, set_applied=run.set_applied,
                      resume=run.meta.started())


# ---------------------------------------------------------------- deliver

def _mark_document(run: Run, delivery: StagedDelivery) -> None:
    """The last step: one guarded write of the marked document, unless it already carries the mark."""
    if rdl.DOC_MARK in run.meta.steps_done:
        return
    language = run.setup.language
    if rd.is_delivered(run.read.text, language):
        delivery.record(rdl.DOC_MARK)
        return
    marked = rd.mark_delivered(run.read.text, language, _utc_now())
    delivery.mark_in_flight(rdl.DOC_MARK)
    try:
        run.vault.client.write_note(run.read.doc_path, marked, expected_modified=run.read.modified)
    except KadoError as exc:
        stop = delivery.fail(rdl.DOC_MARK, exc)
        if rkc.is_conflict(exc):
            stop.status, stop.reason = DOC_CHANGED, rkc.conflict_reason(exc)
        raise stop from exc
    delivery.record(rdl.DOC_MARK)


def _overwrite_step(run: Run, delivery: StagedDelivery, step: str, payload: str, set_doc: dict) -> None:
    """A set step written over the finished set of an earlier run: the set JSON under the ``modified`` the probe
    read, the MD plain; the set this delivery landed itself (the same actions, ``applied`` aside) is never
    rewritten. Recorded like an uploaded step."""
    path = run.paths[step]
    if step == rdl.SET_JSON and run.held is not None and rs.without_applied(run.held.data) == rs.without_applied(set_doc):
        delivery.record(step)
        return
    delivery.mark_in_flight(step)
    try:
        if step == rdl.SET_JSON:
            run.vault.client.write_file(path, payload.encode("utf-8"),
                                        expected_modified=run.held.modified if run.held is not None else None)
        else:
            run.vault.client.write_note(path, payload)
    except KadoError as exc:
        raise delivery.fail(step, exc) from exc
    delivery.record(step)


def deliver(args: argparse.Namespace) -> dict:
    run = load_run(args)
    refusal = (rdl.resume_refusal(run.meta, run.plan, run.problems, run.anchor_picked, bool(run.choices))
               if run.meta.started() else None)
    if refusal is not None:
        out = {"status": "refused", "stem": run.stem, "problems": [refusal], "notices": run.notices}
        if refusal == rdl.ANCHOR_NEEDED:
            out["headings"] = run.pick_headings
        return out
    if run.problems:
        return {"status": "refused", "stem": run.stem, "problems": run.problems, "notices": run.notices,
                **run.sections(lines=False)}
    paths = rdl.delivery_paths(run.paths, run.plan)
    set_doc = ra.build_review_instruction_set(run.plan, stem=run.stem, generated=run.meta.generated,
                                              profile=run.profile)
    payloads = {rdl.SET_JSON: json.dumps(set_doc, indent=2, ensure_ascii=False) + "\n",
                rdl.SET_MD: rdl.set_md(run.plan, run.meta, run.profile)}
    if rdl.NOTE in paths:
        payloads[rdl.NOTE] = run.plan.note_text or ""
    resumed = run.meta.started()
    if run.replaces_set:
        run.meta.data[SET_REPLACED] = True                     # persisted with the first step's in-flight mark
    if not resumed:                                            # the plan this run writes, persisted the same way
        run.meta.data[rdl.DELIVERED_PLAN] = rdl.plan_record(run.plan, run.setup.anchor, run.anchor_picked,
                                                            bool(run.choices))
    delivery = StagedDelivery(run.vault.client, rdl.STEPS, paths, run.meta,
                              lambda: rdl.save_meta(run.stage, run.meta), script=SCRIPT)
    try:
        for step in (rdl.NOTE, rdl.SET_JSON, rdl.SET_MD):
            if step not in paths or step in run.meta.steps_done:
                continue
            if run.replaces_set and step != rdl.NOTE:
                _overwrite_step(run, delivery, step, payloads[step], set_doc)
            else:
                delivery.deliver_step(step, payloads[step])
        _mark_document(run, delivery)
    except DeliveryStop as stop:
        if stop.status == "exists":
            return {"status": "refused", "stem": run.stem, "problems": [NAME_TAKEN], "exists_path": stop.exists_path,
                    "step": stop.step}
        stopped = {"status": "stopped", "stem": run.stem, "step": stop.step, "failed_step": run.meta.failed_step,
                   "paths": rdl.public_paths(paths), "problems": [KADO_WRITE_FAILED]}
        if stop.reason is not None:
            stopped["problems"], stopped["reason"] = [DOC_CHANGED], stop.reason
        return stopped
    out = run.output(section=False, status="resumed" if resumed else "delivered", step="",
                     paths=rdl.public_paths(paths), next=NEXT)
    return rdl.report_delivered_plan(run.meta, out) if resumed else out


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
    kind = str(meta.data.get("kind"))
    setup, profile = _setup(args, kind)
    try:
        paths = rdl.set_paths(setup, args.stem)
    except rc.UnsafePath:
        raise Refused("inbox-not-configured") from None
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
    return {"status": "withdrawn", "stem": args.stem, "paths": rdl.public_paths(paths)}


# ---------------------------------------------------------------- status

def status(args: argparse.Namespace) -> dict:
    meta = rs.read_meta(Path(args.tmp), args.stem)
    doc_path = doc_path_of(meta)
    if doc_path is None:
        raise NotFound()
    config, profile = _config_and_profile(args)
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

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
