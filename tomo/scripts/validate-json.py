#!/usr/bin/env python3
# version: 0.1.0
"""validate-json.py — Deterministic JSON parse-gate for .base/.canvas artefacts.

WHY this script exists (ADR-4 + ADR-9):

ADR-4 (.base/.canvas via direct-compose → operation=file):
  JSON artefacts such as Obsidian .base and .canvas files are composed directly
  and written to the vault via kado-write-file.py operation=file.  A malformed
  file would land in the vault and silently corrupt the user's canvas or base.
  This gate intercepts the file BEFORE any write: if json.loads fails here, the
  write is aborted and the vault is never touched.

ADR-9 (extract safety logic to deterministic, testable scripts — Constitution L1):
  Whether a JSON file is structurally valid must not depend on LLM judgment.
  An LLM inspecting the content can hallucinate "looks fine" even on broken
  output.  A deterministic json.loads call either succeeds or raises — no drift
  between runs, no model-version sensitivity.  The gate is also fully unit-testable
  in both directions (valid → exit 0, malformed → exit 1), satisfying the MiYo
  Constitution L1 requirement that safety properties be covered by automated tests.

Usage:
  python3 tomo/scripts/validate-json.py <path>

Exit codes:
  0 — file is valid JSON
  1 — file is malformed JSON (parse error printed to stderr)
  1 — file does not exist (error printed to stderr)

The script is read-only — it WRITES NOTHING.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("Usage: validate-json.py <path>", file=sys.stderr)
        return 1

    path = Path(args[0])
    if not path.exists():
        print(f"validate-json: file not found: {path}", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"validate-json: cannot read {path}: {exc}", file=sys.stderr)
        return 1

    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"validate-json: {path}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
