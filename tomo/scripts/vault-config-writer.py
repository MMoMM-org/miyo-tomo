#!/usr/bin/env python3
# version: 0.5.3
"""vault-config-writer.py — deterministic section writer for vault-config.yaml.

The /explore-vault agent classifies and the user confirms — then this script
renders the YAML. Pattern: same as XDD 008's instruction-render.py. No more
LLM-composed vault-config sections.

Subcommands (one per top-level vault-config section):
  tags              → tomo/schemas/vault-config-tags.schema.json
  relationships     → tomo/schemas/vault-config-relationships.schema.json
  callouts          → tomo/schemas/vault-config-callouts.schema.json
  trackers          → tomo/schemas/vault-config-trackers.schema.json
  templates-include → tomo/schemas/vault-config-templates.schema.json
                      (input {"note_include": [...]}; inserts or replaces only
                      the templates.note_include lines, never the whole
                      templates: block; appends a templates: block if absent)

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
import os
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

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
    stripped = line.rstrip("\r\n")
    if not stripped.startswith(f"{key}:"):
        return False
    after = stripped[len(key) + 1:]
    return after == "" or after.startswith(" ") or after.startswith("\t") or after.startswith("#")


def replace_top_level_section(
    yaml_text: str, section_key: str, new_block: str, newline: str = "\n",
) -> str:
    """Replace the `<section_key>:` block at column 0. Preserve everything else.

    A "block" starts at the `<section_key>:` line and continues through
    contiguous indented or blank lines until the next column-0 key is found.

    If the section doesn't exist, the new block is appended (separated by a
    blank line from any preceding content). `newline` is the line ending
    used for the separator lines the append adds.
    """
    new_block = new_block if new_block.endswith("\n") else new_block + newline
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
            out[-1] += newline
        if out and out[-1].strip() != "":
            out.append(newline)
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
    preserve_fn=None,
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

    # A section write REPLACES its whole block, so any user-curated key the
    # caller does not resupply is destroyed. `preserve_fn` carries those keys
    # forward from the config on disk. It runs BEFORE the --stdout branch so
    # the preview shows what would actually be written, not a version missing
    # everything the preservation would have restored.
    config_path = Path(args.config)
    if preserve_fn is not None:
        try:
            existing = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (FileNotFoundError, yaml.YAMLError):
            existing = {}
        preserve_fn(data, existing)

    new_block = renderer(data)

    if args.stdout:
        sys.stdout.write(new_block)
        return 0

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
    "scale", "positive_keywords", "negative_keywords", "keywords", "active",
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
    if "active" in entry and not isinstance(entry["active"], bool):
        _fail(f"{path}.active: must be true or false")
    if "scale" in entry and entry["scale"] is not None:
        if not isinstance(entry["scale"], str):
            _fail(f"{path}.scale: must be a string or null")


def validate_trackers_input(data: dict) -> None:
    if not isinstance(data, dict):
        _fail("trackers input must be an object")
    if "enabled" in data and not isinstance(data["enabled"], bool):
        _fail("trackers.enabled: must be true or false")
    if "daily_note_trackers" not in data:
        _fail("trackers input missing required: daily_note_trackers")
    extra = set(data) - {"daily_note_trackers", "end_of_day_fields", "enabled"}
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
    # Only written when explicitly false — absent means active, and emitting
    # `active: true` on every field would add noise to a 15-field block.
    if entry.get("active") is False:
        lines.append(f"{child}active: false")
    for key in ("keywords", "positive_keywords", "negative_keywords"):
        vals = entry.get(key)
        if not vals:
            continue
        inner = ", ".join(_qstr(v) for v in vals)
        lines.append(f"{child}{key}: [{inner}]")
    return lines


def render_trackers_section(data: dict) -> str:
    lines = ["trackers:"]
    # Written only when explicitly false, mirroring per-field `active`:
    # absent means enabled, so an untouched config gains no new line.
    if data.get("enabled") is False:
        lines.append("  enabled: false")
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


# Keys a person curates and a rediscovery pass does not know how to produce.
# Absent from the incoming JSON means "not supplied", never "cleared" — the
# writer carries the existing value forward instead of dropping it.
TRACKER_CURATED_KEYS = ("keywords", "positive_keywords", "negative_keywords", "active")


def _tracker_lists(block: dict):
    """Yield (list_name, fields) for every tracker-field list in a block."""
    dnt = (block.get("daily_note_trackers") or {}) if isinstance(block, dict) else {}
    for key in ("today_fields", "yesterday_fields"):
        fields = dnt.get(key)
        if isinstance(fields, list):
            yield f"daily_note_trackers.{key}", fields
    eod = (block.get("end_of_day_fields") or {}) if isinstance(block, dict) else {}
    fields = eod.get("fields")
    if isinstance(fields, list):
        yield "end_of_day_fields.fields", fields


def preserve_curated_tracker_keys(data: dict, existing_config: dict) -> list[str]:
    """Carry curated tracker keys from the config on disk into `data`, in place.

    WHY this exists: `/explore-vault` rediscovers tracker fields by scanning
    daily notes and emits name/type/syntax/description only. The writer then
    replaces the whole `trackers:` block, so every keyword list a person had
    entered through `tomo-trackers-wizard` was silently destroyed — and the
    only visible symptom was that trackers quietly stopped matching, which
    reads as "nothing matched" rather than "the configuration is gone".

    Matching is by (list, field name). A renamed or removed field keeps
    nothing: that is a real change the caller is making, not an omission.

    Returns the "<list>.<name>.<key>" paths it restored, for reporting —
    a preservation nobody is told about is only half a fix.
    """
    old_block = existing_config.get("trackers") or {}

    # The master switch is curated the same way a keyword list is, and a
    # rediscovery pass has no opinion about it — carry it forward unless the
    # caller states one.
    restored: list[str] = []
    if "enabled" not in data and isinstance(old_block.get("enabled"), bool):
        data["enabled"] = old_block["enabled"]
        restored.append("trackers.enabled")

    old_by_key: dict[tuple[str, str], dict] = {}
    for list_name, fields in _tracker_lists(old_block):
        for f in fields:
            if isinstance(f, dict) and isinstance(f.get("name"), str):
                old_by_key[(list_name, f["name"])] = f

    for list_name, fields in _tracker_lists(data):
        for f in fields:
            if not isinstance(f, dict):
                continue
            old = old_by_key.get((list_name, f.get("name")))
            if not old:
                continue
            for key in TRACKER_CURATED_KEYS:
                if key not in f and key in old:
                    f[key] = old[key]
                    restored.append(f"{list_name}.{f['name']}.{key}")
    return restored


def _preserve_trackers(data: dict, existing_config: dict) -> None:
    restored = preserve_curated_tracker_keys(data, existing_config)
    if restored:
        print(
            f"vault-config-writer: preserved {len(restored)} curated tracker "
            f"value(s) the input did not supply: {', '.join(restored)}",
            file=sys.stderr,
        )


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
        preserve_fn=_preserve_trackers,
    )


# ──────────────────────────────────────────────────────────────────────────────
# `templates-include` subcommand — edits ONE key inside `templates:`
# (templates.note_include), never the rest of the hand-curated block.
# ──────────────────────────────────────────────────────────────────────────────

TEMPLATES_INCLUDE_KEY = "note_include"


def validate_templates_include_input(data) -> None:
    if not isinstance(data, dict):
        _fail("templates-include input must be a JSON object")
    extra = set(data) - {TEMPLATES_INCLUDE_KEY}
    if extra:
        _fail(f"templates-include: {len(extra)} unexpected top-level key(s); "
              f"only {TEMPLATES_INCLUDE_KEY} is allowed")
    globs = data.get(TEMPLATES_INCLUDE_KEY)
    if not isinstance(globs, list) or not globs:
        _fail("templates-include: note_include must be a non-empty list")
    for i, g in enumerate(globs):
        if not isinstance(g, str) or not g.strip():
            _fail(f"templates-include: note_include[{i}] must be a non-empty string")
        if g != g.strip():
            _fail(f"templates-include: note_include[{i}] has leading or trailing whitespace; "
                  "remove it, a padded glob never matches a filename")


def render_templates_include_lines(
    globs: list[str], indent: str = "  ", newline: str = "\n",
) -> str:
    lines = [f"{indent}{TEMPLATES_INCLUDE_KEY}:"]
    lines.extend(f"{indent}  - {_qstr(g)}" for g in globs)
    return newline.join(lines) + newline


def _newline_of(text: str) -> str:
    """The ending of the file's first line: CRLF files get CRLF insertions."""
    first = text.find("\n")
    return "\r\n" if first > 0 and text[first - 1] == "\r" else "\n"


