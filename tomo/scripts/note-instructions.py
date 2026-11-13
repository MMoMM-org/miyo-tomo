#!/usr/bin/env python3
# version: 0.3.1
"""note-instructions.py — lifecycle of one /note draft in tomo-tmp/note/<stem>/.

The note-from-template skill calls this script for every state change of a
draft; the skill itself only writes draft.md. Run from the instance root
(paths are relative to the working directory).

Subcommands:
  new   --template <vault path .md> [--source <inbox note .md>]
        Draws the stem (YYYY-MM-DD_HHMMSS), the run id and `generated`; reads
        concepts.inbox, concepts.atomic_note and profile from
        config/vault-config.yaml and the destination of
        config/note-processes/<template-stem>.md; stages source.md (read via
        Kado) and writes meta.json (profile included); removes
        tomo-tmp/note/view.md. Every vault path must
        be relative (lib/note_paths: vault_note, vault_folder); --source must
        lie inside concepts.inbox.
        Output: {stem, run_id, default_destination, inbox}
        Exit: 0; 1 Kado error reading the source; 2 bad invocation, config or I/O
  stage --stem <stem> [--title <t>] [--destination <folder>] [--keep-source true|false]
        Updates meta.json unless a frozen field would change; writes note.md,
        which is draft.md with every {{source_link}} resolved from keep_source
        ([[<source stem>]] when kept, empty otherwise; draft.md is never
        changed); runs the filled-note check on note.md. Removes
        tomo-tmp/note/view.md first, and writes it again (the approval header
        and note.md in a fence) only when a title is staged and the check
        passes; a refused stage leaves none.
        Output: {stem, title, inbox_file, destination_file, keep_source, frozen,
                 check: {ok, findings[]}}
        Exit: 0 (findings are output); 2 bad invocation or unknown stem
  deliver --stem <stem>
        Resolves draft.md as stage does and refuses on a failing filled-note
        check; checks the destination and the guards; then writes, in order,
        the stamped note, <stem>_instructions.json and <stem>_instructions.md
        flat in the inbox and merges the source mark. A step already landed
        with identical text counts as done; meta.json records every step, and
        names a step as failed_step before uploading it.
        A source gone before the mark counts as delivered, source_marked false.
        Removes tomo-tmp/note/view.md at its start and the stage directory on
        success.
        No Kado URL or token: failed at step kado_config, recorded as
        failed_step, nothing written. Kado down: failed at step note.
        A failing check or stamp: failed with step "", nothing recorded.
        Output: {status: delivered|exists|failed|withdrawn,
                 step: kado_config|note|instructions_json|instructions_md|
                       source_mark|"",
                 note_path, instructions_json, instructions_md, source_marked,
                 steps_done, frozen, exists_path}
        steps_done: the steps meta.json records as landed when the run ended.
        frozen: true when stage would refuse a title or destination change
        (lib/note_meta.is_frozen on meta.json as the run ended).
        On a taken name the first stdout line is EXISTS:<vault path>.
        Exit: 0 delivered; 1 Kado, check or guard failure; 2 bad invocation,
              unknown stem or meta.json write failure (no JSON on stdout);
              3 name taken (nothing more written)
  drop  --stem <stem>
        Removes the stage directory and tomo-tmp/note/view.md.
        Output: {stem, removed}
        Exit: 0; 2 malformed stem

stdout carries one JSON object; stderr carries diagnostics that name the
problem class only, never a title, a path or note text.

Design notes: docs/tomo/scripts/note-instructions.md
"""
from __future__ import annotations

