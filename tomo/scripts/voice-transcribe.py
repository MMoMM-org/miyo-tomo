#!/usr/bin/env python3
# version: 0.6.0
"""voice-transcribe.py — Batch CLI for audio → markdown transcription.

Loads the Whisper model once, iterates all inputs, emits a single JSON
manifest on stdout describing per-file results. When the process exits,
the OS releases the model's RAM — no separate unload step needed.

Usage:
  voice-transcribe.py <audio_path>... [--model-dir PATH] [--language LANG]

Path resolution (hybrid, 2026-04-22 — v0.3.0):
  * If the argument resolves to an existing FS path → use it directly.
    This supports local test fixtures and any future host-side runs.
  * Otherwise, treat the argument as a vault-relative path and fetch
    the audio bytes via Kado (`kado-read` operation="file") into a
    temp file for transcription. Tomo's strict "no direct vault FS
    access" rule requires this path inside the container — the vault
    is NOT bind-mounted; only the Kado HTTP MCP is reachable.
  * Temp files are cleaned up after each file regardless of outcome.

Per-file errors surface inside the stdout manifest (`results[i].error`):
  * `audio_not_found` — neither the FS path nor the Kado-fetch succeeded
  * `transcription_error` — Whisper raised during transcription

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
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Re-exported at module scope so tests can monkey-patch them.
from lib.voice_transcriber import load_model, transcribe  # noqa: E402
from lib.voice_render import render_markdown  # noqa: E402
from lib.obsidian_filename import sanitize_stem  # noqa: E402


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


def _fetch_from_kado(vault_path: Path) -> Path:
    """Fetch a vault file via Kado `kado-read` operation="file" into a
    temp file. Returns the temp path. Caller owns cleanup.

    Raises KadoError (from kado_client) on any Kado-side failure — the
    per-file loop converts that into an `audio_not_found` entry so
    batch transcription never crashes on a single missing file.
    """
    from lib.kado_client import KadoClient  # noqa: E402 — lazy: tests may not need Kado
    client = KadoClient()
    data = client.read_file_bytes(str(vault_path))
    suffix = vault_path.suffix or ".bin"
    fd, tmp_path = tempfile.mkstemp(
        prefix="tomo-voice-", suffix=suffix, dir="/tmp"
    )
    import os
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return Path(tmp_path)


def _resolve_audio(audio: Path) -> tuple[Path, Path | None]:
    """Return (path_to_transcribe, tmp_to_cleanup).

    * FS exists → (audio, None) — direct.
    * FS missing → Kado fetch → (tmp, tmp).
    * Kado also fails → re-raise so the caller records audio_not_found.
    """
    if audio.exists():
        return audio, None
    tmp = _fetch_from_kado(audio)
    return tmp, tmp


def main() -> int:
    args = build_parser().parse_args()

    if not args.model_dir.exists():
        _emit_stderr_error("model_dir_missing", str(args.model_dir))
        return 3

    # Model-load wall time — paid once per CLI invocation. Tracked for
    # T5.2 performance measurement so the agent/user can see whether a
    # slow run came from the load or the transcription itself.
    _load_start = time.perf_counter()
    model = load_model(args.model_dir)  # ONE load for the whole batch
    model_load_sec = round(time.perf_counter() - _load_start, 2)

    results: list[dict] = []
    for audio in args.audio_paths:
        # Strip Obsidian-forbidden chars (\\ / : * ? " < > | null) from the
        # transcript target — audio files from external recorders often
        # carry colons in timestamp portions (e.g. "memo 11:48:29.m4a").
        # The source filename stays as-is (that's what lives in the vault);
        # only the sibling .md target we're about to kado-write is sanitised.
        target_stem = sanitize_stem(audio.stem)
        entry = {
            "audio": audio.name,
            "target": f"{target_stem}.md",
            "markdown": None,
            "error": None,
            "transcribe_sec": None,
        }
        transcribe_path: Path | None = None
        tmp_to_cleanup: Path | None = None
        try:
            transcribe_path, tmp_to_cleanup = _resolve_audio(audio)
        except Exception as exc:
            entry["error"] = {
                "code": "audio_not_found",
                "detail": f"{str(audio)} ({type(exc).__name__}: {exc})",
            }

        if transcribe_path is not None:
            try:
                _t_start = time.perf_counter()
                result = transcribe(model, transcribe_path, language=args.language)
                entry["transcribe_sec"] = round(time.perf_counter() - _t_start, 2)
                # Restore the ORIGINAL vault-relative path on the result so the
                # rendered `source:` metadata and `![[...]]` embed reference the
                # actual audio file users will see in Obsidian — not the
                # ephemeral `/tmp/tomo-voice-*.m4a` we fetched through Kado.
                result.audio_path = audio
                entry["markdown"] = render_markdown(
                    result, transcribe_sec=entry["transcribe_sec"]
                )
            except Exception as e:
                entry["error"] = {
                    "code": "transcription_error",
                    "detail": f"{type(e).__name__}: {e}",
                }

        if tmp_to_cleanup is not None:
            try:
                tmp_to_cleanup.unlink(missing_ok=True)
            except OSError:
                pass  # best-effort cleanup; don't mask the real result

        results.append(entry)

    # Batch-level summary on stderr — one compact line for eyeballing run
    # performance without parsing the JSON. Example:
    #   voice-transcribe: 2 files, model_load=3.1s, transcribe_total=263.4s
    transcribe_total = sum(
        (r.get("transcribe_sec") or 0) for r in results
    )
    print(
        f"voice-transcribe: {len(results)} files, "
        f"model_load={model_load_sec}s, "
        f"transcribe_total={round(transcribe_total, 2)}s",
        file=sys.stderr,
    )

    json.dump(
        {
            "model_dir": str(args.model_dir),
            "model_load_sec": model_load_sec,
            "results": results,
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
