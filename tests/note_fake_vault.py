#!/usr/bin/env python3
# version: 0.3.0
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

It fails the way lib.kado_client.KadoClient does: an absent path raises
KadoNotFoundError (frontmatter writes included); a note read or frontmatter
read of a non-.md path raises KadoToolError (Kado's VALIDATION_ERROR);
path_exists probes .md through read_frontmatter and every other path through
read_file; write_frontmatter honours mode merge|replace and raises
KadoConcurrencyError on a stale expected_modified. write_note and write_file
over an existing path hold to Kado's write guard (core/concurrency-guard): no
expected_modified, or one that is not the path's `modified`, raises
KadoToolError with Kado's CONFLICT payload and writes nothing; an absent path
is created without one. Paths ending in UNGUARDED_SUFFIXES skip the guard:
production still overwrites the readable /review instruction set without
expected_modified (F-R3b-1 follow-up), so those tests keep their old fake.
`modified[path] = None` makes the reads omit `modified`.
"""
from __future__ import annotations

import base64
import copy
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import (  # noqa: E402
    KadoConcurrencyError, KadoNotFoundError, KadoToolError,
)

FRONTMATTER_MODES = ("merge", "replace")
GUARD_MISSING = ('kado-write returned an error: {"code":"CONFLICT","message":"expectedModified is required '
                 'when updating an existing file. Read the file first to get the current modified timestamp."}')
GUARD_STALE = ('kado-write returned an error: {"code":"CONFLICT",'
               '"message":"File was updated in the background. Re-read before retrying."}')
# The readable /review instruction set (`<stem>_review_instructions.md`): review-instructions.py drop (the
# withdrawn MD) and lib/review_instructions_deliver._overwrite_step (the MD over an earlier run's) overwrite it
# without expected_modified today. Remove the entry once both callers send the stamp.
UNGUARDED_SUFFIXES = ("_review_instructions.md",)


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


def _require_md(path: str) -> None:
    """Kado's note and frontmatter reads refuse a non-.md path (VALIDATION_ERROR)."""
    if not path.lower().endswith(".md"):
        raise KadoToolError("kado-read returned an error: VALIDATION_ERROR")


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

    def _stat(self, path: str, content) -> dict:
        modified = self.modified.get(path, 1)
        return {"content": content} if modified is None else {"content": content, "modified": modified}

    def _bump(self, path: str) -> None:
        self.modified[path] = (self.modified.get(path) or 0) + 1

    def text(self, path: str) -> str:
        data = self.files[path]
        return data if isinstance(data, str) else data.decode("utf-8")

    # ── reads ──
    def read_note(self, path):
        self._call("read_note", path)
        _require_md(path)
        self._need(path)
        return self._stat(path, self.text(path))

    def read_file(self, path):
        self._call("read_file", path)
        data = self._need(path)
        raw = data if isinstance(data, bytes) else data.encode("utf-8")
        return self._stat(path, base64.b64encode(raw).decode("ascii"))

    def read_file_bytes(self, path):
        return base64.b64decode(self.read_file(path)["content"])

    def read_frontmatter(self, path):
        self._call("read_frontmatter", path)
        _require_md(path)
        self._need(path)
        return self._stat(path, split_frontmatter(self.text(path))[0])

    def path_exists(self, path):
        """Probe like KadoClient.path_exists: .md via read_frontmatter, else read_file."""
        self._call("path_exists", path)
        try:
            if path.lower().endswith(".md"):
                self.read_frontmatter(path)
            else:
                self.read_file(path)
            return True
        except KadoNotFoundError:
            return False

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
        self._bump(path)
        self.writes.append(path)

    def _guard(self, path, expected_modified) -> None:
        """Kado's write guard: an existing path is overwritten only with its current ``modified``."""
        if path not in self.files or path.endswith(UNGUARDED_SUFFIXES):
            return
        if expected_modified is None:
            raise KadoToolError(GUARD_MISSING)
        if expected_modified != self.modified.get(path, 1):
            raise KadoToolError(GUARD_STALE)

    def write_note(self, path, content, expected_modified=None):
        self._call("write_note", path)
        self._guard(path, expected_modified)
        self._store(path, content)
        return {"path": path}

    def write_file(self, path, data, expected_modified=None):
        self._call("write_file", path)
        assert isinstance(data, bytes), "KadoClient.write_file takes bytes"
        self._guard(path, expected_modified)
        self._store(path, data)
        return {"path": path}

    def write_frontmatter(self, path, frontmatter, mode="merge", expected_modified=None):
        self._call("write_frontmatter", path)
        if mode not in FRONTMATTER_MODES:
            raise KadoToolError("kado-write returned an error: VALIDATION_ERROR mode")
        self._need(path)
        if expected_modified is not None and expected_modified != self.modified.get(path, 1):
            raise KadoConcurrencyError("kado-write returned an error: expectedModified mismatch")
        self.merges.append({"path": path, "frontmatter": copy.deepcopy(frontmatter),
                            "mode": mode, "expected_modified": expected_modified})
        current, body = split_frontmatter(self.text(path))
        merged = _deep_merge(current, frontmatter) if mode == "merge" else copy.deepcopy(frontmatter)
        dumped = yaml.safe_dump(merged, sort_keys=False, allow_unicode=True)
        self.files[path] = f"---\n{dumped}---\n{body}"
        self._bump(path)
        return {"path": path, "modified": self.modified[path]}