def _leading_ws(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def _section_extent(lines: list[str], section_key: str) -> tuple[int, int] | None:
    """(header index, index after the last non-blank body line) or None."""
    start = next((i for i, ln in enumerate(lines) if _is_top_level_key_line(ln, section_key)), None)
    if start is None:
        return None
    end = last = start + 1
    while end < len(lines) and (lines[end].strip() == "" or lines[end].startswith((" ", "\t"))):
        end += 1
        if lines[end - 1].strip():
            last = end
    return start, last


def _child_indent(body: list[str]) -> str:
    for ln in body:
        if ln.strip() and not ln.lstrip().startswith("#"):
            return _leading_ws(ln)
    return "  "


def _is_key_line(line: str, indent: str, key: str) -> bool:
    """`<indent>key:`, plain or quoted — YAML reads all three as the same key."""
    spellings = (f"{key}:", f'"{key}":', f"'{key}':")
    return _leading_ws(line) == indent and line.lstrip().startswith(spellings)


def _is_list_continuation(line: str, indent: str) -> bool:
    ws = _leading_ws(line)
    return bool(line.strip()) and (
        len(ws) > len(indent) or (ws == indent and line.lstrip().startswith("- "))
    )


def _key_extent(body: list[str], indent: str, key: str) -> tuple[int, int] | None:
    """Span of the key line through its last non-comment continuation line.

    Comment lines after the last list item stay outside the span (they are the
    user's); comments between items are inside it and are replaced with the list.
    """
    for i, ln in enumerate(body):
        if not _is_key_line(ln, indent, key):
            continue
        end = j = i + 1
        while j < len(body) and _is_list_continuation(body[j], indent):
            j += 1
            if not body[j - 1].lstrip().startswith("#"):
                end = j
        return i, end
    return None


def set_templates_note_include(yaml_text: str, globs: list[str]) -> str:
    """Insert or replace the templates.note_include lines only; keep every other byte."""
    section_key, key = "templates", TEMPLATES_INCLUDE_KEY
    nl = _newline_of(yaml_text)
    lines = yaml_text.splitlines(keepends=True)
    extent = _section_extent(lines, section_key)
    if extent is None:
        block = f"{section_key}:{nl}" + render_templates_include_lines(globs, newline=nl)
        return replace_top_level_section(yaml_text, section_key, block, newline=nl)
    start, last = extent
    body = lines[start + 1:last]
    indent = _child_indent(body)
    rendered = render_templates_include_lines(globs, indent, newline=nl)
    span = _key_extent(body, indent, key)
    lo, hi = (start + 1 + span[0], start + 1 + span[1]) if span else (last, last)
    if lo > 0 and not lines[lo - 1].endswith("\n"):
        lines[lo - 1] += nl
    return "".join(lines[:lo]) + rendered + "".join(lines[hi:])


_MERGE_TAG = "tag:yaml.org,2002:merge"
_KEY_CONSTRUCTOR = yaml.SafeLoader("")  # builds scalar keys the way safe_load does


_UNCOMPARABLE = object()


class KeyRepeat(NamedTuple):
    count: int
    lines: tuple[int, ...]  # 1-based line of each occurrence, in file order


def _key_identity(key_node):
    """The key as safe_load would build it, or _UNCOMPARABLE."""
    if not isinstance(key_node, yaml.ScalarNode) or key_node.tag == _MERGE_TAG:
        return _UNCOMPARABLE
    try:
        key = _KEY_CONSTRUCTOR.construct_object(key_node, deep=True)
        hash(key)
    except (yaml.YAMLError, TypeError):
        return _UNCOMPARABLE
    return key


def _collect_key_lines(node, path: tuple, lines: dict, seen: set) -> None:
    """Record {key path: [1-based line of each occurrence]} for every mapping key."""
    if node is None or id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, yaml.SequenceNode):
        for i, child in enumerate(node.value):
            _collect_key_lines(child, path + (i,), lines, seen)
    elif isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            key = _key_identity(key_node)
            if key is _UNCOMPARABLE:
                continue
            lines.setdefault(path + (key,), []).append(key_node.start_mark.line + 1)
            _collect_key_lines(value_node, path + (key,), lines, seen)


