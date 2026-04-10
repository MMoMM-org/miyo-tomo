#!/usr/bin/env python3
# version: 0.1.0
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

    Returns:
        {
            "note_count": int,
            "file_count": int,
            "subdirectories": [ {"name": str, "note_count": int}, ... ]  # folders only
        }
    """
    result = {"note_count": 0, "file_count": 0, "subdirectories": []}

    if not path:
        return result

    try:
        items = client.list_dir(path)
    except Exception as exc:
        print(f"[warn] Could not list {path!r}: {exc}", file=sys.stderr)
        return result

    for item in items:
        item_type = item.get("type", "")
        name = item.get("name", "")

        if item_type == "file":
            result["file_count"] += 1
            if name.endswith(".md"):
                result["note_count"] += 1
        elif item_type == "folder":
            # Scan subdirectory for its note count
            sub_path = path.rstrip("/") + "/" + name + "/"
            sub_notes = _count_notes_in_dir(client, sub_path)
            result["subdirectories"].append({"name": name, "note_count": sub_notes})

    return result


def _count_notes_in_dir(client: KadoClient, path: str) -> int:
    """Return count of .md files directly inside path."""
    try:
        items = client.list_dir(path)
    except Exception as exc:
        print(f"[warn] Could not list {path!r}: {exc}", file=sys.stderr)
        return 0
    return sum(1 for i in items if i.get("type") == "file" and i.get("name", "").endswith(".md"))


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

    # Scan vault root for unmapped folders
    print("[scan] scanning vault root for unmapped folders", file=sys.stderr)
    unmapped_folders: list[str] = []
    try:
        root_items = client.list_dir("")
        for item in root_items:
            if item.get("type") == "folder":
                name = item.get("name", "")
                if name and name not in all_configured_roots:
                    unmapped_folders.append(name + "/")
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
