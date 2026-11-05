#!/usr/bin/env python3
# note-session.py — Deterministic session start of /note.
# version: 0.1.1
"""Start a /note session: mode, draft state and template candidates; preview globs.

/note fills a vault template into a new note. This script makes its start the
same on every run: which mode the arguments select, which earlier drafts wait
for resume or drop, whether note templates are configured, and which templates
in ``templates.base_path`` match ``templates.note_include``. ``match`` previews
proposed globs during the first-run setup before anything is saved.

Usage (cwd = instance root):
    python3 scripts/note-session.py start --args="<$ARGUMENTS verbatim>"
    python3 scripts/note-session.py match --globs "t_*,i_*"

Output: one JSON object on stdout.
    start: mode, process_template, process_template_path, include_configured,
           note_include, kept_drafts, stale_stages, candidates, folder_listed,
           listing_error
    match: matched, unmatched, excluded_daily, folder_listed, listing_error

Rules:
    A leading ``--process`` token selects process mode; the rest of the text,
    with one pair of surrounding quotes and one trailing ``.md`` removed, is the
    template stem. An empty stem makes no Kado call. Any other text is note mode
    and appears in neither stdout nor stderr.
    The template folder is listed with depth 1; only ``.md`` files count.
    Globs match the filename without ``.md``, case-sensitively. The daily
    template (``templates.mapping.daily``, ``.md`` optional) is never a
    candidate or a match.
    ``listing_error`` is Kado's error text, or ``<class>: <message>`` for a
    transport error; a failed listing still exits 0. JSON is ASCII-escaped.

Exit codes:
    0 — output usable (also on a listing failure or a missing config)
    2 — bad invocation (unknown subcommand, missing argument, empty glob list)

Design notes: docs/tomo/scripts/note-session.md
"""
from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.note_meta import list_stages  # noqa: E402

PROCESS_FLAG = "--process"
NO_BASE_PATH = "templates.base_path is not set in vault-config.yaml"


# ---------------------------------------------------------------- config

def load_config(path: str) -> dict:
    """Return vault-config.yaml as a dict; empty (one stderr line) when unusable."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"note-session: config unusable ({type(exc).__name__})", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def templates_section(cfg: dict) -> dict:
    section = cfg.get("templates")
    return section if isinstance(section, dict) else {}


def note_include(templates: dict) -> list[str]:
    """Return the configured globs; empty unless a non-empty list of non-empty strings."""
    value = templates.get("note_include")
    if not isinstance(value, list) or not value:
        return []
    if not all(isinstance(g, str) and g.strip() for g in value):
        return []
    return list(value)


def daily_stem(templates: dict) -> str:
    """Return the daily template's stem: basename with an optional ``.md`` removed."""
    mapping = templates.get("mapping")
    value = mapping.get("daily") if isinstance(mapping, dict) else None
    if not isinstance(value, str) or not value.strip():
        return ""
    return PurePosixPath(value.strip()).name.removesuffix(".md")


# ---------------------------------------------------------------- listing

def list_templates(base_path: object) -> tuple[list[dict], str]:
    """Return ``([{path, stem}], listing_error)`` for the .md files in base_path."""
    if not isinstance(base_path, str) or not base_path.strip():
        return [], NO_BASE_PATH
    try:
        items = KadoClient().list_dir(base_path, depth=1)
    except KadoError as exc:
        return [], str(exc)
    except (OSError, TimeoutError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    files = [i["path"] for i in items
             if i.get("type") == "file" and str(i.get("path", "")).endswith(".md")]
    return [{"path": p, "stem": PurePosixPath(p).name[:-3]} for p in files], ""


def matches(stem: str, globs: list[str]) -> bool:
    return any(fnmatchcase(stem, g) for g in globs)


# ---------------------------------------------------------------- start

def parse_args_text(text: str) -> tuple[str, str]:
    """Return ``(mode, process_template)`` from the $ARGUMENTS text."""
    parts = text.split(maxsplit=1)
    if not parts or parts[0] != PROCESS_FLAG:
        return "note", ""
    stem = parts[1].strip() if len(parts) > 1 else ""
    if len(stem) >= 2 and stem[0] == stem[-1] and stem[0] in "\"'":
        stem = stem[1:-1].strip()
    return "process", stem.removesuffix(".md")


def process_path(templates_found: list[dict], stem: str) -> str:
    if not stem:
        return ""
    return next((t["path"] for t in templates_found if t["stem"] == stem), "")


def note_candidates(found: list[dict], globs: list[str], daily: str) -> list[dict]:
    return [t for t in found if t["stem"] != daily and matches(t["stem"], globs)]


def start(args: argparse.Namespace) -> dict:
    mode, stem = parse_args_text(args.args)
    templates = templates_section(load_config(args.config))
    globs = note_include(templates)
    stages = list_stages(Path.cwd())
    found, error = [], ""
    if (mode == "process" and stem) or (mode == "note" and globs):
        found, error = list_templates(templates.get("base_path"))
    candidates = note_candidates(found, globs, daily_stem(templates))
    return {
        "mode": mode,
        "process_template": stem,
        "process_template_path": process_path(found, stem),
        "include_configured": bool(globs),
        "note_include": globs,
        "kept_drafts": stages.kept_drafts,
        "stale_stages": stages.stale_stages,
        "candidates": candidates,
        "folder_listed": len(found),
        "listing_error": error,
    }


# ---------------------------------------------------------------- match

def split_globs(text: str) -> list[str]:
    return [g.strip() for g in text.split(",") if g.strip()]


def match(args: argparse.Namespace, globs: list[str]) -> dict:
    templates = templates_section(load_config(args.config))
    found, error = list_templates(templates.get("base_path"))
    daily = daily_stem(templates)
    stems = [t["stem"] for t in found]
    kept = [s for s in stems if s != daily]
    return {
        "matched": [s for s in kept if matches(s, globs)],
        "unmatched": [s for s in kept if not matches(s, globs)],
        "excluded_daily": daily if daily in stems else "",
        "folder_listed": len(found),
        "listing_error": error,
    }


# ---------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Session start and glob preview for /note.")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("start", help="Mode, kept drafts, candidates")
    s.add_argument("--args", required=True, help="$ARGUMENTS verbatim (use --args=<text>)")
    m = sub.add_parser("match", help="Preview proposed note_include globs")
    m.add_argument("--globs", required=True, help="Comma-separated filename globs")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "start":
        result = start(args)
    else:
        globs = split_globs(args.globs)
        if not globs:
            print("note-session: match needs at least one glob", file=sys.stderr)
            return 2
        result = match(args, globs)
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
