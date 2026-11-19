# review_instructions_run.py — the context of one review-instructions run: what it read and the plan built from it.
# version: 0.1.0
"""The ``Run`` of ``review-instructions.py`` and the builder that fills it (split out of the script at spec 046
T6.4, constitution L2 file size).

``build_run`` takes the document read the script already made and reads, in this order, the set at the stem's path,
then the target note and the template (the set before the note, so a set Hashi applies between the reads never meets
an older note: spec 046 T6.2), builds the plan and classifies its problems. ``setup_of`` and ``config_and_profile``
are the setup lookups ``drop`` and ``status`` share. ``Refused`` and ``NotFound`` are the two ways a subcommand
ends early; the script's ``main`` turns them into output.

The Kado client is the caller's: this module never constructs one.

Design notes: docs/tomo/scripts/lib/review_instructions_run.md
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from lib import review_actions as ra
from lib import review_config as rc
from lib import review_delivery as rdl
from lib import review_state as rs
from lib import review_target_read as rtr
from lib.note_io import ConfigError, load_vault_config
from lib.review_doc_read import DocRead
from lib.review_vault import Vault

SET_REPLACED = "set_replaced"                           # meta.json: this delivery writes over an earlier run's applied set


class Refused(Exception):
    def __init__(self, problem: str, **extra):
        super().__init__(problem)
        self.problem, self.extra = problem, extra


class NotFound(Exception):
    def __init__(self, doc_path: Optional[str] = None):
        super().__init__("not-found")
        self.doc_path = doc_path


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


def config_and_profile(args: argparse.Namespace) -> tuple:
    try:
        config = load_vault_config(args.config)
    except ConfigError:
        config = {}
    return config, rc.load_profile(Path(args.profiles_dir), config)


def setup_of(args: argparse.Namespace, kind: str) -> tuple:
    config, profile = config_and_profile(args)
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


def set_paths_of(setup: rc.ReviewSetup, stem: str) -> Dict[str, str]:
    try:
        return rdl.set_paths(setup, stem)
    except rc.UnsafePath:
        raise Refused("inbox-not-configured") from None


def _set_problems(held: Optional[rs.SetRead], meta: rdl.ReviewMeta) -> tuple:
    """``(extra problems, any action applied)`` of the set found at the stem's path."""
    applied_any = held is not None and rs.any_applied(held.data)
    if held is not None and meta.started() and not meta.withdrawn() and rs.is_emptied_set(held.data):
        return [rdl.SET_WITHDRAWN], applied_any                     # a drop that did not finish: never resumed over
    return ([rdl.SET_EXISTS] if meta.second_set(held is not None, applied_any) else []), applied_any


def build_run(args: argparse.Namespace, stage: Path, meta: rdl.ReviewMeta, vault: Vault, read: DocRead) -> Run:
    """Read the set at the stem's path, the target and the template; build the plan; classify its problems."""
    front = read.parsed.frontmatter
    kind = front.get("review_kind") if isinstance(front.get("review_kind"), str) else str(meta.data.get("kind"))
    period_name = front.get("review_period") if isinstance(front.get("review_period"), str) else meta.data.get("period")
    setup, profile = setup_of(args, kind)
    paths = set_paths_of(setup, args.stem)
    held = rs.read_set(vault, paths[rdl.SET_JSON])     # before the note, never after it (T6.2)
    target = rtr.locate(vault, setup, str(period_name or ""))
    if target is None:
        raise Refused("setup-invalid", errors=[f"/naming/calendar_patterns/{rc.GRANULARITY[setup.kind]}"])
    template = rtr.template(vault, setup, target)
    anchor, choices = getattr(args, "place_anchor", None), getattr(args, "choices", None) or {}
    plan = ra.build_review_plan(read.parsed.approved_review(), setup, target, template, anchor=anchor,
                                choices=choices, run_id=meta.run_id, generated=meta.generated)
    extra, applied_any = _set_problems(held, meta)     # a set with any action applied is written over (ADR-12)
    counts = read.parsed.section_counts()
    problems, notices = rdl.classify(plan, extra, counts, choices)
    # the finished set of an earlier run is written over; the flag outlives the first write for the resume
    replaces_set = not problems and (applied_any or meta.data.get(SET_REPLACED) is True)
    return Run(args.stem, stage, meta, setup, profile, vault, read, paths, held, replaces_set, plan, problems, notices,
               anchor is not None, ra.pick_headings(setup, target, template), choices, counts)
