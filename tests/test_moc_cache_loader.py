#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_cache_loader.py — Behavioural tests for lib.moc_cache_loader (T2.1).

The loader sits between moc-discovery and the MOC-structure cache:
  - fresh (now − last_scan ≤ ttl_days)         → load, NO rebuild
  - stale / missing / corrupt                  → rebuild inline, then load
  - persistently unwritable/empty after rebuild → abort "cache-rebuild-failed"
                                                  (NOT a re-scan every run)
  - future last_scan (clock skew)              → treated fresh
  - shim: cache["map_notes"] = entries[kind=="moc"]

Tests inject a fake `rebuilder` (no Kado, no real builder run) and a fixed
`now`, and write cache YAML fixtures to tmp_path.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import moc_cache_loader  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_dict(last_scan: str, *, entries=None, ttl_days=1) -> dict:
    return {
        "moc_cache_version": 1,
        "last_scan": last_scan,
        "ttl_days": ttl_days,
        "scope_paths": ["Atlas/200 Maps/"],
        "exclude_paths": [],
        "moc_tag": "type/others/moc",
        "entries": entries if entries is not None else [
            {"path": "Atlas/200 Maps/Home.md", "stem": "Home", "kind": "moc",
             "title": "Home", "topics": ["x"], "up_state": "absent",
             "up_target": None, "up_source": None, "tags": [],
             "classification": None, "linked_notes": 0},
            {"path": "Atlas/202 Notes/Idea.md", "stem": "Idea", "kind": "note",
             "title": "Idea", "topics": ["y"], "up_state": "valid",
             "up_target": "Home", "up_source": "frontmatter", "tags": []},
        ],
    }


def _write_cache(path: Path, cache: dict) -> None:
    path.write_text(yaml.safe_dump(cache, sort_keys=False), encoding="utf-8")


class _Rebuilder:
    """Records calls; writes a fresh cache to the path on invocation."""

    def __init__(self, *, fresh_cache: dict | None = None, fail: bool = False):
        self.calls = 0
        self._fresh = fresh_cache
        self._fail = fail

    def __call__(self, cache_path: str, config_path: str) -> None:
        self.calls += 1
        if self._fail:
            return  # leaves the file missing/stale — simulates unwritable target
        cache = self._fresh if self._fresh is not None else _cache_dict(_iso(NOW))
        _write_cache(Path(cache_path), cache)


# ──────────────────────────────────────────────────────────────────────────────
# Staleness (pure)
# ──────────────────────────────────────────────────────────────────────────────

def test_fresh_within_ttl_is_not_stale():
    cache = _cache_dict(_iso(NOW - timedelta(hours=12)), ttl_days=1)
    assert moc_cache_loader.is_stale(cache, now=NOW) is False


def test_older_than_ttl_is_stale():
    cache = _cache_dict(_iso(NOW - timedelta(days=2)), ttl_days=1)
    assert moc_cache_loader.is_stale(cache, now=NOW) is True


def test_future_last_scan_is_fresh():
    """Clock skew: a last_scan in the future is treated as fresh (SDD)."""
    cache = _cache_dict(_iso(NOW + timedelta(days=5)), ttl_days=1)
    assert moc_cache_loader.is_stale(cache, now=NOW) is False


def test_missing_last_scan_is_stale():
    cache = _cache_dict(_iso(NOW))
    del cache["last_scan"]
    assert moc_cache_loader.is_stale(cache, now=NOW) is True


def test_corrupt_last_scan_is_stale():
    cache = _cache_dict("not-a-timestamp")
    assert moc_cache_loader.is_stale(cache, now=NOW) is True


def test_none_cache_is_stale():
    assert moc_cache_loader.is_stale(None, now=NOW) is True


# ──────────────────────────────────────────────────────────────────────────────
# Shim
# ──────────────────────────────────────────────────────────────────────────────

def test_shim_projects_moc_entries_to_map_notes():
    cache = _cache_dict(_iso(NOW))
    shimmed = moc_cache_loader.apply_shim(cache)
    assert "map_notes" in shimmed
    assert [m["path"] for m in shimmed["map_notes"]] == ["Atlas/200 Maps/Home.md"]
    assert all(m["kind"] == "moc" for m in shimmed["map_notes"])


def test_shim_empty_entries_yields_empty_map_notes():
    cache = _cache_dict(_iso(NOW), entries=[])
    shimmed = moc_cache_loader.apply_shim(cache)
    assert shimmed["map_notes"] == []


