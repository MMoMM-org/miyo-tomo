#!/usr/bin/env python3
# version: 0.1.0
"""tag-handler-group.py — Deterministic grouping helper for tag-handler results.

Groups routing-plan handled[] items by (handler, target_path) and provides a
mechanical field-template compose path (no LLM). Pure and deterministic: no
network, no LLM calls.

The LLM-directive compose path (one LLM call per group receiving the whole
batch) lives in the tag-handler-interpreter skill — not here. This module
supplies the grouping structure and the no-LLM mechanical path that the skill
calls when compose is an array of field names.

Importable API:
    from tag_handler_group import group_handled, compose_field_template

CLI:
    python3 tag-handler-group.py --routing-plan <path> [--output <path>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


def group_handled(handled_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group routing-plan handled[] items by (handler, target_path).

    Parameters
    ----------
    handled_list:
        The ``handled[]`` array from routing-plan.json as produced by
        inbox-triage.py + tag-handler-resolve.py.

    Returns
    -------
    list[dict]
        One dict per (handler, target_path) pair, sorted lexically by handler
        then target_path (None sorts after non-None strings under the same
        handler). Each dict carries:
        - handler, target_path, marker, placement, compose  (from item config)
        - source_paths  (all paths in this group, in handled_list order)
    """
    # Build an ordered dict keyed by (handler, target_path) to accumulate groups.
    # We use a plain dict (insertion-ordered in Python 3.7+) and sort at the end.
    groups: dict[tuple, dict[str, Any]] = {}

    for item in handled_list:
        handler = item["handler"]
        target_path = item.get("target_path")
        key = (handler, target_path)

        if key not in groups:
            groups[key] = {
                "handler": handler,
                "target_path": target_path,
                "marker": item.get("marker"),
                "placement": item.get("placement"),
                "compose": item.get("compose"),
                "source_paths": [],
            }

        groups[key]["source_paths"].append(item["path"])

    # Deterministic sort: handler (lexical), then target_path (None last within handler).
    def _sort_key(key: tuple) -> tuple:
        handler, target = key
        # None → sorts after any non-None string under the same handler
        return (handler, target is None, target or "")

    return [groups[k] for k in sorted(groups.keys(), key=_sort_key)]


# ---------------------------------------------------------------------------
# Mechanical field-template compose (no LLM)
# ---------------------------------------------------------------------------


def compose_field_template(
    captures: list[dict[str, Any]],
    fields: list[str],
) -> str:
    """Produce a composed block from field values — no LLM.

    Called when the handler config's ``compose`` is an array of field names
    (mechanical template path, SDD §5). Joins each capture's declared fields
    into a simple bullet list.

    Parameters
    ----------
    captures:
        List of ``{path, vars, fields}`` dicts from the group.
    fields:
        Ordered list of field names to render for each capture.

    Returns
    -------
    str
        A markdown string with one section per capture, each listing the
        requested field values. Missing fields are silently skipped.
    """
    if not captures or not fields:
        return ""

    lines: list[str] = []
    for capture in captures:
        capture_fields = capture.get("fields") or {}
        path = capture.get("path", "")
        # Emit a lightweight heading per source so provenance is clear.
        lines.append(f"- `{path}`")
        for field in fields:
            if field in capture_fields:
                lines.append(f"  - **{field}**: {capture_fields[field]}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Group routing-plan handled[] items by (handler, target_path).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--routing-plan",
        metavar="PATH",
        required=True,
        help="Path to routing-plan.json produced by inbox-triage.py",
    )
    p.add_argument(
        "--output",
        metavar="PATH",
        default="-",
        help="Output path for JSON groups array (default: stdout)",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    plan = json.loads(Path(args.routing_plan).read_text(encoding="utf-8"))
    handled = plan.get("handled") or []
    groups = group_handled(handled)

    output = json.dumps(groups, indent=2)
    if args.output == "-":
        print(output, flush=True)
    else:
        Path(args.output).write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
