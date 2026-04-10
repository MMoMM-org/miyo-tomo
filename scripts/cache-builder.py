#!/usr/bin/env python3
# version: 0.1.0
"""
cache-builder.py — Assemble scan results into discovery-cache.yaml.

Reads JSON outputs from vault-scan.py, moc-tree-builder.py, and optional
analysis scripts, then writes a single discovery-cache.yaml file.

Usage:
    python cache-builder.py \\
        --structure vault-structure.json \\
        --mocs moc-tree.json \\
        [--frontmatter frontmatter.json] \\
        [--tags tags.json] \\
        [--orphans orphans.json] \\
        [--output config/discovery-cache.yaml] \\
        [--start-time 2026-04-10T12:00:00Z]

Exit: 0 on success, 1 on error
"""

import argparse
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone

import yaml

CACHE_VERSION = 1


# ──────────────────────────────────────────────────────────────────────────────
# Input loading
# ──────────────────────────────────────────────────────────────────────────────

def load_json(path: str, label: str) -> dict | list | None:
    """Load JSON from a file path. Returns None on error (logs warning)."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"[error] {label} file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[error] {label} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Section builders
# ──────────────────────────────────────────────────────────────────────────────

def build_vault_structure(structure_data: dict | None) -> dict:
    """Extract vault_structure section from vault-scan.py output."""
    if not structure_data:
        return {}
    return structure_data.get("vault_structure", {})


def build_map_notes(mocs_data: dict | None) -> list:
    """Extract map_notes array from moc-tree-builder.py output."""
    if not mocs_data:
        return []
    return mocs_data.get("map_notes", [])


def build_placeholder_mocs(mocs_data: dict | None) -> list:
    """Extract placeholder_mocs array from moc-tree-builder.py output."""
    if not mocs_data:
        return []
    return mocs_data.get("placeholder_mocs", [])


def build_classifications(map_notes: list) -> dict:
    """
    Compute classification coverage by aggregating map_notes data.

    For each unique classification value:
      map_count = count of map_notes with that classification
      note_count = sum of linked_notes for those map_notes
      top_keywords = deduplicated union of all topics from those map_notes
    """
    buckets: dict[int, dict] = {}

    for note in map_notes:
        classification = note.get("classification")
        if classification is None:
            continue
        if not isinstance(classification, int):
            try:
                classification = int(classification)
            except (ValueError, TypeError):
                continue

        if classification not in buckets:
            buckets[classification] = {
                "map_count": 0,
                "note_count": 0,
                "top_keywords": [],
                "_keywords_set": set(),
            }

        bucket = buckets[classification]
        bucket["map_count"] += 1
        bucket["note_count"] += note.get("linked_notes", 0)

        for kw in note.get("topics", []):
            if kw and kw not in bucket["_keywords_set"]:
                bucket["_keywords_set"].add(kw)
                bucket["top_keywords"].append(kw)

    # Remove internal set used for deduplication
    result: dict = {}
    for cat, bucket in sorted(buckets.items()):
        result[cat] = {
            "map_count": bucket["map_count"],
            "note_count": bucket["note_count"],
            "top_keywords": bucket["top_keywords"],
        }

    return result


def build_scan_stats(
    structure_data: dict | None,
    map_notes: list,
    classifications: dict,
    tags_data: dict | None,
) -> dict:
    """Derive scan_stats from assembled inputs."""
    vault_structure = build_vault_structure(structure_data)

    total_notes = vault_structure.get("total_notes", 0)
    total_map_notes = len(map_notes)
    total_classification_maps = sum(
        b.get("map_count", 0) for b in classifications.values()
    )

    # Count unique tags across all tag_patterns prefixes
    total_tags_unique = 0
    if tags_data:
        tag_patterns = tags_data.get("tag_patterns", tags_data)
        if isinstance(tag_patterns, dict):
            for prefix_values in tag_patterns.values():
                if isinstance(prefix_values, dict):
                    total_tags_unique += len(prefix_values)

    return {
        "total_notes": total_notes,
        "total_map_notes": total_map_notes,
        "total_classification_maps": total_classification_maps,
        "total_tags_unique": total_tags_unique,
    }


def build_tag_patterns(tags_data: dict | None) -> dict:
    """Extract tag_patterns from tags analysis JSON (empty if not provided)."""
    if not tags_data:
        return {}
    # Support both {tag_patterns: {...}} and a flat dict
    if "tag_patterns" in tags_data:
        return tags_data["tag_patterns"]
    return tags_data


def build_frontmatter_usage(frontmatter_data: dict | None) -> dict:
    """Extract frontmatter_usage from frontmatter sampling JSON (empty if not provided)."""
    if not frontmatter_data:
        return {}
    if "frontmatter_usage" in frontmatter_data:
        return frontmatter_data["frontmatter_usage"]
    return frontmatter_data


def build_orphans(orphans_data: dict | None) -> dict:
    """Extract orphans section from orphan detection JSON (empty if not provided)."""
    if not orphans_data:
        return {}
    if "orphans" in orphans_data:
        return orphans_data["orphans"]
    return orphans_data


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────

def _has_nan_or_inf(obj, path: str = "") -> list[str]:
    """Recursively find any NaN or Infinity values. Returns list of offending paths."""
    issues: list[str] = []
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            issues.append(f"NaN/Infinity at {path!r}: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            issues.extend(_has_nan_or_inf(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            issues.extend(_has_nan_or_inf(item, f"{path}[{i}]"))
    return issues


def _has_absolute_paths(obj, path: str = "") -> list[str]:
    """Recursively find any string values that look like absolute paths."""
    issues: list[str] = []
    if isinstance(obj, str):
        if obj.startswith("/") or (len(obj) > 2 and obj[1] == ":" and obj[2] in "/\\"):
            issues.append(f"Absolute path at {path!r}: {obj!r}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            issues.extend(_has_absolute_paths(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            issues.extend(_has_absolute_paths(item, f"{path}[{i}]"))
    return issues


def validate_cache(cache: dict) -> list[str]:
    """
    Validate the assembled cache dict.

    Returns a list of error/warning strings (empty = valid).
    """
    errors: list[str] = []

    # cache_version present
    if "cache_version" not in cache:
        errors.append("Missing required field: cache_version")

    # last_scan is valid ISO 8601
    last_scan = cache.get("last_scan", "")
    if not last_scan:
        errors.append("Missing required field: last_scan")
    else:
        try:
            datetime.fromisoformat(last_scan.replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"last_scan is not a valid ISO 8601 timestamp: {last_scan!r}")

    # map_notes — warn if empty (not an error that blocks writing)
    map_notes = cache.get("map_notes", [])
    if not map_notes:
        print("[warn] map_notes is empty — no MOCs found in vault", file=sys.stderr)

    # No NaN or Infinity
    nan_issues = _has_nan_or_inf(cache)
    errors.extend(nan_issues)

    # No absolute paths
    abs_issues = _has_absolute_paths(cache)
    errors.extend(abs_issues)

    return errors


def validate_yaml_file(path: str) -> bool:
    """Re-read and parse the written YAML file to verify it is valid."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            print(f"[error] Validation: YAML root is not a mapping (got {type(data).__name__})", file=sys.stderr)
            return False
        return True
    except yaml.YAMLError as exc:
        print(f"[error] Validation: YAML parse failed after write: {exc}", file=sys.stderr)
        return False
    except OSError as exc:
        print(f"[error] Validation: Cannot re-read output file: {exc}", file=sys.stderr)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Timestamp / duration helpers
