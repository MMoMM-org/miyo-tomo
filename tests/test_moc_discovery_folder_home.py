#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_folder_home.py — Phase 6 skips clusters a folder-home MOC already covers.

A folder-home MOC is an existing MOC whose stem equals the name of the folder it
sits in (e.g. ``Atlas/202 Notes/2821 Quotes/2821 Quotes.md``). Such a note lists
its folder's notes itself (typically a Dataview table), so those notes carry no
``up::`` and look orphaned. A proposed cluster whose members sit mostly inside
that folder duplicates the folder-home MOC and must be skipped with
``reason="folder-home"``.

Live witness (2026-10-29): /moc-propose proposed "Quote (MOC)" over the 63
notes in ``2821 Quotes/``; title and topic overlap (0.22) both missed it.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "moc_discovery_folder_home", SCRIPTS_DIR / "moc-discovery.py"
)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery_folder_home"] = moc_discovery
_spec.loader.exec_module(moc_discovery)

QUOTES_DIR = "Atlas/202 Notes/2821 Quotes"
QUOTES_HOME = {
    "path": f"{QUOTES_DIR}/2821 Quotes.md",
    "stem": "2821 Quotes",
    "title": "2821 Quotes",
    "topics": ["2821 quotes", "2821", "communication", "quote", "quotes"],
}


class _Config:
    pass


def _quote_cluster(stems: list[str]) -> dict:
    return {"topic": "quote", "items": list(stems), "parent": "", "tags": [],
            "title": "Quote (MOC)"}


def _run(cluster: dict, map_notes: list[dict], member_paths: dict[str, str] | None,
         container_roots: list[str] | None = None):
    return moc_discovery.phase6_dedupe(
        [cluster], {"map_notes": map_notes}, {}, _Config(),
        member_paths=member_paths, container_roots=container_roots,
    )


# ── Unit: phase6_dedupe ──────────────────────────────────────────────────────


def test_cluster_inside_folder_home_moc_is_skipped():
    stems = [f"q{i}" for i in range(5)]
    paths = {s: f"{QUOTES_DIR}/{s}.md" for s in stems}

    kept, dups, sq = _run(_quote_cluster(stems), [QUOTES_HOME], paths)

    assert kept == []
    assert sq == []
    assert dups == [{"cluster_id": "MOC01", "reason": "folder-home",
                     "existing_moc": "2821 Quotes"}]


def test_members_in_subfolders_of_the_folder_home_count_as_inside():
    stems = [f"q{i}" for i in range(4)]
    paths = {s: f"{QUOTES_DIR}/German/{s}.md" for s in stems}

    kept, dups, _ = _run(_quote_cluster(stems), [QUOTES_HOME], paths)

    assert kept == []
    assert dups[0]["reason"] == "folder-home"


def test_cluster_mostly_outside_the_folder_is_kept():
    stems = [f"q{i}" for i in range(5)]
    paths = {s: f"{QUOTES_DIR}/{s}.md" for s in stems[:3]}
    paths.update({s: f"Atlas/202 Notes/{s}.md" for s in stems[3:]})  # 3/5 = 0.60

    kept, dups, _ = _run(_quote_cluster(stems), [QUOTES_HOME], paths)

    assert len(kept) == 1
    assert dups == []


def test_moc_whose_stem_differs_from_its_folder_is_not_a_folder_home():
    stems = [f"q{i}" for i in range(5)]
    paths = {s: f"Atlas/200 Maps/{s}.md" for s in stems}
    maps_moc = {"path": "Atlas/200 Maps/Quote Collection.md", "stem": "Quote Collection",
                "title": "Quote Collection", "topics": ["collection"]}

    kept, dups, _ = _run(_quote_cluster(stems), [maps_moc], paths)

    assert len(kept) == 1
    assert dups == []


def test_folder_prefix_must_match_a_whole_path_segment():
    stems = [f"q{i}" for i in range(5)]
    paths = {s: f"{QUOTES_DIR} Archive/{s}.md" for s in stems}

    kept, dups, _ = _run(_quote_cluster(stems), [QUOTES_HOME], paths)

    assert len(kept) == 1
    assert dups == []


def test_without_member_paths_the_check_does_not_fire():
    stems = [f"q{i}" for i in range(5)]

    kept, dups, _ = _run(_quote_cluster(stems), [QUOTES_HOME], None)

    assert len(kept) == 1
    assert dups == []


