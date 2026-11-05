#!/usr/bin/env python3
# version: 0.2.1
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
        Kado) and writes meta.json (profile included). Every vault path must
        be relative (lib/note_paths: vault_note, vault_folder); --source must
        lie inside concepts.inbox.
        Output: {stem, run_id, default_destination, inbox}
        Exit: 0; 1 Kado error reading the source; 2 bad invocation, config or I/O
  stage --stem <stem> [--title <t>] [--destination <folder>] [--keep-source true|false]
        Updates meta.json unless a frozen field would change; writes note.md,
        which is draft.md with every {{source_link}} resolved from keep_source
        ([[<source stem>]] when kept, empty otherwise; draft.md is never
        changed); runs the filled-note check on note.md.
        Output: {stem, title, inbox_file, destination_file, keep_source, frozen,
                 check: {ok, findings[]}}
        Exit: 0 (findings are output); 2 bad invocation or unknown stem
  deliver --stem <stem>
        Resolves draft.md as stage does and refuses on a failing filled-note
        check; checks the destination and the guards; then writes, in order,
        the stamped note, <stem>_instructions.json and <stem>_instructions.md
        flat in the inbox and merges the source mark. A step already landed
        with identical text counts as done; meta.json records every step.
        Removes the stage directory on success.
        Output: {status: delivered|exists|failed|withdrawn,
                 step: note|instructions_json|instructions_md|source_mark|"",
                 note_path, instructions_json, instructions_md, source_marked,
                 exists_path}
        On a taken name the first stdout line is EXISTS:<vault path>.
        Exit: 0 delivered; 1 Kado, check or guard failure; 2 bad invocation
              or unknown stem; 3 name taken (nothing more written)
  drop  --stem <stem>
        Removes the stage directory.
        Output: {stem, removed}
        Exit: 0; 2 malformed stem

stdout carries one JSON object; stderr carries diagnostics that name the
problem class only, never a title, a path or note text.

Design notes: docs/tomo/scripts/note-instructions.md
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import yaml  # noqa: E402

from lib import run_id as run_id_lib  # noqa: E402
from lib.doc_frontmatter import (  # noqa: E402
    FrontmatterMergeError, build_tomo_block, merge_tomo_block_into_markdown,
)
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.note_actions import build_note_actions, build_note_instruction_set  # noqa: E402
from lib.note_meta import (  # noqa: E402
    MetaError, apply_stage_update, draw_stem, mark_step_done, mark_step_failed,
    new_meta, read_meta, remove_stage, stage_dir, write_meta,
)
from lib.note_paths import (  # noqa: E402
    has_template_syntax, has_unsafe_char, is_inside, vault_folder, vault_note,
)
from lib.note_process import PROCESS_DIR, read_process  # noqa: E402
from lib.render_md import render_instructions_md  # noqa: E402
from lib.render_withhold import (  # noqa: E402
    make_folder_listing, validate_destinations, withdraw_unjustified_deletes,
)
from lib.template_syntax import (  # noqa: E402
    filled_note_check, resolve_tokens, source_link_value,
)

CONFIG_PATH = Path("config") / "vault-config.yaml"
SOURCE_FILE = "source.md"
DRAFT_FILE = "draft.md"
NOTE_FILE = "note.md"
SOURCE_LINK = "source_link"
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


def _write_atomic(target: Path, text: str) -> None:
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)


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
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise UsageError(f"vault-config.yaml unreadable ({type(exc).__name__})") from exc
    if not isinstance(cfg, dict):
        raise UsageError("vault-config.yaml is not a mapping")
    return cfg


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
            _write_atomic(stage / SOURCE_FILE, body)
        write_meta(stage, meta)
    except OSError:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def cmd_new(args: argparse.Namespace) -> int:
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
    _write_atomic(note, resolved)
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
    title, destination = _title_arg(args.title), _destination_arg(args.destination)
    keep = None if args.keep_source is None else args.keep_source == "true"
    stage = _existing_stage(args.stem)
    meta = _stage_meta(stage)
    frozen = apply_stage_update(meta, title=title, destination=destination, keep_source=keep)
    if not frozen:
        write_meta(stage, meta)
    _emit(_stage_output(meta, frozen, _resolve_and_check(stage, meta)))
    return 0


# ── deliver ──────────────────────────────────────────────────────────────

INBOX_STEPS = ("note", "instructions_json", "instructions_md")


class DeliveryStop(Exception):
    """Ends a delivery early with an output status, a step and an exit code."""

    def __init__(self, status: str, step: str, code: int, exists_path: str = ""):
        super().__init__(status)
        self.status, self.step, self.code, self.exists_path = status, step, code, exists_path


def _set_path(meta, suffix: str) -> str:
    return f"{posixpath.dirname(meta.inbox_file)}/{meta.instructions_stem()}{suffix}"


def _targets(meta) -> dict:
    return {"note": meta.inbox_file, "instructions_json": _set_path(meta, ".json"),
            "instructions_md": _set_path(meta, ".md")}


