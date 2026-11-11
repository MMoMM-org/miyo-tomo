#!/usr/bin/env python3
# version: 0.2.0
"""review_fake_vault.py — one in-memory vault behind the /review scripts
(spec 045, from T2.2 on; the shared fake of Phase 3 from T3.1 on).

Lives in tests/, not tomo/scripts/lib/: it is never a production code path.
Not named `test_*`, so pytest does not collect it.

`ReviewFakeVault` extends tests/note_fake_vault.NoteFakeVault (reads, writes,
frontmatter merges, `events`, `fail`) with what the review scripts call:

- `list_dir(path, depth=...)` honours any depth, returns folder entries for
  the subfolders it passes through, and raises KadoNotFoundError
  ("Path not found") for a folder that holds nothing and was not declared in
  `folders` — a declared empty folder returns `[]`, the way a denied folder
  does on a live Kado.
- `list_notes(path, ...)` returns the `.md` files under the path as
  `{path, created, modified}` items (plus `links` as `{kind, target}`,
  `tags` with their `#`, `headings` when `fields` asks for them), applies
  the Kado filter keys `createdAfter/Before`, `modifiedAfter/Before`
  (Unix ms, inclusive) and `path` (prefix) against the per-note stamps
  (`stamp(path, created=, modified=)`), pages by `page_size` (one call per
  page, the filter repeated on every page, like KadoClient._search_all) and
  records the filter it was given per page in `list_notes_filters`.
- `search_by_name(query)` matches the filename: a glob when the query has
  glob characters, a substring otherwise (Kado byName).
- `search_by_frontmatter` returns `frontmatter: {}` per hit, like Kado.
- `connection_error` / `auth_error` switch every call to raise that
  exception (set them to an instance; None switches them off); `fail`
  raises per `(method, path)`; none of these is retried, as in the client.
- `rate_limit(path, failures=N | None, status=429 | 503)` turns the next N
  sends on that path away (None: every send); `burst(N, status)` turns the
  next N sends on any path away.

Retry accounting mirrors `lib.kado_client.KadoClient._call_tool` on a
virtual clock (`clock`, seconds; a send itself takes no time):
`attempt_count` per send, `call_count` per logical call, up to `_MAX_RETRIES`
retries after a 429/503 with `retry_wait_s` summing the sleeps (429: a
deterministic Retry-After of `RETRY_AFTER_S`; 503: the client's backoff base
and cap, no jitter), `pace_wait_s` summing the `min_interval` gaps, the
`attempt_gate` consulted before every send, and `KadoRateLimitError(status)`
once the retries are spent. `sends` lists every send as
`{method, path, outcome: "ok" | status | "error", interval}`.

`paths_seen` is every path any call asked for, so a test can assert that a
path (for example anything under `.obsidian`) was never requested.
"""
from __future__ import annotations

import re
import sys
from fnmatch import fnmatchcase
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from note_fake_vault import NoteFakeVault, split_frontmatter  # noqa: E402,F401
from lib.kado_client import (  # noqa: E402
    _MAX_RETRIES,
    _RETRY_BACKOFF_BASE,
    _RETRY_BACKOFF_CAP,
    KadoBudgetExhausted,
    KadoNotFoundError,
    KadoRateLimitError,
)

_GLOB_CHARS = ("*", "?", "[")
RETRY_AFTER_S = 1.0  # what the fake's 429 asks for; Kado's default window makes it ≤ 5 s
_LINK_RE = re.compile(r"(!?)\[\[([^\]]+)\]\]")
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*$")


def _folder_key(path: str) -> str:
    stripped = (path or "/").strip("/")
    return stripped + "/" if stripped else ""


class _TurnedAway:
    """Sends to turn away: `remaining` None means every send."""

    def __init__(self, status: int, remaining: int | None):
        self.status = status
        self.remaining = remaining

    def take(self) -> int | None:
        if self.remaining is None:
            return self.status
        if self.remaining <= 0:
            return None
        self.remaining -= 1
        return self.status


