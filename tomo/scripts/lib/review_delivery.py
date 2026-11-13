# review_delivery.py — what a /review delivery needs around the plan: problem classes, meta adapter, set paths, peers.
# version: 0.2.0
"""The delivery-side helpers of ``review-instructions.py`` (spec 045; ADR-11, ADR-13).

``classify(plan)`` splits a ``ReviewPlan``'s problems into ``(problems,
notices)``: ``REFUSING`` names stop a delivery (nothing is written),
``NOTICES`` are shown and the delivery proceeds; the plan's flags
(``templater_hint``, ``variant_missing``, ``template_unmergeable``) join the
notices as names; a name in neither tuple refuses; ``ALREADY_APPLIED`` is
``drop``'s refusal (a set Hashi marked applied) and ``SET_WITHDRAWN``
``deliver``'s refusal of an emptied set on a begun stem (a drop that did not
finish), ``REPLAN_DIFFERS`` ``deliver``'s refusal of a resume whose re-plan
contradicts the recorded ``delivered_plan`` while a set step is undone, and
``ANCHOR_NEEDED`` its refusal of a resume without ``--place-anchor`` of a
delivery begun with one — all listed among ``REFUSING`` so one pin covers
every name.
``STEPS`` is the delivery
order ``note → set_json → set_md → doc_mark``. ``ReviewMeta`` lends the
``meta.json`` dict the attributes ``staged_delivery`` records into
(``steps_done`` shared, ``failed_step``, ``run_id``, ``generated``);
``second_set(set_exists, set_applied)`` says whether a delivery now would
be a second set — a complete or withdrawn delivery always, a set this
delivery did not write unless every action in it is applied (a rerun
writes over the finished set of an earlier run); ``save_meta`` persists
the dict atomically. ``set_json_path`` names the set
JSON from the inbox folder and the stem alone (what ``review_state`` has
without a setup); ``set_paths`` gives both set paths through
``ReviewSetup.inbox_path``; ``delivery_paths`` adds the new note's path when the plan
creates it and ``public_paths`` keeps the three a delivery output reports; ``template_paths`` the template's and the
variant's vault paths. ``set_md`` renders the readable
peer through ``render_md`` with the stable tomo block; ``withdrawn_set`` and
``withdrawn_md`` are what ``drop`` writes over a set Tomo already delivered:
the envelope with an empty ``actions`` list and an MD that names the files
to delete.

``tool_error_payload``, ``tool_error_code``, ``is_conflict`` and
``conflict_reason`` read a ``KadoError`` the delivery caught (Kado's refused
guard, by code and by message); ``plan_record``, ``replan_differs``,
``resume_refusal`` and ``report_delivered_plan`` are the ``delivered_plan``
record of ``meta.json`` and what a resumed run does with it (#258). They take
the plan, the meta and the problems they need, never the script's ``Run``.

No Kado call, no clock. Design notes: docs/tomo/scripts/lib/review_delivery.md
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_actions as ra
from lib import review_config as rc
from lib.doc_frontmatter import merge_tomo_block_into_markdown
from lib.kado_client import KadoConcurrencyError, KadoError, KadoToolError
from lib.note_io import atomic_write_text
from lib.note_meta import META_FILE
from lib.render_md import render_instructions_md
from lib.review_doc_parse import APPROVED_MISSING
from lib.staged_delivery import stable_block
from lib.wire_version import wire_schema_version

NOTE, SET_JSON, SET_MD, DOC_MARK = "note", "set_json", "set_md", "doc_mark"
STEPS = (NOTE, SET_JSON, SET_MD, DOC_MARK)
SET_EXISTS = "set-exists"
SET_WITHDRAWN = "set-withdrawn"
ALREADY_APPLIED = "already-applied"
REPLAN_DIFFERS = "replan-differs"
ANCHOR_NEEDED = "anchor-needed"
TEMPLATER_HINT, VARIANT_MISSING, TEMPLATE_UNMERGEABLE = "templater_hint", "variant_missing", "template_unmergeable"
REFUSING = (ra.NOT_APPROVED, APPROVED_MISSING, ra.NOTHING_TO_DELIVER, ra.PLACE_MISSING, ra.PLACE_TOO_DEEP,
            ra.HEADING_COLLISION, SET_EXISTS, SET_WITHDRAWN, ALREADY_APPLIED, REPLAN_DIFFERS, ANCHOR_NEEDED)
NOTICES = (ra.HEADING_RENAMED, ra.UNLANDED_ITEMS, VARIANT_MISSING, TEMPLATER_HINT, TEMPLATE_UNMERGEABLE)
INSTRUCTIONS_SUFFIX = "_instructions"
DELIVERED_PLAN = "delivered_plan"                       # meta.json: the mode, target and place the delivery writes
ANCHOR_PICKED = "anchor_picked"                         # delivered_plan: --place-anchor was given (never the heading)
CONFLICT = "CONFLICT"                                   # Kado's error code for a refused guard or a dirty editor
TOOL_ERROR_PREFIX = "returned an error: "               # KadoClient's prefix before the MCP error payload
OPEN_UNSAVED, CHANGED_SINCE_READ, UNKNOWN_CONFLICT = "open-unsaved", "changed-since-read", "unknown"
EDITOR_PHRASE = "open in the editor with unsaved changes"   # Kado's dirty-editor refusal (note-adapter conflictEditorError)
GUARD_PHRASE = "updated in the background"                  # Kado's write guard (concurrency-guard)


# --- the classification --------------------------------------------------------------

def classify(plan: ra.ReviewPlan, extra: Sequence[str] = ()) -> Tuple[List[str], List[str]]:
    """``(refusing problems, notices)`` of ``plan`` plus ``extra`` names, in order; an unknown name refuses."""
    problems: List[str] = []
    notices: List[str] = []
    for name in [*plan.problems, *extra]:
        (notices if name in NOTICES else problems).append(name)
    for name, flag in ((TEMPLATER_HINT, plan.templater_hint), (VARIANT_MISSING, plan.variant_missing),
                       (TEMPLATE_UNMERGEABLE, plan.template_unmergeable)):
        if flag and name not in notices:
            notices.append(name)
    return problems, notices


# --- meta.json ------------------------------------------------------------------------

class ReviewMeta:
    """The ``meta.json`` dict with the attributes the staged loop records; the dict stays the record."""

    def __init__(self, data: dict):
        self.data = data
        if not isinstance(data.get("steps_done"), list):
            data["steps_done"] = []
        if not isinstance(data.get("failed_step"), str):
            data["failed_step"] = ""

    @property
    def steps_done(self) -> List[str]:
        return self.data["steps_done"]

    @property
    def failed_step(self) -> str:
        return self.data["failed_step"]

    @failed_step.setter
    def failed_step(self, value: str) -> None:
        self.data["failed_step"] = value

    @property
    def run_id(self) -> str:
        return str(self.data.get("run_id") or "")

    @property
    def generated(self) -> str:
        return str(self.data.get("generated") or "")

    def started(self) -> bool:
        """Whether a delivery began: a step done or one in flight."""
        return bool(self.steps_done) or bool(self.failed_step)

    def wrote_set(self) -> bool:
        """Whether this delivery uploaded, or may have uploaded, the set JSON."""
        return SET_JSON in self.steps_done or self.failed_step == SET_JSON

    def withdrawn(self) -> bool:
        return self.data.get("withdrawn") is True

    def second_set(self, set_exists: bool, set_applied: bool = False) -> bool:
        """Whether a delivery now would be a second set: this one is complete or withdrawn, or a set
        this delivery did not write sits at the path — unless every action in it is applied
        (``set_applied``: the finished set of an earlier run, written over)."""
        if DOC_MARK in self.steps_done or self.withdrawn():
            return True
        return set_exists and not set_applied and not self.wrote_set()


def save_meta(stage: Path, meta: ReviewMeta) -> None:
    atomic_write_text(Path(stage) / META_FILE, json.dumps(meta.data, ensure_ascii=True, indent=2) + "\n")


# --- paths ----------------------------------------------------------------------------

def set_json_path(inbox: str, stem: str) -> str:
    """``<inbox>/<stem>_instructions.json``; ``UnsafePath`` from ``review_config.inbox_path``."""
    return rc.inbox_path(inbox, f"{stem}{INSTRUCTIONS_SUFFIX}.json")


def set_paths(setup: rc.ReviewSetup, stem: str) -> Dict[str, str]:
    """``{set_json, set_md}`` of ``stem`` in the inbox; ``UnsafePath`` from ``inbox_path``."""
    return {SET_JSON: set_json_path(setup.inbox, stem),
            SET_MD: setup.inbox_path(f"{stem}{INSTRUCTIONS_SUFFIX}.md")}


def delivery_paths(paths: Dict[str, str], plan: ra.ReviewPlan) -> Dict[str, str]:
    """``paths`` plus the new note's path when the plan creates the note."""
    out = dict(paths)
    if plan.mode == ra.NEW_NOTE and plan.note_path:
        out[NOTE] = plan.note_path
    return out