def _deliver_output(meta, status: str, step: str = "", exists_path: str = "") -> dict:
    targets = _targets(meta)
    return {"status": status, "step": step, "note_path": targets["note"],
            "instructions_json": targets["instructions_json"],
            "instructions_md": targets["instructions_md"],
            "source_marked": status == "delivered" and bool(meta.source_path),
            "exists_path": exists_path}


def _stable_block(doc_type: str, state: str, meta) -> dict:
    """A tomo: block whose updated_at is meta.generated, so a rebuild is byte-identical."""
    block = build_tomo_block(doc_type, state, meta.run_id)
    block["updated_at"] = meta.generated
    return block


def _checked_note(stage: Path, meta) -> str:
    """Return the resolved draft stamped rendered-note/pending-move; refuse a failing check."""
    resolved = _resolved_draft(stage, meta)
    if resolved is None or not filled_note_check(resolved).ok:
        print("note-instructions: filled-note check failed; fix the draft and run stage",
              file=sys.stderr)
        raise DeliveryStop("failed", "", 1)
    try:
        return merge_tomo_block_into_markdown(
            resolved, _stable_block("rendered-note", "pending-move", meta))
    except FrontmatterMergeError as exc:
        print(f"note-instructions: cannot stamp the note ({type(exc).__name__})", file=sys.stderr)
        raise DeliveryStop("failed", "", 1) from exc


def _guarded_actions(meta, client) -> list[dict]:
    """Run the destination and delete guards; refuse a clash or any cut action."""
    actions = build_note_actions(meta)
    kept, clashes = validate_destinations(actions, make_folder_listing(client))
    kept, _withdrawn = withdraw_unjustified_deletes(kept)
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
                md, _stable_block("instructions", "pending-apply", meta))}


def _without_final_newline(text: str) -> str:
    return text[:-1] if text.endswith("\n") else text


def _same_text(client, path: str, payload: str) -> bool:
    if path.endswith(".md"):
        landed = client.read_note(path).get("content") or ""
    else:
        landed = client.read_file_bytes(path).decode("utf-8", errors="replace")
    return _without_final_newline(landed) == _without_final_newline(payload)


def _upload(client, path: str, payload: str) -> None:
    if path.endswith(".md"):
        client.write_note(path, payload)
    else:
        client.write_file(path, payload.encode("utf-8"))


def _record(stage: Path, meta, step: str) -> None:
    mark_step_done(meta, step)
    write_meta(stage, meta)


def _fail(stage: Path, meta, step: str, exc: Exception) -> DeliveryStop:
    mark_step_failed(meta, step)
    write_meta(stage, meta)
    print(f"note-instructions: delivery failed at {step} ({type(exc).__name__})", file=sys.stderr)
    return DeliveryStop("failed", step, 1)


def _deliver_step(client, stage: Path, meta, step: str, payload: str) -> None:
    """Identical target: done. Other text: name taken. Absent: write unless already done."""
    path = _targets(meta)[step]
    try:
        if client.path_exists(path):
            if not _same_text(client, path, payload):
                raise DeliveryStop("exists", step, 3, path)
        elif step not in meta.steps_done:
            _upload(client, path, payload)
    except KadoError as exc:
        raise _fail(stage, meta, step, exc) from exc
    _record(stage, meta, step)


def _mark_source(client, stage: Path, meta) -> None:
    """Merge source/captured into the source note, guarded by its modified time (ADR-3)."""
    if not meta.source_path or "source_mark" in meta.steps_done:
        return
    try:
        modified = client.read_frontmatter(meta.source_path).get("modified")
        client.write_frontmatter(
            meta.source_path, {"tomo": build_tomo_block("source", "captured", meta.run_id)},
            mode="merge", expected_modified=modified)
    except KadoError as exc:
        raise _fail(stage, meta, "source_mark", exc) from exc
    _record(stage, meta, "source_mark")


def _deliver(stage: Path, meta) -> None:
    note_text = _checked_note(stage, meta)
    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"note-instructions: cannot reach Kado ({type(exc).__name__})", file=sys.stderr)
        raise DeliveryStop("failed", "", 1) from exc
    payloads = _payloads(meta, note_text, _guarded_actions(meta, client))
    for step in INBOX_STEPS:
        _deliver_step(client, stage, meta, step, payloads[step])
    _mark_source(client, stage, meta)


def cmd_deliver(args: argparse.Namespace) -> int:
    stage = _existing_stage(args.stem)
    meta = _stage_meta(stage)
    if not meta.title:
        raise UsageError("no title staged: run stage --title first")
    try:
        _deliver(stage, meta)
    except DeliveryStop as stop:
        if stop.exists_path:
            print(f"EXISTS:{stop.exists_path}")
        _emit(_deliver_output(meta, stop.status, stop.step, stop.exists_path))
        return stop.code
    remove_stage(Path.cwd(), meta.stem)
    _emit(_deliver_output(meta, "delivered"))
    return 0


# ── drop ─────────────────────────────────────────────────────────────────


def cmd_drop(args: argparse.Namespace) -> int:
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
