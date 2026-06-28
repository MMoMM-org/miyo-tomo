#!/usr/bin/env python3
# version: 0.1.0
"""validate-yaml.py — Deterministic YAML parse-gate for .base artefacts.

WHY this script exists (ADR-4 corrected + ADR-9):

ADR-4 (corrected — .base is YAML, not JSON):
  Obsidian Bases (.base extension) use YAML, not JSON.  The original ADR-4
  assumed both .base and .canvas were JSON; this was incorrect.  .canvas files
  remain JSON (JSON Canvas 1.0 spec) and are gated by validate-json.py.
  .base files are gated here.  The gate intercepts the file BEFORE any vault
  write: if yaml.safe_load raises, the write is aborted and the vault is
  never touched with a malformed file.

ADR-9 (extract safety logic to deterministic, testable scripts — Constitution L1):
  Whether a YAML file is structurally valid must not depend on LLM judgment.
  An LLM inspecting the content can hallucinate "looks fine" even on broken
  output.  A deterministic yaml.safe_load call either succeeds or raises —
  no drift between runs, no model-version sensitivity.  The gate is fully
  unit-testable in both directions (valid → exit 0, malformed → exit 1),
  satisfying the MiYo Constitution L1 requirement that safety properties be
  covered by automated tests.

Extension routing contract (mirrors validate-json.py):
  .canvas  →  validate-json.py  (JSON Canvas 1.0 is JSON)
  .base    →  validate-yaml.py  (Obsidian Bases is YAML)

Usage:
  python3 tomo/scripts/validate-yaml.py <path>

Exit codes:
  0 — file is valid YAML
  1 — file is malformed YAML (parse error printed to stderr)
  1 — file does not exist (error printed to stderr)

The script is read-only — it WRITES NOTHING.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("Usage: validate-yaml.py <path>", file=sys.stderr)
        return 1

    path = Path(args[0])
    if not path.exists():
        print(f"validate-yaml: file not found: {path}", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"validate-yaml: cannot read {path}: {exc}", file=sys.stderr)
        return 1

    try:
        yaml.safe_load(text)
    except yaml.YAMLError as exc:
        print(f"validate-yaml: {path}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
