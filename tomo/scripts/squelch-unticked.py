#!/usr/bin/env python3
# version: 0.1.0
"""squelch-unticked.py — Persist un-ticked MOC clusters to the F-43 squelch registry.

Reads a JSON object (with key "unticked_clusters") or a raw JSON list of unticked
cluster dicts from a file path argument or stdin, then calls the F-43 squelch API
(add_or_replace + save_registry_atomic). No new squelch logic — pure reuse.

Each cluster dict must carry:
    "topic_signature": str   — stable hash (computed by T5.1 suggestion-parser)
    "title":           str   — human-readable cluster title (stored as topic_keywords)

Usage:
    python3 scripts/squelch-unticked.py tomo-tmp/moc-parsed.json
    python3 scripts/squelch-unticked.py -                          # read from stdin
    python3 scripts/squelch-unticked.py                            # also reads stdin
"""

from __future__ import annotations

import json
import sys
import pathlib
from datetime import datetime, timezone

_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.squelch import SquelchEntry, add_or_replace, load_registry, save_registry_atomic  # noqa: E402

_DEFAULT_RUNS_REMAINING = 3
_REGISTRY_PATH_REL = pathlib.Path("state") / "moc-squelch.json"


def _load_clusters(argv: list[str]) -> list[dict]:
    """Read unticked cluster list from a file arg or stdin."""
    if len(argv) > 1 and argv[1] != "-":
        raw = pathlib.Path(argv[1]).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    parsed = json.loads(raw)

    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        clusters = parsed.get("unticked_clusters")
        if isinstance(clusters, list):
            return clusters
        raise ValueError(
            "Input JSON object must have an 'unticked_clusters' key with a list value"
        )
    raise ValueError(f"Input must be a JSON list or object, got {type(parsed).__name__}")


def _registry_path() -> pathlib.Path:
    """Resolve registry path relative to cwd (matches runtime working directory)."""
    return _REGISTRY_PATH_REL


def main(argv: list[str]) -> int:
    clusters = _load_clusters(argv)

    if not clusters:
        print("[squelch-unticked] no unticked clusters — nothing to persist", file=sys.stderr)
        return 0

    registry_path = _registry_path()
    registry = load_registry(registry_path) if registry_path.exists() else {}
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for cluster in clusters:
        signature = cluster.get("topic_signature", "")
        if not signature:
            print(
                f"[squelch-unticked] WARN: cluster missing topic_signature, skipping: {cluster!r}",
                file=sys.stderr,
            )
            continue

        title = cluster.get("title", "")
        topic_keywords = [kw for kw in [title] if kw]

        entry = SquelchEntry(
            topic_signature=signature,
            topic_keywords=topic_keywords,
            rejected_at_run_id="",
            runs_remaining=_DEFAULT_RUNS_REMAINING,
            first_seen_at=now_iso,
        )
        registry = add_or_replace(registry, entry)

    save_registry_atomic(registry_path, registry)
    print(
        f"[squelch-unticked] persisted {len(clusters)} entr{'y' if len(clusters) == 1 else 'ies'}"
        f" to {registry_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
