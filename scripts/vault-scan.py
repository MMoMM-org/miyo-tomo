#!/usr/bin/env python3
# version: 0.2.0
"""
vault-scan.py — Scan vault folder structure via Kado and output JSON.

Reads vault-config.yaml for concept paths, queries each path via KadoClient,
counts notes and subdirectories, detects unmapped top-level folders, and
writes a structure map to stdout as JSON.

Usage:
    python vault-scan.py [--config PATH]
"""

import argparse
import json
import os
import re
import sys

import yaml

# Allow importing from scripts/lib/
sys.path.insert(0, os.path.dirname(__file__))
from lib.kado_client import KadoClient  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Config parsing
# ──────────────────────────────────────────────────────────────────────────────

CONCEPT_KEYS = [
    "inbox",
    "atomic_note",
    "map_note",
    "calendar",
    "project",
    "area",
    "source",
    "template",
    "asset",
]

DEWEY_PATTERN = re.compile(r"^\d+\s+.+")


def extract_primary_path(concept_key: str, concept_value) -> str | None:
    """
    Return the primary folder path for a concept config entry.

    Handles all config formats:
      - Simple string:  inbox: "+/"
      - base_path dict: atomic_note: { base_path: "Atlas/202 Notes/" }
      - paths list:     map_note: { paths: ["Atlas/200 Maps/"] }
      - calendar:       calendar: { base_path: "Calendar/", granularities: {...} }
    """
    if concept_value is None:
        return None

    if isinstance(concept_value, str):
        return concept_value

    if isinstance(concept_value, dict):
        # calendar: prefer base_path
        if "base_path" in concept_value:
            return concept_value["base_path"]
        # map_note style: paths list
        if "paths" in concept_value and concept_value["paths"]:
            return concept_value["paths"][0]

    return None


def extract_all_paths(concept_value) -> list[str]:
    """Return every configured path for a concept (used for unmapped detection)."""
    if concept_value is None:
        return []
    if isinstance(concept_value, str):
        return [concept_value]
    if isinstance(concept_value, dict):
        paths: list[str] = []
        if "base_path" in concept_value and concept_value["base_path"]:
            paths.append(concept_value["base_path"])
        if "paths" in concept_value:
            paths.extend(p for p in concept_value["paths"] if p)
        # calendar granularities
        if "granularities" in concept_value:
            for gran in concept_value["granularities"].values():
                if isinstance(gran, dict) and gran.get("path"):
                    paths.append(gran["path"])
        return paths
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Vault scanning helpers
# ──────────────────────────────────────────────────────────────────────────────

def scan_path(client: KadoClient, path: str) -> dict:
    """
    Scan a single concept path.

    Uses Kado v0.2.0+ ``listDir`` which returns both files and folders
    with a ``type`` field (``'file'`` or ``'folder'``).

    Returns:
        {
            "note_count": int,          # .md files anywhere under path
            "file_count": int,          # items with type == 'file'
            "subdirectories": [         # items with type == 'folder' at depth 1
                {"name": str, "note_count": int},
                ...
            ]
        }
    """
    result: dict = {"note_count": 0, "file_count": 0, "subdirectories": []}

    if not path:
        return result

    try:
        items = client.list_dir(path)
    except Exception as exc:
        print(f"[warn] Could not list {path!r}: {exc}", file=sys.stderr)
        return result

    base = path.rstrip("/")
    base_prefix = base + "/" if base else ""

    # Track note counts per direct subdirectory
    subdir_notes: dict[str, int] = {}

    for item in items:
        item_type = item.get("type", "file")
        item_path = item.get("path", "")
        name = item.get("name", "")

        if item_type == "folder":
            # Direct child folder — seed the subdir entry
            if base_prefix and item_path.startswith(base_prefix):
                rel = item_path[len(base_prefix):].rstrip("/")
                if "/" not in rel:
                    subdir_notes.setdefault(rel or name, 0)
            continue

        # type == 'file'
        result["file_count"] += 1
        is_note = name.endswith(".md") or item_path.endswith(".md")
        if is_note:
            result["note_count"] += 1

        # Attribute note to its top-level subdirectory
        if base_prefix and item_path.startswith(base_prefix):
            rel = item_path[len(base_prefix):]
            head, sep, _tail = rel.partition("/")
            if sep and head:
                subdir_notes.setdefault(head, 0)
                if is_note:
                    subdir_notes[head] += 1

    result["subdirectories"] = [
        {"name": name, "note_count": count}
        for name, count in sorted(subdir_notes.items())
    ]

    return result