def test_container_root_and_its_ancestors_are_no_folder_home():
    """``202 Notes`` and ``Atlas`` hold every atomic note — never a folder-home."""
    stems = [f"n{i}" for i in range(5)]
    paths = {s: f"Atlas/202 Notes/{s}.md" for s in stems}
    notes_home = {"path": "Atlas/202 Notes/202 Notes.md", "title": "202 Notes", "topics": []}
    atlas_home = {"path": "Atlas/Atlas.md", "title": "Atlas", "topics": []}

    kept, dups, _ = _run(_quote_cluster(stems), [notes_home, atlas_home], paths,
                         container_roots=["Atlas/202 Notes/", "Atlas/200 Maps/"])

    assert len(kept) == 1
    assert dups == []


def test_folder_home_below_a_container_root_still_counts():
    stems = [f"q{i}" for i in range(5)]
    paths = {s: f"{QUOTES_DIR}/{s}.md" for s in stems}
    notes_home = {"path": "Atlas/202 Notes/202 Notes.md", "title": "202 Notes", "topics": []}

    kept, dups, _ = _run(_quote_cluster(stems), [notes_home, QUOTES_HOME], paths,
                         container_roots=["Atlas/202 Notes/"])

    assert kept == []
    assert dups[0]["existing_moc"] == "2821 Quotes"


# ── End-to-end: main() scan threads the candidate paths into Phase 6 ─────────


def _write_inputs(tmp_path: Path, home_path: str, home_stem: str) -> tuple[Path, Path, Path]:
    cfg = {"profile": "miyo",
           "concepts": {"atomic_note": {"path": "Atlas/202 Notes/"}},
           "tomo": {"moc_proposal": {"min_notes": 2, "confidence_threshold": 0.10}}}
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text(yaml.dump(cfg), encoding="utf-8")

    home = {"path": home_path, "stem": home_stem, "kind": "moc", "title": home_stem,
            "topics": ["2821", "communication", "quote", "quotes"], "up_state": "valid"}
    notes_home = {"path": "Atlas/202 Notes/202 Notes.md", "stem": "202 Notes",
                  "kind": "moc", "title": "202 Notes", "topics": ["notes"],
                  "up_state": "valid"}
    notes = [
        {"path": f"{QUOTES_DIR}/Saying {i} (Quote).md", "stem": f"Saying {i} (Quote)",
         "kind": "note", "title": f"Saying {i} (Quote)", "topics": ["quote"],
         "up_state": "absent"}
        for i in range(3)
    ]
    cache = {"moc_cache_version": 1,
             "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "ttl_days": 1, "scope_paths": [], "exclude_paths": [],
             "moc_tag": "type/others/moc", "entries": [notes_home, home, *notes],
             "placeholder_links": []}
    cache_path = tmp_path / "moc-structure-cache.yaml"
    cache_path.write_text(yaml.dump(cache, allow_unicode=True), encoding="utf-8")

    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        json.dumps({"schema_version": "1", "last_run_id": "", "rejections": []}),
        encoding="utf-8")
    return config_path, cache_path, squelch_path


class _FakeKado:
    attempt_count = 0
    attempt_gate = None
    min_interval = 0.0

    def search_by_tag(self, query: str) -> list[dict]:  # pragma: no cover
        return []

    def read_note(self, path: str) -> dict:  # pragma: no cover
        return {"content": "# stub\n"}

    def graph(self, *_a, **_k):
        from lib.kado_client import KadoError

        raise KadoError("graph unavailable in this fake")

    def list_dir(self, path: str, depth: int = 10) -> list[dict]:  # pragma: no cover
        return []


def _scan(tmp_path: Path, monkeypatch, home_path: str, home_stem: str) -> dict:
    config_path, cache_path, squelch_path = _write_inputs(tmp_path, home_path, home_stem)
    monkeypatch.setattr(moc_discovery, "_build_kado_client", lambda: _FakeKado())
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = moc_discovery.main(["--config", str(config_path), "--cache", str(cache_path),
                                   "--squelch-state", str(squelch_path)])
    assert code in (0, 1), out.getvalue()
    return json.loads(out.getvalue())


def test_scan_skips_quote_cluster_covered_by_folder_home(tmp_path: Path, monkeypatch):
    report = _scan(tmp_path, monkeypatch, f"{QUOTES_DIR}/2821 Quotes.md", "2821 Quotes")

    assert report["topic_clusters"] == []
    assert [(d["reason"], d["existing_moc"]) for d in report["duplicates_skipped"]] == [
        ("folder-home", "2821 Quotes")]


def test_scan_proposes_quote_cluster_when_the_moc_is_no_folder_home(tmp_path: Path, monkeypatch):
    report = _scan(tmp_path, monkeypatch, "Atlas/200 Maps/Sayings Hub.md", "Sayings Hub")

    assert [c["topic_keywords"][0] for c in report["topic_clusters"]] == ["quote"]
    assert report["duplicates_skipped"] == []
