#!/usr/bin/env python3
# version: 0.3.0
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

  # Refuse the write if the vault path already exists:
  python3 scripts/kado-write-file.py --no-overwrite \\
    --local tomo-tmp/rendered/artifact.base \\
    --vault "100 Inbox/artifact.base"

Exit codes:
  0 — file written successfully
  1 — Kado returned an error
  2 — I/O or argument error
  3 — --no-overwrite: vault path already exists; no write performed.
      stdout: EXISTS:<vault-path>  (T4.2 reads this exact contract — do not change)

Note on --no-overwrite for non-.md paths: the existence check uses
KadoClient.path_exists(), which internally calls read_frontmatter. That method is
.md-oriented; results for non-.md extensions (e.g. .base, .canvas) may be
unreliable. The primary collision target for --no-overwrite is the .md inbox
artifact path; non-.md collision detection is best-effort only.
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
    p.add_argument(
        "--no-overwrite",
        action="store_true",
        help=(
            "Refuse the write if the vault path already exists. "
            "Signals collision via exit code 3 and prints EXISTS:<vault-path> on stdout. "
            "T4.2 reads this exact contract — do not change the exit code or stdout format."
        ),
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

    # Collision check: refuse write if vault path already exists.
    if args.no_overwrite and client.path_exists(args.vault):
        print(f"EXISTS:{args.vault}")
        return 3

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
