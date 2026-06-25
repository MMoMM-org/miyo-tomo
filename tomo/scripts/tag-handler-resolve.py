#!/usr/bin/env python3
# version: 0.2.1
"""tag-handler-resolve.py — Deterministic tag-handler resolver.

Loads the registry from config/tag-handlers/*.json, validates each file
against tomo/schemas/tag-handler.schema.json, and matches an inbox item's
tags against registered handlers. Pure: no LLM, no network beyond the
registry read. Invalid or disabled handlers are skipped with a warning.

Only 'insert_under_marker' is shipped in v1; all other actions are rejected
with a clear error at match time (SDD §4).

Usage (CLI):
    python3 tag-handler-resolve.py --registry <dir> --item <json-string>
    python3 tag-handler-resolve.py --registry <dir> --item-file <path>

Importable API:
    from tag_handler_resolve import load_registry, resolve_item
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Inject script dir so lib.* resolves when run as a top-level script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from jsonschema import ValidationError, validate as _jsonschema_validate
except ImportError:  # pragma: no cover — venv always has it; guard for edge cases
    _jsonschema_validate = None  # type: ignore[assignment]
    ValidationError = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema path — relative to this script (always inside the Tomo repo)
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent  # tomo/scripts/ → tomo/ → repo root
_SCHEMA_PATH = _REPO_ROOT / "tomo" / "schemas" / "tag-handler.schema.json"

_SHIPPED_ACTION = "insert_under_marker"
_DEFERRED_ACTIONS = frozenset(["route_to_folder", "link_to_moc", "enrich_frontmatter"])


# ---------------------------------------------------------------------------
# Schema loader (cached after first read)
# ---------------------------------------------------------------------------

_schema_cache: dict | None = None


def _load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


# ---------------------------------------------------------------------------
# Registry loader — injectable path for tests
# ---------------------------------------------------------------------------


def load_registry(registry_dir: Path | str) -> list[dict]:
    """Load and validate all handler configs from *registry_dir*.

    Files that are not valid JSON or fail schema validation are skipped with a
    logged WARNING — the run continues (additive safety, AC-5). A missing or
    empty directory returns an empty list.

    Handlers are returned sorted lexically by ``id`` (deterministic order).
    """
    registry_dir = Path(registry_dir)

    if not registry_dir.is_dir():
        logger.debug("Registry dir %s does not exist — zero handlers loaded", registry_dir)
        return []

    schema = _load_schema()
    handlers: list[dict] = []

    for json_file in sorted(registry_dir.glob("*.json")):
        raw = json_file.read_text(encoding="utf-8")
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Skipping %s — malformed JSON: %s", json_file.name, exc)
            continue

        if _jsonschema_validate is not None:
            try:
                _jsonschema_validate(instance=config, schema=schema)
            except ValidationError as exc:
                logger.warning("Skipping %s — schema invalid: %s", json_file.name, exc.message)
                continue
        else:
            logger.warning("jsonschema not available — skipping schema validation for %s", json_file.name)

        handlers.append(config)

    # Deterministic sort: lexical by id (SDD §3)
    handlers.sort(key=lambda h: h.get("id", ""))
    return handlers


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def resolve_item(item: dict[str, Any], registry: list[dict]) -> dict[str, Any] | None:
    """Match *item* against the loaded *registry* and return a resolution dict.

    Parameters
    ----------
    item:
        ``{"path": str, "tags": list[str], "frontmatter": dict}``
    registry:
        List of validated handler dicts as returned by :func:`load_registry`.
        The list must already be sorted in the desired priority order (lexical
        by id, as :func:`load_registry` guarantees).

    Returns
    -------
    dict | None
        Resolution mapping (SDD §3 output shape) if a handler matched, else
        ``None``.

    Raises
    ------
    ValueError
        If the matched handler's action is a declared-but-deferred action
        (SDD §4 — not yet implemented), or is entirely unknown to the registry.
    """
    tags: list[str] = item.get("tags") or []
    frontmatter: dict = item.get("frontmatter") or {}

    for handler in registry:
        # Skip disabled handlers exactly like invalid ones (SDD §2)
        if not handler.get("enabled", True):
            continue

        match_cfg = handler.get("match", {})
        prefix: str = match_cfg.get("tag_prefix", "")
        if not prefix:
            continue

        # Find the first tag (in item order) that carries this prefix.
        # Obsidian/Kado return frontmatter tags with a leading '#'
        # (e.g. '#MiYo/Tsukai/Tomo'); strip it before matching so both
        # '#'-prefixed and bare tags resolve identically. matched_tag keeps
        # the normalized (bare) form so the suffix binding below is correct.
        matched_tag: str | None = None
        for tag in tags:
            normalized = tag[1:] if tag.startswith("#") else tag
            if normalized.startswith(prefix):
                matched_tag = normalized
                break

        if matched_tag is None:
            continue

        # --- handler matched ---

        action: str = handler.get("action", "")
        if action in _DEFERRED_ACTIONS:
            raise ValueError(
                f"Handler '{handler['id']}' uses action '{action}' which is "
                "declared but not yet implemented in v1 of the action registry."
            )
        if action != _SHIPPED_ACTION:
            raise ValueError(
                f"Handler '{handler['id']}' uses unknown action '{action}' — "
                "not in the v1 action registry."
            )

        # Bind capture_segments from the suffix after the prefix
        suffix = matched_tag[len(prefix):]
        capture_names: list[str] = match_cfg.get("capture_segments", [])
        suffix_parts = suffix.split("/") if suffix else []
        vars_: dict[str, str] = dict(zip(capture_names, suffix_parts))

        # Pull read_fields from frontmatter
        read_field_names: list[str] = match_cfg.get("read_fields", [])
        fields: dict[str, Any] = {
            k: frontmatter[k] for k in read_field_names if k in frontmatter
        }

        # Target resolution: target.map[ vars[target.by] ] → path or null
        target_path: str | None = None
        target_cfg = handler.get("target")
        if target_cfg:
            target_by: str = target_cfg.get("by", "")
            target_map: dict[str, str] = target_cfg.get("map", {})
            lookup_key = vars_.get(target_by)
            if lookup_key is not None:
                target_path = target_map.get(lookup_key)  # None if unmapped

        return {
            "handler": handler["id"],
            "vars": vars_,
            "fields": fields,
            "target_path": target_path,
            "marker": handler.get("marker"),
            "action": action,
            "placement": handler.get("placement"),
            "compose": handler.get("compose"),
        }

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Resolve an inbox item against the tag-handler registry.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--registry",
        metavar="DIR",
        default="config/tag-handlers",
        help="Path to the registry directory (default: config/tag-handlers)",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--item",
        metavar="JSON",
        help="Inline JSON string: {\"path\": ..., \"tags\": [...], \"frontmatter\": {...}}",
    )
    g.add_argument(
        "--item-file",
        metavar="PATH",
        help="Path to a JSON file containing the item dict",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    registry = load_registry(Path(args.registry))

    if args.item:
        item = json.loads(args.item)
    else:
        item = json.loads(Path(args.item_file).read_text(encoding="utf-8"))

    try:
        result = resolve_item(item, registry)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), flush=True)
        sys.exit(1)

    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
