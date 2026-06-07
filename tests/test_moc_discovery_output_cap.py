#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_discovery_output_cap.py — orphan output shaping (spec 021 T6.3 + T7.5).

ADR-12 + ADR-13 D1:
  - _cap_orphans and emit_orphan_suggestions remain in scope (used by check path).
  - `--check-moc-uplinks` runs the orphan pass over kind==moc only, skipping the
    clustering pipeline.
  - Default scan (cluster mode) emits NO orphan suggestions (T7.5 D1).
    The note-orphan pass was removed from _run_pipeline; orphan_suggestions is []
    for all cluster runs. Interactive note-orphan handling deferred to #30.

Covers:
  - _cap_orphans: truncation + total/overflow counts (unit)
  - _run_moc_uplink_check: MOC-only pass, capped (unit, no Kado)
  - main() default scan: report has orphan_suggestions=[] (T7.5 D1)
  - main() --check-moc-uplinks: MOC suggestions, no clustering
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
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
_moc_disc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = _moc_disc
_spec.loader.exec_module(_moc_disc)

_BASE_PATH = "Atlas/202 Notes/"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _write_config(tmp_path: Path, *, orphan_display_cap: int | None = None) -> Path:
    moc_proposal: dict = {"min_notes": 2, "confidence_threshold": 0.10}
    if orphan_display_cap is not None:
        moc_proposal["orphan_display_cap"] = orphan_display_cap
    cfg = {"profile": "miyo", "tomo": {"moc_proposal": moc_proposal}}
    p = tmp_path / "vault-config.yaml"
    p.write_text(yaml.dump(cfg, allow_unicode=True), encoding="utf-8")
    return p


def _write_cache(tmp_path: Path, entries: list[dict]) -> Path:
    cache = {
        "moc_cache_version": 1,
        "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ttl_days": 1,
        "scope_paths": [],
        "exclude_paths": [],
        "moc_tag": "type/others/moc",
        "entries": entries,
        "placeholder_mocs": [],
    }
    p = tmp_path / "moc-structure-cache.yaml"
    p.write_text(yaml.dump(cache, allow_unicode=True), encoding="utf-8")
    return p


def _write_squelch(tmp_path: Path) -> Path:
    p = tmp_path / "moc-squelch.json"
    p.write_text(
        json.dumps({"schema_version": "1", "last_run_id": "", "rejections": []}),
        encoding="utf-8",
    )
    return p


def _note_orphan(i: int) -> dict:
    """A note orphan with a UNIQUE topic (so no cluster forms — isolates the
    orphan pass) under the miyo atomic-note prefix (survives the pre-filter)."""
    return {
        "path": f"{_BASE_PATH}orphan_{i:03d}.md",
        "stem": f"orphan_{i:03d}",
        "kind": "note",
        "title": f"orphan_{i:03d}",
        "topics": [f"uniquetopic{i:03d}"],
        "up_state": "absent",
    }


def _orphan_moc(stem: str, topics: list[str]) -> dict:
    return {
        "path": f"Atlas/200 Maps/{stem}.md",
        "stem": stem,
        "kind": "moc",
        "title": stem,
        "topics": topics,
        "up_state": "absent",
    }


class _NoUpKado:
    """Fake Kado: read_note returns content without up:: (no-op for this suite)."""

    def search_by_tag(self, query: str) -> list[dict]:  # pragma: no cover
        return []

    def read_note(self, path: str) -> dict:  # pragma: no cover
        return {"content": "# stub\nno up here\n"}

    def list_dir(self, path: str, depth: int = 10) -> list[dict]:  # pragma: no cover
        return []


# ── Unit: _cap_orphans ────────────────────────────────────────────────────────


def test_cap_orphans_truncates_and_counts():
    items = [{"stem": f"s{i}"} for i in range(60)]
    kept, total, overflow = _moc_disc._cap_orphans(items, 50)
    assert len(kept) == 50
    assert total == 60
    assert overflow == 10
    assert kept == items[:50], "must keep the head (most-actionable first)"


def test_cap_orphans_under_cap_no_overflow():
    items = [{"stem": f"s{i}"} for i in range(10)]
    kept, total, overflow = _moc_disc._cap_orphans(items, 50)
    assert kept == items
    assert total == 10
    assert overflow == 0


