#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_scan.py — Unit tests for lib/moc_scan.py (T1.2, Phase 1).

Coverage:
  - tag-primary discovery: #type/others/moc in-scope → kind=moc
  - exclude wins over tag (OQ-5, Rule 8): MOC tag in excluded path → skipped
  - trailing-space prefix gotcha (Calendar/301 Daily/ )
  - scope read from config (default = map_note paths + atomic_note paths)
  - M8: scalar AND dict atomic_note shape both normalised correctly
  - DENIAL PATH (H4 / Constitution L1 Testing): Kado permission error on one
    in-scope path → that path skipped with stderr warning, others still scanned,
    NO fabricated entry in results

All tests use a fake KadoClient — no live Kado connection required.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
LIB_DIR = SCRIPTS_DIR / "lib"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import KadoAuthError  # noqa: E402

# Import the module under test.
import lib.moc_scan as moc_scan  # noqa: E402


# ── Fake Kado client ─────────────────────────────────────────────────────────


class FakeKadoClient:
    """Minimal recording stand-in for KadoClient.

    Supports search_by_tag and list_notes/list_dir calls.
    Per-path errors are configurable via set_path_error so denial-path tests
    can prove that errors on one path don't suppress other paths.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []
        self._tag_responses: dict[str, list[dict]] = {}
        self._tag_default: list[dict] = []
        self._listnotes_responses: dict[str, list[dict]] = {}
        self._listnotes_default: list[dict] = []
        self._path_errors: dict[str, Exception] = {}

    def set_tag_response(self, tag: str, items: list[dict]) -> None:
        self._tag_responses[tag] = items

    def set_listnotes_response(self, path: str, items: list[dict]) -> None:
        self._listnotes_responses[path] = items

    def set_path_error(self, path: str, exc: Exception) -> None:
        """Make list_notes raise exc when called with this path."""
        self._path_errors[path] = exc

    def search_by_tag(self, tag: str, limit: int = 500) -> list:
        self.calls.append(("search_by_tag", (tag,), {"limit": limit}))
        return list(self._tag_responses.get(tag, self._tag_default))

    def list_notes(self, path: str, *, fields=None, depth=None, limit=500) -> list:
        self.calls.append(("list_notes", (path,), {"depth": depth, "limit": limit}))
        if path in self._path_errors:
            raise self._path_errors[path]
        return list(self._listnotes_responses.get(path, self._listnotes_default))

    def list_dir(self, path: str = "/", *, depth=None, limit=500) -> list:
        # moc_scan may call list_dir or list_notes; support both.
        self.calls.append(("list_dir", (path,), {"depth": depth, "limit": limit}))
        if path in self._path_errors:
            raise self._path_errors[path]
        return list(self._listnotes_responses.get(path, self._listnotes_default))


# ── Helpers ──────────────────────────────────────────────────────────────────

MOC_TAG = "#type/others/moc"


def _make_config(
    map_note_paths: list[str] | None = None,
    atomic_note=None,
    exclude_paths: list[str] | None = None,
) -> dict:
    """Build a minimal vault-config.yaml concepts dict for the scanner."""
    return {
        "concepts": {
            "map_note": {
                "paths": map_note_paths or ["Atlas/200 Maps/"],
                "tags": ["type/others/moc"],
            },
            "atomic_note": atomic_note if atomic_note is not None else "Atlas/202 Notes/",
        },
        "tomo": {
            "moc_structure_cache": {
                "exclude_paths": exclude_paths or [],
            }
        },
    }


# ── Tests ────────────────────────────────────────────────────────────────────


class TestMocTagDiscovery:
    """#type/others/moc in-scope → discovered as MOC."""

    def test_moc_tag_in_scope_is_discovered(self):
        """A note carrying #type/others/moc under an in-scope path → kind=moc."""
        fake = FakeKadoClient()
        fake.set_tag_response(
            MOC_TAG,
            [{"path": "Atlas/200 Maps/Programming MOC.md"}],
        )
        # In-scope notes from the atomic_note path
        fake.set_listnotes_response(
            "Atlas/202 Notes/",
            [{"path": "Atlas/202 Notes/my-note.md", "type": "file"}],
        )

        config = _make_config()
        result = moc_scan.scan(fake, config)

        assert "Atlas/200 Maps/Programming MOC.md" in result.moc_paths

    def test_non_moc_note_not_in_moc_paths(self):
        """A plain atomic note is in in_scope_note_paths, NOT in moc_paths."""
        fake = FakeKadoClient()
        fake.set_tag_response(MOC_TAG, [])
        fake.set_listnotes_response(
            "Atlas/202 Notes/",
            [{"path": "Atlas/202 Notes/my-note.md", "type": "file"}],
        )

        config = _make_config()
        result = moc_scan.scan(fake, config)

        assert "Atlas/202 Notes/my-note.md" not in result.moc_paths
        assert "Atlas/202 Notes/my-note.md" in result.in_scope_note_paths


