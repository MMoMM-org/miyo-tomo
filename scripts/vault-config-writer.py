#!/usr/bin/env python3
# version: 0.3.0
"""vault-config-writer.py — deterministic section writer for vault-config.yaml.

The /explore-vault agent classifies and the user confirms — then this script
renders the YAML. Pattern: same as XDD 008's instruction-render.py. No more
LLM-composed vault-config sections.

Subcommands (one per top-level vault-config section):
  tags           → tomo/schemas/vault-config-tags.schema.json
  relationships  → tomo/schemas/vault-config-relationships.schema.json
  callouts       → tomo/schemas/vault-config-callouts.schema.json
  trackers       → tomo/schemas/vault-config-trackers.schema.json

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
# Shared section-write flow — every subcommand uses the same pipeline:
#   load JSON → validate → render → (stdout OR replace → verify-YAML → write)
# ──────────────────────────────────────────────────────────────────────────────

def _run_section_command(
    args: argparse.Namespace,
    section_key: str,
    validator,
    renderer,
    summary_fn,
) -> int:
    input_path = Path(args.input)
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return 1

    validator(data)
    new_block = renderer(data)

    if args.stdout:
        sys.stdout.write(new_block)
        return 0

    config_path = Path(args.config)
    try:
        current = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 2

    updated = replace_top_level_section(current, section_key, new_block)

    try:
        yaml.safe_load(updated)
    except yaml.YAMLError as exc:
        print(f"error: resulting YAML would be invalid, refusing to write: {exc}", file=sys.stderr)
        return 1

    config_path.write_text(updated, encoding="utf-8")
    print(
        f"vault-config-writer: {section_key} block written ({summary_fn(data)}) → {config_path}",
        file=sys.stderr,
    )
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# `tags` subcommand
# ──────────────────────────────────────────────────────────────────────────────

def cmd_tags(args: argparse.Namespace) -> int:
    return _run_section_command(
        args, "tags",
        validate_tags_input,
        render_tags_section,
        lambda d: f"{len(d['prefixes'])} prefix(es)",
    )


# ──────────────────────────────────────────────────────────────────────────────
# `relationships` subcommand
# ──────────────────────────────────────────────────────────────────────────────

RELATIONSHIP_REQUIRED = {"marker", "format", "position", "location_type", "multi", "separator"}
RELATIONSHIP_POSITIONS = {"connect_callout", "frontmatter", "top_of_body", "end_of_frontmatter"}
RELATIONSHIP_LOCATION_TYPES = {"inline", "frontmatter"}


def validate_relationships_input(data: dict) -> None:
    if not isinstance(data, dict) or not data:
        _fail("relationships input must be a non-empty object keyed by relationship name")
    for name, entry in data.items():
        if not isinstance(name, str) or not name or not name[0].islower():
            _fail(f"relationship name {name!r} must be lowercase [a-z][a-z0-9_]*")
        if not all(c.isalnum() or c == "_" for c in name):
            _fail(f"relationship name {name!r} must be [a-z][a-z0-9_]*")
        if not isinstance(entry, dict):
            _fail(f"relationship {name!r}: entry must be an object")
        missing = RELATIONSHIP_REQUIRED - set(entry)
        if missing:
            _fail(f"relationship {name!r}: missing fields {sorted(missing)}")
        extra = set(entry) - RELATIONSHIP_REQUIRED
        if extra:
            _fail(f"relationship {name!r}: unexpected fields {sorted(extra)}")
        if not isinstance(entry["marker"], str) or not entry["marker"].strip():
            _fail(f"relationship {name!r}: marker must be a non-empty string")
        if not isinstance(entry["format"], str) or "{{link}}" not in entry["format"]:
            _fail(f"relationship {name!r}: format must be a string containing {{{{link}}}}")
        if entry["position"] not in RELATIONSHIP_POSITIONS:
            _fail(f"relationship {name!r}: position must be one of {sorted(RELATIONSHIP_POSITIONS)}")
        if entry["location_type"] not in RELATIONSHIP_LOCATION_TYPES:
            _fail(f"relationship {name!r}: location_type must be inline or frontmatter")
        if not isinstance(entry["multi"], bool):
            _fail(f"relationship {name!r}: multi must be a bool")
        if not isinstance(entry["separator"], str) or not entry["separator"]:
            _fail(f"relationship {name!r}: separator must be a non-empty string")


def render_relationships_section(data: dict) -> str:
    lines = ["relationships:"]
    for name, entry in data.items():
        lines.append(f"  {name}:")
        lines.append(f"    marker: {_qstr(entry['marker'])}")
        lines.append(f"    format: {_qstr(entry['format'])}")
        lines.append(f"    position: {_qstr(entry['position'])}")
        lines.append(f"    location_type: {_qstr(entry['location_type'])}")
        lines.append(f"    multi: {'true' if entry['multi'] else 'false'}")
        lines.append(f"    separator: {_qstr(entry['separator'])}")
    return "\n".join(lines) + "\n"


def cmd_relationships(args: argparse.Namespace) -> int:
    return _run_section_command(
        args, "relationships",
        validate_relationships_input,
        render_relationships_section,
        lambda d: f"{len(d)} relationship type(s)",
    )


# ──────────────────────────────────────────────────────────────────────────────
# `callouts` subcommand
# ──────────────────────────────────────────────────────────────────────────────

CALLOUT_BUCKETS = ("editable", "protected", "ignore")
CALLOUT_ALLOWED_TOP = {"enabled", *CALLOUT_BUCKETS}


def validate_callouts_input(data: dict) -> None:
    if not isinstance(data, dict):
        _fail("callouts input must be an object")
    if "enabled" not in data:
        _fail("callouts input missing required field: enabled")
    if not isinstance(data["enabled"], bool):
        _fail("callouts.enabled must be a bool")
    extra = set(data) - CALLOUT_ALLOWED_TOP
    if extra:
        _fail(f"callouts: unexpected top-level fields {sorted(extra)}")
    for bucket in CALLOUT_BUCKETS:
        if bucket not in data:
            continue
        bucket_data = data[bucket]
        if not isinstance(bucket_data, dict):
            _fail(f"callouts.{bucket} must be an object (name → description)")
        for cname, cdesc in bucket_data.items():
            if not isinstance(cname, str) or not cname or not cname[0].isalpha():
                _fail(f"callouts.{bucket}: name {cname!r} must match [A-Za-z][A-Za-z0-9_-]*")
            if not all(c.isalnum() or c in "_-" for c in cname):
                _fail(f"callouts.{bucket}: name {cname!r} has invalid characters")
            if not isinstance(cdesc, str) or not cdesc.strip():
                _fail(f"callouts.{bucket}.{cname}: description must be a non-empty string")


def render_callouts_section(data: dict) -> str:
    lines = ["callouts:"]
    lines.append(f"  enabled: {'true' if data['enabled'] else 'false'}")
    for bucket in CALLOUT_BUCKETS:
        entries = data.get(bucket) or {}
        if not entries:
            continue
        lines.append("")
        lines.append(f"  {bucket}:")
        for name, desc in entries.items():
            lines.append(f"    {name}: {_qstr(desc)}")
    return "\n".join(lines) + "\n"


def cmd_callouts(args: argparse.Namespace) -> int:
    return _run_section_command(
        args, "callouts",
        validate_callouts_input,
        render_callouts_section,
        lambda d: (
            f"enabled={d['enabled']}, "
            + ", ".join(f"{b}={len(d.get(b) or {})}" for b in CALLOUT_BUCKETS)
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# `trackers` subcommand
# ──────────────────────────────────────────────────────────────────────────────

TRACKER_FIELD_REQUIRED = {"name", "type", "syntax", "description"}
TRACKER_FIELD_ALLOWED = TRACKER_FIELD_REQUIRED | {
    "scale", "positive_keywords", "negative_keywords", "keywords",
}
TRACKER_TYPES = {"boolean", "integer", "text", "duration", "time"}
TRACKER_SYNTAXES = {"inline_field", "callout_body", "task_checkbox", "checkbox"}


def _validate_tracker_field(entry: dict, path: str) -> None:
    if not isinstance(entry, dict):
        _fail(f"{path}: must be an object")
    missing = TRACKER_FIELD_REQUIRED - set(entry)
    if missing:
        _fail(f"{path}: missing fields {sorted(missing)}")
    extra = set(entry) - TRACKER_FIELD_ALLOWED
    if extra:
        _fail(f"{path}: unexpected fields {sorted(extra)}")
    if not isinstance(entry["name"], str) or not entry["name"].strip():
        _fail(f"{path}: name must be a non-empty string")
    if entry["type"] not in TRACKER_TYPES:
        _fail(f"{path}: type must be one of {sorted(TRACKER_TYPES)}")
    if entry["syntax"] not in TRACKER_SYNTAXES:
        _fail(f"{path}: syntax must be one of {sorted(TRACKER_SYNTAXES)}")
    if not isinstance(entry["description"], str) or not entry["description"].strip():
        _fail(f"{path}: description must be a non-empty string")
    for key in ("positive_keywords", "negative_keywords", "keywords"):
        if key in entry:
            if not isinstance(entry[key], list):
                _fail(f"{path}.{key}: must be a list")
            for kw in entry[key]:
                if not isinstance(kw, str) or not kw.strip():
                    _fail(f"{path}.{key}: items must be non-empty strings")
    if "scale" in entry and entry["scale"] is not None:
        if not isinstance(entry["scale"], str):
            _fail(f"{path}.scale: must be a string or null")


def validate_trackers_input(data: dict) -> None:
    if not isinstance(data, dict):
        _fail("trackers input must be an object")
    if "daily_note_trackers" not in data:
        _fail("trackers input missing required: daily_note_trackers")
    extra = set(data) - {"daily_note_trackers", "end_of_day_fields"}
    if extra:
        _fail(f"trackers: unexpected top-level fields {sorted(extra)}")

    dnt = data["daily_note_trackers"]
    if not isinstance(dnt, dict):
        _fail("trackers.daily_note_trackers must be an object")
    dnt_extra = set(dnt) - {"section", "today_fields", "yesterday_fields"}
    if dnt_extra:
        _fail(f"trackers.daily_note_trackers: unexpected fields {sorted(dnt_extra)}")
    if "today_fields" not in dnt:
        _fail("trackers.daily_note_trackers missing required: today_fields")
    if "section" in dnt and (not isinstance(dnt["section"], str) or not dnt["section"].strip()):
        _fail("trackers.daily_note_trackers.section must be a non-empty string")
    for key in ("today_fields", "yesterday_fields"):
        fields = dnt.get(key)
        if fields is None:
            continue
        if not isinstance(fields, list):
            _fail(f"trackers.daily_note_trackers.{key} must be a list")
        for i, f in enumerate(fields):
            _validate_tracker_field(f, f"trackers.daily_note_trackers.{key}[{i}]")

    eod = data.get("end_of_day_fields")
    if eod is not None:
        if not isinstance(eod, dict):
            _fail("trackers.end_of_day_fields must be an object")
        eod_extra = set(eod) - {"section", "fields"}
        if eod_extra:
            _fail(f"trackers.end_of_day_fields: unexpected fields {sorted(eod_extra)}")
        if "fields" not in eod:
            _fail("trackers.end_of_day_fields missing required: fields")
        if "section" in eod and (not isinstance(eod["section"], str) or not eod["section"].strip()):
            _fail("trackers.end_of_day_fields.section must be a non-empty string")
        if not isinstance(eod["fields"], list):
            _fail("trackers.end_of_day_fields.fields must be a list")
        for i, f in enumerate(eod["fields"]):
            _validate_tracker_field(f, f"trackers.end_of_day_fields.fields[{i}]")


def _render_tracker_field(entry: dict, indent: str) -> list[str]:
    lines = [f"{indent}- name: {_qstr(entry['name'])}"]
    child = indent + "  "
    lines.append(f"{child}type: {_qstr(entry['type'])}")
    lines.append(f"{child}syntax: {_qstr(entry['syntax'])}")
    if entry.get("scale"):
        lines.append(f"{child}scale: {_qstr(entry['scale'])}")
    lines.append(f"{child}description: {_qstr(entry['description'])}")
    for key in ("keywords", "positive_keywords", "negative_keywords"):
        vals = entry.get(key)
        if not vals:
            continue
        inner = ", ".join(_qstr(v) for v in vals)
        lines.append(f"{child}{key}: [{inner}]")
    return lines


def render_trackers_section(data: dict) -> str:
    lines = ["trackers:"]
    dnt = data["daily_note_trackers"]
    lines.append("  daily_note_trackers:")
    if dnt.get("section"):
        lines.append(f"    section: {_qstr(dnt['section'])}")
    for key in ("today_fields", "yesterday_fields"):
        fields = dnt.get(key)
        if not fields:
            continue
        lines.append(f"    {key}:")
        for f in fields:
            lines.extend(_render_tracker_field(f, "      "))
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
    eod = data.get("end_of_day_fields")
    if eod:
        lines.append("")
        lines.append("  end_of_day_fields:")
        if eod.get("section"):
            lines.append(f"    section: {_qstr(eod['section'])}")
        lines.append("    fields:")
        for f in eod["fields"]:
            lines.extend(_render_tracker_field(f, "      "))
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
    return "\n".join(lines) + "\n"


def cmd_trackers(args: argparse.Namespace) -> int:
    def _summary(d: dict) -> str:
        dnt = d["daily_note_trackers"]
        today = len(dnt.get("today_fields") or [])
        yest = len(dnt.get("yesterday_fields") or [])
        eod = len((d.get("end_of_day_fields") or {}).get("fields") or [])
        return f"today={today} yesterday={yest} end_of_day={eod}"
    return _run_section_command(
        args, "trackers",
        validate_trackers_input,
        render_trackers_section,
        _summary,
    )


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deterministic section writer for vault-config.yaml.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _common_args(sp, schema_name: str) -> None:
        sp.add_argument(
            "--input", required=True,
            help=f"Path to JSON input matching tomo/schemas/{schema_name}.schema.json",
        )
        sp.add_argument(
            "--config", default="config/vault-config.yaml",
            help="Path to vault-config.yaml (default: config/vault-config.yaml)",
        )
        sp.add_argument(
            "--stdout", action="store_true",
            help="Render the new block to stdout; do not modify --config.",
        )

    p_tags = sub.add_parser("tags", help="Render/replace the top-level `tags:` block.")
    _common_args(p_tags, "vault-config-tags")
    p_tags.set_defaults(func=cmd_tags)

    p_rel = sub.add_parser("relationships", help="Render/replace the top-level `relationships:` block.")
    _common_args(p_rel, "vault-config-relationships")
    p_rel.set_defaults(func=cmd_relationships)

    p_cal = sub.add_parser("callouts", help="Render/replace the top-level `callouts:` block.")
    _common_args(p_cal, "vault-config-callouts")
    p_cal.set_defaults(func=cmd_callouts)

    p_trk = sub.add_parser("trackers", help="Render/replace the top-level `trackers:` block.")
    _common_args(p_trk, "vault-config-trackers")
    p_trk.set_defaults(func=cmd_trackers)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
