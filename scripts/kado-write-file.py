#!/usr/bin/env python3
# version: 0.1.0
"""kado-write-file.py — Write a local file to the vault via Kado operation="file".

Kado's `kado-write` operation="note" only accepts markdown. For any other
content type (JSON instruction sets, YAML configs, binary assets, PDFs, images)
operation="file" takes the content as a base64 string. This script is the
deterministic helper so agents don't have to orchestrate the base64 dance in
Bash/prompt text.

Usage:
  python3 scripts/kado-write-file.py \\
    --local tomo-tmp/rendered/instructions.json \\
    --vault "100 Inbox/2026-04-21_1200_instructions.json"

  # Pipe stdin instead of reading a local path:
  cat foo.json | python3 scripts/kado-write-file.py --vault "100 Inbox/foo.json"

Exit codes:
  0 — file written successfully
  1 — Kado returned an error
  2 — I/O or argument error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description="Write a local file to the Obsidian vault via Kado operation=file."
    )
    p.add_argument(
        "--local",
        help="Path to the local file to upload. If omitted, content is read from stdin.",
    )
    p.add_argument(
        "--vault", required=True,
        help="Vault-relative destination path, e.g. \"100 Inbox/2026-04-21_1200_instructions.json\".",
    )
    args = p.parse_args()

    try:
        if args.local:
            data = Path(args.local).read_bytes()
            source = args.local
        else:
            data = sys.stdin.buffer.read()
            source = "<stdin>"
    except OSError as exc:
        print(f"error: cannot read input: {exc}", file=sys.stderr)
        return 2

    if not data:
        print("error: input is empty, refusing to write", file=sys.stderr)
        return 2

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"error: cannot connect to Kado: {exc}", file=sys.stderr)
        return 1

    try:
        result = client.write_file(args.vault, data)
    except KadoError as exc:
        print(f"error: kado-write operation=file failed: {exc}", file=sys.stderr)
        return 1

    modified = result.get("modified") if isinstance(result, dict) else None
    print(
        f"kado-write-file: {source} ({len(data)} bytes) → {args.vault}"
        + (f" (modified={modified})" if modified is not None else ""),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