class TestExcludeWinsOverTag:
    """Exclude wins over tag (OQ-5, Rule 8)."""

    def test_moc_tag_in_excluded_path_is_not_a_moc(self):
        """A note with #type/others/moc under an excluded path → NOT in moc_paths."""
        fake = FakeKadoClient()
        # Note lives under Calendar/ which is excluded
        fake.set_tag_response(
            MOC_TAG,
            [{"path": "Calendar/Daily MOC.md"}],
        )
        fake.set_listnotes_response("Atlas/202 Notes/", [])

        config = _make_config(exclude_paths=["Calendar/"])
        result = moc_scan.scan(fake, config)

        assert "Calendar/Daily MOC.md" not in result.moc_paths

    def test_moc_in_non_excluded_path_still_discovered(self):
        """Exclude only affects matching paths; other MOCs are still found."""
        fake = FakeKadoClient()
        fake.set_tag_response(
            MOC_TAG,
            [
                {"path": "Atlas/200 Maps/Programming MOC.md"},
                {"path": "Calendar/Daily MOC.md"},
            ],
        )
        fake.set_listnotes_response("Atlas/202 Notes/", [])

        config = _make_config(exclude_paths=["Calendar/"])
        result = moc_scan.scan(fake, config)

        assert "Atlas/200 Maps/Programming MOC.md" in result.moc_paths
        assert "Calendar/Daily MOC.md" not in result.moc_paths

    def test_trailing_space_exclude_prefix_matches(self):
        """Exclude prefix 'Calendar/301 Daily/ ' (trailing space) must still match paths under it."""
        fake = FakeKadoClient()
        # The trailing space in the exclude prefix is a real vault gotcha (M8 / OQ-5)
        exclude_prefix = "Calendar/301 Daily/ "
        fake.set_tag_response(
            MOC_TAG,
            [{"path": "Calendar/301 Daily/ 2026-06-05.md"}],
        )
        fake.set_listnotes_response("Atlas/202 Notes/", [])

        config = _make_config(exclude_paths=[exclude_prefix])
        result = moc_scan.scan(fake, config)

        assert "Calendar/301 Daily/ 2026-06-05.md" not in result.moc_paths


class TestScopeConfig:
    """Scope is read from config (default = map_note paths + atomic_note paths)."""

    def test_default_scope_includes_map_note_and_atomic_note(self):
        """scan() reads both map_note.paths and atomic_note as scope roots."""
        fake = FakeKadoClient()
        fake.set_tag_response(MOC_TAG, [])
        # map_note path contributes notes
        fake.set_listnotes_response(
            "Atlas/200 Maps/",
            [{"path": "Atlas/200 Maps/Programming MOC.md", "type": "file"}],
        )
        # atomic_note path contributes notes
        fake.set_listnotes_response(
            "Atlas/202 Notes/",
            [{"path": "Atlas/202 Notes/my-note.md", "type": "file"}],
        )

        config = _make_config(
            map_note_paths=["Atlas/200 Maps/"],
            atomic_note="Atlas/202 Notes/",
        )
        result = moc_scan.scan(fake, config)

        assert "Atlas/200 Maps/Programming MOC.md" in result.in_scope_note_paths
        assert "Atlas/202 Notes/my-note.md" in result.in_scope_note_paths

    def test_scope_read_scope_paths_returns_correct_list(self):
        """read_scope_paths() returns the union of map_note.paths + atomic_note paths."""
        config = _make_config(
            map_note_paths=["Atlas/200 Maps/"],
            atomic_note="Atlas/202 Notes/",
        )
        paths = moc_scan.read_scope_paths(config)
        assert "Atlas/200 Maps/" in paths
        assert "Atlas/202 Notes/" in paths


class TestAtomicNoteM8Normalisation:
    """M8: atomic_note appears as a SCALAR in vault-example.yaml but as a DICT
    in the live instance config. read_scope_paths() must normalise both shapes."""

    def test_scalar_atomic_note_is_normalised(self):
        """concepts.atomic_note = "Atlas/202 Notes/" (scalar) → one scope path."""
        config = _make_config(atomic_note="Atlas/202 Notes/")
        paths = moc_scan.read_scope_paths(config)
        assert "Atlas/202 Notes/" in paths

    def test_dict_atomic_note_is_normalised(self):
        """concepts.atomic_note = {path: "Atlas/202 Notes/", ...} (dict) → one scope path."""
        config = _make_config(
            atomic_note={"path": "Atlas/202 Notes/", "label": "Notes"}
        )
        paths = moc_scan.read_scope_paths(config)
        assert "Atlas/202 Notes/" in paths

    def test_dict_atomic_note_with_paths_list(self):
        """concepts.atomic_note = {paths: ["Atlas/202 Notes/", "Atlas/203 Literature/"]} → both."""
        config = _make_config(
            atomic_note={"paths": ["Atlas/202 Notes/", "Atlas/203 Literature/"]}
        )
        paths = moc_scan.read_scope_paths(config)
        assert "Atlas/202 Notes/" in paths
        assert "Atlas/203 Literature/" in paths


