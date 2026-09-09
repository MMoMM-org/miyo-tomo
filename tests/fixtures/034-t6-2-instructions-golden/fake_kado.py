#!/usr/bin/env python3
# version: 1.0.0
"""The fake vault both sides of the T6.2 instruction-set golden read.

`record.py` runs the Pass-2 chain at `ee44cb3` against this client; the test at
HEAD runs today's chain against the same one. A shared implementation is the
point: a recording made against a different fake than the replay would compare
two pipelines AND two vaults, and nothing would say which one moved.

`KadoError` is passed in rather than imported, so the same class serves the
worktree's `lib.kado_client` during recording and HEAD's during replay.
"""
from __future__ import annotations

import json
from pathlib import Path

VAULT_JSON = Path(__file__).resolve().parent / "vault.json"


def load_notes() -> dict[str, str]:
    return json.loads(VAULT_JSON.read_text(encoding="utf-8"))["notes"]


class FakeKado:
    """Read-only vault backed by `vault.json`.

    Only the four methods the Pass-2 chain calls are implemented — a broader
    fake would invite a future consumer to reach for something this fixture
    never recorded an answer for.
    """

    def __init__(self, notes: dict[str, str], kado_error: type[Exception]):
        self._notes = dict(notes)
        self._error = kado_error

    def read_note(self, path: str) -> dict:
        if path not in self._notes:
            raise self._error(f"not found: {path}")
        return {"content": self._notes[path], "modified": 0}

    def search_by_name(self, name: str) -> list[dict]:
        stem = name[:-3] if name.endswith(".md") else name
        return [
            {"path": p} for p in self._notes
            if p.rsplit("/", 1)[-1].removesuffix(".md") == stem
        ]

    def note_exists(self, path: str) -> bool:
        return path in self._notes

    def resolve_stem_to_path(self, stem: str) -> str | None:
        hits = self.search_by_name(stem)
        return hits[0]["path"] if hits else None

    def list_dir(self, *_args, **_kwargs) -> list[dict]:
        return []
