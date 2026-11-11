# review_vault.py — the Kado calls of /review's session script and the evidence a weekly note carries.
# version: 0.1.0
"""Kado access for ``review-session.py`` and the date evidence of weekly notes (spec 045).

Owns ``Vault``, the wrapper that maps every Kado failure onto the SDD's error
kinds (``Stopped("kado-unreachable" | "kado-auth")`` stops the run; a failed
single read degrades to None / ``unreadable``), and the helpers that read a
weekly note's evidence: ``frontmatter_start`` (``journal-start-date``, else
``journal-end-date`` − 6), ``headings`` (level and text outside code fences)
and ``heading_start`` (the week's first day from the day-heading links, only
when they cover a full week). No note text leaves this module except through
the return values the caller asked for.

Design notes: docs/tomo/scripts/lib/review_vault.md
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import List, Optional, Set, Tuple

from lib.kado_client import KadoAuthError, KadoConnectionError, KadoError, KadoNotFoundError
from lib.vault_folder_lookup import VaultFolderLookup

START_KEYS = ("journal-start-date",)
END_KEYS = ("journal-end-date",)
TEMPLATER_MARK = "<%"
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_DAY_LINK_RE = re.compile(r"\[\[(\d{4}-\d{2}-\d{2})")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


class Stopped(Exception):
    """Kado cannot be used for this run; ``kind`` names the error kind."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


# ---------------------------------------------------------------- Kado access

class Vault:
    """The Kado calls the session script makes, each mapped onto the SDD's error kinds."""

    def __init__(self, client_factory):
        try:
            self.client = client_factory()
        except KadoError as exc:
            raise Stopped("kado-unreachable", str(exc)) from None

    def _guard(self, exc: KadoError) -> None:
        if isinstance(exc, KadoAuthError):
            raise Stopped("kado-auth", str(exc)) from None
        if isinstance(exc, KadoConnectionError):
            raise Stopped("kado-unreachable", str(exc)) from None

    def list_notes(self, folder: str) -> Optional[List[str]]:
        """Paths of the ``.md`` files in ``folder`` and its direct subfolders;
        None when Kado answered with nothing (an empty listing or ``Path not found``)."""
        try:
            items = self.client.list_dir(folder, depth=2)
        except KadoNotFoundError:
            return None
        except KadoError as exc:
            self._guard(exc)
            raise Stopped("kado-unreachable", str(exc)) from None
        if not items:
            return None
        return [str(i.get("path")) for i in items
                if i.get("type") == "file" and str(i.get("path", "")).endswith(".md")]

    def frontmatter(self, path: str) -> Optional[dict]:
        try:
            content = self.client.read_frontmatter(path).get("content")
        except KadoError as exc:
            self._guard(exc)
            return None
        return content if isinstance(content, dict) else None

    def note(self, path: str) -> Optional[str]:
        try:
            content = self.client.read_note(path).get("content")
        except KadoError as exc:
            self._guard(exc)
            return None
        return content if isinstance(content, str) else None

    def template(self, path: str) -> Tuple[str, Optional[str]]:
        """``(kind, text)``: plain | templater | missing | unreadable."""
        try:
            content = self.client.read_note(path).get("content")
        except KadoNotFoundError:
            return "missing", None
        except KadoError as exc:
            self._guard(exc)
            return "unreadable", None
        text = content if isinstance(content, str) else ""
        return ("templater" if TEMPLATER_MARK in text else "plain"), text

    def folder_listed(self, folder: str) -> bool:
        lookup = VaultFolderLookup(self.client)
        state = lookup.state(folder)
        if state == "unanswered":
            # the lookup swallowed the error; a dead connection must still stop the run
            try:
                self.client.list_dir(folder, depth=1)
            except KadoError as exc:
                self._guard(exc)
        return state == "listed"


# ---------------------------------------------------------------- dates and headings

def _as_date(value) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def frontmatter_start(frontmatter: dict) -> Optional[date]:
    for key in START_KEYS:
        start = _as_date(frontmatter.get(key))
        if start is not None:
            return start
    for key in END_KEYS:
        end = _as_date(frontmatter.get(key))
        if end is not None:
            return end - timedelta(days=6)
    return None


def headings(text: str) -> List[Tuple[int, str]]:
    """``(level, text)`` of every heading outside code fences."""
    found: List[Tuple[int, str]] = []
    fence: Optional[str] = None
    for line in text.splitlines():
        opener = _FENCE_RE.match(line)
        if opener:
            mark = opener.group(1)[0]
            if fence is None:
                fence = mark
            elif mark == fence:
                fence = None
            continue
        if fence is not None:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((len(match.group(1)), match.group(2).strip()))
    return found


def heading_start(text: str) -> Optional[date]:
    """The week's first day from day-heading links, only when they cover a full week."""
    dates: Set[date] = set()
    for _, heading in headings(text):
        for raw in _DAY_LINK_RE.findall(heading):
            d = _as_date(raw)
            if d is not None:
                dates.add(d)
    if len(dates) != 7 or (max(dates) - min(dates)).days != 6:
        return None
    return min(dates)