import argparse
import json
import posixpath
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import run_id as run_id_lib  # noqa: E402
from lib.doc_frontmatter import (  # noqa: E402
    FrontmatterMergeError, build_tomo_block, merge_tomo_block_into_markdown,
)
from lib.kado_client import KadoClient, KadoError, KadoNotFoundError  # noqa: E402
from lib.note_actions import build_note_actions, build_note_instruction_set  # noqa: E402
from lib.note_io import ConfigError, atomic_write_text, load_vault_config  # noqa: E402
from lib.note_meta import (  # noqa: E402
    KADO_CONFIG, STEPS, MetaError, apply_stage_update, draw_stem, is_frozen,
    mark_step_failed, new_meta, read_meta, remove_stage, stage_dir, write_meta,
)
from lib.note_meta import NOTE_FILE, stage_root  # noqa: E402
from lib.note_paths import (  # noqa: E402
    has_template_syntax, has_unsafe_char, is_inside, vault_folder, vault_note,
)
from lib.note_process import PROCESS_DIR, read_process  # noqa: E402
from lib.render_helpers import fence_for  # noqa: E402
from lib.render_md import render_instructions_md  # noqa: E402
from lib.render_withhold import (  # noqa: E402
    make_folder_listing, validate_destinations, withdraw_unjustified_deletes,
)
from lib.staged_delivery import DeliveryStop, StagedDelivery, stable_block  # noqa: E402
from lib.template_syntax import (  # noqa: E402
    filled_note_check, resolve_tokens, source_link_value,
)

CONFIG_PATH = Path("config") / "vault-config.yaml"
SOURCE_FILE = "source.md"
DRAFT_FILE = "draft.md"
SOURCE_LINK = "source_link"
VIEW_FILE = "view.md"
_STEM_ATTEMPTS = 60


class UsageError(Exception):
    """Bad invocation, config or local I/O; exit 2. Message names the class only."""


class SourceError(Exception):
    """Kado could not deliver the source note; exit 1."""


# ── shared helpers ───────────────────────────────────────────────────────


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_path(node: object) -> str | None:
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        paths = node.get("paths")
        first = paths[0] if isinstance(paths, list) and paths else None
        return node.get("path") or first
    return None


def _load_config(path: Path) -> dict:
    try:
        return load_vault_config(path)
    except ConfigError as exc:
        raise UsageError(str(exc)) from exc


def read_note_config(path: Path = CONFIG_PATH) -> dict:
    """Return {inbox, atomic_path, profile} from vault-config.yaml; UsageError when unusable."""
    cfg = _load_config(path)
    concepts = cfg.get("concepts") if isinstance(cfg.get("concepts"), dict) else {}
    inbox = vault_folder(concepts.get("inbox"))
    if inbox is None:
        raise UsageError("vault-config.yaml concepts.inbox is not a relative vault folder")
    atomic = vault_folder(_atomic_path(concepts.get("atomic_note")))
    if atomic is None:
        raise UsageError("vault-config.yaml concepts.atomic_note is not a relative vault folder")
    profile = cfg.get("profile")
    return {"inbox": inbox, "atomic_path": atomic,
            "profile": profile if isinstance(profile, str) else None}


# ── view.md ──────────────────────────────────────────────────────────────


def _view_path() -> Path:
    return stage_root(Path.cwd()) / VIEW_FILE


def remove_view() -> None:
    _view_path().unlink(missing_ok=True)


def render_view(meta, note_text: str) -> str:
    """Return the approval header (SKILL step 6 wording) and note_text in a fence."""
    lines = [f"Template: {meta.template_stem} · Final name: {meta.destination_file()} · "
             f"In the inbox until applied: {posixpath.basename(meta.inbox_file)}"]
    if meta.source_path and not meta.keep_source:
        lines.append(f"Source {meta.source_path} is deleted when you apply "
                     "the instruction set in Hashi.")
    fence = fence_for(note_text)
    body = note_text if note_text.endswith("\n") else note_text + "\n"
    return "\n\n".join(lines) + f"\n\n{fence}markdown\n{body}{fence}\n"


def _write_view(stage: Path, meta, check: dict) -> None:
    if meta.title and check["ok"]:
        note_text = (stage / NOTE_FILE).read_text(encoding="utf-8")
        atomic_write_text(_view_path(), render_view(meta, note_text))


# ── new ──────────────────────────────────────────────────────────────────


def _note_arg(value: str | None, what: str) -> str:
    path = vault_note(value)
    if path is None:
        raise UsageError(f"{what} must be a relative vault path ending in .md")
    return path


def _require_inside(source: str | None, inbox: str) -> None:
    """UsageError when the source is not under the inbox (note_paths.is_inside)."""
    if source is not None and not is_inside(source, inbox):
        raise UsageError("--source must be a note inside concepts.inbox")


