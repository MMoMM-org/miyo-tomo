#!/usr/bin/env python3
# version: 0.2.0
"""voice-transcribe.py — Batch CLI for audio → markdown transcription.

Loads the Whisper model once, iterates all inputs, emits a single JSON
manifest on stdout describing per-file results. When the process exits,
the OS releases the model's RAM — no separate unload step needed.

Usage:
  voice-transcribe.py <audio_path>... [--model-dir PATH] [--language LANG]

Stdout (always valid JSON, exit 0 unless fatal):
  {
    "model_dir": "/tomo/voice/models/faster-whisper-medium",
    "results": [
      {"audio": "memo-1.m4a", "target": "memo-1.md",
       "markdown": "...", "error": null},
      {"audio": "memo-2.m4a", "target": "memo-2.md",
       "markdown": null,
       "error": {"code": "transcription_error", "detail": "..."}}
    ]
  }

**Consumer contract — success vs error discrimination**:
For every `results[i]` entry, exactly one of `markdown` or `error` is
non-null. The reliable test is `"error is not None"` (Python) or
`.error != null` (jq). Truthy/falsy tests may trip consumers whose
language coerces `null`/None differently — e.g., shell `jq .error`
returns the literal string `null` for JSON null, which is truthy if
tested as a string. Future consumers SHOULD rely on explicit
`is None`/`!= null` checks, never truthy coercion.

Exit codes:
  0 — batch completed (individual file errors appear inside results[].error)
  2 — CLI usage error (argparse)
  3 — model-dir missing or unreadable (fatal; nothing attempted)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Re-exported at module scope so tests can monkey-patch them.
from lib.voice_transcriber import load_model, transcribe  # noqa: E402
from lib.voice_render import render_markdown  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="voice-transcribe",
        description="Batch-transcribe audio files to markdown via faster-whisper.",
    )
    p.add_argument("audio_paths", type=Path, nargs="+",
                   help="one or more audio files to transcribe")
    # --model-dir is REQUIRED. A hardcoded default silently targeted the
    # wrong directory when the wizard selected a non-medium model
    # (reviewed 2026-04-22, H3). The caller knows which model is active
    # via voice/config.json .model — pass it explicitly.
    p.add_argument("--model-dir", type=Path, required=True,
                   help="path to a faster-whisper CT2 model directory "
                        "(typically /tomo/voice/models/faster-whisper-<size>)")
    p.add_argument("--language", default=None,
                   help="language hint (e.g. de, en) or omit for auto-detect")
    return p


def _emit_stderr_error(code: str, detail: str) -> None:
    """Print a single-line JSON blob on stderr. Used for fatal pre-batch
    errors; per-file errors go inside the stdout manifest instead."""
    print(json.dumps({"error": code, "detail": detail}), file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()

    if not args.model_dir.exists():
        _emit_stderr_error("model_dir_missing", str(args.model_dir))
        return 3

    model = load_model(args.model_dir)  # ONE load for the whole batch

    results: list[dict] = []
    for audio in args.audio_paths:
        entry = {
            "audio": audio.name,
            "target": f"{audio.stem}.md",
            "markdown": None,
            "error": None,
        }
        if not audio.exists():
            entry["error"] = {"code": "audio_not_found", "detail": str(audio)}
        else:
            try:
                result = transcribe(model, audio, language=args.language)
                entry["markdown"] = render_markdown(result)
            except Exception as e:
                entry["error"] = {
                    "code": "transcription_error",
                    "detail": f"{type(e).__name__}: {e}",
                }
        results.append(entry)

    json.dump(
        {"model_dir": str(args.model_dir), "results": results},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
