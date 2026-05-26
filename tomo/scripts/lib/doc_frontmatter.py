# version: 0.3.0
"""doc_frontmatter.py — Producer helper for the 'tomo:' frontmatter block.

Every Tomo-produced doc (suggestions, suggestions-fan, moc-proposal,
instructions, source) carries a 'tomo:' frontmatter block as its
single source of lifecycle truth. This module provides the two canonical
operations on that block: constructing it (with validation) and parsing
it back out of a full frontmatter dict.

ADR-4 (SDD §Architecture Decisions): Schema validation is dual-mode.
- Dev mode  (TOMO_SCHEMA_STRICT=1 env var): build_tomo_block raises
  SchemaValidationError immediately so the producing script fails fast.
- Prod mode (env var absent or empty):       build_tomo_block emits a
  stderr WARNING and returns the dict anyway — a bad schema rev must not
  block a live vault write mid-session.

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/solution.md §Application Data Models
AC:   AC-1.5, AC-7.2 (schema validation gates every producer write)
      AC-4.5 (source_* pattern extensibility)
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

# jsonschema is optional — when unavailable, _validate() degrades to a no-op
# (matching the fallback pattern in validate-result.py and vault-config-writer.py).
# F-47 originally hard-imported this and broke F-54 live-test 2026-05-22 when the
# subagent's Python env didn't have it. Strict validation still runs whenever
# the package IS available; the fallback keeps the producer path alive on
# minimal installs.
try:
    import jsonschema  # type: ignore

    _HAVE_JSONSCHEMA = True
except ImportError:
    jsonschema = None  # type: ignore
    _HAVE_JSONSCHEMA = False


class SchemaValidationError(Exception):
    """Raised in dev mode when a tomo: block fails schema validation."""


# Schema file is at tomo/schemas/doc-frontmatter.schema.json relative to
# the repo root.  This file lives at tomo/scripts/lib/doc_frontmatter.py,
# so: parents[0] = lib/  parents[1] = scripts/  parents[2] = tomo/
#     parents[3] = repo_root/
_SCHEMA_PATH: Path = (
    Path(__file__).resolve().parents[2] / "schemas" / "doc-frontmatter.schema.json"
)

if not _SCHEMA_PATH.exists():
    raise FileNotFoundError(
        f"doc-frontmatter.schema.json not found at {_SCHEMA_PATH}. "
        "Ensure the schema file is committed at tomo/schemas/doc-frontmatter.schema.json."
    )

with _SCHEMA_PATH.open() as _f:
    _SCHEMA: dict = json.load(_f)


def build_tomo_block(
    doc_type: str,
    state: str,
    run_id: str,
    sources: list[dict[str, str]] | None = None,
) -> dict:
    """Construct the inner 'tomo' block dict. Auto-sets updated_at.

    Parameters
    ----------
    doc_type:
        One of: source, suggestions, suggestions-fan, moc-proposal, instructions.
    state:
        Lifecycle state; must be valid for the given doc_type.
    run_id:
        Run-id string produced by run-id.py.
    sources:
        Optional list of source-reference dicts, each with at minimum a 'path'
        key and an optional 'checksum' key (sha256:<hex64> format). Used by
        instructions docs to cross-reference their upstream suggestion file(s).
        Pass None (default) to omit the field entirely.

    Returns
    -------
    dict
        The inner tomo block (without the outer 'tomo' key wrapper).
        Callers assemble the full frontmatter as: {"tomo": build_tomo_block(...)}.

    Raises
    ------
    SchemaValidationError
        When TOMO_SCHEMA_STRICT=1 and the block fails schema validation.
    """
    block: dict = {
        "doc_type": doc_type,
        "state": state,
        "run_id": run_id,
        "updated_at": _utc_now(),
    }
    if sources is not None:
        block["sources"] = sources
    _validate(block)
    return block


def parse_tomo_block(frontmatter: dict) -> dict | None:
    """Return the 'tomo' sub-dict from a frontmatter dict, or None if absent.

    Pure lookup — no validation. The caller is responsible for deciding
    whether to validate the returned block.

    Parameters
    ----------
    frontmatter:
        Full frontmatter dict as returned by e.g. kado_client.read_frontmatter().

    Returns
    -------
    dict | None
        The tomo block dict, or None if the 'tomo' key is absent.
    """
    return frontmatter.get("tomo")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate(block: dict) -> None:
    """Validate block against the doc-frontmatter schema (inner 'tomo' node).

    Wraps block in {"tomo": block} for validation because the schema's root
    requires the 'tomo' key.  Dev mode raises; prod mode warns.

    If `jsonschema` is unavailable, validation is skipped silently. Strict
    mode (TOMO_SCHEMA_STRICT) still raises if jsonschema is missing AND
    strict was requested — that combination is a misconfigured CI/test env.
    """
    if not _HAVE_JSONSCHEMA:
        if os.environ.get("TOMO_SCHEMA_STRICT", ""):
            raise SchemaValidationError(
                "TOMO_SCHEMA_STRICT requested but jsonschema package is not "
                "installed. Install with: pip install jsonschema"
            )
        return
    doc = {"tomo": block}
    try:
        jsonschema.validate(doc, _SCHEMA)
    except jsonschema.ValidationError as exc:
        strict = os.environ.get("TOMO_SCHEMA_STRICT", "")
        if strict:
            raise SchemaValidationError(
                f"tomo: block failed schema validation: {exc.message}"
            ) from exc
        print(
            f"WARNING: tomo: block failed schema validation: {exc.message}",
            file=sys.stderr,
        )
