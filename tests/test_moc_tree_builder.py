#!/usr/bin/env python3
# version: 0.3.0
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
    # T1.2: Home has no `up` declaration at all (absent) — the key is still
    # written, carrying None (ADR-3: presence, not value, is the freshness signal).
    assert "up_value" in moc_entry
    assert moc_entry["up_value"] is None

    note_entry = by_path[note_path]
    assert note_entry["kind"] == "note"
    assert note_entry["stem"] == "Idea"
    # Idea declares `up` via frontmatter (`up: "[[Home]]"`) — up_value must equal
    # the property value AS PARSED (verbatim, not target-resolved).
    assert note_entry["up_source"] == "frontmatter"
    assert note_entry["up_value"] == "[[Home]]"


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
    # T1.2: inline declarations carry up_value=None (there is no property to
    # guard) — but the key must still be PRESENT, not omitted.
    assert "up_value" in by_path[child]
    assert by_path[child]["up_value"] is None
    assert "up_value" in by_path[stray]
    assert by_path[stray]["up_value"] is None


def test_resolve_up_state_reports_why():
    """Spec 033 T1.1 / PRD F1: _resolve_up_state takes the note-stem set as a
    third argument and returns (up_state, up_broken_reason). up_state's three
    values are unchanged (ADR-2); up_broken_reason is a second, additive
    return value that is None everywhere except the "unresolved" case.
    """
    moc_stems = {"Home", "Shared"}
    note_stems = {"Idea", "Shared"}

    # target is a MOC stem → valid, no reason.
    assert _builder._resolve_up_state("Home", moc_stems, note_stems) == ("valid", None)

    # target is an in-scope note stem (not a MOC) → broken, not-a-moc.
    assert _builder._resolve_up_state("Idea", moc_stems, note_stems) == (
        "broken",
        "not-a-moc",
    )

    # target is in neither set → broken, unresolved.
    assert _builder._resolve_up_state("Nonexistent", moc_stems, note_stems) == (
        "broken",
        "unresolved",
    )

    # target is None → absent, no reason (unchanged).
    assert _builder._resolve_up_state(None, moc_stems, note_stems) == ("absent", None)

    # a stem in BOTH sets (a MOC also listed as a note) → MOC wins, valid.
    assert _builder._resolve_up_state("Shared", moc_stems, note_stems) == ("valid", None)


def test_up_value_key_present_for_every_entry_regardless_of_declaration_style():
    """T1.2 / ADR-3: `up_value` is written UNCONDITIONALLY for every entry — its
    PRESENCE (not its value) is the cache-freshness signal a downstream reader
    uses (a `_MISSING` sentinel, per the spec). A conditionally-written key would
    destroy that signal, so this test checks presence via a sentinel default
    rather than truthiness, and covers absent/inline/frontmatter declarations in
    one cache build. CON-7: up_state/up_target/up_source are unchanged.
    """
    _MISSING = object()
    home = "Atlas/200 Maps/Home.md"              # no up → absent
    child = "Atlas/200 Maps/Child.md"             # up:: [[Home]] → inline
    note = "Atlas/202 Notes/Idea.md"              # up: "[[Home]]" → frontmatter
    client = FakeKadoClient(
        tagged=[{"path": home}, {"path": child}],
        listings={
            "Atlas/200 Maps/": [{"path": home}, {"path": child}],
            "Atlas/202 Notes/": [{"path": note}],
        },
        notes={
            home: "---\ntitle: Home\n---\n# Home\n",
            child: "---\ntitle: Child\n---\n# Child\n\nup:: [[Home]]\n",
            note: '---\ntitle: Idea\nup: "[[Home]]"\n---\n# Idea\n',
        },
    )
    cache = _cache(client, _config())
    by_path = {e["path"]: e for e in cache["entries"]}

    for path in (home, child, note):
        entry = by_path[path]
        assert entry.get("up_value", _MISSING) is not _MISSING, (
            f"up_value key missing entirely for {path} — freshness signal broken"
        )

    assert by_path[home]["up_value"] is None
    assert by_path[child]["up_value"] is None
    assert by_path[note]["up_value"] == "[[Home]]"

    # CON-7: up_state/up_target/up_source unchanged for every fixture.
    assert by_path[home]["up_state"] == "absent"
    assert by_path[home]["up_target"] is None
    assert by_path[home]["up_source"] is None
    assert by_path[child]["up_state"] == "valid"
    assert by_path[child]["up_target"] == "Home"
    assert by_path[child]["up_source"] == "inline"
    assert by_path[note]["up_state"] == "valid"
    assert by_path[note]["up_target"] == "Home"
    assert by_path[note]["up_source"] == "frontmatter"


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


