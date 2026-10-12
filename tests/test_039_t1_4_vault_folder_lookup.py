#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t1_4_vault_folder_lookup.py — spec 039 T1.4.

Pins the shared folder lookup `lib/vault_folder_lookup.py` (SDD K2, ADR-2):
one raw `list_dir` per folder, served to every reader — the Pass-1 reducer's
`notes()` / `assets()` / `occupied_by_folder()`, the new `state()`, and the
Pass-2 `make_folder_listing` `.md` view — and the three-way folder state
F2-AC8 / F3-AC6 need: `listed`, `absent` (Kado's tool-level `Path not found`
on `listDir`), `unanswered` (an endpoint 404 or any other error).

FALSIFICATION — mechanisms each test kills:
- `test_absent_is_only_kados_path_not_found` / `test_an_endpoint_404_is_
  unanswered_not_absent`: classify by exception type alone
  (`isinstance(exc, KadoNotFoundError)` → absent). The endpoint 404 is ALSO a
  `KadoNotFoundError`, so that mutation reports a misconfigured server as
  "the folder does not exist".
- `test_one_list_dir_per_folder_however_many_views_read_it`: give
  `make_folder_listing` (or `state()`) its own cache instead of the lookup's
  raw one — the second view then lists the folder again.
- `test_make_folder_listing_returns_todays_map`: any change to the `.md`
  filter, the `_dest_join` recomposition, the fold, or fail-open-to-empty.

CON-7: fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib import render_actions  # noqa: E402
from lib.kado_client import (  # noqa: E402
    KadoError,
    KadoNotFoundError,
    KadoToolError,
)
from lib.vault_folder_lookup import VaultFolderLookup  # noqa: E402
from lib.vault_paths import _asset_dest_join, _dest_join  # noqa: E402


def _load_reducer():
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer_t039_t1_4", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t039_t1_4"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()

FOLDER = "Atlas/290 Assets/295 Attachments/"

ENTRIES = [
    {"path": f"{FOLDER}Karte.PNG", "type": "file"},
    {"path": f"{FOLDER}scan.heic", "type": "file"},
    {"path": f"{FOLDER}Dresden.md", "type": "file"},
    {"path": f"{FOLDER}Notiz.MD", "type": "file"},
    {"path": f"{FOLDER}foto.png", "type": "folder"},
    {"path": f"{FOLDER}Archiv", "type": "folder"},
]

# The exact text kado_client raises for an HTTP 404 on the endpoint itself.
ENDPOINT_404 = (
    "Kado endpoint not found (HTTP 404). "
    "Check that KADO_URL points to the right server and port."
)


class CountingKado:
    """`list_dir` over fixed entries; counts round trips like `KadoClient`."""

    def __init__(self, entries=None, *, pages: int = 1, error: Exception | None = None):
        self.entries = list(entries or [])
        self.pages = pages
        self.error = error
        self.probed: list[str] = []
        self.call_count = 0

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500) -> list:
        self.probed.append(path)
        self.call_count += self.pages
        if self.error is not None:
            raise self.error
        return list(self.entries)


def _todays_make_folder_listing(kado_client):
    """Verbatim reproduction of `render_actions.make_folder_listing` before
    T1.4 — the reference the re-based view must match exactly."""
    cache: dict[str, dict[str, str]] = {}

    def folder_listing(location: str) -> dict[str, str]:
        folder = (location or "").rstrip("/") + "/"
        if folder not in cache:
            found: dict[str, str] = {}
            try:
                for entry in kado_client.list_dir(folder, depth=1):
                    path = entry.get("path") or ""
                    name = path.rsplit("/", 1)[-1]
                    if entry.get("type") != "file" or not name.lower().endswith(".md"):
                        continue
                    found[_dest_join(folder, name[:-3]).casefold()] = path
            except Exception:  # noqa: BLE001
                found = {}
            cache[folder] = found
        return cache[folder]

    return folder_listing


# ── state() ───────────────────────────────────────────────────────────────


def test_a_folder_that_lists_is_listed():
    lookup = VaultFolderLookup(CountingKado(ENTRIES))
    assert lookup.state(FOLDER) == "listed"


def test_an_empty_folder_is_still_listed():
    lookup = VaultFolderLookup(CountingKado([]))
    assert lookup.state(FOLDER) == "listed"


@pytest.mark.parametrize(
    "message",
    [
        f"listDir: Path not found: {FOLDER}",
        f'listDir: {{"code":"NOT_FOUND","message":"Path not found: {FOLDER}"}}',
    ],
)
def test_absent_is_only_kados_path_not_found(message):
    lookup = VaultFolderLookup(CountingKado(error=KadoNotFoundError(message)))
    assert lookup.state(FOLDER) == "absent"


