#!/usr/bin/env python3
# version: 0.1.0
"""note_fake_vault.py — one in-memory vault behind note-instructions.py deliver
and triage's frontmatter buckets (spec 044 T2.6).

Lives in tests/, not tomo/scripts/lib/: it is never a production code path.
Not named `test_*`, so pytest does not collect it.

`NoteFakeVault` is a KadoClient stand-in. Notes are text, other files bytes.
It records every call in `events` (in order), every write in `writes`, every
frontmatter merge in `merges`, and raises the exception named for a
`(method, path)` pair in `fail` — a KadoError subclass for a Kado failure, or
`Killed` (a BaseException) to stand for the process dying mid-run.
`search_by_frontmatter` reads the stored frontmatter, so triage's buckets come
from what deliver actually wrote.
"""
from __future__ import annotations

import base64
import copy
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import KadoNotFoundError  # noqa: E402


class Killed(BaseException):
    """The process died between two steps; nothing catches it."""


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body); {} when there is no leading block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return yaml.safe_load("".join(lines[1:i])) or {}, "".join(lines[i + 1:])
    return {}, text


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _dig(data: dict, dotted: str):
    for part in dotted.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


class NoteFakeVault:
    def __init__(self, files: dict | None = None):
        self.files: dict = dict(files or {})
        self.modified: dict = {p: 1 for p in self.files}
        self.events: list[tuple[str, str]] = []
        self.writes: list[str] = []
        self.merges: list[dict] = []
        self.fail: dict = {}
        self.call_count = 0

    def __call__(self):
        """Stand in for the KadoClient class: every construction returns this vault."""
        return self

    def _call(self, method: str, path: str) -> None:
        self.call_count += 1
        self.events.append((method, path))
        exc = self.fail.get((method, path))
        if exc is not None:
            raise exc

    def _need(self, path: str):
        if path not in self.files:
            raise KadoNotFoundError("NOT_FOUND")
        return self.files[path]

    def text(self, path: str) -> str:
        data = self.files[path]
        return data if isinstance(data, str) else data.decode("utf-8")

    # ── reads ──
    def read_note(self, path):
        self._call("read_note", path)
        self._need(path)
        return {"content": self.text(path), "modified": self.modified.get(path, 1)}

    def read_file(self, path):
        self._call("read_file", path)
        data = self._need(path)
        raw = data if isinstance(data, bytes) else data.encode("utf-8")
        return {"content": base64.b64encode(raw).decode("ascii"), "modified": self.modified.get(path, 1)}

    def read_file_bytes(self, path):
        return base64.b64decode(self.read_file(path)["content"])

    def read_frontmatter(self, path):
        self._call("read_frontmatter", path)
        self._need(path)
        return {"content": split_frontmatter(self.text(path))[0], "modified": self.modified.get(path, 1)}

    def path_exists(self, path):
        self._call("path_exists", path)
        return path in self.files

    def list_dir(self, path="/", *, depth=None, limit=500):
        self._call("list_dir", path)
        folder = path.rstrip("/") + "/"
        found = [p for p in self.files if p.startswith(folder)]
        if depth == 1:
            found = [p for p in found if "/" not in p[len(folder):]]
        return [{"path": p, "type": "file"} for p in sorted(found)]

    def search_by_frontmatter(self, query, path_prefix=None, **_kw):
        key, _, value = query.partition("=")
        hits = []
        for p in sorted(self.files):
            if not p.endswith(".md") or (path_prefix and not p.startswith(path_prefix)):
                continue
            if _dig(split_frontmatter(self.text(p))[0], key) == value:
                hits.append({"path": p, "frontmatter": {}})
        return hits

    # ── writes ──
    def _store(self, path, data):
        self.files[path] = data
        self.modified[path] = self.modified.get(path, 0) + 1
        self.writes.append(path)

    def write_note(self, path, content, expected_modified=None):
        self._call("write_note", path)
        self._store(path, content)
        return {"path": path}

    def write_file(self, path, data, expected_modified=None):
        self._call("write_file", path)
        assert isinstance(data, bytes), "KadoClient.write_file takes bytes"
        self._store(path, data)
        return {"path": path}

    def write_frontmatter(self, path, frontmatter, mode="merge", expected_modified=None):
        self._call("write_frontmatter", path)
        self.merges.append({"path": path, "frontmatter": copy.deepcopy(frontmatter),
                            "mode": mode, "expected_modified": expected_modified})
        current, body = split_frontmatter(self.text(path))
        merged = _deep_merge(current, frontmatter)
        dumped = yaml.safe_dump(merged, sort_keys=False, allow_unicode=True)
        self.files[path] = f"---\n{dumped}---\n{body}"
        self.modified[path] = self.modified.get(path, 1) + 1
        return {"path": path, "modified": self.modified.get(path, 1)}
