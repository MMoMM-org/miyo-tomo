#!/usr/bin/env python3
# review-instructions.py — Pass 2 of /review: preview the section, deliver the set resumably, drop it, name the state.
# version: 0.2.1
"""Pass 2 of /review (spec 045; PRD F5-AC1, F5-AC2, F5-AC8 to F5-AC11, F6-AC2, F6-AC4; ADR-3, ADR-6, ADR-11,
ADR-13).

``preview`` reads the approved document fresh through Kado, builds the plan
(``lib/review_actions``) against the target note as it is now, and prints the
section as it will land, its target and place, the refusing problems and the
notices — nothing is written. ``deliver`` builds the same plan and writes, in
this order, the new note (``new-note`` mode only), ``<stem>_instructions.json``
and ``<stem>_instructions.md`` to the inbox through ``lib/staged_delivery``,
then marks the document delivered with one write guarded by the ``modified``
the reader saw; ``meta.json`` records every step so a failed delivery resumes
without a duplicate. ``drop`` withdraws any delivery that began — a step
done or in flight — by writing the set with an empty ``actions`` list and
an MD that names every file the delivery left (the new note among them);
before any step it removes the stage. ``status`` names the review's state
through ``lib/review_state.stem_state`` — the function ``review-session.py
start`` uses per listed document — which reads the set JSON for an approved
document and probes the target and the inbox copy for a waiting set (ADR-6).

Usage (cwd = instance root):
    python3 scripts/review-instructions.py preview --stem <period>_review [--place-anchor H]
    python3 scripts/review-instructions.py deliver --stem <period>_review [--place-anchor H]
    python3 scripts/review-instructions.py drop    --stem <period>_review
    python3 scripts/review-instructions.py status  --stem <period>_review
        [--config config/vault-config.yaml] [--profiles-dir profiles] [--tmp tomo-tmp/review]

Output: one JSON object on stdout, ASCII-escaped.
    preview: status ok, stem, doc_path, mode insert|replace|new-note, target, target_moved?, duplicates?,
             target_appeared?, place {anchor, placement, level}, section_md, escaped_lines, templater_hint,
             variant_missing?, template_unmergeable?, unlanded?, problems [refusing], notices, headings?,
             set_exists, resume
    deliver: status delivered|resumed, stem, step "", paths {set_json, set_md, note?}, next hashi-or-by-hand,
             mode, target, place, notices, target_appeared?
           | status refused, stem, problems [<refusing problems>|set-exists|name-taken], exists_path?, step?
           | status stopped, stem, step, failed_step, paths, problems [doc-changed|kado-write-failed]
    drop:    status withdrawn, stem, paths {set_json, set_md, note?} | status dropped, stem, removed
           | status stopped, stem, problems [kado-write-failed]
    status:  state (one of lib/review_state.STATES, or null for a withdrawn review), stem
    every subcommand: status not-found, stem, doc_path? | status refused, stem, problems [setup-missing|
             setup-invalid|inbox-not-configured], errors? | status stopped, stem, error {kind, detail}

Rules: a refusing problem means nothing is written; a second set for the stem is refused (set-exists);
    steps already done are skipped on resume, a step in flight is compared or uploaded; the document mark
    is the last step — a refused guard (Kado's error code CONFLICT, or the client's KadoConcurrencyError)
    is doc-changed with failed_step doc_mark, any other write failure kado-write-failed, both resumable.
    Nothing of the document or a note reaches stdout except preview's section_md; stderr names problem
    classes only.

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
from lib.kado_client import (  # noqa: E402
    KadoClient, KadoConcurrencyError, KadoError, KadoNotFoundError, KadoToolError,
)
from lib.note_io import ConfigError, load_vault_config  # noqa: E402
from lib.period import parse_name, render_name  # noqa: E402
from lib import review_state as rs  # noqa: E402
from lib.review_doc_read import DocRead, doc_path_of, read_document  # noqa: E402
from lib.review_vault import Stopped, Vault, kado_stops  # noqa: E402
from lib.staged_delivery import DeliveryStop, StagedDelivery  # noqa: E402

DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
DEFAULT_TMP = "tomo-tmp/review"
SCRIPT = "review-instructions"
NEXT = "hashi-or-by-hand"
DOC_CHANGED, KADO_WRITE_FAILED, NAME_TAKEN = "doc-changed", "kado-write-failed", "name-taken"
CONFLICT = "CONFLICT"                                   # Kado's error code for a refused guard or a dirty editor
TOOL_ERROR_PREFIX = "returned an error: "               # KadoClient's prefix before the MCP error payload


class Refused(Exception):
    def __init__(self, problem: str, **extra):
        super().__init__(problem)
        self.problem, self.extra = problem, extra


class NotFound(Exception):
    def __init__(self, doc_path: Optional[str] = None):
        super().__init__("not-found")
        self.doc_path = doc_path


# ---------------------------------------------------------------- Kado reads

def _note(vault: Vault, path: str) -> Optional[str]:
    """The note's text; None when nothing is at ``path``; ``Stopped`` on any other failure."""
    with kado_stops():
        try:
            content = vault.client.read_note(path).get("content")
        except KadoNotFoundError:
            return None
    return content if isinstance(content, str) else None


