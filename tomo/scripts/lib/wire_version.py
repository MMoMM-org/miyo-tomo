#!/usr/bin/env python3
# version: 0.2.0
"""wire_version.py — Read a wire schema's own declared schema_version (spec 035 T3.1).

ADR-5: a renderer must not declare `schema_version` as a free string literal.
Each of the three wire producers (suggestions-render.py, instruction-render.py,
garden-audit-render.py) calls wire_schema_version() at its emission site
instead, so a schema bump and a renderer's emitted value can never diverge in
either direction without the other. See docs/tomo/scripts/lib/wire_version.md.
"""
from __future__ import annotations

import json
from pathlib import Path


def _default_schemas_dir() -> Path:
    """tomo/schemas/, resolved from this file's own location.

    This module lives at tomo/scripts/lib/wire_version.py:
    parents[0]=lib/ parents[1]=scripts/ parents[2]=tomo/ — the same depth as
    doc_frontmatter.py's schema lookup. A function, not a module-level
    constant, so the lookup happens per call rather than at import time —
    tests redirect it via monkeypatch instead of fighting an import-time
    FileNotFoundError.
    """
    return Path(__file__).resolve().parents[2] / "schemas"


def wire_schema_version(schema_filename: str) -> str:
    """The `schema_version` a wire schema declares for its own documents.

    `schema_filename` is one of PUBLISHED_WIRES (lib.wire_shape) — e.g.
    "suggestions-wire.schema.json". Raises FileNotFoundError, naming the
    resolved path, when the schema is not where the instance install
    (scripts/install-tomo.sh) puts it — matching doc_frontmatter.py's
    treatment of the same failure. Also raises, naming the same path, when
    the schema is not valid JSON or its `properties.schema_version.const`
    is missing or not a string (Hashi's validator requires a string const;
    an int or null const reaching a renderer's wire payload would only fail
    at apply, one layer below where this module is meant to catch it).
    Never falls back to a literal or an empty string.
    """
    schema_path = _default_schemas_dir() / schema_filename
    if not schema_path.exists():
        raise FileNotFoundError(
            f"{schema_filename} not found at {schema_path}. "
            "Ensure the schema file is committed at tomo/schemas/ and, for a "
            "running instance, synced by scripts/install-tomo.sh."
        )
    with schema_path.open(encoding="utf-8") as f:
        try:
            schema = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{schema_filename} at {schema_path} is not valid JSON: {exc}"
            ) from exc
    try:
        const = schema["properties"]["schema_version"]["const"]
    except (KeyError, TypeError) as exc:
        raise KeyError(
            f"{schema_filename} at {schema_path} has no "
            "properties.schema_version.const to read"
        ) from exc
    if not isinstance(const, str):
        raise TypeError(
            f"{schema_filename} at {schema_path} declares "
            f"properties.schema_version.const as {const!r} "
            f"({type(const).__name__}, not str) — Hashi's validator requires "
            "schema_version to be a string const."
        )
    return const
