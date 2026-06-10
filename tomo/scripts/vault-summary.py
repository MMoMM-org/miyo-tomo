#!/usr/bin/env python3
# version: 0.3.1
"""
vault-summary.py — Aggregate pipeline stats into a single JSON summary.

Reads pre-computed artifacts from the vault-explorer pipeline and emits one
JSON object to stdout. Used by vault-explorer Step 10 and 10b so the agent
never needs inline python to compute summary numbers.

Usage:
    python3 scripts/vault-summary.py \\
        [--scan   tomo-tmp/scan-output.json] \\
        [--mocs   tomo-tmp/moc-output.json] \\
        [--cache  config/discovery-cache.yaml] \\
        [--config config/vault-config.yaml]

Output: JSON to stdout. Logs to stderr only.
Exit: always 0 — missing inputs yield null fields, never crash /explore-vault.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import islice
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Safe loaders — log to stderr, never crash
# ──────────────────────────────────────────────────────────────────────────────

def load_json_safe(path: str, label: str) -> dict | None:
    """Load JSON from path. Returns None on missing/invalid file (logs stderr)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"[warn] {label} not found: {path}", file=sys.stderr)
        return None
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[warn] {label} unreadable: {exc}", file=sys.stderr)
        return None


def load_yaml_safe(path: str, label: str) -> dict | None:
    """Load YAML from path. Returns None on missing/invalid file (logs stderr)."""
    try:
        import yaml  # noqa: PLC0415
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        print(f"[warn] {label} not found: {path}", file=sys.stderr)
        return None
    except Exception as exc:  # yaml.YAMLError and OSError both extend Exception
        print(f"[warn] {label} unreadable: {exc}", file=sys.stderr)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Field extractors — each returns a typed value or safe default
# ──────────────────────────────────────────────────────────────────────────────

def _extract_moc_stats(mocs: dict | None) -> tuple[int | None, int | None, list[str]]:
    """Return (moc_count, moc_max_depth, key_moc_titles) from moc-output.json."""
    if mocs is None:
        return None, None, []
    tree = mocs.get("tree_stats") or {}
    count = tree.get("total_mocs")
    depth = tree.get("max_depth")
    map_notes = mocs.get("map_notes") or []
    # Cap at 10 without materializing every title first: skip falsy/missing
    # titles, stop after 10 via islice.
    titles = list(islice((n["title"] for n in map_notes if n.get("title")), 10))
    return count, depth, titles


def _extract_scan_stats(scan: dict | None) -> tuple[int | None, dict, list[str]]:
    """Return (total_notes, notes_per_concept, unmapped_folders) from scan-output.json."""
    if scan is None:
        return None, {}, []
    vs = scan.get("vault_structure") or {}
    total = vs.get("total_notes")
    concepts_mapped = vs.get("concepts_mapped") or {}
    notes_per_concept: dict[str, int] = {}
    for name, info in concepts_mapped.items():
        if isinstance(info, dict):
            notes_per_concept[name] = info.get("note_count", 0)
        else:
            notes_per_concept[name] = 0
    unmapped = vs.get("unmapped_folders") or []
    return total, notes_per_concept, unmapped


def _extract_tag_stats(
    config: dict | None,
) -> tuple[int | None, int | None, dict, int | None, int | None]:
    """Return (namespace_count, unique_tag_count, prefix_table, required, optional)."""
    if config is None:
        return None, None, {}, None, None
    prefixes = (config.get("tags") or {}).get("prefixes") or {}
    namespace_count = len(prefixes)
    unique_values: set[str] = set()  # deduped across prefixes, so the count is honest
    prefix_table: dict[str, Any] = {}
    required_count = 0
    optional_count = 0
    for prefix, info in prefixes.items():
        if not isinstance(info, dict):
            optional_count += 1
            prefix_table[prefix] = None
            continue
        known = info.get("known_values") or []
        unique_values.update(str(v) for v in known)
        prefix_table[prefix] = known[0] if known else None
        if info.get("required_for"):
            required_count += 1
        else:
            optional_count += 1
    return namespace_count, len(unique_values), prefix_table, required_count, optional_count


def _extract_relationship_markers(config: dict | None) -> list[dict]:
    """Return markers list from vault-config.yaml relationships.markers."""
    if config is None:
        return []
    return (config.get("relationships") or {}).get("markers") or []


