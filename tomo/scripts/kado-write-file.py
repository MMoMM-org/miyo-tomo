#!/usr/bin/env python3
# version: 0.4.0
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

On OVERWRITE, Kado requires the ``expectedModified`` optimistic-concurrency guard.
This script AUTO-RESOLVES it: before the write it fetches the target's current
``modified`` (read_note for .md, read_file for other) and threads it into the
write. A NOT_FOUND read means the target is new → no guard (plain create).
``--expected-modified <ms>`` overrides the fetch. ``--no-overwrite`` wins over
``--expected-modified`` (refuse-if-exists takes precedence, before any fetch/write).

Exit codes:
  0 — file written successfully
  1 — Kado returned an error (connect / read / non-conflict write)
  2 — I/O or argument error
  3 — --no-overwrite: vault path already exists; no write performed.
      stdout: EXISTS:<vault-path>  (T4.2 reads this exact contract — do not change)
  4 — optimistic-concurrency conflict: the vault path changed since the guard read
      (expectedModified mismatch). Retry.

--no-overwrite works for all extensions: KadoClient.path_exists() routes the
existence probe by extension (.md via read_frontmatter, non-.md via read_file),
because Kado's frontmatter/note operations reject non-.md paths with
VALIDATION_ERROR rather than NOT_FOUND. (Fixed after the spec 026 live walk,
where a .base collision check errored out and the write fell back off-pipeline.)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import (  # noqa: E402
    KadoClient,
    KadoConcurrencyError,
    KadoError,
    KadoNotFoundError,
)


def _is_concurrency_conflict(exc: KadoError) -> bool:
    """True iff a write error is an optimistic-concurrency conflict.

    write_note/write_file raise the generic KadoToolError (not KadoConcurrencyError)
    on a mismatch — the tool-level message carries the signature. Detect both the
    typed exception and the message signature write_frontmatter uses.
    """
    if isinstance(exc, KadoConcurrencyError):
        return True
    msg = str(exc).lower()
    return "expectedmodified" in msg and "mismatch" in msg


def _resolve_expected_modified(
    client: KadoClient, vault: str, is_markdown: bool
) -> int | None:
    """Fetch the target's current `modified` as the overwrite guard.

    Returns the timestamp, or None when the target does not exist yet (NOT_FOUND
    → plain create, no guard). Any other read error propagates as KadoError.
    """
    try:
        result = client.read_note(vault) if is_markdown else client.read_file(vault)
    except KadoNotFoundError:
        return None  # new file — no concurrency guard needed
    return result.get("modified") if isinstance(result, dict) else None


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
            "Wins over --expected-modified when both are given."
        ),
    )
    p.add_argument(
        "--expected-modified",
        type=int,
        default=None,
        metavar="MS",
        help=(
            "Explicit optimistic-concurrency guard for an overwrite (the target's "
            "last-known `modified` ms timestamp). Skips the auto-fetch. Without this, "
            "the script fetches the current `modified` before writing."
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
    if args.no_overwrite:
        try:
            exists = client.path_exists(args.vault)
        except KadoError as exc:
            print(f"error: cannot check vault path: {exc}", file=sys.stderr)
            return 1
        if exists:
            print(f"EXISTS:{args.vault}")
            return 3

    # Markdown → operation="note"; anything else → operation="file" (base64).
    is_markdown = args.vault.lower().endswith(".md")
    op = "note" if is_markdown else "file"

    # Resolve the overwrite guard: an explicit --expected-modified wins; otherwise
    # fetch the target's current `modified` (NOT_FOUND → new file → no guard).
    if args.expected_modified is not None:
        expected_modified = args.expected_modified
    else:
        try:
            expected_modified = _resolve_expected_modified(client, args.vault, is_markdown)
        except KadoError as exc:
            print(f"error: cannot read vault path for concurrency guard: {exc}", file=sys.stderr)
            return 1

    try:
        if is_markdown:
            result = client.write_note(
                args.vault, data.decode("utf-8"), expected_modified=expected_modified
            )
        else:
            result = client.write_file(
                args.vault, data, expected_modified=expected_modified
            )
    except UnicodeDecodeError as exc:
        print(
            f"error: --vault ends in .md but content is not UTF-8 text: {exc}",
            file=sys.stderr,
        )
        return 2
    except KadoError as exc:
        if _is_concurrency_conflict(exc):
            print(
                f"error: kado-write operation={op}: vault path changed since read "
                f"(expectedModified mismatch) — retry: {exc}",
                file=sys.stderr,
            )
            return 4
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
