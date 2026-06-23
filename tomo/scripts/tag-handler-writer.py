#!/usr/bin/env python3
# version: 0.1.0
"""tag-handler-writer.py — Atomic schema-validated writer for tag-handler configs.

WHY this script exists:
  The tomo-tag-handler-wizard skill assembles a handler dict via AskUserQuestion
  and needs to persist it to config/tag-handlers/<id>.json. The write must be
  (a) schema-validated against tomo/schemas/tag-handler.schema.json BEFORE any
      file is created, and (b) atomic (write temp + os.replace) so a validation
      failure leaves zero partial files on disk.
  This script is the tested, deterministic writer that the skill delegates to —
  the skill is pure glue; validation and I/O live here.

  Mirrors the idiom of vault-config-writer.py (validate-then-write, abort on
  invalid, exit codes 0/1/2). Validation = schema only; action-level gating
  (deferred actions) is the resolver's job at runtime, not write time.

Usage:
  python3 tomo/scripts/tag-handler-writer.py \\
    --input <path-to-handler.json> \\
    [--out-dir config/tag-handlers]

  Input file: a JSON object matching tomo/schemas/tag-handler.schema.json.
  The output filename is derived from the handler `id` field.

Exit codes:
  0 — success (file written)
  1 — validation failure (schema invalid or malformed JSON); NO file written
  2 — I/O or argument error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent  # tomo/scripts/ → tomo/ → repo root
_SCHEMA_PATH = _REPO_ROOT / "tomo" / "schemas" / "tag-handler.schema.json"

try:
    from jsonschema import ValidationError, validate as _jsonschema_validate
except ImportError:  # pragma: no cover
    _jsonschema_validate = None  # type: ignore[assignment]
    ValidationError = Exception  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _die(msg: str, code: int = 1) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _load_schema() -> dict:
    """Load and return the tag-handler JSON schema."""
    try:
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _die(f"schema not found: {_SCHEMA_PATH}", code=2)
    except json.JSONDecodeError as exc:
        _die(f"schema is not valid JSON: {exc}", code=2)


def _safe_stem(handler_id: str) -> str:
    """Return a filesystem-safe stem derived from the handler id.

    The id field is a non-empty string per schema. We replace path-unsafe
    characters with underscores for extra safety, keeping alphanumerics,
    hyphens, and dots.
    """
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in handler_id)


def _validate(handler: dict, schema: dict) -> None:
    """Validate *handler* against *schema*; call sys.exit(1) on failure."""
    if _jsonschema_validate is None:
        _die("jsonschema is not available — cannot validate handler", code=2)
    try:
        _jsonschema_validate(instance=handler, schema=schema)
    except ValidationError as exc:
        _die(f"handler fails schema validation: {exc.message}")


def _atomic_write(target: Path, content: str) -> None:
    """Write *content* to *target* atomically via a temp file + os.replace."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, target)
    except Exception:
        # Clean up temp file on any error; do not surface partial file
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Core write function (importable for tests if needed)
# ---------------------------------------------------------------------------


def write_handler(handler: dict, out_dir: Path) -> Path:
    """Validate *handler* and write it atomically to *out_dir*/<id>.json.

    Returns the path of the written file on success.
    Calls sys.exit(1) on validation failure (no file written).
    Calls sys.exit(2) on I/O errors.
    """
    schema = _load_schema()
    _validate(handler, schema)

    handler_id: str = handler.get("id", "")
    if not handler_id:
        _die("handler has no 'id' field (required by schema)")

    stem = _safe_stem(handler_id)
    target = out_dir / f"{stem}.json"

    content = json.dumps(handler, indent=2, ensure_ascii=False) + "\n"
    try:
        _atomic_write(target, content)
    except OSError as exc:
        _die(f"I/O error writing {target}: {exc}", code=2)

    print(f"tag-handler-writer: wrote {target}", file=sys.stderr)
    return target


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Atomic schema-validated writer for tag-handler configs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to a JSON file containing the handler dict (or '-' for stdin).",
    )
    p.add_argument(
        "--out-dir",
        default="config/tag-handlers",
        metavar="DIR",
        help="Directory to write the handler JSON into (default: config/tag-handlers).",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    input_path = args.input
    if input_path == "-":
        raw = sys.stdin.read()
    else:
        try:
            raw = Path(input_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            _die(f"input file not found: {input_path}", code=2)
        except OSError as exc:
            _die(f"cannot read input file: {exc}", code=2)

    try:
        handler = json.loads(raw)
    except json.JSONDecodeError as exc:
        _die(f"input is not valid JSON: {exc}")

    out_dir = Path(args.out_dir)
    write_handler(handler, out_dir)


if __name__ == "__main__":
    main()