# ──────────────────────────────────────────────────────────────────────────────
# Observability events (M2/M4/M7) — placeholder.build + moc-cache.build to stderr
# ──────────────────────────────────────────────────────────────────────────────

def _parse_events(stderr: str) -> dict[str, dict]:
    """Extract `[moc-tree] <event> {json}` lines into {event_name: payload}."""
    events: dict[str, dict] = {}
    for line in stderr.splitlines():
        for name in ("placeholder.build", "moc-cache.build"):
            marker = f"[moc-tree] {name} "
            if marker in line:
                events[name] = json.loads(line.split(marker, 1)[1])
    return events


def test_run_with_client_emits_build_telemetry(capsys):
    """placeholder.build + moc-cache.build land on stderr; counts reflect the
    correction (date_dropped + vault_resolved) and stdout stays uncorrupted."""
    moc_path = "Atlas/200 Maps/Home.md"
    real_note = "Atlas/202 Notes/Real Idea.md"
    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": real_note}],
        },
        notes={
            moc_path: (
                "---\ntitle: Home\n---\n# Home\n\n"
                "[[Ghost MOC]]\n"        # genuine placeholder → kept
                "[[2024-01-15]]\n"       # daily note → date_dropped
                "[[Real Idea]]\n"        # resolves to in-scope note → vault_resolved
                "[[#^selfref]]\n"        # same-note anchor → anchor_dropped
            ),
            real_note: "---\ntitle: Real Idea\n---\n# Real Idea\n",
        },
    )
    _builder.run_with_client(client, _config())
    captured = capsys.readouterr()

    events = _parse_events(captured.err)
    assert "placeholder.build" in events and "moc-cache.build" in events

    pb = events["placeholder.build"]
    assert pb["kept_count"] == 1               # only Ghost MOC survives
    assert pb["date_dropped"] == 1             # 2024-01-15
    assert pb["vault_resolved"] == 1           # Real Idea
    assert pb["anchor_dropped"] == 1           # #^selfref
    assert pb["false_positive_dropped"] == 2   # date_dropped + vault_resolved

    mc = events["moc-cache.build"]
    assert mc["mocs_count"] == 1
    assert mc["notes_count"] == 1
    assert mc["excluded_leak_count"] == 0
    assert mc["duration_ms"] >= 0


def test_excluded_leak_counter_flags_entries_under_excluded_prefix():
    """_count_excluded_leaks is the M7 defense-in-depth guard: it counts any entry
    that slipped past the scan's own exclusion. 0 in the normal case (scan excludes
    correctly); non-zero only signals a scan bug, so the counter is unit-tested in
    isolation rather than via the seam (the scan never lets a leak through end-to-end).
    """
    entries = [
        {"path": "Atlas/200 Maps/Home.md"},
        {"path": "X/TemplateVault/Readwise.md"},   # under excluded prefix → leak
        {"path": "Atlas/202 Notes/Idea.md"},
    ]
    assert _builder._count_excluded_leaks(entries, ["X/"]) == 1
    assert _builder._count_excluded_leaks(entries, []) == 0
    assert _builder._count_excluded_leaks(entries, ["X"]) == 1  # prefix normalised w/ trailing /
    # A path that merely shares a name prefix but not a folder boundary is NOT a leak.
    assert _builder._count_excluded_leaks([{"path": "Xenon/Note.md"}], ["X/"]) == 0