def _extract_callout_counts(config: dict | None) -> tuple[int | None, int | None]:
    """Return (protected_count, editable_count) from vault-config.yaml callouts."""
    if config is None:
        return None, None
    callouts = config.get("callouts") or {}
    protected = len(callouts.get("protected") or [])
    editable = len(callouts.get("editable") or [])
    return protected, editable


def _extract_tracker_field_count(config: dict | None) -> int | None:
    """Return total tracker field count from vault-config.yaml trackers."""
    if config is None:
        return None
    trackers = config.get("trackers") or {}
    daily = len(trackers.get("daily_note_trackers") or [])
    eod = len(trackers.get("end_of_day_fields") or [])
    return daily + eod


def _extract_template_counts(config: dict | None) -> tuple[int | None, int | None]:
    """Return (found_count, missing_count) from vault-config.yaml templates.mapping."""
    if config is None:
        return None, None
    mapping = (config.get("templates") or {}).get("mapping") or {}
    found = 0
    missing = 0
    for entry in mapping.values():
        if entry is None:
            missing += 1
        elif isinstance(entry, dict) and entry.get("path"):
            found += 1
        elif isinstance(entry, str) and entry:
            found += 1
        else:
            missing += 1
    return found, missing


# ──────────────────────────────────────────────────────────────────────────────
# Core aggregator
# ──────────────────────────────────────────────────────────────────────────────

def aggregate_summary(
    scan_path: str,
    mocs_path: str,
    cache_path: str,
    config_path: str,
) -> dict:
    """Aggregate pipeline artifacts into a flat summary dict."""
    # cache_path: echoed as metadata only — not loaded since T3.3 (accumulation retired)
    mocs = load_json_safe(mocs_path, "--mocs")
    scan = load_json_safe(scan_path, "--scan")
    config = load_yaml_safe(config_path, "--config")

    moc_count, moc_max_depth, key_moc_titles = _extract_moc_stats(mocs)
    total_notes, notes_per_concept, unmapped_folders = _extract_scan_stats(scan)
    (
        tag_namespace_count,
        unique_tag_count,
        tag_prefix_table,
        frontmatter_required_count,
        frontmatter_optional_count,
    ) = _extract_tag_stats(config)
    relationship_markers = _extract_relationship_markers(config)
    callout_protected_count, callout_editable_count = _extract_callout_counts(config)
    tracker_field_count = _extract_tracker_field_count(config)
    templates_found_count, templates_missing_count = _extract_template_counts(config)

    return {
        "total_notes": total_notes,
        "notes_per_concept": notes_per_concept,
        "unmapped_folders": unmapped_folders,
        "moc_count": moc_count,
        "moc_max_depth": moc_max_depth,
        "key_moc_titles": key_moc_titles,
        "frontmatter_required_count": frontmatter_required_count,
        "frontmatter_optional_count": frontmatter_optional_count,
        "tag_namespace_count": tag_namespace_count,
        "unique_tag_count": unique_tag_count,
        "tag_prefix_table": tag_prefix_table,
        "relationship_markers": relationship_markers,
        "callout_protected_count": callout_protected_count,
        "callout_editable_count": callout_editable_count,
        "tracker_field_count": tracker_field_count,
        "templates_found_count": templates_found_count,
        "templates_missing_count": templates_missing_count,
        "cache_path": cache_path,
    }


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Aggregate vault-explorer pipeline artifacts into a JSON summary.",
    )
    p.add_argument(
        "--scan",
        default="tomo-tmp/scan-output.json",
        help="Path to scan-output.json (default: tomo-tmp/scan-output.json)",
    )
    p.add_argument(
        "--mocs",
        default="tomo-tmp/moc-output.json",
        help="Path to moc-output.json (default: tomo-tmp/moc-output.json)",
    )
    p.add_argument(
        "--cache",
        default="config/discovery-cache.yaml",
        help="Path to discovery-cache.yaml (reported in summary; not read)",
    )
    p.add_argument(
        "--config",
        default="config/vault-config.yaml",
        help="Path to vault-config.yaml (default: config/vault-config.yaml)",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    summary = aggregate_summary(
        scan_path=args.scan,
        mocs_path=args.mocs,
        cache_path=args.cache,
        config_path=args.config,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
