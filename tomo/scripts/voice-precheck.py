#!/usr/bin/env python3
# version: 0.2.0
"""voice-precheck.py — Cheap sibling-existence check before dispatching voice-transcriber.

The voice-transcriber subagent costs ~17k tokens to load even when it
has no work to do. When every audio file already has its sibling .md
transcript next to it, the dispatch is pure waste.

This script answers the question "would voice-transcriber do any work?"
without dispatching it. One Kado listDir call, no file reads, no model
boot. The orchestrator skips the dispatch entirely when all_cached.

Logic:
  1. listDir the inbox (top-level, files only).
  2. Collect audio files by extension match.
  3. For each audio, compute the Obsidian-safe sibling .md path via
     sanitize_stem (single source of truth shared with voice-transcribe.py).
  4. Check sibling presence in the same listDir result — no extra calls.
  5. Emit a JSON summary on stdout for the orchestrator to consume.

Usage:
  voice-precheck.py <inbox_path>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts"))

from lib.audio_constants import AUDIO_EXTS  # noqa: E402
from lib.kado_client import KadoClient  # noqa: E402
from lib.obsidian_filename import sanitize_stem  # noqa: E402


def _audio_stem(path: str) -> str:
    return Path(path).stem


def _expected_md_path(audio_path: str) -> str:
    p = Path(audio_path)
    safe = sanitize_stem(p.stem)
    return str(p.parent / f"{safe}.md")


def precheck(inbox: str) -> dict:
    client = KadoClient()
    items = client.list_dir(inbox, depth=1)

    files = [i for i in items if i.get("type") == "file"]
    paths = {i["path"] for i in files}

    audio = [i["path"] for i in files if Path(i["path"]).suffix.lower() in AUDIO_EXTS]
    cached, missing = [], []
    for a in audio:
        if _expected_md_path(a) in paths:
            cached.append(a)
        else:
            missing.append(a)

    return {
        "all_cached": len(audio) > 0 and not missing,
        "audio_count": len(audio),
        "cached_count": len(cached),
        "missing_count": len(missing),
        "missing": missing,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: voice-precheck.py <inbox_path>", file=sys.stderr)
        return 2
    result = precheck(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
