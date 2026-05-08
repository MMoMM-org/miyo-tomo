#!/usr/bin/env python3
# version: 0.4.0
"""tag-captured.py — Tag processed inbox items with #<prefix>/captured.

Reads the state-file, finds all items with status=done, and adds the
lifecycle tag to each item's frontmatter via Kado. Idempotent — skips
items that already have the tag. Also skips non-markdown items
(audio, binaries, stray text files) since they have no frontmatter
for the tag to live in.

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
from lib.squelch_persist import persist_rejected_clusters  # noqa: E402


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


def load_squelch_config(config_path: str = "config/vault-config.yaml") -> dict:
    """Load squelch-related config from vault-config.yaml.

    Returns a dict with at least ``squelch_runs`` (int, default 3).
    Tolerates missing or unreadable config file.
    """
    squelch_runs = 3
    if not os.path.isfile(config_path):
        return {"squelch_runs": squelch_runs}
    try:
        import yaml  # type: ignore[import]
        with open(config_path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        squelch_runs = int(
            cfg.get("tomo", {})
            .get("moc_proposal", {})
            .get("squelch_runs", 3)
        )
    except Exception:  # noqa: BLE001
        pass
    return {"squelch_runs": squelch_runs}


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
    p.add_argument(
        "--squelch-registry",
        default="state/moc-squelch.json",
        help="Path to MOC squelch registry (default: state/moc-squelch.json)",
    )
    args = p.parse_args()

    state_path = Path(args.state)
    if not state_path.exists():
        print(f"FATAL: state-file not found: {state_path}", file=sys.stderr)
        return 2

    prefix = load_tag_prefix(args.config)
    tag = f"{prefix}/captured"

    squelch_cfg = load_squelch_config(args.config)
    registry_path = Path(args.squelch_registry)

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
    skipped_non_md = 0
    squelched_total = 0

    for stem in sorted(done_stems):
        entry = state[stem]
        path = entry.get("path", "")
        if not path:
            continue

        # Lifecycle tags live in markdown frontmatter. Any non-.md path
        # is a skip — covers audio (.m4a, .mp3, .wav, .ogg, .opus, .flac,
        # .aac), plain text (.txt), binaries, and anything else the
        # inbox may end up carrying (Phase 0a voice makes the inbox
        # polyglot). Without this guard Kado's `operation=note` rejects
        # non-.md paths with VALIDATION_ERROR, which would otherwise
        # count as a hard failure and fail the whole tag-captured run.
        if not path.lower().endswith(".md"):
            print(f"  [skip] {stem}: non-markdown path, no frontmatter ({path})",
                  file=sys.stderr)
            skipped_non_md += 1
            continue

        print(f"  [{stem}] tagging {path}", file=sys.stderr)
        if add_tag_to_frontmatter(client, path, tag):
            tagged += 1
        else:
            errors += 1
            continue  # Don't attempt squelch-persist if tagging failed

        # ── Squelch-persist: for MOC proposal-docs, record rejected clusters ──
        filename = os.path.basename(path)
        if filename.startswith("tomo-moc-proposal-") and filename.endswith(".md"):
            try:
                result = client.read_note(path)
                doc_text = result.get("content", "")
            except KadoError as exc:
                print(
                    f"  [warn] {stem}: cannot read proposal-doc for squelch "
                    f"({exc}); skipping squelch-persist",
                    file=sys.stderr,
                )
                doc_text = ""
            if doc_text:
                try:
                    n_squelched = persist_rejected_clusters(
                        doc_text,
                        filename=filename,
                        registry_path=registry_path,
                        config=squelch_cfg,
                    )
                    if n_squelched:
                        print(
                            f"  [{stem}] squelch-persist: {n_squelched} rejected "
                            f"cluster(s) written to {registry_path}",
                            file=sys.stderr,
                        )
                        squelched_total += n_squelched
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"  [warn] {stem}: squelch-persist failed ({exc}); continuing",
                        file=sys.stderr,
                    )

    print(
        f"tag-captured: tagged={tagged} errors={errors} "
        f"skipped_non_md={skipped_non_md} squelched={squelched_total} prefix={prefix}",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
