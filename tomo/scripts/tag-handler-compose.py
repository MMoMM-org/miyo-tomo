#!/usr/bin/env python3
# version: 0.1.0
"""tag-handler-compose.py — Thin orchestration bridge between the interpreter skill and
the deterministic target_structure assembly helper (spec 025 / T4.1a / ADR-3).

The interpreter skill cannot call pure Python helpers directly, so it writes a payload
JSON file and delegates to this script (skill→script→lib pattern). This script:

  1. Reads the payload JSON at argv[1].
  2. Calls target_structure.assemble(section_lines, output_format, cell_values_per_item, marker).
  3. Prints exactly ONE JSON object to stdout:
       {"status": "ok",       "composed_block": "...", "resolved_anchor": {...}}
       {"status": "fallback", "reason": "..."}
       {"status": "error",    "message": "..."} (non-zero exit on bad input)

The script does NOT write the group-result file and does NOT compose prose — the
interpreter skill (step 4) owns that. On fallback the skill composes a plain prose
block and annotates with a warning glyph (FR-19).

No IO beyond reading the payload file and writing stdout. No Kado, no LLM.
Paths are cwd-relative; do NOT rely on SCRIPT_DIR.parent.parent (CON-2 instance layout).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Mirror the import pattern used by sibling scripts (e.g. instruction-render.py):
# insert SCRIPT_DIR onto sys.path so `from lib.X import Y` resolves.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from lib.target_structure import assemble, Fallback  # noqa: E402


# ---------------------------------------------------------------------------
# Public entry point (testable without subprocess)
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> None:
    """Run the compose script.

    Args:
        argv: Argument list — argv[0] is the payload JSON file path.
    """
    if not argv:
        _error_exit("Usage: tag-handler-compose.py <payload.json>")

    payload_path = Path(argv[0])
    if not payload_path.exists():
        _error_exit(f"Payload file not found: {payload_path}")

    try:
        raw = payload_path.read_text(encoding="utf-8")
    except OSError as exc:
        _error_exit(f"Cannot read payload file: {exc}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        _error_exit(f"Malformed JSON payload: {exc}")

    try:
        section_lines = payload["section_lines"]
        output_format = payload["output_format"]
        cell_values_per_item = payload["cell_values_per_item"]
        marker = payload["marker"]
    except (KeyError, TypeError) as exc:
        _error_exit(f"Missing or invalid payload field: {exc}")

    result = assemble(section_lines, output_format, cell_values_per_item, marker)

    if isinstance(result, Fallback):
        print(json.dumps({"status": "fallback", "reason": result.reason}))
    else:
        composed_block, resolved_anchor = result
        print(
            json.dumps(
                {
                    "status": "ok",
                    "composed_block": composed_block,
                    "resolved_anchor": resolved_anchor,
                }
            )
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _error_exit(message: str) -> None:
    """Print a clean JSON error to stdout and exit non-zero."""
    print(json.dumps({"status": "error", "message": message}))
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main(sys.argv[1:])