def _default_destination(template_stem: str, atomic_path: str) -> str:
    """Return the process destination (read_process has validated it), else atomic_path."""
    try:
        process = read_process(PROCESS_DIR, template_stem)
    except ValueError as exc:
        raise UsageError("template name cannot name a process file") from exc
    if process["error"]:
        print(f"note-instructions: process file ignored: {process['error']}", file=sys.stderr)
        return atomic_path
    return process["destination"] or atomic_path


def _read_source(path: str) -> str:
    try:
        return KadoClient().read_note(path).get("content") or ""
    except KadoError as exc:
        raise SourceError(f"cannot read the source note ({type(exc).__name__})") from exc


def _create_stage(base: Path) -> tuple[str, Path]:
    now = datetime.now()
    for offset in range(_STEM_ATTEMPTS):
        stem = draw_stem(now + timedelta(seconds=offset))
        stage = stage_dir(base, stem)
        try:
            stage.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return stem, stage
    raise UsageError("no free stem within a minute of now")


def _fill_stage(stage: Path, body: str | None, meta) -> None:
    """Write source.md and meta.json atomically; on failure remove the stage and re-raise."""
    try:
        if body is not None:
            atomic_write_text(stage / SOURCE_FILE, body)
        write_meta(stage, meta)
    except OSError:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def cmd_new(args: argparse.Namespace) -> int:
    remove_view()
    template = _note_arg(args.template, "--template")
    source = _note_arg(args.source, "--source") if args.source is not None else None
    cfg = read_note_config()
    _require_inside(source, cfg["inbox"])
    template_stem = posixpath.basename(template)[:-3]
    default_dest = _default_destination(template_stem, cfg["atomic_path"])
    body = _read_source(source) if source else None
    stem, stage = _create_stage(Path.cwd())
    now = _utc_now()
    meta = new_meta(stem=stem, inbox=cfg["inbox"], title="", destination=default_dest,
                    default_destination=default_dest, run_id=run_id_lib.generate(),
                    created=now, generated=now, template=template,
                    template_stem=template_stem, source_path=source,
                    profile=cfg["profile"])
    _fill_stage(stage, body, meta)
    _emit({"stem": stem, "run_id": meta.run_id,
           "default_destination": meta.default_destination, "inbox": cfg["inbox"]})
    return 0


# ── stage ────────────────────────────────────────────────────────────────


def _existing_stage(stem: str) -> Path:
    try:
        stage = stage_dir(Path.cwd(), stem)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    if not stage.is_dir():
        raise UsageError("unknown stem: no stage directory")
    return stage


def _title_arg(value: str | None) -> str | None:
    if value is None:
        return None
    if has_unsafe_char(value):
        raise UsageError("--title must not contain control or invisible characters")
    title = value.strip().rstrip(". ")
    if not title:
        raise UsageError("--title must not be blank")
    if title.startswith("."):
        raise UsageError("--title must not start with a dot")
    if has_template_syntax(title):
        raise UsageError("--title must not contain template syntax")
    return title


def _destination_arg(value: str | None) -> str | None:
    if value is None:
        return None
    dest = vault_folder(value)
    if dest is None:
        raise UsageError("--destination must be a relative vault folder")
    return dest


def resolve_source_link(text: str, meta) -> str:
    """Replace each real {{source_link}} token from meta's source and keep_source; nothing else."""
    value = source_link_value(meta.source_path, meta.keep_source)
    return resolve_tokens(text, {SOURCE_LINK: value})


def _missing_draft() -> dict:
    return {"ok": False, "findings": [{
        "check": "draft_present", "status": "FAIL",
        "detail": "draft.md is missing in the stage directory.",
        "fix": "Write draft.md, then run stage again."}]}


def _resolved_draft(stage: Path, meta) -> str | None:
    """Return draft.md with {{source_link}} resolved, None when draft.md is missing."""
    draft = stage / DRAFT_FILE
    if not draft.is_file():
        return None
    return resolve_source_link(draft.read_text(encoding="utf-8"), meta)


def _resolve_and_check(stage: Path, meta) -> dict:
    note = stage / NOTE_FILE
    resolved = _resolved_draft(stage, meta)
    if resolved is None:
        note.unlink(missing_ok=True)
        return _missing_draft()
    atomic_write_text(note, resolved)
    result = filled_note_check(resolved)
    return {"ok": result.ok, "findings": result.findings}