def _exists(vault: Vault, path: str) -> bool:
    with kado_stops():
        return bool(vault.client.path_exists(path))


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
    set_exists: bool
    plan: ra.ReviewPlan
    problems: List[str]
    notices: List[str]

    def output(self, *, section: bool, **extra) -> dict:
        """The plan's preview shape; ``section_md`` only when ``section`` (the preview prints it on purpose)."""
        out: Dict[str, object] = {"stem": self.stem, "doc_path": self.read.doc_path, **self.plan.preview()}
        if not section:
            del out["section_md"]
        out["problems"], out["notices"] = list(self.problems), list(self.notices)
        if self.meta.data.get("mode") == ra.NEW_NOTE and self.plan.mode != ra.NEW_NOTE:
            out["target_appeared"] = True
        out.update(extra)
        return out


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


def _target(vault: Vault, setup: rc.ReviewSetup, period_name: str) -> ra.Target:
    period = parse_name(period_name, setup.format, setup.rule)
    if period is None:
        raise Refused("setup-invalid", errors=[f"/naming/calendar_patterns/{rc.GRANULARITY[setup.kind]}"])
    candidates = period.note_paths(setup.folder, setup.format)
    texts: Dict[str, Optional[str]] = {}
    for path in candidates:
        texts[path] = _note(vault, path)
        if texts[path] is not None:
            break
    elsewhere: List[str] = []
    if all(texts.get(p) is None for p in candidates):
        name = f"{render_name(period, setup.format)}.md"
        with kado_stops():
            hits = vault.client.search_by_name(name)
        inbox = setup.inbox.strip().strip("/") + "/"
        elsewhere = sorted(str(h.get("path")) for h in hits
                           if isinstance(h, dict) and posixpath.basename(str(h.get("path") or "")) == name
                           and not str(h.get("path")).startswith(inbox))      # never the staged copy in the inbox
        for path in elsewhere:
            texts[path] = _note(vault, path)
    return ra.locate_target(candidates, texts, elsewhere)


def _template(vault: Vault, setup: rc.ReviewSetup, target: ra.Target) -> Optional[ra.Template]:
    if target.text is not None:
        return None
    raw_path, variant_path = rdl.template_paths(setup)
    return ra.Template(raw=_note(vault, raw_path) if raw_path else None,
                       variant=_note(vault, variant_path) if variant_path else None)


def load_run(args: argparse.Namespace) -> Run:
    """Read the document, the target and the template; build the plan; classify its problems."""
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
    target = _target(vault, setup, str(period_name or ""))
    plan = ra.build_review_plan(read.parsed.approved_review(), setup, target, _template(vault, setup, target),
                                anchor=getattr(args, "place_anchor", None), run_id=meta.run_id,
                                generated=meta.generated)
    set_exists = _exists(vault, paths[rdl.SET_JSON])
    problems, notices = rdl.classify(plan, [rdl.SET_EXISTS] if meta.second_set(set_exists) else [])
    return Run(args.stem, stage, meta, setup, profile, vault, read, paths, set_exists, plan, problems, notices)


# ---------------------------------------------------------------- preview

def preview(args: argparse.Namespace) -> dict:
    run = load_run(args)
    return run.output(section=True, status="ok", set_exists=run.set_exists, resume=run.meta.started())


# ---------------------------------------------------------------- deliver