def public_paths(paths: Dict[str, str]) -> Dict[str, str]:
    """The paths a delivery output reports: the set pair and the note."""
    return {key: paths[key] for key in (SET_JSON, SET_MD, NOTE) if key in paths}


def template_paths(setup: rc.ReviewSetup) -> Tuple[Optional[str], Optional[str]]:
    """``(template path, variant path)`` under ``templates.base_path``; None where the setup names none."""
    def under_base(name: Optional[str]) -> Optional[str]:
        if name is None:
            return None
        return f"{setup.template_base.rstrip('/')}/{name}" if setup.template_base else name
    return under_base(setup.template), under_base(setup.template_variant)


# --- the peers ------------------------------------------------------------------------

def set_md(plan: ra.ReviewPlan, meta: ReviewMeta, profile: Optional[str]) -> str:
    """The readable instructions of ``plan`` with the stable tomo block."""
    md = render_instructions_md(plan.actions, {"generated": meta.generated, "profile": profile},
                                {"templater_hint": plan.templater_hint})
    return merge_tomo_block_into_markdown(md, stable_block("instructions", "pending-apply", meta))


def withdrawn_set(stem: str, meta: ReviewMeta, profile: Optional[str]) -> dict:
    """The set envelope with nothing to apply: what ``drop`` writes over a delivered set."""
    return {"schema_version": wire_schema_version(ra.WIRE_SCHEMA), "type": ra.WIRE_TYPE,
            "generated": meta.generated, "profile": profile, "md_peer": f"{stem}{INSTRUCTIONS_SUFFIX}",
            "actions": []}


