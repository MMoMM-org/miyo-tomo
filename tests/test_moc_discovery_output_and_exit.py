#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_output_and_exit.py — exit 0 for skipped duplicates, `--output PATH`.

Live witness (2026-10-29/30): Pass 2 exited 1 whenever D3 dropped duplicate
clusters. Claude Code shows any non-zero exit as an error, so the agent re-ran
Pass 2: Kado link lookups ran twice and the squelch registry was decremented
twice. A report-bearing run now exits 0, and `--output` writes the report to a
file so the agent never captures 35 KB of JSON through stdout.
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
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "moc_discovery_output_and_exit", SCRIPTS_DIR / "moc-discovery.py"
)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery_output_and_exit"] = moc_discovery
_spec.loader.exec_module(moc_discovery)

NOTES = "Atlas/202 Notes"


class _FakeKado:
    attempt_count = 0
    attempt_gate = None
    min_interval = 0.0

    def read_note(self, path: str) -> dict:  # pragma: no cover
        return {"content": "# stub\n"}

    def graph(self, *_a, **_k):
        from lib.kado_client import KadoError

        raise KadoError("graph unavailable in this fake")


def _inputs(tmp_path: Path, notes: list[dict]) -> list[str]:
    cfg = {"profile": "miyo", "concepts": {"atomic_note": {"path": f"{NOTES}/"}},
           "tomo": {"moc_proposal": {"min_notes": 2, "confidence_threshold": 0.10}}}
    (tmp_path / "vault-config.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
    moc = {"path": "Atlas/200 Maps/Hub.md", "stem": "Hub", "kind": "moc", "title": "Hub",
           "topics": ["hub"], "up_state": "valid"}
    cache = {"moc_cache_version": 1,
             "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "ttl_days": 1, "scope_paths": [], "exclude_paths": [],
             "moc_tag": "type/others/moc", "entries": [moc, *notes], "placeholder_links": []}
    (tmp_path / "cache.yaml").write_text(yaml.dump(cache), encoding="utf-8")
    (tmp_path / "squelch.json").write_text(
        json.dumps({"schema_version": "1", "last_run_id": "", "rejections": []}),
        encoding="utf-8")
    return ["--config", str(tmp_path / "vault-config.yaml"), "--cache", str(tmp_path / "cache.yaml"),
            "--squelch-state", str(tmp_path / "squelch.json")]


def _note(stem: str, topics: list[str]) -> dict:
    return {"path": f"{NOTES}/{stem}.md", "stem": stem, "kind": "note", "title": stem,
            "topics": topics, "up_state": "absent"}


# Two topics over the same three notes → two clusters, D3 drops one as a duplicate.
OVERLAPPING = [_note(f"Note {i}", ["alpha", "beta"]) for i in range(3)]


def _run(monkeypatch, argv: list[str]) -> tuple[int, str]:
    monkeypatch.setattr(moc_discovery, "_build_kado_client", lambda: _FakeKado())
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = moc_discovery.main(argv)
    return code, out.getvalue()


def test_run_with_skipped_duplicates_exits_0(tmp_path: Path, monkeypatch):
    code, stdout = _run(monkeypatch, _inputs(tmp_path, OVERLAPPING))

    report = json.loads(stdout)
    assert report["duplicates_skipped"] and report["topic_clusters"]
    assert code == 0


def test_output_writes_the_report_to_the_file_and_nothing_to_stdout(tmp_path: Path, monkeypatch):
    argv = _inputs(tmp_path, OVERLAPPING)
    _, expected = _run(monkeypatch, argv)
    target = tmp_path / "report.json"

    code, stdout = _run(monkeypatch, [*argv, "--output", str(target)])

    assert code == 0
    assert stdout == ""
    report = json.loads(target.read_text(encoding="utf-8"))
    expected_report = json.loads(expected)
    for d in (report, expected_report):
        d.pop("run_id")
    assert report == expected_report
    assert not (tmp_path / "report.json.tmp").exists()


def test_output_carries_an_abort_report_with_exit_0(tmp_path: Path, monkeypatch):
    target = tmp_path / "report.json"

    code, _ = _run(monkeypatch, [*_inputs(tmp_path, []), "--output", str(target)])

    assert code == 0
    assert json.loads(target.read_text(encoding="utf-8"))["abort_reason"] == "zero-candidates"


def test_output_on_a_fatal_run_removes_an_old_report(tmp_path: Path, monkeypatch):
    target = tmp_path / "report.json"
    target.write_text('{"stale": true}', encoding="utf-8")
    argv = [*_inputs(tmp_path, OVERLAPPING), "--profile", "no-such-profile",
            "--output", str(target)]

    code, _ = _run(monkeypatch, argv)

    assert code == 2
    assert not target.exists()


def test_output_with_emit_phase1_is_refused(tmp_path: Path, monkeypatch):
    target = tmp_path / "report.json"
    argv = [*_inputs(tmp_path, OVERLAPPING), "--emit-phase1", str(tmp_path / "p1.json"),
            "--output", str(target)]

    code, _ = _run(monkeypatch, argv)

    assert code == 2
    assert not target.exists()
    assert not (tmp_path / "p1.json").exists()
