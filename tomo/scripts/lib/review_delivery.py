# review_delivery.py — what a /review delivery needs around the plan: problem classes, meta adapter, set paths, peers.
# version: 0.1.3
"""The delivery-side helpers of ``review-instructions.py`` (spec 045; ADR-11, ADR-13).

``classify(plan)`` splits a ``ReviewPlan``'s problems into ``(problems,
notices)``: ``REFUSING`` names stop a delivery (nothing is written),
``NOTICES`` are shown and the delivery proceeds; the plan's flags
(``templater_hint``, ``variant_missing``, ``template_unmergeable``) join the
notices as names; a name in neither tuple refuses; ``ALREADY_APPLIED`` is
``drop``'s refusal (a set Hashi marked applied), listed among ``REFUSING``
so one pin covers every name. ``STEPS`` is the delivery
order ``note → set_json → set_md → doc_mark``. ``ReviewMeta`` lends the
``meta.json`` dict the attributes ``staged_delivery`` records into
(``steps_done`` shared, ``failed_step``, ``run_id``, ``generated``);
``save_meta`` persists the dict atomically. ``set_json_path`` names the set
JSON from the inbox folder and the stem alone (what ``review_state`` has
without a setup); ``set_paths`` gives both set paths through
``ReviewSetup.inbox_path``; ``template_paths`` the template's and the
variant's vault paths. ``set_md`` renders the readable
peer through ``render_md`` with the stable tomo block; ``withdrawn_set`` and
``withdrawn_md`` are what ``drop`` writes over a set Tomo already delivered:
the envelope with an empty ``actions`` list and an MD that names the files
to delete.

No Kado, no clock. Design notes: docs/tomo/scripts/lib/review_delivery.md
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_actions as ra
from lib import review_config as rc
from lib.doc_frontmatter import merge_tomo_block_into_markdown
from lib.note_io import atomic_write_text
from lib.note_meta import META_FILE
from lib.render_md import render_instructions_md
from lib.review_doc_parse import APPROVED_MISSING
from lib.staged_delivery import stable_block
from lib.wire_version import wire_schema_version

NOTE, SET_JSON, SET_MD, DOC_MARK = "note", "set_json", "set_md", "doc_mark"
STEPS = (NOTE, SET_JSON, SET_MD, DOC_MARK)
SET_EXISTS = "set-exists"
ALREADY_APPLIED = "already-applied"
TEMPLATER_HINT, VARIANT_MISSING, TEMPLATE_UNMERGEABLE = "templater_hint", "variant_missing", "template_unmergeable"
REFUSING = (ra.NOT_APPROVED, APPROVED_MISSING, ra.NOTHING_TO_DELIVER, ra.PLACE_MISSING, ra.PLACE_TOO_DEEP,
            ra.HEADING_COLLISION, SET_EXISTS, ALREADY_APPLIED)
NOTICES = (ra.HEADING_RENAMED, ra.UNLANDED_ITEMS, VARIANT_MISSING, TEMPLATER_HINT, TEMPLATE_UNMERGEABLE)
INSTRUCTIONS_SUFFIX = "_instructions"


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

    def second_set(self, set_exists: bool) -> bool:
        """Whether a delivery now would be a second set: this one is complete or withdrawn, or a set
        this delivery did not write sits at the path."""
        return DOC_MARK in self.steps_done or self.withdrawn() or (set_exists and not self.wrote_set())


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