def withdrawn_md(stem: str, meta: ReviewMeta, profile: Optional[str], files: Sequence[str]) -> str:
    """The MD peer of a withdrawn set: says so and names every file the delivery left."""
    md = render_instructions_md([], {"generated": meta.generated, "profile": profile}, {"templater_hint": False})
    lines = ["## Withdrawn — delete these files", "",
             f"The review `{stem}` was dropped before it was applied. This set holds no action; "
             "Hashi applies nothing from it. Delete these files:", ""]
    lines += [f"- `{path}`" for path in files]
    text = md.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n"
    return merge_tomo_block_into_markdown(text, stable_block("instructions", "pending-apply", meta))


# --- Kado's refused guard -------------------------------------------------------------

def tool_error_payload(exc: KadoToolError) -> Optional[dict]:
    """The MCP error payload after the client's prefix as a dict; None when it is not a JSON object."""
    text = str(exc)
    payload = text.split(TOOL_ERROR_PREFIX, 1)[1] if TOOL_ERROR_PREFIX in text else text
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def tool_error_code(exc: KadoToolError) -> Optional[str]:
    """The ``code`` of the MCP error payload after the client's prefix; the exact ``"code":"CONFLICT"``
    token when the payload is not JSON; None when neither names a code."""
    data = tool_error_payload(exc)
    if data is None:
        return CONFLICT if f'"code":"{CONFLICT}"' in str(exc) else None
    code = data.get("code")
    return code if isinstance(code, str) else None


def is_conflict(exc: KadoError) -> bool:
    """Kado refused the guard: the client's concurrency error, or a tool error whose code is CONFLICT."""
    return isinstance(exc, KadoConcurrencyError) or (
        isinstance(exc, KadoToolError) and tool_error_code(exc) == CONFLICT)


