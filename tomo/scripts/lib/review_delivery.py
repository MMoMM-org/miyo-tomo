# review_delivery.py — what a /review delivery needs around the plan: problem classes, meta adapter, set paths, peers.
# version: 0.5.0
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
every name. Spec 046 T5.5: the section stops, ``choice-invalid`` and
``choices-needed`` refuse, the section notices are notices
(``review_section_report.names``); a plan with no refusing problem and no action
is ``nothing-to-deliver``; ``section_report`` gives the fields of those names.
``STEPS`` is the delivery
order ``note → set_json → set_md → doc_mark``. ``ReviewMeta`` lends the
``meta.json`` dict the attributes ``staged_delivery`` records into
(``steps_done`` shared, ``failed_step``, ``run_id``, ``generated``);
``second_set(set_exists, any_applied)`` says whether a delivery now would
be a second set — a complete or withdrawn delivery always, a set this
delivery did not write unless any action in it is applied (a rerun
writes over the finished or partly applied set of an earlier run); ``save_meta`` persists
the dict atomically. ``set_json_path`` names the set
JSON from the inbox folder and the stem alone (what ``review_state`` has
without a setup); ``set_paths`` gives both set paths through
``ReviewSetup.inbox_path``; ``delivery_paths`` adds the new note's path when the plan
creates it and ``public_paths`` keeps the three a delivery output reports; ``template_paths`` the template's and the
variant's vault paths. ``set_md`` renders the readable
peer through ``render_md`` with the stable tomo block, whose ``sources``
(``peer_sources``) are the review document and, for a new note, its inbox
copy — never ``plan.target``: Hashi's cleanup trashes every listed path;
``withdrawn_set`` and ``withdrawn_md`` are what ``drop`` writes over a set Tomo
already delivered: the envelope with an empty ``actions`` list and an MD that
names the files to delete, with ``sources: []``.

