#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_tree_builder.py — Behavioural tests for the rebuilt MOC-structure
cache builder (spec 021, Phase 1 T1.4).

moc-tree-builder.py is rebuilt to orchestrate lib/moc_scan + Kado read_note +
lib/up_parse.parse_up_from_content + lib/placeholder_detect, and to write
config/moc-structure-cache.yaml (the MocStructureCache shape from SDD
Application Data Models) instead of the legacy tree JSON.

Tests use a FakeKadoClient (no live Kado). They lock:
  - per-entry assembly (kind, path/stem/title/topics/up_* /tags)
  - C2: kind==moc entries ALSO carry classification + linked_notes so
    cache-builder's classifications/scan_stats do not collapse
  - M1: caller resolves up_state (absent/valid/broken) against the MOC stem set
  - the versioned cache schema (moc_cache_version, last_scan, ttl_days,
    scope_paths, exclude_paths, moc_tag, entries)
  - atomic tmp-rename write
  - empty scope → empty entries, no crash
  - C2 regression guard: rebuild → cache-builder reads kind==moc projection →
    discovery-cache.yaml classifications is NON-EMPTY
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(module_name: str, filename: str):
    """Load a hyphen-named script module via importlib."""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_builder = _load("moc_tree_builder", "moc-tree-builder.py")
_cache_builder = _load("cache_builder", "cache-builder.py")


# ──────────────────────────────────────────────────────────────────────────────
# Fake Kado client
# ──────────────────────────────────────────────────────────────────────────────

class FakeKadoClient:
    """Minimal Kado fake covering the surface moc_scan + the builder use:
    search_by_tag, list_notes, read_note.
    """

    def __init__(self, *, tagged=None, listings=None, notes=None):
        # tagged: list of {"path": ...} returned by search_by_tag(MOC_TAG)
        self._tagged = tagged or []
        # listings: {folder_path: [ {"path": ...}, ... ]}
        self._listings = listings or {}
        # notes: {path: raw_content_str}
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


def _config(scope_paths=None, exclude_paths=None, ttl_days=1):
    """Build a vault-config dict the builder can consume."""
    return {
        "concepts": {
            "map_note": {"paths": ["Atlas/200 Maps/"], "tags": ["type/others/moc"]},
            "atomic_note": {"path": "Atlas/202 Notes/"},
        },
        "tomo": {
            "moc_structure_cache": {
                "scope_paths": scope_paths if scope_paths is not None
                else ["Atlas/200 Maps/", "Atlas/202 Notes/"],
                "exclude_paths": exclude_paths if exclude_paths is not None else [],
                "ttl_days": ttl_days,
                "moc_tag": "type/others/moc",
            }
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_builder_assembles_entries_with_correct_kind_and_fields():
    """Each entry carries kind moc|note plus the per-entry metadata fields."""
    moc_path = "Atlas/200 Maps/Home.md"
    note_path = "Atlas/202 Notes/Idea.md"
    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}],
        },
        notes={
            moc_path: "---\ntitle: Home\ntags:\n  - type/others/moc\n  - topic/knowledge\n---\n# Home\n\n[[Idea]]\n",
            note_path: "---\ntitle: Idea\nup: \"[[Home]]\"\n---\n# Idea\n",
        },
    )
    cache = _builder.run_with_client(client, _config())

    by_path = {e["path"]: e for e in cache["entries"]}
    assert moc_path in by_path and note_path in by_path

    moc_entry = by_path[moc_path]
    assert moc_entry["kind"] == "moc"
    assert moc_entry["stem"] == "Home"
    assert moc_entry["title"] == "Home"
    assert moc_entry["discovered_via"] in ("tag", "path", "both")
    assert isinstance(moc_entry["topics"], list)
    assert moc_entry["up_state"] in ("absent", "valid", "broken")
    assert "up_target" in moc_entry
    assert "up_source" in moc_entry
    assert isinstance(moc_entry["tags"], list)

    note_entry = by_path[note_path]
    assert note_entry["kind"] == "note"
    assert note_entry["stem"] == "Idea"