def conflict_reason(exc: KadoError) -> str:
    """Why Kado refused the guard, as a name only: ``open-unsaved`` for the dirty-editor message,
    ``changed-since-read`` for the write guard's message and for ``KadoConcurrencyError``, else ``unknown``."""
    if isinstance(exc, KadoConcurrencyError):
        return CHANGED_SINCE_READ
    data = tool_error_payload(exc) if isinstance(exc, KadoToolError) else None
    message = data.get("message") if data is not None else None
    message = message if isinstance(message, str) else ""
    if EDITOR_PHRASE in message:
        return OPEN_UNSAVED
    if GUARD_PHRASE in message:
        return CHANGED_SINCE_READ
    return UNKNOWN_CONFLICT


# --- the delivered plan and the resume (#258) -----------------------------------------

def plan_record(plan: ra.ReviewPlan, configured_anchor: Optional[str], anchor_picked: bool) -> dict:
    """``mode``, ``target`` and ``place`` of the plan about to be written, for ``meta.json``: the anchor only
    when it is the configured one (config text) — a heading of the note's own stays out of ``tomo-tmp``."""
    place = dict(plan.place)
    if place.get("anchor") != configured_anchor:
        place["anchor"] = None
    record = {"mode": plan.mode, "target": plan.target, "place": place}
    if anchor_picked:
        record[ANCHOR_PICKED] = True
    return record


def replan_differs(plan: ra.ReviewPlan, record: dict) -> bool:
    """Whether ``plan`` built now would write something else than ``record`` says the delivery wrote: ``mode``,
    ``target``, ``place.placement`` and ``place.level``, plus ``place.anchor`` when the record holds one."""
    place, recorded = plan.place, record.get("place")
    recorded = recorded if isinstance(recorded, dict) else {}
    keys = ["placement", "level"] + (["anchor"] if recorded.get("anchor") is not None else [])
    return (record.get("mode") != plan.mode or record.get("target") != plan.target
            or any(recorded.get(key) != place.get(key) for key in keys))


def resume_refusal(meta: ReviewMeta, plan: ra.ReviewPlan, problems: Sequence[str], anchor_picked: bool) -> Optional[str]:
    """Why a resumed run must not write: ``anchor-needed`` when the record says a heading was picked and none was
    given now; ``replan-differs`` when a step of the recorded plan is undone and the plan built now differs from
    the record. None without a record, with only ``doc_mark`` undone, or when the plans agree — and None for a
    delivery nothing resumes (the mark done, withdrawn, or a drop that did not finish): it keeps its own refusal."""
    record = meta.data.get(DELIVERED_PLAN)
    closed = DOC_MARK in meta.steps_done or meta.withdrawn() or SET_WITHDRAWN in problems
    if not isinstance(record, dict) or closed:
        return None
    if record.get(ANCHOR_PICKED) is True and not anchor_picked:
        return ANCHOR_NEEDED
    steps = ([NOTE] if record.get("mode") == ra.NEW_NOTE else []) + [SET_JSON, SET_MD]
    if all(step in meta.steps_done for step in steps):
        return None
    return REPLAN_DIFFERS if replan_differs(plan, record) else None


def report_delivered_plan(meta: ReviewMeta, out: dict) -> dict:
    """A resumed output reports the plan recorded when the delivery began — ``mode``, ``target``, ``place`` —
    and ``target_appeared`` against that mode; an anchor the record could not hold stays the rebuilt plan's;
    without a record (a delivery begun before it existed) the rebuilt plan stands."""
    record = meta.data.get(DELIVERED_PLAN)
    if not isinstance(record, dict):
        return out
    out.update({key: record[key] for key in ("mode", "target") if key in record})
    if isinstance(record.get("place"), dict):
        place = dict(record["place"])
        if place.get("anchor") is None:
            place["anchor"] = out["place"].get("anchor")
        out["place"] = place
    out.pop("target_appeared", None)
    if meta.data.get("mode") == ra.NEW_NOTE and record.get("mode") != ra.NEW_NOTE:
        out["target_appeared"] = True
    return out