def _tool_error_code(exc: KadoToolError) -> Optional[str]:
    """The ``code`` of the MCP error payload after the client's prefix; the exact ``"code":"CONFLICT"``
    token when the payload is not JSON; None when neither names a code."""
    text = str(exc)
    payload = text.split(TOOL_ERROR_PREFIX, 1)[1] if TOOL_ERROR_PREFIX in text else text
    try:
        data = json.loads(payload)
    except ValueError:
        return CONFLICT if f'"code":"{CONFLICT}"' in payload else None
    code = data.get("code") if isinstance(data, dict) else None
    return code if isinstance(code, str) else None


def _is_conflict(exc: KadoError) -> bool:
    """Kado refused the guard: the client's concurrency error, or a tool error whose code is CONFLICT."""
    return isinstance(exc, KadoConcurrencyError) or (
        isinstance(exc, KadoToolError) and _tool_error_code(exc) == CONFLICT)


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
        stop.status = DOC_CHANGED if _is_conflict(exc) else stop.status
        raise stop from exc
    delivery.record(rdl.DOC_MARK)


def _delivery_paths(run: Run) -> Dict[str, str]:
    paths = dict(run.paths)
    if run.plan.mode == ra.NEW_NOTE and run.plan.note_path:
        paths[rdl.NOTE] = run.plan.note_path
    return paths


def _public_paths(paths: Dict[str, str]) -> Dict[str, str]:
    return {key: paths[key] for key in (rdl.SET_JSON, rdl.SET_MD, rdl.NOTE) if key in paths}


def deliver(args: argparse.Namespace) -> dict:
    run = load_run(args)
    if run.problems:
        return {"status": "refused", "stem": run.stem, "problems": run.problems, "notices": run.notices}
    paths = _delivery_paths(run)
    set_doc = ra.build_review_instruction_set(run.plan, stem=run.stem, generated=run.meta.generated,
                                              profile=run.profile)
    payloads = {rdl.SET_JSON: json.dumps(set_doc, indent=2, ensure_ascii=False) + "\n",
                rdl.SET_MD: rdl.set_md(run.plan, run.meta, run.profile)}
    if rdl.NOTE in paths:
        payloads[rdl.NOTE] = run.plan.note_text or ""
    resumed = run.meta.started()
    delivery = StagedDelivery(run.vault.client, rdl.STEPS, paths, run.meta,
                              lambda: rdl.save_meta(run.stage, run.meta), script=SCRIPT)
    try:
        for step in (rdl.NOTE, rdl.SET_JSON, rdl.SET_MD):
            if step in paths and step not in run.meta.steps_done:
                delivery.deliver_step(step, payloads[step])
        _mark_document(run, delivery)
    except DeliveryStop as stop:
        if stop.status == "exists":
            return {"status": "refused", "stem": run.stem, "problems": [NAME_TAKEN], "exists_path": stop.exists_path,
                    "step": stop.step}
        problem = DOC_CHANGED if stop.status == DOC_CHANGED else KADO_WRITE_FAILED
        return {"status": "stopped", "stem": run.stem, "step": stop.step, "failed_step": run.meta.failed_step,
                "paths": _public_paths(paths), "problems": [problem]}
    return run.output(section=False, status="resumed" if resumed else "delivered", step="",
                      paths=_public_paths(paths), next=NEXT)


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
    try:
        vault.client.write_file(paths[rdl.SET_JSON],
                               (json.dumps(rdl.withdrawn_set(args.stem, meta, profile), indent=2,
                                           ensure_ascii=False) + "\n").encode("utf-8"))
        vault.client.write_note(paths[rdl.SET_MD], rdl.withdrawn_md(args.stem, meta, profile, files))
    except KadoError as exc:
        return {"status": "stopped", "stem": args.stem, "problems": [KADO_WRITE_FAILED],
                "error": {"kind": type(exc).__name__}}
    meta.data["withdrawn"] = True
    meta.failed_step = ""
    rdl.save_meta(stage, meta)
    return {"status": "withdrawn", "stem": args.stem, "paths": _public_paths(paths)}


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


def _stem_arg(text: str) -> str:
    if not rs.safe_stem(text):
        raise argparse.ArgumentTypeError("expected a plain stem like 2026-W13_review (not empty, . or .., no / or \\)")
    return text


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
        cmd.add_argument("--stem", required=True, type=_stem_arg, help="<period>_review, the tomo-tmp/review/ folder")
        if name in ("preview", "deliver"):
            cmd.add_argument("--place-anchor", help="The heading the user chose instead of the configured anchor")
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
