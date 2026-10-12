#!/usr/bin/env python3
# version: 0.1.0
"""attachment_plan_fakes.py — one fake vault behind both of the plan's vault
views, and the `plan_from_remedies` helper the old builder harnesses migrate
through (spec 039 T4.2, T4.3).

Lives in tests/, not tomo/scripts/lib/: it is never a production code path and
tomo/ is synced into the instance. Not named `test_*`, so pytest does not
collect it.

`FakeVault` holds one set of file paths and answers both questions the plan
asks, so a test cannot give K2 and K3 two different vaults:

- `.client` — a Kado stand-in with `list_dir(folder, depth=1)` and a
  `call_count`, driven through the REAL `VaultFolderLookup` (K2), so the plan
  is tested against K2's real interface, not a copy of it. A folder that holds
  no file and is not named in `existing_folders` is absent (Kado's
  `Path not found`); a folder in `failing_folders` raises a plain `KadoError`
  (unanswered).
- `.census` — K3's interface (`count`, `searches`, `pages`): files whose
  basename case-folds equal (NFC) to the asked name, one search per distinct
  name; a name in `unanswered_names` answers `None`.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.attachment_plan import build_attachment_plan  # noqa: E402
from lib.kado_client import KadoError, KadoNotFoundError  # noqa: E402
from lib.vault_folder_lookup import VaultFolderLookup  # noqa: E402


def _key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _parent(path: str) -> str:
    return path.rstrip("/").rpartition("/")[0]


class _FakeKado:
    def __init__(self, vault: "FakeVault") -> None:
        self._vault = vault
        self.call_count = 0
        self.listed: list[str] = []

    def list_dir(self, folder: str, depth: int = 1) -> list[dict]:
        self.call_count += 1
        name = folder.rstrip("/")
        self.listed.append(name)
        if name in self._vault.failing_folders:
            raise KadoError("Kado timed out")
        if name not in self._vault.folders():
            raise KadoNotFoundError(f"Path not found: {folder}")
        entries = [
            {"path": p, "type": "file"}
            for p in self._vault.files if _parent(p) == name
        ]
        entries += [
            {"path": f, "type": "folder"}
            for f in sorted(self._vault.folders()) if f and _parent(f) == name
        ]
        return entries


class _FakeCensus:
    def __init__(self, vault: "FakeVault") -> None:
        self._vault = vault
        self._asked: set[str] = set()
        self.searches = 0
        self.pages = 0

    def count(self, basename: str) -> int | None:
        key = _key(basename)
        if key not in self._asked:
            self._asked.add(key)
            self.searches += 1
            self.pages += 1
        if key in {_key(n) for n in self._vault.unanswered_names}:
            return None
        return sum(1 for p in self._vault.files if _key(p.rsplit("/", 1)[-1]) == key)


class FakeVault:
    def __init__(
        self,
        files=(),
        *,
        existing_folders=(),
        failing_folders=(),
        unanswered_names=(),
    ) -> None:
        self.files = list(files)
        self.existing_folders = {f.rstrip("/") for f in existing_folders}
        self.failing_folders = {f.rstrip("/") for f in failing_folders}
        self.unanswered_names = set(unanswered_names)
        self.client = _FakeKado(self)
        self.lookup = VaultFolderLookup(self.client)
        self.census = _FakeCensus(self)

    def folders(self) -> set[str]:
        """Every folder that exists: each file's ancestors plus the named ones."""
        found = set()
        for path in list(self.files) + list(self.existing_folders):
            parts = path.split("/")
            upto = len(parts) - 1 if path in self.files else len(parts)
            for i in range(1, upto + 1):
                found.add("/".join(parts[:i]))
        return found


def plan_from_remedies(
    confirmed,
    remedies=None,
    *,
    inbox_path,
    asset_folder,
    vault: FakeVault | None = None,
):
    """Build the plan the way the old `_build_move_asset_actions(...,
    attachment_conflict_remedies=...)` call sites assumed the vault was:
    holding only the inbox copies of every attachment, with the asset folder
    present and free. Pass `vault` to describe any other vault.
    """
    if vault is None:
        sources = [
            p for item in confirmed for p in (item.get("attachments") or [])
            if p.rsplit("/", 1)[-1]
        ]
        vault = FakeVault(sources, existing_folders=[asset_folder])
    return build_attachment_plan(
        confirmed,
        {r["source"]: r for r in (remedies or [])},
        asset_folder=asset_folder,
        inbox_path=inbox_path,
        folder_lookup=vault.lookup,
        census=vault.census,
    )