# ──────────────────────────────────────────────────────────────────────────────

def compute_duration(start_time_str: str | None) -> float | None:
    """Return elapsed seconds since start_time_str (ISO 8601), or None if not provided."""
    if not start_time_str:
        return None
    try:
        start = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - start
        return round(delta.total_seconds(), 1)
    except ValueError as exc:
        print(f"[warn] Could not parse --start-time: {exc}", file=sys.stderr)
        return None


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ──────────────────────────────────────────────────────────────────────────────
# Assembly
# ──────────────────────────────────────────────────────────────────────────────

def assemble_cache(
    structure_data: dict | None,
    mocs_data: dict | None,
    frontmatter_data: dict | None,
    tags_data: dict | None,
    orphans_data: dict | None,
    start_time: str | None,
) -> dict:
    """Assemble all inputs into the final cache dict."""
    map_notes = build_map_notes(mocs_data)
    placeholder_mocs = build_placeholder_mocs(mocs_data)
    classifications = build_classifications(map_notes)
    scan_stats = build_scan_stats(structure_data, map_notes, classifications, tags_data)
    vault_structure = build_vault_structure(structure_data)
    tag_patterns = build_tag_patterns(tags_data)
    frontmatter_usage = build_frontmatter_usage(frontmatter_data)
    orphans = build_orphans(orphans_data)

    last_scan = utc_now_iso()
    duration = compute_duration(start_time)

    cache: dict = {
        "cache_version": CACHE_VERSION,
        "last_scan": last_scan,
    }

    if duration is not None:
        cache["scan_duration_seconds"] = duration

    cache["scan_stats"] = scan_stats
    cache["vault_structure"] = vault_structure
    cache["map_notes"] = map_notes
    cache["placeholder_mocs"] = placeholder_mocs
    cache["classifications"] = classifications
    cache["tag_patterns"] = tag_patterns
    cache["frontmatter_usage"] = frontmatter_usage
    cache["orphans"] = orphans

    return cache