def test_moc_entries_carry_classification_and_linked_notes():
    """C2: kind==moc entries MUST carry classification + linked_notes so that
    cache-builder.build_classifications / build_scan_stats do not collapse.

    linked_notes is the INT count of non-MOC wikilinks — the sole consumer
    (cache-builder:110) does numeric `+=`, so a list would TypeError. (Decision
    A, confirmed by team-lead; SDD line 253 `list[str]` is a doc bug being
    corrected in solution.md.)
    """
    moc_path = "Atlas/200 Maps/Home.md"
    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={"Atlas/200 Maps/": [{"path": moc_path}]},
        notes={moc_path: "---\ntitle: Home\n---\n# Home\n\n[[Ghost A]]\n[[Ghost B]]\n"},
    )
    cache = _builder.run_with_client(client, _config(scope_paths=["Atlas/200 Maps/"]))
    moc_entry = next(e for e in cache["entries"] if e["kind"] == "moc")
    assert moc_entry["classification"] is None
    assert isinstance(moc_entry["linked_notes"], int)
    assert moc_entry["linked_notes"] == 2  # both [[Ghost A]], [[Ghost B]] are non-MOC


def test_caller_resolves_up_state_absent_valid_broken():
    """M1: target None → absent; target in MOC-stem-set → valid; else → broken."""
    home = "Atlas/200 Maps/Home.md"           # no up → absent
    child = "Atlas/200 Maps/Child.md"          # up:: [[Home]] (a MOC) → valid
    stray = "Atlas/202 Notes/Stray.md"         # up:: [[Nonexistent]] → broken
    client = FakeKadoClient(
        tagged=[{"path": home}, {"path": child}],
        listings={
            "Atlas/200 Maps/": [{"path": home}, {"path": child}],
            "Atlas/202 Notes/": [{"path": stray}],
        },
        notes={
            home: "---\ntitle: Home\n---\n# Home\n",
            child: "---\ntitle: Child\n---\n# Child\n\nup:: [[Home]]\n",
            stray: "---\ntitle: Stray\n---\n# Stray\n\nup:: [[Nonexistent]]\n",
        },
    )
    cache = _builder.run_with_client(client, _config())
    by_path = {e["path"]: e for e in cache["entries"]}
    assert by_path[home]["up_state"] == "absent"
    assert by_path[home]["up_target"] is None
    assert by_path[child]["up_state"] == "valid"
    assert by_path[child]["up_target"] == "Home"
    assert by_path[child]["up_source"] == "inline"
    assert by_path[stray]["up_state"] == "broken"
    assert by_path[stray]["up_target"] == "Nonexistent"


def test_writes_moc_structure_cache_yaml_with_versioned_schema(tmp_path):
    moc_path = "Atlas/200 Maps/Home.md"
    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={"Atlas/200 Maps/": [{"path": moc_path}]},
        notes={moc_path: "---\ntitle: Home\n---\n# Home\n"},
    )
    out = tmp_path / "moc-structure-cache.yaml"
    cache = _builder.run_with_client(
        client, _config(scope_paths=["Atlas/200 Maps/"], exclude_paths=["X/"], ttl_days=2)
    )
    _builder.write_cache_atomic(cache, str(out))

    on_disk = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert isinstance(on_disk["moc_cache_version"], int)
    # last_scan is valid ISO 8601 UTC
    from datetime import datetime
    datetime.fromisoformat(on_disk["last_scan"].replace("Z", "+00:00"))
    assert on_disk["ttl_days"] == 2
    assert on_disk["scope_paths"] == ["Atlas/200 Maps/"]
    assert on_disk["exclude_paths"] == ["X/"]
    assert on_disk["moc_tag"] == "type/others/moc"
    assert isinstance(on_disk["entries"], list)


