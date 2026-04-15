#!/usr/bin/env python3
# template-from-schema.py — Generate a skeleton JSON template from a JSON Schema.
# version: 0.1.0
"""
Walks a JSON Schema and produces a skeleton document where every required
field is present with a placeholder value. The LLM fills in the placeholders
rather than composing JSON from memory.

Inputs (CLI):
  --schema    Path to a JSON Schema file (draft-2020-12 supported subset).
  --output    Target path for the skeleton JSON.
  --oneof     Strategy for oneOf/anyOf: "first" (default) picks the first
              branch; "all" emits an array of alternatives (use for docs).

Placeholder conventions (LLM must replace):
  string      → "<FIELD_NAME>" (UPPER_SNAKE derived from the field key)
  integer     → 0
  number      → 0.0
  boolean     → false
  array       → [] (or [single_skeleton] if `minItems: 1`)
  object      → recurse into required fields
  null-only   → null
  const/enum  → the literal first value

For polymorphic arrays (oneOf branches), the first branch is emitted as
the default. Additional branches become comments-as-keys so the LLM sees
them without parsing them (e.g. "_alternatives": [...]) — kept out for MVP
to stay schema-valid.

Exit: 0 on success, 1 on invalid schema / write error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def upper_snake(key: str) -> str:
    """Convert a field key to UPPER_SNAKE for placeholder rendering."""
    out = []
    for ch in key:
        if ch.isupper() and out and out[-1] != "_":
            out.append("_")
        out.append(ch.upper())
    return "".join(out)


def _resolve_ref(schema: dict, ref: str, root: dict) -> dict:
    """Resolve a local $ref like `#/$defs/create_atomic_note`."""
    if not ref.startswith("#/"):
        return schema
    path = ref[2:].split("/")
    node: Any = root
    for part in path:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return {}
    return node if isinstance(node, dict) else {}


def skeleton(schema: dict, root: dict, field_key: str = "") -> Any:
    """Build a skeleton value for a schema node."""
    if "$ref" in schema:
        resolved = _resolve_ref(schema, schema["$ref"], root)
        return skeleton(resolved, root, field_key)

    if "const" in schema:
        return schema["const"]

    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]

    # oneOf / anyOf: pick the first branch for the template
    for combiner in ("oneOf", "anyOf"):
        if combiner in schema and schema[combiner]:
            # Prefer a non-null branch so the placeholder is useful
            non_null = [b for b in schema[combiner]
                        if not (isinstance(b, dict) and b.get("type") == "null")]
            chosen = non_null[0] if non_null else schema[combiner][0]
            return skeleton(chosen, root, field_key)

    t = schema.get("type")
    # Type can be a list (e.g. ["string", "null"]) — pick the first non-null
    if isinstance(t, list):
        non_null_types = [x for x in t if x != "null"]
        t = non_null_types[0] if non_null_types else t[0]

    if t == "object":
        out: dict[str, Any] = {}
        required = set(schema.get("required") or [])
        props = schema.get("properties") or {}
        # Emit EVERY declared property. The LLM sees the full shape this way
        # and can drop optional fields it doesn't set. Ordering: required
        # first, then optional — matches how humans skim the template.
        ordered = [k for k in props.keys() if k in required] + \
                  [k for k in props.keys() if k not in required]
        for key in ordered:
            out[key] = skeleton(props[key], root, key)
        return out

    if t == "array":
        items = schema.get("items")
        min_items = schema.get("minItems") or 0
        if not items:
            return []
        if min_items > 0:
            return [skeleton(items, root, field_key + "_ITEM") for _ in range(min_items)]
        # Optional array — include one illustrative element if items has structure
        if isinstance(items, dict) and (items.get("type") == "object" or "$ref" in items or "oneOf" in items):
            return [skeleton(items, root, field_key + "_ITEM")]
        return []

    if t == "string":
        return f"<{upper_snake(field_key) or 'STRING'}>"

    if t == "integer":
        return 0

    if t == "number":
        return 0.0

    if t == "boolean":
        return False

    if t == "null":
        return None

    # Fallback
    return f"<{upper_snake(field_key) or 'VALUE'}>"


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a skeleton template from a JSON Schema.")
    p.add_argument("--schema", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"ERROR: schema not found: {schema_path}", file=sys.stderr)
        return 1
    with schema_path.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)

    root = schema
    skel = skeleton(schema, root)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(skel, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"template-from-schema: wrote {out_path} from {schema_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
