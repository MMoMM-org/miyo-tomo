#!/usr/bin/env python3
# version: 0.2.1
"""test_moc_discovery_folder_home.py — notes a folder-home MOC holds never join a proposal.

A folder-home MOC is an existing MOC whose stem equals the name of the folder it
sits in (e.g. ``Atlas/202 Notes/2821 Quotes/2821 Quotes.md``). Such a note lists
its folder's notes itself (typically a Dataview table), so those notes carry no
``up::`` and look orphaned. Phase 1 drops them from the candidates and
``NodeEligibility`` refuses them as link members.

Live witnesses: 2026-10-29 /moc-propose proposed "Quote (MOC)" over the 63 notes
in ``2821 Quotes/``; 2026-10-30, with a cluster-level check, single quotes still
joined mixed clusters ("Have (MOC)": 4 quotes + 2 code snippets).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.folder_homes import atomic_roots, drop_home_members, folder_homes, home_of  # noqa: E402
from lib.link_members import FOLDER_HOME, OK, NodeEligibility  # noqa: E402
from lib.moc_discovery_phase1 import phase1_select_candidates  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "moc_discovery_folder_home", SCRIPTS_DIR / "moc-discovery.py"
)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery_folder_home"] = moc_discovery
_spec.loader.exec_module(moc_discovery)

NOTES = "Atlas/202 Notes"
QUOTES_DIR = f"{NOTES}/2821 Quotes"
QUOTES_HOME = {"path": f"{QUOTES_DIR}/2821 Quotes.md", "stem": "2821 Quotes",
               "title": "2821 Quotes", "topics": ["quote"]}
NOTES_HOME = {"path": f"{NOTES}/202 Notes.md", "stem": "202 Notes", "title": "202 Notes"}
ATLAS_HOME = {"path": "Atlas/Atlas.md", "stem": "Atlas", "title": "Atlas"}
ROOTS = [f"{NOTES}/"]

# The miyo profile lists every folder-home folder as an atomic-note subdirectory.
MIYO_LIKE_PROFILE = {"concept_defaults": {"atomic_note": {
    "base_path": f"{NOTES}/",
    "subdirectories": [{"path": f"{QUOTES_DIR}/"}, {"path": f"{NOTES}/2611 Code Snippets/"}],
}}}


# ── lib.folder_homes ─────────────────────────────────────────────────────────


def test_moc_named_like_its_folder_is_a_folder_home():
    other = {"path": "Atlas/200 Maps/Quote Collection.md", "title": "Quote Collection"}

    assert folder_homes([QUOTES_HOME, other], ROOTS) == [(QUOTES_DIR, "2821 Quotes")]


def test_atomic_root_and_its_ancestors_are_no_folder_home():
    homes = folder_homes([NOTES_HOME, ATLAS_HOME, QUOTES_HOME], ROOTS)

    assert homes == [(QUOTES_DIR, "2821 Quotes")]


def test_home_of_matches_whole_path_segments_case_insensitively():
    homes = folder_homes([QUOTES_HOME], ROOTS)

    assert home_of(f"{QUOTES_DIR}/q.md", homes) == "2821 Quotes"
    assert home_of(f"{QUOTES_DIR}/German/q.md", homes) == "2821 Quotes"
    assert home_of(f"{QUOTES_DIR.lower()}/q.md", homes) == "2821 Quotes"
    assert home_of(f"{QUOTES_DIR} Archive/q.md", homes) is None
    assert home_of(f"{NOTES}/q.md", homes) is None


def test_atomic_roots_never_take_profile_subdirectories():
    assert atomic_roots(None, MIYO_LIKE_PROFILE) == [f"{NOTES}/"]
    assert atomic_roots({"concepts": {"atomic_note": {"path": "Dots/"}}},
                        MIYO_LIKE_PROFILE) == ["Dots/"]
    assert atomic_roots({"concepts": {"atomic_note": "Cards/"}}, None) == ["Cards/"]


def test_drop_home_members_counts_per_home():
    homes = folder_homes([QUOTES_HOME], ROOTS)
    items = [SimpleNamespace(path=f"{QUOTES_DIR}/a.md"), SimpleNamespace(path=f"{NOTES}/b.md"),
             SimpleNamespace(path=f"{QUOTES_DIR}/c.md")]

    kept, dropped = drop_home_members(items, homes)

    assert [i.path for i in kept] == [f"{NOTES}/b.md"]
    assert dropped == Counter({"2821 Quotes": 2})


# ── Phase 1 ──────────────────────────────────────────────────────────────────


def _note(path: str, topics: list[str]) -> dict:
    stem = path.rpartition("/")[2][:-3]
    return {"path": path, "stem": stem, "kind": "note", "title": stem,
            "topics": topics, "up_state": "absent"}


def _phase1(entries: list[dict], map_notes: list[dict], cap: int = 500):
    cache = {"entries": entries, "map_notes": map_notes}
    return phase1_select_candidates("scan", "", MIYO_LIKE_PROFILE, cache, None,
                                    SimpleNamespace(candidate_cap=cap))


def test_phase1_drops_candidates_a_folder_home_holds():
    entries = [_note(f"{QUOTES_DIR}/q{i}.md", ["quote"]) for i in range(3)]
    entries.append(_note(f"{NOTES}/loose.md", ["quote"]))

    candidates, abort = _phase1(entries, [NOTES_HOME, QUOTES_HOME])

    assert abort is None
    assert [c.path for c in candidates] == [f"{NOTES}/loose.md"]


def test_phase1_dropped_candidates_do_not_count_against_the_cap():
    entries = [_note(f"{QUOTES_DIR}/q{i}.md", ["quote"]) for i in range(5)]
    entries += [_note(f"{NOTES}/n{i}.md", ["x"]) for i in range(2)]

    candidates, abort = _phase1(entries, [QUOTES_HOME], cap=2)

    assert abort is None
    assert len(candidates) == 2


def test_phase1_with_only_folder_home_notes_aborts_zero_candidates():
    entries = [_note(f"{QUOTES_DIR}/q{i}.md", ["quote"]) for i in range(3)]

    assert _phase1(entries, [QUOTES_HOME]) == ([], "zero-candidates")


# ── NodeEligibility ──────────────────────────────────────────────────────────


def test_note_a_folder_home_holds_is_no_link_member():
    quote, loose = f"{QUOTES_DIR}/q.md", f"{NOTES}/loose.md"
    cache = {"entries": [_note(quote, []), _note(loose, [])], "map_notes": [QUOTES_HOME]}
    cfg = {"concepts": {"atomic_note": {"path": f"{NOTES}/"}}}

    eligibility = NodeEligibility(cache, MIYO_LIKE_PROFILE, cfg)

    assert eligibility.check(quote) == (False, FOLDER_HOME)
    assert eligibility.check(loose) == (True, OK)


# ── End-to-end: main() scan ──────────────────────────────────────────────────


def _write_inputs(tmp_path: Path, home_path: str, home_stem: str,
                  atomic_path: str = f"{NOTES}/") -> tuple[Path, Path, Path]:
    cfg = {"profile": "miyo",
           "concepts": {"atomic_note": {"path": atomic_path}},
           "tomo": {"moc_proposal": {"min_notes": 2, "confidence_threshold": 0.10}}}
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text(yaml.dump(cfg), encoding="utf-8")

    home = {"path": home_path, "stem": home_stem, "kind": "moc", "title": home_stem,
            "topics": ["2821", "communication"], "up_state": "valid"}
    notes_home = {**NOTES_HOME, "kind": "moc", "topics": ["notes"], "up_state": "valid"}
    quotes = [_note(f"{QUOTES_DIR}/Saying {i} (Quote).md", ["have"]) for i in range(3)]
    loose = [_note(f"{NOTES}/Habit {i}.md", ["have"]) for i in range(2)]
    cache = {"moc_cache_version": 1,
             "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "ttl_days": 1, "scope_paths": [], "exclude_paths": [],
             "moc_tag": "type/others/moc", "entries": [notes_home, home, *quotes, *loose],
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

    def read_note(self, path: str) -> dict:
        return {"content": "# stub\n"}

    def graph(self, *_a, **_k):
        from lib.kado_client import KadoError

        raise KadoError("graph unavailable in this fake")

    def list_dir(self, path: str, depth: int = 10) -> list[dict]:  # pragma: no cover
        return []


def _main(tmp_path: Path, monkeypatch, home_path: str, home_stem: str, *extra: str,
          atomic_path: str = f"{NOTES}/") -> str:
    config_path, cache_path, squelch_path = _write_inputs(tmp_path, home_path, home_stem,
                                                          atomic_path)
    monkeypatch.setattr(moc_discovery, "_build_kado_client", lambda: _FakeKado())
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = moc_discovery.main(["--config", str(config_path), "--cache", str(cache_path),
                                   "--squelch-state", str(squelch_path), *extra])
    assert code in (0, 1), out.getvalue()
    return out.getvalue()


def _cluster_members(report: dict) -> list[list[str]]:
    return [sorted(i if isinstance(i, str) else i["stem"] for i in c["items"])
            for c in report["topic_clusters"]]


def test_scan_keeps_folder_home_notes_out_of_a_mixed_cluster(tmp_path: Path, monkeypatch):
    report = json.loads(_main(tmp_path, monkeypatch, f"{QUOTES_DIR}/2821 Quotes.md",
                              "2821 Quotes"))

    assert _cluster_members(report) == [["Habit 0", "Habit 1"]]


def test_scan_clusters_the_notes_when_the_moc_is_no_folder_home(tmp_path: Path, monkeypatch):
    report = json.loads(_main(tmp_path, monkeypatch, "Atlas/200 Maps/Sayings Hub.md",
                              "Sayings Hub"))

    assert _cluster_members(report) == [
        ["Habit 0", "Habit 1", "Saying 0 (Quote)", "Saying 1 (Quote)", "Saying 2 (Quote)"]]


def test_emit_phase1_leaves_folder_home_notes_out(tmp_path: Path, monkeypatch):
    emit = tmp_path / "phase1.json"
    _main(tmp_path, monkeypatch, f"{QUOTES_DIR}/2821 Quotes.md", "2821 Quotes",
          "--emit-phase1", str(emit))

    paths = sorted(c["path"] for c in json.loads(emit.read_text())["candidates"])
    assert paths == [f"{NOTES}/Habit 0.md", f"{NOTES}/Habit 1.md"]


def test_scan_takes_the_atomic_root_from_vault_config_over_the_profile(tmp_path: Path,
                                                                        monkeypatch):
    """A user root naming the quotes folder makes 2821 Quotes no folder-home."""
    report = json.loads(_main(tmp_path, monkeypatch, f"{QUOTES_DIR}/2821 Quotes.md",
                              "2821 Quotes", atomic_path=f"{QUOTES_DIR}/"))

    assert _cluster_members(report) == [
        ["Habit 0", "Habit 1", "Saying 0 (Quote)", "Saying 1 (Quote)", "Saying 2 (Quote)"]]


def test_emit_phase1_takes_the_atomic_root_from_vault_config(tmp_path: Path, monkeypatch):
    emit = tmp_path / "phase1.json"
    _main(tmp_path, monkeypatch, f"{QUOTES_DIR}/2821 Quotes.md", "2821 Quotes",
          "--emit-phase1", str(emit), atomic_path=f"{QUOTES_DIR}/")

    assert len(json.loads(emit.read_text())["candidates"]) == 5