``plan_record``, ``replan_differs``,
``resume_refusal`` and ``report_delivered_plan`` are the ``delivered_plan``
record of ``meta.json`` and what a resumed run does with it (#258). They take
the plan, the meta and the problems they need, never the script's ``Run``.
Reading a ``KadoError`` the delivery caught is ``review_kado_conflict``'s (T6.2).

No Kado call, no clock. Design notes: docs/tomo/scripts/lib/review_delivery.md
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_actions as ra
from lib import review_config as rc
from lib import review_section_plan as rsp
from lib import review_section_report as rsr
from lib.doc_frontmatter import merge_tomo_block_into_markdown
from lib.note_io import atomic_write_text
from lib.note_meta import META_FILE
from lib.render_md import render_instructions_md
from lib.review_doc_parse import APPROVED_MISSING, SECTION_CHECKBOX_MISSING
from lib.staged_delivery import stable_block
from lib.wire_version import wire_schema_version

NOTE, SET_JSON, SET_MD, DOC_MARK = "note", "set_json", "set_md", "doc_mark"
STEPS = (NOTE, SET_JSON, SET_MD, DOC_MARK)
SET_EXISTS = "set-exists"
SET_WITHDRAWN = "set-withdrawn"
ALREADY_APPLIED = "already-applied"
REPLAN_DIFFERS = "replan-differs"
ANCHOR_NEEDED = "anchor-needed"
CHOICES_NEEDED, CHOICE_INVALID = "choices-needed", rsr.CHOICE_INVALID
SECTION_DROPPED, SECTION_EMPTY = rsr.SECTION_DROPPED, rsr.SECTION_EMPTY
TEMPLATER_HINT, VARIANT_MISSING, TEMPLATE_UNMERGEABLE = "templater_hint", "variant_missing", "template_unmergeable"
REFUSING = (ra.NOT_APPROVED, APPROVED_MISSING, SECTION_CHECKBOX_MISSING, ra.NOTHING_TO_DELIVER, ra.PLACE_MISSING,
            ra.PLACE_TOO_DEEP, ra.HEADING_COLLISION, SET_EXISTS, SET_WITHDRAWN, ALREADY_APPLIED, REPLAN_DIFFERS,
            ANCHOR_NEEDED, *rsp.STOPS.values(), CHOICE_INVALID, CHOICES_NEEDED)
NOTICES = (ra.HEADING_RENAMED, ra.UNLANDED_ITEMS, VARIANT_MISSING, TEMPLATER_HINT, TEMPLATE_UNMERGEABLE,
           rsp.BLOCK_REPLACED, rsp.BLOCK_MOVED_CONFIRMED, rsp.REVIEW_SECTION_KEPT, SECTION_DROPPED, SECTION_EMPTY)
INSTRUCTIONS_SUFFIX = "_instructions"
DELIVERED_PLAN = "delivered_plan"                       # meta.json: the mode, target and place the delivery writes
ANCHOR_PICKED = "anchor_picked"                         # delivered_plan: --place-anchor was given (never the heading)
SECTIONS, CHOICES_GIVEN = "sections", "choices_given"   # delivered_plan: section keys + modes; choices were given


# --- the classification --------------------------------------------------------------

def classify(plan: ra.ReviewPlan, extra: Sequence[str] = (), counts: Optional[Dict[str, dict]] = None,
             choices: Optional[Dict[str, str]] = None) -> Tuple[List[str], List[str]]:
    """``(refusing problems, notices)`` of ``plan`` plus ``extra`` names, in order, each once; an unknown name
    refuses; the parsed document's section ``counts`` and the user's ``choices`` add theirs."""
    problems: List[str] = []
    notices: List[str] = []
    section_names = rsr.names(plan.sections, counts or {}, choices or {})
    for name in [*plan.problems, *extra, *section_names, *plan.notices]:
        listed = notices if name in NOTICES else problems
        if name not in listed:
            listed.append(name)
    if not problems and not plan.actions:
        problems.append(ra.NOTHING_TO_DELIVER)              # every section left out, nothing for "Tomo Review"
    for name, flag in ((TEMPLATER_HINT, plan.templater_hint), (VARIANT_MISSING, plan.variant_missing),
                       (TEMPLATE_UNMERGEABLE, plan.template_unmergeable)):
        if flag and name not in notices:
            notices.append(name)
    return problems, notices


def section_report(plan: ra.ReviewPlan, counts: Dict[str, dict], choices: Dict[str, str], *, lines: bool) -> dict:
    """The output fields of a mapped plan (``review_section_report.fields``)."""
    return rsr.fields(plan.sections, counts, choices, lines=lines)


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

    @property
    def doc_path(self) -> Optional[str]:
        path = self.data.get("doc_path")
        return path if isinstance(path, str) and path else None

    def started(self) -> bool:
        """Whether a delivery began: a step done or one in flight."""
        return bool(self.steps_done) or bool(self.failed_step)

    def wrote_set(self) -> bool:
        """Whether this delivery uploaded, or may have uploaded, the set JSON."""
        return SET_JSON in self.steps_done or self.failed_step == SET_JSON

    def withdrawn(self) -> bool:
        return self.data.get("withdrawn") is True

    def second_set(self, set_exists: bool, any_applied: bool = False) -> bool:
        """Whether a delivery now would be a second set: this one is complete or withdrawn, or a set
        this delivery did not write sits at the path — unless any action in it is applied
        (``any_applied``: the finished or partly applied set of an earlier run, written over)."""
        if DOC_MARK in self.steps_done or self.withdrawn():
            return True
        return set_exists and not any_applied and not self.wrote_set()


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

def peer_sources(plan: ra.ReviewPlan, meta: ReviewMeta) -> List[Dict[str, str]]:
    """What Hashi's cleanup may trash after a full apply: the review document, then the new note's inbox
    copy; never the review target."""
    paths = [meta.doc_path, plan.note_path if plan.mode == ra.NEW_NOTE else None]
    return [{"path": path} for path in paths if path and path != plan.target]


def set_md(plan: ra.ReviewPlan, meta: ReviewMeta, profile: Optional[str]) -> str:
    """The readable instructions of ``plan`` with the stable tomo block and its ``sources``."""
    md = render_instructions_md(plan.actions, {"generated": meta.generated, "profile": profile},
                                {"templater_hint": plan.templater_hint})
    block = stable_block("instructions", "pending-apply", meta, sources=peer_sources(plan, meta))
    return merge_tomo_block_into_markdown(md, block)


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
    return merge_tomo_block_into_markdown(text, stable_block("instructions", "pending-apply", meta, sources=[]))


# --- the delivered plan and the resume (#258) -----------------------------------------

def plan_record(plan: ra.ReviewPlan, configured_anchor: Optional[str], anchor_picked: bool,
                choices_given: bool = False) -> dict:
    """``mode``, ``target`` and ``place`` of the plan about to be written, for ``meta.json``: the anchor only
    when it is the configured one (config text) — a heading of the note's own stays out of ``tomo-tmp``; with
    mapped sections also ``sections`` (keys and enums) and ``choices_given``."""
    place = dict(plan.place)
    if place.get("anchor") != configured_anchor:
        place["anchor"] = None
    record = {"mode": plan.mode, "target": plan.target, "place": place}
    if anchor_picked:
        record[ANCHOR_PICKED] = True
    if plan.sections:
        record[SECTIONS], record[CHOICES_GIVEN] = rsr.record(plan.sections), choices_given
    return record


def replan_differs(plan: ra.ReviewPlan, record: dict) -> bool:
    """Whether ``plan`` built now would write something else than ``record`` says the delivery wrote: ``mode``,
    ``target``, ``place.placement`` and ``place.level``, plus ``place.anchor`` when the record holds one, and the
    sections' keys and modes when it holds them."""
    place, recorded = plan.place, record.get("place")
    recorded = recorded if isinstance(recorded, dict) else {}
    keys = ["placement", "level"] + (["anchor"] if recorded.get("anchor") is not None else [])
    return (record.get("mode") != plan.mode or record.get("target") != plan.target
            or any(recorded.get(key) != place.get(key) for key in keys)
            or (SECTIONS in record and record[SECTIONS] != rsr.record(plan.sections)))


def resume_refusal(meta: ReviewMeta, plan: ra.ReviewPlan, problems: Sequence[str], anchor_picked: bool,
                   choices_given: bool = False) -> Optional[str]:
    """Why a resumed run must not write: ``anchor-needed`` when the record says a heading was picked and none was
    given now; ``choices-needed`` when it says choices were given and none are now; ``replan-differs`` when a
    step of the recorded plan is undone and the plan built now differs from the record. None without a record, with only ``doc_mark`` undone, or when the plans agree — and None for a
    delivery nothing resumes (the mark done, withdrawn, or a drop that did not finish): it keeps its own refusal."""
    record = meta.data.get(DELIVERED_PLAN)
    closed = DOC_MARK in meta.steps_done or meta.withdrawn() or SET_WITHDRAWN in problems
    if not isinstance(record, dict) or closed:
        return None
    if record.get(ANCHOR_PICKED) is True and not anchor_picked:
        return ANCHOR_NEEDED
    if record.get(CHOICES_GIVEN) is True and not choices_given:
        return CHOICES_NEEDED
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
