#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_tree_builder_profile_marker.py — Phase 4 T4.2 wire-in.

moc-tree-builder.py must resolve the active profile's parent_marker from its
existing --config and thread it into up_parse.parse_up_from_content (spec 028
ADR-1). FOOTER_CALLOUTS is out of scope and untouched.

Locks:
  1. A config selecting a profile whose parent_marker differs → relationship
     links written with that marker are parsed into up_target.
  2. miyo (default) → up:: still parses (CON-2 byte-identical).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_builder = _load("moc_tree_builder", "moc-tree-builder.py")


class FakeKadoClient:
    def __init__(self, *, tagged=None, listings=None, notes=None):
        self._tagged = tagged or []
        self._listings = listings or {}
        self._notes = notes or {}

    def search_by_tag(self, tag, limit=500):
        return list(self._tagged)

    def list_notes(self, path, **kwargs):
        return list(self._listings.get(path, []))

    def read_note(self, path):
        if path not in self._notes:
            from lib.kado_client import KadoNotFoundError
            raise KadoNotFoundError(f"not found: {path}")
        return {"content": self._notes[path]}


def _config(profile=None):
    cfg = {
        "concepts": {
            "map_note": {"paths": ["Atlas/200 Maps/"], "tags": ["type/others/moc"]},
            "atomic_note": {"path": "Atlas/202 Notes/"},
        },
        "tomo": {
            "moc_structure_cache": {
                "scope_paths": ["Atlas/200 Maps/", "Atlas/202 Notes/"],
                "exclude_paths": [],
                "ttl_days": 1,
                "moc_tag": "type/others/moc",
            }
        },
    }
    if profile is not None:
        cfg["profile"] = profile
    return cfg


def _scene():
    home = "Atlas/200 Maps/Home.md"
    child = "Atlas/202 Notes/Child.md"
    return home, child


def test_custom_parent_marker_parsed_via_config(tmp_path, monkeypatch):
    """A profile whose parent_marker is 'parent::' → 'parent:: [[Home]]' parses."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "custom.yaml").write_text(
        "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_builder, "DEFAULT_PROFILES_DIR", profiles_dir)

    home, child = _scene()
    client = FakeKadoClient(
        tagged=[{"path": home}],
        listings={
            "Atlas/200 Maps/": [{"path": home}],
            "Atlas/202 Notes/": [{"path": child}],
        },
        notes={
            home: "---\ntitle: Home\n---\n# Home\n",
            child: "---\ntitle: Child\n---\n# Child\n\nparent:: [[Home]]\n",
        },
    )
    cache, _feed = _builder.run_with_client(client, _config(profile="custom"))
    by_path = {e["path"]: e for e in cache["entries"]}
    assert by_path[child]["up_target"] == "Home"
    assert by_path[child]["up_state"] == "valid"


def test_custom_marker_does_not_parse_default_up(tmp_path, monkeypatch):
    """Under the custom parent_marker, a legacy 'up::' line must NOT parse
    (proves the marker is actually driven by the profile, not hardcoded)."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "custom.yaml").write_text(
        "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_builder, "DEFAULT_PROFILES_DIR", profiles_dir)

    home, child = _scene()
    client = FakeKadoClient(
        tagged=[{"path": home}],
        listings={
            "Atlas/200 Maps/": [{"path": home}],
            "Atlas/202 Notes/": [{"path": child}],
        },
        notes={
            home: "---\ntitle: Home\n---\n# Home\n",
            child: "---\ntitle: Child\n---\n# Child\n\nup:: [[Home]]\n",
        },
    )
    cache, _feed = _builder.run_with_client(client, _config(profile="custom"))
    by_path = {e["path"]: e for e in cache["entries"]}
    assert by_path[child]["up_target"] is None
    assert by_path[child]["up_state"] == "absent"


def test_miyo_up_marker_still_parses(tmp_path, monkeypatch):
    """miyo default → 'up:: [[Home]]' parses (CON-2 byte-identical)."""
    # Real bundled profiles dir; miyo.yaml → up::.
    home, child = _scene()
    client = FakeKadoClient(
        tagged=[{"path": home}],
        listings={
            "Atlas/200 Maps/": [{"path": home}],
            "Atlas/202 Notes/": [{"path": child}],
        },
        notes={
            home: "---\ntitle: Home\n---\n# Home\n",
            child: "---\ntitle: Child\n---\n# Child\n\nup:: [[Home]]\n",
        },
    )
    cache, _feed = _builder.run_with_client(client, _config(profile="miyo"))
    by_path = {e["path"]: e for e in cache["entries"]}
    assert by_path[child]["up_target"] == "Home"
    assert by_path[child]["up_state"] == "valid"
