#!/usr/bin/env python3
# version: 0.1.0
"""upload-rendered.py — Upload Pass-2 rendered outputs to the vault via Kado.

Reads `<rendered-dir>/manifest.json` and uploads each rendered note + the two
instruction-set artefacts (`instructions.md`, `instructions.json`) to the
vault inbox via Kado. Replaces what was Step 4 of the `instruction-builder`
agent — pure I/O orchestration with no LLM judgement involved.

Inputs (read from rendered-dir):
  - manifest.json       — list of rendered file entries (rendered_file basename
                          required; other fields ignored here)
  - instructions.md     — human-readable instruction set
  - instructions.json   — machine-readable instruction set (carries `generated`
                          ISO timestamp used to derive the YYYY-MM-DD_HHMM
                          filename prefix on the vault side)
  - <rendered_file>     — one markdown file per manifest entry

Outputs (written to vault under <inbox>):
  - <rendered_file>                              — operation="note"
  - <YYYY-MM-DD_HHMM>_instructions.md            — operation="note"
  - <YYYY-MM-DD_HHMM>_instructions.json          — operation="file" (base64)

Usage:
  python3 scripts/upload-rendered.py \\
    --rendered-dir tomo-tmp/rendered \\
    --inbox "100 Inbox/"

  # Override timestamp derivation (rare):
  python3 scripts/upload-rendered.py \\
    --rendered-dir tomo-tmp/rendered \\
    --inbox "100 Inbox/" \\
    --timestamp 2026-04-30_1432

Exit codes:
  0 — all uploads succeeded
  1 — one or more Kado writes failed (partial — earlier writes already landed)
  2 — fatal: bad input, missing manifest, malformed instructions.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402


def _derive_timestamp(generated: str) -> str:
    """Convert `2026-04-30T14:32:18Z` → `2026-04-30_1432`.

    Tolerates both `Z` and `+00:00` UTC suffixes (renderer emits `Z`).
    """
    s = generated.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise SystemExit(
            f"error: cannot parse `generated` timestamp {generated!r}: {exc}"
        ) from exc
    return dt.strftime("%Y-%m-%d_%H%M")


def _join(inbox: str, name: str) -> str:
    return inbox.rstrip("/") + "/" + name.lstrip("/")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Upload Pass-2 rendered outputs to the vault via Kado."
    )
    p.add_argument(
        "--rendered-dir", required=True,
        help="Local directory containing manifest.json + rendered files + instructions.{md,json}.",
    )
    p.add_argument(
        "--inbox", required=True,
        help="Vault inbox path (with trailing slash), e.g. \"100 Inbox/\".",
    )
    p.add_argument(
        "--timestamp",
        help="YYYY-MM-DD_HHMM prefix for the instruction-set filenames. "
             "Derived from instructions.json `generated` if omitted.",
    )
    args = p.parse_args()

    rendered_dir = Path(args.rendered_dir)
    if not rendered_dir.is_dir():
        print(f"error: rendered-dir not found: {rendered_dir}", file=sys.stderr)
        return 2

    manifest_path = rendered_dir / "manifest.json"
    instructions_md_path = rendered_dir / "instructions.md"
    instructions_json_path = rendered_dir / "instructions.json"
    for required in (manifest_path, instructions_md_path, instructions_json_path):
        if not required.is_file():
            print(f"error: required file missing: {required}", file=sys.stderr)
            return 2

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: manifest.json is not valid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        instructions = json.loads(instructions_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: instructions.json is not valid JSON: {exc}", file=sys.stderr)
        return 2

    timestamp = args.timestamp or _derive_timestamp(instructions.get("generated", ""))

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"error: cannot connect to Kado: {exc}", file=sys.stderr)
        return 1

    failures: list[str] = []
    notes_written = 0

    # ── Rendered notes (one per manifest entry) ──────────────────────
    for entry in manifest:
        rendered_file = entry.get("rendered_file")
        if not rendered_file:
            failures.append(f"manifest entry missing rendered_file: {entry!r}")
            continue
        local = rendered_dir / rendered_file
        if not local.is_file():
            failures.append(f"rendered file not on disk: {local}")
            continue
        body = local.read_text(encoding="utf-8")
        target = _join(args.inbox, rendered_file)
        try:
            client.write_note(target, body)
        except KadoError as exc:
            failures.append(f"kado-write note {target}: {exc}")
            continue
        notes_written += 1
        print(f"  [note] {target} ({len(body)} chars)", file=sys.stderr)

    # ── instructions.md ──────────────────────────────────────────────
    md_target = _join(args.inbox, f"{timestamp}_instructions.md")
    md_body = instructions_md_path.read_text(encoding="utf-8")
    try:
        client.write_note(md_target, md_body)
        print(f"  [note] {md_target} ({len(md_body)} chars)", file=sys.stderr)
    except KadoError as exc:
        failures.append(f"kado-write note {md_target}: {exc}")

    # ── instructions.json ────────────────────────────────────────────
    json_target = _join(args.inbox, f"{timestamp}_instructions.json")
    json_bytes = instructions_json_path.read_bytes()
    try:
        client.write_file(json_target, json_bytes)
        print(f"  [file] {json_target} ({len(json_bytes)} bytes)", file=sys.stderr)
    except KadoError as exc:
        failures.append(f"kado-write file {json_target}: {exc}")

    if failures:
        print("", file=sys.stderr)
        print(f"upload-rendered: {len(failures)} failure(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        print(
            f"upload-rendered: {notes_written} note(s) + "
            f"{2 - sum(1 for f in failures if 'instructions.' in f)} instruction artefact(s) written",
            file=sys.stderr,
        )
        return 1

    print(
        f"upload-rendered: {notes_written} note(s) + 2 instruction artefact(s) "
        f"written under {args.inbox}",
        file=sys.stderr,
    )
    print(
        f"  ↳ {timestamp}_instructions.md / .json",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