class ReviewFakeVault(NoteFakeVault):
    def __init__(self, files: dict | None = None, folders=()):
        super().__init__(files)
        self.folders: set[str] = {_folder_key(f) for f in folders}
        self.created: dict = {p: 0 for p in self.files}
        self.connection_error: Exception | None = None
        self.auth_error: Exception | None = None
        self.list_notes_filters: list = []
        self.page_size: int | None = None
        # KadoClient's pacing and accounting surface
        self.attempt_count = 0
        self.attempt_gate = None
        self.min_interval = 0.0
        self.retry_wait_s = 0.0
        self.pace_wait_s = 0.0
        self.clock = 0.0
        self._last_send: float | None = None
        self.sends: list[dict] = []
        self._rate_limits: dict[str, _TurnedAway] = {}
        self._burst: _TurnedAway | None = None

    # ── injection ──
    def stamp(self, path: str, *, created: int | None = None, modified: int | None = None) -> None:
        if created is not None:
            self.created[path] = created
        if modified is not None:
            self.modified[path] = modified

    def rate_limit(self, path: str, *, failures: int | None = None, status: int = 429) -> None:
        self._rate_limits[path] = _TurnedAway(status, failures)

    def burst(self, failures: int, *, status: int = 429) -> None:
        self._burst = _TurnedAway(status, failures)

    def _turned_away(self, path: str) -> int | None:
        if self._burst is not None:
            status = self._burst.take()
            if status is not None:
                return status
        spec = self._rate_limits.get(path)
        return spec.take() if spec is not None else None

    # ── the client's send loop on a virtual clock ──
    def _pace(self) -> None:
        if self.min_interval > 0 and self._last_send is not None:
            wait = self._last_send + self.min_interval - self.clock
            if wait > 0:
                self.pace_wait_s += wait
                self.clock += wait
        self._last_send = self.clock

    def _retry_delay(self, status: int, attempt: int) -> float:
        if status == 429:
            return RETRY_AFTER_S
        return min(_RETRY_BACKOFF_CAP, _RETRY_BACKOFF_BASE * (2 ** attempt))

    def _call(self, method: str, path: str) -> None:
        self.call_count += 1
        self.events.append((method, path))
        exc = self.connection_error or self.auth_error or self.fail.get((method, path))
        for attempt in range(_MAX_RETRIES + 1):
            if self.attempt_gate is not None and not self.attempt_gate():
                raise KadoBudgetExhausted(f"Kado attempt budget exhausted before {method}")
            self.attempt_count += 1
            self._pace()
            send = {"method": method, "path": path, "outcome": "ok", "interval": self.min_interval}
            self.sends.append(send)
            if exc is not None:
                send["outcome"] = "error"
                raise exc
            status = self._turned_away(path)
            if status is None:
                return
            send["outcome"] = status
            if attempt < _MAX_RETRIES:
                delay = self._retry_delay(status, attempt)
                self.retry_wait_s += delay
                self.clock += delay
                continue
            raise KadoRateLimitError(
                f"HTTP {status} from Kado: turned away (after {_MAX_RETRIES} retries)", status=status
            )

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

    def _passes(self, path: str, filter) -> bool:
        if not filter:
            return True
        created = self.created.get(path) or 0
        modified = self.modified.get(path) or 0
        if "path" in filter and not path.startswith(filter["path"]):
            return False
        if "createdAfter" in filter and created < filter["createdAfter"]:
            return False
        if "createdBefore" in filter and created > filter["createdBefore"]:
            return False
        if "modifiedAfter" in filter and modified < filter["modifiedAfter"]:
            return False
        if "modifiedBefore" in filter and modified > filter["modifiedBefore"]:
            return False
        return True

    def _note_item(self, path: str, fields) -> dict:
        item = {"path": path, "created": self.created.get(path) or 0,
                "modified": self.modified.get(path) or 0}
        if not fields:
            return item
        text = self.text(path)
        frontmatter, body = split_frontmatter(text)
        if "links" in fields:
            item["links"] = [{"kind": "embed" if bang else "link", "target": target}
                             for bang, target in _LINK_RE.findall(body)]
        if "tags" in fields:
            tags = frontmatter.get("tags") or []
            tags = [tags] if isinstance(tags, str) else list(tags)
            item["tags"] = [t if str(t).startswith("#") else f"#{t}" for t in tags]
        if "headings" in fields:
            item["headings"] = [m.group(1) for m in map(_HEADING_RE.match, body.splitlines()) if m]
        return item

    def list_notes(self, path, *, fields=None, depth=None, limit=500, filter=None):
        folder = _folder_key(path)
        items = [self._note_item(e["path"], fields) for e in self._under(folder, depth)
                 if e["type"] == "file" and e["path"].endswith(".md") and self._passes(e["path"], filter)]
        page = min(limit, self.page_size) if self.page_size else limit
        out: list[dict] = []
        offset = 0
        while True:
            self._call("list_notes", path)
            self.list_notes_filters.append(filter)
            chunk = items[offset:offset + page]
            out.extend(chunk)
            offset += page
            if not chunk or offset >= len(items):
                return out

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
