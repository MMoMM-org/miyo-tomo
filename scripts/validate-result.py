#!/usr/bin/env python3
# validate-result.py — Validate a tomo-tmp/items/<stem>.result.json
# against the item-result schema. Used by inbox-analyst immediately after
# writing the file, before state-update done.
# version: 0.1.0
"""
Inputs (CLI):
  --result   Path to <stem>.result.json
  --schema   Path to item-result.schema.json (default: schemas/item-result.schema.json)

Exit codes:
  0 — valid
  1 — invalid (reason printed to stderr)
  2 — file not found / cannot read

Validation is schema-shape-only — it does NOT check semantic consistency
beyond the declared JSON Schema. If `jsonschema` is unavailable, falls back
to a minimal hand-rolled required-field check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_TOP = {"schema_version", "stem", "path", "type", "type_confidence", "actions"}
ALLOWED_KINDS = {
    "create_atomic_note",
    "update_daily",
    "link_to_moc",
    "create_moc",
    "modify_note",
}
REQUIRED_PER_KIND = {
    "create_atomic_note": {
        "kind", "suggested_title", "template", "location", "candidate_mocs", "tags_to_add",
    },
    "update_daily": {"kind", "date", "daily_note_path", "updates"},
    "link_to_moc": {"kind", "target_moc", "section_name"},
    "create_moc": {"kind", "moc_title", "parent_moc"},
    "modify_note": {"kind", "target_path", "diff_description"},
}
# Fields that MUST NOT appear — catches common drift.
FORBIDDEN_PER_KIND_ATOMIC = {
    "title": "use `suggested_title` instead",
    "classification_category": "use `classification: {category, confidence}` instead",
    "classification_confidence": "use nested `classification.confidence` instead",
    "destination_concept": "split into `template` (Obsidian template name) and `location` (target folder path)",
    "destination": "split into `template` and `location`",
}


def validate_hand(result: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TOP - set(result.keys())
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")
    if result.get("schema_version") != "1":
        errors.append(f"schema_version must be '1', got {result.get('schema_version')!r}")
    actions = result.get("actions")
    if not isinstance(actions, list) or not actions:
        errors.append("actions must be a non-empty list")
        return errors
    for i, a in enumerate(actions):
        if not isinstance(a, dict):
            errors.append(f"actions[{i}] must be an object")
            continue
        kind = a.get("kind")
        if kind not in ALLOWED_KINDS:
            errors.append(f"actions[{i}].kind={kind!r} not in {sorted(ALLOWED_KINDS)}")
            continue
        missing = REQUIRED_PER_KIND[kind] - set(a.keys())
        if missing:
            errors.append(f"actions[{i}] ({kind}) missing fields: {sorted(missing)}")
        if kind == "create_atomic_note":
            for bad, hint in FORBIDDEN_PER_KIND_ATOMIC.items():
                if bad in a:
                    errors.append(f"actions[{i}].{bad} is forbidden — {hint}")
            mocs = a.get("candidate_mocs") or []
            for mi, m in enumerate(mocs):
                if not isinstance(m, dict):
                    errors.append(f"actions[{i}].candidate_mocs[{mi}] must be an object, got {type(m).__name__}")
                    continue
                for f in ("path", "score", "pre_check"):
                    if f not in m:
                        errors.append(f"actions[{i}].candidate_mocs[{mi}] missing `{f}`")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate a Tomo per-item result JSON.")
    p.add_argument("--result", required=True)
    p.add_argument("--schema", default="schemas/item-result.schema.json")
    args = p.parse_args()

    result_path = Path(args.result)
    if not result_path.exists():
        print(f"ERROR: result file not found: {result_path}", file=sys.stderr)
        return 2
    try:
        with result_path.open("r", encoding="utf-8") as fh:
            result = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"ERROR: {result_path} is not valid JSON: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    try:
        import jsonschema  # type: ignore
    except ImportError:
        errors = validate_hand(result)
    else:
        schema_path = Path(args.schema)
        if not schema_path.exists():
            errors = validate_hand(result)
        else:
            try:
                with schema_path.open("r", encoding="utf-8") as fh:
                    schema = json.load(fh)
                jsonschema.validate(result, schema)
                errors.extend(validate_hand(result))  # still run forbidden-field check
            except jsonschema.ValidationError as exc:
                errors.append(str(exc).splitlines()[0])

    if errors:
        for e in errors:
            print(f"INVALID: {e}", file=sys.stderr)
        return 1

    print(f"OK {result_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