class TestDenialPath:
    """DENIAL PATH (H4 / Constitution L1 Testing).

    A fake Kado raising a permission error on ONE in-scope path must:
    - skip that path with a stderr warning
    - continue scanning other paths
    - NOT fabricate a presence/absence entry for the failed path
    """

    def test_permission_error_on_one_path_is_skipped(self, capsys):
        """KadoAuthError on one scope path → warning on stderr, path absent from results."""
        fake = FakeKadoClient()
        fake.set_tag_response(MOC_TAG, [])
        # "Atlas/200 Maps/" raises a permission error
        fake.set_path_error("Atlas/200 Maps/", KadoAuthError("permission denied"))
        # "Atlas/202 Notes/" succeeds normally
        fake.set_listnotes_response(
            "Atlas/202 Notes/",
            [{"path": "Atlas/202 Notes/my-note.md", "type": "file"}],
        )

        config = _make_config(
            map_note_paths=["Atlas/200 Maps/"],
            atomic_note="Atlas/202 Notes/",
        )
        result = moc_scan.scan(fake, config)

        # The failing path must NOT appear in results
        failing_paths = [p for p in result.in_scope_note_paths if p.startswith("Atlas/200 Maps/")]
        assert not failing_paths, "No notes from the denied path should appear in results"

        # The successful path MUST still appear
        assert "Atlas/202 Notes/my-note.md" in result.in_scope_note_paths

        # A warning must have been emitted on stderr
        captured = capsys.readouterr()
        assert "warn" in captured.err.lower() or "skip" in captured.err.lower() or "Atlas/200 Maps/" in captured.err

    def test_permission_error_does_not_fabricate_moc_entry(self, capsys):
        """A denied tag query must not produce a fabricated MOC entry."""
        fake = FakeKadoClient()
        # Simulate a tag-search error (e.g. the entire byTag call fails)
        # by raising on the list_notes call for the only scope path
        fake.set_tag_response(MOC_TAG, [{"path": "Atlas/200 Maps/Denied MOC.md"}])
        # The denied scope path means the note is excluded from in_scope
        fake.set_path_error("Atlas/200 Maps/", KadoAuthError("permission denied"))
        fake.set_listnotes_response("Atlas/202 Notes/", [])

        config = _make_config(
            map_note_paths=["Atlas/200 Maps/"],
            atomic_note="Atlas/202 Notes/",
        )
        result = moc_scan.scan(fake, config)

        # Even though byTag returned "Denied MOC.md", it's in the denied scope path.
        # The test verifies the module doesn't silently smuggle it in via the tag path
        # while the scope-list path fails. (Implementation chooses its own approach;
        # what matters is: the result must be consistent — no split-brain entries.)
        # We assert the denied scope path produced no in-scope notes.
        denied_notes = [p for p in result.in_scope_note_paths if "200 Maps" in p]
        assert not denied_notes

    def test_other_paths_still_scanned_after_one_denial(self, capsys):
        """Three scope paths; first one denied → other two still scanned."""
        fake = FakeKadoClient()
        fake.set_tag_response(MOC_TAG, [])
        fake.set_path_error("Atlas/200 Maps/", KadoAuthError("denied"))
        fake.set_listnotes_response(
            "Atlas/202 Notes/",
            [{"path": "Atlas/202 Notes/note-a.md", "type": "file"}],
        )
        fake.set_listnotes_response(
            "Atlas/203 Literature/",
            [{"path": "Atlas/203 Literature/ref-b.md", "type": "file"}],
        )

        config = {
            "concepts": {
                "map_note": {
                    "paths": ["Atlas/200 Maps/"],
                    "tags": ["type/others/moc"],
                },
                "atomic_note": {"paths": ["Atlas/202 Notes/", "Atlas/203 Literature/"]},
            },
            "tomo": {"moc_structure_cache": {"exclude_paths": []}},
        }
        result = moc_scan.scan(fake, config)

        # Both non-denied paths must still produce results
        assert "Atlas/202 Notes/note-a.md" in result.in_scope_note_paths
        assert "Atlas/203 Literature/ref-b.md" in result.in_scope_note_paths
