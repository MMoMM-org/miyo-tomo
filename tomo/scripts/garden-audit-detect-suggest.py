#!/usr/bin/env python3
# version: 0.1.0
"""garden-audit-detect-suggest.py — decide whether a bare /garden-audit is a suggest run.

The garden-auditor agent calls this at Step 1 (mode resolution) when the user typed a
bare `/garden-audit` with no mode token. It finds the NEWEST published garden-audit
report in the vault and decides whether it has UN-RUN suggestion requests — i.e. the
next action should be a suggest enrichment, not a fresh scan.

WHY a wire-based signal (not the markdown box): the Tomo-Editor writes suggest requests
into the WIRE (top-level suggest_pending, per-finding decision.suggest_requested) and
never ticks the markdown `- [x] Suggest targets` box — so grepping the markdown misses
every editor-driven request. Two channels, either → pending:
  - wire top-level `suggest_pending: true` (editor path — the primary signal), OR
  - a markdown `- [x] Suggest targets` block with no `Pick one` pick list / `No
    suggestions found` note (--suggest not yet run — the .md-only fallback).

Output contract (the agent branches on stdout):
  - pending  → print the report .md vault path (REPORT_VAULT) and exit 0.
  - not pending / no report / any Kado error → print NOTHING and exit 0 (fail-open →
    the agent falls through to a fresh audit). Diagnostics go to stderr.

No CLI args — the agent calls it bare from the instance cwd (KadoClient resolves the
Kado URL + token from .mcp.json).

Design notes: docs/tomo/scripts/garden-audit-detect-suggest.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402

# A ticked Suggest box in the markdown (the .md-only channel).
_RE_SUGGEST_TICKED = re.compile(
    r"^\s*-\s+\[x\]\s+Suggest targets\b", re.MULTILINE | re.IGNORECASE
)
# Markers a --suggest run leaves in an enriched block (either = fulfilled).
_FULFILLED_MARKERS = ("Pick one", "No suggestions found")
# Finding-block splitter (### F01 …).
_RE_FINDING = re.compile(r"^###\s+F\d+\b", re.MULTILINE)


def _markdown_suggest_pending(body: str) -> bool:
    """True if any `### F` block ticks Suggest but carries no enriched pick list."""
    for block in _RE_FINDING.split(body):
        if _RE_SUGGEST_TICKED.search(block) and not any(
            m in block for m in _FULFILLED_MARKERS
        ):
            return True
    return False


def detect(client: KadoClient) -> str | None:
    """Return the newest garden-audit report .md path if it has un-run suggests, else None."""
    wires = [
        r for r in client.search_by_name("*_garden-audit.json")
        if r.get("path", "").endswith("_garden-audit.json")
    ]
    if not wires:
        return None
    # Newest first — mtime is the robust signal; the ts-prefixed name is the tiebreak.
    wires.sort(key=lambda r: (r.get("modified", 0), r.get("path", "")), reverse=True)
    wire_path = wires[0]["path"]
    report_path = wire_path[: -len(".json")] + ".md"

    # Wire channel (primary): top-level suggest_pending.
    try:
        wire = json.loads(client.read_file_bytes(wire_path))
        if isinstance(wire, dict) and wire.get("suggest_pending") is True:
            return report_path
    except (KadoError, json.JSONDecodeError, OSError) as exc:
        print(f"detect-suggest: wire unreadable ({exc})", file=sys.stderr)

    # Markdown channel (.md-only fallback).
    try:
        body = client.read_note(report_path).get("content", "")
        if _markdown_suggest_pending(body):
            return report_path
    except (KadoError, OSError) as exc:
        print(f"detect-suggest: report unreadable ({exc})", file=sys.stderr)

    return None


def main() -> int:
    try:
        client = KadoClient()
        report = detect(client)
    except (KadoError, Exception) as exc:  # noqa: BLE001 — fail-open by contract
        print(f"detect-suggest: no detection ({exc})", file=sys.stderr)
        return 0
    if report:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