def _stage_output(meta, frozen: bool, check: dict) -> dict:
    named = bool(meta.title)
    return {"stem": meta.stem, "title": meta.title,
            "inbox_file": meta.inbox_file if named else "",
            "destination_file": meta.destination_file() if named else "",
            "keep_source": meta.keep_source, "frozen": frozen, "check": check}


def _stage_meta(stage: Path):
    try:
        return read_meta(stage)
    except MetaError as exc:
        raise UsageError(str(exc)) from exc


def cmd_stage(args: argparse.Namespace) -> int:
    remove_view()
    title, destination = _title_arg(args.title), _destination_arg(args.destination)
    keep = None if args.keep_source is None else args.keep_source == "true"
    stage = _existing_stage(args.stem)
    meta = _stage_meta(stage)
    frozen = apply_stage_update(meta, title=title, destination=destination, keep_source=keep)
    if not frozen:
        write_meta(stage, meta)
    check = _resolve_and_check(stage, meta)
    _write_view(stage, meta, check)
    _emit(_stage_output(meta, frozen, check))
    return 0


# ── deliver ──────────────────────────────────────────────────────────────

INBOX_STEPS = STEPS[:3]
SOURCE_MARK = STEPS[3]


class UnguardedMarkError(Exception):
    """read_frontmatter returned no modified time; the merge would be unguarded."""


def _set_path(meta, suffix: str) -> str:
    return f"{posixpath.dirname(meta.inbox_file)}/{meta.instructions_stem()}{suffix}"


def _targets(meta) -> dict:
    return {"note": meta.inbox_file, "instructions_json": _set_path(meta, ".json"),
            "instructions_md": _set_path(meta, ".md")}


def _deliver_output(meta, status: str, step: str = "", exists_path: str = "",
                    source_marked: bool = False) -> dict:
    targets = _targets(meta)
    return {"status": status, "step": step, "note_path": targets["note"],
            "instructions_json": targets["instructions_json"],
            "instructions_md": targets["instructions_md"],
            "source_marked": source_marked,
            "steps_done": list(meta.steps_done),
            "frozen": is_frozen(meta),
            "exists_path": exists_path}


def _checked_note(stage: Path, meta) -> str:
    """Return the resolved draft stamped rendered-note/pending-move; refuse a failing check."""
    resolved = _resolved_draft(stage, meta)
    if resolved is None or not filled_note_check(resolved).ok:
        print("note-instructions: filled-note check failed; fix the draft and run stage",
              file=sys.stderr)
        raise DeliveryStop("failed", "", 1)
    try:
        return merge_tomo_block_into_markdown(
            resolved, stable_block("rendered-note", "pending-move", meta))
    except FrontmatterMergeError as exc:
        print(f"note-instructions: cannot stamp the note ({type(exc).__name__})", file=sys.stderr)
        raise DeliveryStop("failed", "", 1) from exc


def _guarded_actions(meta, client) -> list[dict]:
    """Run the destination and delete guards; refuse a clash or any cut action."""
    actions = build_note_actions(meta)
    kept, clashes = validate_destinations(actions, make_folder_listing(client))
    kept, _ = withdraw_unjustified_deletes(kept)
    if clashes:
        raise DeliveryStop("exists", "", 3, clashes[0]["destination"])
    if kept != actions:
        print("note-instructions: a guard withdrew an action; nothing written", file=sys.stderr)
        raise DeliveryStop("withdrawn", "", 1)
    return kept


def _payloads(meta, note_text: str, actions: list[dict]) -> dict:
    doc = build_note_instruction_set(meta)
    doc["actions"] = actions
    md = render_instructions_md(actions, {"generated": meta.generated,
                                          "profile": meta.profile},
                                {"templater_hint": False})
    return {"note": note_text,
            "instructions_json": json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
            "instructions_md": merge_tomo_block_into_markdown(
                md, stable_block("instructions", "pending-apply", meta))}


def _staged_delivery(client, stage: Path, meta) -> StagedDelivery:
    """The shared loop over /note's steps, persisting meta.json through write_meta."""
    return StagedDelivery(client, STEPS, _targets(meta), meta,
                          lambda: write_meta(stage, meta), script="note-instructions")