def test_an_endpoint_404_is_unanswered_not_absent():
    lookup = VaultFolderLookup(CountingKado(error=KadoNotFoundError(ENDPOINT_404)))
    assert lookup.state(FOLDER) == "unanswered"


@pytest.mark.parametrize(
    "error",
    [
        KadoToolError("listDir returned an error: listDir target must be a folder"),
        KadoError("JSON-RPC error from Kado (-32000): boom"),
        RuntimeError("socket closed"),
    ],
)
def test_any_other_error_is_unanswered(error):
    lookup = VaultFolderLookup(CountingKado(error=error))
    assert lookup.state(FOLDER) == "unanswered"


@pytest.mark.parametrize(
    "error", [KadoNotFoundError(f"listDir: Path not found: {FOLDER}"), KadoError("x")]
)
def test_a_failed_listing_still_fails_open_and_is_charged(error):
    kado = CountingKado(ENTRIES, error=error)
    lookup = VaultFolderLookup(kado)
    assert lookup.notes(FOLDER) == {}
    assert lookup.assets(FOLDER) == {}
    assert lookup.occupied_by_folder(FOLDER) == set()
    assert lookup.folder_listing_calls == 1
    assert kado.probed == [FOLDER]


# ── views ─────────────────────────────────────────────────────────────────


def test_assets_keys_by_asset_dest_join_and_holds_non_md_files_only():
    lookup = VaultFolderLookup(CountingKado(ENTRIES))
    assert lookup.assets(FOLDER) == {
        _asset_dest_join(FOLDER, "Karte.PNG").casefold(): f"{FOLDER}Karte.PNG",
        _asset_dest_join(FOLDER, "scan.heic").casefold(): f"{FOLDER}scan.heic",
    }


def test_notes_keys_by_dest_join_and_holds_md_files_only():
    lookup = VaultFolderLookup(CountingKado(ENTRIES))
    assert lookup.notes(FOLDER) == {
        _dest_join(FOLDER, "Dresden").casefold(): f"{FOLDER}Dresden.md",
        _dest_join(FOLDER, "Notiz").casefold(): f"{FOLDER}Notiz.MD",
    }


def test_one_list_dir_per_folder_however_many_views_read_it():
    kado = CountingKado(ENTRIES)
    lookup = VaultFolderLookup(kado)
    listing = render_actions.make_folder_listing(lookup)

    lookup.state(FOLDER)
    lookup.notes(FOLDER.rstrip("/"))
    lookup.assets(FOLDER)
    lookup.occupied_by_folder(FOLDER)
    listing(FOLDER)
    listing(FOLDER.rstrip("/"))
    lookup.state(FOLDER.rstrip("/"))

    assert kado.probed == [FOLDER]
    assert lookup.folder_listing_calls == 1


def test_make_folder_listing_over_a_lookup_reads_that_lookups_listing():
    """Kills: wrapping the handed-in lookup as if it were a client — the inner
    lookup has no `list_dir`, fails open, and the view reads empty."""
    lookup = VaultFolderLookup(CountingKado(ENTRIES))
    listing = render_actions.make_folder_listing(lookup)
    assert listing(FOLDER) == lookup.notes(FOLDER)
    assert listing(FOLDER) != {}


def test_the_counter_charges_pages_not_folders():
    kado = CountingKado(ENTRIES, pages=3)
    lookup = VaultFolderLookup(kado)
    lookup.assets(FOLDER)
    lookup.notes(FOLDER)
    lookup.state(FOLDER)
    assert lookup.folder_listing_calls == 3


# ── make_folder_listing ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "kado_factory",
    [
        lambda: CountingKado(ENTRIES),
        lambda: CountingKado([]),
        lambda: CountingKado(error=KadoError("boom")),
        lambda: CountingKado(error=KadoNotFoundError(f"listDir: Path not found: {FOLDER}")),
    ],
)
def test_make_folder_listing_returns_todays_map(kado_factory):
    today = _todays_make_folder_listing(kado_factory())
    rebased = render_actions.make_folder_listing(kado_factory())
    for location in (FOLDER, FOLDER.rstrip("/"), "", "Other/"):
        assert rebased(location) == today(location)


def test_make_folder_listing_from_a_client_lists_each_folder_once():
    kado = CountingKado(ENTRIES)
    listing = render_actions.make_folder_listing(kado)
    listing(FOLDER)
    listing(FOLDER.rstrip("/"))
    listing("Other")
    assert kado.probed == [FOLDER, "Other/"]


# ── homes ─────────────────────────────────────────────────────────────────


def test_render_actions_re_exports_the_path_helpers():
    assert render_actions._dest_join is _dest_join
    assert render_actions._asset_dest_join is _asset_dest_join


def test_the_reducer_uses_the_shared_lookup():
    assert REDUCER._VaultFolderLookup is VaultFolderLookup
