#!/usr/bin/env python3
# version: 0.1.1
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
        Kado) and writes meta.json (profile included).
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
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import yaml  # noqa: E402

from lib import run_id as run_id_lib  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.note_meta import (  # noqa: E402
    MetaError, apply_stage_update, draw_stem, folder, new_meta, read_meta,
    remove_stage, stage_dir, write_meta,
)
from lib.note_process import PROCESS_DIR, read_process  # noqa: E402
from lib.template_syntax import _token_matches, filled_note_check  # noqa: E402

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
    inbox, atomic = concepts.get("inbox"), _atomic_path(concepts.get("atomic_note"))
    if not isinstance(inbox, str) or not inbox.strip("/ "):
        raise UsageError("vault-config.yaml has no concepts.inbox")
    if not isinstance(atomic, str) or not atomic.strip("/ "):
        raise UsageError("vault-config.yaml has no concepts.atomic_note path")
    profile = cfg.get("profile")
    return {"inbox": folder(inbox), "atomic_path": folder(atomic),
            "profile": profile if isinstance(profile, str) else None}


# ── new ──────────────────────────────────────────────────────────────────


def _md_path(value: str | None, what: str) -> str:
    if not isinstance(value, str) or not value.strip() or not value.endswith(".md"):
        raise UsageError(f"{what} must be a vault path ending in .md")
    return value


def _default_destination(template_stem: str, atomic_path: str) -> str:
    try:
        process = read_process(PROCESS_DIR, template_stem)
    except ValueError as exc:
        raise UsageError("template name cannot name a process file") from exc
    if process["error"]:
        print(f"note-instructions: process file ignored: {process['error']}", file=sys.stderr)
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


def cmd_new(args: argparse.Namespace) -> int:
    template = _md_path(args.template, "--template")
    source = _md_path(args.source, "--source") if args.source is not None else None
    cfg = read_note_config()
    template_stem = posixpath.basename(template)[:-3]
    default_dest = _default_destination(template_stem, cfg["atomic_path"])
    body = _read_source(source) if source else None
    stem, stage = _create_stage(Path.cwd())
    if body is not None:
        (stage / SOURCE_FILE).write_text(body, encoding="utf-8")
    now = _utc_now()
    meta = new_meta(stem=stem, inbox=cfg["inbox"], title="", destination=default_dest,
                    default_destination=default_dest, run_id=run_id_lib.generate(),
                    created=now, generated=now, template=template,
                    template_stem=template_stem, source_path=source,
                    profile=cfg["profile"])
    write_meta(stage, meta)
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
    if value is not None and not value.strip():
        raise UsageError("--title must not be blank")
    return value


def _destination_arg(value: str | None) -> str | None:
    if value is None:
        return None
    parts = value.strip().strip("/").split("/")
    if not value.strip() or value.startswith("/") or any(p in ("", ".", "..") for p in parts):
        raise UsageError("--destination must be a relative vault folder")
    return value.strip()


def source_link_value(meta) -> str:
    """``[[<source stem>]]`` when the source exists and is kept; empty text otherwise."""
    if not meta.source_path or not meta.keep_source:
        return ""
    name = posixpath.basename(meta.source_path)
    return "[[" + (name[:-3] if name.endswith(".md") else name) + "]]"


def resolve_source_link(text: str, meta) -> str:
    """Replace each real {{source_link}} token (as tokens() sees them); nothing else."""
    value, parts, cursor = source_link_value(meta), [], 0
    for match, _line in _token_matches(text):
        if match.group(1) == SOURCE_LINK:
            parts += [text[cursor:match.start()], value]
            cursor = match.end()
    return "".join(parts) + text[cursor:]


def _write_atomic(target: Path, text: str) -> None:
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)


def _missing_draft() -> dict:
    return {"ok": False, "findings": [{
        "check": "draft_present", "status": "FAIL",
        "detail": "draft.md is missing in the stage directory.",
        "fix": "Write draft.md, then run stage again."}]}


def _resolve_and_check(stage: Path, meta) -> dict:
    draft, note = stage / DRAFT_FILE, stage / NOTE_FILE
    if not draft.is_file():
        note.unlink(missing_ok=True)
        return _missing_draft()
    resolved = resolve_source_link(draft.read_text(encoding="utf-8"), meta)
    _write_atomic(note, resolved)
    result = filled_note_check(resolved)
    return {"ok": result.ok, "findings": result.findings}


def _stage_output(meta, frozen: bool, check: dict) -> dict:
    named = bool(meta.title)
    return {"stem": meta.stem, "title": meta.title,
            "inbox_file": meta.inbox_file if named else "",
            "destination_file": meta.destination_file() if named else "",
            "keep_source": meta.keep_source, "frozen": frozen, "check": check}


def cmd_stage(args: argparse.Namespace) -> int:
    title, destination = _title_arg(args.title), _destination_arg(args.destination)
    keep = None if args.keep_source is None else args.keep_source == "true"
    stage = _existing_stage(args.stem)
    try:
        meta = read_meta(stage)
    except MetaError as exc:
        raise UsageError(str(exc)) from exc
    frozen = apply_stage_update(meta, title=title, destination=destination, keep_source=keep)
    if not frozen:
        write_meta(stage, meta)
    _emit(_stage_output(meta, frozen, _resolve_and_check(stage, meta)))
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
    drop = sub.add_parser("drop", help="Remove the stage directory.")
    drop.add_argument("--stem", required=True)
    return p


COMMANDS = {"new": cmd_new, "stage": cmd_stage, "drop": cmd_drop}


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
