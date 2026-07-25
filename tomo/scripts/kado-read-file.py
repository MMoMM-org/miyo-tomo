#!/usr/bin/env python3
# version: 0.1.0
"""kado-read-file.py — Download a vault file to a local path via Kado.

Read counterpart to kado-write-file.py. Auto-selects the Kado read operation by
source extension:
  - `.md`  → operation="note" (markdown body as text)
  - other  → operation="file" (base64 → raw bytes: JSON wires, YAML, images, …)

Why a script, not an inline `kado-read` tool call: the content is pulled via this
script's own Kado client and written straight to disk, so a large artefact (e.g. a
published garden-audit report + wire) NEVER passes through the agent's
output-token budget. Mirrors kado-write-file.py's rationale in the other direction.

Usage:
  python3 scripts/kado-read-file.py \\
    --vault "100 Inbox/2026-07-21_garden-audit.md" \\
    --local tomo-tmp/suggest-report.md

Exit codes:
  0 — file read + written successfully
  1 — Kado returned an error (incl. NOT_FOUND)
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
        description="Download a vault file to a local path via Kado."
    )
    p.add_argument(
        "--vault", required=True,
        help="Vault-relative source path, e.g. \"100 Inbox/2026-07-21_garden-audit.md\".",
    )
    p.add_argument(
        "--local", required=True,
        help="Local destination path to write the downloaded content to.",
    )
    args = p.parse_args()

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"error: cannot connect to Kado: {exc}", file=sys.stderr)
        return 1

    local_path = Path(args.local)
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if args.vault.endswith(".md"):
            result = client.read_note(args.vault)
            local_path.write_text(result.get("content") or "", encoding="utf-8")
        else:
            local_path.write_bytes(client.read_file_bytes(args.vault))
    except KadoError as exc:
        print(f"error: cannot read vault file {args.vault!r}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: cannot write local file {args.local!r}: {exc}", file=sys.stderr)
        return 2

    print(f"kado-read-file: {args.vault} → {args.local}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
