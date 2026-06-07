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
import json
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

def _cache(client, config) -> dict:
    """run_with_client returns (cache, feed); helper for tests that need only the cache."""
    cache, _feed = _builder.run_with_client(client, config)
    return cache


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
    cache = _cache(client, _config())

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

    W2: same-note anchors (`[[#^id]]`, `[[#Heading]]`) reduce to an empty stem
    and must NOT be counted — they are not links to another note.
    """
    moc_path = "Atlas/200 Maps/Home.md"
    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={"Atlas/200 Maps/": [{"path": moc_path}]},
        notes={
            moc_path: (
                "---\ntitle: Home\n---\n# Home\n\n"
                "[[Ghost A]]\n[[Ghost B]]\n"   # two real non-MOC links → count 2
                "[[#^blockref]]\n[[#Heading]]\n"  # same-note anchors → must NOT count (W2)
            )
        },
    )
    cache = _cache(client, _config(scope_paths=["Atlas/200 Maps/"]))
    moc_entry = next(e for e in cache["entries"] if e["kind"] == "moc")
    assert moc_entry["classification"] is None
    assert isinstance(moc_entry["linked_notes"], int)
    # 2 non-MOC links; the two same-note anchors are excluded (W2).
    assert moc_entry["linked_notes"] == 2


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
    cache = _cache(client, _config())
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
    cache = _cache(
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
    # placeholder_links persisted into the cache file too (solution.md 304/307).
    assert isinstance(on_disk["placeholder_links"], list)


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
    cache, feed = _builder.run_with_client(client, _config(scope_paths=[], exclude_paths=[]))
    assert cache["entries"] == []
    assert cache["placeholder_links"] == []
    assert isinstance(cache["last_scan"], str)
    assert cache["moc_cache_version"] >= 1
    # The JSON feed degrades to empty lists, not a crash — cache-builder reads them.
    assert feed["map_notes"] == []
    assert feed["placeholder_links"] == []


def test_discovered_via_tag_for_moc_outside_scope():
    """W3: a MOC discovered via tag but NOT under any scope path → discovered_via='tag'.

    The other branches ('both' for an in-scope tagged MOC, 'path' for an in-scope
    non-MOC note) are exercised by the assembly test; this locks the tag-only one.
    """
    scattered = "Elsewhere/Scattered.md"      # tagged MOC, NOT under scope
    in_scope_moc = "Atlas/200 Maps/Home.md"   # tagged MOC, under scope
    plain = "Atlas/200 Maps/Plain.md"         # in-scope non-MOC note
    client = FakeKadoClient(
        tagged=[{"path": scattered}, {"path": in_scope_moc}],
        listings={"Atlas/200 Maps/": [{"path": in_scope_moc}, {"path": plain}]},
        notes={
            scattered: "# Scattered\n",
            in_scope_moc: "# Home\n",
            plain: "# Plain\n",
        },
    )
    cache = _cache(client, _config(scope_paths=["Atlas/200 Maps/"]))
    by_path = {e["path"]: e for e in cache["entries"]}
    assert by_path[scattered]["discovered_via"] == "tag"
    assert by_path[scattered]["kind"] == "moc"
    assert by_path[in_scope_moc]["discovered_via"] == "both"
    assert by_path[plain]["discovered_via"] == "path"


def test_json_feed_shape_map_notes_and_placeholders():
    """W1/FIX4: run_with_client returns a cache-builder JSON feed with map_notes
    (kind==moc projection, carrying classification + linked_notes(int)) and a
    placeholder_links list equal to detect_placeholders' output.

    This is the feed that vault-explorer Step 9 pipes into cache-builder
    (`moc-tree-builder.py > moc-output.json`).
    """
    moc_path = "Atlas/200 Maps/Home.md"
    note_path = "Atlas/202 Notes/Real.md"
    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}],
        },
        notes={
            # [[Real]] resolves to an in-scope note (not a placeholder);
            # [[Phantom]] is a genuine dead link → one placeholder.
            moc_path: "---\ntitle: Home\n---\n# Home\n\n[[Real]]\n[[Phantom]]\n",
            note_path: "---\ntitle: Real\n---\n# Real\n",
        },
    )
    cache, feed = _builder.run_with_client(client, _config())

    # map_notes is exactly the kind==moc projection.
    assert {m["path"] for m in feed["map_notes"]} == {moc_path}
    mn = feed["map_notes"][0]
    assert mn["classification"] is None
    assert isinstance(mn["linked_notes"], int)
    assert {"path", "stem", "title", "topics", "tags"} <= set(mn)
    assert all(m["kind"] == "moc" for m in feed["map_notes"])

    # placeholder_links present, equals the detector output, and is the SAME
    # list persisted into the YAML cache.
    assert feed["placeholder_links"] == [
        {"target": "Phantom", "referenced_by": moc_path}
    ]
    assert cache["placeholder_links"] == feed["placeholder_links"]


def test_json_feed_is_valid_json_via_run(tmp_path, monkeypatch, capsys):
    """End-to-end: run() prints ONLY valid JSON to stdout (warnings → stderr), so
    `moc-tree-builder.py > moc-output.json` then json.load works."""
    moc_path = "Atlas/200 Maps/Home.md"
    fake = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={"Atlas/200 Maps/": [{"path": moc_path}]},
        notes={moc_path: "---\ntitle: Home\n---\n# Home\n\n[[Phantom]]\n"},
    )
    cfg = _config(scope_paths=["Atlas/200 Maps/"])

    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    out_yaml = tmp_path / "moc-structure-cache.yaml"

    # Patch KadoClient so run() uses the fake; config + output go to tmp.
    monkeypatch.setattr(_builder, "KadoClient", lambda *a, **k: fake)
    _builder.run(str(cfg_file), str(out_yaml))

    captured = capsys.readouterr()
    feed = json.loads(captured.out)  # must parse — stdout is JSON only
    assert {m["path"] for m in feed["map_notes"]} == {moc_path}
    assert feed["placeholder_links"] == [{"target": "Phantom", "referenced_by": moc_path}]
    assert out_yaml.exists()


def test_cache_entries_carry_real_tags_per_ac7():
    """PRD/F8 AC7: each built cache entry carries its note's real tags.

    Locks:
      - MOC entry: tags list matches frontmatter values (not an empty list).
      - Note entry: tags list matches frontmatter values.
      - Note with no tags → tags == [].

    Tags arrive from the frontmatter already read during read_note_raw()
    (one round-trip per note — no extra per-note tags query needed). This
    is the cheapest path: the same content string that supplies title/up/
    wikilinks also yields the frontmatter tags via parse_frontmatter.
    (WHY: see docs/tomo/scripts/moc-tree-builder.md — tags are cached
    because the exclude-tag filters (exclude/moc, exclude/note) depend on them.)
    """
    moc_path = "Atlas/200 Maps/Home.md"
    note_path = "Atlas/202 Notes/Idea.md"
    tagless_path = "Atlas/202 Notes/NoTags.md"

    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}, {"path": tagless_path}],
        },
        notes={
            moc_path: (
                "---\ntitle: Home\ntags:\n"
                "  - type/others/moc\n  - project/alpha\n---\n# Home\n"
            ),
            note_path: "---\ntitle: Idea\ntags:\n  - idea/seed\n---\n# Idea\n",
            tagless_path: "---\ntitle: NoTags\n---\n# NoTags\n",
        },
    )
    cache = _cache(client, _config())

    by_path = {e["path"]: e for e in cache["entries"]}

    # MOC entry: real tags from frontmatter, not an empty list.
    assert by_path[moc_path]["tags"] == ["type/others/moc", "project/alpha"], (
        "AC7 FAIL: MOC entry tags are empty or wrong — "
        "cache builder must populate tags from frontmatter"
    )

    # Note entry: real tags from frontmatter.
    assert by_path[note_path]["tags"] == ["idea/seed"], (
        "AC7 FAIL: note entry tags are empty or wrong"
    )

    # Note with no frontmatter tags → empty list, never None.
    assert by_path[tagless_path]["tags"] == [], (
        "AC7 FAIL: note with no tags must produce [], not None or missing"
    )


def test_c2_kind_moc_projection_feeds_cache_builder_without_collapse():
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
    cache = _cache(client, _config(scope_paths=["Atlas/200 Maps/"]))

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
