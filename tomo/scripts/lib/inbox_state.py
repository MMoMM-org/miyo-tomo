# inbox_state.py — Replay tomo-tmp/inbox-state.jsonl into a per-item view.
# version: 0.1.0
"""Last-write-wins replay of the append-only inbox run-state log (spec 034).

`inbox-state.jsonl` is written one line per state transition and never
truncated, so every reader has to replay it and keep the last entry per item.
Two readers used to do that independently — `suggestions-reducer.py` and
`mark-captured.py` — and both keyed on the bare filename, which merges two
inbox items that share a name in different subfolders: one item's status
masks its namesake's and that namesake drops out of the run (ADR-2).

This module is the single replay. It keys on `item_key` — the item's
vault-relative path, verbatim (ADR-1) — which stays unique across subfolders.

Public API:

    last_state_per_item_key(state_path: str | Path) -> dict[str, dict]
        {item_key: last entry for that key}. Fails open: an absent log is an
        empty replay, and an unparseable or key-less line is passed over
        rather than aborting the run.

Stdlib only — no new dependencies.
"""
from __future__ import annotations

import json
from pathlib import Path


def last_state_per_item_key(state_path: str | Path) -> dict[str, dict]:
    """Return {item_key: last_entry} by replaying the append-only JSONL."""
    out: dict[str, dict] = {}
    path = Path(state_path)
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            item_key = entry.get("item_key")
            if item_key:
                out[item_key] = entry
    return out


def display_stem(entry: dict, item_key: str) -> str:
    """The bare filename to render for an entry (ADR-2: stem is display-only).

    Falls back to the key's own basename rather than the key itself, so a
    malformed entry can never put a path into a note title or a wikilink.
    """
    stem = entry.get("stem")
    if isinstance(stem, str) and stem:
        return stem
    basename = item_key.rsplit("/", 1)[-1]
    return basename[:-3] if basename.endswith(".md") else basename
