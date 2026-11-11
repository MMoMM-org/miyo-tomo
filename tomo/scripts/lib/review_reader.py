# review_reader.py — the paced, cached Kado reads of a period read: notes, link stems, listings, the end pass.
# version: 0.1.0
"""Kado access of ``lib/review_period.py`` (spec 045, T3.3; PRD F3-AC10..12).

``PacedReader`` is one cache in front of ``ReviewPacer.read``: every note,
listing and name lookup of a period read goes through it once, so a task
note read on seven days costs one call and the day re-run after the end pass
costs none. ``note(path)`` reads a note; ``target(stem)`` resolves a link
stem to its vault path with one ``byName`` (exact ``.md`` stem) and reads
it; ``folder(path)`` lists the ``.md`` files of a folder and its direct
subfolders; ``notes(path, **kw)`` is a ``listNotes`` query. A read the pacer
recorded as failed is *pending* (``hit_pending`` tells the caller its unit
of work is incomplete) until ``finish()`` runs the pacer's end pass and
merges what it recovered; what still failed is ``not_read``. ``Path not
found`` is *missing* and cached as None. Connection, auth and budget errors
propagate.

Design notes: docs/tomo/scripts/lib/review_reader.md
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set

from lib.kado_client import KadoNotFoundError
from lib.vault_paths import path_key


class PacedReader:
    """One cache of everything read; a failed read is pending until the end pass."""

    def __init__(self, client, pacer):
        self.client, self.pacer = client, pacer
        self.cache: Dict[str, Any] = {}
        self.pending: Set[str] = set()
        self.missing: Set[str] = set()
        self.not_read: List[str] = []
        self.hit_pending = False

    def _get(self, key: str, fn: Callable[[str], Any]) -> Any:
        if key in self.cache:
            return self.cache[key]
        if key in self.pending:
            self.hit_pending = True
            return None
        try:
            value = self.pacer.read(key, fn)
        except KadoNotFoundError:
            self.missing.add(key)
            value = None
        if value is None and key not in self.missing:
            self.pending.add(key)
            self.hit_pending = True
            return None
        self.cache[key] = value
        return value

    def answered(self, key: str) -> bool:
        """True when Kado answered ``key`` (also with nothing) — not pending, not failed."""
        return key not in self.pending and key not in self.not_read

    def _note_text(self, path: str) -> Optional[str]:
        content = self.client.read_note(path).get("content")
        return content if isinstance(content, str) else None

    def note(self, path: str) -> Optional[str]:
        return self._get(path, self._note_text)

    def _lookup(self, stem: str) -> str:
        """The vault path whose stem is ``stem`` (``.md`` only), else ``""``."""
        want = path_key(stem)
        for hit in self.client.search_by_name(stem) or []:
            path = str(hit.get("path") or "")
            name = path.rsplit("/", 1)[-1]
            if name.lower().endswith(".md") and path_key(name[:-3]) == want:
                return path
        return ""

    def path_of(self, stem: str) -> Optional[str]:
        return self.cache.get(stem) or None

    def target(self, stem: str) -> Optional[str]:
        """The text of the note a link stem names, resolved once; None when it does not resolve."""
        path = self._get(stem, self._lookup)
        return self.note(path) if path else None

    def _md_paths(self, folder: str) -> List[str]:
        items = self.client.list_dir(folder, depth=2)
        return [str(i.get("path")) for i in items
                if i.get("type") == "file" and str(i.get("path", "")).endswith(".md")]

    def folder(self, folder: str) -> Optional[List[str]]:
        """``.md`` paths of ``folder`` and its direct subfolders; None when Kado answered with nothing."""
        return self._get(folder, self._md_paths) or None

    def notes(self, folder: str, **kw) -> Optional[List[dict]]:
        return self._get(folder, lambda p: self.client.list_notes(p, **kw)) or None

    def finish(self) -> None:
        self.not_read = self.pacer.finish()
        for key in self.pending:
            self.cache[key] = self.pacer.recovered.get(key)
        self.pending = set()