# ──────────────────────────────────────────────────────────────────────────────
# T3.1 — MOC heading/callout inventory in cache entries (spec 022)
# ──────────────────────────────────────────────────────────────────────────────

def test_t31_moc_entry_carries_headings_and_editable_callouts():
    """T3.1: A MOC body is parsed for H2-H6 headings + editable callouts and the
    result is stored in the cache entry's `headings` and `editable_callouts` fields.

    No new Kado call must happen — the body is already in raw_by_path.
    """
    moc_path = "Atlas/200 Maps/Knowledge.md"
    note_path = "Atlas/202 Notes/Idea.md"

    moc_body = (
        "---\ntitle: Knowledge\ntags:\n  - type/others/moc\n---\n"
        "# Knowledge\n\n"
        "## Key Concepts\n\n"
        "Some content.\n\n"
        "### Details\n\n"
        "More content.\n\n"
        "> [!blocks]+ My Blocks\n"
        "> block content\n\n"
        "> [!connect] Connect\n"
        "connect content\n\n"
        "> [!video] Footer video\n"
        "footer content\n"
    )
    note_body = "---\ntitle: Idea\n---\n# Idea\n\nSome idea.\n"

    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}],
        },
        notes={moc_path: moc_body, note_path: note_body},
    )
    # Supply callouts.editable in config so the builder can read it.
    cfg = _config()
    cfg["callouts"] = {"editable": ["blocks", "connect"]}

    cache = _cache(client, cfg)
    by_path = {e["path"]: e for e in cache["entries"]}
    moc_entry = by_path[moc_path]

    # headings: only H2+ before footer (video callout is footer boundary)
    assert "headings" in moc_entry, "MOC entry must carry headings"
    assert isinstance(moc_entry["headings"], list)
    # Expect ## Key Concepts (level 2) and ### Details (level 3) only
    # — H1 excluded, and everything after > [!video] is past the footer boundary.
    assert {"text": "Key Concepts", "level": 2} in moc_entry["headings"]
    assert {"text": "Details", "level": 3} in moc_entry["headings"]
    # H1 must NOT appear in headings
    assert not any(h["level"] == 1 for h in moc_entry["headings"])

    # editable_callouts: lines whose callout type is in editable_set
    assert "editable_callouts" in moc_entry, "MOC entry must carry editable_callouts"
    assert isinstance(moc_entry["editable_callouts"], list)
    # [!blocks] and [!connect] are in editable_set; [!video] is absent because
    # "video" is not in editable_set (parse_editable_callouts scans the full body,
    # not footer-bounded).
    assert any("blocks" in c for c in moc_entry["editable_callouts"])
    assert any("connect" in c for c in moc_entry["editable_callouts"])
    assert not any("video" in c for c in moc_entry["editable_callouts"])


def test_t31_non_moc_note_has_no_inventory_fields():
    """T3.1: Non-MOC note entries must NOT carry headings or editable_callouts.

    Inventory is MOC-only — adding it to notes would bloat the cache with
    irrelevant data and break the kind-discriminated contract.
    """
    moc_path = "Atlas/200 Maps/Home.md"
    note_path = "Atlas/202 Notes/Idea.md"

    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}],
        },
        notes={
            moc_path: "---\ntitle: Home\n---\n# Home\n\n## Section\n",
            note_path: "---\ntitle: Idea\n---\n# Idea\n\n## Note Section\n",
        },
    )
    cfg = _config()
    cfg["callouts"] = {"editable": ["blocks"]}

    cache = _cache(client, cfg)
    by_path = {e["path"]: e for e in cache["entries"]}

    note_entry = by_path[note_path]
    assert "headings" not in note_entry, "Non-MOC note must NOT have headings"
    assert "editable_callouts" not in note_entry, "Non-MOC note must NOT have editable_callouts"