# ──────────────────────────────────────────────────────────────────────────────
# load_moc_cache — orchestration
# ──────────────────────────────────────────────────────────────────────────────

def test_fresh_cache_loads_without_rebuild(tmp_path):
    cache_path = tmp_path / "moc-structure-cache.yaml"
    _write_cache(cache_path, _cache_dict(_iso(NOW - timedelta(hours=1))))
    rebuilder = _Rebuilder()

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort is None
    assert rebuilder.calls == 0
    assert cache["map_notes"]  # shim applied


def test_fresh_cache_with_zero_mocs_returns_cache_empty_no_rebuild(tmp_path):
    """A FRESH cache carrying no kind==moc entries is an empty vault → cache-empty,
    WITHOUT a rebuild (rebuilding a fresh cache would not add MOCs). Preserves
    moc-discovery's original validate_cache_loaded contract."""
    cache_path = tmp_path / "moc-structure-cache.yaml"
    # Fresh, but only a note entry — no MOCs.
    note_only = _cache_dict(_iso(NOW), entries=[
        {"path": "Atlas/202 Notes/Idea.md", "stem": "Idea", "kind": "note",
         "title": "Idea", "topics": [], "up_state": "absent",
         "up_target": None, "up_source": None, "tags": []},
    ])
    _write_cache(cache_path, note_only)
    rebuilder = _Rebuilder()

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort == "cache-empty"
    assert rebuilder.calls == 0  # fresh → no rebuild
    assert cache is None


def test_stale_cache_triggers_inline_rebuild_then_loads(tmp_path):
    cache_path = tmp_path / "moc-structure-cache.yaml"
    _write_cache(cache_path, _cache_dict(_iso(NOW - timedelta(days=3))))
    rebuilder = _Rebuilder(fresh_cache=_cache_dict(_iso(NOW)))

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort is None
    assert rebuilder.calls == 1
    assert cache["map_notes"]


def test_missing_cache_triggers_rebuild_then_loads(tmp_path):
    cache_path = tmp_path / "moc-structure-cache.yaml"  # does not exist
    rebuilder = _Rebuilder(fresh_cache=_cache_dict(_iso(NOW)))

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort is None
    assert rebuilder.calls == 1
    assert cache["map_notes"]


def test_corrupt_cache_triggers_rebuild_then_loads(tmp_path):
    cache_path = tmp_path / "moc-structure-cache.yaml"
    cache_path.write_text("{{ this is not: valid yaml ][", encoding="utf-8")
    rebuilder = _Rebuilder(fresh_cache=_cache_dict(_iso(NOW)))

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort is None
    assert rebuilder.calls == 1
    assert cache["map_notes"]


def test_persistently_unwritable_after_rebuild_aborts_not_rescan(tmp_path):
    """The builder ran but the cache is still missing/stale → abort
    cache-rebuild-failed (NOT a re-scan loop every run)."""
    cache_path = tmp_path / "moc-structure-cache.yaml"  # missing
    rebuilder = _Rebuilder(fail=True)  # never writes the file

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort == "cache-rebuild-failed"
    # exactly ONE rebuild attempt — not a re-scan every run
    assert rebuilder.calls == 1
    assert cache is None


def test_empty_entries_after_rebuild_aborts(tmp_path):
    """A rebuilt-but-empty cache (zero MOCs) → cache-rebuild-failed (no usable
    map_notes), not an infinite rebuild."""
    cache_path = tmp_path / "moc-structure-cache.yaml"
    rebuilder = _Rebuilder(fresh_cache=_cache_dict(_iso(NOW), entries=[]))

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort == "cache-rebuild-failed"
    assert rebuilder.calls == 1


def test_rebuild_attempted_exactly_once_even_when_still_stale(tmp_path):
    """Guard against the re-scan-every-run trap: even if the rebuilder writes a
    STILL-stale cache, the loader rebuilds once then aborts — it does not loop."""
    cache_path = tmp_path / "moc-structure-cache.yaml"
    _write_cache(cache_path, _cache_dict(_iso(NOW - timedelta(days=10))))
    # rebuilder writes another stale cache (simulates a broken clock/builder)
    rebuilder = _Rebuilder(fresh_cache=_cache_dict(_iso(NOW - timedelta(days=9))))

    cache, abort = moc_cache_loader.load_moc_cache(
        str(cache_path), "config/vault-config.yaml", now=NOW, rebuilder=rebuilder
    )
    assert abort == "cache-rebuild-failed"
    assert rebuilder.calls == 1