def _duplicate_keys(text: str) -> dict[tuple, KeyRepeat]:
    """{key path: KeyRepeat} for repeated keys.

    Plain safe_load keeps the last duplicate, so a shadowing second
    `templates:` or `note_include` would otherwise pass the read-back.
    """
    lines: dict[tuple, list[int]] = {}
    _collect_key_lines(yaml.compose(text, Loader=yaml.SafeLoader), (), lines, set())
    return {p: KeyRepeat(len(ls), tuple(ls)) for p, ls in lines.items() if len(ls) > 1}


def _describe_yaml_error(exc: yaml.YAMLError) -> str:
    """Class name and line only: the PyYAML message quotes config text."""
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    return type(exc).__name__ + (f" at line {mark.line + 1}" if mark else "")


def _duplicate_refusal(original: str, updated: str) -> str | None:
    """Why the result must not be written, or None. Never names a key or value."""
    try:
        after = _duplicate_keys(updated)
    except yaml.YAMLError as exc:
        return f"resulting YAML is not usable ({_describe_yaml_error(exc)})"
    try:
        before = _duplicate_keys(original)
    except yaml.YAMLError:
        before = {}
    introduced = []
    for path, rep in after.items():
        prior = before[path].count if path in before else 1
        if rep.count > prior:
            introduced.append(rep.lines[prior])  # first copy the edit added
    if introduced:
        return (f"duplicate mapping key introduced by the edit "
                f"(line {min(introduced)} of the result)")
    shadowed = [rep.lines[1] for p, rep in before.items() if p[0] == "templates"]
    if shadowed:
        return (f"pre-existing duplicate key in the templates: block, already in the config "
                f"(line {min(shadowed)}); the edit could land in the copy YAML ignores, "
                "fix the file first")
    return None


