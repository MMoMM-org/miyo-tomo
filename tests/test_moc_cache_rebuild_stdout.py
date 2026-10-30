#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_cache_rebuild_stdout.py — an inline cache rebuild never writes to the caller's stdout.

`moc-tree-builder.run()` prints its JSON feed (~70 KB live) to stdout. The
loader runs it in-process when the cache is stale, so a report-emitting
`moc-discovery.py` run with a stale cache emitted the feed followed by the
report, which is invalid JSON whether stdout or `--output PATH` carries it.
Seen live 2026-10-30 after deleting the instance cache: the feed landed in the
Pass 1 tool output.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import moc_cache_loader  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "moc_discovery_rebuild_stdout", SCRIPTS_DIR / "moc-discovery.py"
)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery_rebuild_stdout"] = moc_discovery
_spec.loader.exec_module(moc_discovery)

NOTES = "Atlas/202 Notes"
FEED = '{"map_notes": [{"path": "noise.md"}]}'


def _fresh_cache(path: Path) -> None:
    def note(i: int) -> dict:
        return {"path": f"{NOTES}/Note {i}.md", "stem": f"Note {i}", "kind": "note",
                "title": f"Note {i}", "topics": ["alpha"], "up_state": "absent"}

    moc = {"path": "Atlas/200 Maps/Hub.md", "stem": "Hub", "kind": "moc", "title": "Hub",
           "topics": ["hub"], "up_state": "valid"}
    cache = {"moc_cache_version": 1,
             "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "ttl_days": 1, "scope_paths": [], "exclude_paths": [],
             "moc_tag": "type/others/moc", "entries": [moc, *[note(i) for i in range(3)]],
             "placeholder_links": []}
    path.write_text(yaml.dump(cache), encoding="utf-8")


def _printing_rebuilder(source: Path):
    def rebuild(cache_path: str, _config_path: str) -> None:
        print(FEED)
        shutil.copy(source, cache_path)

    return rebuild


def test_load_moc_cache_keeps_the_builder_feed_off_stdout(tmp_path: Path, capsys):
    source = tmp_path / "fresh.yaml"
    _fresh_cache(source)

    cache, abort = moc_cache_loader.load_moc_cache(
        str(tmp_path / "cache.yaml"), str(tmp_path / "cfg.yaml"),
        rebuilder=_printing_rebuilder(source),
    )

    assert abort is None and cache is not None
    assert capsys.readouterr().out == ""


def test_report_run_with_a_stale_cache_writes_valid_json(tmp_path: Path, monkeypatch):
    source = tmp_path / "fresh.yaml"
    _fresh_cache(source)
    cfg = {"profile": "miyo", "concepts": {"atomic_note": {"path": f"{NOTES}/"}},
           "tomo": {"moc_proposal": {"min_notes": 2, "confidence_threshold": 0.10}}}
    (tmp_path / "cfg.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
    (tmp_path / "squelch.json").write_text(
        json.dumps({"schema_version": "1", "last_run_id": "", "rejections": []}),
        encoding="utf-8")
    monkeypatch.setattr(moc_cache_loader, "_default_rebuilder", _printing_rebuilder(source))

    class _FakeKado:
        attempt_count = 0
        attempt_gate = None
        min_interval = 0.0

        def graph(self, *_a, **_k):
            from lib.kado_client import KadoError

            raise KadoError("graph unavailable in this fake")

    monkeypatch.setattr(moc_discovery, "_build_kado_client", lambda: _FakeKado())
    target = tmp_path / "report.json"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = moc_discovery.main([
            "--config", str(tmp_path / "cfg.yaml"), "--cache", str(tmp_path / "cache.yaml"),
            "--squelch-state", str(tmp_path / "squelch.json"), "--output", str(target),
        ])

    assert code == 0
    assert out.getvalue() == ""
    report = json.loads(target.read_text(encoding="utf-8"))
    assert [c["topic_keywords"][0] for c in report["topic_clusters"]] == ["alpha"]