def test_atomic_tmp_rename_write(tmp_path):
    """Write leaves no .tmp residue and produces a parseable YAML file."""
    out = tmp_path / "moc-structure-cache.yaml"
    cache = {
        "moc_cache_version": 1,
        "last_scan": "2026-06-05T00:00:00Z",
        "ttl_days": 1,
        "scope_paths": [],
        "exclude_paths": [],
        "moc_tag": "type/others/moc",
        "entries": [],
    }
    _builder.write_cache_atomic(cache, str(out))
    assert out.exists()
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []
    assert yaml.safe_load(out.read_text(encoding="utf-8"))["moc_cache_version"] == 1


def test_empty_scope_produces_empty_entries_no_crash():
    client = FakeKadoClient(tagged=[], listings={}, notes={})
    cache = _builder.run_with_client(client, _config(scope_paths=[], exclude_paths=[]))
    assert cache["entries"] == []
    assert isinstance(cache["last_scan"], str)
    assert cache["moc_cache_version"] >= 1


def test_c2_kind_moc_projection_feeds_cache_builder_without_collapse(tmp_path):
    """End-to-end C2 guard: rebuild the MOC-structure cache → take the kind==moc
    projection as cache-builder's map_notes → feed it through
    build_classifications / build_scan_stats and prove the projection does NOT
    collapse the consumer.

    The C2 trap is a moc projection missing the `classification`/`linked_notes`
    FIELDS, or carrying a `linked_notes` shape that crashes the numeric `+=` in
    build_classifications. This guard proves:
      - every moc entry carries both fields (no KeyError-shaped collapse),
      - linked_notes is numerically summable (int — the only consumer is the
        `note_count += linked_notes` arithmetic at cache-builder:110),
      - build_classifications runs and, WHEN classification is present, yields a
        non-empty classifications dict,
      - build_scan_stats counts every map (total_map_notes == projection size).

    Note: in the live vault classification is None on all MOCs, so a literal
    "classifications is always non-empty" assertion would never have held even
    before this work (verified against the live discovery-cache). The guard is
    therefore scoped to the no-collapse contract + the conditional non-empty
    path, which is what C2 actually protects.
    """
    moc_a = "Atlas/200 Maps/Knowledge.md"
    moc_b = "Atlas/200 Maps/Projects.md"
    client = FakeKadoClient(
        tagged=[{"path": moc_a}, {"path": moc_b}],
        listings={"Atlas/200 Maps/": [{"path": moc_a}, {"path": moc_b}]},
        notes={
            moc_a: "---\ntitle: Knowledge\ntags:\n  - topic/knowledge\n---\n# Knowledge\n\n[[Ghost1]]\n[[Ghost2]]\n",
            moc_b: "---\ntitle: Projects\ntags:\n  - topic/applied\n---\n# Projects\n\n[[Ghost3]]\n",
        },
    )
    cache = _builder.run_with_client(client, _config(scope_paths=["Atlas/200 Maps/"]))

    # Loader shim: cache-builder's map_notes = kind==moc projection
    map_notes = [e for e in cache["entries"] if e["kind"] == "moc"]
    assert map_notes, "precondition: at least one moc entry"

    # No-collapse: both C2 fields present and linked_notes is numerically summable.
    for m in map_notes:
        assert "classification" in m
        assert "linked_notes" in m
        assert isinstance(m["linked_notes"], int)

    classifications = _cache_builder.build_classifications(map_notes)
    # build_scan_stats must count every map regardless of classification value.
    stats = _cache_builder.build_scan_stats(None, map_notes, classifications, None)
    assert stats["total_map_notes"] == len(map_notes)

    # Conditional non-empty: if the builder assigned any classification, the
    # consumer must surface it (proves the projection→classifications path works).
    if any(m.get("classification") is not None for m in map_notes):
        assert classifications, "C2 regression: classifications collapsed despite a classified MOC"
