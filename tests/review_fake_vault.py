#!/usr/bin/env python3
# version: 0.1.0
"""review_fake_vault.py — one in-memory vault behind the /review scripts
(spec 045, from T2.2 on).

Lives in tests/, not tomo/scripts/lib/: it is never a production code path.
Not named `test_*`, so pytest does not collect it.

`ReviewFakeVault` extends tests/note_fake_vault.NoteFakeVault (reads, writes,
frontmatter merges, `events`, `fail`) with what the review scripts call:

- `list_dir(path, depth=...)` honours any depth, returns folder entries for
  the subfolders it passes through, and raises KadoNotFoundError
  ("Path not found") for a folder that holds nothing and was not declared in
  `folders` — a declared empty folder returns `[]`, the way a denied folder
  does on a live Kado.
- `list_notes(path, ...)` returns the `.md` files under the path and records
  the filter it was given in `list_notes_filters`.
- `search_by_name(query)` matches the filename: a glob when the query has
  glob characters, a substring otherwise (Kado byName).
- `search_by_frontmatter` returns `frontmatter: {}` per hit, like Kado.
- `connection_error` / `auth_error` switch every call to raise that
  exception (set them to an instance; None switches them off).

`paths_seen` is every path any call asked for, so a test can assert that a
path (for example anything under `.obsidian`) was never requested.
"""
from __future__ import annotations

import sys
from fnmatch import fnmatchcase
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from note_fake_vault import NoteFakeVault, split_frontmatter  # noqa: E402,F401
from lib.kado_client import KadoNotFoundError  # noqa: E402

_GLOB_CHARS = ("*", "?", "[")


def _folder_key(path: str) -> str:
    stripped = (path or "/").strip("/")
    return stripped + "/" if stripped else ""


class ReviewFakeVault(NoteFakeVault):
    def __init__(self, files: dict | None = None, folders=()):
        super().__init__(files)
        self.folders: set[str] = {_folder_key(f) for f in folders}
        self.connection_error: Exception | None = None
        self.auth_error: Exception | None = None
        self.list_notes_filters: list = []

    def _call(self, method: str, path: str) -> None:
        self.call_count += 1
        self.events.append((method, path))
        if self.connection_error is not None:
            raise self.connection_error
        if self.auth_error is not None:
            raise self.auth_error
        exc = self.fail.get((method, path))
        if exc is not None:
            raise exc

    @property
    def paths_seen(self) -> set[str]:
        return {path for _, path in self.events}

    # ── listings ──
    def _under(self, folder: str, depth) -> list[dict]:
        entries: dict[str, dict] = {}
        for p in sorted(self.files):
            if not p.startswith(folder):
                continue
            parts = p[len(folder):].split("/")
            if depth is not None and len(parts) > depth:
                parts = parts[:depth]
                sub = folder + "/".join(parts)
                entries.setdefault(sub, {"path": sub, "type": "folder"})
                continue
            for i in range(1, len(parts)):
                sub = folder + "/".join(parts[:i])
                entries.setdefault(sub, {"path": sub, "type": "folder"})
            entries[p] = {"path": p, "type": "file"}
        return [entries[k] for k in sorted(entries)]

    def list_dir(self, path="/", *, depth=None, limit=500):
        self._call("list_dir", path)
        folder = _folder_key(path)
        known = folder in self.folders or any(p.startswith(folder) for p in self.files)
        if not known:
            raise KadoNotFoundError("kado-search returned an error: Path not found")
        return self._under(folder, depth)

    def list_notes(self, path, *, fields=None, depth=None, limit=500, filter=None):
        self._call("list_notes", path)
        self.list_notes_filters.append(filter)
        folder = _folder_key(path)
        return [{"path": e["path"]} for e in self._under(folder, depth)
                if e["type"] == "file" and e["path"].endswith(".md")]

    def search_by_name(self, query, limit=500):
        self._call("search_by_name", query)
        hits = []
        for p in sorted(self.files):
            name = p.rsplit("/", 1)[-1]
            stem = name[:-3] if name.endswith(".md") else name
            if any(c in query for c in _GLOB_CHARS):
                if fnmatchcase(name, query) or fnmatchcase(stem, query):
                    hits.append({"path": p})
            elif query in name:
                hits.append({"path": p})
        return hits

    def search_by_frontmatter(self, query, path_prefix=None, **kw):
        self._call("search_by_frontmatter", query)
        return super().search_by_frontmatter(query, path_prefix=path_prefix, **kw)
