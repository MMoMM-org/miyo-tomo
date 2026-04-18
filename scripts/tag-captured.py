#!/usr/bin/env python3
# version: 0.2.0
"""tag-captured.py — Tag processed inbox items with #<prefix>/captured.

Reads the state-file, finds all items with status=done, and adds the
lifecycle tag to each item's frontmatter via Kado. Idempotent — skips
items that already have the tag.

Called by the orchestrator after successfully writing the suggestions
document to the vault (Phase D).

Usage:
    python3 scripts/tag-captured.py --state tomo-tmp/inbox-state.jsonl

Exit codes:
    0 — all done items tagged (or already tagged)
    1 — one or more items failed (partial, logged to stderr)
    2 — fatal error (no Kado connection, no state-file)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402


def load_tag_prefix(config_path: str = "config/vault-config.yaml") -> str:
    """Load lifecycle tag_prefix from vault-config.yaml."""
    if not os.path.isfile(config_path):
        return "MiYo-Tomo"
    try:
        with open(config_path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("tag_prefix:"):
                    val = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    except OSError:
        pass
    return "MiYo-Tomo"


def last_state_per_stem(state_path: Path) -> dict[str, dict]:
    """Read state-file and return the last entry per stem."""
    state: dict[str, dict] = {}
    for line in state_path.read_text(encoding="utf-8").strip().splitlines():
        entry = json.loads(line)
        state[entry["stem"]] = entry
    return state


def has_tag(tags: list, tag: str) -> bool:
    """Check if a tag (with or without #) is in the list."""
    tag_clean = tag.lstrip("#")
    for t in tags:
        if str(t).lstrip("#") == tag_clean:
            return True
    return False


def add_tag_to_frontmatter(client: KadoClient, path: str, tag: str) -> bool:
    """Read note frontmatter, add tag if missing, write back.

    Returns True if tag was added or already present, False on error.
    """
    try:
        result = client.read_note(path)
        content = result.get("content", "")
        modified = result.get("modified")
    except KadoError as exc:
        print(f"  [error] Cannot read {path}: {exc}", file=sys.stderr)
        return False

    # Parse frontmatter
    if not content.startswith("---"):
        print(f"  [warn] {path}: no frontmatter found, skipping", file=sys.stderr)
        return False

    fm_end = content.find("---", 3)
    if fm_end == -1:
        print(f"  [warn] {path}: malformed frontmatter, skipping", file=sys.stderr)
        return False

    fm_text = content[3:fm_end]
    body = content[fm_end:]

    # Find tags in frontmatter
    tag_clean = tag.lstrip("#")

    # Check if tag already present
    if tag_clean in fm_text:
        print(f"  [skip] {path}: already has {tag}", file=sys.stderr)
        return True

    # Find the tags line/block and append
    lines = fm_text.splitlines()
    new_lines = []
    tag_added = False
    in_tags_block = False

    for line in lines:
        new_lines.append(line)
        stripped = line.strip()

        # Detect tags field
        if re.match(r"^tags\s*:", stripped):
            # Inline tags: tags: [a, b] or tags:
            if "[" in stripped:
                # Inline array — insert before closing bracket
                new_lines[-1] = line.rstrip("]").rstrip() + f", {tag_clean}]"
                tag_added = True
            elif stripped == "tags:" or stripped == "tags: []":
                # Empty or block start — next lines are list items
                in_tags_block = True
            else:
                in_tags_block = True
        elif in_tags_block:
            if stripped.startswith("- "):
                continue  # keep collecting tag lines
            else:
                # End of tag block — insert new tag before this line
                # Find indentation from previous tag lines
                indent = "  "
                new_lines.insert(-1, f"{indent}- {tag_clean}")
                tag_added = True
                in_tags_block = False

    # If we were still in the tag block at EOF
    if in_tags_block and not tag_added:
        new_lines.append(f"  - {tag_clean}")
        tag_added = True

    # If no tags field found at all, add one
    if not tag_added:
        new_lines.append("tags:")
        new_lines.append(f"  - {tag_clean}")

    new_fm = "\n".join(new_lines)
    # Ensure newline before closing --- (body starts with ---)
    if new_fm and not new_fm.endswith("\n"):
        new_fm += "\n"
    new_content = f"---{new_fm}{body}"

    try:
        client.write_note(path, new_content, expected_modified=modified)
        return True
    except KadoError as exc:
        print(f"  [error] Cannot write {path}: {exc}", file=sys.stderr)
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="Tag done items with lifecycle captured tag.")
    p.add_argument("--state", required=True, help="Path to inbox-state.jsonl")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    args = p.parse_args()

    state_path = Path(args.state)
    if not state_path.exists():
        print(f"FATAL: state-file not found: {state_path}", file=sys.stderr)
        return 2

    prefix = load_tag_prefix(args.config)
    tag = f"{prefix}/captured"

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"FATAL: Cannot connect to Kado: {exc}", file=sys.stderr)
        return 2

    state = last_state_per_stem(state_path)
    done_stems = [s for s, e in state.items() if e.get("status") == "done"]

    if not done_stems:
        print("tag-captured: no done items to tag", file=sys.stderr)
        return 0

    tagged = 0
    errors = 0
    for stem in sorted(done_stems):
        entry = state[stem]
        path = entry.get("path", "")
        if not path:
            continue

        print(f"  [{stem}] tagging {path}", file=sys.stderr)
        if add_tag_to_frontmatter(client, path, tag):
            tagged += 1
        else:
            errors += 1

    print(
        f"tag-captured: tagged={tagged} errors={errors} prefix={prefix}",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