def _write_mark(client, meta) -> bool:
    """Merge source/captured guarded by its modified time (ADR-3); False when the source is gone."""
    try:
        modified = client.read_frontmatter(meta.source_path).get("modified")
        if modified is None:
            raise UnguardedMarkError("no modified time")
        client.write_frontmatter(
            meta.source_path, {"tomo": build_tomo_block("source", "captured", meta.run_id)},
            mode="merge", expected_modified=modified)
    except KadoNotFoundError:
        return False
    return True


def _carries_mark(client, meta) -> bool:
    """True when the source holds this draft's source/captured block; False when it is gone."""
    try:
        frontmatter = client.read_frontmatter(meta.source_path).get("content")
    except KadoNotFoundError:
        return False
    block = frontmatter.get("tomo") if isinstance(frontmatter, dict) else None
    return (isinstance(block, dict) and block.get("state") == "captured"
            and block.get("run_id") == meta.run_id)


def _mark_source(client, delivery: StagedDelivery, meta) -> bool:
    """Run the source_mark step; return whether the source carries the mark."""
    if not meta.source_path:
        return False
    recorded = SOURCE_MARK in meta.steps_done
    try:
        marked = _carries_mark(client, meta) if recorded else _write_mark(client, meta)
    except (KadoError, UnguardedMarkError) as exc:
        raise delivery.fail(SOURCE_MARK, exc) from exc
    delivery.record(SOURCE_MARK)
    return marked


def _deliver(stage: Path, meta) -> bool:
    note_text = _checked_note(stage, meta)
    try:
        client = KadoClient()
    except KadoError as exc:
        print("note-instructions: Kado is not configured (no URL or token)", file=sys.stderr)
        mark_step_failed(meta, KADO_CONFIG)
        write_meta(stage, meta)
        raise DeliveryStop("failed", KADO_CONFIG, 1) from exc
    payloads = _payloads(meta, note_text, _guarded_actions(meta, client))
    delivery = _staged_delivery(client, stage, meta)
    for step in INBOX_STEPS:
        delivery.deliver_step(step, payloads[step])
    return _mark_source(client, delivery, meta)


def cmd_deliver(args: argparse.Namespace) -> int:
    remove_view()
    stage = _existing_stage(args.stem)
    meta = _stage_meta(stage)
    if not meta.title:
        raise UsageError("no title staged: run stage --title first")
    try:
        marked = _deliver(stage, meta)
    except DeliveryStop as stop:
        if stop.exists_path:
            print(f"EXISTS:{stop.exists_path}")
        _emit(_deliver_output(meta, stop.status, stop.step, stop.exists_path))
        return stop.code
    remove_stage(Path.cwd(), meta.stem)
    _emit(_deliver_output(meta, "delivered", source_marked=marked))
    return 0


# ── drop ─────────────────────────────────────────────────────────────────


def cmd_drop(args: argparse.Namespace) -> int:
    remove_view()
    try:
        removed = remove_stage(Path.cwd(), args.stem)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    _emit({"stem": args.stem, "removed": removed})
    return 0


# ── entry point ──────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lifecycle of one /note draft.")
    sub = p.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="Start a draft.")
    new.add_argument("--template", required=True, help="Vault path of the template (.md).")
    new.add_argument("--source", help="Vault path of the inbox note the draft is made from.")
    stage = sub.add_parser("stage", help="Record title, destination, keep-source; check the draft.")
    stage.add_argument("--stem", required=True)
    stage.add_argument("--title")
    stage.add_argument("--destination", help="Vault folder the note moves to.")
    stage.add_argument("--keep-source", choices=("true", "false"))
    deliver = sub.add_parser("deliver", help="Write the note and its instruction set; mark the source.")
    deliver.add_argument("--stem", required=True)
    drop = sub.add_parser("drop", help="Remove the stage directory.")
    drop.add_argument("--stem", required=True)
    return p


COMMANDS = {"new": cmd_new, "stage": cmd_stage, "deliver": cmd_deliver, "drop": cmd_drop}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except SourceError as exc:
        print(f"note-instructions: {exc}", file=sys.stderr)
        return 1
    except UsageError as exc:
        print(f"note-instructions: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"note-instructions: local I/O failed ({type(exc).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
