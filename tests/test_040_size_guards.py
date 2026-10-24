#!/usr/bin/env python3
# version: 0.1.0
"""test_040_size_guards.py — spec 040 T1.5: size guards replace budget shedding.

No analyst reads `mocs` whole any more, so the builder must stop deleting
headings, callouts and topics to meet a file budget (SDD ADR-4, PRD F2-AC2).
`size_guards` warns per read instead, and the summary line carries the SDD's
field list (C1-AC1).

Mechanisms falsified:
  - any shedding pass left in place  → test_512_mocs_keep_their_full_detail
  - a guard that sheds or mutates    → test_size_guards_never_alter_the_context
  - a file-level instead of per-read guard, or a silent one
                                     → test_names_over_threshold_warns_once_and_still_writes
  - the old summary keys             → test_summary_line_carries_exactly_the_sdd_fields
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("shared_ctx_builder_040g", SCRIPTS_DIR / "shared-ctx-builder.py")
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder_040g"] = scb
_spec.loader.exec_module(scb)

FOLDER = "Atlas/200 Maps/"
SUMMARY_KEYS = [
    "mocs_total", "mocs_after_reconcile", "mocs_reconcile_dropped",
    "eligible", "excluded", "collisions", "names_bytes", "detail_bytes",
    "tag_prefixes_included", "classification_categories", "placeholder_targets",
    "daily_notes_enabled", "asset_folder", "bytes", "run_id",
]


def _entry(path: str, title: str, tags=None, inventory=True) -> dict:
    entry = {
        "path": path,
        "title": title,
        "topics": [f"{title.lower()} {j}" for j in range(6)],
        "tags": tags or ["type/others/moc"],
    }
    if inventory:
        entry["headings"] = [{"text": f"{title} heading {j}", "level": 2} for j in range(10)]
        entry["editable_callouts"] = [f"> [!blocks]- {title} callout {j}" for j in range(4)]
        entry["has_footer"] = True
    return entry


def _scale_cache(inventory=True) -> dict:
    """512 eligible MOCs as in #173: 256 titles, each held by two paths, plus 2 excluded."""
    notes = []
    for i in range(256):
        title = f"Topic {i:03d} (MOC)"
        notes.append(_entry(f"{FOLDER}{title}.md", title, inventory=inventory))
        notes.append(_entry(f"Efforts/Area {i:03d}/{title}.md", title, inventory=inventory))
    notes.append(_entry(f"{FOLDER}000 Index.md", "000 Index", tags=["MiYo/Tomo/exclude/moc"]))
    notes.append(_entry(f"{FOLDER}001 Hub.md", "001 Hub", tags=["#MiYo/Tomo/exclude/moc"]))
    return {"map_notes": notes}


def _build(tmp_path: Path, cache: dict, *extra: str) -> subprocess.CompletedProcess:
    (tmp_path / "cache.yaml").write_text(yaml.safe_dump(cache), encoding="utf-8")
    (tmp_path / "vault-config.yaml").write_text(yaml.safe_dump({
        "profile": "miyo",
        "tags": {"prefixes": {}},
        "concepts": {"map_note": {"paths": [FOLDER], "tags": ["type/others/moc"]}},
    }), encoding="utf-8")
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "shared-ctx-builder.py"),
        "--cache", str(tmp_path / "cache.yaml"),
        "--vault-config", str(tmp_path / "vault-config.yaml"),
        "--profiles-dir", str(REPO_ROOT / "tomo" / "profiles"),
        "--run-id", "r040g", "--output", str(tmp_path / "ctx.json"), "--skip-reconcile",
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def _compact_len(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _summary(stderr: str) -> str:
    return [ln for ln in stderr.splitlines() if ln.startswith("mocs_total=")][-1]


def test_512_mocs_keep_their_full_detail(tmp_path):
    cache = _scale_cache()
    out = _build(tmp_path, cache)
    assert out.returncode == 0, out.stderr
    ctx = json.loads((tmp_path / "ctx.json").read_text())
    by_path = {e["path"]: e for e in cache["map_notes"]}
    assert len(ctx["mocs"]) == 512
    for moc in ctx["mocs"]:
        src = by_path[moc["path"]]
        assert moc["headings"] == src["headings"][:scb._HEADINGS_CAP], moc["path"]
        assert moc["editable_callouts"] == src["editable_callouts"][:scb._CALLOUTS_CAP], moc["path"]
        assert moc["topics"] == src["topics"], moc["path"]


def test_names_over_threshold_warns_once_and_still_writes(tmp_path):
    cache = _scale_cache(inventory=False)
    first = _build(tmp_path, cache, "--max-bytes", "1000000")
    assert first.returncode == 0, first.stderr
    ctx = json.loads((tmp_path / "ctx.json").read_text())
    names_bytes = _compact_len([m["name"] for m in ctx["mocs"]])
    detail_bytes = 20 * max(_compact_len(m) for m in ctx["mocs"])
    assert names_bytes > detail_bytes  # fixture: only the names read crosses the threshold below

    (tmp_path / "ctx.json").unlink()
    out = _build(tmp_path, cache, "--max-bytes", str(names_bytes - 1))
    assert out.returncode == 0, out.stderr
    warns = [ln for ln in out.stderr.splitlines() if ln.startswith("WARN:")]
    assert len(warns) == 1, warns
    assert "names" in warns[0] and str(names_bytes) in warns[0]
    assert (tmp_path / "ctx.json").exists()
    assert f"names_bytes={names_bytes} " in _summary(out.stderr)


def test_summary_line_carries_exactly_the_sdd_fields(tmp_path):
    out = _build(tmp_path, _scale_cache())
    assert out.returncode == 0, out.stderr
    line = _summary(out.stderr)
    assert re.findall(r"(?:^| )([a-z_]+)=", line) == SUMMARY_KEYS
    assert " eligible=512 " in line
    assert " excluded=2 " in line
    assert " collisions=256 " in line


def test_max_bytes_default_is_32768():
    args = scb.build_arg_parser().parse_args(["--cache", "x", "--vault-config", "y", "--output", "z"])
    assert args.max_bytes == 32768


def test_size_guards_are_quiet_under_the_threshold():
    ctx = {"mocs": [{"name": "A", "path": "a.md", "title": "A", "topics": ["a"]}],
           "tag_prefixes": [], "classification_keywords": {}, "asset_folder": "x/",
           "placeholder_targets": []}
    assert scb.size_guards(ctx, 32768) == []


def test_size_guards_never_alter_the_context():
    """Guard: curated tracker keyword lists — and everything else — leave untouched."""
    ctx = {
        "mocs": [{"name": f"M{i}", "path": f"m{i}.md", "title": f"M{i}",
                  "topics": [f"t{j}" for j in range(40)],
                  "headings": [{"text": f"H{j}", "level": 2} for j in range(8)],
                  "editable_callouts": [f"c{j}" for j in range(5)]} for i in range(40)],
        "tag_prefixes": [], "classification_keywords": {}, "asset_folder": "x/",
        "placeholder_targets": ["Weinbau (MOC)"],
        "daily_notes": {"trackers_enabled": True, "tracker_fields": [{
            "name": "Sport", "keywords": ["sport"], "description": "Did physical exercise today.",
            "positive_keywords": ["laufen", "joggen"], "negative_keywords": ["video"], "active": True}]},
    }
    before = copy.deepcopy(ctx)
    warns = scb.size_guards(ctx, 1)
    assert {w.split("'")[1] for w in warns} == {"names", "step1", "placeholder_targets", "detail"}
    assert ctx == before