# ──────────────────────────────────────────────────────────────────────────────
# Writing
# ──────────────────────────────────────────────────────────────────────────────

def write_cache_atomic(cache: dict, output_path: str) -> None:
    """
    Write the cache dict to output_path atomically.

    Writes to a temp file in the same directory, then renames to target.
    Raises OSError on failure.
    """
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("# discovery-cache.yaml — auto-generated by cache-builder.py\n")
            fh.write("# Do not edit manually — re-run /explore-vault to refresh.\n")
            yaml.dump(
                cache,
                fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
    except Exception:
        os.unlink(tmp_path)
        raise

    os.replace(tmp_path, output_path)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cache-builder.py",
        description=(
            "Assemble vault scan results into a single discovery-cache.yaml.\n\n"
            "Reads JSON outputs from vault-scan.py, moc-tree-builder.py, and\n"
            "optional analysis scripts (frontmatter, tags, orphans)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--structure",
        metavar="FILE",
        help="vault-scan.py JSON output (vault_structure section)",
    )
    parser.add_argument(
        "--mocs",
        metavar="FILE",
        help="moc-tree-builder.py JSON output (map_notes, placeholder_mocs, tree_stats)",
    )
    parser.add_argument(
        "--frontmatter",
        metavar="FILE",
        help="(optional) Frontmatter sampling results JSON",
    )
    parser.add_argument(
        "--tags",
        metavar="FILE",
        help="(optional) Tag analysis results JSON",
    )
    parser.add_argument(
        "--orphans",
        metavar="FILE",
        help="(optional) Orphan detection results JSON",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default="config/discovery-cache.yaml",
        help="Output path for discovery-cache.yaml (default: config/discovery-cache.yaml)",
    )
    parser.add_argument(
        "--start-time",
        metavar="TIMESTAMP",
        dest="start_time",
        help="ISO 8601 UTC timestamp when the scan started (used to compute scan_duration_seconds)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Load inputs
    structure_data = load_json(args.structure, "--structure") if args.structure else None
    mocs_data = load_json(args.mocs, "--mocs") if args.mocs else None
    frontmatter_data = load_json(args.frontmatter, "--frontmatter") if args.frontmatter else None
    tags_data = load_json(args.tags, "--tags") if args.tags else None
    orphans_data = load_json(args.orphans, "--orphans") if args.orphans else None

    # Assemble
    print("[cache-builder] Assembling discovery cache...", file=sys.stderr)
    cache = assemble_cache(
        structure_data=structure_data,
        mocs_data=mocs_data,
        frontmatter_data=frontmatter_data,
        tags_data=tags_data,
        orphans_data=orphans_data,
        start_time=args.start_time,
    )

    # Validate before writing
    errors = validate_cache(cache)
    if errors:
        for err in errors:
            print(f"[error] Validation: {err}", file=sys.stderr)
        return 1

    # Write atomically
    output_path = args.output
    try:
        write_cache_atomic(cache, output_path)
    except OSError as exc:
        print(f"[error] Failed to write cache: {exc}", file=sys.stderr)
        return 1

    # Verify the written file is valid YAML
    if not validate_yaml_file(output_path):
        print(f"[error] Post-write validation failed for {output_path!r}", file=sys.stderr)
        return 1

    file_size = os.path.getsize(output_path)
    print(
        f"[cache-builder] Discovery cache written: {output_path} ({file_size} bytes)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
