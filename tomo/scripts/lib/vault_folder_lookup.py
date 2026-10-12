# version: 0.2.0
"""vault_folder_lookup.py — one `list_dir` per vault folder, served to every
reader in a run.

Exists so Pass 1 and Pass 2 ask the vault about a folder exactly once and
read every view — notes, attachments, folder-occupied names, the folder's
state — from the same raw listing. Caching a caller-derived map instead would
hand the second caller a map built for the first. A failed listing reads as
empty (an error is not a collision); `state()` says whether the folder was
listed, is absent, or went unanswered. Rationale:
docs/tomo/scripts/lib/vault_folder_lookup.md.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from lib.kado_client import KadoNotFoundError, observed_call_count
from lib.vault_paths import _asset_dest_join, _dest_join, path_key

FolderState = Literal["listed", "absent", "unanswered"]

# Kado's tool-level NOT_FOUND message on listDir. Matched in the message:
# kado_client raises KadoNotFoundError for an endpoint HTTP 404 too.
_PATH_NOT_FOUND = "path not found"


def _folder_key(location: str) -> str:
    return (location or "").rstrip("/") + "/"


def _classify(exc: Exception) -> FolderState:
    if isinstance(exc, KadoNotFoundError) and _PATH_NOT_FOUND in str(exc).casefold():
        return "absent"
    return "unanswered"


class VaultFolderLookup:
    """Raw `list_dir(folder, depth=1)` cache with derived per-call views.

    `folder_listing_calls` counts Kado round trips spent listing, failed
    listings included.
    """

    def __init__(self, kado_client) -> None:
        self._kado_client = kado_client
        self.folders: dict[str, list[dict]] = {}
        self._states: dict[str, FolderState] = {}
        self.folder_listing_calls = 0

    def _entries(self, folder: str) -> list[dict]:
        if folder in self.folders:
            return self.folders[folder]
        calls_before = observed_call_count(self._kado_client)
        try:
            entries = list(self._kado_client.list_dir(folder, depth=1))
            state: FolderState = "listed"
        except Exception as exc:  # noqa: BLE001 — an error is not a collision
            entries = []
            state = _classify(exc)
        calls_after = observed_call_count(self._kado_client)
        self.folder_listing_calls += (
            calls_after - calls_before
            if calls_before is not None and calls_after is not None
            else 1
        )
        self.folders[folder] = entries
        self._states[folder] = state
        return entries

    def state(self, location: str) -> FolderState:
        """`listed`, `absent` (Kado: `Path not found`), or `unanswered`."""
        folder = _folder_key(location)
        self._entries(folder)
        return self._states[folder]

    def _map(
        self,
        location: str,
        *,
        file_predicate: Callable[[str], bool],
        join: Callable[[str, str], str],
    ) -> dict[str, str]:
        folder = _folder_key(location)
        found: dict[str, str] = {}
        for entry in self._entries(folder):
            path = entry.get("path") or ""
            name = path.rsplit("/", 1)[-1]
            if entry.get("type") != "file" or not file_predicate(name):
                continue
            found[path_key(join(folder, name))] = path
        return found

    def notes(self, location: str) -> dict[str, str]:
        """The `.md` notes in `location`: `path_key(_dest_join(...))` → vault path."""
        return self._map(
            location,
            file_predicate=lambda name: name.lower().endswith(".md"),
            join=lambda folder, name: _dest_join(folder, name[:-3]),
        )

    def assets(self, location: str) -> dict[str, str]:
        """The non-`.md` files in `location`: `path_key(_asset_dest_join(...))`
        → vault path. A note sharing the folder is not an attachment collision.
        """
        return self._map(
            location,
            file_predicate=lambda name: not name.lower().endswith(".md"),
            join=_asset_dest_join,
        )

    def occupied_by_folder(self, location: str) -> set[str]:
        """`path_key(_asset_dest_join(...))` keys held by a FOLDER entry in `location`
        — the entries `notes()` and `assets()` drop.
        """
        folder = _folder_key(location)
        found: set[str] = set()
        for entry in self._entries(folder):
            if entry.get("type") == "file":
                continue
            path = entry.get("path") or ""
            name = path.rsplit("/", 1)[-1]
            if not name:
                continue
            found.add(path_key(_asset_dest_join(folder, name)))
        return found