def _reads_back(updated: str, globs: list[str]) -> bool:
    try:
        parsed = yaml.safe_load(updated)
    except yaml.YAMLError as exc:
        print(f"error: resulting YAML is not usable ({_describe_yaml_error(exc)})", file=sys.stderr)
        return False
    templates = parsed.get("templates") if isinstance(parsed, dict) else None
    return isinstance(templates, dict) and templates.get(TEMPLATES_INCLUDE_KEY) == globs


def _load_json_input(path: Path):
    """Return (data, None) or (None, exit code) — mirrors _run_section_command."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        print(f"error: input file not found: {path}", file=sys.stderr)
        return None, 2
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        return None, 1


def _atomic_write(path: Path, text: str) -> None:
    """Write via a same-directory temp file + os.replace, keeping the mode bits."""
    mode = path.stat().st_mode & 0o7777
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def cmd_templates_include(args: argparse.Namespace) -> int:
    data, rc = _load_json_input(Path(args.input))
    if rc is not None:
        return rc
    validate_templates_include_input(data)
    globs = data[TEMPLATES_INCLUDE_KEY]
    if args.stdout:
        sys.stdout.write(render_templates_include_lines(globs, indent=""))
        return 0
    config_path = Path(args.config)
    try:
        with open(config_path, encoding="utf-8", newline="") as fh:
            current = fh.read()
    except FileNotFoundError:
        print(f"error: config not found: {config_path}", file=sys.stderr)
        return 2
    updated = set_templates_note_include(current, globs)
    refusal = _duplicate_refusal(current, updated)
    if refusal:
        print(f"error: {refusal}, refusing to write", file=sys.stderr)
        return 1
    if not _reads_back(updated, globs):
        print("error: resulting YAML would not read back templates.note_include, "
              "refusing to write", file=sys.stderr)
        return 1
    try:
        _atomic_write(config_path, updated)
    except OSError as exc:
        print(f"error: could not write {config_path}: {exc}", file=sys.stderr)
        return 2
    print(f"vault-config-writer: templates.note_include written ({len(globs)} glob(s)) "
          f"→ {config_path}", file=sys.stderr)
    return 0


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

    p_tpl = sub.add_parser(
        "templates-include",
        help="Insert/replace only `templates.note_include`; the rest of `templates:` is untouched.",
    )
    _common_args(p_tpl, "vault-config-templates")
    p_tpl.set_defaults(func=cmd_templates_include)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
