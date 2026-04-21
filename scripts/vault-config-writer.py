#!/usr/bin/env python3
# version: 0.2.0
"""vault-config-writer.py — deterministic section writer for vault-config.yaml.

The /explore-vault agent classifies and the user confirms — then this script
renders the YAML. Pattern: same as XDD 008's instruction-render.py. No more
LLM-composed vault-config sections.

Current subcommands:
  tags     Render/replace the top-level `tags:` block from JSON input matching
           tomo/schemas/vault-config-tags.schema.json.

Future subcommands (not implemented yet): relationships, callouts, trackers.

The writer does textual section replacement, not a full YAML round-trip, so
comments, formatting, and unrelated sections stay byte-for-byte identical.

Usage:
  python3 scripts/vault-config-writer.py tags \\
    --input tomo-tmp/tags.json \\
    --config config/vault-config.yaml

  # Dry-run — render to stdout, don't touch the file:
  python3 scripts/vault-config-writer.py tags \\
    --input tomo-tmp/tags.json --stdout

Exit codes:
  0 — success (section written or printed)
  1 — validation failure (input doesn't match the schema) or YAML would be
      invalid after writing (aborts before touching the target file)
  2 — I/O or argument error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent


# ──────────────────────────────────────────────────────────────────────────────
# Structural validation (lightweight — jsonschema isn't guaranteed available).
# Mirrors tomo/schemas/vault-config-tags.schema.json.
# ──────────────────────────────────────────────────────────────────────────────

ALLOWED_CONCEPTS = {
    "atomic_note", "map_note", "project", "area",
    "source", "asset", "template",
}

PREFIX_REQUIRED = {"description", "known_values", "wildcard", "required_for", "proposable"}


def _fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def validate_tags_input(data: dict) -> None:
    if not isinstance(data, dict):
        _fail("input must be a JSON object")
    if list(data.keys()) != ["prefixes"] and set(data.keys()) != {"prefixes"}:
        extra = set(data) - {"prefixes"}
        if extra:
            _fail(f"unexpected top-level keys: {sorted(extra)}")
    prefixes = data.get("prefixes")
    if not isinstance(prefixes, dict) or not prefixes:
        _fail("`prefixes` must be a non-empty object")
    for name, entry in prefixes.items():
        if not isinstance(name, str) or not name:
            _fail(f"prefix name must be a non-empty string, got: {name!r}")
        if not name[0].isalpha() or not all(c.isalnum() or c in "_-" for c in name):
            _fail(f"prefix name {name!r} must match [A-Za-z][A-Za-z0-9_-]*")
        if not isinstance(entry, dict):
            _fail(f"prefix {name!r}: entry must be an object")
        missing = PREFIX_REQUIRED - set(entry)
        if missing:
            _fail(f"prefix {name!r}: missing fields {sorted(missing)}")
        extra = set(entry) - PREFIX_REQUIRED
        if extra:
            _fail(f"prefix {name!r}: unexpected fields {sorted(extra)}")
        if not isinstance(entry["description"], str) or not entry["description"].strip():
            _fail(f"prefix {name!r}: description must be a non-empty string")
        kv = entry["known_values"]
        if not isinstance(kv, list) or any(not isinstance(v, str) or not v for v in kv):
            _fail(f"prefix {name!r}: known_values must be a list of non-empty strings")
        if not isinstance(entry["wildcard"], bool):
            _fail(f"prefix {name!r}: wildcard must be a bool (not {type(entry['wildcard']).__name__})")
        if not isinstance(entry["proposable"], bool):
            _fail(f"prefix {name!r}: proposable must be a bool (not {type(entry['proposable']).__name__})")
        rf = entry["required_for"]
        if not isinstance(rf, list):
            _fail(f"prefix {name!r}: required_for must be a list")
        for c in rf:
            if c not in ALLOWED_CONCEPTS:
                _fail(f"prefix {name!r}: required_for entry {c!r} not in {sorted(ALLOWED_CONCEPTS)}")
        if len(rf) != len(set(rf)):
            _fail(f"prefix {name!r}: required_for contains duplicates")


# ──────────────────────────────────────────────────────────────────────────────
# Rendering — hand-written so the output matches the format of vault-example.yaml
# (double-quoted strings, two-space indent, inline `[]` for empty lists).
# ──────────────────────────────────────────────────────────────────────────────

def _qstr(s: str) -> str:
    """Return a YAML-safe double-quoted string (piggybacks on JSON escaping)."""
    return json.dumps(s, ensure_ascii=False)


def render_tags_section(data: dict) -> str:
    """Render the `tags:` block (including the `tags:` root key itself)."""
    lines: list[str] = ["tags:", "  prefixes:"]
    for name, entry in data["prefixes"].items():
        lines.append(f"    {name}:")
        lines.append(f"      description: {_qstr(entry['description'])}")
        kv = entry["known_values"]
        if kv:
            lines.append("      known_values:")
            for v in kv:
                lines.append(f"        - {_qstr(v)}")
        else:
            lines.append("      known_values: []")
        lines.append(f"      wildcard: {'true' if entry['wildcard'] else 'false'}")
        lines.append(f"      proposable: {'true' if entry['proposable'] else 'false'}")
        rf = entry["required_for"]
        if rf:
            lines.append("      required_for:")
            for c in rf:
                lines.append(f"        - {c}")
        else:
            lines.append("      required_for: []")
        lines.append("")  # blank line between prefixes for readability
    # Drop trailing blank (we handle outer separation in the caller)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Textual section replacement — preserves everything outside the target key.
# ──────────────────────────────────────────────────────────────────────────────

def _is_top_level_key_line(line: str, key: str) -> bool:
    """`tags:` or `tags: # comment` or `tags: {}` at column 0."""
    stripped = line.rstrip("\n")
    if not stripped.startswith(f"{key}:"):
        return False
    after = stripped[len(key) + 1:]
    return after == "" or after.startswith(" ") or after.startswith("\t") or after.startswith("#")


def replace_top_level_section(yaml_text: str, section_key: str, new_block: str) -> str:
    """Replace the `<section_key>:` block at column 0. Preserve everything else.

    A "block" starts at the `<section_key>:` line and continues through
    contiguous indented or blank lines until the next column-0 key is found.

    If the section doesn't exist, the new block is appended (separated by a
    blank line from any preceding content).
    """
    new_block = new_block if new_block.endswith("\n") else new_block + "\n"
    lines = yaml_text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    n = len(lines)
    replaced = False

    while i < n:
        line = lines[i]
        if _is_top_level_key_line(line, section_key):
            out.append(new_block)
            i += 1
            # Consume all lines that belong to this section:
            # blank lines AND indented (starts with space/tab) lines.
            while i < n:
                nxt = lines[i]
                body = nxt.rstrip("\n")
                if body == "":
                    i += 1
                    continue
                if nxt.startswith((" ", "\t")):
                    i += 1
                    continue
                # Any other column-0 non-blank line — new section starts here.
                break
            replaced = True
            continue
        out.append(line)
        i += 1

    if not replaced:
        # Ensure a trailing newline on the previous content and a blank separator
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        if out and out[-1].strip() != "":
            out.append("\n")
        out.append(new_block)

    return "".join(out)


# ──────────────────────────────────────────────────────────────────────────────
# `tags` subcommand
# ──────────────────────────────────────────────────────────────────────────────

def cmd_tags(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return 1

    validate_tags_input(data)
    new_block = render_tags_section(data)

    if args.stdout:
        sys.stdout.write(new_block)
        return 0

    config_path = Path(args.config)
    try:
        current = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 2

    updated = replace_top_level_section(current, "tags", new_block)

    # Abort if the result wouldn't be valid YAML.
    try:
        yaml.safe_load(updated)
    except yaml.YAMLError as exc:
        print(f"error: resulting YAML would be invalid, refusing to write: {exc}", file=sys.stderr)
        return 1

    config_path.write_text(updated, encoding="utf-8")
    n_prefixes = len(data["prefixes"])
    print(
        f"vault-config-writer: tags block written ({n_prefixes} prefix(es)) → {config_path}",
        file=sys.stderr,
    )
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deterministic section writer for vault-config.yaml.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_tags = sub.add_parser("tags", help="Render/replace the top-level `tags:` block.")
    p_tags.add_argument(
        "--input", required=True,
        help="Path to JSON input matching tomo/schemas/vault-config-tags.schema.json",
    )
    p_tags.add_argument(
        "--config", default="config/vault-config.yaml",
        help="Path to vault-config.yaml (default: config/vault-config.yaml)",
    )
    p_tags.add_argument(
        "--stdout", action="store_true",
        help="Render the new block to stdout; do not modify --config.",
    )
    p_tags.set_defaults(func=cmd_tags)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
