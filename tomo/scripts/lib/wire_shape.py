# wire_shape.py — Shape manifest for a wire schema: describe / diff / classify (spec 035).
# version: 0.1.0
"""Pure schema-shape helpers shared by the wire-shape CLI and its tests.

describe_shape(schema) -> dict[pointer, NodeShape] is implemented here (T1.1).
diff_shapes and classify are Phase 2 and are not implemented yet — do not stub
them.
"""
from __future__ import annotations

__all__ = ["describe_shape"]


def describe_shape(schema: dict) -> dict:
    """Every object node in a schema, by JSON pointer, with the three facts that
    decide whether a consumer breaks.

    `closed` is the discriminator for an ADDED property: measured against the
    consumer's own validator across eight change classes, it is what separates
    "add a field and break them" from "add a field and do not".

    Descriptions are deliberately absent — the consumer's validator ignores
    prose, and recording it would fail the check on edits that oblige nobody,
    which is how a detector becomes one nobody reads. Types ARE recorded: a
    type change is consumer-affecting in its own right, independent of
    openness.
    """
    nodes: dict[str, dict] = {}

    def walk(node: dict, pointer: str) -> None:
        if not isinstance(node, dict):
            return
        props = node.get("properties")
        if isinstance(props, dict):
            nodes[pointer] = {
                # A JSON-Schema node with no additionalProperties defaults to
                # permissive. Recording the effective value, not the literal
                # one, keeps the classification honest for a node that never
                # declared it.
                "closed": node.get("additionalProperties") is False,
                "required": sorted(node.get("required") or []),
                # name -> type keyword. A type change is consumer-affecting
                # (emitting null where string is declared errors in their
                # validator), so the type is recorded; the description is
                # not.
                "properties": {
                    name: (child or {}).get("type", "any")
                    for name, child in sorted(props.items())
                },
            }
            for name, child in props.items():
                walk(child, f"{pointer}/{name}")
        for key in ("items", "contains"):
            if key in node:
                walk(node[key], f"{pointer}/{key}")
        for key in ("$defs", "definitions"):
            for name, child in (node.get(key) or {}).items():
                walk(child, f"{pointer}/{key}/{name}")
        for key in ("allOf", "anyOf", "oneOf"):
            for i, child in enumerate(node.get(key) or []):
                walk(child, f"{pointer}/{key}/{i}")

    walk(schema, "")
    return nodes
