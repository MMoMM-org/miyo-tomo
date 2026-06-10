#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_propose_cluster_no_orphan_section.py — cluster proposal-doc has no note-orphan section.

SDD ADR-13 D1 + PRD Feature 8 AC1:
  /moc-propose (scan and scoped cluster runs) must produce NO per-note orphan
  section (## Orphan Notes & MOCs / ### Oxx) in the rendered proposal-doc.
  The orphan renderer stays; it is used ONLY by check:moc-uplinks (regression
  guard in this file).

Two categories:

  cluster_mode — scan or scoped DiscoveryReport: orphan section MUST be absent.
  check_mode   — check-moc-uplinks report: orphan section MUST still be present
                 (regression guard — this path must not regress).
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

# ── Load moc-discovery ────────────────────────────────────────────────────────

_disc_path = SCRIPTS_DIR / "moc-discovery.py"
_disc_spec = importlib.util.spec_from_file_location("moc_discovery_cluster_orphan", _disc_path)
_disc_mod = importlib.util.module_from_spec(_disc_spec)
assert _disc_spec.loader is not None
sys.modules["moc_discovery_cluster_orphan"] = _disc_mod
_disc_spec.loader.exec_module(_disc_mod)

# ── Load suggestions-reducer ──────────────────────────────────────────────────

_red_path = SCRIPTS_DIR / "suggestions-reducer.py"
_red_spec = importlib.util.spec_from_file_location("suggestions_reducer_cluster_orphan", _red_path)
_red_mod = importlib.util.module_from_spec(_red_spec)
assert _red_spec.loader is not None
sys.modules["suggestions_reducer_cluster_orphan"] = _red_mod
_red_spec.loader.exec_module(_red_mod)

render_moc_proposal_doc = _red_mod.render_moc_proposal_doc  # type: ignore[attr-defined]


# ── Config / cache fixtures ───────────────────────────────────────────────────


class _Cfg:
    max_results: int = 5


def _write_config(tmp_path: Path) -> Path:
    cfg = {"profile": "miyo", "tomo": {"moc_proposal": {"min_notes": 2, "confidence_threshold": 0.10}}}
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
        "placeholder_links": [],
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
    """A note orphan with a UNIQUE topic under the miyo atomic-note prefix."""
    return {
        "path": f"Atlas/202 Notes/orphan_{i:03d}.md",
        "stem": f"orphan_{i:03d}",
        "kind": "note",
        "title": f"orphan_{i:03d}",
        "topics": [f"uniquetopic{i:03d}"],
        "up_state": "absent",
    }


def _orphan_moc(stem: str) -> dict:
    return {
        "path": f"Atlas/200 Maps/{stem}.md",
        "stem": stem,
        "kind": "moc",
        "title": stem,
        "topics": ["pkm"],
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


# ── Helper: build a minimal cluster-mode DiscoveryReport for the reducer ──────


def _cluster_report(*, mode: str = "scan", orphan_suggestions: list[dict] | None = None) -> dict:
    """Minimal DiscoveryReport with cluster fields and optional orphan_suggestions."""
    return {
        "schema_version": "1",
        "run_id": "test-cluster-orphan",
        "mode": mode,
        "trigger_arg": "",
        "profile": "miyo",
        "candidates_total": 0,
        "candidates_after_prefilter": 0,
        "candidates_capped": False,
        "candidates": [],
        "topic_clusters": [],
        "parent_options_per_cluster": {},
        "duplicates_skipped": [],
        "squelched": [],
        "orphan_suggestions": orphan_suggestions or [],
        "orphan_total": len(orphan_suggestions or []),
        "orphan_overflow": 0,
        "abort_reason": None,
        "abort_message": None,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLUSTER MODE TESTS — orphan section must be ABSENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_scan_proposal_doc_has_no_orphan_section():
    """PRD Feature 8 AC1: A scan-mode DiscoveryReport renders no ## Orphan Notes & MOCs.

    After D1 the cluster path no longer populates orphan_suggestions, so the
    reducer gate (if orphan_suggestions:) is never triggered and the orphan
    section is absent from the proposal-doc.
    """
    report = _cluster_report(mode="scan", orphan_suggestions=[])
    _filename, body = render_moc_proposal_doc(report, _Cfg())

    assert "## Orphan Notes & MOCs" not in body, (
        "Cluster-mode proposal-doc must contain NO ## Orphan Notes & MOCs section "
        f"(ADR-13 D1). Found in:\n{body}"
    )
    assert "### O" not in body, (
        "Cluster-mode proposal-doc must contain NO ### Oxx entry "
        f"(ADR-13 D1). Found in:\n{body}"
    )


def test_scoped_proposal_doc_has_no_orphan_section():
    """PRD Feature 8 AC1: A scoped (tag-mode) cluster run also renders no orphan section."""
    report = _cluster_report(mode="tag", orphan_suggestions=[])
    _filename, body = render_moc_proposal_doc(report, _Cfg())

    assert "## Orphan Notes & MOCs" not in body, (
        "Scoped cluster-mode (tag) proposal-doc must contain NO ## Orphan Notes & MOCs. "
        f"Found in:\n{body}"
    )
    assert "### O" not in body, (
        f"Scoped cluster-mode (tag) must have no ### Oxx entries. Found in:\n{body}"
    )


def test_scan_discovery_report_emits_empty_orphan_suggestions(tmp_path: Path, monkeypatch):
    """End-to-end: main() scan path produces orphan_suggestions=[] after D1 change.

    After D1, the cluster path in _run_pipeline no longer calls
    emit_orphan_suggestions(kinds=("note",)) and the report fields
    orphan_suggestions / orphan_total / orphan_overflow are empty/zero.

    The cache requires at least one kind==moc entry so the shim populates
    map_notes and the pipeline proceeds past the cache-empty guard.
    """
    config_path = _write_config(tmp_path)
    # Include a real MOC entry (required for map_notes shim) and note orphans
    # (to prove the note-orphan pass no longer runs in cluster mode).
    entries = [
        _orphan_moc("SomeParentMOC"),  # satisfies the map_notes shim
        _note_orphan(1),
        _note_orphan(2),
    ]
    entries[0]["up_state"] = "valid"  # not an orphan — avoids scan picking it up
    cache_path = _write_cache(tmp_path, entries)
    squelch_path = _write_squelch(tmp_path)

    monkeypatch.setattr(_disc_mod, "_build_kado_client", lambda: _NoUpKado())

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = _disc_mod.main(
            [
                "--config", str(config_path),
                "--cache", str(cache_path),
                "--squelch-state", str(squelch_path),
            ]
        )
    assert exit_code in (0, 1), captured.getvalue()
    report = json.loads(captured.getvalue())

    assert report["mode"] == "scan"
    assert report["orphan_suggestions"] == [], (
        f"Scan report must have orphan_suggestions=[]; got {report['orphan_suggestions']!r}"
    )
    assert report["orphan_total"] == 0, (
        f"Scan report must have orphan_total=0; got {report['orphan_total']!r}"
    )
    assert report["orphan_overflow"] == 0, (
        f"Scan report must have orphan_overflow=0; got {report['orphan_overflow']!r}"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REGRESSION GUARD — check-moc-uplinks MUST still render its orphan section
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_check_mode_proposal_doc_renders_moc_orphan_section():
    """REGRESSION GUARD: check-moc-uplinks report renders its MOC orphan section.

    The orphan renderer (_render_orphan_section) must NOT be removed; it is
    still the only way check-moc-uplinks surfaces its MOC-orphan audit.
    """
    report = _cluster_report(mode="check-moc-uplinks")
    report["orphan_suggestions"] = [
        {
            "stem": "OrphanMap",
            "path": "Atlas/200 Maps/OrphanMap.md",
            "kind": "moc",
            "mode": "create_new",
            "candidates": [],
            "reason": "No parent MOC.",
        }
    ]
    report["orphan_total"] = 1
    _filename, body = render_moc_proposal_doc(report, _Cfg())

    assert "## MOC Uplink Check" in body, (
        "check-moc-uplinks report must render ## MOC Uplink Check section. "
        f"Not found in:\n{body}"
    )
    assert "### O01" in body, (
        f"check-moc-uplinks report must render ### O01 orphan entry. Not found in:\n{body}"
    )


def test_check_moc_uplinks_pipeline_populates_moc_orphan_suggestions(tmp_path: Path):
    """REGRESSION GUARD: --check-moc-uplinks main() path populates orphan_suggestions.

    The check path (_run_moc_uplink_check) must continue to call
    emit_orphan_suggestions and _cap_orphans for kind==moc entries — this
    is the only path that produces MOC-orphan suggestions.
    """
    config_path = _write_config(tmp_path)
    entries = [
        _orphan_moc("OrphanMapA"),
        _orphan_moc("OrphanMapB"),
        _note_orphan(1),  # note orphan — must NOT appear in check mode
    ]
    cache_path = _write_cache(tmp_path, entries)
    squelch_path = _write_squelch(tmp_path)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = _disc_mod.main(
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
    assert len(report["orphan_suggestions"]) == 2, (
        f"check-moc-uplinks must emit 2 MOC orphans; got {report['orphan_suggestions']!r}"
    )
    kinds = {s["kind"] for s in report["orphan_suggestions"]}
    assert kinds == {"moc"}, f"check mode must emit only MOC orphans; got {kinds}"
