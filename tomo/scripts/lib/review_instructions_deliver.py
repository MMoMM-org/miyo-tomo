# review_instructions_deliver.py — the write side of review-instructions deliver: steps, resume, document mark.
# version: 0.1.0
"""Delivery of one ``Run`` (split out of ``review-instructions.py`` at spec 046 T6.4, constitution L2 file size).

``deliver_run`` decides between the resume with stored payloads, a refusal and a fresh delivery, then
``write_steps`` uploads the undone steps in order through ``lib/staged_delivery`` and marks the document last.
A set written over an earlier run's applied set goes through ``_overwrite_step``. The Kado client is the run's
(``run.vault.client``); nothing here constructs one.

Design notes: docs/tomo/scripts/lib/review_instructions_deliver.md
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, Optional

from lib import review_actions as ra
from lib import review_delivery as rdl
from lib import review_doc as rd
from lib import review_kado_conflict as rkc
from lib import review_state as rs
from lib.kado_client import KadoError
from lib.review_doc_parse import APPROVED_MISSING
from lib.review_instructions_run import SET_REPLACED, Run
from lib.staged_delivery import DeliveryStop, StagedDelivery

SCRIPT = "review-instructions"
NEXT = "hashi-or-by-hand"
DOC_CHANGED, KADO_WRITE_FAILED, NAME_TAKEN = "doc-changed", "kado-write-failed", "name-taken"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    path = delivery.targets[step]
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


def _stop_output(run: Run, stop: DeliveryStop, paths: Dict[str, str]) -> dict:
    if stop.status == "exists":
        if not run.meta.started():
            rdl.remove_payloads(run.stage)                 # nothing began: a fresh delivery builds them again
        return {"status": "refused", "stem": run.stem, "problems": [NAME_TAKEN], "exists_path": stop.exists_path,
                "step": stop.step}
    stopped = {"status": "stopped", "stem": run.stem, "step": stop.step, "failed_step": run.meta.failed_step,
               "paths": rdl.public_paths(paths), "problems": [KADO_WRITE_FAILED]}
    if stop.reason is not None:
        stopped["problems"], stopped["reason"] = [DOC_CHANGED], stop.reason
    return stopped


def write_steps(run: Run, paths: Dict[str, str], payloads: Dict[str, str], set_doc: dict, replaces_set: bool,
                resumed: bool) -> dict:
    """Upload the undone steps of ``payloads`` in order, then mark the document; the output of the run."""
    delivery = StagedDelivery(run.vault.client, rdl.STEPS, paths, run.meta,
                              lambda: rdl.save_meta(run.stage, run.meta), script=SCRIPT)
    try:
        for step in (rdl.NOTE, rdl.SET_JSON, rdl.SET_MD):
            if step not in paths or step in run.meta.steps_done:
                continue
            if replaces_set and step != rdl.NOTE:
                _overwrite_step(run, delivery, step, payloads[step], set_doc)
            else:
                delivery.deliver_step(step, payloads[step])
        _mark_document(run, delivery)
    except DeliveryStop as stop:
        return _stop_output(run, stop, paths)
    rdl.remove_payloads(run.stage)
    out = run.output(section=False, status="resumed" if resumed else "delivered", step="",
                     paths=rdl.public_paths(paths), next=NEXT)
    return rdl.report_delivered_plan(run.meta, out) if resumed else out


def _approval_problem(run: Run) -> Optional[str]:
    """Why the document no longer approves what was stored: its Approved line unreadable or unticked."""
    review = run.read.parsed.approved_review()
    if APPROVED_MISSING in review["warnings"]:
        return APPROVED_MISSING
    return None if review["approved"] else ra.NOT_APPROVED


def _resume_stored(run: Run, paths: Dict[str, str], payloads: Dict[str, str]) -> dict:
    """An open delivery resumed with the payloads its first attempt stored: the rebuilt plan's problems and the
    resume refusals do not apply, the stored texts are uploaded unchanged."""
    approval = _approval_problem(run)
    if approval is not None:
        return {"status": "refused", "stem": run.stem, "problems": [approval], "notices": []}
    replaces_set = run.meta.data.get(SET_REPLACED) is True or (run.held is not None and rs.any_applied(run.held.data))
    run.problems, run.notices = [], []
    return write_steps(run, paths, payloads, json.loads(payloads[rdl.SET_JSON]), replaces_set, resumed=True)


def _refusal_output(run: Run) -> Optional[dict]:
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
    return None


def deliver_run(run: Run) -> dict:
    """The output of ``deliver`` for a loaded run."""
    stored = rdl.read_payloads(run.stage, run.meta) if rdl.delivery_open(run.meta, run.problems) else None
    if stored is not None:
        return _resume_stored(run, *stored)
    refused = _refusal_output(run)
    if refused is not None:
        return refused
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
    if not resumed:                                            # the plan and payloads this run writes, stored the same way
        run.meta.data[rdl.DELIVERED_PLAN] = rdl.plan_record(run.plan, run.setup.anchor, run.anchor_picked,
                                                            bool(run.choices))
        rdl.save_payloads(run.stage, paths, payloads)
    return write_steps(run, paths, payloads, set_doc, run.replaces_set, resumed)
