#!/usr/bin/env python3
# version: 0.2.0
"""kado-write-file.py — Upload a local file to the vault via Kado.

Auto-selects the Kado write operation by target extension:
  - `.md`  → operation="note" (the proper markdown-note path)
  - other  → operation="file" (base64: JSON instruction sets, YAML, images, PDFs)

Why a script, not an inline `kado-write` tool call from an agent: the content is
read from disk and pushed via this script's own Kado client, so it NEVER passes
through the agent's output-token budget. A large artefact (e.g. a 136 KB MOC
proposal-doc) cannot be transported by an inline `kado-write` — the body would
have to be emitted as tool-call args and blows the token limit. Run this script
instead. (docs/ai/memory/decisions.md — "large/many writes → script with
embedded Kado client".)

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

    # Markdown → operation="note"; anything else → operation="file" (base64).
    is_markdown = args.vault.lower().endswith(".md")
    op = "note" if is_markdown else "file"
    try:
        if is_markdown:
            result = client.write_note(args.vault, data.decode("utf-8"))
        else:
            result = client.write_file(args.vault, data)
    except UnicodeDecodeError as exc:
        print(
            f"error: --vault ends in .md but content is not UTF-8 text: {exc}",
            file=sys.stderr,
        )
        return 2
    except KadoError as exc:
        print(f"error: kado-write operation={op} failed: {exc}", file=sys.stderr)
        return 1

    modified = result.get("modified") if isinstance(result, dict) else None
    print(
        f"kado-write-file: {source} ({len(data)} bytes, op={op}) → {args.vault}"
        + (f" (modified={modified})" if modified is not None else ""),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
