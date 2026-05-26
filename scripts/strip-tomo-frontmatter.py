#!/usr/bin/env python3
# strip-tomo-frontmatter.py — surgical removal of the `tomo:` block from note(s).
# version: 0.2.0
"""Strip the `tomo:` frontmatter block from one or more vault notes via Kado.

Use when:
  - Resetting an instance and you want the source notes clean of lifecycle state.
  - A test/dev run left tomo blocks on user notes that shouldn't carry them.
  - Manual cleanup after a botched /inbox run.

Usage:
  # Explicit paths
  python3 scripts/strip-tomo-frontmatter.py "100 Inbox/Catan Strategien.md" "100 Inbox/Sport.md"

  # All .md notes in one folder (recursive)
  python3 scripts/strip-tomo-frontmatter.py --folder "100 Inbox"

  # Preview (no writes)
  python3 scripts/strip-tomo-frontmatter.py --folder "100 Inbox" --dry-run

Behavior per path:
  1. Read frontmatter via Kado.
  2. If no `tomo:` key → log "clean" and skip.
  3. Otherwise: pop the `tomo` key, write back via kado-write
     operation=frontmatter mode=replace with the remaining keys, guarded by
     optimistic concurrency (`expectedModified` from the read).
  4. On concurrency mismatch: retry once after a fresh read.

Exits 0 on full success (every target either clean or successfully stripped).
Exits 1 if any path fails. Per-path status printed to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
# kado_client lives with the runtime Python in tomo/scripts/lib/ — pull it
# in from there rather than duplicating the library under scripts/.
sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts" / "lib"))

from kado_client import (  # noqa: E402
    KadoClient,
    KadoConcurrencyError,
    KadoError,
    KadoNotFoundError,
    _extract_from_mcp_json,
)


def _running_in_container() -> bool:
    """Best-effort: Docker drops a /.dockerenv marker file."""
    return Path("/.dockerenv").exists()


def build_kado_client() -> KadoClient:
    """Construct a KadoClient that works from BOTH host and container.

    Resolution order:
      1. Standard KadoClient() — picks up KADO_URL/KADO_TOKEN env or .mcp.json
         in cwd (this is what container-side scripts rely on).
      2. Fallback: walk up from this script to find `tomo-instance/.mcp.json`,
         which is the Tomo Docker instance's MCP config. Parse it for the Kado
         URL+token, rewrite `host.docker.internal` → `localhost` when not
         actually inside a container, and pass explicit args to KadoClient.
    """
    try:
        return KadoClient()
    except KadoError as first_err:
        for parent in [SCRIPT_DIR, *SCRIPT_DIR.parents]:
            candidate = parent / "tomo-instance" / ".mcp.json"
            if not candidate.is_file():
                continue
            try:
                cfg = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            url, tok = _extract_from_mcp_json(cfg)
            if not (url and tok):
                continue
            if not _running_in_container():
                url = url.replace("host.docker.internal", "localhost")
            print(
                f"[strip-tomo-frontmatter] using Kado from {candidate} → {url}",
                file=sys.stderr,
            )
            return KadoClient(base_url=url, token=tok)
        # Nothing worked — re-raise the original error
        raise first_err


def collect_paths(args: argparse.Namespace, client: KadoClient) -> list[str]:
    """Build the list of vault-relative .md paths to process."""
    paths: list[str] = list(args.paths or [])
    if args.folder:
        try:
            items = client.list_dir(args.folder, depth=None if args.recursive else 1)
        except KadoError as exc:
            print(f"ERROR: listDir({args.folder!r}) failed: {exc}", file=sys.stderr)
            sys.exit(1)
        for it in items:
            if not isinstance(it, dict):
                continue
            if it.get("type") != "file":
                continue
            p = (it.get("path") or "").lstrip("/")
            if p.endswith(".md"):
                paths.append(p)
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def strip_one(client: KadoClient, path: str, dry_run: bool) -> str:
    """Return one of: 'stripped', 'clean', 'missing', 'error:<msg>'."""
    try:
        result = client.read_frontmatter(path)
    except KadoNotFoundError:
        return "missing"
    except KadoError as exc:
        return f"error:read_frontmatter — {exc}"

    fm = result.get("content")
    if not isinstance(fm, dict):
        # Note has no frontmatter at all → nothing to do.
        return "clean"
    if "tomo" not in fm:
        return "clean"

    new_fm = {k: v for k, v in fm.items() if k != "tomo"}
    if dry_run:
        return "stripped(dry-run)"

    expected_modified = result.get("modified")
    try:
        client.write_frontmatter(
            path,
            frontmatter=new_fm,
            mode="replace",
            expected_modified=expected_modified,
        )
    except KadoConcurrencyError:
        # Someone wrote between our read and our write. Re-read and retry once.
        try:
            result2 = client.read_frontmatter(path)
            fm2 = result2.get("content") or {}
            if "tomo" not in fm2:
                return "clean"  # someone else stripped it in the meantime
            new_fm2 = {k: v for k, v in fm2.items() if k != "tomo"}
            client.write_frontmatter(
                path,
                frontmatter=new_fm2,
                mode="replace",
                expected_modified=result2.get("modified"),
            )
        except KadoError as exc:
            return f"error:retry_failed — {exc}"
    except KadoError as exc:
        return f"error:write_frontmatter — {exc}"
    return "stripped"


def main() -> int:
    p = argparse.ArgumentParser(
        description="Strip the `tomo:` frontmatter block from vault notes via Kado.",
    )
    p.add_argument("paths", nargs="*", help="Explicit vault-relative paths (.md)")
    p.add_argument("--folder", help="Process every .md under this folder")
    p.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Recurse into subfolders when --folder is given (default: on)",
    )
    p.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Only process direct children of --folder",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be stripped without writing",
    )
    args = p.parse_args()

    if not args.paths and not args.folder:
        p.error("supply at least one positional path or --folder")

    client = build_kado_client()
    paths = collect_paths(args, client)
    if not paths:
        print("No paths to process.", file=sys.stderr)
        return 0

    print(
        f"strip-tomo-frontmatter: {len(paths)} path(s) "
        f"({'dry-run' if args.dry_run else 'writing'})",
        file=sys.stderr,
    )

    counts = {"stripped": 0, "stripped(dry-run)": 0, "clean": 0, "missing": 0, "error": 0}
    failures: list[tuple[str, str]] = []
    for path in paths:
        status = strip_one(client, path, args.dry_run)
        if status.startswith("error"):
            counts["error"] += 1
            failures.append((path, status))
            print(f"  ✗ {path}  {status}", file=sys.stderr)
        else:
            counts[status] = counts.get(status, 0) + 1
            mark = {
                "stripped": "✓",
                "stripped(dry-run)": "→",
                "clean": "·",
                "missing": "?",
            }.get(status, " ")
            print(f"  {mark} {path}  {status}", file=sys.stderr)

    print(file=sys.stderr)
    print(
        "Summary: "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v),
        file=sys.stderr,
    )
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
