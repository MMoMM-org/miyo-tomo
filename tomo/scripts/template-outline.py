#!/usr/bin/env python3
# version: 0.1.2
"""template-outline.py — List the points of one note template for /note.

Reads one template (through Kado, or a local file with --local) and prints its
outline as one JSON object on stdout:

  {"template": str,
   "frontmatter": [{key, has_value, line}],
   "headings": [{level, text, line, has_body}],
   "tokens": [{name, line, prefilled}],
   "templater": [{line, text}],
   "frontmatter_ok": bool}

A point is a heading, a frontmatter key or a token with prefilled false. The
parser is lib/template_syntax.py, the one the filled-note check uses.

--stage <stem>  reads tomo-tmp/note/<stem>/meta.json (source_path set means the
                source tokens are prefilled), then writes
                tomo-tmp/note/<stem>/template.md with every prefilled token but
                {{source_link}} replaced (generated values from the clock, config
                values from config/vault-config.yaml, source_path from meta.json;
                a token without a value becomes empty text) and
                tomo-tmp/note/<stem>/outline.json (the stdout object).
                {{source_link}} stays; note-instructions.py stage resolves it.
--out <file>    writes the stdout object to that file as well.

All files of one run are written together or not at all.

Paths are relative to the working directory (the instance root).

On exit 1 or a stage/write problem, stdout is {"template": str, "error": str};
the error names the error class and the Kado message, never template text.

Usage:
  python3 scripts/template-outline.py --template "Templates/t_meeting.md" --stage 2026-11-04_173005
  python3 scripts/template-outline.py --template "Templates/t_meeting.md" --out tomo-tmp/note/process-outline.json
  python3 scripts/template-outline.py --local tests/fixture.md

Exit codes:
  0  outline printed (also when frontmatter_ok is false)
  1  template unreadable (Kado error, missing local file, no text)
  2  bad invocation, unusable stage meta.json, or a local write failure

Design notes: docs/tomo/scripts/template-outline.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import template_syntax as ts  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.note_io import (  # noqa: E402
    ConfigError, ConfigNotMapping, load_vault_config, remove_temps, temp_sibling,
)
from lib.note_meta import MetaError, read_meta, stage_dir  # noqa: E402

CONFIG_PATH = Path("config") / "vault-config.yaml"


class OutlineError(Exception):
    """A problem that ends the run with an error object; carries the exit code."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List the points of one note template.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--template", help="vault path of the template (.md)")
    source.add_argument("--local", help="local template file (tests)")
    parser.add_argument("--stage", help="draft stem YYYY-MM-DD_HHMMSS")
    parser.add_argument("--out", help="file to write the outline JSON to")
    args = parser.parse_args(argv)
    if args.template is not None and not args.template.endswith(".md"):
        parser.error("--template must be a vault path ending in .md")
    if args.stage is not None:
        try:
            stage_dir(Path.cwd(), args.stage)
        except ValueError as exc:
            parser.error(f"--stage: {exc}")
    return args


def _read_template(args: argparse.Namespace) -> str:
    """Return the template text; OutlineError(code 1) when it cannot be read."""
    try:
        if args.local is not None:
            text = Path(args.local).read_text(encoding="utf-8")
        else:
            text = KadoClient().read_note(args.template).get("content")
    except KadoError as exc:
        raise OutlineError(f"{type(exc).__name__}: {exc}", 1) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise OutlineError(f"cannot read local template ({type(exc).__name__})", 1) from exc
    if not isinstance(text, str):
        raise OutlineError("Kado returned no text for the template", 1)
    return text


def _stage_source(stem: str) -> str | None:
    """Return the stage's source_path; OutlineError(code 2) on unusable meta.json."""
    try:
        return read_meta(stage_dir(Path.cwd(), stem)).source_path
    except MetaError as exc:
        raise OutlineError(f"stage {stem}: {exc}", 2) from exc


def build_outline(name: str, text: str, has_source: bool) -> dict:
    """Return the outline object of one template text."""
    return {
        "template": name,
        "frontmatter": ts.frontmatter_keys(text),
        "headings": ts.headings(text),
        "tokens": ts.tokens(text, has_source),
        "templater": ts.templater_spans(text),
        "frontmatter_ok": ts.frontmatter_ok(text),
    }


def _load_config() -> dict:
    """Return vault-config.yaml as a dict; {} when absent, not a mapping or unreadable."""
    if not CONFIG_PATH.is_file():
        return {}
    try:
        return load_vault_config(CONFIG_PATH)
    except ConfigNotMapping:
        return {}
    except ConfigError as exc:
        print(f"warning: vault-config.yaml unusable ({exc.cause})", file=sys.stderr)
        return {}


def prefilled_values(source_path: str | None) -> dict:
    """Values for the prefilled tokens: clock, config and (with a source) source_path."""
    values = {**ts.generated_values(_now()), **ts.config_values(_load_config())}
    if source_path:
        values["source_path"] = source_path
    return values


def _write_all(files: dict[Path, str]) -> None:
    """Write every file or none: .tmp siblings first, os.replace once all are written."""
    temps: dict[Path, Path] = {}
    try:
        for path, content in files.items():
            temps[path] = temp_sibling(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            temps[path].write_text(content, encoding="utf-8")
        for path, temp in temps.items():
            os.replace(temp, path)
    except OSError as exc:
        raise OutlineError(f"cannot write {path} ({type(exc).__name__})", 2) from exc
    finally:
        remove_temps(temps.values())


def _run(args: argparse.Namespace) -> dict:
    """Read, outline and write the requested files; return the outline."""
    source_path = _stage_source(args.stage) if args.stage else None
    text = _read_template(args)
    outline = build_outline(args.template or args.local, text, bool(source_path))
    dumped = json.dumps(outline, ensure_ascii=False, indent=2) + "\n"
    files: dict[Path, str] = {}
    if args.stage:
        stage = stage_dir(Path.cwd(), args.stage)
        values = prefilled_values(source_path)
        files[stage / "template.md"] = ts.resolve_prefilled(text, values, bool(source_path))
        files[stage / "outline.json"] = dumped
    if args.out:
        files[Path(args.out)] = dumped
    _write_all(files)
    return outline


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        outline = _run(args)
    except OutlineError as exc:
        error = {"template": args.template or args.local, "error": str(exc)}
        print(json.dumps(error, ensure_ascii=False))
        return exc.code
    print(json.dumps(outline, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