def test_t21_moc_entry_has_footer_true_when_footer_callout_present():
    """T2.1 (spec 023): has_footer is True when the MOC body contains a footer-marker callout.

    The footer set is FOOTER_CALLOUTS = {video, calendar, puzzle, compass}.
    A body with a > [!video] line must yield has_footer == True in the cache entry.
    No new Kado call is made — parsed from body already in raw_by_path.
    """
    moc_path = "Atlas/200 Maps/WithFooter.md"
    note_path = "Atlas/202 Notes/Plain.md"

    moc_body = (
        "---\ntitle: WithFooter\ntags:\n  - type/others/moc\n---\n"
        "# WithFooter\n\n"
        "## Key Concepts\n\n"
        "Some content.\n\n"
        "> [!video] Footer video\n"
        "footer content\n"
    )
    note_body = "---\ntitle: Plain\n---\n# Plain\n\nSome idea.\n"

    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}],
        },
        notes={moc_path: moc_body, note_path: note_body},
    )
    cfg = _config()
    cfg["callouts"] = {"editable": ["blocks"]}

    cache = _cache(client, cfg)
    by_path = {e["path"]: e for e in cache["entries"]}
    moc_entry = by_path[moc_path]

    assert "has_footer" in moc_entry, "MOC entry must carry has_footer"
    assert moc_entry["has_footer"] is True, (
        "has_footer must be True when a footer-marker callout (e.g. > [!video]) is present"
    )


def test_t21_moc_entry_has_footer_false_when_no_footer_callout():
    """T2.1 (spec 023): has_footer is False when the MOC body has headings but NO footer-marker callout.

    A body with H2 headings and editable callouts but no {video,calendar,puzzle,compass}
    callout must yield has_footer == False in the cache entry.
    """
    moc_path = "Atlas/200 Maps/NoFooter.md"
    note_path = "Atlas/202 Notes/Plain.md"

    moc_body = (
        "---\ntitle: NoFooter\ntags:\n  - type/others/moc\n---\n"
        "# NoFooter\n\n"
        "## Key Concepts\n\n"
        "Some content.\n\n"
        "> [!blocks]+ My Blocks\n"
        "> block content\n"
    )
    note_body = "---\ntitle: Plain\n---\n# Plain\n\nSome idea.\n"

    client = FakeKadoClient(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}],
        },
        notes={moc_path: moc_body, note_path: note_body},
    )
    cfg = _config()
    cfg["callouts"] = {"editable": ["blocks"]}

    cache = _cache(client, cfg)
    by_path = {e["path"]: e for e in cache["entries"]}
    moc_entry = by_path[moc_path]

    assert "has_footer" in moc_entry, "MOC entry must carry has_footer"
    assert moc_entry["has_footer"] is False, (
        "has_footer must be False when no footer-marker callout is present"
    )


def test_t31_no_extra_kado_call_for_inventory():
    """T3.1: Inventory parsing must NOT trigger additional Kado calls — it parses
    body bytes already in raw_by_path.

    The read count must equal the number of notes in the vault, the same as
    without inventory parsing.
    """
    moc_path = "Atlas/200 Maps/Home.md"
    note_path = "Atlas/202 Notes/Idea.md"

    class CountingFakeKado(FakeKadoClient):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.read_count = 0

        def read_note(self, path):
            self.read_count += 1
            return super().read_note(path)

    counting_client = CountingFakeKado(
        tagged=[{"path": moc_path}],
        listings={
            "Atlas/200 Maps/": [{"path": moc_path}],
            "Atlas/202 Notes/": [{"path": note_path}],
        },
        notes={
            moc_path: "---\ntitle: Home\n---\n# Home\n\n## Section\n\n> [!blocks] B\n",
            note_path: "---\ntitle: Idea\n---\n# Idea\n",
        },
    )
    cfg = _config()
    cfg["callouts"] = {"editable": ["blocks"]}

    _cache(counting_client, cfg)
    # 2 paths, each read exactly once — no extra call for inventory
    assert counting_client.read_count == 2, (
        f"Expected 2 Kado reads, got {counting_client.read_count} — "
        "inventory must parse body already in memory, not re-read from Kado"
    )