def is_dewey_dir(name: str) -> bool:
    """Return True if the folder name matches the Dewey-number pattern (digits + space + name)."""
    return bool(DEWEY_PATTERN.match(name))


def top_level_folder_name(path: str) -> str:
    """Return the first path component of a concept path (for unmapped detection)."""
    return path.strip("/").split("/")[0]


# ──────────────────────────────────────────────────────────────────────────────
# Main scan
# ──────────────────────────────────────────────────────────────────────────────

def run_scan(config_path: str) -> dict:
    # Load config
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[error] Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"[error] Failed to parse config: {exc}", file=sys.stderr)
        sys.exit(1)

    concepts_config: dict = config.get("concepts", {})

    # Connect to Kado
    try:
        client = KadoClient()
    except Exception as exc:
        print(f"[error] Failed to initialise KadoClient: {exc}", file=sys.stderr)
        sys.exit(1)

    # Collect all configured paths (for unmapped detection)
    all_configured_roots: set[str] = set()
    for key in CONCEPT_KEYS:
        value = concepts_config.get(key)
        for p in extract_all_paths(value):
            root = top_level_folder_name(p)
            if root:
                all_configured_roots.add(root)

    # Scan each concept
    concepts_mapped: dict = {}
    total_notes = 0
    total_files = 0

    for key in CONCEPT_KEYS:
        value = concepts_config.get(key)
        primary_path = extract_primary_path(key, value)

        print(f"[scan] concept={key} path={primary_path!r}", file=sys.stderr)

        if not primary_path:
            concepts_mapped[key] = {"path": None, "note_count": 0, "file_count": 0}
            continue

        scan = scan_path(client, primary_path)
        entry: dict = {
            "path": primary_path,
            "note_count": scan["note_count"],
            "file_count": scan["file_count"],
        }

        if key == "atomic_note" and scan["subdirectories"]:
            # Report subdirs; flag Dewey-numbered ones
            subdirs = scan["subdirectories"]
            for sub in subdirs:
                sub["dewey"] = is_dewey_dir(sub["name"])
            entry["subdirectories"] = subdirs

        total_notes += scan["note_count"]
        total_files += scan["file_count"]

        concepts_mapped[key] = entry

    # Scan vault root for unmapped folders using depth=1 to get direct children.
    print("[scan] scanning vault root for unmapped folders", file=sys.stderr)
    unmapped_folders: list[str] = []
    try:
        root_items = client.list_dir("/", depth=1)
        root_folder_names: set[str] = set()
        for item in root_items:
            if item.get("type") != "folder":
                continue
            name = item.get("name", "")
            if name and name not in all_configured_roots:
                root_folder_names.add(name)
        unmapped_folders = sorted(name + "/" for name in root_folder_names)
    except Exception as exc:
        print(f"[warn] Could not list vault root: {exc}", file=sys.stderr)

    return {
        "vault_structure": {
            "total_notes": total_notes,
            "total_files": total_files,
            "concepts_mapped": concepts_mapped,
            "unmapped_folders": unmapped_folders,
        }
    }


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan vault folder structure via Kado and output JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default="config/vault-config.yaml",
        help="Path to vault-config.yaml (default: config/vault-config.yaml)",
    )
    args = parser.parse_args()

    result = run_scan(args.config)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
