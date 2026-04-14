#!/usr/bin/env python3
# version: 0.2.0
"""
state-scanner.py — Discover source inbox items by lifecycle state via Kado tag search.

Source items use lifecycle tags (`captured`, `active`). Workflow documents
(suggestions, instructions) use checkboxes instead of tags — those are
discovered by the inbox command via `listDir` + content parsing, not by
this script.

Modes:

  --state STATE   Find all items with the given state, output JSON array.
                  Valid states: captured, active.
  --discover      Check for captured items (Pass 1 fallback).
  --all           Scan captured + active, output grouped by state.

Usage:
    python state-scanner.py --state captured [--config PATH]
    python state-scanner.py --discover [--config PATH]
    python state-scanner.py --all [--config PATH]
"""

import argparse
import json
import os
import sys

import yaml

# Allow importing from scripts/lib/
sys.path.insert(0, os.path.dirname(__file__))
from lib.kado_client import KadoClient, KadoError  # noqa: E402


# ── Constants ──────────────────────────────────────────────────────────────────

LIFECYCLE_STATES = [
    "captured",
    "active",
]

DEFAULT_TAG_PREFIX = "MiYo-Tomo"
DEFAULT_CONFIG = "config/vault-config.yaml"

# --discover mode only checks captured items (Pass 1 fallback).
# Workflow document states (approved suggestions, applied instructions) are
# discovered by the inbox command via listDir + checkbox parsing.
DISCOVER_PRIORITY = ["captured"]

DISCOVER_ACTIONS = {
    "captured": "pass1",
}


# ── Config loading ─────────────────────────────────────────────────────────────

def load_tag_prefix(config_path: str) -> str:
    """Load tag_prefix from vault-config.yaml lifecycle section.

    Returns the configured prefix, or DEFAULT_TAG_PREFIX if the config
    file is missing, unreadable, or does not specify a prefix.
    """
    if not os.path.isfile(config_path):
        print(
            f"[warn] Config file not found: {config_path!r} — using default prefix "
            f"{DEFAULT_TAG_PREFIX!r}",
            file=sys.stderr,
        )
        return DEFAULT_TAG_PREFIX

    try:
        with open(config_path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        print(
            f"[warn] Failed to parse config {config_path!r}: {exc} — using default prefix",
            file=sys.stderr,
        )
        return DEFAULT_TAG_PREFIX

    if not isinstance(config, dict):
        return DEFAULT_TAG_PREFIX

    lifecycle = config.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return DEFAULT_TAG_PREFIX

    prefix = lifecycle.get("tag_prefix")
    return prefix if isinstance(prefix, str) and prefix.strip() else DEFAULT_TAG_PREFIX


# ── Kado helpers ───────────────────────────────────────────────────────────────

def build_tag(prefix: str, state: str) -> str:
    """Build the full tag string for a lifecycle state."""
    return f"#{prefix}/{state}"


def scan_state(client: KadoClient, prefix: str, state: str) -> list[dict]:
    """Search vault for notes tagged with the given lifecycle state.

    Returns a list of item dicts: [{"path": str, "title": str}, ...]
    """
    tag = build_tag(prefix, state)
    print(f"[scan] state={state!r} tag={tag!r}", file=sys.stderr)

    try:
        results = client.search_by_tag(tag)
    except KadoError as exc:
        print(f"[error] Tag search failed for {tag!r}: {exc}", file=sys.stderr)
        raise

    items = []
    for entry in results:
        path = entry.get("path", "")
        # Derive title from filename (strip directory and .md extension)
        basename = os.path.basename(path)
        title = basename[:-3] if basename.endswith(".md") else basename
        items.append({"path": path, "title": title})

    return items


# ── Output builders ────────────────────────────────────────────────────────────

def build_state_result(state: str, items: list[dict], action: str = None) -> dict:
    """Build the standard output dict for a state scan."""
    result = {"state": state, "items": items}
    if action is not None:
        result["action"] = action
    return result


# ── Scan modes ─────────────────────────────────────────────────────────────────

def mode_state(client: KadoClient, prefix: str, state: str) -> dict:
    """--state MODE: scan a single state, return items."""
    if state not in LIFECYCLE_STATES:
        print(
            f"[error] Unknown state {state!r}. Valid states: {', '.join(LIFECYCLE_STATES)}",
            file=sys.stderr,
        )
        sys.exit(1)

    items = scan_state(client, prefix, state)
    return build_state_result(state, items)


def mode_discover(client: KadoClient, prefix: str) -> dict:
    """--discover MODE: priority scan, return first state with items + action."""
    for state in DISCOVER_PRIORITY:
        items = scan_state(client, prefix, state)
        if items:
            action = DISCOVER_ACTIONS[state]
            print(
                f"[discover] Found {len(items)} item(s) in state={state!r} → action={action!r}",
                file=sys.stderr,
            )
            return build_state_result(state, items, action=action)

    print("[discover] No pending items found → idle", file=sys.stderr)
    return build_state_result("", [], action="idle")


def mode_all(client: KadoClient, prefix: str) -> dict:
    """--all MODE: scan every state, return grouped results."""
    grouped = {}
    for state in LIFECYCLE_STATES:
        items = scan_state(client, prefix, state)
        grouped[state] = items
        print(f"[scan] state={state!r} → {len(items)} item(s)", file=sys.stderr)
    return {"states": grouped}


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover inbox items by lifecycle state via Kado tag search.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--state",
        metavar="STATE",
        help=(
            f"Find all items with the given state "
            f"({', '.join(LIFECYCLE_STATES)})"
        ),
    )
    mode_group.add_argument(
        "--discover",
        action="store_true",
        help=(
            "Priority discovery: check applied→confirmed→captured, "
            "return first state with items and the action to take."
        ),
    )
    mode_group.add_argument(
        "--all",
        action="store_true",
        help="Scan all lifecycle states and output grouped results.",
    )

    parser.add_argument(
        "--config",
        metavar="PATH",
        default=DEFAULT_CONFIG,
        help=f"Path to vault-config.yaml (default: {DEFAULT_CONFIG})",
    )

    args = parser.parse_args()

    # Load config
    prefix = load_tag_prefix(args.config)
    print(f"[config] tag_prefix={prefix!r}", file=sys.stderr)

    # Connect to Kado
    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"[error] Failed to initialise KadoClient: {exc}", file=sys.stderr)
        sys.exit(1)

    # Run the selected mode
    try:
        if args.state:
            result = mode_state(client, prefix, args.state)
        elif args.discover:
            result = mode_discover(client, prefix)
        else:
            result = mode_all(client, prefix)
    except KadoError as exc:
        print(f"[error] Kado error: {exc}", file=sys.stderr)
        sys.exit(1)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