def test_cap_orphans_exactly_at_cap_no_overflow():
    items = [{"stem": f"s{i}"} for i in range(50)]
    kept, total, overflow = _moc_disc._cap_orphans(items, 50)
    assert len(kept) == 50
    assert overflow == 0


# ── Unit: _run_moc_uplink_check (no Kado) ─────────────────────────────────────


def test_run_moc_uplink_check_moc_only(tmp_path: Path):
    config_path = _write_config(tmp_path)
    cache = {
        "entries": [
            _orphan_moc("OrphanMapA", ["pkm"]),
            _orphan_moc("OrphanMapB", ["food"]),
            _note_orphan(1),  # a note orphan — must be ignored by check mode
        ]
    }
    report = _moc_disc._run_moc_uplink_check(cache, config_path, "miyo")
    assert report["mode"] == "check-moc-uplinks"
    kinds = {s["kind"] for s in report["orphan_suggestions"]}
    assert kinds == {"moc"}, f"check mode must emit MOC orphans only; got {kinds}"
    stems = {s["stem"] for s in report["orphan_suggestions"]}
    assert stems == {"OrphanMapA", "OrphanMapB"}
    assert report["orphan_total"] == 2
    assert report["orphan_overflow"] == 0


# ── main(): default scan (cluster mode) has no orphan suggestions (T7.5 D1) ───


def test_default_scan_has_no_orphan_suggestions(tmp_path: Path, monkeypatch):
    """ADR-13 D1: the cluster path no longer produces orphan suggestions.

    Note orphans in the cache are ignored by the scan pipeline (T7.5).
    orphan_suggestions, orphan_total, orphan_overflow are all empty/zero.
    Interactive note-orphan handling is deferred to Garden-Audit (#30).
    """
    config_path = _write_config(tmp_path, orphan_display_cap=50)
    entries = [_note_orphan(i) for i in range(60)]
    entries.append(_orphan_moc("OrphanMap", ["pkm"]))  # satisfies map_notes shim
    cache_path = _write_cache(tmp_path, entries)
    squelch_path = _write_squelch(tmp_path)

    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: _NoUpKado())

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = _moc_disc.main(
            [
                "--config", str(config_path),
                "--cache", str(cache_path),
                "--squelch-state", str(squelch_path),
            ]
        )
    assert exit_code in (0, 1), captured.getvalue()
    report = json.loads(captured.getvalue())

    assert report["mode"] == "scan"
    # T7.5 D1: cluster path no longer populates orphan fields.
    assert report["orphan_suggestions"] == [], (
        f"scan (cluster mode) must have no orphan_suggestions; got {report['orphan_suggestions']!r}"
    )
    assert report["orphan_total"] == 0, (
        f"scan (cluster mode) must have orphan_total=0; got {report['orphan_total']!r}"
    )
    assert report["orphan_overflow"] == 0, (
        f"scan (cluster mode) must have orphan_overflow=0; got {report['orphan_overflow']!r}"
    )


# ── main(): --check-moc-uplinks runs MOC pass only, no clustering ──────────────


def test_check_moc_uplinks_skips_clustering(tmp_path: Path):
    config_path = _write_config(tmp_path)
    entries = [
        _orphan_moc("OrphanMapA", ["pkm", "notes"]),
        _orphan_moc("OrphanMapB", ["food", "recipes"]),
        _note_orphan(1),
        _note_orphan(2),
    ]
    cache_path = _write_cache(tmp_path, entries)
    squelch_path = _write_squelch(tmp_path)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = _moc_disc.main(
            [
                "--check-moc-uplinks",
                "--config", str(config_path),
                "--cache", str(cache_path),
                "--squelch-state", str(squelch_path),
            ]
        )
    assert exit_code == 0, captured.getvalue()
    report = json.loads(captured.getvalue())

    assert report["mode"] == "check-moc-uplinks"
    assert report["topic_clusters"] == [], "check mode must skip the clustering pipeline"
    kinds = {s["kind"] for s in report["orphan_suggestions"]}
    assert kinds == {"moc"}, f"check mode emits MOC orphans only; got {kinds}"
